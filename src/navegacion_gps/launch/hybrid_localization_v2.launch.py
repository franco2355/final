from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from nav2_common.launch import RewrittenYaml


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


def generate_launch_description():
    gps_wpf_dir = get_package_share_directory("navegacion_gps")
    default_local_params = _resolve_config_file_path(gps_wpf_dir, "localization_v2.yaml")
    default_dual_ekf_params = _resolve_config_file_path(
        gps_wpf_dir, "dual_ekf_navsat_params.yaml"
    )

    use_sim_time = LaunchConfiguration("use_sim_time")
    drive_telemetry_topic = LaunchConfiguration("drive_telemetry_topic")
    gps_topic = LaunchConfiguration("gps_topic")
    imu_topic = LaunchConfiguration("imu_topic")
    wheelbase_m = LaunchConfiguration("wheelbase_m")
    invert_measured_steer_sign = LaunchConfiguration("invert_measured_steer_sign")
    localization_params_file = LaunchConfiguration("localization_params_file")
    dual_ekf_params_file = LaunchConfiguration("dual_ekf_params_file")
    pose_covariance_xy = LaunchConfiguration("pose_covariance_xy")
    pose_covariance_yaw = LaunchConfiguration("pose_covariance_yaw")
    twist_covariance_vx = LaunchConfiguration("twist_covariance_vx")
    twist_covariance_vy = LaunchConfiguration("twist_covariance_vy")
    twist_covariance_yaw_rate = LaunchConfiguration("twist_covariance_yaw_rate")
    ekf_global = LaunchConfiguration("ekf_global")
    wait_for_datum = LaunchConfiguration("wait_for_datum")

    configured_dual_ekf_params = RewrittenYaml(
        source_file=dual_ekf_params_file,
        root_key="",
        param_rewrites={
            "gps_topic": gps_topic,
            "wait_for_datum": wait_for_datum,
        },
        convert_types=True,
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("use_sim_time", default_value="False"),
            DeclareLaunchArgument(
                "drive_telemetry_topic",
                default_value="/controller/drive_telemetry",
            ),
            DeclareLaunchArgument("gps_topic", default_value="/gps/fix"),
            DeclareLaunchArgument("imu_topic", default_value="/imu/data"),
            DeclareLaunchArgument("wheelbase_m", default_value="0.94"),
            DeclareLaunchArgument(
                "invert_measured_steer_sign",
                default_value="False",
            ),
            DeclareLaunchArgument(
                "localization_params_file",
                default_value=default_local_params,
            ),
            DeclareLaunchArgument(
                "dual_ekf_params_file",
                default_value=default_dual_ekf_params,
            ),
            DeclareLaunchArgument("pose_covariance_xy", default_value="0.05"),
            DeclareLaunchArgument("pose_covariance_yaw", default_value="0.1"),
            DeclareLaunchArgument("twist_covariance_vx", default_value="0.05"),
            DeclareLaunchArgument("twist_covariance_vy", default_value="0.01"),
            DeclareLaunchArgument("twist_covariance_yaw_rate", default_value="0.1"),
            DeclareLaunchArgument("ekf_global", default_value="True"),
            DeclareLaunchArgument("wait_for_datum", default_value="True"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    str(Path(gps_wpf_dir) / "launch" / "localization_v2.launch.py")
                ),
                launch_arguments={
                    "use_sim_time": use_sim_time,
                    "drive_telemetry_topic": drive_telemetry_topic,
                    "imu_topic": imu_topic,
                    "wheelbase_m": wheelbase_m,
                    "invert_measured_steer_sign": invert_measured_steer_sign,
                    "localization_params_file": localization_params_file,
                    "pose_covariance_xy": pose_covariance_xy,
                    "pose_covariance_yaw": pose_covariance_yaw,
                    "twist_covariance_vx": twist_covariance_vx,
                    "twist_covariance_vy": twist_covariance_vy,
                    "twist_covariance_yaw_rate": twist_covariance_yaw_rate,
                }.items(),
            ),
            Node(
                package="robot_localization",
                executable="ukf_node",
                name="ekf_filter_node_map",
                output="screen",
                condition=IfCondition(ekf_global),
                parameters=[
                    configured_dual_ekf_params,
                    {"use_sim_time": ParameterValue(use_sim_time, value_type=bool)},
                ],
                remappings=[
                    ("imu/data", imu_topic),
                    ("odometry/filtered", "/odometry/global"),
                ],
            ),
            Node(
                package="robot_localization",
                executable="navsat_transform_node",
                name="navsat_transform",
                output="screen",
                condition=IfCondition(ekf_global),
                parameters=[
                    configured_dual_ekf_params,
                    {"use_sim_time": ParameterValue(use_sim_time, value_type=bool)},
                ],
                remappings=[
                    ("imu/data", imu_topic),
                    ("odometry/filtered", "/odometry/local"),
                    ("odometry/gps", "/odometry/gps"),
                ],
            ),
        ]
    )
