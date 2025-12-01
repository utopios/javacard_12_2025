#!/usr/bin/env python3
"""
jcardsim-socket-server.py - Serveur socket pour jCardSim

Ce script lance jCardSim et expose un serveur socket TCP pour
permettre l'envoi de commandes APDU à distance.

Protocole:
- Client envoie: 2 bytes (big-endian) longueur + APDU
- Serveur répond: 2 bytes (big-endian) longueur + Response
"""

import os
import socket
import struct
import subprocess
import sys
import threading
import time
from typing import Optional

# Configuration
HOST = os.getenv('JCARDSIM_HOST', '0.0.0.0')
PORT = int(os.getenv('JCARDSIM_PORT', '9025'))


class JCardSimProcess:
    """Gère le processus jCardSim."""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.process: Optional[subprocess.Popen] = None
        self.input_pipe = None
        self.output_pipe = None
    
    def start(self):
        """Démarre jCardSim en mode console."""
        classpath = self._build_classpath()
        
        cmd = [
            'java',
            '-cp', classpath,
            'com.licel.jcardsim.utils.APDUScriptTool'
        ]
        
        if self.config_file:
            cmd.append(self.config_file)
        
        print(f"Starting jCardSim: {' '.join(cmd)}")
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False
        )
        
        # Attendre que jCardSim soit prêt
        time.sleep(2)
        
        if self.process.poll() is not None:
            stderr = self.process.stderr.read().decode()
            raise RuntimeError(f"jCardSim failed to start: {stderr}")
        
        print("jCardSim started successfully")
    
    def _build_classpath(self) -> str:
        """Construit le classpath Java."""
        jars = []
        lib_dir = '/app/lib'
        
        if os.path.exists(lib_dir):
            for f in os.listdir(lib_dir):
                if f.endswith('.jar'):
                    jars.append(os.path.join(lib_dir, f))
        
        # Ajouter les applets
        applets_dir = '/app/applets'
        if os.path.exists(applets_dir):
            for f in os.listdir(applets_dir):
                if f.endswith('.jar'):
                    jars.append(os.path.join(applets_dir, f))
        
        return ':'.join(jars)
    
    def send_apdu(self, apdu: bytes) -> bytes:
        """Envoie un APDU à jCardSim et retourne la réponse."""
        if not self.process:
            return b'\x6F\x00'  # Erreur
        
        try:
            # Format pour APDUScriptTool: hex string + newline
            apdu_hex = apdu.hex().upper()
            self.process.stdin.write(f"{apdu_hex}\n".encode())
            self.process.stdin.flush()
            
            # Lire la réponse (hex string)
            response_line = self.process.stdout.readline().decode().strip()
            
            # Parser la réponse
            if response_line:
                # Enlever les préfixes/suffixes éventuels
                response_hex = ''.join(c for c in response_line if c in '0123456789ABCDEFabcdef')
                if response_hex:
                    return bytes.fromhex(response_hex)
            
            return b'\x6F\x00'
            
        except Exception as e:
            print(f"APDU error: {e}")
            return b'\x6F\x00'
    
    def stop(self):
        """Arrête jCardSim."""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None


