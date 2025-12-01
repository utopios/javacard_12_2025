#!/usr/bin/env python3
"""
apdu-shell.py - Shell interactif pour les commandes APDU JavaCard

Fonctionnalités:
- Mode interactif avec historique
- Macros pour les commandes courantes
- Support des scripts
- Parsing TLV automatique
- Colorisation de la sortie
"""

import argparse
import os
import readline
import socket
import struct
import sys
from typing import Optional, Dict, List, Tuple


# Configuration
JCARDSIM_HOST = os.getenv('JCARDSIM_HOST', 'localhost')
JCARDSIM_PORT = int(os.getenv('JCARDSIM_PORT', '9025'))

# Couleurs
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


# Macros pré-définies
MACROS: Dict[str, str] = {
    'select_isd': '00A4040008A000000003000000',
    'get_cplc': '80CA9F7F00',
    'get_data': '00CA00{tag:02X}00',
    'init_update': '8050000008{random}00',
}


class TLVParser:
    """Parser pour les données TLV."""
    
    @staticmethod
    def parse(data: bytes, indent: int = 0) -> List[str]:
        """Parse les données TLV et retourne une liste de lignes formatées."""
        lines = []
        i = 0
        prefix = "  " * indent
        
        while i < len(data):
            # Tag (1 ou 2 bytes)
            tag = data[i]
            i += 1
            
            if (tag & 0x1F) == 0x1F:  # Tag sur 2 bytes
                if i >= len(data):
                    break
                tag = (tag << 8) | data[i]
                i += 1
            
            # Longueur
            if i >= len(data):
                break
            
            length = data[i]
            i += 1
            
            if length & 0x80:  # Longueur sur plusieurs bytes
                num_bytes = length & 0x7F
                if i + num_bytes > len(data):
                    break
                length = int.from_bytes(data[i:i+num_bytes], 'big')
                i += num_bytes
            
            # Valeur
            if i + length > len(data):
                break
            
            value = data[i:i+length]
            i += length
            
            # Formater
            tag_hex = f"{tag:04X}" if tag > 0xFF else f"{tag:02X}"
            
            # Essayer de décoder en ASCII si possible
            try:
                if all(32 <= b < 127 for b in value):
                    value_str = f'"{value.decode("ascii")}"'
                else:
                    value_str = value.hex().upper()
            except:
                value_str = value.hex().upper()
            
            lines.append(f"{prefix}Tag {tag_hex} ({length}): {value_str}")
            
            # Parser récursivement si c'est un tag construit
            if tag & 0x20:
                lines.extend(TLVParser.parse(value, indent + 1))
        
        return lines


