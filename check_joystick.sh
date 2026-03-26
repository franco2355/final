#!/bin/bash

# Verificación rápida del sistema de joystick.
# Soporta ROS 2 local o el contenedor ros2 del workspace.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
ROS_DISTRO="${ROS_DISTRO:-humble}"
WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTAINER_EXEC="$WORKSPACE_DIR/tools/exec.sh"
EXEC_MODE=""

check_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

check_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

detect_exec_mode() {
    if command -v ros2 >/dev/null 2>&1; then
        EXEC_MODE="local"
        return 0
    fi

    if [ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]; then
        # shellcheck disable=SC1090
        source "/opt/ros/$ROS_DISTRO/setup.bash"
    fi

    if command -v ros2 >/dev/null 2>&1; then
        EXEC_MODE="local"
        return 0
    fi

    if [ -x "$CONTAINER_EXEC" ]; then
        EXEC_MODE="container"
        return 0
    fi

    return 1
}

container_exec() {
    "$CONTAINER_EXEC" "$1"
}

device_exists() {
    local path="$1"

    if [ "$EXEC_MODE" = "local" ]; then
        [ -e "$path" ]
    else
        container_exec "test -e $path" >/dev/null
    fi
}

ros_pkg_exists() {
    local pkg="$1"

    if [ "$EXEC_MODE" = "local" ]; then
        ros2 pkg prefix "$pkg" >/dev/null 2>&1
    else
        container_exec "source /ros2_ws/install/setup.bash && ros2 pkg prefix $pkg >/dev/null 2>&1" >/dev/null
    fi
}

joy_run_preview() {
    if [ "$EXEC_MODE" = "local" ]; then
        echo "ros2 run joy joy_node"
    else
        echo "./tools/exec.sh 'source /ros2_ws/install/setup.bash && ros2 run joy joy_node'"
    fi
}

joystick_run_preview() {
    if [ "$EXEC_MODE" = "local" ]; then
        echo "ros2 run navegacion_gps joystick_node"
    else
        echo "./tools/exec.sh 'source /ros2_ws/install/setup.bash && export PYTHONPATH=/ros2_ws/src/navegacion_gps:\$PYTHONPATH && python3 -m navegacion_gps.joystick_node'"
    fi
}

echo -e "\n${BLUE}======================================${NC}"
echo -e "${BLUE}VERIFICACIÓN SISTEMA JOYSTICK XBOX${NC}"
echo -e "${BLUE}======================================${NC}\n"

if detect_exec_mode; then
    check_ok "Entorno ROS detectado: $EXEC_MODE"
else
    check_fail "No se encontró ROS 2 local ni acceso al contenedor"
fi

echo ""
echo -e "${BLUE}Hardware:${NC}"

if device_exists /dev/input/js0; then
    check_ok "Joystick detectado: /dev/input/js0"
else
    check_fail "Joystick NO detectado"
    check_info "Conectar Xbox por USB o Bluetooth"
fi

if device_exists /dev/input/js1; then
    check_warn "Segundo joystick detectado: /dev/input/js1"
fi

echo ""
echo -e "${BLUE}ROS 2 / Paquetes:${NC}"

if [ -n "$EXEC_MODE" ]; then
    check_info "ROS Distro: $ROS_DISTRO"

    if ros_pkg_exists joy; then
        check_ok "Paquete 'joy' instalado"
    else
        check_fail "Paquete 'joy' NO instalado"
    fi

    if ros_pkg_exists navegacion_gps; then
        check_ok "Paquete 'navegacion_gps' encontrado"
    else
        check_fail "Paquete 'navegacion_gps' NO encontrado"
    fi

    if ros_pkg_exists interfaces; then
        check_ok "Paquete 'interfaces' encontrado"
    else
        check_fail "Paquete 'interfaces' NO encontrado"
    fi
else
    check_warn "Sin entorno ROS activo; se omite la verificación de paquetes"
fi

echo ""
echo -e "${BLUE}Workspace y scripts:${NC}"

if [ -x "$WORKSPACE_DIR/start_joystick.sh" ]; then
    check_ok "start_joystick.sh disponible"
else
    check_fail "start_joystick.sh no ejecutable"
fi

if [ -x "$WORKSPACE_DIR/check_joystick.sh" ]; then
    check_ok "check_joystick.sh disponible"
else
    check_fail "check_joystick.sh no ejecutable"
fi

if [ -x "$WORKSPACE_DIR/joystick_commands.sh" ]; then
    check_ok "joystick_commands.sh disponible"
else
    check_fail "joystick_commands.sh no ejecutable"
fi

if [ -f "$WORKSPACE_DIR/install/setup.bash" ]; then
    check_ok "Workspace compilado: install/setup.bash"
else
    check_warn "Workspace no compilado todavía"
fi

if [ -f "$WORKSPACE_DIR/src/navegacion_gps/navegacion_gps/joystick_node.py" ]; then
    check_ok "joystick_node.py presente en source tree"
else
    check_fail "joystick_node.py no encontrado"
fi

echo ""
echo -e "${BLUE}Comandos recomendados:${NC}"
echo "1. joy_node:"
echo "   $(joy_run_preview)"
echo ""
echo "2. joystick_node:"
echo "   $(joystick_run_preview)"
echo ""
echo "3. Activar modo manual:"
if [ "$EXEC_MODE" = "local" ]; then
    echo "   ros2 service call /nav_command_server/set_manual_mode interfaces/srv/SetManualMode '{enabled: true}'"
else
    echo "   ./tools/exec.sh 'source /ros2_ws/install/setup.bash && ros2 service call /nav_command_server/set_manual_mode interfaces/srv/SetManualMode \"{enabled: true}\"'"
fi

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}RESUMEN${NC}"
echo -e "${BLUE}======================================${NC}\n"

ERRORS=0
if [ -z "$EXEC_MODE" ]; then
    ((ERRORS++))
fi
if ! device_exists /dev/input/js0; then
    ((ERRORS++))
fi
if [ -n "$EXEC_MODE" ] && ! ros_pkg_exists joy; then
    ((ERRORS++))
fi

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ SISTEMA LISTO PARA USAR${NC}"
    echo ""
    echo "Próximo paso: ./start_joystick.sh"
else
    echo -e "${RED}✗ HAY $ERRORS PROBLEMAS QUE RESOLVER${NC}"
fi

echo ""
