from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_DIR = PACKAGE_ROOT / "launch"


def _read_launch_file(name: str) -> str:
    return (LAUNCH_DIR / name).read_text(encoding="utf-8")


def test_simulation_launch_is_a_local_stack_wrapper_with_web_tools() -> None:
    simulation_launch = _read_launch_file("simulacion.launch.py")

    assert "sim_local_v2.launch.py" in simulation_launch
    assert "no_go_editor.launch.py" in simulation_launch
    assert 'DeclareLaunchArgument("ekf_global", default_value="False")' in simulation_launch
    assert 'DeclareLaunchArgument("datum_setter", default_value="false")' in simulation_launch
    assert '"map_frame": "odom"' in simulation_launch
    assert '"zones_fromll_output_frame": "odom"' in simulation_launch


def test_real_launch_keeps_global_navigation_contracts() -> None:
    simulation_launch = _read_launch_file("simulacion.launch.py")
    real_launch = _read_launch_file("real.launch.py")

    assert "dual_ekf_navsat_params.yaml" not in simulation_launch
    assert "dual_ekf_navsat_params.yaml" in real_launch
    assert 'default_value="/gps/fix"' in real_launch
    assert '"odometry/local"' in real_launch
    assert '"map_frame": "map"' in real_launch


def test_simulation_and_real_entrypoints_are_distinct_by_design() -> None:
    simulation_launch = _read_launch_file("simulacion.launch.py")
    real_launch = _read_launch_file("real.launch.py")

    assert "sim_local_v2.launch.py" in simulation_launch
    assert "nav2_only.launch.py" not in simulation_launch
    assert "navigation_launch.py" not in simulation_launch
    assert "nav2_only.launch.py" in real_launch
