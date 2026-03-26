#!/bin/bash

# Script para iniciar el sistema de control joystick Xbox.
# Soporta ROS 2 local o el contenedor ros2 del workspace.

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

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

WORKSPACE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"
CONTAINER_EXEC="$WORKSPACE_DIR/tools/exec.sh"
EXEC_MODE=""
USE_TUI=true
JOY_ONLY=false
HELP=false

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

ros_pkg_prefix() {
    local pkg="$1"

    if [ "$EXEC_MODE" = "local" ]; then
        ros2 pkg prefix "$pkg"
    else
        container_exec "source /ros2_ws/install/setup.bash && ros2 pkg prefix $pkg"
    fi
}

run_joy_node() {
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 run joy joy_node
    else
        container_exec "source /ros2_ws/install/setup.bash && ros2 run joy joy_node"
    fi
}

run_joystick_node() {
    local tui_args=""
    if [ "$USE_TUI" != true ]; then
        tui_args=" --ros-args -p use_tui:=false"
    fi

    if [ "$EXEC_MODE" = "local" ]; then
        ros2 run navegacion_gps joystick_node$tui_args
    else
        container_exec "source /ros2_ws/install/setup.bash && export PYTHONPATH=/ros2_ws/src/navegacion_gps:\$PYTHONPATH && python3 -m navegacion_gps.joystick_node$tui_args"
    fi
}

joy_command_preview() {
    if [ "$EXEC_MODE" = "local" ]; then
        echo "ros2 run joy joy_node"
    else
        echo "./tools/exec.sh 'source /ros2_ws/install/setup.bash && ros2 run joy joy_node'"
    fi
}

joystick_command_preview() {
    local tui_args=""
    if [ "$USE_TUI" != true ]; then
        tui_args=" --ros-args -p use_tui:=false"
    fi

    if [ "$EXEC_MODE" = "local" ]; then
        echo "ros2 run navegacion_gps joystick_node$tui_args"
    else
        echo "./tools/exec.sh 'source /ros2_ws/install/setup.bash && export PYTHONPATH=/ros2_ws/src/navegacion_gps:\$PYTHONPATH && python3 -m navegacion_gps.joystick_node$tui_args'"
    fi
}

echo_joy_topic() {
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 topic echo /joy --max-count=3
    else
        container_exec "source /ros2_ws/install/setup.bash && ros2 topic echo /joy --max-count=3"
    fi
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-tui)
            USE_TUI=false
            shift
            ;;
        --joy-only)
            JOY_ONLY=true
            shift
            ;;
        --help|-h)
            HELP=true
            shift
            ;;
        *)
            print_error "Opción desconocida: $1"
            HELP=true
            shift
            ;;
    esac
done

if [ "$HELP" = true ]; then
    cat << 'EOF'
Iniciar sistema de control Joystick Xbox para el cuatri

Uso:
    ./start_joystick.sh [opciones]

Opciones:
    --no-tui      Iniciar sin pantalla TUI (para launches multi-nodo)
    --joy-only    Solo iniciar joy_node (sin joystick_node)
    --help        Mostrar esta ayuda

Notas:
    - Si ROS 2 no está instalado en el host, el script usa el contenedor ros2.
    - Terminal 1: ./start_joystick.sh --joy-only
    - Terminal 2: ./start_joystick.sh

EOF
    exit 0
fi

print_header "VERIFICACIONES PREVIAS"

print_info "Detectando entorno ROS 2..."
if ! detect_exec_mode; then
    print_error "No se encontró ROS 2 local ni tools/exec.sh para usar el contenedor"
    exit 1
fi
print_success "Modo de ejecución: $EXEC_MODE"

print_info "Verificando joystick conectado..."
if device_exists /dev/input/js0; then
    print_success "Joystick detectado en /dev/input/js0"
else
    print_error "Joystick NO detectado en /dev/input/js0"
    print_info "Conectar Xbox por USB o Bluetooth y ejecutar de nuevo"
    exit 1
fi

print_info "Verificando paquete joy instalado..."
if ! ros_pkg_prefix joy >/dev/null 2>&1; then
    print_error "Paquete 'joy' no instalado en el entorno activo"
    echo "Instalar con:"
    echo "  sudo apt install ros-$ROS_DISTRO-joy"
    echo "o dentro del contenedor ros2"
    exit 1
fi
print_success "Paquete joy disponible"

print_info "Verificando workspace..."
if [ ! -f "$WORKSPACE_DIR/install/setup.bash" ]; then
    print_error "No se encontró install/setup.bash en $WORKSPACE_DIR"
    echo "Compilar primero:"
    echo "  cd $WORKSPACE_DIR"
    echo "  ./tools/compile-ros.sh interfaces navegacion_gps"
    exit 1
