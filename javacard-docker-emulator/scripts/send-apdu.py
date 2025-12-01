#!/usr/bin/env python3
"""
send-apdu.py - Outil en ligne de commande pour envoyer des APDUs à jCardSim

Usage:
    python send-apdu.py "00A4040007A0000000041010"  # Sélection applet
    python send-apdu.py --file commands.txt          # Fichier de commandes
    python send-apdu.py --interactive                # Mode interactif
"""

import argparse
import os
import readline  # Pour l'historique en mode interactif
import socket
import struct
import sys
from typing import Optional, Tuple


class APDUClient:
    """Client pour envoyer des APDUs à jCardSim via socket."""
    
    def __init__(self, host: str = 'localhost', port: int = 9025):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
    
    def connect(self) -> bool:
        """Établit la connexion."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            print(f"✓ Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Ferme la connexion."""
        if self.socket:
            self.socket.close()
            self.socket = None
    
    def send_apdu(self, apdu_hex: str) -> Tuple[Optional[bytes], str]:
        """
        Envoie un APDU en hexadécimal et retourne la réponse.
        
        Returns:
            Tuple (response_bytes, status_word_description)
        """
        # Nettoyer l'entrée
        apdu_hex = apdu_hex.replace(' ', '').replace(':', '').strip()
        
        try:
            apdu = bytes.fromhex(apdu_hex)
        except ValueError as e:
            return None, f"Invalid hex: {e}"
        
        if len(apdu) < 4:
            return None, "APDU too short (minimum 4 bytes: CLA INS P1 P2)"
        
        try:
            # Envoyer: longueur (2 bytes) + APDU
            length = struct.pack('>H', len(apdu))
            self.socket.sendall(length + apdu)
            
            # Recevoir: longueur (2 bytes)
            resp_len_bytes = self._recv_exact(2)
            if not resp_len_bytes:
                return None, "No response"
            
            resp_len = struct.unpack('>H', resp_len_bytes)[0]
            
            # Recevoir la réponse
            response = self._recv_exact(resp_len)
            if not response:
                return None, "Incomplete response"
            
            # Extraire le Status Word
            sw_desc = self._decode_sw(response[-2:]) if len(response) >= 2 else ""
            
            return response, sw_desc
            
        except Exception as e:
            return None, f"Error: {e}"
    
    def _recv_exact(self, length: int) -> Optional[bytes]:
        """Reçoit exactement 'length' bytes."""
        data = b''
        while len(data) < length:
            chunk = self.socket.recv(length - len(data))
            if not chunk:
                return None
            data += chunk
        return data
    
    @staticmethod
    def _decode_sw(sw: bytes) -> str:
        """Décode le Status Word en description lisible."""
        if len(sw) != 2:
            return ""
        
        sw1, sw2 = sw[0], sw[1]
        sw_hex = f"{sw1:02X}{sw2:02X}"
        
        # Status Words courants
        sw_codes = {
            '9000': 'Success',
            '6100': f'More data available ({sw2} bytes)',
            '6283': 'Card locked',
            '6300': 'Authentication failed',
            '6400': 'Execution error',
            '6581': 'Memory error',
            '6700': 'Wrong length',
            '6882': 'Secure messaging not supported',
            '6883': 'Last command of chain expected',
            '6884': 'Command chaining not supported',
            '6982': 'Security not satisfied',
            '6983': 'Auth method blocked',
            '6984': 'Reference data invalidated',
            '6985': 'Conditions not satisfied',
            '6986': 'Command not allowed',
            '6A80': 'Wrong data',
            '6A81': 'Function not supported',
            '6A82': 'File not found',
            '6A83': 'Record not found',
            '6A84': 'Not enough memory',
            '6A86': 'Incorrect P1P2',
            '6A88': 'Referenced data not found',
            '6B00': 'Wrong P1P2',
            '6C00': f'Wrong Le ({sw2} expected)',
            '6D00': 'Instruction not supported',
            '6E00': 'Class not supported',
            '6F00': 'Unknown error',
        }
        
        # Vérifier les patterns
        if sw_hex in sw_codes:
            return sw_codes[sw_hex]
        elif sw_hex.startswith('61'):
            return f'More data ({sw2} bytes)'
        elif sw_hex.startswith('63'):
            if sw2 >= 0xC0:
                return f'PIN tries remaining: {sw2 - 0xC0}'
            return f'Warning: {sw_hex}'
        elif sw_hex.startswith('6C'):
            return f'Wrong Le, correct is {sw2}'
        elif sw_hex.startswith('9F'):
            return f'Data available ({sw2} bytes)'
        
        return f'Unknown: {sw_hex}'


