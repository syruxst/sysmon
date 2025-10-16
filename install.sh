#!/bin/bash

# Script de instalación para sysmon
# Instala sysmon como comando del sistema

set -e

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # Sin color

echo -e "${BLUE}"
echo "================================================"
echo "       Instalador de sysmon"
echo "       Monitor simple del sistema"
echo "================================================"
echo -e "${NC}"

# Verificar si se ejecuta con privilegios
if [ "$EUID" -ne 0 ]; then 
    echo -e "${YELLOW}Este script necesita permisos de administrador.${NC}"
    echo -e "${YELLOW}Reintentando con sudo...${NC}\n"
    sudo "$0" "$@"
    exit $?
fi

# Verificar que existe el archivo sysmon.py
if [ ! -f "sysmon.py" ]; then
    echo -e "${RED}❌ Error: No se encontró el archivo sysmon.py${NC}"
    echo -e "${RED}   Asegúrate de estar en el directorio correcto${NC}"
    exit 1
fi

# Verificar Python 3
echo -e "${BLUE}🔍 Verificando Python 3...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 no está instalado${NC}"
    echo -e "${YELLOW}   Instálalo con: sudo apt install python3${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 encontrado${NC}"

# Verificar/Instalar psutil
echo -e "\n${BLUE}🔍 Verificando psutil...${NC}"
if ! python3 -c "import psutil" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  psutil no está instalado. Instalando...${NC}"
    
    # Intentar instalar con pip3
    if command -v pip3 &> /dev/null; then
        pip3 install psutil
    else
        # Intentar con el gestor de paquetes del sistema
        if command -v apt &> /dev/null; then
            apt update && apt install -y python3-psutil
        elif command -v dnf &> /dev/null; then
            dnf install -y python3-psutil
        elif command -v pacman &> /dev/null; then
            pacman -S --noconfirm python-psutil
        else
            echo -e "${RED}❌ No se pudo instalar psutil automáticamente${NC}"
            echo -e "${YELLOW}   Instálalo manualmente con: pip3 install psutil${NC}"
            exit 1
        fi
    fi
fi
echo -e "${GREEN}✓ psutil instalado${NC}"

# Copiar el script a /usr/local/bin
echo -e "\n${BLUE}📦 Instalando sysmon...${NC}"
cp sysmon.py /usr/local/bin/sysmon
chmod +x /usr/local/bin/sysmon

# Verificar instalación
if command -v sysmon &> /dev/null; then
    echo -e "\n${GREEN}================================================"
    echo -e "✓ ¡Instalación completada exitosamente!"
    echo -e "================================================${NC}"
    echo -e "\n${BLUE}Uso:${NC}"
    echo -e "  Simplemente escribe: ${YELLOW}sysmon${NC}"
    echo -e "\n${BLUE}Para desinstalar:${NC}"
    echo -e "  sudo rm /usr/local/bin/sysmon"
else
    echo -e "${RED}❌ Hubo un problema con la instalación${NC}"
    exit 1
fi