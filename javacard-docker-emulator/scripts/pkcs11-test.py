#!/usr/bin/env python3
"""
pkcs11-test.py - Tests du module PKCS#11 avec OpenSC

Ce script teste l'intégration PKCS#11 avec la carte JavaCard émulée:
- Liste des slots et tokens
- Génération de clés
- Opérations cryptographiques
- Gestion des certificats
"""

import os
import sys

try:
    import PyKCS11
except ImportError:
    print("PyKCS11 not installed. Run: pip install pykcs11")
    sys.exit(1)


# Chemin du module PKCS#11 - détection automatique selon l'architecture
def find_pkcs11_lib():
    """Trouve automatiquement la bibliothèque PKCS#11."""
    possible_paths = [
        '/usr/lib/aarch64-linux-gnu/pkcs11/opensc-pkcs11.so',  # ARM64 (Apple Silicon)
        '/usr/lib/x86_64-linux-gnu/pkcs11/opensc-pkcs11.so',   # x86_64
        '/usr/lib/aarch64-linux-gnu/opensc-pkcs11.so',
        '/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so',
        '/usr/lib/pkcs11/opensc-pkcs11.so',
        '/usr/local/lib/opensc-pkcs11.so',
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return possible_paths[0]  # Fallback

PKCS11_LIB = os.getenv('PKCS11_MODULE', find_pkcs11_lib())


def list_slots(pkcs11lib):
    """Liste tous les slots disponibles."""
    print("\n=== Slots Disponibles ===")
    
    slots = pkcs11lib.getSlotList(tokenPresent=False)
    print(f"Nombre total de slots: {len(slots)}")
    
    for slot_id in slots:
        try:
            slot_info = pkcs11lib.getSlotInfo(slot_id)
            print(f"\nSlot {slot_id}:")
            print(f"  Description: {slot_info.slotDescription.strip()}")
            print(f"  Manufacturer: {slot_info.manufacturerID.strip()}")
            print(f"  Flags: {slot_info.flags}")
            
            # Vérifier si un token est présent
            if slot_info.flags & PyKCS11.CKF_TOKEN_PRESENT:
                token_info = pkcs11lib.getTokenInfo(slot_id)
                print(f"  Token présent:")
                print(f"    Label: {token_info.label.strip()}")
                print(f"    Model: {token_info.model.strip()}")
                print(f"    Serial: {token_info.serialNumber.strip()}")
                print(f"    Flags: {token_info.flags}")
            else:
                print("  Aucun token présent")
                
        except PyKCS11.PyKCS11Error as e:
            print(f"  Erreur: {e}")
    
    return slots


def list_objects(session, obj_class=None):
    """Liste les objets dans le token."""
    print("\n=== Objets dans le Token ===")
    
    template = []
    if obj_class:
        template = [(PyKCS11.CKA_CLASS, obj_class)]
    
    objects = session.findObjects(template)
    
    obj_types = {
        PyKCS11.CKO_CERTIFICATE: "Certificate",
        PyKCS11.CKO_PUBLIC_KEY: "Public Key",
        PyKCS11.CKO_PRIVATE_KEY: "Private Key",
        PyKCS11.CKO_SECRET_KEY: "Secret Key",
        PyKCS11.CKO_DATA: "Data Object",
    }
    
    for obj in objects:
        attrs = session.getAttributeValue(obj, [
            PyKCS11.CKA_CLASS,
            PyKCS11.CKA_LABEL,
            PyKCS11.CKA_ID,
        ])
        
        obj_class = attrs[0]
        label = bytes(attrs[1]).decode('utf-8', errors='ignore') if attrs[1] else "<no label>"
        obj_id = bytes(attrs[2]).hex() if attrs[2] else "<no id>"
        
        type_name = obj_types.get(obj_class, f"Unknown ({obj_class})")
        print(f"  - {type_name}: {label} (ID: {obj_id})")
    
    return objects


def generate_rsa_keypair(session, key_label="Test RSA Key", key_size=2048):
    """Génère une paire de clés RSA."""
    print(f"\n=== Génération de clé RSA ({key_size} bits) ===")
    
    # Template pour la clé publique
    public_template = [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_PUBLIC_KEY),
        (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_RSA),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_MODULUS_BITS, key_size),
        (PyKCS11.CKA_LABEL, key_label),
        (PyKCS11.CKA_ID, bytes([0x01])),
        (PyKCS11.CKA_ENCRYPT, True),
        (PyKCS11.CKA_VERIFY, True),
        (PyKCS11.CKA_WRAP, True),
    ]
    
    # Template pour la clé privée
    private_template = [
        (PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY),
        (PyKCS11.CKA_KEY_TYPE, PyKCS11.CKK_RSA),
        (PyKCS11.CKA_TOKEN, True),
        (PyKCS11.CKA_PRIVATE, True),
        (PyKCS11.CKA_SENSITIVE, True),
        (PyKCS11.CKA_LABEL, key_label),
        (PyKCS11.CKA_ID, bytes([0x01])),
        (PyKCS11.CKA_DECRYPT, True),
        (PyKCS11.CKA_SIGN, True),
        (PyKCS11.CKA_UNWRAP, True),
    ]
    
    try:
        pub_key, priv_key = session.generateKeyPair(
            public_template,
            private_template,
            mecha=PyKCS11.Mechanism(PyKCS11.CKM_RSA_PKCS_KEY_PAIR_GEN)
        )
        print(f"✓ Clés générées avec succès")
        print(f"  Public key handle: {pub_key}")
        print(f"  Private key handle: {priv_key}")
        return pub_key, priv_key
    except PyKCS11.PyKCS11Error as e:
        print(f"✗ Erreur de génération: {e}")
        return None, None


