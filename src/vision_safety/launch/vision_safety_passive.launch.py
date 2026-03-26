"""
Fase 1 – Visión pasiva.

Lanza SOLO los nodos de fusión y detección mock (opcional).
NO lanza cmd_vel_gate_node: el stop nunca bloquea el movimiento.
Puede usarse solo (con la simulación corriendo en otra terminal) o
incluirse desde vision_safety_simulation_passive.launch.py.

Argumentos principales:
  use_mock_detections  [false]   Publicar detecciones sintéticas para probar la fusión.
  scan_topic           [/scan]   LaserScan que ya publica la simulación base.
  detections_topic     [/vision/detections]
  rviz_frame_id        [map]     Frame para los markers de RViz.
  stop_distance_m      [2.5]     Umbral de distancia para el flag /vision/fused_stop_active.
                                  En modo pasivo ese flag se publica pero NADIE lo lee.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description() -> LaunchDescription:
    # ── parámetros configurables ─────────────────────────────────────────────
    use_mock_detections = LaunchConfiguration("use_mock_detections")
    scan_topic = LaunchConfiguration("scan_topic")
    detections_topic = LaunchConfiguration("detections_topic")
    fused_objects_topic = LaunchConfiguration("fused_objects_topic")
    fusion_status_topic = LaunchConfiguration("fusion_status_topic")
    confirmed_stop_topic = LaunchConfiguration("confirmed_stop_topic")
    fused_markers_topic = LaunchConfiguration("fused_markers_topic")
    rviz_frame_id = LaunchConfiguration("rviz_frame_id")
    camera_hfov_deg = LaunchConfiguration("camera_hfov_deg")
    image_width_px = LaunchConfiguration("image_width_px")
    stop_distance_m = LaunchConfiguration("stop_distance_m")
    mock_class_id = LaunchConfiguration("mock_class_id")
    mock_bbox_center_x_px = LaunchConfiguration("mock_bbox_center_x_px")
    mock_bbox_width_px = LaunchConfiguration("mock_bbox_width_px")
    use_sim_time = LaunchConfiguration("use_sim_time")

    # ── nodo de fusión ───────────────────────────────────────────────────────
    fusion_node = Node(
        package="vision_safety",
        executable="vision_lidar_fusion_node",
        name="vision_lidar_fusion",
        output="screen",
        parameters=[
            {
                "detections_topic": detections_topic,
                "scan_topic": scan_topic,
                "fused_objects_topic": fused_objects_topic,
                "fusion_status_topic": fusion_status_topic,
                # /vision/fused_stop_active se publica pero en modo pasivo
                # nadie lo consume — no afecta el movimiento del robot.
                "confirmed_stop_topic": confirmed_stop_topic,
                "fused_markers_topic": fused_markers_topic,
                "output_frame_id": rviz_frame_id,
                "camera_hfov_deg": camera_hfov_deg,
                "image_width_px": image_width_px,
                "stop_distance_m": stop_distance_m,
                "use_sim_time": use_sim_time,
            }
        ],
    )

    # ── detecciones mock (solo si use_mock_detections:=true) ────────────────
    mock_detections_node = Node(
        package="vision_safety",
        executable="mock_detections_node",
        name="mock_detections",
        output="screen",
        condition=IfCondition(use_mock_detections),
        parameters=[
            {
                "output_topic": detections_topic,
                "class_id": mock_class_id,
                "bbox_center_x_px": mock_bbox_center_x_px,
                "bbox_width_px": mock_bbox_width_px,
                "use_sim_time": use_sim_time,
            }
        ],
    )

    return LaunchDescription(
        [
            # ── defaults ─────────────────────────────────────────────────────
            DeclareLaunchArgument(
                "use_mock_detections",
                default_value="false",
                description="Publicar detecciones sintéticas para probar fusión",
            ),
            DeclareLaunchArgument(
                "scan_topic",
                default_value="/scan",
                description="LaserScan publicado por la simulación base",
            ),
            DeclareLaunchArgument(
                "detections_topic",
                default_value="/vision/detections",
                description="Detection2DArray de entrada (real o mock)",
            ),
            DeclareLaunchArgument(
                "fused_objects_topic",
                default_value="/vision/fused_objects",
            ),
            DeclareLaunchArgument(
                "fusion_status_topic",
                default_value="/vision/fusion/status",
            ),
            DeclareLaunchArgument(
                "confirmed_stop_topic",
                default_value="/vision/fused_stop_active",
                description=(
                    "Bool publicado por la fusión. En modo pasivo nadie lo consume."
                ),
            ),
            DeclareLaunchArgument(
                "fused_markers_topic",
                default_value="/vision/fused_markers",
            ),
            DeclareLaunchArgument(
                "rviz_frame_id",
                default_value="map",
            ),
            DeclareLaunchArgument(
                "camera_hfov_deg",
                default_value="90.0",
            ),
            DeclareLaunchArgument(
                "image_width_px",
                default_value="1280.0",
            ),
            DeclareLaunchArgument(
                "stop_distance_m",
                default_value="2.5",
                description="Umbral de distancia para el flag de stop (solo observacional)",
            ),
            DeclareLaunchArgument(
                "mock_class_id",
                default_value="person",
            ),
            DeclareLaunchArgument(
                "mock_bbox_center_x_px",
                default_value="640.0",
            ),
            DeclareLaunchArgument(
                "mock_bbox_width_px",
                default_value="240.0",
            ),
            DeclareLaunchArgument(
                "use_sim_time",
                default_value="true",
            ),
            # ── nodos ────────────────────────────────────────────────────────
            fusion_node,
            mock_detections_node,
        ]
    )
