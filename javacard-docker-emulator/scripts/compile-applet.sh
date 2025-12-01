#!/bin/bash
# =============================================================================
# compile-applet.sh - Compile un applet JavaCard pour jCardSim
# =============================================================================

set -e

# Configuration
JC_HOME=${JC_HOME:-/opt/javacard/jc305u3_kit}
ANT_JAVACARD=${ANT_JAVACARD:-/opt/ant-javacard.jar}
OUTPUT_DIR=${OUTPUT_DIR:-/app/applets}

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 <applet_source_dir> [options]"
    echo ""
    echo "Options:"
    echo "  -o, --output DIR    Output directory (default: $OUTPUT_DIR)"
    echo "  -a, --aid AID       Applet AID in hex (required)"
    echo "  -p, --package PKG   Package AID (default: derived from applet AID)"
    echo "  -c, --class CLASS   Applet class name (required)"
    echo "  -v, --version VER   Applet version (default: 1.0.0)"
    echo "  -h, --help          Show this help"
    echo ""
    echo "Example:"
    echo "  $0 ./myapplet -a F0000000010001 -c com.example.MyApplet"
    exit 1
}

# Parse arguments
APPLET_AID=""
PACKAGE_AID=""
APPLET_CLASS=""
VERSION="1.0.0"
SOURCE_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -a|--aid)
            APPLET_AID="$2"
            shift 2
            ;;
        -p|--package)
            PACKAGE_AID="$2"
            shift 2
            ;;
        -c|--class)
            APPLET_CLASS="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            if [ -z "$SOURCE_DIR" ]; then
                SOURCE_DIR="$1"
            fi
            shift
            ;;
    esac
done

# Vérifications
if [ -z "$SOURCE_DIR" ]; then
    echo -e "${RED}Error: Source directory required${NC}"
    usage
fi

if [ -z "$APPLET_AID" ]; then
    echo -e "${RED}Error: Applet AID required (-a)${NC}"
    usage
fi

if [ -z "$APPLET_CLASS" ]; then
    echo -e "${RED}Error: Applet class required (-c)${NC}"
    usage
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo -e "${RED}Error: Source directory not found: $SOURCE_DIR${NC}"
    exit 1
fi

# Dériver le package AID si non spécifié (premiers 5-7 bytes de l'AID)
if [ -z "$PACKAGE_AID" ]; then
    PACKAGE_AID="${APPLET_AID:0:14}"
fi

# Nom du package basé sur la classe
PACKAGE_NAME=$(echo "$APPLET_CLASS" | rev | cut -d'.' -f2- | rev)
APPLET_NAME=$(echo "$APPLET_CLASS" | rev | cut -d'.' -f1 | rev)

echo "=========================================="
echo -e "${GREEN}  JavaCard Applet Compilation${NC}"
echo "=========================================="
echo "Source:       $SOURCE_DIR"
echo "Class:        $APPLET_CLASS"
echo "Applet AID:   $APPLET_AID"
echo "Package AID:  $PACKAGE_AID"
echo "Version:      $VERSION"
echo "Output:       $OUTPUT_DIR"
echo "=========================================="

# Créer le répertoire de travail
WORK_DIR=$(mktemp -d)
trap "rm -rf $WORK_DIR" EXIT

# Copier les sources
cp -r "$SOURCE_DIR"/* "$WORK_DIR/"

# Créer le build.xml pour ant-javacard
cat > "$WORK_DIR/build.xml" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<project name="JavaCardApplet" default="build" basedir=".">
    
    <property name="jc.home" value="${JC_HOME}"/>
    <property name="ant.javacard.jar" value="${ANT_JAVACARD}"/>
    
    <taskdef name="javacard" 
             classname="pro.javacard.ant.JavaCard" 
             classpath="\${ant.javacard.jar}"/>
    
    <target name="build">
        <javacard jckit="\${jc.home}">
            <cap output="${OUTPUT_DIR}/${APPLET_NAME}.cap"
                 aid="${PACKAGE_AID}"
                 version="${VERSION}">
                
                <applet class="${APPLET_CLASS}" 
                        aid="${APPLET_AID}"/>
                
                <import jar="\${jc.home}/lib/api_classic.jar"/>
            </cap>
        </javacard>
    </target>
    
</project>
EOF

echo -e "\n${YELLOW}Compiling...${NC}"

# Compiler avec ant
cd "$WORK_DIR"
ant -f build.xml build

# Vérifier le résultat
if [ -f "${OUTPUT_DIR}/${APPLET_NAME}.cap" ]; then
    echo -e "\n${GREEN}✓ Compilation successful!${NC}"
    echo "Output: ${OUTPUT_DIR}/${APPLET_NAME}.cap"
    
    # Afficher les infos du CAP
    echo -e "\n${YELLOW}CAP file info:${NC}"
    ls -lh "${OUTPUT_DIR}/${APPLET_NAME}.cap"
    
    # Créer aussi un JAR pour jCardSim
    echo -e "\n${YELLOW}Creating JAR for jCardSim...${NC}"
    
    # Compiler les classes Java
    mkdir -p "$WORK_DIR/classes"
    find "$WORK_DIR" -name "*.java" -exec javac \
        -cp "${JC_HOME}/lib/api_classic.jar" \
        -d "$WORK_DIR/classes" \
        -source 1.8 -target 1.8 \
        {} +
    
    # Créer le JAR
    jar cf "${OUTPUT_DIR}/${APPLET_NAME}.jar" -C "$WORK_DIR/classes" .
    echo -e "${GREEN}✓ JAR created: ${OUTPUT_DIR}/${APPLET_NAME}.jar${NC}"
else
    echo -e "\n${RED}✗ Compilation failed${NC}"
    exit 1
fi

echo -e "\n${GREEN}Done!${NC}"