class SimpleCardSimulator:
    """Simulateur de carte simple pour les tests de base."""

    # AIDs des applets
    AID_HELLOWORLD = bytes.fromhex('F0000000010001')
    AID_COUNTER = bytes.fromhex('F0000000010002')

    def __init__(self):
        self.selected_aid = None
        self.applets = {}
        self.data_store = {}

        # État HelloWorld
        self.hw_pin_validated = False
        self.hw_pin_tries = 3
        self.hw_usage_count = 0

        # État Counter
        self.counter_value = 0
        self.counter_limit = 0x7FFFFFFF
        self.counter_limit_enabled = False
        self.counter_op_count = 0

        # ATR par défaut
        self.atr = bytes.fromhex('3B8F8001804F0CA000000306030001000000006A')

    def process_apdu(self, apdu: bytes) -> bytes:
        """Traite un APDU et retourne la réponse."""
        if len(apdu) < 4:
            return b'\x67\x00'  # Wrong length

        cla = apdu[0]
        ins = apdu[1]
        p1 = apdu[2]
        p2 = apdu[3]
        lc = apdu[4] if len(apdu) > 4 else 0
        data = apdu[5:5+lc] if len(apdu) > 5 else b''

        # SELECT command
        if ins == 0xA4:
            return self._handle_select(apdu)

        # GET RESPONSE
        if ins == 0xC0:
            return b'\x90\x00'

        # Commandes propriétaires (CLA = 0x80)
        if cla == 0x80:
            # Dispatcher selon l'applet sélectionné
            if self.selected_aid == self.AID_HELLOWORLD:
                return self._process_helloworld(ins, p1, p2, data)
            elif self.selected_aid == self.AID_COUNTER:
                return self._process_counter(ins, p1, p2, data)

        return b'\x6D\x00'  # Instruction not supported

    def _process_helloworld(self, ins, p1, p2, data) -> bytes:
        """Commandes HelloWorld Applet."""
        self.hw_usage_count += 1

        if ins == 0x00:  # HELLO
            return b'Hello World!\x90\x00'

        elif ins == 0x01:  # ECHO
            if data:
                return data + b'\x90\x00'
            return b'\x90\x00'

        elif ins == 0x02:  # GET_DATA
            stored = self.data_store.get('hw_data', b'')
            if stored:
                return stored + b'\x90\x00'
            return b'\x69\x85'  # Conditions not satisfied

        elif ins == 0x03:  # PUT_DATA
            if not self.hw_pin_validated:
                return b'\x69\x85'  # Security status not satisfied
            if data:
                self.data_store['hw_data'] = data
            return b'\x90\x00'

        elif ins == 0x20:  # VERIFY PIN
            if data == b'1234':
                self.hw_pin_validated = True
                self.hw_pin_tries = 3
                return b'\x90\x00'
            else:
                self.hw_pin_tries = max(0, self.hw_pin_tries - 1)
                return bytes([0x63, 0xC0 | self.hw_pin_tries])

        elif ins == 0xF0:  # GET STATUS
            data_len = len(self.data_store.get('hw_data', b''))
            status = bytes([
                0x01, 0x00,  # Version
                (self.hw_usage_count >> 8) & 0xFF, self.hw_usage_count & 0xFF,
                self.hw_pin_tries,
                0x01 if self.hw_pin_validated else 0x00,
                (data_len >> 8) & 0xFF, data_len & 0xFF
            ])
            return status + b'\x90\x00'

        return b'\x6D\x00'

    def _process_counter(self, ins, p1, p2, data) -> bytes:
        """Commandes Counter Applet."""
        self.counter_op_count += 1

        def counter_bytes():
            return self.counter_value.to_bytes(4, 'big')

        if ins == 0x10:  # GET_COUNTER
            return counter_bytes() + b'\x90\x00'

        elif ins == 0x11:  # INCREMENT
            inc = p1 if p1 > 0 else 1
            new_val = self.counter_value + inc
            if self.counter_limit_enabled and new_val > self.counter_limit:
                return b'\x69\x85'  # Conditions not satisfied
            if new_val > 0xFFFFFFFF:
                return b'\x69\x85'
            self.counter_value = new_val
            return counter_bytes() + b'\x90\x00'

        elif ins == 0x12:  # DECREMENT
            dec = p1 if p1 > 0 else 1
            if self.counter_value < dec:
                return b'\x69\x85'
            self.counter_value -= dec
            return counter_bytes() + b'\x90\x00'

        elif ins == 0x13:  # RESET
            self.counter_value = 0
            return b'\x90\x00'

        elif ins == 0x14:  # SET_VALUE
            if len(data) != 4:
                return b'\x67\x00'
            new_val = int.from_bytes(data, 'big')
            if self.counter_limit_enabled and new_val > self.counter_limit:
                return b'\x69\x85'
            self.counter_value = new_val
            return b'\x90\x00'

        elif ins == 0x15:  # SET_LIMIT
            if len(data) != 4:
                return b'\x67\x00'
            self.counter_limit = int.from_bytes(data, 'big')
            self.counter_limit_enabled = (p1 == 0x01)
            return b'\x90\x00'

        elif ins == 0x16:  # GET_INFO
            result = counter_bytes()
            result += self.counter_limit.to_bytes(4, 'big')
            result += bytes([0x01 if self.counter_limit_enabled else 0x00])
            result += self.counter_op_count.to_bytes(2, 'big')
            return result + b'\x90\x00'

        elif ins == 0x17:  # ADD_VALUE
            if len(data) != 2:
                return b'\x67\x00'
            add_val = int.from_bytes(data, 'big')
            new_val = self.counter_value + add_val
            if self.counter_limit_enabled and new_val > self.counter_limit:
                return b'\x69\x85'
            if new_val > 0xFFFFFFFF:
                return b'\x69\x85'
            self.counter_value = new_val
            return counter_bytes() + b'\x90\x00'

        elif ins == 0x18:  # SUB_VALUE
            if len(data) != 2:
                return b'\x67\x00'
            sub_val = int.from_bytes(data, 'big')
            if self.counter_value < sub_val:
                return b'\x69\x85'
            self.counter_value -= sub_val
            return counter_bytes() + b'\x90\x00'

        return b'\x6D\x00'
    
    def _handle_select(self, apdu: bytes) -> bytes:
        """Gère la commande SELECT."""
        if len(apdu) < 5:
            return b'\x67\x00'
        
        lc = apdu[4]
        if len(apdu) < 5 + lc:
            return b'\x67\x00'
        
        aid = apdu[5:5+lc]
        self.selected_aid = aid
        
        # FCI template simplifié
        fci = bytes([0x6F, len(aid) + 2, 0x84, len(aid)]) + aid
        return fci + b'\x90\x00'


