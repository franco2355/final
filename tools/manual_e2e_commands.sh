#!/usr/bin/env bash
set -euo pipefail

# Manual E2E command matrix for controller_server.
# Runs full matrix via /cmd_vel_safe, then repeats via WebSocket.
# No automatic assertions; intended for operator observation.

SLEEP_SECS=2
WS_URL="${WS_URL:-ws://127.0.0.1:8765}"

if ! command -v ros2 >/dev/null 2>&1; then
  echo "ERROR: ros2 command not found. Source your ROS2 environment first."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 command not found."
  exit 1
fi

echo "============================================================"
echo "Manual E2E matrix"
echo "WS_URL: ${WS_URL}"
echo "Sleep between cases: ${SLEEP_SECS}s"
echo "============================================================"
echo
echo "Recommended monitor (run in another terminal):"
echo "  ros2 topic echo /controller/status"
echo

run_cmd_vel_case() {
  local name="$1"
  local linear_x="$2"
  local angular_z="$3"
  echo "[cmd_vel_safe] ${name}: linear.x=${linear_x}, angular.z=${angular_z}"
  ros2 topic pub --once /cmd_vel_safe geometry_msgs/msg/Twist \
    "{linear: {x: ${linear_x}, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: ${angular_z}}}"
  sleep "${SLEEP_SECS}"
}

ws_send_json() {
  local payload="$1"
  python3 - "$WS_URL" "$payload" <<'PY'
import asyncio
import json
import sys

ws_url = sys.argv[1]
payload_raw = sys.argv[2]

async def main():
    try:
        import websockets
    except Exception as exc:
        print(f"ERROR: missing websockets package: {exc}")
        raise

    payload = json.loads(payload_raw)
    async with websockets.connect(ws_url) as ws:
        hello = await ws.recv()
        print(f"  ws hello: {hello}")
        await ws.send(json.dumps(payload))
        reply = await ws.recv()
        print(f"  ws reply: {reply}")

asyncio.run(main())
PY
}

run_ws_case() {
  local name="$1"
  local payload="$2"
  echo "[websocket] ${name}: payload=${payload}"
  ws_send_json "${payload}"
  sleep "${SLEEP_SECS}"
}

echo "---- Phase 1/2: /cmd_vel_safe matrix ----"
run_cmd_vel_case "straight_slow" "0.40" "0.00"
run_cmd_vel_case "straight_medium" "0.80" "0.00"
run_cmd_vel_case "turn_right_only" "0.00" "-0.30"
run_cmd_vel_case "turn_left_only" "0.00" "0.30"
run_cmd_vel_case "accelerate_turn_right" "0.80" "-0.25"
run_cmd_vel_case "accelerate_turn_left" "0.80" "0.25"
run_cmd_vel_case "slow_forward_tight_right" "0.20" "-0.40"
run_cmd_vel_case "slow_forward_tight_left" "0.20" "0.40"
run_cmd_vel_case "stop_command" "0.00" "0.00"

echo
echo "---- Phase 2/2: WebSocket matrix ----"
run_ws_case "set_manual_mode" '{"mode":"manual","estop":false}'
run_ws_case "enable_drive" '{"drive":true,"speed_mps":0.0,"steer_pct":0,"brake_pct":0}'
run_ws_case "straight_slow" '{"drive":true,"speed_mps":0.40,"steer_pct":0,"brake_pct":0}'
run_ws_case "straight_medium" '{"drive":true,"speed_mps":0.80,"steer_pct":0,"brake_pct":0}'
run_ws_case "turn_right_only" '{"drive":true,"speed_mps":0.00,"steer_pct":-35,"brake_pct":0}'
run_ws_case "turn_left_only" '{"drive":true,"speed_mps":0.00,"steer_pct":35,"brake_pct":0}'
run_ws_case "accelerate_turn_right" '{"drive":true,"speed_mps":0.80,"steer_pct":-30,"brake_pct":0}'
run_ws_case "accelerate_turn_left" '{"drive":true,"speed_mps":0.80,"steer_pct":30,"brake_pct":0}'
run_ws_case "apply_brake" '{"drive":true,"speed_mps":0.00,"steer_pct":0,"brake_pct":30}'
run_ws_case "release_brake" '{"drive":true,"speed_mps":0.00,"steer_pct":0,"brake_pct":0}'
run_ws_case "safe_stop" '{"drive":false,"speed_mps":0.0,"steer_pct":0,"brake_pct":0,"cmd_estop":false}'
run_ws_case "back_to_auto_mode" '{"mode":"auto","estop":false}'

echo
echo "Matrix completed."
echo "If needed, enforce safe stop manually:"
echo "  python3 - <<'PY'"
echo "  import asyncio, json, websockets"
echo "  async def main():"
echo "      async with websockets.connect('${WS_URL}') as ws:"
echo "          await ws.recv(); await ws.send(json.dumps({'mode':'manual','drive':False,'speed_mps':0,'steer_pct':0,'brake_pct':0,'estop':True}))"
echo "          print(await ws.recv())"
echo "  asyncio.run(main())"
echo "  PY"
