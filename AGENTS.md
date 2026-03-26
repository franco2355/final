# AGENTS

## Project context
- Project: large autonomous patrol quadricycle (Ackermann steering)
- Platform: Raspberry Pi 5
- ROS 2 distro: Humble (Docker-based workflow)
- Navigation stack: Nav2 + robot_localization (dual EKF + navsat_transform)
- Hardware: Pixhawk 6X + DroneCAN F9P (GPS), RoboSense RS16 LiDAR, wheel odometry

## Access
- SSH target: `ssh salus`

## Paths
- Local workspace on this machine: `/home/gmorini/Documentos/codigo/ros2/workspace`
- Workspace inside Docker container: `/ros2_ws`
- ROS 2 workspace on robot target: `~/ros2_ws`
- Reference controller code (wheels/brakes/steering): `~/codigo/RASPY_SALUS`

## Source packages (current)
- `src/navegacion_gps`: Nav2 bringup, localization launch composition, GPS waypoint tools, frame_id normalization, simulation assets (URDF/worlds/config).
- `src/sensores`: Pixhawk MAVLink driver, RS16 launch/config, optional web status server.
- `src/cmd_vel_uart_bridge`: `/cmd_vel_safe` to UART/WebSocket bridge and `salus_v2` protocol stack.
- `src/rslidar_sdk`: RoboSense SDK node (point cloud/packets pipeline).
- `src/rslidar_msg`: custom RoboSense ROS 2 messages.

## Launch entry points (source of truth)
- Navigation package:
  - `ros2 launch navegacion_gps simulacion.launch.py`
  - `ros2 launch navegacion_gps real.launch.py`
  - `ros2 launch navegacion_gps full_stack.launch.py`
  - `ros2 launch navegacion_gps navegacion.launch.py`
  - `ros2 launch navegacion_gps dual_ekf_navsat.launch.py`
  - `ros2 launch navegacion_gps rviz_real.launch.py`
  - `ros2 launch navegacion_gps mapviz.launch.py`
- Sensors package:
  - `ros2 launch sensores pixhawk.launch.py`
  - `ros2 launch sensores rs16.launch.py`
- Bridge package:
  - `ros2 launch cmd_vel_uart_bridge salus_bridge.launch.py`
  - `ros2 launch cmd_vel_uart_bridge ws_bridge.launch.py`
  - `ros2 launch cmd_vel_uart_bridge bridge.launch.py`
  - `ros2 launch cmd_vel_uart_bridge web_control.launch.py`

## Runtime architecture notes
- `cmd_vel` safety path:
  - Nav2 publishes `/cmd_vel`
  - `nav2_collision_monitor` outputs `/cmd_vel_safe`
  - actuator bridges consume `/cmd_vel_safe`
- LiDAR path:
  - RS16 publishes point cloud on `/scan_3d`
  - `pointcloud_to_laserscan` publishes `/scan` for Nav2/costmaps
- Localization inputs:
  - `/imu/data`, `/gps/fix`, `/odom`
  - outputs include `/odometry/local` and `/odometry/gps` with TF `map -> odom -> base_footprint`
- Simulation (Gazebo/ros_gz):
  - robot consumes `/cmd_vel_steer`
  - bridge config handles topic remaps and raw sensor topics (`*_raw`)

## Practical scripts (repo root)
- `./tools/exec.sh`
- `./tools/compile-ros.sh`
- `./tools/launch_real_nav.sh`
- `./tools/launch_real_rviz.sh`
- `./tools/ws-bridge.sh`
- `./tools/healthcheck-lidar.sh`

## Known drift / caveats
- Some old docs/scripts in history reference launches or nodes that are not present anymore.
- In `src/navegacion_gps/setup.py`, entry point `teleop = navegacion_gps.teleop:main` exists, but `navegacion_gps/teleop.py` is currently missing.
- Prefer the launch files listed in this AGENTS file as current canonical entry points.

## Repository layout caveat
- `src/*` includes nested git repositories; check git status/branch per package when making changes or reviews.
