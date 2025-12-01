#!/usr/bin/env python3
"""
test-applet.py - Tests automatisés pour l'applet HelloWorld

Usage:
    python test-applet.py                    # Tests complets
    python test-applet.py --test hello       # Test spécifique
    python test-applet.py --verbose          # Mode verbeux
"""

import argparse
import os
import socket
import struct
import sys
from typing import Optional, Tuple, List

# Configuration
JCARDSIM_HOST = os.getenv('JCARDSIM_HOST', 'localhost')
JCARDSIM_PORT = int(os.getenv('JCARDSIM_PORT', '9025'))

# AID de l'applet HelloWorld
APPLET_AID = "F0000000010001"

# Codes de statut courants
SW_OK = bytes.fromhex("9000")
SW_SECURITY_NOT_SATISFIED = bytes.fromhex("6982")
SW_CONDITIONS_NOT_SATISFIED = bytes.fromhex("6985")

# Couleurs pour le terminal
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    END = '\033[0m'


class TestResult:
    def __init__(self, name: str, passed: bool, message: str = ""):
        self.name = name
        self.passed = passed
        self.message = message


class APDUTester:
    """Client de test APDU pour jCardSim."""
    
    def __init__(self, host: str, port: int, verbose: bool = False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.socket: Optional[socket.socket] = None
        self.results: List[TestResult] = []
    
    def connect(self) -> bool:
        """Établit la connexion."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            if self.verbose:
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
        """
        Envoie un APDU et retourne (data, sw).
        """
        apdu = bytes.fromhex(apdu_hex.replace(' ', ''))
        
        if self.verbose:
            print(f"  → {apdu.hex().upper()}")
        
        # Envoyer
        length = struct.pack('>H', len(apdu))
        self.socket.sendall(length + apdu)
        
        # Recevoir la longueur
        resp_len = struct.unpack('>H', self.socket.recv(2))[0]
        
        # Recevoir la réponse
        response = b''
        while len(response) < resp_len:
            response += self.socket.recv(resp_len - len(response))
        
        # Séparer data et SW
        data = response[:-2] if len(response) > 2 else b''
        sw = response[-2:] if len(response) >= 2 else b''
        
        if self.verbose:
            if data:
                print(f"  ← Data: {data.hex().upper()}")
            print(f"  ← SW: {sw.hex().upper()}")
        
        return data, sw
    
    def record_result(self, name: str, passed: bool, message: str = ""):
        """Enregistre un résultat de test."""
        self.results.append(TestResult(name, passed, message))
        
        status = f"{Colors.GREEN}PASS{Colors.END}" if passed else f"{Colors.RED}FAIL{Colors.END}"
        print(f"  [{status}] {name}", end="")
        if message:
            print(f" - {message}")
        else:
            print()
    
    def assert_sw(self, sw: bytes, expected: bytes, test_name: str) -> bool:
        """Vérifie le status word."""
        passed = sw == expected
        self.record_result(
            test_name,
            passed,
            f"Expected {expected.hex().upper()}, got {sw.hex().upper()}" if not passed else ""
        )
        return passed
    
    def assert_data(self, data: bytes, expected: bytes, test_name: str) -> bool:
        """Vérifie les données."""
        passed = data == expected
        self.record_result(
            test_name,
            passed,
            f"Data mismatch" if not passed else ""
        )
        return passed


def test_select_applet(tester: APDUTester) -> bool:
    """Test: Sélection de l'applet."""
    print(f"\n{Colors.CYAN}=== Test: Select Applet ==={Colors.END}")
    
    # SELECT avec AID
    apdu = f"00A4040007{APPLET_AID}"
    data, sw = tester.send_apdu(apdu)
    
    return tester.assert_sw(sw, SW_OK, "Select applet by AID")


def test_hello_world(tester: APDUTester) -> bool:
    """Test: Commande Hello World."""
    print(f"\n{Colors.CYAN}=== Test: Hello World ==={Colors.END}")
    
    # Sélectionner l'applet d'abord
    tester.send_apdu(f"00A4040007{APPLET_AID}")
    
    # Commande HELLO (CLA=80, INS=00)
    data, sw = tester.send_apdu("80000000")
    
    expected = b"Hello World!"
    
    result1 = tester.assert_sw(sw, SW_OK, "Hello command SW")
    result2 = tester.assert_data(data, expected, "Hello response data")
    
    return result1 and result2


def test_echo(tester: APDUTester) -> bool:
    """Test: Commande Echo."""
    print(f"\n{Colors.CYAN}=== Test: Echo ==={Colors.END}")
    
    # Sélectionner l'applet
    tester.send_apdu(f"00A4040007{APPLET_AID}")
    
    # Test avec différentes données
    test_cases = [
        ("DEADBEEF", "Short data"),
        ("00112233445566778899AABBCCDDEEFF", "16 bytes"),
        ("41424344", "ASCII 'ABCD'"),
    ]
    
    all_passed = True
    for test_data, description in test_cases:
        lc = f"{len(test_data)//2:02X}"
        apdu = f"8001000{lc}{test_data}{lc}"
        data, sw = tester.send_apdu(apdu)
        
        expected = bytes.fromhex(test_data)
        passed = sw == SW_OK and data == expected
        tester.record_result(f"Echo {description}", passed)
        all_passed = all_passed and passed
    
    return all_passed


def test_pin_verification(tester: APDUTester) -> bool:
    """Test: Vérification du PIN."""
    print(f"\n{Colors.CYAN}=== Test: PIN Verification ==={Colors.END}")
    
    # Sélectionner l'applet
    tester.send_apdu(f"00A4040007{APPLET_AID}")
    
    # Test avec PIN incorrect
    wrong_pin = "30303030"  # "0000"
    data, sw = tester.send_apdu(f"80200004{wrong_pin}")
    
    # Devrait retourner 63 Cx (x = essais restants)
    wrong_pin_ok = sw[0] == 0x63 and (sw[1] & 0xF0) == 0xC0
    tester.record_result("Wrong PIN rejected", wrong_pin_ok)
    
    # Test avec PIN correct (par défaut: "1234")
    correct_pin = "31323334"  # "1234"
    data, sw = tester.send_apdu(f"80200004{correct_pin}")
    correct_pin_ok = tester.assert_sw(sw, SW_OK, "Correct PIN accepted")
    
    return wrong_pin_ok and correct_pin_ok


def test_data_storage(tester: APDUTester) -> bool:
    """Test: Stockage de données."""
    print(f"\n{Colors.CYAN}=== Test: Data Storage ==={Colors.END}")
    
    # Sélectionner l'applet
    tester.send_apdu(f"00A4040007{APPLET_AID}")
    
    # Essayer de stocker sans authentification
    test_data = "48656C6C6F"  # "Hello"
    data, sw = tester.send_apdu(f"8003000505{test_data}")
    no_auth_rejected = tester.assert_sw(sw, SW_SECURITY_NOT_SATISFIED, "PUT_DATA without PIN rejected")
    
    # Authentifier avec PIN
    tester.send_apdu("8020000431323334")
    
    # Stocker des données
    data, sw = tester.send_apdu(f"8003000505{test_data}")
    put_ok = tester.assert_sw(sw, SW_OK, "PUT_DATA with PIN")
    
    # Lire les données
    data, sw = tester.send_apdu("80020000")
    get_ok = sw == SW_OK and data == bytes.fromhex(test_data)
    tester.record_result("GET_DATA returns stored data", get_ok)
    
    return no_auth_rejected and put_ok and get_ok


def test_status(tester: APDUTester) -> bool:
    """Test: Commande Status."""
    print(f"\n{Colors.CYAN}=== Test: Get Status ==={Colors.END}")
    
    # Sélectionner l'applet
    tester.send_apdu(f"00A4040007{APPLET_AID}")
    
    # Obtenir le statut
    data, sw = tester.send_apdu("80F00000")
    
    status_ok = sw == SW_OK and len(data) >= 8
    tester.record_result("Get status command", status_ok)
    
    if status_ok and tester.verbose:
        version = f"{data[0]}.{data[1]}"
        counter = int.from_bytes(data[2:4], 'big')
        pin_tries = data[4]
        pin_validated = data[5]
        data_len = int.from_bytes(data[6:8], 'big')
        
        print(f"    Version: {version}")
        print(f"    Usage counter: {counter}")
        print(f"    PIN tries remaining: {pin_tries}")
        print(f"    PIN validated: {bool(pin_validated)}")
        print(f"    Data stored: {data_len} bytes")
    
    return status_ok


def run_all_tests(tester: APDUTester) -> bool:
    """Exécute tous les tests."""
    print(f"\n{'='*60}")
    print(f"  JavaCard HelloWorld Applet - Test Suite")
    print(f"{'='*60}")
    print(f"Host: {tester.host}:{tester.port}")
    print(f"Applet AID: {APPLET_AID}")
    
    if not tester.connect():
        return False
    
    try:
        test_select_applet(tester)
        test_hello_world(tester)
        test_echo(tester)
        test_pin_verification(tester)
        test_data_storage(tester)
        test_status(tester)
    finally:
        tester.disconnect()
    
    # Résumé
    print(f"\n{'='*60}")
    print(f"  Test Results Summary")
    print(f"{'='*60}")
    
    passed = sum(1 for r in tester.results if r.passed)
    total = len(tester.results)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"\n{Colors.GREEN}✓ All tests passed!{Colors.END}")
        return True
    else:
        print(f"\n{Colors.RED}✗ Some tests failed:{Colors.END}")
        for r in tester.results:
            if not r.passed:
                print(f"  - {r.name}: {r.message}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Test JavaCard HelloWorld Applet')
    parser.add_argument('--host', default=JCARDSIM_HOST, help='jCardSim host')
    parser.add_argument('--port', type=int, default=JCARDSIM_PORT, help='jCardSim port')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--test', choices=['select', 'hello', 'echo', 'pin', 'data', 'status'],
                        help='Run specific test')
    
    args = parser.parse_args()
    
    tester = APDUTester(args.host, args.port, args.verbose)
    
    if args.test:
        if not tester.connect():
            sys.exit(1)
        
        try:
            tests = {
                'select': test_select_applet,
                'hello': test_hello_world,
                'echo': test_echo,
                'pin': test_pin_verification,
                'data': test_data_storage,
                'status': test_status,
            }
            tests[args.test](tester)
        finally:
            tester.disconnect()
    else:
        success = run_all_tests(tester)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
