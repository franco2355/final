from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_DIR = PACKAGE_ROOT / "launch"


def _read_launch_file(name: str) -> str:
    return (LAUNCH_DIR / name).read_text(encoding="utf-8")


def test_named_local_and_global_wrappers_point_to_expected_launches() -> None:
    assert "sim_local_v2.launch.py" in _read_launch_file("sim_local_nav_v2.launch.py")
    assert "real_local_v2.launch.py" in _read_launch_file("real_local_nav_v2.launch.py")
    assert "sim_hybrid_nav_v2.launch.py" in _read_launch_file("sim_global_nav_v2.launch.py")
    assert "real_hybrid_nav_v2.launch.py" in _read_launch_file("real_global_nav_v2.launch.py")
