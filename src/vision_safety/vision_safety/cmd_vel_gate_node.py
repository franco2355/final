#!/usr/bin/env python3
"""
Gate de velocidad con stop y reversa controlada por visión.

Pipeline esperado (modo gate activo):
  Nav2 → /cmd_vel_nav → collision_monitor (out=/cmd_vel_nav_safe)
       → [este nodo] → /cmd_vel_safe → bridge → Gazebo

Estados:
  PASSTHROUGH   No hay detección. Reenvía el comando del CM sin cambios.
  STOPPING      Detección activa. Publica cero. Espera N frames para confirmar.
  REVERSING     Retrocede a velocidad baja por reverse_duration_s segundos.
  WAIT_CLEAR    Retroceso completado. Publica cero hasta que la vía esté libre.

Transiciones:
  PASSTHROUGH → STOPPING      : fused_stop_active=True por ≥1 frame fresco
  STOPPING    → REVERSING     : stop_confirm_frames consecutivos con stop activo
  REVERSING   → WAIT_CLEAR    : elapsed >= reverse_duration_s
  WAIT_CLEAR  → PASSTHROUGH   : clear_frames_needed frames seguidos sin stop
                                 O timeout wait_clear_timeout_s (failsafe: sigue la ruta)
  cualquier estado → PASSTHROUGH (si vision_signal queda stale)

Post-ciclo: tras REVERSE→PASSTHROUGH se activa cooldown post_cycle_cooldown_s durante
el cual el gate no frena aunque haya detección (evita oscilar en el mismo punto).
Solo se frena si linear.x > min_stop_speed_mps (robot avanzando hacia el obstáculo).

El nodo NO se lanza en el wrapper pasivo. Solo se usa desde
vision_safety_simulation_gate.launch.py.
"""
from __future__ import annotations

import json
import time
from typing import Optional

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Bool, String


def _zero() -> Twist:
    """Retorna un mensaje Twist con todos los campos en cero para detener el robot completamente."""
    # Twist con todos los campos en cero → detiene el robot completamente
    return Twist()


def _reverse(speed: float) -> Twist:
    """Genera un mensaje Twist de retroceso con velocidad lineal negativa a partir de la magnitud dada."""
    # Genera comando de retroceso; abs() garantiza lineal.x negativo sin importar el signo de speed
    msg = Twist()
    msg.linear.x = -abs(speed)
    return msg


