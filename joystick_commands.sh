#!/bin/bash

# Comandos rápidos para el sistema Joystick Xbox.
# Si ROS 2 no está disponible en el host, usa el contenedor ros2.

JOYSTICK_WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS_DISTRO="${ROS_DISTRO:-humble}"
CONTAINER_EXEC="$JOYSTICK_WORKSPACE/tools/exec.sh"
EXEC_MODE=""

if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    MODE="menu"
else
    MODE="functions"
fi

joystick_detect_mode() {
    if [ -n "$EXEC_MODE" ]; then
        return 0
    fi

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

    echo "No se encontró ROS 2 local ni acceso al contenedor ros2" >&2
    return 1
}

joystick_container_exec() {
    "$CONTAINER_EXEC" "$1"
}

joystick_source_env() {
    joystick_detect_mode || return 1

    if [ "$EXEC_MODE" = "local" ] && [ -f "$JOYSTICK_WORKSPACE/install/setup.bash" ]; then
        # shellcheck disable=SC1090
        source "$JOYSTICK_WORKSPACE/install/setup.bash"
    fi
}

joystick_joy_only() {
    joystick_source_env || return 1
    echo "Iniciando joy_node..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 run joy joy_node
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && ros2 run joy joy_node"
    fi
}

joystick_start() {
    joystick_source_env || return 1
    echo "Iniciando joystick_node (con TUI)..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 run navegacion_gps joystick_node
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && export PYTHONPATH=/ros2_ws/src/navegacion_gps:\$PYTHONPATH && python3 -m navegacion_gps.joystick_node"
    fi
}

joystick_start_notui() {
    joystick_source_env || return 1
    echo "Iniciando joystick_node (sin TUI)..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 run navegacion_gps joystick_node --ros-args -p use_tui:=false
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && export PYTHONPATH=/ros2_ws/src/navegacion_gps:\$PYTHONPATH && python3 -m navegacion_gps.joystick_node --ros-args -p use_tui:=false"
    fi
}

joystick_spy_joy() {
    joystick_source_env || return 1
    echo "Espiar /joy topic..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 topic echo /joy
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && ros2 topic echo /joy"
    fi
}

joystick_spy_cmd() {
    joystick_source_env || return 1
    echo "Espiar /cmd_vel_teleop topic..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 topic echo /cmd_vel_teleop
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && ros2 topic echo /cmd_vel_teleop"
    fi
}

joystick_manual_on() {
    joystick_source_env || return 1
    echo "Activar manual mode..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 service call /nav_command_server/set_manual_mode \
            interfaces/srv/SetManualMode '{enabled: true}'
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && ros2 service call /nav_command_server/set_manual_mode interfaces/srv/SetManualMode '{enabled: true}'"
    fi
}

joystick_manual_off() {
    joystick_source_env || return 1
    echo "Desactivar manual mode..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 service call /nav_command_server/set_manual_mode \
            interfaces/srv/SetManualMode '{enabled: false}'
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && ros2 service call /nav_command_server/set_manual_mode interfaces/srv/SetManualMode '{enabled: false}'"
    fi
}

joystick_state() {
    joystick_source_env || return 1
    echo "Estado del servidor de navegación..."
    if [ "$EXEC_MODE" = "local" ]; then
        ros2 service call /nav_command_server/get_state interfaces/srv/GetNavState '{}'
    else
        joystick_container_exec "source /ros2_ws/install/setup.bash && ros2 service call /nav_command_server/get_state interfaces/srv/GetNavState '{}'"
    fi
}

joystick_build() {
    joystick_detect_mode || return 1
    echo "Compilando navegacion_gps..."
    cd "$JOYSTICK_WORKSPACE"
    if [ "$EXEC_MODE" = "local" ]; then
        colcon build --packages-select interfaces navegacion_gps
    else
        ./tools/compile-ros.sh interfaces navegacion_gps
    fi
}

joystick_check() {
    echo "Ejecutando check_joystick.sh..."
    bash "$JOYSTICK_WORKSPACE/check_joystick.sh"
}

show_menu() {
    clear
    echo "╔════════════════════════════════════════════╗"
    echo "║   COMANDOS RÁPIDOS - JOYSTICK XBOX        ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    echo "INICIAR:"
    echo "  1) Iniciar joy_node solo"
    echo "  2) Iniciar joystick_node (con TUI)"
    echo "  3) Iniciar joystick_node (sin TUI)"
    echo ""
    echo "ESPIAR TOPICS:"
    echo "  4) Espiar /joy"
    echo "  5) Espiar /cmd_vel_teleop"
    echo ""
    echo "CONTROL MANUAL MODE:"
    echo "  6) Activar manual mode"
    echo "  7) Desactivar manual mode"
    echo "  8) Ver estado del servidor"
    echo ""
    echo "HERRAMIENTAS:"
    echo "  9) Compilar paquete"
    echo "  10) Verificación del sistema"
    echo ""
    echo "  0) Salir"
    echo ""
    read -r -p "Seleccionar [0-10]: " choice
}

run_option() {
    case $1 in
        1) joystick_joy_only ;;
        2) joystick_start ;;
        3) joystick_start_notui ;;
        4) joystick_spy_joy ;;
        5) joystick_spy_cmd ;;
        6) joystick_manual_on ;;
        7) joystick_manual_off ;;
        8) joystick_state ;;
        9) joystick_build ;;
        10) joystick_check ;;
        0) echo "Saliendo..."; exit 0 ;;
        *) echo "Opción inválida" ;;
    esac
}

if [ "$MODE" = "functions" ]; then
    true
else
    while true; do
        show_menu
        run_option "$choice"
        echo ""
        read -r -p "Presionar Enter para continuar..."
    done
fi
