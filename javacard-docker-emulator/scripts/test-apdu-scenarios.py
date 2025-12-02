#!/usr/bin/env python3
"""
test-apdu-scenarios.py - Test complet des commandes APDU avec scénario multi-applets

Ce script démontre:
1. La communication APDU de base
2. La sélection d'applets
3. Le changement d'applet (contexte switching)
4. Toutes les commandes des deux applets

Connexion directe à jCardSim via TCP/IP (port 9025)
"""

import socket
import struct
import sys
import time

# Configuration (utilise les variables d'environnement si disponibles)
import os
JCARDSIM_HOST = os.getenv("JCARDSIM_HOST", "localhost")
JCARDSIM_PORT = int(os.getenv("JCARDSIM_PORT", "9025"))

# AIDs des applets
AID_HELLOWORLD = bytes.fromhex("F0000000010001")
AID_COUNTER = bytes.fromhex("F0000000010002")

# Couleurs pour l'affichage
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def colorize(text, color):
    return f"{color}{text}{Colors.ENDC}"

# =============================================================================
# CLASSE DE COMMUNICATION
# =============================================================================

class SmartCardConnection:
    """Gère la connexion avec jCardSim"""

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = None

    def connect(self):
        """Établit la connexion"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
        print(colorize(f"✓ Connecté à jCardSim sur {self.host}:{self.port}", Colors.GREEN))

    def disconnect(self):
        """Ferme la connexion"""
        if self.socket:
            self.socket.close()
            self.socket = None

    def send_apdu(self, apdu_hex, description=""):
        """Envoie un APDU et retourne la réponse"""
        if isinstance(apdu_hex, str):
            apdu = bytes.fromhex(apdu_hex.replace(" ", ""))
        else:
            apdu = apdu_hex

        # Afficher la commande
        print(f"\n{colorize('>> APDU:', Colors.CYAN)} {apdu.hex().upper()}")
        if description:
            print(f"   {colorize(description, Colors.YELLOW)}")

        # Envoyer: 2 bytes longueur + APDU
        length = struct.pack('>H', len(apdu))
        self.socket.sendall(length + apdu)

        # Recevoir: 2 bytes longueur + réponse
        resp_len_bytes = self._recv_exact(2)
        resp_len = struct.unpack('>H', resp_len_bytes)[0]
        response = self._recv_exact(resp_len)

        # Parser la réponse
        if len(response) >= 2:
            sw = response[-2:]
            data = response[:-2]
            sw_hex = sw.hex().upper()

            # Interpréter le SW
            sw_meaning = self._interpret_sw(sw)

            if sw_hex == "9000":
                color = Colors.GREEN
            elif sw_hex.startswith("61") or sw_hex.startswith("6C"):
                color = Colors.YELLOW
            else:
                color = Colors.RED

            print(f"{colorize('<< Réponse:', Colors.CYAN)} {response.hex().upper()}")
            if data:
                print(f"   Data: {data.hex().upper()} ({len(data)} bytes)")
                # Essayer de décoder en ASCII
                try:
                    ascii_data = data.decode('ascii')
                    if ascii_data.isprintable():
                        print(f"   ASCII: \"{ascii_data}\"")
                except:
                    pass
            print(f"   {colorize(f'SW: {sw_hex}', color)} - {sw_meaning}")

            return data, sw
        else:
            print(f"{colorize('<< Réponse:', Colors.RED)} {response.hex().upper()} (format invalide)")
            return response, b'\x00\x00'

    def _recv_exact(self, n):
        """Reçoit exactement n bytes"""
        data = b''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if not chunk:
                raise Exception("Connexion fermée")
            data += chunk
        return data

    def _interpret_sw(self, sw):
        """Interprète le Status Word"""
        sw1, sw2 = sw[0], sw[1]
        sw_hex = sw.hex().upper()

        sw_meanings = {
            "9000": "Succès",
            "6100": "Données disponibles (Le=00)",
            "6283": "Fichier désactivé",
            "6300": "Vérification échouée",
            "6400": "Erreur (pas de changement d'état)",
            "6581": "Erreur mémoire",
            "6700": "Longueur incorrecte",
            "6882": "Canal sécurisé non supporté",
            "6883": "Chaînage non supporté",
            "6984": "Données référencées invalides",
            "6985": "Conditions d'utilisation non satisfaites",
            "6986": "Commande non autorisée",
            "6A80": "Paramètres dans les données incorrects",
            "6A81": "Fonction non supportée",
            "6A82": "Fichier non trouvé",
            "6A83": "Enregistrement non trouvé",
            "6A84": "Mémoire insuffisante",
            "6A86": "P1-P2 incorrects",
            "6A88": "Données référencées non trouvées",
            "6B00": "Paramètres incorrects (offset)",
            "6D00": "INS non supporté",
            "6E00": "CLA non supporté",
            "6F00": "Erreur interne",
        }

        if sw_hex in sw_meanings:
            return sw_meanings[sw_hex]
        elif sw_hex.startswith("61"):
            return f"{sw2} bytes disponibles"
        elif sw_hex.startswith("63C"):
            return f"{sw2 & 0x0F} essais restants"
        elif sw_hex.startswith("6C"):
            return f"Longueur exacte: {sw2}"
        else:
            return "Code inconnu"

# =============================================================================
# FONCTIONS D'AIDE POUR LES COMMANDES
# =============================================================================

def build_select_apdu(aid):
    """Construit un APDU SELECT"""
    return bytes([0x00, 0xA4, 0x04, 0x00, len(aid)]) + aid

def build_apdu(cla, ins, p1, p2, data=None, le=None):
    """Construit un APDU générique"""
    apdu = bytes([cla, ins, p1, p2])
    if data:
        apdu += bytes([len(data)]) + data
    if le is not None:
        apdu += bytes([le])
    return apdu

# =============================================================================
# SCÉNARIOS DE TEST
# =============================================================================

def test_basic_select(card):
    """Test 1: Sélection basique d'applet"""
    print("\n" + "="*60)
    print(colorize(" SCÉNARIO 1: Sélection d'Applet", Colors.HEADER + Colors.BOLD))
    print("="*60)

    # Sélectionner HelloWorld
    print("\n--- Sélection de HelloWorld Applet ---")
    apdu = build_select_apdu(AID_HELLOWORLD)
    data, sw = card.send_apdu(apdu, "SELECT HelloWorld (AID: F0000000010001)")

    if sw != b'\x90\x00':
        print(colorize("✗ Échec de la sélection!", Colors.RED))
        return False

    print(colorize("✓ HelloWorld sélectionné avec succès", Colors.GREEN))
    return True

