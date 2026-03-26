from setuptools import find_packages, setup
import os
from glob import glob

package_name = "vision_safety"

setup(
    name=package_name,
    version="0.2.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob("launch/*.launch.py"),
        ),
        (
            os.path.join("share", package_name, "config"),
            glob("config/*.rviz") + glob("config/*.yaml"),
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="franco",
    maintainer_email="dev@example.com",
    description="Passive vision + LiDAR fusion layer",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "vision_lidar_fusion_node = vision_safety.vision_lidar_fusion_node:main",
            "mock_detections_node = vision_safety.mock_detections_node:main",
            "mock_laserscan_node = vision_safety.mock_laserscan_node:main",
            "cmd_vel_gate_node = vision_safety.cmd_vel_gate_node:main",
            "vision_safety_viz_node = vision_safety.vision_safety_viz_node:main",
        ],
    },
)