class SocketServer:
    """Serveur socket TCP pour les APDUs."""
    
    def __init__(self, host: str, port: int, simulator):
        self.host = host
        self.port = port
        self.simulator = simulator
        self.server_socket: Optional[socket.socket] = None
        self.running = False
    
    def start(self):
        """Démarre le serveur."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Socket server listening on {self.host}:{self.port}")
        
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"Client connected: {addr}")
                
                # Gérer le client dans un thread
                thread = threading.Thread(target=self._handle_client, args=(client,))
                thread.daemon = True
                thread.start()
                
            except socket.error:
                if self.running:
                    raise
    
    def _handle_client(self, client: socket.socket):
        """Gère un client connecté."""
        try:
            while self.running:
                # Lire la longueur (2 bytes big-endian)
                length_bytes = self._recv_exact(client, 2)
                if not length_bytes:
                    break
                
                length = struct.unpack('>H', length_bytes)[0]
                
                # Lire l'APDU
                apdu = self._recv_exact(client, length)
                if not apdu:
                    break
                
                print(f"← APDU: {apdu.hex().upper()}")
                
                # Traiter l'APDU
                response = self.simulator.process_apdu(apdu)
                
                print(f"→ Response: {response.hex().upper()}")
                
                # Envoyer la réponse
                resp_length = struct.pack('>H', len(response))
                client.sendall(resp_length + response)
                
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            client.close()
            print("Client disconnected")
    
    def _recv_exact(self, sock: socket.socket, length: int) -> Optional[bytes]:
        """Reçoit exactement 'length' bytes."""
        data = b''
        while len(data) < length:
            try:
                chunk = sock.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            except socket.error:
                return None
        return data
    
    def stop(self):
        """Arrête le serveur."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()