def test_helloworld_commands(card):
    """Test 2: Commandes de l'applet HelloWorld"""
    print("\n" + "="*60)
    print(colorize(" SCÉNARIO 2: Commandes HelloWorld Applet", Colors.HEADER + Colors.BOLD))
    print("="*60)

    # S'assurer que HelloWorld est sélectionné
    card.send_apdu(build_select_apdu(AID_HELLOWORLD), "SELECT HelloWorld")

    # INS 00: Hello
    print("\n--- INS 00: GET HELLO ---")
    apdu = build_apdu(0x80, 0x00, 0x00, 0x00, le=0x00)
    card.send_apdu(apdu, "Demande le message 'Hello World!'")

    # INS 01: Echo
    print("\n--- INS 01: ECHO ---")
    test_data = b"Test Echo Data"
    apdu = build_apdu(0x80, 0x01, 0x00, 0x00, test_data)
    card.send_apdu(apdu, f"Echo des données: '{test_data.decode()}'")

    # INS F0: Get Status
    print("\n--- INS F0: GET STATUS ---")
    apdu = build_apdu(0x80, 0xF0, 0x00, 0x00, le=0x08)
    data, sw = card.send_apdu(apdu, "Obtenir le statut de l'applet")
    if sw == b'\x90\x00' and len(data) >= 8:
        print(f"   Version: {data[0]}.{data[1]}")
        usage = (data[2] << 8) | data[3]
        print(f"   Compteur d'utilisation: {usage}")
        print(f"   Essais PIN restants: {data[4]}")
        print(f"   PIN validé: {'Oui' if data[5] == 1 else 'Non'}")
        data_len = (data[6] << 8) | data[7]
        print(f"   Données stockées: {data_len} bytes")

    # INS 20: Verify PIN (correct)
    print("\n--- INS 20: VERIFY PIN (correct: 1234) ---")
    pin = b"1234"
    apdu = build_apdu(0x80, 0x20, 0x00, 0x00, pin)
    card.send_apdu(apdu, "Vérification du PIN '1234'")

    # INS 03: Put Data (nécessite PIN)
    print("\n--- INS 03: PUT DATA (après authentification) ---")
    store_data = b"Donnees secretes!"
    apdu = build_apdu(0x80, 0x03, 0x00, 0x00, store_data)
    card.send_apdu(apdu, f"Stockage des données: '{store_data.decode()}'")

    # INS 02: Get Data
    print("\n--- INS 02: GET DATA ---")
    apdu = build_apdu(0x80, 0x02, 0x00, 0x00, le=0x20)
    card.send_apdu(apdu, "Lecture des données stockées")

    # INS 20: Verify PIN (incorrect)
    print("\n--- INS 20: VERIFY PIN (incorrect: 0000) ---")
    bad_pin = b"0000"
    apdu = build_apdu(0x80, 0x20, 0x00, 0x00, bad_pin)
    card.send_apdu(apdu, "Vérification du PIN '0000' (doit échouer)")

