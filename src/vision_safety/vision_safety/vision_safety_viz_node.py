#!/usr/bin/env python3
"""RViz visualization for the vision_safety MVP."""

from __future__ import annotations

import json
import math
import time
from typing import Optional

import rclpy
from geometry_msgs.msg import Point, Twist
from rclpy.node import Node
from std_msgs.msg import Bool, String
from visualization_msgs.msg import Marker, MarkerArray


def _point(x: float, y: float, z: float) -> Point:
    """Crea y retorna un objeto Point con las coordenadas x, y, z dadas."""
    pt = Point()
    pt.x = x
    pt.y = y
    pt.z = z
    return pt


class VisionSafetyVizNode(Node):
    """Publish a compact RViz view of gate state and cmd_vel flow."""

    def __init__(self) -> None:
        """Inicializa el nodo de visualización, declara parámetros y crea publicadores, suscriptores y el timer de renderizado."""
        super().__init__("vision_safety_viz")

        self.declare_parameter("frame_id", "map")
        self.declare_parameter("input_cmd_vel_topic", "/cmd_vel_safe")
        self.declare_parameter("output_cmd_vel_topic", "/cmd_vel_final")
        self.declare_parameter("vision_stop_topic", "/vision/stop_active")
        self.declare_parameter("gate_state_topic", "/vision_safety/cmd_vel_gate/state")
        self.declare_parameter("markers_topic", "/vision_safety/markers")
        self.declare_parameter("compat_markers_topic", "/visualization_marker_array")
        self.declare_parameter("publish_hz", 10.0)
        self.declare_parameter("linear_scale", 1.2)

        self.frame_id = str(self.get_parameter("frame_id").value)
        self.input_cmd_vel_topic = str(
            self.get_parameter("input_cmd_vel_topic").value
        )
        self.output_cmd_vel_topic = str(
            self.get_parameter("output_cmd_vel_topic").value
        )
        self.vision_stop_topic = str(self.get_parameter("vision_stop_topic").value)
        self.gate_state_topic = str(self.get_parameter("gate_state_topic").value)
        self.markers_topic = str(self.get_parameter("markers_topic").value)
        self.compat_markers_topic = str(
            self.get_parameter("compat_markers_topic").value
        )
        self.publish_hz = max(1.0, float(self.get_parameter("publish_hz").value))
        self.linear_scale = max(0.1, float(self.get_parameter("linear_scale").value))

        self._last_input_cmd = Twist()
        self._last_output_cmd = Twist()
        self._last_vision_stop = False
        self._gate_blocked = False
        self._gate_degraded = False
        self._gate_reason = "no_state"
        self._last_gate_update_s: Optional[float] = None

        self._markers_pub = self.create_publisher(MarkerArray, self.markers_topic, 10)
        self._compat_markers_pub = self.create_publisher(
            MarkerArray, self.compat_markers_topic, 10
        )
        self.create_subscription(Twist, self.input_cmd_vel_topic, self._on_input_cmd, 10)
        self.create_subscription(
            Twist, self.output_cmd_vel_topic, self._on_output_cmd, 10
        )
        self.create_subscription(
            Bool, self.vision_stop_topic, self._on_vision_stop, 10
        )
        self.create_subscription(
            String, self.gate_state_topic, self._on_gate_state, 10
        )
        self.create_timer(1.0 / self.publish_hz, self._tick)

        self.get_logger().info(
            "vision_safety_viz ready "
            f"(frame={self.frame_id}, markers={self.markers_topic}, compat={self.compat_markers_topic})"
        )

    def _on_input_cmd(self, msg: Twist) -> None:
        """Almacena el último comando de velocidad de entrada recibido en el tópico input_cmd_vel."""
        self._last_input_cmd = msg

    def _on_output_cmd(self, msg: Twist) -> None:
        """Almacena el último comando de velocidad de salida recibido en el tópico output_cmd_vel."""
        self._last_output_cmd = msg

    def _on_vision_stop(self, msg: Bool) -> None:
        """Actualiza el flag de parada de visión con el valor del mensaje Bool recibido."""
        self._last_vision_stop = bool(msg.data)

    def _on_gate_state(self, msg: String) -> None:
        """Parsea el JSON del estado del gate y actualiza los flags internos de bloqueo, degradación y razón."""
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self._gate_reason = "invalid_gate_state_json"
            self._last_gate_update_s = time.monotonic()
            return
        self._gate_blocked = bool(payload.get("blocked", False))
        self._gate_degraded = bool(payload.get("degraded", False))
        self._gate_reason = str(payload.get("reason", "unknown"))
        self._last_gate_update_s = time.monotonic()

    def _make_text_marker(
        self, marker_id: int, x: float, y: float, z: float, text: str,
        rgb: tuple[float, float, float], scale_z: float = 0.14
    ) -> Marker:
        """Crea y retorna un Marker de tipo TEXT_VIEW_FACING en la posición y color indicados."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "vision_safety_text"
        marker.id = marker_id
        marker.type = Marker.TEXT_VIEW_FACING
        marker.action = Marker.ADD
        marker.pose.position = _point(x, y, z)
        marker.pose.orientation.w = 1.0
        marker.scale.z = scale_z
        marker.color.a = 1.0
        marker.color.r, marker.color.g, marker.color.b = rgb
        marker.text = text
        return marker

    def _make_sphere_marker(
        self, marker_id: int, x: float, y: float, z: float,
        rgb: tuple[float, float, float], scale: float = 0.16
    ) -> Marker:
        """Crea y retorna un Marker de tipo SPHERE en la posición y color indicados con escala uniforme."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "vision_safety_state"
        marker.id = marker_id
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.pose.position = _point(x, y, z)
        marker.pose.orientation.w = 1.0
        marker.scale.x = scale
        marker.scale.y = scale
        marker.scale.z = scale
        marker.color.a = 0.95
        marker.color.r, marker.color.g, marker.color.b = rgb
        return marker

    def _make_cube_marker(
        self, marker_id: int, x: float, y: float, z: float,
        rgb: tuple[float, float, float], scale_xyz: tuple[float, float, float]
    ) -> Marker:
        """Crea y retorna un Marker de tipo CUBE en la posición y color indicados con escala no uniforme."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "vision_safety_state"
        marker.id = marker_id
        marker.type = Marker.CUBE
        marker.action = Marker.ADD
        marker.pose.position = _point(x, y, z)
        marker.pose.orientation.w = 1.0
        marker.scale.x = scale_xyz[0]
        marker.scale.y = scale_xyz[1]
        marker.scale.z = scale_xyz[2]
        marker.color.a = 0.85
        marker.color.r, marker.color.g, marker.color.b = rgb
        return marker

    def _make_arrow_marker(
        self, marker_id: int, origin_y: float, cmd: Twist,
        rgb: tuple[float, float, float]
    ) -> Marker:
        """Crea y retorna un Marker de tipo ARROW cuya longitud y dirección representan visualmente el Twist dado."""
        marker = Marker()
        marker.header.frame_id = self.frame_id
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = "vision_safety_cmd"
        marker.id = marker_id
        marker.type = Marker.ARROW
        marker.action = Marker.ADD

        linear = float(cmd.linear.x)
        angular = float(cmd.angular.z)
        # Longitud de la flecha proporcional a velocidad lineal; límite visual de 1.5 m
        length = max(0.02, min(abs(linear) * self.linear_scale, 1.5))
        direction = -1.0 if linear < 0.0 else 1.0  # retroceso → flecha apunta hacia atrás (−X)
        end_x = direction * length
        # Desviación lateral de la punta proporcional a angular.z; límite ±0.35 m visual
        end_y = origin_y + max(-0.35, min(angular * 0.35, 0.35))
        marker.points = [_point(0.0, origin_y, 0.18), _point(end_x, end_y, 0.18)]
        marker.scale.x = 0.05
        marker.scale.y = 0.09
        marker.scale.z = 0.12
        marker.color.a = 0.95
        marker.color.r, marker.color.g, marker.color.b = rgb
        return marker

    def _tick(self) -> None:
        """Construye y publica el MarkerArray completo con el estado del gate, la señal de stop y las flechas de cmd_vel."""
        markers = MarkerArray()

        # Referencia visual grande y fija en el origen para que RViz muestre
        # algo claro incluso cuando no hay cmd_vel ni stop activos.
        markers.markers.append(
            self._make_cube_marker(0, 0.0, 0.0, 0.05, (0.15, 0.55, 1.0), (0.45, 0.45, 0.10))
        )
        markers.markers.append(
            self._make_text_marker(
                1,
                0.0,
                0.0,
                0.22,
                "vision_safety origin",
                (0.7, 0.9, 1.0),
                0.10,
            )
        )

        # Color del estado del gate: rojo=bloqueado, verde=libre, amarillo=degradado/sin señal
        state_rgb = (0.9, 0.2, 0.2) if self._gate_blocked else (0.2, 0.8, 0.2)
        if self._gate_degraded and not self._gate_blocked:
            state_rgb = (1.0, 0.8, 0.2)  # amarillo: señal de estado obsoleta o con error

        markers.markers.append(self._make_sphere_marker(2, 0.0, 0.0, 0.65, state_rgb))
        markers.markers.append(
            self._make_text_marker(
                3,
                0.0,
                0.0,
                0.92,
                f"gate: {'BLOCKED' if self._gate_blocked else 'PASS'} | {self._gate_reason}",
                state_rgb,
                0.12,
            )
        )

        # Indicador de señal de stop: rojo=stop activo (fusión detectó peligro), verde=libre
        stop_rgb = (0.95, 0.15, 0.15) if self._last_vision_stop else (0.3, 0.9, 0.3)
        markers.markers.append(self._make_sphere_marker(4, 0.0, 0.38, 0.5, stop_rgb, 0.12))
        markers.markers.append(
            self._make_text_marker(
                5,
                0.0,
                0.38,
                0.68,
                f"vision_stop={self._last_vision_stop}",
                stop_rgb,
                0.10,
            )
        )

        markers.markers.append(
            self._make_arrow_marker(6, 0.32, self._last_input_cmd, (1.0, 0.55, 0.15))
        )
        markers.markers.append(
            self._make_text_marker(
                7,
                0.0,
                0.32,
                0.34,
                "cmd_vel_safe",
                (1.0, 0.75, 0.3),
                0.09,
            )
        )

        markers.markers.append(
            self._make_arrow_marker(8, -0.32, self._last_output_cmd, (0.2, 0.6, 1.0))
        )
        markers.markers.append(
            self._make_text_marker(
                9,
                0.0,
                -0.32,
                0.34,
                "cmd_vel_final",
                (0.4, 0.8, 1.0),
                0.09,
            )
        )

        markers.markers.append(
            self._make_text_marker(
                10,
                0.0,
                -0.65,
                0.18,
                (
                    f"in vx={self._last_input_cmd.linear.x:.2f} wz={self._last_input_cmd.angular.z:.2f} | "
                    f"out vx={self._last_output_cmd.linear.x:.2f} wz={self._last_output_cmd.angular.z:.2f}"
                ),
                (0.95, 0.95, 0.95),
                0.08,
            )
        )

        self._markers_pub.publish(markers)
        self._compat_markers_pub.publish(markers)


def main(args: Optional[list[str]] = None) -> None:
    """Punto de entrada del nodo: inicializa rclpy, crea el nodo de visualización y lo mantiene en spin hasta interrupción."""
    rclpy.init(args=args)
    node = VisionSafetyVizNode()
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
