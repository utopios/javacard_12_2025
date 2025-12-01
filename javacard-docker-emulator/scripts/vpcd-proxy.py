#!/usr/bin/env python3
"""
vpcd-proxy.py - Serveur proxy entre VPCD (Virtual PCD) et jCardSim

Architecture CORRIGEE:
- Ce script est un SERVEUR qui écoute sur le port 35963
- Le driver VPCD (dans pcscd) se CONNECTE à ce port en tant que CLIENT
- Ce script fait le pont vers jCardSim qui écoute sur le port 9025

Protocole VPCD:
- 2 bytes: longueur du message (big-endian)
- N bytes: données

Commandes VPCD:
- CYCLIC_POWER_OFF (0x00): Éteindre la carte
- CYCLIC_RESET (0x01): Reset de la carte
- CYCLIC_GET_ATR (0x02): Obtenir l'ATR
- CYCLIC_APDU (0x03 + data): Envoyer un APDU

Protocole jCardSim:
- 2 bytes: longueur APDU (big-endian)
- N bytes: APDU
- Réponse: 2 bytes longueur + données + SW1 SW2
"""

import os
import socket
import struct
import sys
import threading
import time
import signal

# Force unbuffered output for Docker logs
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Configuration
JCARDSIM_HOST = os.getenv('JCARDSIM_HOST', 'jcardsim')
JCARDSIM_PORT = int(os.getenv('JCARDSIM_PORT', '9025'))
VPCD_PORT = int(os.getenv('VPCD_PORT', '35963'))

# ATR pour jCardSim - supporte T=0 et T=1
# 3B = TS (direct convention)
# 90 = T0: TD1 présent (bit 7=1), 0 historical bytes (bits 0-3=0)
# 95 = TD1: TA2 présent (bit 4), T=1 protocol (bits 0-3 = 5 means specific mode, but we want T=1 = 1)
# Correction: utilisons un ATR connu qui fonctionne avec T=1
# ATR de carte SIM standard supportant T=0: 3B 9F 95 80 1F C3 80 31 E0 73 FE 21 13 57 86 81 02 86 98
# ATR minimaliste T=1: 3B 80 01 - TS=3B, T0=80 (TD1 present), TD1=01 (T=1)
DEFAULT_ATR = bytes.fromhex('3B8001')

# Commandes VPCD
CYCLIC_POWER_OFF = 0x00
CYCLIC_RESET = 0x01
CYCLIC_GET_ATR = 0x02
CYCLIC_APDU = 0x03
CYCLIC_CARD_PRESENT = 0x04  # Card present check

running = True


class JCardSimConnection:
    """Gère la connexion vers jCardSim."""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None
        self.lock = threading.Lock()

    def connect(self):
        """Établit la connexion."""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            print(f"[PROXY] Connected to jCardSim at {self.host}:{self.port}")

    def disconnect(self):
        """Ferme la connexion."""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None

    def send_apdu(self, apdu):
        """Envoie un APDU et retourne la réponse."""
        with self.lock:
            if not self.socket:
                raise Exception("Not connected to jCardSim")

            try:
                # Envoyer: 2 bytes longueur + APDU
                length = struct.pack('>H', len(apdu))
                self.socket.sendall(length + apdu)

                # Recevoir: 2 bytes longueur + réponse
                resp_len_bytes = self._recv_exact(2)
                if not resp_len_bytes:
                    return None

                resp_len = struct.unpack('>H', resp_len_bytes)[0]
                response = self._recv_exact(resp_len)

                return response

            except Exception as e:
                print(f"[PROXY] Error sending APDU: {e}")
                self.socket = None
                raise

    def _recv_exact(self, n):
        """Reçoit exactement n bytes."""
        data = b''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        return data


def recv_exact(sock, n):
    """Reçoit exactement n bytes."""
    data = b''
    while len(data) < n:
        try:
            chunk = sock.recv(n - len(data))
            if not chunk:
                return None
            data += chunk
        except socket.timeout:
            return None
    return data