class APDUShell:
    """Shell interactif APDU."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.history: List[str] = []
        self.macros = MACROS.copy()
        self.verbose = True
        self.parse_tlv = False
        
        # Configurer readline
        self.histfile = os.path.expanduser("~/.apdu_history")
        try:
            readline.read_history_file(self.histfile)
        except FileNotFoundError:
            pass
    
    def connect(self) -> bool:
        """Établit la connexion."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            print(f"{Colors.GREEN}✓ Connected to {self.host}:{self.port}{Colors.END}")
            return True
        except Exception as e:
            print(f"{Colors.RED}✗ Connection failed: {e}{Colors.END}")
            return False
    
    def disconnect(self):
        """Ferme la connexion."""
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def send_apdu(self, apdu_hex: str) -> Tuple[bytes, bytes]:
        """Envoie un APDU."""
        apdu = bytes.fromhex(apdu_hex.replace(' ', '').replace(':', ''))
        
        if not self.socket:
            if not self.connect():
                return b'', b''
        
        try:
            # Envoyer
            length = struct.pack('>H', len(apdu))
            self.socket.sendall(length + apdu)
            
            # Recevoir
            resp_len = struct.unpack('>H', self.socket.recv(2))[0]
            response = b''
            while len(response) < resp_len:
                response += self.socket.recv(resp_len - len(response))
            
            data = response[:-2] if len(response) > 2 else b''
            sw = response[-2:] if len(response) >= 2 else b''
            
            return data, sw
            
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")
            self.disconnect()
            return b'', b''
    
    def decode_sw(self, sw: bytes) -> str:
        """Décode le Status Word."""
        if len(sw) != 2:
            return "Invalid SW"
        
        sw_hex = sw.hex().upper()
        
        # Dictionnaire des SW
        sw_dict = {
            '9000': 'Success',
            '6283': 'Selected file invalidated',
            '6300': 'Authentication failed',
            '6700': 'Wrong length',
            '6982': 'Security status not satisfied',
            '6983': 'Authentication method blocked',
            '6984': 'Reference data invalidated',
            '6985': 'Conditions not satisfied',
            '6A80': 'Wrong data',
            '6A81': 'Function not supported',
            '6A82': 'File or application not found',
            '6A86': 'Incorrect P1-P2',
            '6A88': 'Referenced data not found',
            '6D00': 'Instruction not supported',
            '6E00': 'Class not supported',
            '6F00': 'Unknown error',
        }
        
        if sw_hex in sw_dict:
            return sw_dict[sw_hex]
        elif sw_hex.startswith('61'):
            return f"More data available ({sw[1]} bytes)"
        elif sw_hex.startswith('63C'):
            return f"PIN tries remaining: {sw[1] & 0x0F}"
        elif sw_hex.startswith('6C'):
            return f"Wrong Le, expected {sw[1]}"
        
        return "Unknown"
    
    def print_response(self, data: bytes, sw: bytes):
        """Affiche la réponse formatée."""
        # Status Word
        sw_desc = self.decode_sw(sw)
        sw_color = Colors.GREEN if sw == b'\x90\x00' else Colors.YELLOW
        print(f"{sw_color}SW: {sw.hex().upper()} ({sw_desc}){Colors.END}")
        
        # Données
        if data:
            print(f"{Colors.CYAN}Data ({len(data)} bytes):{Colors.END}")
            
            # Affichage hexadécimal formaté
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                hex_str = ' '.join(f'{b:02X}' for b in chunk)
                ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                print(f"  {i:04X}: {hex_str:<48} {ascii_str}")
            
            # Parser TLV si activé
            if self.parse_tlv:
                print(f"\n{Colors.CYAN}TLV Structure:{Colors.END}")
                for line in TLVParser.parse(data):
                    print(f"  {line}")
    
    def show_help(self):
        """Affiche l'aide."""
        print(f"""
{Colors.HEADER}APDU Shell Commands{Colors.END}

{Colors.BOLD}Basic Commands:{Colors.END}
  <APDU>          Send APDU in hex format (e.g., 00A4040007F0000000010001)
  connect         Reconnect to jCardSim
  disconnect      Close connection
  quit/exit       Exit shell

{Colors.BOLD}Macros:{Colors.END}
  /macro          List available macros
  /macro <name>   Execute macro
  /define <name> <apdu>  Define new macro

{Colors.BOLD}Settings:{Colors.END}
  /verbose        Toggle verbose mode
  /tlv            Toggle TLV parsing
  /history        Show command history

{Colors.BOLD}Special:{Colors.END}
  /select <AID>   Select applet by AID
  /get_response   Get remaining data (after 61xx)
  /reset          Reset card connection

{Colors.BOLD}Pre-defined Macros:{Colors.END}
""")
        for name, apdu in self.macros.items():
            print(f"  {name}: {apdu}")
    
    def execute_command(self, cmd: str) -> bool:
        """Exécute une commande. Retourne False pour quitter."""
        cmd = cmd.strip()
        
        if not cmd:
            return True
        
        # Commandes spéciales
        if cmd.lower() in ('quit', 'exit', 'q'):
            return False
        
        if cmd.lower() == 'help':
            self.show_help()
            return True
        
        if cmd.lower() == 'connect':
            self.disconnect()
            self.connect()
            return True
        
        if cmd.lower() == 'disconnect':
            self.disconnect()
            print("Disconnected")
            return True
        
        # Commandes /
        if cmd.startswith('/'):
            return self.handle_slash_command(cmd[1:])
        
        # C'est un APDU
        try:
            # Nettoyer
            apdu_hex = cmd.replace(' ', '').replace(':', '').upper()
            
            # Vérifier le format
            if not all(c in '0123456789ABCDEF' for c in apdu_hex):
                print(f"{Colors.RED}Invalid hex format{Colors.END}")
                return True
            
            if len(apdu_hex) < 8:
                print(f"{Colors.RED}APDU too short (minimum 4 bytes){Colors.END}")
                return True
            
            # Envoyer
            print(f"{Colors.BLUE}→ {apdu_hex}{Colors.END}")
            data, sw = self.send_apdu(apdu_hex)
            
            if sw:
                self.print_response(data, sw)
                self.history.append(apdu_hex)
            
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")
        
        return True
    
    def handle_slash_command(self, cmd: str) -> bool:
        """Gère les commandes /."""
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''
        
        if command == 'macro':
            if not args:
                print(f"\n{Colors.HEADER}Available Macros:{Colors.END}")
                for name, apdu in self.macros.items():
                    print(f"  {name}: {apdu}")
            elif args in self.macros:
                apdu = self.macros[args]
                print(f"Executing macro: {args}")
                return self.execute_command(apdu)
            else:
                print(f"{Colors.RED}Unknown macro: {args}{Colors.END}")
        
        elif command == 'define':
            parts = args.split(maxsplit=1)
            if len(parts) == 2:
                self.macros[parts[0]] = parts[1]
                print(f"Defined macro: {parts[0]}")
            else:
                print(f"{Colors.RED}Usage: /define <name> <apdu>{Colors.END}")
        
        elif command == 'verbose':
            self.verbose = not self.verbose
            print(f"Verbose mode: {'ON' if self.verbose else 'OFF'}")
        
        elif command == 'tlv':
            self.parse_tlv = not self.parse_tlv
            print(f"TLV parsing: {'ON' if self.parse_tlv else 'OFF'}")
        
        elif command == 'history':
            for i, cmd in enumerate(self.history[-20:], 1):
                print(f"  {i}: {cmd}")
        
        elif command == 'select':
            if args:
                aid = args.replace(' ', '').upper()
                lc = f"{len(aid)//2:02X}"
                apdu = f"00A40400{lc}{aid}"
                return self.execute_command(apdu)
            else:
                print(f"{Colors.RED}Usage: /select <AID>{Colors.END}")
        
        elif command == 'get_response':
            le = args if args else "00"
            return self.execute_command(f"00C00000{le}")
        
        elif command == 'reset':
            self.disconnect()
            self.connect()
        
        else:
            print(f"{Colors.RED}Unknown command: /{command}{Colors.END}")
            print("Type 'help' for available commands")
        
        return True
    
    def run(self):
        """Boucle principale du shell."""
        print(f"""
{Colors.HEADER}╔════════════════════════════════════════╗
║        APDU Interactive Shell          ║
║     Type 'help' for commands           ║
╚════════════════════════════════════════╝{Colors.END}
""")
        
        if not self.connect():
            print("You can type 'connect' to retry")
        
        try:
            while True:
                try:
                    prompt = f"{Colors.GREEN}APDU>{Colors.END} " if self.socket else f"{Colors.RED}APDU>{Colors.END} "
                    cmd = input(prompt)
                    
                    if not self.execute_command(cmd):
                        break
                    
                except KeyboardInterrupt:
                    print("\nUse 'quit' to exit")
                except EOFError:
                    break
        finally:
            # Sauvegarder l'historique
            try:
                readline.write_history_file(self.histfile)
            except:
                pass
            
            self.disconnect()
            print(f"\n{Colors.GREEN}Goodbye!{Colors.END}")


def main():
    parser = argparse.ArgumentParser(description='APDU Interactive Shell')
    parser.add_argument('--host', default=JCARDSIM_HOST, help='jCardSim host')
    parser.add_argument('--port', type=int, default=JCARDSIM_PORT, help='jCardSim port')
    parser.add_argument('-c', '--command', help='Execute single command and exit')
    parser.add_argument('-f', '--file', help='Execute commands from file')
    
    args = parser.parse_args()
    
    shell = APDUShell(args.host, args.port)
    
    if args.command:
        shell.connect()
        shell.execute_command(args.command)
        shell.disconnect()
    elif args.file:
        shell.connect()
        with open(args.file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    print(f"\n>>> {line}")
                    shell.execute_command(line)
        shell.disconnect()
    else:
        shell.run()


if __name__ == '__main__':
    main()