def format_response(response: bytes) -> str:
    """Formate la réponse pour affichage."""
    hex_str = response.hex().upper()
    
    # Séparer les données du SW
    if len(response) >= 2:
        data = hex_str[:-4] if len(hex_str) > 4 else ""
        sw = hex_str[-4:]
        if data:
            return f"Data: {data}\nSW:   {sw}"
        return f"SW: {sw}"
    
    return hex_str


def interactive_mode(client: APDUClient):
    """Mode interactif avec historique."""
    print("\n=== Mode Interactif APDU ===")
    print("Commandes: 'quit', 'exit', 'help', 'history'")
    print("Format APDU: CLA INS P1 P2 [Lc] [Data] [Le]")
    print("Exemple: 00A4040007A0000000041010")
    print()
    
    history = []
    
    while True:
        try:
            cmd = input("APDU> ").strip()
            
            if not cmd:
                continue
            
            if cmd.lower() in ('quit', 'exit', 'q'):
                break
            
            if cmd.lower() == 'help':
                print("""
Commandes APDU courantes:
  SELECT AID:      00 A4 04 00 <len> <AID>
  GET RESPONSE:    00 C0 00 00 <Le>
  GET DATA:        00 CA <P1> <P2> <Le>
  PUT DATA:        00 DA <P1> <P2> <Lc> <Data>
  VERIFY PIN:      00 20 00 <PIN_ID> <Lc> <PIN>
  CHANGE PIN:      00 24 00 <PIN_ID> <Lc> <oldPIN><newPIN>
  GENERATE KEY:    00 46 00 00
  
Exemples:
  00A4040007A0000000041010    # Select applet by AID
  00CA00FE00                  # Get FCI
  8050000008<random>00        # Initialize Update (GP)
""")
                continue
            
            if cmd.lower() == 'history':
                for i, h in enumerate(history[-20:], 1):
                    print(f"  {i}: {h}")
                continue
            
            # Envoyer l'APDU
            response, sw_desc = client.send_apdu(cmd)
            
            if response:
                print(f"→ {format_response(response)}")
                print(f"   ({sw_desc})")
                history.append(cmd)
            else:
                print(f"✗ {sw_desc}")
            
            print()
            
        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
        except EOFError:
            break


def main():
    parser = argparse.ArgumentParser(
        description='Send APDU commands to jCardSim',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "00A4040007A0000000041010"
  %(prog)s --interactive
  %(prog)s --file commands.txt
  %(prog)s --host jcardsim --port 9025 "00A40400"
        """
    )
    
    parser.add_argument('apdu', nargs='?', help='APDU in hex format')
    parser.add_argument('--host', default=os.getenv('JCARDSIM_HOST', 'localhost'),
                        help='jCardSim host (default: localhost or $JCARDSIM_HOST)')
    parser.add_argument('--port', type=int, 
                        default=int(os.getenv('JCARDSIM_PORT', '9025')),
                        help='jCardSim port (default: 9025 or $JCARDSIM_PORT)')
    parser.add_argument('-i', '--interactive', action='store_true',
                        help='Interactive mode')
    parser.add_argument('-f', '--file', help='File containing APDU commands')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    # Créer le client
    client = APDUClient(args.host, args.port)
    
    if not client.connect():
        sys.exit(1)
    
    try:
        if args.interactive:
            interactive_mode(client)
        
        elif args.file:
            with open(args.file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    print(f"← {line}")
                    response, sw_desc = client.send_apdu(line)
                    
                    if response:
                        print(f"→ {format_response(response)} ({sw_desc})")
                    else:
                        print(f"✗ {sw_desc}")
                    print()
        
        elif args.apdu:
            response, sw_desc = client.send_apdu(args.apdu)
            
            if response:
                if args.verbose:
                    print(f"Command:  {args.apdu}")
                    print(f"Response: {response.hex().upper()}")
                    print(f"Status:   {sw_desc}")
                else:
                    print(response.hex().upper())
                sys.exit(0)
            else:
                print(f"Error: {sw_desc}", file=sys.stderr)
                sys.exit(1)
        
        else:
            parser.print_help()
    
    finally:
        client.disconnect()


if __name__ == '__main__':
    main()
