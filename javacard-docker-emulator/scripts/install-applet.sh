#!/bin/bash
# =============================================================================
# install-applet.sh - Installe un applet sur la carte émulée via GlobalPlatform
# =============================================================================

set -e

# Configuration
GP_JAR=${GP_JAR:-/opt/gp.jar}
JCARDSIM_HOST=${JCARDSIM_HOST:-localhost}
JCARDSIM_PORT=${JCARDSIM_PORT:-9025}

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

usage() {
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  list                List installed applets"
    echo "  install <cap>       Install CAP file"
    echo "  delete <aid>        Delete applet by AID"
    echo "  info                Show card info"
    echo ""
    echo "Options:"
    echo "  -h, --host HOST     jCardSim host (default: $JCARDSIM_HOST)"
    echo "  -p, --port PORT     jCardSim port (default: $JCARDSIM_PORT)"
    echo "  -d, --debug         Enable debug output"
    echo "  --help              Show this help"
    echo ""
    echo "Examples:"
    echo "  $0 list"
    echo "  $0 install /app/applets/MyApplet.cap"
    echo "  $0 delete F0000000010001"
    exit 1
}

# Fonction pour exécuter GP
run_gp() {
    local debug_flag=""
    if [ "$DEBUG" = "true" ]; then
        debug_flag="-d"
    fi
    
    # GP peut utiliser un lecteur PC/SC ou une connexion directe
    # Pour jCardSim, on utilise une connexion socket via un wrapper
    java -jar "$GP_JAR" \
        --reader "Virtual" \
        $debug_flag \
        "$@"
}

# Alternative: utiliser notre script Python pour les commandes GP de base
run_gp_socket() {
    python3 /app/scripts/gp-commands.py \
        --host "$JCARDSIM_HOST" \
        --port "$JCARDSIM_PORT" \
        "$@"
}

# Parse arguments
COMMAND=""
DEBUG="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            JCARDSIM_HOST="$2"
            shift 2
            ;;
        -p|--port)
            JCARDSIM_PORT="$2"
            shift 2
            ;;
        -d|--debug)
            DEBUG="true"
            shift
            ;;
        --help)
            usage
            ;;
        list|install|delete|info)
            COMMAND="$1"
            shift
            break
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

if [ -z "$COMMAND" ]; then
    usage
fi

echo "=========================================="
echo -e "${CYAN}  GlobalPlatform Card Management${NC}"
echo "=========================================="
echo "Host: $JCARDSIM_HOST:$JCARDSIM_PORT"
echo "Command: $COMMAND"
echo "=========================================="

case $COMMAND in
    list)
        echo -e "\n${YELLOW}Listing installed applets...${NC}\n"
        run_gp --list || {
            echo -e "\n${YELLOW}Trying direct socket connection...${NC}"
            # Utiliser notre script Python comme fallback
            python3 << 'PYEOF'
import socket
import struct
import os

host = os.getenv('JCARDSIM_HOST', 'localhost')
port = int(os.getenv('JCARDSIM_PORT', '9025'))

def send_apdu(sock, apdu_hex):
    apdu = bytes.fromhex(apdu_hex.replace(' ', ''))
    length = struct.pack('>H', len(apdu))
    sock.sendall(length + apdu)
    
    resp_len = struct.unpack('>H', sock.recv(2))[0]
    return sock.recv(resp_len)

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((host, port))

# SELECT ISD (Card Manager)
resp = send_apdu(sock, "00A4040008A000000003000000")
print(f"SELECT ISD: {resp.hex().upper()}")

# GET STATUS - Installed packages
resp = send_apdu(sock, "80F28000024F0000")
if resp[-2:] == b'\x90\x00':
    print("\nInstalled packages/applets:")
    # Parse TLV response
    data = resp[:-2]
    i = 0
    while i < len(data):
        if data[i] == 0xE3:  # Application entry
            length = data[i+1]
            entry = data[i+2:i+2+length]
            aid_len = entry[0]
            aid = entry[1:1+aid_len].hex().upper()
            print(f"  AID: {aid}")
            i += 2 + length
        else:
            i += 1
else:
    print(f"GET STATUS failed: {resp.hex().upper()}")

sock.close()
PYEOF
        }
        ;;
        
    install)
        CAP_FILE="$1"
        if [ -z "$CAP_FILE" ]; then
            echo -e "${RED}Error: CAP file required${NC}"
            exit 1
        fi
        
        if [ ! -f "$CAP_FILE" ]; then
            echo -e "${RED}Error: File not found: $CAP_FILE${NC}"
            exit 1
        fi
        
        echo -e "\n${YELLOW}Installing: $CAP_FILE${NC}\n"
        run_gp --install "$CAP_FILE" || {
            echo -e "${RED}Installation via GP failed${NC}"
            echo -e "${YELLOW}Note: For jCardSim, you may need to configure the applet in jcardsim.cfg${NC}"
        }
        ;;
        
    delete)
        AID="$1"
        if [ -z "$AID" ]; then
            echo -e "${RED}Error: AID required${NC}"
            exit 1
        fi
        
        echo -e "\n${YELLOW}Deleting applet: $AID${NC}\n"
        run_gp --delete "$AID" || {
            echo -e "${RED}Deletion failed${NC}"
        }
        ;;
        
    info)
        echo -e "\n${YELLOW}Getting card info...${NC}\n"
        run_gp --info || {
            echo -e "${YELLOW}Trying basic info via socket...${NC}"
            python3 /app/scripts/send-apdu.py "00A4040008A000000003000000"
        }
        ;;
esac

echo -e "\n${GREEN}Done!${NC}"