fi
print_success "Workspace encontrado en: $WORKSPACE_DIR"

if [ "$EXEC_MODE" = "local" ]; then
    print_info "Sourciendo setup.bash..."
    # shellcheck disable=SC1090
    source "$WORKSPACE_DIR/install/setup.bash"
    print_success "Setup sourced"
fi

print_header "SISTEMA DE CONTROL JOYSTICK XBOX"

echo "Configuración:"
echo "  Modo:              $EXEC_MODE"
echo "  ROS Distro:        $ROS_DISTRO"
echo "  Workspace:         $WORKSPACE_DIR"
echo "  Joystick:          Detectado (/dev/input/js0)"
echo "  TUI:               $([ "$USE_TUI" = true ] && echo "HABILITADO" || echo "DESHABILITADO")"
echo ""

if [ "$JOY_ONLY" = true ]; then
    print_header "INICIANDO JOY DRIVER (TERMINAL 1)"
    echo "Ejecutar en TERMINAL 2:"
    echo "  $(joystick_command_preview)"
    echo ""
    echo "Presionar Ctrl+C para detener"
    echo ""

    run_joy_node
    exit $?
fi

echo "Opciones:"
echo "  1) Iniciar joy_node (Terminal 1)"
echo "  2) Iniciar joystick_node (Terminal 2)"
echo "  3) Iniciar ambos en tmux (si disponible)"
echo "  4) Verificar instalación"
echo "  5) Salir"
echo ""
read -r -p "Seleccionar opción [1-5]: " option

case $option in
    1)
        print_header "JOY DRIVER"
        echo "Ejecutar en otra terminal:"
        echo "  $(joystick_command_preview)"
        echo ""
        echo "Presionar Ctrl+C para detener"
        echo ""
        run_joy_node
        ;;
    2)
        print_header "JOYSTICK CONTROL NODE"
        echo "Asegurar que joy_node está corriendo en otra terminal"
        echo "Comando sugerido:"
        echo "  $(joy_command_preview)"
        echo ""
        echo "Presionar Ctrl+C para detener"
        echo ""
        run_joystick_node
        ;;
    3)
        if ! command -v tmux >/dev/null 2>&1; then
            print_error "tmux no instalado"
            echo "Instalar con: sudo apt install tmux"
            exit 1
        fi

        print_header "INICIANDO EN TMUX"
        SESSION_NAME="joystick_$(date +%s)"
        tmux new-session -d -s "$SESSION_NAME"
        tmux send-keys -t "$SESSION_NAME:0" "$(joy_command_preview)" Enter
        tmux rename-window -t "$SESSION_NAME:0" "joy_driver"
        tmux new-window -t "$SESSION_NAME"
        tmux send-keys -t "$SESSION_NAME:1" "$(joystick_command_preview)" Enter
        tmux rename-window -t "$SESSION_NAME:1" "joystick_node"
        tmux select-window -t "$SESSION_NAME:0"

        print_success "Sesión tmux creada: $SESSION_NAME"
        echo "  tmux attach -t $SESSION_NAME"
        echo "  tmux kill-session -t $SESSION_NAME"
        echo ""
        tmux attach -t "$SESSION_NAME"
        ;;
    4)
        print_header "VERIFICACIÓN DETALLADA"
        echo "1. Joystick físico:"
        if [ "$EXEC_MODE" = "local" ]; then
            ls -la /dev/input/js0
        else
            container_exec "ls -la /dev/input/js0"
        fi
        echo ""
        echo "2. Paquete joy:"
        ros_pkg_prefix joy
        echo ""
        echo "3. Comando joy_node:"
        echo "  $(joy_command_preview)"
        echo ""
        echo "4. Comando joystick_node:"
        echo "  $(joystick_command_preview)"
        echo ""
        echo "5. Verificar /joy topic (presionar botones del joystick):"
        echo "  $(joy_command_preview)"
        echo "  # En otra terminal:"
        if [ "$EXEC_MODE" = "local" ]; then
            echo "  ros2 topic echo /joy --max-count=3"
        else
            echo "  ./tools/exec.sh 'source /ros2_ws/install/setup.bash && ros2 topic echo /joy --max-count=3'"
        fi
        echo ""
        read -r -p "Presionar Enter para continuar..."
        echo_joy_topic
        ;;
    5)
        print_info "Saliendo..."
        exit 0
        ;;
    *)
        print_error "Opción inválida"
        exit 1
        ;;
esac