def test_sign_verify(session, priv_key, pub_key):
    """Teste la signature et vérification."""
    print("\n=== Test Signature RSA ===")
    
    test_data = b"Hello, JavaCard!"
    
    try:
        # Signature
        mechanism = PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS)
        signature = bytes(session.sign(priv_key, test_data, mechanism))
        print(f"✓ Signature: {signature[:32].hex()}...")
        
        # Vérification
        result = session.verify(pub_key, test_data, signature, mechanism)
        print(f"✓ Vérification: {'OK' if result else 'FAILED'}")
        
        return True
    except PyKCS11.PyKCS11Error as e:
        print(f"✗ Erreur: {e}")
        return False


def test_encrypt_decrypt(session, pub_key, priv_key):
    """Teste le chiffrement/déchiffrement RSA."""
    print("\n=== Test Chiffrement RSA ===")
    
    test_data = b"Secret message"
    
    try:
        # Chiffrement avec clé publique
        mechanism = PyKCS11.Mechanism(PyKCS11.CKM_RSA_PKCS)
        encrypted = bytes(session.encrypt(pub_key, test_data, mechanism))
        print(f"✓ Chiffré: {encrypted[:32].hex()}...")
        
        # Déchiffrement avec clé privée
        decrypted = bytes(session.decrypt(priv_key, encrypted, mechanism))
        print(f"✓ Déchiffré: {decrypted}")
        
        if decrypted == test_data:
            print("✓ Données identiques!")
            return True
        else:
            print("✗ Données différentes!")
            return False
            
    except PyKCS11.PyKCS11Error as e:
        print(f"✗ Erreur: {e}")
        return False


def main():
    print("=" * 60)
    print("  Test PKCS#11 avec JavaCard Émulée")
    print("=" * 60)
    print(f"Module PKCS#11: {PKCS11_LIB}")
    
    # Charger la librairie PKCS#11
    try:
        pkcs11lib = PyKCS11.PyKCS11Lib()
        pkcs11lib.load(PKCS11_LIB)
        print("✓ Module PKCS#11 chargé")
    except Exception as e:
        print(f"✗ Erreur de chargement: {e}")
        sys.exit(1)
    
    # Lister les slots
    slots = list_slots(pkcs11lib)
    
    if not slots:
        print("Aucun slot disponible")
        sys.exit(1)
    
    # Trouver un slot avec token
    token_slot = None
    for slot_id in slots:
        try:
            slot_info = pkcs11lib.getSlotInfo(slot_id)
            if slot_info.flags & PyKCS11.CKF_TOKEN_PRESENT:
                token_slot = slot_id
                break
        except:
            pass
    
    if token_slot is None:
        print("\n✗ Aucun token trouvé")
        print("Assurez-vous que jCardSim et le bridge PC/SC sont actifs")
        sys.exit(1)
    
    print(f"\n✓ Utilisation du slot {token_slot}")
    
    # Ouvrir une session
    try:
        session = pkcs11lib.openSession(token_slot, PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
        print("✓ Session ouverte")
        
        # Login (PIN par défaut pour les tests)
        pin = os.getenv('TOKEN_PIN', '12345678')
        try:
            session.login(pin)
            print("✓ Login réussi")
        except PyKCS11.PyKCS11Error as e:
            if 'CKR_USER_ALREADY_LOGGED_IN' in str(e):
                print("✓ Déjà connecté")
            else:
                print(f"⚠ Login: {e}")
        
        # Lister les objets existants
        list_objects(session)
        
        # Demander si on veut générer des clés
        response = input("\nGénérer une paire de clés RSA de test? (o/n): ")
        if response.lower() in ('o', 'y', 'oui', 'yes'):
            pub_key, priv_key = generate_rsa_keypair(session)
            
            if pub_key and priv_key:
                # Tester signature
                test_sign_verify(session, priv_key, pub_key)
                
                # Tester chiffrement
                test_encrypt_decrypt(session, pub_key, priv_key)
        
        # Logout et fermeture
        try:
            session.logout()
        except:
            pass
        session.closeSession()
        print("\n✓ Session fermée")
        
    except PyKCS11.PyKCS11Error as e:
        print(f"✗ Erreur de session: {e}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("  Tests terminés")
    print("=" * 60)


if __name__ == '__main__':
    main()
