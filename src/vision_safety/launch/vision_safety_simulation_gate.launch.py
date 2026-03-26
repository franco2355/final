"""
Fase 3 – Simulación + visión activa con stop y reversa.

Pipeline de velocidad:
  Nav2 → /cmd_vel_nav
       → collision_monitor (propio, cmd_vel_out=/cmd_vel_nav_safe)
       → cmd_vel_gate  (stop + reversa cuando vision detecta obstáculo)
       → /cmd_vel_safe → bridge → Gazebo

La simulación base se lanza con use_collision_monitor:=false para que
el collision_monitor original NO publique en /cmd_vel_safe. Este wrapper
levanta su propio CM con salida en /cmd_vel_nav_safe.

Archivos base NO modificados:
  - simulacion.launch.py         ← intocable
  - bridge_config.yaml           ← intocable (/cmd_vel_safe→/cmd_vel_steer sigue igual)
  - rviz_nav2_full.rviz          ← intocable

Uso:
  ros2 launch vision_safety vision_safety_simulation_gate.launch.py
  ros2 launch vision_safety vision_safety_simulation_gate.launch.py use_mock_detections:=true
  ros2 launch vision_safety vision_safety_simulation_gate.launch.py stop_distance_m:=2.0 reverse_duration_s:=2.0
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description() -> LaunchDescription:
    navegacion_dir = get_package_share_directory("navegacion_gps")
    vision_safety_dir = get_package_share_directory("vision_safety")

    collision_monitor_params = os.path.join(
        navegacion_dir, "config", "collision_monitor.yaml"
    )
    vision_rviz = os.path.join(
        vision_safety_dir, "config", "vision_safety_passive.rviz"
    )

    # ── argumentos ───────────────────────────────────────────────────────────
    use_rviz = LaunchConfiguration("use_rviz")
    rviz_config = LaunchConfiguration("rviz_config")
    use_mock_detections = LaunchConfiguration("use_mock_detections")
    scan_topic = LaunchConfiguration("scan_topic")
    stop_distance_m = LaunchConfiguration("stop_distance_m")
    reverse_speed_mps = LaunchConfiguration("reverse_speed_mps")
    reverse_duration_s = LaunchConfiguration("reverse_duration_s")
    stop_confirm_frames = LaunchConfiguration("stop_confirm_frames")
    clear_frames_needed = LaunchConfiguration("clear_frames_needed")
    vision_timeout_s = LaunchConfiguration("vision_timeout_s")
    wait_clear_timeout_s = LaunchConfiguration("wait_clear_timeout_s")
    post_cycle_cooldown_s = LaunchConfiguration("post_cycle_cooldown_s")
    mock_class_id = LaunchConfiguration("mock_class_id")
    mock_bbox_center_x_px = LaunchConfiguration("mock_bbox_center_x_px")
    mock_bbox_width_px = LaunchConfiguration("mock_bbox_width_px")

    # ── simulación base (use_collision_monitor:=false) ───────────────────────
    # Se deshabilita el CM original para que NO publique en /cmd_vel_safe.
    # El gate toma ese rol. Todo lo demás de la simulación es idéntico.
    simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(navegacion_dir, "launch", "simulacion.launch.py")
        ),
        launch_arguments={
            "use_rviz": use_rviz,
            "rviz_config": rviz_config,
            "use_collision_monitor": "false",
        }.items(),
    )

    # ── collision monitor propio ─────────────────────────────────────────────
    # Mismos parámetros de geometría y fuentes que el base (mismo yaml),
    # pero cmd_vel_out apunta a /cmd_vel_nav_safe en vez de /cmd_vel_safe.
    collision_monitor = Node(
        package="nav2_collision_monitor",
        executable="collision_monitor",
        name="collision_monitor",
        output="screen",
        parameters=[
            collision_monitor_params,
            {
                "cmd_vel_in_topic": "/cmd_vel_nav",
                "cmd_vel_out_topic": "/cmd_vel_nav_safe",
                "use_sim_time": True,
            },
        ],
    )
    collision_monitor_lifecycle = Node(
        package="nav2_lifecycle_manager",
        executable="lifecycle_manager",
        name="collision_monitor_lifecycle_manager",
        output="screen",
        parameters=[
            {
                "use_sim_time": True,
                "autostart": True,
                "node_names": ["collision_monitor"],
            }
        ],
    )

    # ── visión + fusión ──────────────────────────────────────────────────────
    vision_passive = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(vision_safety_dir, "launch", "vision_safety_passive.launch.py")
        ),
        launch_arguments={
            "use_mock_detections": use_mock_detections,
            "scan_topic": scan_topic,
            "stop_distance_m": stop_distance_m,
            "mock_class_id": mock_class_id,
            "mock_bbox_center_x_px": mock_bbox_center_x_px,
            "mock_bbox_width_px": mock_bbox_width_px,
            "use_sim_time": "true",
            "rviz_frame_id": "map",
        }.items(),
    )

    # ── gate de velocidad ────────────────────────────────────────────────────
    gate_node = Node(
        package="vision_safety",
        executable="cmd_vel_gate_node",
        name="cmd_vel_gate",
        output="screen",
        parameters=[
            {
                "input_cmd_vel_topic": "/cmd_vel_nav_safe",
                "output_cmd_vel_topic": "/cmd_vel_safe",
                "vision_stop_topic": "/vision/fused_stop_active",
                "gate_state_topic": "/vision_safety/gate/state",
                "publish_hz": 20.0,
                "vision_timeout_s": vision_timeout_s,
                "stop_confirm_frames": stop_confirm_frames,
                "reverse_speed_mps": reverse_speed_mps,
                "reverse_duration_s": reverse_duration_s,
                "clear_frames_needed": clear_frames_needed,
                "wait_clear_timeout_s": wait_clear_timeout_s,
                "post_cycle_cooldown_s": post_cycle_cooldown_s,
                "use_sim_time": True,
            }
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_rviz", default_value="true"),
            DeclareLaunchArgument("rviz_config", default_value=vision_rviz),
            DeclareLaunchArgument(
                "use_mock_detections",
                default_value="false",
                description="true → mock_detections_node activo (objeto frontal sintético)",
            ),
            DeclareLaunchArgument("scan_topic", default_value="/scan"),
            DeclareLaunchArgument(
                "stop_distance_m",
                default_value="2.5",
                description="Distancia máxima (m) para activar el stop",
            ),
            DeclareLaunchArgument(
                "reverse_speed_mps",
                default_value="0.25",
                description="Velocidad de retroceso (m/s)",
            ),
            DeclareLaunchArgument(
                "reverse_duration_s",
                default_value="1.5",
                description="Duración del retroceso (segundos)",
            ),
            DeclareLaunchArgument(
                "stop_confirm_frames",
                default_value="3",
                description="Frames consecutivos con stop antes de retroceder",
            ),
            DeclareLaunchArgument(
                "clear_frames_needed",
                default_value="5",
                description="Frames consecutivos sin obstáculo para reanudar",
            ),
            DeclareLaunchArgument(
                "wait_clear_timeout_s",
                default_value="3.0",
                description="Segundos máximos en wait_clear antes de retomar ruta (failsafe)",
            ),
            DeclareLaunchArgument(
                "post_cycle_cooldown_s",
                default_value="5.0",
                description="Segundos de cooldown post-ciclo: el gate no frena aunque haya detección",
            ),
            DeclareLaunchArgument(
                "vision_timeout_s",
                default_value="0.5",
                description="Segundos sin señal de visión para ignorarla (fail-safe open)",
            ),
            DeclareLaunchArgument("mock_class_id", default_value="person"),
            DeclareLaunchArgument("mock_bbox_center_x_px", default_value="640.0"),
            DeclareLaunchArgument("mock_bbox_width_px", default_value="240.0"),
            simulation,
            collision_monitor,
            collision_monitor_lifecycle,
            vision_passive,
            gate_node,
        ]
    )
