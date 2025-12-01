#!/bin/bash
# =============================================================================
# setup-mac.sh - Script d'installation pour macOS
# =============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     JavaCard Docker Emulator - macOS Setup                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Vérifier si on est sur macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo -e "${YELLOW}Warning: This script is designed for macOS${NC}"
fi

# Fonction pour vérifier une commande
check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 is installed"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 is NOT installed"
        return 1
    fi
}

# Fonction pour installer avec Homebrew
brew_install() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${YELLOW}Installing $1...${NC}"
        brew install "$1"
    fi
}

echo -e "\n${CYAN}Checking prerequisites...${NC}\n"

# Vérifier Docker
if ! check_command docker; then
    echo -e "\n${YELLOW}Docker Desktop is required.${NC}"
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    echo ""
    read -p "Open Docker Desktop download page? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "https://www.docker.com/products/docker-desktop"
    fi
    exit 1
fi

# Vérifier que Docker est en cours d'exécution
if ! docker info &> /dev/null; then
    echo -e "\n${YELLOW}Docker is not running.${NC}"
    echo "Please start Docker Desktop and run this script again."
    exit 1
fi
echo -e "  ${GREEN}✓${NC} Docker is running"

# Vérifier Docker Compose
if ! check_command "docker compose" && ! check_command docker-compose; then
    echo -e "\n${YELLOW}Docker Compose is required.${NC}"
    echo "It should be included with Docker Desktop."
fi

# Vérifier Homebrew
if ! check_command brew; then
    echo -e "\n${YELLOW}Homebrew is recommended for installing dependencies.${NC}"
    read -p "Install Homebrew? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
fi

# Vérifier Python 3
if ! check_command python3; then
    echo -e "\n${YELLOW}Python 3 is recommended for local scripts.${NC}"
    if command -v brew &> /dev/null; then
        read -p "Install Python 3 via Homebrew? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            brew install python3
        fi
    fi
fi

# Vérifier make
check_command make

echo -e "\n${CYAN}Installing Python dependencies for local scripts...${NC}\n"

# Installer les dépendances Python locales (optionnel)
if command -v pip3 &> /dev/null; then
    pip3 install --user pyscard 2>/dev/null || echo -e "${YELLOW}  Note: pyscard requires PC/SC libraries${NC}"
fi

echo -e "\n${CYAN}Creating required directories...${NC}\n"

# Créer les répertoires
mkdir -p data logs tests
echo -e "  ${GREEN}✓${NC} Directories created"

echo -e "\n${CYAN}Building Docker images...${NC}\n"

# Construire les images
docker compose build

echo -e "\n${CYAN}Starting services...${NC}\n"

# Démarrer les services
docker compose up -d

# Attendre que les services soient prêts
echo -e "\n${YELLOW}Waiting for services to be ready...${NC}"
sleep 5

# Vérifier la connexion
echo -e "\n${CYAN}Testing connection...${NC}\n"

if nc -z localhost 9025 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} jCardSim is accessible on port 9025"
else
    echo -e "  ${YELLOW}⚠${NC} jCardSim might not be ready yet. Check logs with: make logs"
fi

echo -e "\n${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    Setup Complete!                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${CYAN}Quick Start:${NC}"
echo ""
echo "  make status       # Check service status"
echo "  make test         # Run tests"
echo "  make apdu-shell   # Interactive APDU shell"
echo "  make shell        # Open test client shell"
echo ""
echo -e "${CYAN}Useful commands:${NC}"
echo ""
echo "  make logs         # View all logs"
echo "  make down         # Stop services"
echo "  make help         # Show all commands"
echo ""
echo -e "${YELLOW}Documentation:${NC} README.md"
echo ""
