from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_DIR = PACKAGE_ROOT / "launch"


def _read_launch_file(name: str) -> str:
    return (LAUNCH_DIR / name).read_text(encoding="utf-8")


def test_hybrid_localization_builds_local_plus_global_overlay() -> None:
    launch_contents = _read_launch_file("hybrid_localization_v2.launch.py")

    assert "localization_v2.launch.py" in launch_contents
    assert 'name="ekf_filter_node_map"' in launch_contents
    assert 'name="navsat_transform"' in launch_contents
    assert '"wait_for_datum": wait_for_datum' in launch_contents
    assert 'DeclareLaunchArgument("ekf_global", default_value="True")' in launch_contents


def test_sim_hybrid_launch_uses_global_nav_preset_on_top_of_local_base() -> None:
    launch_contents = _read_launch_file("sim_hybrid_nav_v2.launch.py")

    assert "sim_v2_base.launch.py" in launch_contents
    assert "hybrid_localization_v2.launch.py" in launch_contents
    assert "nav_local_v2.launch.py" in launch_contents
    assert '"fromll_frame": "map"' in launch_contents
    assert '"map_frame": "map"' in launch_contents
    assert '"forward_cmd_vel_safe_without_goal": True' in launch_contents
    assert '"keepout_mask_frame": "map"' in launch_contents
    assert 'DeclareLaunchArgument("wait_for_datum", default_value="False")' in launch_contents


def test_real_hybrid_launch_uses_global_nav_preset_and_runtime_datum() -> None:
    launch_contents = _read_launch_file("real_hybrid_nav_v2.launch.py")

    assert "hybrid_localization_v2.launch.py" in launch_contents
    assert "nav_local_v2.launch.py" in launch_contents
    assert 'executable="datum_setter"' in launch_contents
    assert 'executable="zones_manager"' in launch_contents
    assert 'executable="nav_snapshot_server"' in launch_contents
    assert '"fromll_frame": "map"' in launch_contents
    assert '"forward_cmd_vel_safe_without_goal": True' in launch_contents
    assert '"wait_for_datum": "True"' in launch_contents
