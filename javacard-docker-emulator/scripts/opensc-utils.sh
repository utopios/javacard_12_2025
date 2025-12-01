#!/bin/bash
# =============================================================================
# opensc-utils.sh - Utilitaires OpenSC pour la carte émulée
# =============================================================================

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

show_menu() {
    echo ""
    echo -e "${CYAN}=========================================="
    echo "  OpenSC Utilities - JavaCard Emulator"
    echo "==========================================${NC}"
    echo ""
    echo "1) List readers"
    echo "2) Card info (ATR, protocols)"
    echo "3) List PKCS#15 objects"
    echo "4) List certificates"
    echo "5) List keys"
    echo "6) Initialize PKCS#15 structure"
    echo "7) Generate RSA key pair"
    echo "8) Test PKCS#11 module"
    echo "9) Send custom APDU"
    echo "0) Exit"
    echo ""
    echo -n "Choice: "
}

list_readers() {
    echo -e "\n${YELLOW}=== PC/SC Readers ===${NC}"
    pcsc_scan -n || echo -e "${RED}No readers found or pcscd not running${NC}"
}

card_info() {
    echo -e "\n${YELLOW}=== Card Information ===${NC}"
    
    echo -e "\n${CYAN}ATR:${NC}"
    opensc-tool --atr 2>/dev/null || echo "Could not read ATR"
    
    echo -e "\n${CYAN}Card name:${NC}"
    opensc-tool --name 2>/dev/null || echo "Unknown"
    
    echo -e "\n${CYAN}Serial number:${NC}"
    opensc-tool --serial 2>/dev/null || echo "Unknown"
}

list_pkcs15() {
    echo -e "\n${YELLOW}=== PKCS#15 Objects ===${NC}"
    pkcs15-tool --dump 2>/dev/null || {
        echo -e "${RED}PKCS#15 not initialized or not supported${NC}"
        echo "Use option 6 to initialize PKCS#15 structure"
    }
}

list_certs() {
    echo -e "\n${YELLOW}=== Certificates ===${NC}"
    pkcs15-tool --list-certificates 2>/dev/null || {
        echo -e "${YELLOW}No certificates found${NC}"
    }
}

list_keys() {
    echo -e "\n${YELLOW}=== Keys ===${NC}"
    
    echo -e "\n${CYAN}Public keys:${NC}"
    pkcs15-tool --list-public-keys 2>/dev/null || echo "None"
    
    echo -e "\n${CYAN}Private keys:${NC}"
    pkcs15-tool --list-keys 2>/dev/null || echo "None"
}

init_pkcs15() {
    echo -e "\n${YELLOW}=== Initialize PKCS#15 ===${NC}"
    echo -e "${RED}WARNING: This will erase existing data!${NC}"
    echo -n "Continue? (yes/no): "
    read confirm
    
    if [ "$confirm" != "yes" ]; then
        echo "Aborted"
        return
    fi
    
    echo -e "\n${CYAN}Creating PKCS#15 structure...${NC}"
    
    # Créer la structure PKCS#15
    pkcs15-init --create-pkcs15 \
        --profile pkcs15+onepin \
        --label "JavaCard Token" \
        --so-pin 12345678 \
        --so-puk 12345678 \
        --pin 12345678 \
        --puk 12345678 \
        2>/dev/null && echo -e "${GREEN}✓ PKCS#15 initialized${NC}" || {
        echo -e "${RED}✗ Initialization failed${NC}"
        echo "The card may not support PKCS#15 initialization"
    }
}

generate_key() {
    echo -e "\n${YELLOW}=== Generate RSA Key Pair ===${NC}"
    
    echo -n "Key label (default: 'RSA Key'): "
    read key_label
    key_label=${key_label:-"RSA Key"}
    
    echo -n "Key size [1024/2048/4096] (default: 2048): "
    read key_size
    key_size=${key_size:-2048}
    
    echo -n "PIN: "
    read -s pin
    echo ""
    
    echo -e "\n${CYAN}Generating key...${NC}"
    
    pkcs15-init --generate-key rsa/${key_size} \
        --auth-id 01 \
        --label "$key_label" \
        --pin "$pin" \
        2>/dev/null && echo -e "${GREEN}✓ Key generated${NC}" || {
        echo -e "${RED}✗ Key generation failed${NC}"
    }
}

test_pkcs11() {
    echo -e "\n${YELLOW}=== PKCS#11 Module Test ===${NC}"
    
    PKCS11_MOD=${PKCS11_MODULE:-/usr/lib/x86_64-linux-gnu/pkcs11/opensc-pkcs11.so}
    
    echo -e "${CYAN}Module: $PKCS11_MOD${NC}"
    
    echo -e "\n${CYAN}Listing slots:${NC}"
    pkcs11-tool --module "$PKCS11_MOD" --list-slots 2>/dev/null || {
        echo -e "${RED}Failed to list slots${NC}"
        return
    }
    
    echo -e "\n${CYAN}Listing mechanisms:${NC}"
    pkcs11-tool --module "$PKCS11_MOD" --list-mechanisms 2>/dev/null || true
    
    echo -e "\n${CYAN}Listing objects:${NC}"
    echo -n "PIN (or press Enter to skip): "
    read -s pin
    echo ""
    
    if [ -n "$pin" ]; then
        pkcs11-tool --module "$PKCS11_MOD" --login --pin "$pin" --list-objects 2>/dev/null || true
    else
        pkcs11-tool --module "$PKCS11_MOD" --list-objects 2>/dev/null || true
    fi
}

send_apdu() {
    echo -e "\n${YELLOW}=== Send APDU ===${NC}"
    echo "Format: CLA INS P1 P2 [Lc] [Data] [Le]"
    echo "Example: 00 A4 04 00 07 A0000000041010"
    echo ""
    echo -n "APDU (hex): "
    read apdu
    
    if [ -z "$apdu" ]; then
        echo "No APDU entered"
        return
    fi
    
    echo -e "\n${CYAN}Sending...${NC}"
    opensc-tool --send-apdu "$apdu" 2>/dev/null || {
        echo -e "${YELLOW}Trying with scriptor...${NC}"
        echo "$apdu" | scriptor 2>/dev/null || {
            echo -e "${YELLOW}Trying direct socket...${NC}"
            python3 /app/scripts/send-apdu.py "$apdu"
        }
    }
}

# Menu principal
while true; do
    show_menu
    read choice
    
    case $choice in
        1) list_readers ;;
        2) card_info ;;
        3) list_pkcs15 ;;
        4) list_certs ;;
        5) list_keys ;;
        6) init_pkcs15 ;;
        7) generate_key ;;
        8) test_pkcs11 ;;
        9) send_apdu ;;
        0|q|exit) 
            echo -e "\n${GREEN}Goodbye!${NC}"
            exit 0 
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            ;;
    esac
    
    echo ""
    echo -n "Press Enter to continue..."
    read
done
