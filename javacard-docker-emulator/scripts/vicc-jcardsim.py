#!/usr/bin/env python3
"""
vicc-jcardsim.py - Virtual ICC that relays APDUs to jCardSim

This script implements a virtual smart card that connects to the
VPCD (Virtual PCD) driver and relays all APDUs to jCardSim.
"""

import os
import socket
import struct
import time
import sys

JCARDSIM_HOST = os.getenv('JCARDSIM_HOST', 'jcardsim')
JCARDSIM_PORT = int(os.getenv('JCARDSIM_PORT', '9025'))
VPCD_HOST = os.getenv('VPCD_HOST', 'localhost')
VPCD_PORT = int(os.getenv('VPCD_PORT', '35963'))

# Standard ATR for jCardSim
ATR = bytes.fromhex('3B6800000073C84012009000')

# VPCD Commands
CYCLIC_POWER_OFF = 0x00
CYCLIC_RESET = 0x01
CYCLIC_GET_ATR = 0x02
CYCLIC_APDU = 0x03


def connect_jcardsim():
    """Connect to jCardSim."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((JCARDSIM_HOST, JCARDSIM_PORT))
    print(f"[VICC] Connected to jCardSim at {JCARDSIM_HOST}:{JCARDSIM_PORT}")
    return sock


def send_apdu_to_jcardsim(jc_sock, apdu):
    """Send APDU to jCardSim and return response."""
    # jCardSim protocol: 2 bytes length (big-endian) + APDU
    length = struct.pack('>H', len(apdu))
    jc_sock.sendall(length + apdu)

    # Read response: 2 bytes length + response
    resp_len_bytes = jc_sock.recv(2)
    if not resp_len_bytes:
        return b'\x6F\x00'  # General error

    resp_len = struct.unpack('>H', resp_len_bytes)[0]
    response = b''
    while len(response) < resp_len:
        chunk = jc_sock.recv(resp_len - len(response))
        if not chunk:
            break
        response += chunk

    return response


def recv_exact(sock, n):
    """Receive exactly n bytes."""
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


def main():
    print("=" * 50)
    print("  Virtual ICC - jCardSim Relay")
    print("=" * 50)
    print(f"  jCardSim: {JCARDSIM_HOST}:{JCARDSIM_PORT}")
    print(f"  VPCD: {VPCD_HOST}:{VPCD_PORT}")
    print("=" * 50)

    # Try to connect to VPCD
    print(f"[VICC] Connecting to VPCD at {VPCD_HOST}:{VPCD_PORT}...")

    vpcd = None
    for attempt in range(60):
        try:
            vpcd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            vpcd.settimeout(10)
            vpcd.connect((VPCD_HOST, VPCD_PORT))
            print(f"[VICC] Connected to VPCD!")
            break
        except Exception as e:
            if attempt % 5 == 0:
                print(f"[VICC] Waiting for VPCD... ({attempt+1}/60) - {e}")
            time.sleep(2)
            vpcd = None

    if not vpcd:
        print("[VICC] Failed to connect to VPCD")
        sys.exit(1)

    jc_sock = None
    card_powered = False

    print("[VICC] Virtual card ready, waiting for commands...")

    while True:
        try:
            # Read command length from VPCD (2 bytes, big-endian)
            length_bytes = recv_exact(vpcd, 2)
            if not length_bytes:
                print("[VICC] VPCD connection closed")
                break

            length = struct.unpack('>H', length_bytes)[0]
            if length == 0:
                continue

            # Read command data
            data = recv_exact(vpcd, length)
            if not data:
                print("[VICC] Failed to read command data")
                break

            cmd = data[0]
            response = None

            # Process VPCD command
            if cmd == CYCLIC_POWER_OFF:
                print("[VICC] Power OFF")
                card_powered = False
                if jc_sock:
                    try:
                        jc_sock.close()
                    except:
                        pass
                    jc_sock = None
                response = b'\x00'  # Success

            elif cmd == CYCLIC_RESET:
                print("[VICC] Reset")
                card_powered = True
                try:
                    if jc_sock:
                        jc_sock.close()
                    jc_sock = connect_jcardsim()
                    response = b'\x00'  # Success
                except Exception as e:
                    print(f"[VICC] Reset failed: {e}")
                    response = b'\x01'  # Error

            elif cmd == CYCLIC_GET_ATR:
                print(f"[VICC] Get ATR -> {ATR.hex().upper()}")
                if not card_powered:
                    card_powered = True
                    try:
                        jc_sock = connect_jcardsim()
                    except Exception as e:
                        print(f"[VICC] Connection to jCardSim failed: {e}")
                response = ATR

            elif cmd == CYCLIC_APDU:
                apdu = data[1:]
                print(f"[VICC] APDU: {apdu.hex().upper()}")

                # Connect to jCardSim if not connected
                if not jc_sock:
                    try:
                        jc_sock = connect_jcardsim()
                    except Exception as e:
                        print(f"[VICC] Connection failed: {e}")
                        response = b'\x6F\x00'
                        resp_length = struct.pack('>H', len(response))
                        vpcd.sendall(resp_length + response)
                        continue

                # Send APDU to jCardSim
                try:
                    response = send_apdu_to_jcardsim(jc_sock, apdu)
                    print(f"[VICC] Response: {response.hex().upper()}")
                except Exception as e:
                    print(f"[VICC] APDU error: {e}")
                    jc_sock = None
                    response = b'\x6F\x00'

            else:
                print(f"[VICC] Unknown command: {cmd:02X}")
                response = b'\x01'  # Error

            # Send response to VPCD
            if response is not None:
                resp_length = struct.pack('>H', len(response))
                vpcd.sendall(resp_length + response)

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            print("\n[VICC] Interrupted")
            break
        except Exception as e:
            print(f"[VICC] Error: {e}")
            import traceback
            traceback.print_exc()
            break

    # Cleanup
    if vpcd:
        vpcd.close()
    if jc_sock:
        jc_sock.close()

    print("[VICC] Shutdown complete")


if __name__ == '__main__':
    main()
