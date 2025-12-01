#!/bin/bash
# =============================================================================
# start-pcsc-bridge.sh - Démarre le bridge PC/SC vers jCardSim
#
# Architecture:
# 1. vpcd-proxy.py écoute sur le port 35963 en tant que SERVEUR
# 2. pcscd avec le driver vpcd se CONNECTE au port 35963 en tant que CLIENT
# 3. vpcd-proxy.py fait le pont vers jCardSim sur le port 9025
# =============================================================================

# Configuration
JCARDSIM_HOST=${JCARDSIM_HOST:-jcardsim}
JCARDSIM_PORT=${JCARDSIM_PORT:-9025}
VPCD_PORT=${VPCD_PORT:-35963}

echo "=========================================="
echo "  PC/SC Virtual Reader Bridge"
echo "=========================================="
echo "jCardSim: ${JCARDSIM_HOST}:${JCARDSIM_PORT}"
echo "VPCD Port: ${VPCD_PORT}"
echo "=========================================="

# Attendre que jCardSim soit disponible
echo "Waiting for jCardSim to be ready..."
max_attempts=60
attempt=0
while ! nc -z ${JCARDSIM_HOST} ${JCARDSIM_PORT} 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ $attempt -ge $max_attempts ]; then
        echo "ERROR: jCardSim not available after ${max_attempts} attempts"
        exit 1
    fi
    echo "  Attempt $attempt/$max_attempts..."
    sleep 2
done
echo "jCardSim is ready!"

# Créer les répertoires nécessaires
mkdir -p /run/pcscd

# Trouver le chemin de la librairie vpcd
VPCD_LIB=$(find /usr -name 'libifdvpcd.so' 2>/dev/null | head -1)
if [ -z "$VPCD_LIB" ]; then
    VPCD_LIB="/usr/lib/pcsc/drivers/serial/libifdvpcd.so"
fi
echo "Found VPCD library: $VPCD_LIB"

# Supprimer toutes les anciennes configs vpcd
rm -f /etc/reader.conf.d/*.conf 2>/dev/null || true

# Configurer vpcd pour pcscd (un seul lecteur)
echo "Configuring VPCD (single reader)..."
cat > /etc/reader.conf.d/vpcd.conf << EOF
FRIENDLYNAME "jCardSim Virtual Reader"
DEVICENAME localhost:${VPCD_PORT}
LIBPATH ${VPCD_LIB}
CHANNELID 0x8C7B
EOF

echo "VPCD configuration:"
cat /etc/reader.conf.d/vpcd.conf

# Fonction de nettoyage
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $PROXY_PID 2>/dev/null || true
    kill $PCSCD_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

# 1. D'ABORD: Démarrer le proxy VPCD-jCardSim
# Ce proxy transmet les APDUs de pcscd vers jCardSim
echo ""
echo "Starting VPCD-jCardSim proxy on port ${VPCD_PORT}..."
python3 /app/scripts/vpcd-jcardsim-proxy.py &
PROXY_PID=$!
sleep 3

if ps -p $PROXY_PID > /dev/null 2>&1; then
    echo "VPCD proxy server started (PID: $PROXY_PID)"
else
    echo "ERROR: VPCD proxy failed to start"
    exit 1
fi

# Attendre que le serveur soit prêt
echo "Waiting for VPCD proxy server to be ready..."
attempt=0
while ! nc -z localhost ${VPCD_PORT} 2>/dev/null; do
    attempt=$((attempt + 1))
    if [ $attempt -ge 10 ]; then
        echo "ERROR: VPCD proxy not listening"
        exit 1
    fi
    sleep 1
done
echo "VPCD proxy server is ready on port ${VPCD_PORT}"

# 2. ENSUITE: Démarrer pcscd (il se connectera à notre serveur)
echo ""
echo "Starting pcscd daemon (will connect to VPCD proxy)..."
pkill -9 pcscd 2>/dev/null || true
sleep 1
pcscd --foreground &
PCSCD_PID=$!
sleep 3

if ps -p $PCSCD_PID > /dev/null 2>&1; then
    echo "pcscd started (PID: $PCSCD_PID)"
else
    echo "ERROR: pcscd failed to start"
fi

echo ""
echo "=========================================="
echo "  PC/SC Bridge Started"
echo "=========================================="
echo ""
echo "Reader name: Virtual JavaCard Reader"
echo ""
echo "Available commands (from opensc-middleware):"
echo "  pcsc_scan           - Scan for readers"
echo "  opensc-tool -l      - List readers"
echo "  opensc-tool -a      - Show ATR"
echo "  pkcs11-tool -L      - List PKCS#11 slots"
echo ""

# Boucle principale - surveiller les processus
while true; do
    if ! ps -p $PROXY_PID > /dev/null 2>&1; then
        echo "$(date): VPCD proxy died, restarting..."
        python3 /app/scripts/vpcd-jcardsim-proxy.py &
        PROXY_PID=$!
        sleep 3
    fi
    if ! ps -p $PCSCD_PID > /dev/null 2>&1; then
        echo "$(date): pcscd died, restarting..."
        pcscd --foreground &
        PCSCD_PID=$!
        sleep 3
    fi
    sleep 10
done
