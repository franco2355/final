from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_localization_v2_launch_is_local_only_single_ekf_stack() -> None:
    launch_path = PACKAGE_ROOT / "launch" / "localization_v2.launch.py"
    launch_contents = launch_path.read_text(encoding="utf-8")

    assert "localization_v2.yaml" in launch_contents
    assert 'executable="ackermann_odometry"' in launch_contents
    assert '"localization_params_file"' in launch_contents
    assert 'name="ekf_filter_node_local_v2"' in launch_contents
    assert 'executable="ekf_node"' in launch_contents
    assert launch_contents.count('executable="ukf_node"') == 0
    assert 'executable="pixhawk_odometry"' not in launch_contents
    assert 'name="navsat_transform"' not in launch_contents
    assert 'DeclareLaunchArgument("imu_topic", default_value="/imu/data")' in launch_contents
    assert '("odometry/filtered", "/odometry/local")' in launch_contents


def test_nav_local_v2_uses_keepout_specific_overrides() -> None:
    launch_path = PACKAGE_ROOT / "launch" / "nav_local_v2.launch.py"
    launch_contents = launch_path.read_text(encoding="utf-8")

    assert "nav2_no_map_local_frame_overrides.yaml" not in launch_contents
    assert "nav2_local_v2_keepout_overrides.yaml" in launch_contents
    assert "nav2_local_v2_no_keepout_overrides.yaml" in launch_contents
    assert "configured_nav2_overrides" in launch_contents
    assert 'DeclareLaunchArgument("keepout_mask_frame", default_value="odom")' in launch_contents
    assert '"keepout_mask_frame": keepout_mask_frame' in launch_contents


def test_nav2_only_launch_disables_velocity_smoother_and_honors_use_sim_time() -> None:
    launch_path = PACKAGE_ROOT / "launch" / "nav2_only.launch.py"
    launch_contents = launch_path.read_text(encoding="utf-8")

    assert '"use_velocity_smoother": "False"' in launch_contents
    assert '"use_sim_time": use_sim_time' in launch_contents
    assert "nav2_use_sim_time = ParameterValue(use_sim_time, value_type=bool)" in launch_contents


def test_nav2_no_map_uses_map_for_global_frame_and_odom_for_local_costmap() -> None:
    nav2_config_path = PACKAGE_ROOT / "config" / "nav2_no_map_params.yaml"
    nav2_config_contents = nav2_config_path.read_text(encoding="utf-8")

    assert "bt_navigator:" in nav2_config_contents
    assert "behavior_server:" in nav2_config_contents
    assert "global_costmap:" in nav2_config_contents
    assert "bt_navigator:" in nav2_config_contents
    assert "global_frame: map" in nav2_config_contents
    assert "local_costmap:" in nav2_config_contents
    assert "global_frame: odom" in nav2_config_contents


def test_dual_ekf_local_uses_wheel_and_pixhawk_odometry_topics() -> None:
    ekf_config_path = PACKAGE_ROOT / "config" / "dual_ekf_navsat_params.yaml"
    ekf_config_contents = ekf_config_path.read_text(encoding="utf-8")

    assert "ekf_filter_node_odom:" in ekf_config_contents
    assert "/wheel/odometry" in ekf_config_contents
    assert "ekf_filter_node_map:" in ekf_config_contents
    assert "odom1: /odometry/gps" in ekf_config_contents


def test_real_launch_includes_datum_setter_node() -> None:
    launch_path = PACKAGE_ROOT / "launch" / "real.launch.py"
    launch_contents = launch_path.read_text(encoding="utf-8")

    assert 'DeclareLaunchArgument(\n        "datum_setter",' in launch_contents
    assert "default_value=\"true\"" in launch_contents
    assert 'executable="datum_setter"' in launch_contents
    assert '"set_datum_service": "/datum_setter/set_datum"' in launch_contents
    assert '"get_datum_service": "/datum_setter/get_datum"' in launch_contents
    assert '"datum_service": "/datum"' in launch_contents
    assert '"datum_service_fallback": "/navsat_transform/datum"' in launch_contents
    assert "PythonExpression([\"'\", datum_setter, \"'.lower() == 'true'\"])" in launch_contents


def test_real_launch_includes_ackermann_odometry_by_default() -> None:
    launch_path = PACKAGE_ROOT / "launch" / "real.launch.py"
    launch_contents = launch_path.read_text(encoding="utf-8")

    assert 'DeclareLaunchArgument(\n        "ackermann_odometry",' in launch_contents
    assert 'default_value="true"' in launch_contents
    assert 'executable="ackermann_odometry"' in launch_contents
    assert "PythonExpression([\"'\", ackermann_odometry, \"'.lower() == 'true'\"])" in launch_contents
    assert '"telemetry_topic": "/controller/drive_telemetry"' in launch_contents
    assert '"odom_topic": "/wheel/odometry"' in launch_contents


def test_real_launch_includes_zones_manager_toggle() -> None:
    launch_path = PACKAGE_ROOT / "launch" / "real.launch.py"
    launch_contents = launch_path.read_text(encoding="utf-8")

    assert 'DeclareLaunchArgument(\n        "zones_manager",' in launch_contents
    assert 'default_value="true"' in launch_contents
    assert 'executable="zones_manager"' in launch_contents
    assert "PythonExpression([\"'\", zones_manager, \"'.lower() == 'true'\"])" in launch_contents


def test_real_launch_exposes_dual_ekf_toggles_and_no_controller_server() -> None:
    launch_path = PACKAGE_ROOT / "launch" / "real.launch.py"
    launch_contents = launch_path.read_text(encoding="utf-8")

    assert 'DeclareLaunchArgument(\n        "ekf_local",' in launch_contents
    assert 'default_value="true"' in launch_contents
    assert 'DeclareLaunchArgument(\n        "ekf_global",' in launch_contents
    assert "condition=IfCondition(ekf_local)" in launch_contents
    assert "condition=IfCondition(ekf_global)" in launch_contents
    assert 'name="ekf_filter_node_odom"' in launch_contents
    assert 'name="ekf_filter_node_map"' in launch_contents
    assert 'name="navsat_transform"' in launch_contents
    assert launch_contents.count('executable="ukf_node"') == 2
    assert 'executable="ekf_node"' not in launch_contents
    assert "condition=IfCondition(use_navsat)" not in launch_contents
    assert 'controller_server' not in launch_contents


def test_dual_ekf_navsat_waits_for_runtime_datum() -> None:
    ekf_config_path = PACKAGE_ROOT / "config" / "dual_ekf_navsat_params.yaml"
    ekf_config_contents = ekf_config_path.read_text(encoding="utf-8")

    assert "wait_for_datum: true" in ekf_config_contents
    assert "\n    datum:" not in ekf_config_contents