def handle_vpcd_client(client_socket, client_addr, jcardsim):
    """Gère une connexion depuis le driver VPCD."""
    global running
    card_powered = False

    print(f"[PROXY] VPCD client connected from {client_addr}")
    client_socket.settimeout(60)

    try:
        while running:
            # Lire la longueur du message (2 bytes)
            length_bytes = recv_exact(client_socket, 2)
            if not length_bytes:
                print("[PROXY] VPCD client disconnected")
                break

            length = struct.unpack('>H', length_bytes)[0]

            if length == 0:
                continue

            # Lire les données
            data = recv_exact(client_socket, length)
            if not data:
                break

            # Traiter la commande
            cmd = data[0]
            response = None

            if cmd == CYCLIC_POWER_OFF:
                print("[PROXY] << POWER OFF")
                card_powered = False
                jcardsim.disconnect()
                response = b'\x00'  # Success

            elif cmd == CYCLIC_RESET:
                print("[PROXY] << RESET")
                card_powered = True
                try:
                    jcardsim.connect()
                    # After reset, return ATR directly (not just success code)
                    print(f"[PROXY] >> ATR: {DEFAULT_ATR.hex().upper()}")
                    response = DEFAULT_ATR
                except Exception as e:
                    print(f"[PROXY] Reset failed: {e}")
                    response = b''  # Empty = error

            elif cmd == CYCLIC_GET_ATR:
                print(f"[PROXY] << GET ATR")
                if not card_powered:
                    card_powered = True
                    try:
                        jcardsim.connect()
                    except Exception as e:
                        print(f"[PROXY] Connection failed: {e}")
                print(f"[PROXY] >> ATR: {DEFAULT_ATR.hex().upper()}")
                response = DEFAULT_ATR

            elif cmd == CYCLIC_APDU:
                apdu = data[1:]
                print(f"[PROXY] << APDU: {apdu.hex().upper()}")

                if not card_powered:
                    card_powered = True
                    try:
                        jcardsim.connect()
                    except Exception as e:
                        print(f"[PROXY] Connection failed: {e}")
                        response = b'\x6F\x00'

                if response is None:
                    try:
                        response = jcardsim.send_apdu(apdu)
                        if response:
                            print(f"[PROXY] >> Response: {response.hex().upper()}")
                        else:
                            response = b'\x6F\x00'
                    except Exception as e:
                        print(f"[PROXY] APDU Error: {e}")
                        response = b'\x6F\x00'

            elif cmd == CYCLIC_CARD_PRESENT:
                # Card present check - respond that card is present (0x00 = present)
                print("[PROXY] << CARD PRESENT CHECK")
                response = b'\x00'  # Card is present

            else:
                print(f"[PROXY] << Unknown command: {cmd:02X}")
                response = b'\x01'  # Error

            # Envoyer la réponse
            if response is not None:
                resp_length = struct.pack('>H', len(response))
                client_socket.sendall(resp_length + response)

    except socket.timeout:
        print("[PROXY] VPCD client timeout")
    except Exception as e:
        print(f"[PROXY] Error handling VPCD client: {e}")
    finally:
        client_socket.close()
        print("[PROXY] VPCD client handler finished")


def wait_for_jcardsim(host, port, timeout=60):
    """Attend que jCardSim soit disponible."""
    print(f"[PROXY] Waiting for jCardSim at {host}:{port}...")
    start = time.time()

    while time.time() - start < timeout:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((host, port))
            sock.close()
            print(f"[PROXY] jCardSim is available!")
            return True
        except:
            time.sleep(1)

    return False


def main():
    global running

    print("=" * 50)
    print("  VPCD Proxy SERVER - jCardSim Bridge")
    print("  (Server mode - VPCD driver connects to us)")
    print("=" * 50)
    print(f"  Listening on: 0.0.0.0:{VPCD_PORT}")
    print(f"  jCardSim: {JCARDSIM_HOST}:{JCARDSIM_PORT}")
    print("=" * 50)

    # Attendre jCardSim
    if not wait_for_jcardsim(JCARDSIM_HOST, JCARDSIM_PORT):
        print("[ERROR] jCardSim not available!")
        sys.exit(1)

    # Créer la connexion jCardSim
    jcardsim = JCardSimConnection(JCARDSIM_HOST, JCARDSIM_PORT)

    # Créer le serveur
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', VPCD_PORT))
    server.listen(5)
    server.settimeout(1)

    print(f"[PROXY] Server listening on port {VPCD_PORT}")
    print("[PROXY] Waiting for VPCD driver to connect...")

    # Gestion des signaux
    def signal_handler(sig, frame):
        global running
        print("\n[PROXY] Shutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Boucle principale - accepter les connexions
    while running:
        try:
            client_socket, client_addr = server.accept()
            print(f"[PROXY] New connection from {client_addr}")

            # Gérer le client dans un thread
            client_thread = threading.Thread(
                target=handle_vpcd_client,
                args=(client_socket, client_addr, jcardsim)
            )
            client_thread.daemon = True
            client_thread.start()

        except socket.timeout:
            continue
        except Exception as e:
            if running:
                print(f"[PROXY] Accept error: {e}")

    server.close()
    jcardsim.disconnect()
    print("[PROXY] Server stopped")


if __name__ == '__main__':
    main()