def test_counter_commands(card):
    """Test 3: Commandes de l'applet Counter"""
    print("\n" + "="*60)
    print(colorize(" SCÉNARIO 3: Commandes Counter Applet", Colors.HEADER + Colors.BOLD))
    print("="*60)

    # Sélectionner Counter
    print("\n--- Sélection de Counter Applet ---")
    card.send_apdu(build_select_apdu(AID_COUNTER), "SELECT Counter (AID: F0000000010002)")

    # INS 10: Get Counter (initial)
    print("\n--- INS 10: GET COUNTER (valeur initiale) ---")
    apdu = build_apdu(0x80, 0x10, 0x00, 0x00, le=0x04)
    data, sw = card.send_apdu(apdu, "Lecture du compteur")
    if sw == b'\x90\x00' and len(data) == 4:
        value = int.from_bytes(data, 'big')
        print(f"   Valeur: {value}")

    # INS 11: Increment +1
    print("\n--- INS 11: INCREMENT (+1) ---")
    apdu = build_apdu(0x80, 0x11, 0x00, 0x00, le=0x04)
    data, sw = card.send_apdu(apdu, "Incrémentation de 1")
    if sw == b'\x90\x00':
        value = int.from_bytes(data, 'big')
        print(f"   Nouvelle valeur: {value}")

    # INS 11: Increment +10
    print("\n--- INS 11: INCREMENT (+10) ---")
    apdu = build_apdu(0x80, 0x11, 0x0A, 0x00, le=0x04)
    data, sw = card.send_apdu(apdu, "Incrémentation de 10")
    if sw == b'\x90\x00':
        value = int.from_bytes(data, 'big')
        print(f"   Nouvelle valeur: {value}")

    # INS 17: Add value (256)
    print("\n--- INS 17: ADD VALUE (+256) ---")
    add_value = struct.pack('>H', 256)
    apdu = build_apdu(0x80, 0x17, 0x00, 0x00, add_value)
    data, sw = card.send_apdu(apdu, "Ajout de 256")
    if sw == b'\x90\x00':
        value = int.from_bytes(data, 'big')
        print(f"   Nouvelle valeur: {value}")

    # INS 12: Decrement -5
    print("\n--- INS 12: DECREMENT (-5) ---")
    apdu = build_apdu(0x80, 0x12, 0x05, 0x00, le=0x04)
    data, sw = card.send_apdu(apdu, "Décrémentation de 5")
    if sw == b'\x90\x00':
        value = int.from_bytes(data, 'big')
        print(f"   Nouvelle valeur: {value}")

    # INS 14: Set Value (1000)
    print("\n--- INS 14: SET VALUE (1000) ---")
    new_value = struct.pack('>I', 1000)
    apdu = build_apdu(0x80, 0x14, 0x00, 0x00, new_value)
    card.send_apdu(apdu, "Définition de la valeur à 1000")

    # INS 15: Set Limit (500) - activé
    print("\n--- INS 15: SET LIMIT (500, activé) ---")
    limit_value = struct.pack('>I', 500)
    apdu = build_apdu(0x80, 0x15, 0x01, 0x00, limit_value)
    card.send_apdu(apdu, "Définition de la limite à 500 (activée)")

    # INS 11: Increment (doit échouer car > limite)
    print("\n--- INS 11: INCREMENT (doit échouer, > limite) ---")
    apdu = build_apdu(0x80, 0x11, 0x01, 0x00, le=0x04)
    card.send_apdu(apdu, "Tentative d'incrémentation (compteur=1000, limite=500)")

    # INS 13: Reset
    print("\n--- INS 13: RESET ---")
    apdu = build_apdu(0x80, 0x13, 0x00, 0x00)
    card.send_apdu(apdu, "Remise à zéro du compteur")

    # INS 16: Get Info
    print("\n--- INS 16: GET INFO ---")
    apdu = build_apdu(0x80, 0x16, 0x00, 0x00, le=0x0B)
    data, sw = card.send_apdu(apdu, "Obtenir toutes les informations")
    if sw == b'\x90\x00' and len(data) >= 11:
        counter = int.from_bytes(data[0:4], 'big')
        limit = int.from_bytes(data[4:8], 'big')
        limit_enabled = data[8] == 1
        op_count = (data[9] << 8) | data[10]
        print(f"   Compteur: {counter}")
        print(f"   Limite: {limit}")
        print(f"   Limite activée: {'Oui' if limit_enabled else 'Non'}")
        print(f"   Nombre d'opérations: {op_count}")

