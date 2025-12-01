#!/usr/bin/env python3
"""
vpcd-jcardsim-proxy.py - Proxy entre VPCD (PC/SC) et jCardSim

Ce proxy implémente le protocole VPCD (Virtual PCD) et transmet
les commandes APDU à jCardSim via son socket TCP.

Protocole VPCD:
- vpcd se connecte au proxy sur le port 35963
- Le proxy répond aux commandes VPCD (power on/off, ATR, APDU)
- Les APDUs sont transmis à jCardSim

Protocole jCardSim:
- 2 bytes big-endian pour la longueur
- Puis les données APDU
"""

import os
import socket
import struct
import sys
import threading
import time

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', buffering=1)

# Configuration
VPCD_PORT = int(os.getenv('VPCD_PORT', '35963'))
JCARDSIM_HOST = os.getenv('JCARDSIM_HOST', 'jcardsim')
JCARDSIM_PORT = int(os.getenv('JCARDSIM_PORT', '9025'))

# Commandes VPCD (protocole vsmartcard)
VPCD_CTRL_OFF = 0
VPCD_CTRL_ON = 1
VPCD_CTRL_RESET = 2
VPCD_CTRL_ATR = 4

# ATR par défaut - ATR simple T=0
# Format: 3B [T0] [historical bytes...]
# 3B = TS (direct convention)
# 00 = T0 (no interface bytes, no historical bytes) = T=0 protocol
# Simple et compatible avec vpcd
DEFAULT_ATR = bytes.fromhex('3B00')


