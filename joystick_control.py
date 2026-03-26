#!/usr/bin/env python3
"""
Control Xbox -> WebSocket del cuatri.

Por defecto replica el protocolo de la pagina legacy `Control.html`,
que hoy es la ruta que realmente mueve el cuatri.
"""

import argparse
import json
import os
import struct
import threading
import time
import sys
from typing import Optional

try:
    import websocket
except ModuleNotFoundError as exc:
    if (
        exc.name == "websocket"
        and sys.executable != "/usr/bin/python3"
        and os.path.exists("/usr/bin/python3")
        and os.environ.get("_JOYSTICK_CONTROL_REEXEC") != "1"
    ):
        env = dict(os.environ)
        env["_JOYSTICK_CONTROL_REEXEC"] = "1"
        os.execve("/usr/bin/python3", ["/usr/bin/python3", __file__, *sys.argv[1:]], env)
    print(
        "Falta el modulo 'websocket'. "
        "Usa /usr/bin/python3 o instala websocket-client en tu entorno actual."
    )
    raise SystemExit(2)


JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80


class JoystickControl:
    def __init__(
        self,
        cuatri_ip: str,
        ws_port: int,
        mode: str,
        dry_run: bool,
        send_hz: float,
        linear_max_mps: float,
        reverse_max_mps: float,
        angular_max_rps: float,
        angular_needs_linear_mps: float,
    ):
        self.mode = mode
        self.dry_run = bool(dry_run)
        if mode == "webui":
            self.ws_url = f"ws://{cuatri_ip}:{ws_port}"
        else:
            self.ws_url = f"ws://{cuatri_ip}:{ws_port}/controls"

        self.send_period_s = 1.0 / max(1.0, float(send_hz))
        self.linear_max_mps = max(0.0, float(linear_max_mps))
        self.reverse_max_mps = max(0.0, float(reverse_max_mps))
        self.angular_max_rps = max(0.0, float(angular_max_rps))
        self.angular_needs_linear_mps = max(0.0, float(angular_needs_linear_mps))

        self.ws: Optional[websocket.WebSocket] = None
        self.ws_lock = threading.Lock()
        self.running = True
        self.connected = False
        self.state_lock = threading.Lock()
        self.manual_enabled_remote = False
        self.throttle = 0.0
        self.steer = 0.0
        self.brake_until_s = 0.0
        self.last_print = None

    @staticmethod
    def _clamp(value: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, value))

    @staticmethod
    def _apply_deadband(value: float, deadband: float = 0.10) -> float:
        if abs(value) < deadband:
            return 0.0
        return value

    def connect(self) -> bool:
        if self.dry_run:
            if self.connected:
                return True
            print(f"Modo local sin red ({self.mode})")
            if self.mode == "webui":
                self.manual_enabled_remote = True
            self.connected = True
            return True
        try:
            self.ws = websocket.create_connection(
                self.ws_url,
                timeout=5,
                enable_multithread=True,
            )
            self.ws.settimeout(1.0)
            self.connected = True
            self.manual_enabled_remote = False
            print(f"Conectado a {self.ws_url} ({self.mode})")
            if self.mode == "webui":
                self._send_json({"op": "set_manual_mode", "enabled": True})
            else:
                self._send_json({"type": "pause", "value": False})
            return True
        except Exception as exc:
            print(f"No se pudo conectar a {self.ws_url}: {exc}")
            self.ws = None
            return False

    def _close_ws(self) -> None:
        ws = self.ws
        self.ws = None
        self.connected = False
        if ws is None:
            return
        try:
            ws.close()
        except Exception:
            pass

    def _send_json(self, payload: dict) -> bool:
        if self.dry_run:
            return True
        ws = self.ws
        if ws is None:
            return False
        try:
            with self.ws_lock:
                ws.send(json.dumps(payload))
            return True
        except Exception as exc:
            print(f"\nError enviando al WebSocket: {exc}")
            self._close_ws()
            return False

    def _drain_messages_loop(self) -> None:
        if self.dry_run:
            while self.running:
                time.sleep(0.2)
            return
        while self.running:
            ws = self.ws
            if ws is None:
                time.sleep(0.2)
                continue
            try:
                raw = ws.recv()
            except websocket.WebSocketTimeoutException:
                continue
            except Exception:
                self._close_ws()
                time.sleep(0.2)
                continue

            if not raw:
                continue

            try:
                msg = json.loads(raw)
            except Exception:
                continue

            if not isinstance(msg, dict):
                continue

            if self.mode == "webui" and "manual_control" in msg:
                manual = msg.get("manual_control") or {}
                self.manual_enabled_remote = bool(manual.get("enabled", False))
                continue

            if msg.get("op") == "ack" and not bool(msg.get("ok", False)):
                print(f"\nACK ERROR [{msg.get('request')}]: {msg.get('error')}")
            elif (
                self.mode == "webui"
                and msg.get("op") == "ack"
                and msg.get("request") == "set_manual_mode"
                and bool(msg.get("ok", False))
            ):
                self.manual_enabled_remote = bool(msg.get("enabled", False))
                print(f"\nManual mode: {msg.get('enabled')}")

    def _current_state(self) -> tuple[float, float, bool]:
        with self.state_lock:
            throttle = self.throttle
            steer = self.steer
            brake = time.monotonic() < self.brake_until_s
        return throttle, steer, brake

    def _current_payload(self) -> dict:
        throttle, steer, brake = self._current_state()
        if self.mode == "bridge":
            return {
                "throttle": round(throttle, 3),
                "steer": round(steer, 3),
                "brake": brake,
                "gear": 1,
                "camX": 0.0,
                "camY": 0.0,
            }

        if throttle >= 0.0:
            linear_x = throttle * self.linear_max_mps
        else:
            linear_x = throttle * self.reverse_max_mps

        angular_z = steer * self.angular_max_rps
        if linear_x < 0.0:
            angular_z = -angular_z
        if abs(linear_x) < self.angular_needs_linear_mps:
            angular_z = 0.0

        return {
            "op": "set_manual_cmd",
            "linear_x": round(linear_x, 3),
            "angular_z": round(angular_z, 3),
            "brake_pct": 100 if brake else 0,
        }

    def _print_state(self) -> None:
        throttle, steer, brake = self._current_state()
        if self.mode == "webui":
            payload = self._current_payload()
            keys = []
            if payload["linear_x"] > 0.0:
                keys.append("W")
            elif payload["linear_x"] < 0.0:
                keys.append("S")
            if payload["angular_z"] > 0.0:
                keys.append("A")
            elif payload["angular_z"] < 0.0:
                keys.append("D")
            if payload["brake_pct"] > 0:
                keys.append("SPACE")
            keys_label = "+".join(keys) if keys else "-"
            line = (
                f"Keys={keys_label:7s} "
                f"Linear={payload['linear_x']:+.2f} m/s "
                f"Angular={payload['angular_z']:+.2f} rad/s "
                f"Brake={payload['brake_pct']:3d}%"
            )
        else:
            line = (
                f"Throttle={throttle:+.2f} "
                f"Steer={steer:+.2f} "
                f"Brake={int(brake)}"
            )
        if line != self.last_print:
            print(line.ljust(64), end="\r", flush=True)
            self.last_print = line

    def _sender_loop(self) -> None:
        while self.running:
            if not self.connected and not self.connect():
                time.sleep(1.0)
                continue

            if self.mode == "webui" and not self.manual_enabled_remote:
                time.sleep(0.1)
                continue

            if not self._send_json(self._current_payload()):
                time.sleep(0.5)
                continue

            time.sleep(self.send_period_s)

    def _set_throttle(self, value: float) -> None:
        value = self._clamp(self._apply_deadband(value), -1.0, 1.0)
        with self.state_lock:
            self.throttle = value

    def _set_steer(self, value: float) -> None:
        value = self._clamp(self._apply_deadband(value), -1.0, 1.0)
        with self.state_lock:
            self.steer = value

    def _brake_now(self) -> None:
        with self.state_lock:
            self.throttle = 0.0
            self.steer = 0.0
            self.brake_until_s = time.monotonic() + 0.5

    def read_joystick(self) -> bool:
        try:
            with open("/dev/input/js0", "rb") as js:
                print("Joystick detectado en /dev/input/js0")
                while self.running:
                    event = js.read(8)
                    if len(event) < 8:
                        break

                    _, value, event_type, number = struct.unpack("IhBB", event)
                    event_type &= ~JS_EVENT_INIT

                    if event_type == JS_EVENT_AXIS:
                        axis_val = value / 32767.0

                        if number == 1:
                            self._set_throttle(-axis_val)
                            self._print_state()
                        elif number == 0:
                            self._set_steer(axis_val)
                            self._print_state()

                    elif event_type == JS_EVENT_BUTTON:
                        if number == 7 and value == 1:
                            self._brake_now()
                            self._print_state()
                            print("\nSTOP enviado")

        except FileNotFoundError:
            print("No existe /dev/input/js0. Conecta el joystick primero.")
            return False
        except KeyboardInterrupt:
            return True
        return True

    def stop(self) -> None:
        self.running = False
        self._brake_now()
        if self.ws is not None:
            for _ in range(3):
                self._send_json(self._current_payload())
                time.sleep(0.05)
            if self.mode == "webui":
                self._send_json({"op": "set_manual_mode", "enabled": False})
                time.sleep(0.05)
        self._close_ws()
        print("\nControl detenido")

    def run(self) -> int:
        sender = threading.Thread(target=self._sender_loop, daemon=True, name="ws-sender")
        receiver = threading.Thread(
            target=self._drain_messages_loop,
            daemon=True,
            name="ws-receiver",
        )
        receiver.start()
        sender.start()
        ok = self.read_joystick()
        self.stop()
        sender.join(timeout=1.0)
        receiver.join(timeout=1.0)
        return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Control Xbox -> cuatri por WebSocket")
    parser.add_argument("--ip", default="100.111.4.7", help="IP del cuatri")
    parser.add_argument(
        "--mode",
        choices=("webui", "bridge"),
        default="webui",
        help="webui: mismo flujo que la pagina WASD; bridge: protocolo legacy",
    )
    parser.add_argument("--port", type=int, default=None, help="Puerto WebSocket")
    parser.add_argument("--hz", type=float, default=20.0, help="Frecuencia de envio")
    parser.add_argument("--linear-max", type=float, default=1.20, help="Velocidad maxima adelante m/s")
    parser.add_argument("--reverse-max", type=float, default=1.20, help="Velocidad maxima reversa m/s")
    parser.add_argument("--angular-max", type=float, default=0.40, help="Velocidad angular maxima rad/s")
    parser.add_argument(
        "--angular-needs-linear",
        type=float,
        default=0.0,
        help="No enviar giro si la velocidad lineal es muy baja",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No abre WebSocket; solo muestra en pantalla el comando que saldria",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ws_port = args.port
    if ws_port is None:
        ws_port = 8766 if args.mode == "webui" else 8765

    ctrl = JoystickControl(
        cuatri_ip=args.ip,
        ws_port=ws_port,
        mode=args.mode,
        dry_run=args.dry_run,
        send_hz=args.hz,
        linear_max_mps=args.linear_max,
        reverse_max_mps=args.reverse_max,
        angular_max_rps=args.angular_max,
        angular_needs_linear_mps=args.angular_needs_linear,
    )
    return ctrl.run()


if __name__ == "__main__":
    raise SystemExit(main())