def test_applet_switching(card):
    """Test 4: Changement de contexte entre applets"""
    print("\n" + "="*60)
    print(colorize(" SCÉNARIO 4: Multi-Applets (Context Switching)", Colors.HEADER + Colors.BOLD))
    print("="*60)

    print("""
    Ce scénario démontre le changement d'applet:
    1. On travaille avec HelloWorld
    2. On switch vers Counter
    3. On revient à HelloWorld
    4. Les données de chaque applet sont isolées
    """)

    # 1. HelloWorld - stocker des données
    print("\n" + "-"*40)
    print("ÉTAPE 1: Travailler avec HelloWorld")
    print("-"*40)
    card.send_apdu(build_select_apdu(AID_HELLOWORLD), "SELECT HelloWorld")
    card.send_apdu(build_apdu(0x80, 0x20, 0x00, 0x00, b"1234"), "VERIFY PIN")
    card.send_apdu(build_apdu(0x80, 0x03, 0x00, 0x00, b"Secret1"), "PUT DATA 'Secret1'")

    # 2. Switch vers Counter
    print("\n" + "-"*40)
    print("ÉTAPE 2: Basculer vers Counter")
    print("-"*40)
    card.send_apdu(build_select_apdu(AID_COUNTER), "SELECT Counter")
    card.send_apdu(build_apdu(0x80, 0x14, 0x00, 0x00, struct.pack('>I', 42)), "SET VALUE 42")
    apdu = build_apdu(0x80, 0x10, 0x00, 0x00, le=0x04)
    data, sw = card.send_apdu(apdu, "GET COUNTER")
    if sw == b'\x90\x00':
        print(f"   ➜ Counter value: {int.from_bytes(data, 'big')}")

    # 3. Retour à HelloWorld
    print("\n" + "-"*40)
    print("ÉTAPE 3: Retour à HelloWorld")
    print("-"*40)
    card.send_apdu(build_select_apdu(AID_HELLOWORLD), "SELECT HelloWorld")

    # Note: après resélection, le PIN doit être revérifié!
    print("\n  Note: Le PIN doit être revérifié après resélection")
    card.send_apdu(build_apdu(0x80, 0x02, 0x00, 0x00, le=0x20), "GET DATA (sans PIN)")

    card.send_apdu(build_apdu(0x80, 0x20, 0x00, 0x00, b"1234"), "VERIFY PIN")
    data, sw = card.send_apdu(build_apdu(0x80, 0x02, 0x00, 0x00, le=0x20), "GET DATA (avec PIN)")
    if sw == b'\x90\x00':
        print(f"   ➜ HelloWorld data: '{data.decode()}'")

    # 4. Vérifier que Counter a gardé sa valeur
    print("\n" + "-"*40)
    print("ÉTAPE 4: Vérifier la persistance de Counter")
    print("-"*40)
    card.send_apdu(build_select_apdu(AID_COUNTER), "SELECT Counter")
    data, sw = card.send_apdu(build_apdu(0x80, 0x10, 0x00, 0x00, le=0x04), "GET COUNTER")
    if sw == b'\x90\x00':
        print(f"   ➜ Counter value (persisté): {int.from_bytes(data, 'big')}")

