"""
Fase 2 – Wrapper pasiva de simulación + visión.

Este launch:
  1. Lanza la simulación canónica (simulacion.launch.py) SIN modificar ningún
     argumento que altere el comportamiento de navegación o control.
     Solo sobreescribe `rviz_config` para usar el RViz de vision_safety —
     ese argumento ya existe en simulacion.launch.py y es de solo-visualización.

  2. Lanza vision_safety_passive.launch.py (solo fusión, sin gate).

La simulación original puede correrse en cualquier momento sin este wrapper
y funciona exactamente igual. Este archivo no toca:
  - /cmd_vel_safe
  - bridge_config.yaml
  - ningún nodo de control

Uso:
  ros2 launch vision_safety vision_safety_simulation_passive.launch.py
  ros2 launch vision_safety vision_safety_simulation_passive.launch.py use_mock_detections:=true
  ros2 launch vision_safety vision_safety_simulation_passive.launch.py use_rviz:=false
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description() -> LaunchDescription:
    navegacion_dir = get_package_share_directory("navegacion_gps")
    vision_safety_dir = get_package_share_directory("vision_safety")

    # RViz config propio: copia de rviz_nav2_full con display de vision añadido.
    # NO es el mismo archivo que usa la simulación original.
    default_vision_rviz = os.path.join(
        vision_safety_dir, "config", "vision_safety_passive.rviz"
    )

    use_rviz = LaunchConfiguration("use_rviz")
    use_mock_detections = LaunchConfiguration("use_mock_detections")
    scan_topic = LaunchConfiguration("scan_topic")
    rviz_config = LaunchConfiguration("rviz_config")
    stop_distance_m = LaunchConfiguration("stop_distance_m")
    mock_class_id = LaunchConfiguration("mock_class_id")
    mock_bbox_center_x_px = LaunchConfiguration("mock_bbox_center_x_px")
    mock_bbox_width_px = LaunchConfiguration("mock_bbox_width_px")

    # ── Simulación base (INTOCABLE) ──────────────────────────────────────────
    # Solo se pasa rviz_config (argumento ya declarado en simulacion.launch.py).
    # Todos los demás argumentos quedan con sus defaults originales.
    # No se pasa bridge_config_path ni ningún argumento de control.
    simulation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(navegacion_dir, "launch", "simulacion.launch.py")
        ),
        launch_arguments={
            "use_rviz": use_rviz,
            "rviz_config": rviz_config,
        }.items(),
    )

    # ── Visión pasiva (sin gate) ─────────────────────────────────────────────
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

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "use_rviz",
                default_value="true",
            ),
            DeclareLaunchArgument(
                "rviz_config",
                default_value=default_vision_rviz,
                description=(
                    "RViz config a usar. Por defecto: vision_safety_passive.rviz "
                    "(incluye todos los displays de nav2 + markers de fusión). "
                    "Para usar el original: rviz_config:=<path>/rviz_nav2_full.rviz"
                ),
            ),
            DeclareLaunchArgument(
                "use_mock_detections",
                default_value="false",
                description=(
                    "true → activa mock_detections_node (objeto frontal sintético). "
                    "false → espera detecciones reales en /vision/detections."
                ),
            ),
            DeclareLaunchArgument(
                "scan_topic",
                default_value="/scan",
                description="LaserScan de entrada a la fusión (ya publicado por la base).",
            ),
            DeclareLaunchArgument(
                "stop_distance_m",
                default_value="2.5",
                description=(
                    "Umbral de distancia para /vision/fused_stop_active. "
                    "En modo pasivo es solo observacional (nadie lo consume)."
                ),
            ),
            DeclareLaunchArgument("mock_class_id", default_value="person"),
            DeclareLaunchArgument("mock_bbox_center_x_px", default_value="640.0"),
            DeclareLaunchArgument("mock_bbox_width_px", default_value="240.0"),
            simulation,
            vision_passive,
        ]
    )