class CmdVelGateNode(Node):
    STATE_PASS = "passthrough"
    STATE_STOP = "stopping"
    STATE_REVERSE = "reversing"
    STATE_WAIT_CLEAR = "wait_clear"

    def __init__(self) -> None:
        """Inicializa el nodo, declara parámetros ROS2 y crea publicadores, suscriptores y el timer principal."""
        super().__init__("cmd_vel_gate")

        # ── tópicos ──────────────────────────────────────────────────────────
        self.declare_parameter("input_cmd_vel_topic", "/cmd_vel_nav_safe")
        self.declare_parameter("output_cmd_vel_topic", "/cmd_vel_safe")
        self.declare_parameter("vision_stop_topic", "/vision/fused_stop_active")
        self.declare_parameter("gate_state_topic", "/vision_safety/gate/state")

        # ── comportamiento ───────────────────────────────────────────────────
        self.declare_parameter("publish_hz", 20.0)
        self.declare_parameter("vision_timeout_s", 0.5)
        self.declare_parameter("stop_confirm_frames", 3)
        self.declare_parameter("reverse_speed_mps", 0.25)
        self.declare_parameter("reverse_duration_s", 1.5)
        self.declare_parameter("clear_frames_needed", 5)
        self.declare_parameter("wait_clear_timeout_s", 3.0)
        self.declare_parameter("post_cycle_cooldown_s", 5.0)
        self.declare_parameter("min_stop_speed_mps", 0.02)

        self._in_topic = str(self.get_parameter("input_cmd_vel_topic").value)
        self._out_topic = str(self.get_parameter("output_cmd_vel_topic").value)
        self._stop_topic = str(self.get_parameter("vision_stop_topic").value)
        self._state_topic = str(self.get_parameter("gate_state_topic").value)

        self._hz = max(1.0, float(self.get_parameter("publish_hz").value))
        self._vision_timeout = max(0.05, float(self.get_parameter("vision_timeout_s").value))
        self._stop_confirm = max(1, int(self.get_parameter("stop_confirm_frames").value))
        self._rev_speed = abs(float(self.get_parameter("reverse_speed_mps").value))
        self._rev_dur = max(0.1, float(self.get_parameter("reverse_duration_s").value))
        self._clear_needed = max(1, int(self.get_parameter("clear_frames_needed").value))
        self._wait_clear_timeout = max(0.5, float(self.get_parameter("wait_clear_timeout_s").value))
        self._post_cycle_cooldown = max(0.0, float(self.get_parameter("post_cycle_cooldown_s").value))
        self._min_stop_speed = abs(float(self.get_parameter("min_stop_speed_mps").value))

        # ── estado interno ───────────────────────────────────────────────────
        self._last_nav_cmd: Twist = _zero()
        self._last_nav_time: Optional[float] = None
        self._vision_stop: bool = False
        self._vision_time: Optional[float] = None

        self._state: str = self.STATE_PASS
        self._stop_frame_count: int = 0
        self._clear_frame_count: int = 0
        self._reverse_start: Optional[float] = None
        self._wait_clear_start: Optional[float] = None
        self._cooldown_end: Optional[float] = None
        self._prev_log_state: Optional[str] = None

        # ── pub/sub ──────────────────────────────────────────────────────────
        self._cmd_pub = self.create_publisher(Twist, self._out_topic, 10)
        self._state_pub = self.create_publisher(String, self._state_topic, 10)
        self.create_subscription(Twist, self._in_topic, self._on_nav_cmd, 10)
        self.create_subscription(Bool, self._stop_topic, self._on_vision_stop, 10)
        self.create_timer(1.0 / self._hz, self._tick)

        self.get_logger().info(
            f"cmd_vel_gate ready  in={self._in_topic}  out={self._out_topic}  "
            f"stop={self._stop_topic}  rev={self._rev_speed}m/s x {self._rev_dur}s"
        )

    # ── callbacks ────────────────────────────────────────────────────────────

    def _on_nav_cmd(self, msg: Twist) -> None:
        """Almacena el último comando de velocidad recibido desde el upstream (Nav2 o collision monitor)."""
        self._last_nav_cmd = msg
        self._last_nav_time = time.monotonic()

    def _on_vision_stop(self, msg: Bool) -> None:
        """Actualiza la señal de parada de visión y registra el instante de recepción para el control de frescura."""
        self._vision_stop = bool(msg.data)
        self._vision_time = time.monotonic()

    # ── lógica principal ─────────────────────────────────────────────────────

    def _vision_is_fresh(self, now: float) -> bool:
        """Retorna True si la última señal de visión llegó dentro del timeout configurado; en caso contrario aplica fail-safe abierto."""
        # Fail-safe abierto: si no hay señal reciente de visión, el gate deja pasar el cmd_vel.
        # Así un fallo del detector no paraliza el robot indefinidamente.
        return (
            self._vision_time is not None
            and (now - self._vision_time) <= self._vision_timeout
        )

    def _tick(self) -> None:
        """Ejecuta un ciclo de la máquina de estados del gate, decide qué comando publicar y actualiza el estado."""
        now = time.monotonic()
        vision_fresh = self._vision_is_fresh(now)              # señal llegó dentro del timeout
        stop_active = self._vision_stop and vision_fresh        # detección activa Y señal fresca
        in_cooldown = self._cooldown_end is not None and now < self._cooldown_end  # post-ciclo: no frenar
        moving_forward = self._last_nav_cmd.linear.x > self._min_stop_speed       # robot avanzando

        if self._state == self.STATE_PASS:
            if stop_active and moving_forward and not in_cooldown:
                # Transición PASSTHROUGH → STOPPING: detección fresca, robot avanza, sin cooldown
                self._state = self.STATE_STOP
                self._stop_frame_count = 1
                self._clear_frame_count = 0
            else:
                self._publish_nav_cmd()

        elif self._state == self.STATE_STOP:
            if not vision_fresh:
                # Señal de visión expiró (timeout) → fail-safe abierto: retomar sin retroceder
                self._reset_to_pass()
                self._publish_nav_cmd()
            elif stop_active:
                self._stop_frame_count += 1
                self._cmd_pub.publish(_zero())
                if self._stop_frame_count >= self._stop_confirm:
                    # N frames consecutivos confirmados → pasar a REVERSING
                    self._state = self.STATE_REVERSE
                    self._reverse_start = now
            else:
                # Obstáculo desapareció antes de confirmar → cancelar frenada
                self._reset_to_pass()
                self._publish_nav_cmd()

        elif self._state == self.STATE_REVERSE:
            # Retrocede a velocidad fija durante reverse_duration_s segundos
            elapsed = now - self._reverse_start if self._reverse_start else self._rev_dur
            if elapsed < self._rev_dur:
                self._cmd_pub.publish(_reverse(self._rev_speed))
            else:
                # Tiempo de retroceso agotado → detener y esperar que el camino quede libre
                self._state = self.STATE_WAIT_CLEAR
                self._clear_frame_count = 0
                self._wait_clear_start = now
                self._cmd_pub.publish(_zero())

        elif self._state == self.STATE_WAIT_CLEAR:
            # Robot detenido; espera clear_frames_needed frames seguidos sin detección activa
            wait_elapsed = now - self._wait_clear_start if self._wait_clear_start else 0.0
            if wait_elapsed >= self._wait_clear_timeout:
                self.get_logger().warning(
                    f"GATE: timeout wait_clear ({self._wait_clear_timeout}s) → retomando ruta "
                    f"(cooldown {self._post_cycle_cooldown}s)"
                )
                self._cooldown_end = now + self._post_cycle_cooldown  # evitar frenada inmediata al retomar
                self._reset_to_pass()
                self._publish_nav_cmd()
            elif not stop_active:
                self._clear_frame_count += 1
                self._cmd_pub.publish(_zero())
                if self._clear_frame_count >= self._clear_needed:
                    # Despeje confirmado: N frames seguidos sin obstáculo → PASSTHROUGH
                    self._reset_to_pass()
                    self._publish_nav_cmd()
            else:
                # Obstáculo aún presente → resetear contador y mantener parado
                self._clear_frame_count = 0
                self._cmd_pub.publish(_zero())

        self._publish_state(now, vision_fresh, stop_active)

    def _publish_nav_cmd(self) -> None:
        """Publica el último comando de navegación recibido, o cero si aún no se ha recibido ninguno."""
        if self._last_nav_time is None:
            self._cmd_pub.publish(_zero())
            return
        self._cmd_pub.publish(self._last_nav_cmd)

    def _reset_to_pass(self) -> None:
        """Restablece la máquina de estados al modo PASSTHROUGH y limpia todos los contadores internos."""
        self._state = self.STATE_PASS
        self._stop_frame_count = 0
        self._clear_frame_count = 0
        self._reverse_start = None
        self._wait_clear_start = None

    def _publish_state(self, now: float, vision_fresh: bool, stop_active: bool) -> None:
        """Serializa el estado interno del gate como JSON y lo publica; también registra cambios de estado en el log."""
        # Serializa el estado interno como JSON y lo publica en gate_state_topic.
        # El viz_node y herramientas de debug (ros2 topic echo) consumen este tópico.
        payload = {
            "state": self._state,
            "stop_active": stop_active,
            "vision_fresh": vision_fresh,
            "stop_frames": self._stop_frame_count,
            "clear_frames": self._clear_frame_count,
        }
        if self._reverse_start and self._state == self.STATE_REVERSE:
            payload["reverse_elapsed_s"] = round(now - self._reverse_start, 2)
        msg = String()
        msg.data = json.dumps(payload, separators=(",", ":"))  # formato compacto sin espacios
        self._state_pub.publish(msg)

        if self._state != self._prev_log_state:
            if self._state == self.STATE_STOP:
                self.get_logger().warning("GATE: objeto detectado → FRENANDO")
            elif self._state == self.STATE_REVERSE:
                self.get_logger().warning(
                    f"GATE: confirmado → RETROCEDIENDO {self._rev_speed}m/s x {self._rev_dur}s"
                )
            elif self._state == self.STATE_WAIT_CLEAR:
                self.get_logger().info("GATE: retroceso completo → esperando despeje")
            elif self._state == self.STATE_PASS:
                self.get_logger().info("GATE: vía libre → PASO NORMAL")
            self._prev_log_state = self._state


def main(args=None) -> None:
    """Punto de entrada del nodo: inicializa rclpy, crea el nodo y lo mantiene en spin hasta interrupción."""
    rclpy.init(args=args)
    node = CmdVelGateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
