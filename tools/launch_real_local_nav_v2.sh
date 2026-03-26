#!/usr/bin/env bash
set -euo pipefail

./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch navegacion_gps real_local_nav_v2.launch.py"
