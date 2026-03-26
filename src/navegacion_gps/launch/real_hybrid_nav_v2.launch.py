"""Hybrid real stack: local v2 control chain + global map/navigation."""

import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    OpaqueFunction,
    TimerAction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


def _resolve_config_file_path(package_share_dir: str, filename: str) -> str:
    package_share_path = Path(package_share_dir)
    default_path = package_share_path / "config" / filename
    try:
        workspace_root = package_share_path.parents[3]
        source_path = workspace_root / "src" / "navegacion_gps" / "config" / filename
        if source_path.parent.exists():
            return str(source_path)
    except IndexError:
        pass
    return str(default_path)


def _build_robot_state_publisher(context):
    custom_urdf = LaunchConfiguration("custom_urdf").perform(context)
    use_sim_time = LaunchConfiguration("use_sim_time").perform(context) == "True"
    robot_description = _read_file(custom_urdf)
    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            name="robot_state_publisher",
            output="screen",
            parameters=[
                {
                    "use_sim_time": use_sim_time,
                    "robot_description": robot_description,
                }
            ],
        )
    ]


def _validate_telemetry_backend(context):
    telemetry_backend = LaunchConfiguration("telemetry_backend").perform(context)
    valid_backends = {"mavros", "pixhawk_driver"}
    if telemetry_backend not in valid_backends:
        raise RuntimeError(
            "telemetry_backend must be one of "
            f"{sorted(valid_backends)}, got {telemetry_backend!r}"
        )
    return []


