"""Named wrapper for the hybrid/global simulation navigation stack."""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    package_share_dir = get_package_share_directory("navegacion_gps")
    legacy_launch = os.path.join(package_share_dir, "launch", "sim_hybrid_nav_v2.launch.py")

    return LaunchDescription(
        [
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(legacy_launch),
            )
        ]
    )