class RealJCardSimulator:
    """Simulateur utilisant le vrai jCardSim avec les applets compilés."""

    def __init__(self, config_file: str = '/app/config/jcardsim.cfg'):
        self.config_file = config_file
        self.simulator = None
        self.jpype = None
        self._init_jcardsim()

    def _init_jcardsim(self):
        """Initialise jCardSim via JPype."""
        try:
            import jpype
            import jpype.imports
            self.jpype = jpype

            if not jpype.isJVMStarted():
                classpath = self._build_classpath()
                print(f"Starting JVM with classpath: {classpath}")
                jpype.startJVM(classpath=classpath.split(':'))

            from com.licel.jcardsim.smartcardio import CardSimulator
            from com.licel.jcardsim.utils import AIDUtil
            from javacard.framework import AID

            self.CardSimulator = CardSimulator
            self.AIDUtil = AIDUtil
            self.AID = AID
            self.simulator = CardSimulator()

            # Charger les applets depuis la config
            self._load_applets_from_config()

            print("jCardSim initialized with JPype")

        except ImportError as e:
            print(f"JPype not available ({e}), using fallback SimpleCardSimulator")
            self.simulator = None
        except Exception as e:
            print(f"Failed to initialize jCardSim: {e}")
            import traceback
            traceback.print_exc()
            self.simulator = None

    def _build_classpath(self) -> str:
        """Construit le classpath Java."""
        import os
        jars = []

        for lib_dir in ['/app/lib', '/app/applets']:
            if os.path.exists(lib_dir):
                for f in os.listdir(lib_dir):
                    if f.endswith('.jar'):
                        jars.append(os.path.join(lib_dir, f))

        return ':'.join(jars)

    def _load_applets_from_config(self):
        """Charge les applets définis dans le fichier de config."""
        import os
        import re

        if not os.path.exists(self.config_file):
            print(f"Config file not found: {self.config_file}")
            return

        with open(self.config_file) as f:
            lines = f.readlines()

        applets = {}
        for line in lines:
            line = line.strip()
            if line.startswith('com.licel.jcardsim.card.applet.'):
                parts = line.split('=', 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()

                    # Extraire le numéro d'applet
                    match = re.search(r'applet\.(\d+)\.(AID|Class)', key)
                    if match:
                        idx = match.group(1)
                        prop = match.group(2)
                        if idx not in applets:
                            applets[idx] = {}
                        applets[idx][prop] = value

        # Installer les applets
        for idx, props in sorted(applets.items()):
            if 'AID' in props and 'Class' in props:
                aid_hex = props['AID']
                class_name = props['Class']
                try:
                    # Créer l'AID
                    aid_bytes = bytes.fromhex(aid_hex)
                    aid = self.AID(aid_bytes, 0, len(aid_bytes))

                    # Charger la classe de l'applet
                    applet_class = self.jpype.JClass(class_name)

                    # Installer l'applet
                    self.simulator.installApplet(aid, applet_class)
                    print(f"Installed applet: {class_name} (AID: {aid_hex})")
                except Exception as e:
                    print(f"Failed to install applet {class_name}: {e}")
                    import traceback
                    traceback.print_exc()

    def process_apdu(self, apdu: bytes) -> bytes:
        """Traite un APDU via jCardSim."""
        if self.simulator is None:
            # Fallback vers simulateur simple
            return SimpleCardSimulator().process_apdu(apdu)

        try:
            from javax.smartcardio import CommandAPDU, ResponseAPDU

            # Créer la commande APDU
            cmd = CommandAPDU(bytes(apdu))
            response = self.simulator.transmitCommand(cmd)

            # Construire la réponse complète
            resp_data = response.getData()
            if resp_data is not None and len(resp_data) > 0:
                data = bytes(resp_data)
            else:
                data = b''

            sw1 = response.getSW1() & 0xFF
            sw2 = response.getSW2() & 0xFF

            return data + bytes([sw1, sw2])

        except Exception as e:
            print(f"APDU processing error: {e}")
            import traceback
            traceback.print_exc()
            return b'\x6F\x00'


def main():
    print("=" * 60)
    print("  jCardSim Socket Server")
    print("=" * 60)
    print(f"Host: {HOST}")
    print(f"Port: {PORT}")
    print("=" * 60)

    # Essayer d'utiliser le vrai jCardSim, sinon fallback
    try:
        simulator = RealJCardSimulator()
        if simulator.simulator is None:
            print("Using SimpleCardSimulator (fallback)")
            simulator = SimpleCardSimulator()
    except Exception as e:
        print(f"Failed to init RealJCardSimulator: {e}")
        print("Using SimpleCardSimulator (fallback)")
        simulator = SimpleCardSimulator()

    # Créer et démarrer le serveur socket
    server = SocketServer(HOST, PORT, simulator)

    try:
        server.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.stop()


if __name__ == '__main__':
    main()