class JCardSimClient:
    """Client pour communiquer avec jCardSim."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.lock = threading.Lock()

    def connect(self):
        """Se connecte à jCardSim."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            print(f"Connected to jCardSim at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"Failed to connect to jCardSim: {e}")
            self.socket = None
            return False

    def disconnect(self):
        """Ferme la connexion."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def send_apdu(self, apdu):
        """Envoie un APDU à jCardSim et retourne la réponse."""
        with self.lock:
            if not self.socket:
                if not self.connect():
                    return bytes([0x6F, 0x00])  # Erreur interne

            try:
                # Envoyer: longueur (2 bytes) + APDU
                length = struct.pack('>H', len(apdu))
                self.socket.sendall(length + apdu)

                # Recevoir la réponse
                resp_length_bytes = self._recv_exact(2)
                if not resp_length_bytes:
                    raise ConnectionError("No response from jCardSim")

                resp_length = struct.unpack('>H', resp_length_bytes)[0]
                response = self._recv_exact(resp_length)

                return response if response else bytes([0x6F, 0x00])

            except Exception as e:
                print(f"APDU error: {e}")
                self.disconnect()
                return bytes([0x6F, 0x00])

    def _recv_exact(self, length):
        """Reçoit exactement 'length' bytes."""
        data = b''
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return data


class VPCDHandler:
    """Gère une connexion VPCD (depuis pcscd)."""

    def __init__(self, client_socket, jcardsim):
        self.client = client_socket
        self.jcardsim = jcardsim
        self.powered_on = False

    def handle(self):
        """Traite les commandes VPCD."""
        print("VPCD client connected", flush=True)

        try:
            while True:
                # Lire la longueur (2 bytes big-endian)
                length_bytes = self._recv_exact(2)
                if not length_bytes:
                    print("  No data received, closing", flush=True)
                    break

                length = struct.unpack('>H', length_bytes)[0]
                print(f"  Received length: {length}", flush=True)

                if length == 1:
                    # Commande de contrôle (length=1 signifie commande VPCD)
                    ctrl = self._recv_exact(1)
                    if not ctrl:
                        break
                    self._handle_control(ctrl[0])
                elif length > 1:
                    # Commande APDU
                    apdu = self._recv_exact(length)
                    if not apdu:
                        break
                    self._handle_apdu(apdu)
                else:
                    # length == 0, rien à faire
                    pass

        except Exception as e:
            print(f"VPCD handler error: {e}")
        finally:
            self.client.close()
            print("VPCD client disconnected")

    def _handle_control(self, ctrl):
        """Gère les commandes de contrôle VPCD."""
        if ctrl == VPCD_CTRL_OFF:
            print("  VPCD: Power OFF", flush=True)
            self.powered_on = False
            # Pas de réponse pour Power OFF

        elif ctrl == VPCD_CTRL_ON:
            print("  VPCD: Power ON", flush=True)
            self.powered_on = True
            # Pas de réponse pour Power ON

        elif ctrl == VPCD_CTRL_RESET:
            print("  VPCD: Reset", flush=True)
            self.powered_on = True
            # Pas de réponse pour Reset

        elif ctrl == VPCD_CTRL_ATR:
            print("  VPCD: Get ATR", flush=True)
            # Seul ATR envoie une réponse
            self._send_response(DEFAULT_ATR)

        else:
            print(f"  VPCD: Unknown control {ctrl}", flush=True)
            # Pas de réponse pour commande inconnue

    def _handle_apdu(self, apdu):
        """Transmet un APDU à jCardSim."""
        print(f"  VPCD APDU: {apdu.hex().upper()}")

        if not self.powered_on:
            print("  Card not powered on!")
            self._send_response(bytes([0x69, 0x00]))
            return

        # Transmettre à jCardSim
        response = self.jcardsim.send_apdu(apdu)
        print(f"  Response: {response.hex().upper()}")

        self._send_response(response)

    def _send_response(self, data):
        """Envoie une réponse au client VPCD."""
        length = struct.pack('>H', len(data))
        self.client.sendall(length + data)

    def _recv_exact(self, length):
        """Reçoit exactement 'length' bytes."""
        data = b''
        while len(data) < length:
            try:
                chunk = self.client.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            except:
                return None
        return data


class VPCDServer:
    """Serveur VPCD qui accepte les connexions de pcscd."""

    def __init__(self, port, jcardsim):
        self.port = port
        self.jcardsim = jcardsim
        self.server_socket = None
        self.running = False

    def start(self):
        """Démarre le serveur."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('0.0.0.0', self.port))
        self.server_socket.listen(5)
        self.running = True

        print(f"VPCD proxy server listening on port {self.port}")
        print(f"Forwarding APDUs to jCardSim at {JCARDSIM_HOST}:{JCARDSIM_PORT}")

        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"VPCD connection from {addr}", flush=True)

                handler = VPCDHandler(client, self.jcardsim)
                thread = threading.Thread(target=handler.handle)
                thread.daemon = True
                thread.start()

            except Exception as e:
                if self.running:
                    print(f"Server error: {e}")

    def stop(self):
        """Arrête le serveur."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


def main():
    print("=" * 60)
    print("  VPCD-jCardSim Proxy")
    print("=" * 60)
    print(f"VPCD Port: {VPCD_PORT}")
    print(f"jCardSim: {JCARDSIM_HOST}:{JCARDSIM_PORT}")
    print("=" * 60)

    # Attendre que jCardSim soit disponible
    print("\nWaiting for jCardSim...")
    for i in range(30):
        try:
            sock = socket.socket()
            sock.settimeout(2)
            sock.connect((JCARDSIM_HOST, JCARDSIM_PORT))
            sock.close()
            print("jCardSim is ready!")
            break
        except:
            print(f"  Attempt {i+1}/30...")
            time.sleep(2)
    else:
        print("ERROR: jCardSim not available")
        sys.exit(1)

    # Créer le client jCardSim
    jcardsim = JCardSimClient(JCARDSIM_HOST, JCARDSIM_PORT)

    # Démarrer le serveur VPCD
    server = VPCDServer(VPCD_PORT, jcardsim)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop()
        jcardsim.disconnect()


if __name__ == '__main__':
    main()
