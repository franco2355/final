#!/usr/bin/env bash
set -euo pipefail

CONTAINER="ros2"
PATTERN='ign gazebo|ros_gz_bridge|ros_gz_sim/create|sim_local_v2.launch.py|sim_v2_base.launch.py|sim_drive_telemetry|sim_sensor_normalizer_v2|cmd_vel_ackermann_bridge_v2|ackermann_odometry|ekf_filter_node_local_v2|lifecycle_manager_local_navigation_v2|nav2_local_v2_params.yaml|collision_monitor_v2.yaml|goal_pose_to_follow_path_v2'

if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "El contenedor ${CONTAINER} no esta corriendo."
  exit 1
fi

docker exec "${CONTAINER}" bash -lc "
  pids=\$(ps -eo pid=,args= | grep -E \"${PATTERN}\" | grep -v grep | awk '{print \$1}')
  if [ -n \"\${pids}\" ]; then
    kill \${pids} || true
    sleep 2
  fi
  remaining=\$(ps -eo pid=,args= | grep -E \"${PATTERN}\" | grep -v grep || true)
  if [ -n \"\${remaining}\" ]; then
    remaining_pids=\$(printf '%s\n' \"\${remaining}\" | awk '{print \$1}')
    kill -9 \${remaining_pids} || true
    sleep 1
    remaining=\$(ps -eo pid=,args= | grep -E \"${PATTERN}\" | grep -v grep || true)
    if [ -n \"\${remaining}\" ]; then
      echo \"Aun quedan procesos:\" >&2
      echo \"\${remaining}\" >&2
      exit 2
    fi
  fi
"

echo "Simulacion v2 detenida."
