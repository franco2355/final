#!/bin/bash

# Script de instalación automática de ROS 2 para Joystick Xbox
# Detección automática de Ubuntu version y ROS 2 distro

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# ==============================================================================
# Detectar versión de Ubuntu
# ==============================================================================

print_header "DETECCIÓN DE SISTEMA"

UBUNTU_VERSION=$(lsb_release -cs 2>/dev/null || echo "unknown")
print_info "Ubuntu version: $UBUNTU_VERSION"

case $UBUNTU_VERSION in
    focal)
        ROS_DISTRO="foxy"
        ;;
    jammy)
        ROS_DISTRO="humble"
        ;;
    noble)
        ROS_DISTRO="iron"
        ;;
    plucky)
        ROS_DISTRO="jazzy"
        ;;
    *)
        print_error "Ubuntu version no soportada: $UBUNTU_VERSION"
        echo "Soportadas: focal (foxy), jammy (humble), noble (iron), plucky (jazzy)"
        exit 1
        ;;
esac

print_success "Usando ROS 2 Distro: $ROS_DISTRO"

# ==============================================================================
# Verificar si ROS 2 ya está instalado
# ==============================================================================

print_header "VERIFICANDO ROS 2"

if [ -d "/opt/ros/$ROS_DISTRO" ]; then
    print_success "ROS 2 $ROS_DISTRO ya está instalado"
    print_info "Sourcear con: source /opt/ros/$ROS_DISTRO/setup.bash"
    exit 0
fi

# ==============================================================================
# Instalar ROS 2
# ==============================================================================

print_header "INSTALANDO ROS 2 $ROS_DISTRO"

echo "Esto requiere permisos de sudo y descargará ~2GB de software"
echo ""
read -p "¿Continuar? [s/N]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    print_error "Instalación cancelada"
    exit 1
fi

# 1. Setup locale
print_info "1/5 Configurando locale..."
sudo apt update > /dev/null 2>&1
sudo locale-gen en_US en_US.UTF-8 > /dev/null 2>&1
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 > /dev/null 2>&1
print_success "Locale configurado"

# 2. Setup sources
print_info "2/5 Agregando repositorio de ROS 2..."
sudo apt install -y software-properties-common > /dev/null 2>&1
sudo add-apt-repository -y universe > /dev/null 2>&1
sudo curl -sSL https://repo.ros2.org/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg > /dev/null 2>&1
echo "deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $UBUNTU_VERSION main" | \
    sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
print_success "Repositorio agregado"

# 3. Update
print_info "3/5 Actualizando apt..."
sudo apt update > /dev/null 2>&1
print_success "Apt actualizado"

# 4. Install ROS 2
print_info "4/5 Instalando ROS 2 $ROS_DISTRO (esto puede tomar unos minutos)..."
sudo apt install -y ros-$ROS_DISTRO-desktop ros-$ROS_DISTRO-dev > /dev/null 2>&1
print_success "ROS 2 instalado"

# 5. Install build tools
print_info "5/5 Instalando herramientas de compilación..."
sudo apt install -y python3-colcon-common-extensions > /dev/null 2>&1
sudo apt install -y ros-$ROS_DISTRO-joy > /dev/null 2>&1
print_success "Herramientas instaladas"

# ==============================================================================
# Verificar instalación
# ==============================================================================

print_header "VERIFICANDO INSTALACIÓN"

if [ -d "/opt/ros/$ROS_DISTRO" ]; then
    print_success "ROS 2 $ROS_DISTRO instalado correctamente"
else
    print_error "Instalación falló"
    exit 1
fi

# ==============================================================================
# Próximos pasos
# ==============================================================================

print_header "PRÓXIMOS PASOS"

echo "1. Agregar a ~/.bashrc (PERMANENTE):"
echo ""
echo "   echo 'source /opt/ros/$ROS_DISTRO/setup.bash' >> ~/.bashrc"
echo "   source ~/.bashrc"
echo ""
echo "2. O sourcear ahora (TEMPORAL):"
echo ""
echo "   source /opt/ros/$ROS_DISTRO/setup.bash"
echo ""
echo "3. Compilar navegacion_gps:"
echo ""
echo "   cd ~/german/aeye-ros-workspace"
echo "   colcon build --packages-select navegacion_gps"
echo "   source install/setup.bash"
echo ""
echo "4. Verificar:"
echo ""
echo "   ./check_joystick.sh"
echo ""
echo "5. Ejecutar:"
echo ""
echo "   ./start_joystick.sh"
echo ""

print_success "¡Instalación completada!"
