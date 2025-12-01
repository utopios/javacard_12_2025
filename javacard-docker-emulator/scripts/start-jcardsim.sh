#!/bin/bash
# =============================================================================
# start-jcardsim.sh - Démarre le serveur jCardSim avec support socket
# =============================================================================

set -e

# Configuration
JCARDSIM_PORT=${JCARDSIM_PORT:-9025}
CONFIG_FILE=${CONFIG_FILE:-/app/config/jcardsim.cfg}
APPLETS_DIR=${APPLETS_DIR:-/app/applets}
DATA_DIR=${DATA_DIR:-/app/data}
LOG_FILE=${LOG_FILE:-/app/logs/jcardsim.log}

echo "=========================================="
echo "  jCardSim Server Starting..."
echo "=========================================="
echo "Port: ${JCARDSIM_PORT}"
echo "Config: ${CONFIG_FILE}"
echo "Applets: ${APPLETS_DIR}"
echo "=========================================="

# Construire le classpath
CLASSPATH="/app/lib/jcardsim.jar"
for jar in /app/lib/*.jar; do
    if [ -f "$jar" ] && [ "$jar" != "/app/lib/jcardsim.jar" ]; then
        CLASSPATH="${CLASSPATH}:${jar}"
    fi
done

# Ajouter les applets compilés au classpath
if [ -d "${APPLETS_DIR}" ]; then
    for applet_jar in ${APPLETS_DIR}/*.jar; do
        if [ -f "$applet_jar" ]; then
            CLASSPATH="${CLASSPATH}:${applet_jar}"
            echo "Added applet: $(basename $applet_jar)"
        fi
    done
fi

export CLASSPATH
export JCARDSIM_PORT

echo "Classpath: ${CLASSPATH}"
echo ""

# Utiliser le serveur Python (plus simple et robuste)
echo "Starting Python socket server on port ${JCARDSIM_PORT}..."
exec python3 /app/jcardsim-socket-server.py 2>&1 | tee "${LOG_FILE}"