def generate_launch_description():
    gps_wpf_dir = get_package_share_directory("navegacion_gps")
    map_tools_dir = get_package_share_directory("map_tools")
    sensores_dir = get_package_share_directory("sensores")

    lidar_to_scan_params = _resolve_config_file_path(
        gps_wpf_dir, "pointcloud_to_laserscan.yaml"
    )
    default_rviz = _resolve_config_file_path(gps_wpf_dir, "rviz_nav2_full.rviz")
    default_keepout_mask = _resolve_config_file_path(gps_wpf_dir, "keepout_mask.yaml")
    default_localization_params = _resolve_config_file_path(
        gps_wpf_dir, "localization_v2.yaml"
    )
    default_dual_ekf_params = _resolve_config_file_path(
        gps_wpf_dir, "dual_ekf_navsat_params.yaml"
    )
    default_nav2_params = _resolve_config_file_path(gps_wpf_dir, "nav2_no_map_params.yaml")
    default_collision_monitor_params = _resolve_config_file_path(
        gps_wpf_dir, "collision_monitor.yaml"
    )
    zones_geojson_path = _resolve_config_file_path(gps_wpf_dir, "no_go_zones.geojson")
    keepout_mask_image_path = _resolve_config_file_path(gps_wpf_dir, "keepout_mask.pgm")
    keepout_mask_yaml_path = _resolve_config_file_path(gps_wpf_dir, "keepout_mask.yaml")

    use_sim_time = LaunchConfiguration("use_sim_time")
    wheelbase_m = LaunchConfiguration("wheelbase_m")
    invert_measured_steer_sign = LaunchConfiguration("invert_measured_steer_sign")
    custom_urdf = LaunchConfiguration("custom_urdf")
    lidar_config_path = LaunchConfiguration("lidar_config_path")
    fcu_url = LaunchConfiguration("fcu_url")
    use_cyclone_dds = LaunchConfiguration("use_cyclone_dds")
    nav_start_delay_s = LaunchConfiguration("nav_start_delay_s")
    use_keepout = LaunchConfiguration("use_keepout")
    launch_web_app = LaunchConfiguration("launch_web_app")
    web_app_port = LaunchConfiguration("web_app_port")
    use_rviz = LaunchConfiguration("use_rviz")
    rviz_config = LaunchConfiguration("rviz_config")
    vx_deadband_mps = LaunchConfiguration("vx_deadband_mps")
    vx_min_effective_mps = LaunchConfiguration("vx_min_effective_mps")
    invert_steer_from_cmd_vel = LaunchConfiguration("invert_steer_from_cmd_vel")
    localization_params_file = LaunchConfiguration("localization_params_file")
    dual_ekf_params_file = LaunchConfiguration("dual_ekf_params_file")
    nav2_params_file = LaunchConfiguration("nav2_params_file")
    collision_monitor_params_file = LaunchConfiguration("collision_monitor_params_file")
    keepout_mask_yaml = LaunchConfiguration("keepout_mask_yaml")
    pose_covariance_xy = LaunchConfiguration("pose_covariance_xy")
    pose_covariance_yaw = LaunchConfiguration("pose_covariance_yaw")
    twist_covariance_vx = LaunchConfiguration("twist_covariance_vx")
    twist_covariance_vy = LaunchConfiguration("twist_covariance_vy")
    twist_covariance_yaw_rate = LaunchConfiguration("twist_covariance_yaw_rate")
    telemetry_backend = LaunchConfiguration("telemetry_backend")
    launch_web = LaunchConfiguration("launch_web")
    gps_topic = LaunchConfiguration("gps_topic")
    map_frame = LaunchConfiguration("map_frame")
    zones_manager = LaunchConfiguration("zones_manager")
    nav_snapshot_server = LaunchConfiguration("nav_snapshot_server")
    datum_setter = LaunchConfiguration("datum_setter")
    ekf_global = LaunchConfiguration("ekf_global")

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="False"),
            DeclareLaunchArgument("wheelbase_m", default_value="0.94"),
            DeclareLaunchArgument(
                "invert_measured_steer_sign",
                default_value="True",
            ),
            DeclareLaunchArgument(
                "custom_urdf",
                default_value=os.path.join(gps_wpf_dir, "models", "cuatri_real.urdf"),
            ),
            DeclareLaunchArgument(
                "lidar_config_path",
                default_value=os.path.join(sensores_dir, "config", "rs16.yaml"),
            ),
            DeclareLaunchArgument("fcu_url", default_value="/dev/ttyACM0:921600"),
            DeclareLaunchArgument("use_cyclone_dds", default_value="false"),
            DeclareLaunchArgument("nav_start_delay_s", default_value="4.0"),
            DeclareLaunchArgument("use_keepout", default_value="True"),
            DeclareLaunchArgument("launch_web_app", default_value="True"),
            DeclareLaunchArgument("web_app_port", default_value="8766"),
            DeclareLaunchArgument("use_rviz", default_value="True"),
            DeclareLaunchArgument("rviz_config", default_value=default_rviz),
            DeclareLaunchArgument("vx_deadband_mps", default_value="0.01"),
            DeclareLaunchArgument("vx_min_effective_mps", default_value="0.5"),
            DeclareLaunchArgument("invert_steer_from_cmd_vel", default_value="True"),
            DeclareLaunchArgument(
                "localization_params_file",
                default_value=default_localization_params,
            ),
            DeclareLaunchArgument(
                "dual_ekf_params_file",
                default_value=default_dual_ekf_params,
            ),
            DeclareLaunchArgument(
                "nav2_params_file",
                default_value=default_nav2_params,
            ),
            DeclareLaunchArgument(
                "collision_monitor_params_file",
                default_value=default_collision_monitor_params,
            ),
            DeclareLaunchArgument("keepout_mask_yaml", default_value=default_keepout_mask),
            DeclareLaunchArgument("pose_covariance_xy", default_value="0.05"),
            DeclareLaunchArgument("pose_covariance_yaw", default_value="0.1"),
            DeclareLaunchArgument("twist_covariance_vx", default_value="0.05"),
            DeclareLaunchArgument("twist_covariance_vy", default_value="0.01"),
            DeclareLaunchArgument("twist_covariance_yaw_rate", default_value="0.1"),
            DeclareLaunchArgument("telemetry_backend", default_value="mavros"),
            DeclareLaunchArgument("launch_web", default_value="False"),
            DeclareLaunchArgument("gps_topic", default_value="/gps/fix"),
            DeclareLaunchArgument("map_frame", default_value="map"),
            DeclareLaunchArgument("zones_manager", default_value="true"),
            DeclareLaunchArgument("nav_snapshot_server", default_value="true"),
            DeclareLaunchArgument("datum_setter", default_value="true"),
            DeclareLaunchArgument("ekf_global", default_value="True"),
            OpaqueFunction(function=_validate_telemetry_backend),
            OpaqueFunction(function=_build_robot_state_publisher),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(sensores_dir, "launch", "mavros.launch.py")
                ),
                launch_arguments={
                    "launch_web": launch_web,
                    "launch_legacy_compat": "true",
                    "fcu_url": fcu_url,
                }.items(),
                condition=IfCondition(
                    PythonExpression(["'", telemetry_backend, "' == 'mavros'"])
                ),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(sensores_dir, "launch", "pixhawk.launch.py")
                ),
                launch_arguments={
                    "launch_web": launch_web,
                }.items(),
                condition=IfCondition(
                    PythonExpression(["'", telemetry_backend, "' == 'pixhawk_driver'"])
                ),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(sensores_dir, "launch", "rs16.launch.py")
                ),
                launch_arguments={
                    "config_path": lidar_config_path,
                    "use_cyclone_dds": use_cyclone_dds,
                }.items(),
            ),
            Node(
                package="pointcloud_to_laserscan",
                executable="pointcloud_to_laserscan_node",
                name="pointcloud_to_laserscan",
                output="screen",
                parameters=[
                    lidar_to_scan_params,
                    {"use_sim_time": ParameterValue(use_sim_time, value_type=bool)},
                    {"output_qos": "sensor_data"},
                ],
                remappings=[("cloud_in", "/scan_3d"), ("scan", "/scan")],
            ),
            Node(
                package="controller_server",
                executable="controller_server_node",
                name="vehicle_controller_server",
                output="screen",
                parameters=[
                    {
                        "serial_port": "/dev/serial0",
                        "serial_baud": 115200,
                        "serial_tx_hz": 50.0,
                        "max_reverse_mps": 1.30,
                        "max_abs_angular_z": 0.4,
                        "vx_deadband_mps": ParameterValue(
                            vx_deadband_mps, value_type=float
                        ),
                        "vx_min_effective_mps": ParameterValue(
                            vx_min_effective_mps, value_type=float
                        ),
                        "invert_steer_from_cmd_vel": ParameterValue(
                            invert_steer_from_cmd_vel, value_type=bool
                        ),
                    }
                ],
            ),
            Node(
                package="navegacion_gps",
                executable="nav_command_server",
                name="nav_command_server",
                output="screen",
                parameters=[
                    {
                        "fromll_service": "/fromLL",
                        "fromll_service_fallback": "/navsat_transform/fromLL",
                        "fromll_wait_timeout_s": 2.0,
                        "fromll_frame": "map",
                        "map_frame": map_frame,
                        "gps_topic": gps_topic,
                        "cmd_vel_safe_topic": "/cmd_vel_safe",
                        "cmd_vel_final_topic": "/cmd_vel_final",
                        "forward_cmd_vel_safe_without_goal": True,
                        "brake_topic": "/cmd_vel_safe",
                        "manual_cmd_topic": "/cmd_vel_safe",
                        "teleop_cmd_topic": "/cmd_vel_teleop",
                        "brake_publish_count": 5,
                        "brake_publish_interval_s": 0.1,
                        "manual_cmd_timeout_s": 0.4,
                        "manual_watchdog_hz": 10.0,
                        "nav_telemetry_hz": 5.0,
                        "telemetry_topic": "/nav_command_server/telemetry",
                        "event_topic": "/nav_command_server/events",
                        "set_goal_service": "/nav_command_server/set_goal_ll",
                        "cancel_goal_service": "/nav_command_server/cancel_goal",
                        "brake_service": "/nav_command_server/brake",
                        "set_manual_mode_service": "/nav_command_server/set_manual_mode",
                        "get_state_service": "/nav_command_server/get_state",
                    }
                ],
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(gps_wpf_dir, "launch", "hybrid_localization_v2.launch.py")
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "gps_topic": gps_topic,
                    "wheelbase_m": wheelbase_m,
                    "invert_measured_steer_sign": invert_measured_steer_sign,
                    "localization_params_file": localization_params_file,
                    "dual_ekf_params_file": dual_ekf_params_file,
                    "pose_covariance_xy": pose_covariance_xy,
                    "pose_covariance_yaw": pose_covariance_yaw,
                    "twist_covariance_vx": twist_covariance_vx,
                    "twist_covariance_vy": twist_covariance_vy,
                    "twist_covariance_yaw_rate": twist_covariance_yaw_rate,
                    "ekf_global": ekf_global,
                    "wait_for_datum": "True",
                }.items(),
            ),
            Node(
                package="navegacion_gps",
                executable="datum_setter",
                name="datum_setter",
                output="screen",
                parameters=[
                    {
                        "gps_topic": gps_topic,
                        "imu_topic": "/imu/data",
                        "rtk_status_topic": "/gps/rtk_status",
                        "set_datum_service": "/datum_setter/set_datum",
                        "get_datum_service": "/datum_setter/get_datum",
                        "datum_service": "/datum",
                        "datum_service_fallback": "/navsat_transform/datum",
                        "imu_yaw_max_age_s": 1.0,
                        "datum_wait_timeout_s": 2.0,
                        "datum_call_timeout_s": 2.5,
                        "datum_call_retries": 3,
                        "datum_retry_delay_s": 0.15,
                    }
                ],
                condition=IfCondition(
                    PythonExpression(["'", datum_setter, "'.lower() == 'true'"])
                ),
            ),
            Node(
                package="navegacion_gps",
                executable="zones_manager",
                name="zones_manager",
                output="screen",
                condition=IfCondition(
                    PythonExpression(["'", zones_manager, "'.lower() == 'true'"])
                ),
                parameters=[
                    {
                        "fromll_service": "/fromLL",
                        "fromll_service_fallback": "/navsat_transform/fromLL",
                        "fromll_wait_timeout_s": 2.0,
                        "load_map_service": "/keepout_filter_mask_server/load_map",
                        "set_geojson_service": "/zones_manager/set_geojson",
                        "get_state_service": "/zones_manager/get_state",
                        "reload_from_disk_service": "/zones_manager/reload_from_disk",
                        "map_frame": map_frame,
                        "geojson_file": zones_geojson_path,
                        "mask_image_file": keepout_mask_image_path,
                        "mask_yaml_file": keepout_mask_yaml_path,
                        "buffer_margin_m": 0.8,
                        "degrade_enabled": True,
                        "degrade_radius_m": 1.5,
                        "degrade_edge_cost": 40,
                        "degrade_min_cost": 1,
                        "degrade_use_l2": True,
                        "mask_origin_mode": "explicit",
                        "mask_origin_x": -150.0,
                        "mask_origin_y": -150.0,
                        "mask_width": 3000,
                        "mask_height": 3000,
                        "mask_resolution": 0.1,
                    }
                ],
            ),
            Node(
                package="navegacion_gps",
                executable="nav_snapshot_server",
                name="nav_snapshot_server",
                output="screen",
                condition=IfCondition(
                    PythonExpression(["'", nav_snapshot_server, "'.lower() == 'true'"])
                ),
                parameters=[
                    {
                        "get_snapshot_service": "/nav_snapshot_server/get_nav_snapshot",
                        "local_costmap_topic": "/local_costmap/costmap",
                        "global_costmap_topic": "/global_costmap/costmap",
                        "keepout_mask_topic": "/keepout_filter_mask",
                        "local_footprint_topic": "/local_costmap/published_footprint",
                        "stop_zone_topic": "/stop_zone",
                        "collision_polygons_topic": "/collision_monitor/polygons",
                        "scan_topic": "/scan",
                        "plan_topic": "/plan",
                        "base_frame": "base_footprint",
                        "snapshot_extent_m": 30.0,
                        "snapshot_size_px": 512,
                        "snapshot_global_inset_px": 160,
                        "snapshot_timeout_ms": 500,
                    }
                ],
            ),
            TimerAction(
                period=nav_start_delay_s,
                actions=[
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(gps_wpf_dir, "launch", "nav_local_v2.launch.py")
                        ),
                        launch_arguments={
                            "use_sim_time": use_sim_time,
                            "use_keepout": use_keepout,
                            "nav2_params_file": nav2_params_file,
                            "collision_monitor_params_file": collision_monitor_params_file,
                            "keepout_mask_yaml": keepout_mask_yaml,
                            "keepout_mask_frame": map_frame,
                        }.items(),
                    )
                ],
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(map_tools_dir, "launch", "no_go_editor.launch.py")
                ),
                launch_arguments={
                    "ws_host": "0.0.0.0",
                    "ws_port": web_app_port,
                    "gps_topic": gps_topic,
                    "map_frame": map_frame,
                    "launch_zones_manager": "false",
                    "launch_nav_command_server": "false",
                    "launch_nav_snapshot_server": "false",
                    "teleop_cmd_topic": "/cmd_vel_teleop",
                    "zones_set_geojson_service": "/zones_manager/set_geojson",
                    "zones_get_state_service": "/zones_manager/get_state",
                    "zones_reload_service": "/zones_manager/reload_from_disk",
                }.items(),
                condition=IfCondition(launch_web_app),
            ),
            Node(
                package="rviz2",
                executable="rviz2",
                name="rviz2",
                output="screen",
                arguments=["-d", rviz_config],
                parameters=[{"use_sim_time": ParameterValue(use_sim_time, value_type=bool)}],
                condition=IfCondition(use_rviz),
            ),
        ]
    )
