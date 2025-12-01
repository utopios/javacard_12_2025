#!/usr/bin/env python3
"""
pcsc-bridge.py - Bridge entre jCardSim (socket) et PC/SC virtual reader (vpcd)

Ce script crée un pont bidirectionnel entre:
- jCardSim qui expose un serveur socket pour les APDUs
- vpcd (Virtual PC/SC Driver) qui expose un lecteur PC/SC virtuel

Protocole jCardSim Socket:
- Longueur (2 bytes big-endian) + APDU command
- Réponse: Longueur (2 bytes big-endian) + APDU response
"""

import argparse
import logging
import select
import socket
import struct
import sys
import threading
import time
from typing import Optional, Tuple

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Constantes VPCD (Virtual PC/SC Driver)
# ============================================================================
VPCD_CTRL_LEN = 1
VPCD_CTRL_OFF = 0
VPCD_CTRL_ON = 1
VPCD_CTRL_RESET = 2
VPCD_CTRL_ATR = 4

# ATR par défaut pour une JavaCard
DEFAULT_ATR = bytes.fromhex('3B8F8001804F0CA000000306030001000000006A')


class JCardSimClient:
    """Client pour communiquer avec jCardSim via socket."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.lock = threading.Lock()
    
    def connect(self) -> bool:
        """Établit la connexion avec jCardSim."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            logger.info(f"Connected to jCardSim at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to jCardSim: {e}")
            return False
    
    def disconnect(self):
        """Ferme la connexion."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def send_apdu(self, apdu: bytes) -> Optional[bytes]:
        """Envoie un APDU et reçoit la réponse."""
        with self.lock:
            if not self.socket:
                if not self.connect():
                    return None
            
            try:
                # Envoyer la longueur (2 bytes big-endian) puis l'APDU
                length = struct.pack('>H', len(apdu))
                self.socket.sendall(length + apdu)
                
                logger.debug(f"Sent APDU: {apdu.hex().upper()}")
                
                # Recevoir la longueur de la réponse
                resp_len_bytes = self._recv_exact(2)
                if not resp_len_bytes:
                    return None
                
                resp_len = struct.unpack('>H', resp_len_bytes)[0]
                
                # Recevoir la réponse
                response = self._recv_exact(resp_len)
                if response:
                    logger.debug(f"Received response: {response.hex().upper()}")
                
                return response
                
            except Exception as e:
                logger.error(f"APDU exchange failed: {e}")
                self.disconnect()
                return None
    
    def _recv_exact(self, length: int) -> Optional[bytes]:
        """Reçoit exactement 'length' bytes."""
        data = b''
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.timeout:
                logger.error("Receive timeout")
                return None
        return data
    
    def power_on(self) -> bytes:
        """Simule la mise sous tension et retourne l'ATR."""
        # jCardSim ne nécessite pas de commande spéciale pour power on
        # On retourne simplement l'ATR configuré
        return DEFAULT_ATR
    
    def power_off(self):
        """Simule la mise hors tension."""
        pass
    
    def reset(self) -> bytes:
        """Reset de la carte et retourne l'ATR."""
        # Déconnecter et reconnecter pour simuler un reset
        self.disconnect()
        if self.connect():
            return DEFAULT_ATR
        return b''


class VPCDServer:
    """Serveur VPCD qui expose un lecteur PC/SC virtuel."""
    
    def __init__(self, port: int, jcardsim: JCardSimClient):
        self.port = port
        self.jcardsim = jcardsim
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.running = False
        self.powered = False
    
    def start(self):
        """Démarre le serveur VPCD."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(1)
        
        logger.info(f"VPCD server listening on port {self.port}")
        self.running = True
        
        while self.running:
            try:
                # Attendre une connexion de pcscd
                readable, _, _ = select.select([self.server_socket], [], [], 1)
                if not readable:
                    continue
                
                self.client_socket, addr = self.server_socket.accept()
                logger.info(f"pcscd connected from {addr}")
                
                self._handle_client()
                
            except Exception as e:
                logger.error(f"Server error: {e}")
                time.sleep(1)
    
    def _handle_client(self):
        """Gère les communications avec pcscd."""
        while self.running and self.client_socket:
            try:
                # Recevoir la commande de pcscd
                data = self.client_socket.recv(1)
                if not data:
                    logger.info("pcscd disconnected")
                    break
                
                cmd = data[0]
                
                if cmd == VPCD_CTRL_OFF:
                    logger.debug("VPCD: Power OFF")
                    self.jcardsim.power_off()
                    self.powered = False
                    self._send_response(b'\x00')  # OK
                
                elif cmd == VPCD_CTRL_ON:
                    logger.debug("VPCD: Power ON")
                    if self.jcardsim.connect():
                        self.powered = True
                        self._send_response(b'\x00')  # OK
                    else:
                        self._send_response(b'\x01')  # Error
                
                elif cmd == VPCD_CTRL_RESET:
                    logger.debug("VPCD: Reset")
                    atr = self.jcardsim.reset()
                    self.powered = bool(atr)
                    self._send_response(b'\x00' if atr else b'\x01')
                
                elif cmd == VPCD_CTRL_ATR:
                    logger.debug("VPCD: Get ATR")
                    atr = self.jcardsim.power_on() if self.powered else b''
                    # Envoyer la longueur puis l'ATR
                    self._send_response(bytes([len(atr)]) + atr)
                
                else:
                    # C'est un APDU - le premier byte est la longueur
                    apdu_len = cmd
                    if apdu_len > 0:
                        # Recevoir le reste de l'APDU
                        apdu = self._recv_exact(apdu_len)
                        if apdu:
                            logger.debug(f"VPCD: APDU command ({apdu_len} bytes)")
                            # Envoyer à jCardSim
                            response = self.jcardsim.send_apdu(apdu)
                            if response:
                                # Envoyer la longueur puis la réponse
                                self._send_response(bytes([len(response)]) + response)
                            else:
                                # Erreur - envoyer SW 6F00
                                self._send_response(b'\x02\x6F\x00')
                
            except socket.error as e:
                logger.error(f"Socket error: {e}")
                break
            except Exception as e:
                logger.error(f"Handler error: {e}")
                break
        
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
    
    def _send_response(self, data: bytes):
        """Envoie une réponse à pcscd."""
        if self.client_socket:
            try:
                self.client_socket.sendall(data)
            except Exception as e:
                logger.error(f"Send error: {e}")
    
    def _recv_exact(self, length: int) -> Optional[bytes]:
        """Reçoit exactement 'length' bytes."""
        if not self.client_socket:
            return None
        
        data = b''
        while len(data) < length:
            chunk = self.client_socket.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    def stop(self):
        """Arrête le serveur."""
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass


def main():
    parser = argparse.ArgumentParser(description='PC/SC Bridge to jCardSim')
    parser.add_argument('--jcardsim-host', default='localhost',
                        help='jCardSim server host')
    parser.add_argument('--jcardsim-port', type=int, default=9025,
                        help='jCardSim server port')
    parser.add_argument('--vpcd-port', type=int, default=35963,
                        help='VPCD server port')
    
    args = parser.parse_args()
    
    # Créer le client jCardSim
    jcardsim = JCardSimClient(args.jcardsim_host, args.jcardsim_port)
    
    # Créer et démarrer le serveur VPCD
    vpcd = VPCDServer(args.vpcd_port, jcardsim)
    
    try:
        vpcd.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        vpcd.stop()
        jcardsim.disconnect()


if __name__ == '__main__':
    main()