def test_error_handling(card):
    """Test 5: Gestion des erreurs"""
    print("\n" + "="*60)
    print(colorize(" SCÉNARIO 5: Gestion des Erreurs", Colors.HEADER + Colors.BOLD))
    print("="*60)

    card.send_apdu(build_select_apdu(AID_HELLOWORLD), "SELECT HelloWorld")

    # CLA non supporté
    print("\n--- Test: CLA non supporté ---")
    apdu = build_apdu(0xFF, 0x00, 0x00, 0x00)
    card.send_apdu(apdu, "CLA 0xFF (non supporté)")

    # INS non supporté
    print("\n--- Test: INS non supporté ---")
    apdu = build_apdu(0x80, 0xFF, 0x00, 0x00)
    card.send_apdu(apdu, "INS 0xFF (non supporté)")

    # Données sans authentification
    print("\n--- Test: PUT DATA sans authentification PIN ---")
    # D'abord, désélectionner/resélectionner pour reset le PIN
    card.send_apdu(build_select_apdu(AID_COUNTER), "SELECT Counter (pour reset)")
    card.send_apdu(build_select_apdu(AID_HELLOWORLD), "SELECT HelloWorld (PIN reset)")
    apdu = build_apdu(0x80, 0x03, 0x00, 0x00, b"test")
    card.send_apdu(apdu, "PUT DATA sans PIN (doit échouer)")

    # PIN incorrect (multiple fois)
    print("\n--- Test: PIN incorrect (essais multiples) ---")
    for i in range(2):
        apdu = build_apdu(0x80, 0x20, 0x00, 0x00, b"9999")
        card.send_apdu(apdu, f"Tentative {i+1}: PIN '9999' (incorrect)")

# =============================================================================
# MAIN
# =============================================================================

def main():
    print(colorize("""
    ╔═══════════════════════════════════════════════════════════╗
    ║       TEST COMPLET DES COMMANDES APDU                     ║
    ║       Scénario Multi-Applets JavaCard                     ║
    ╚═══════════════════════════════════════════════════════════╝
    """, Colors.HEADER + Colors.BOLD))

    print(f"Connexion à jCardSim sur {JCARDSIM_HOST}:{JCARDSIM_PORT}...")

    card = SmartCardConnection(JCARDSIM_HOST, JCARDSIM_PORT)

    try:
        card.connect()

        # Exécuter tous les scénarios
        test_basic_select(card)
        time.sleep(0.5)

        test_helloworld_commands(card)
        time.sleep(0.5)

        test_counter_commands(card)
        time.sleep(0.5)

        test_applet_switching(card)
        time.sleep(0.5)

        test_error_handling(card)

        print("\n" + "="*60)
        print(colorize(" TOUS LES TESTS TERMINÉS", Colors.GREEN + Colors.BOLD))
        print("="*60)

    except ConnectionRefusedError:
        print(colorize(f"\n✗ Impossible de se connecter à jCardSim sur {JCARDSIM_HOST}:{JCARDSIM_PORT}", Colors.RED))
        print("  Assurez-vous que jCardSim est démarré.")
        sys.exit(1)
    except Exception as e:
        print(colorize(f"\n✗ Erreur: {e}", Colors.RED))
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        card.disconnect()

if __name__ == "__main__":
    main()
