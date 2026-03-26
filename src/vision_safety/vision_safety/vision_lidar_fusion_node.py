#!/usr/bin/env python3
"""Approximate camera-LiDAR fusion for local prototyping."""

from __future__ import annotations

import json
import math
import time
from typing import Any, Optional

import rclpy
from geometry_msgs.msg import Point
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String
from vision_msgs.msg import Detection2D, Detection2DArray
from visualization_msgs.msg import Marker, MarkerArray


def _stamp_to_s(sec: int, nanosec: int) -> float:
    """Convierte un timestamp ROS2 (segundos + nanosegundos) a un único valor flotante en segundos."""
    return float(sec) + float(nanosec) * 1e-9


def _safe_float(value: float, default: float = 0.0) -> float:
    """Convierte value a float de forma segura; retorna default si la conversión falla."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class VisionLidarFusionNode(Node):
    """Fuse 2D detections with LaserScan ranges using a camera FOV approximation."""

    def __init__(self) -> None:
        """Inicializa el nodo de fusión, declara todos los parámetros y crea publicadores, suscriptores y el timer."""
        super().__init__("vision_lidar_fusion")

        # Este MVP asume camara frontal aproximadamente alineada con el LiDAR:
        # usa el centro horizontal de cada bbox para elegir un sector del scan.
        self.declare_parameter("detections_topic", "/vision/detections")
        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("fused_objects_topic", "/vision/fused_objects")
        self.declare_parameter("fusion_status_topic", "/vision/fusion/status")
        self.declare_parameter("confirmed_stop_topic", "/vision/fused_stop_active")
        self.declare_parameter("fused_markers_topic", "/vision/fused_markers")
        self.declare_parameter("compat_markers_topic", "/visualization_marker_array")
        self.declare_parameter("output_frame_id", "map")
        self.declare_parameter("publish_hz", 5.0)
        self.declare_parameter("pairing_slop_s", 0.20)
        self.declare_parameter("image_width_px", 1280.0)
        self.declare_parameter("camera_hfov_deg", 90.0)
        self.declare_parameter("min_sector_deg", 6.0)
        self.declare_parameter("sector_padding_deg", 2.0)
        self.declare_parameter("min_range_m", 0.20)
        self.declare_parameter("max_range_m", 20.0)
        self.declare_parameter("min_lidar_samples", 2)
        self.declare_parameter("stop_distance_m", 2.5)
        self.declare_parameter(
            "dangerous_classes",
            ["person", "car", "vehicle", "bicycle", "motorcycle", "truck"],
        )

        self.detections_topic = str(self.get_parameter("detections_topic").value)
        self.scan_topic = str(self.get_parameter("scan_topic").value)
        self.fused_objects_topic = str(self.get_parameter("fused_objects_topic").value)
        self.fusion_status_topic = str(self.get_parameter("fusion_status_topic").value)
        self.confirmed_stop_topic = str(self.get_parameter("confirmed_stop_topic").value)
        self.fused_markers_topic = str(self.get_parameter("fused_markers_topic").value)
        self.compat_markers_topic = str(
            self.get_parameter("compat_markers_topic").value
        )
        self.output_frame_id = str(self.get_parameter("output_frame_id").value)
        self.publish_hz = max(1.0, _safe_float(self.get_parameter("publish_hz").value, 5.0))
        self.pairing_slop_s = max(
            0.01, _safe_float(self.get_parameter("pairing_slop_s").value, 0.20)
        )
        self.image_width_px = max(
            16.0, _safe_float(self.get_parameter("image_width_px").value, 1280.0)
        )
        self.camera_hfov_deg = max(
            10.0, _safe_float(self.get_parameter("camera_hfov_deg").value, 90.0)
        )
        self.min_sector_deg = max(
            1.0, _safe_float(self.get_parameter("min_sector_deg").value, 6.0)
        )
        self.sector_padding_deg = max(
            0.0, _safe_float(self.get_parameter("sector_padding_deg").value, 2.0)
        )
        self.min_range_m = max(
            0.01, _safe_float(self.get_parameter("min_range_m").value, 0.20)
        )
        self.max_range_m = max(
            self.min_range_m,
            _safe_float(self.get_parameter("max_range_m").value, 20.0),
        )
        self.min_lidar_samples = max(
            1, int(self.get_parameter("min_lidar_samples").value)
        )
        self.stop_distance_m = max(
            0.1, _safe_float(self.get_parameter("stop_distance_m").value, 2.5)
        )
        self.dangerous_classes = {
            str(item).strip().lower()
            for item in self.get_parameter("dangerous_classes").value
            if str(item).strip()
        }

        self._last_detections_msg: Optional[Detection2DArray] = None
        self._last_scan_msg: Optional[LaserScan] = None
        self._last_detections_stamp_s: Optional[float] = None
        self._last_scan_stamp_s: Optional[float] = None
        self._last_summary: dict[str, Any] = {
            "state": "waiting_for_inputs",
            "objects": [],
            "pairing_delta_s": None,
            "stop_active": False,
            "updated_at_monotonic_s": time.monotonic(),
        }

        self._summary_pub = self.create_publisher(String, self.fused_objects_topic, 10)
        self._status_pub = self.create_publisher(String, self.fusion_status_topic, 10)
        self._stop_pub = self.create_publisher(Bool, self.confirmed_stop_topic, 10)
        self._markers_pub = self.create_publisher(MarkerArray, self.fused_markers_topic, 10)
        self._compat_markers_pub = self.create_publisher(
            MarkerArray, self.compat_markers_topic, 10
        )
        self.create_subscription(
            Detection2DArray,
            self.detections_topic,
            self._on_detections,
            qos_profile_sensor_data,
        )
        self.create_subscription(
            LaserScan, self.scan_topic, self._on_scan, qos_profile_sensor_data
        )
        self.create_timer(1.0 / self.publish_hz, self._tick)

        self.get_logger().info(
            "vision_lidar_fusion ready "
            f"(detections={self.detections_topic}, scan={self.scan_topic}, "
            f"stop={self.confirmed_stop_topic}, frame={self.output_frame_id})"
        )

    def _on_detections(self, msg: Detection2DArray) -> None:
        """Almacena el último mensaje de detecciones y dispara un intento de fusión inmediato."""
        self._last_detections_msg = msg
        self._last_detections_stamp_s = _stamp_to_s(
            msg.header.stamp.sec, msg.header.stamp.nanosec
        )
        self._maybe_fuse()

    def _on_scan(self, msg: LaserScan) -> None:
        """Almacena el último LaserScan recibido y dispara un intento de fusión inmediato."""
        self._last_scan_msg = msg
        self._last_scan_stamp_s = _stamp_to_s(
            msg.header.stamp.sec, msg.header.stamp.nanosec
        )
        self._maybe_fuse()

    def _best_hypothesis(self, detection: Detection2D) -> tuple[str, float]:
        """Retorna el class_id y score de la hipótesis con mayor puntuación de una detección dada."""
        if not detection.results:
            return "unknown", 0.0
        best = max(detection.results, key=lambda item: float(item.hypothesis.score))
        class_id = str(best.hypothesis.class_id).strip() or "unknown"
        return class_id, float(best.hypothesis.score)

    def _scan_samples_for_detection(
        self, detection: Detection2D, scan: LaserScan
    ) -> tuple[list[tuple[int, float]], float, float]:
        """Calcula el sector angular del LiDAR correspondiente al bbox de una detección y retorna las muestras válidas junto con el ángulo central y el ancho del sector."""
        center_x_px = _safe_float(detection.bbox.center.position.x)
        width_px = max(1.0, _safe_float(detection.bbox.size_x, 1.0))

        # Normaliza posición horizontal del bbox a [-0.5, 0.5] y convierte a ángulo horizontal
        center_ratio = max(-0.5, min(0.5, (center_x_px / self.image_width_px) - 0.5))
        center_angle_deg = center_ratio * self.camera_hfov_deg  # ángulo central del objeto en grados
        # El ancho angular del sector es proporcional al bbox; mínimo min_sector_deg + padding bilateral
        sector_width_deg = max(
            self.min_sector_deg,
            (width_px / self.image_width_px) * self.camera_hfov_deg
            + (2.0 * self.sector_padding_deg),
        )

        # Convertir sector a radianes y recortar a los límites angulares del LiDAR
        sector_min_rad = math.radians(center_angle_deg - (sector_width_deg * 0.5))
        sector_max_rad = math.radians(center_angle_deg + (sector_width_deg * 0.5))
        sector_min_rad = max(scan.angle_min, sector_min_rad)  # no exceder ángulo mínimo del sensor
        sector_max_rad = min(scan.angle_max, sector_max_rad)  # no exceder ángulo máximo del sensor
        if sector_min_rad > sector_max_rad or abs(scan.angle_increment) < 1e-9:
            return [], center_angle_deg, sector_width_deg  # sector fuera del FOV del LiDAR

        # Convertir ángulos (rad) a índices del array ranges[]
        start_index = max(
            0, int(math.floor((sector_min_rad - scan.angle_min) / scan.angle_increment))
        )
        end_index = min(
            len(scan.ranges) - 1,
            int(math.ceil((sector_max_rad - scan.angle_min) / scan.angle_increment)),
        )

        valid_samples: list[tuple[int, float]] = []
        for index in range(start_index, end_index + 1):
            rng = float(scan.ranges[index])
            if not math.isfinite(rng):
                continue
            if rng < self.min_range_m or rng > self.max_range_m:
                continue
            valid_samples.append((index, rng))
        return valid_samples, center_angle_deg, sector_width_deg

    def _fuse_detection(self, detection: Detection2D, scan: LaserScan) -> dict[str, Any]:
        """Fusiona una detección 2D con el LaserScan y retorna un diccionario con clase, distancia LiDAR y flag de peligro."""
        class_id, score = self._best_hypothesis(detection)
        valid_samples, center_angle_deg, sector_width_deg = self._scan_samples_for_detection(
            detection, scan
        )

        summary: dict[str, Any] = {
            "detection_id": str(detection.id),
            "class_id": class_id,
            "score": round(score, 4),
            "bbox_center_x_px": round(
                _safe_float(detection.bbox.center.position.x), 2
            ),
            "bbox_width_px": round(_safe_float(detection.bbox.size_x), 2),
            "camera_angle_deg": round(center_angle_deg, 2),
            "sector_width_deg": round(sector_width_deg, 2),
            "lidar_confirmed": False,
            "lidar_sample_count": len(valid_samples),
            "distance_m": None,
            "scan_angle_deg": None,
            "dangerous_class": class_id.strip().lower() in self.dangerous_classes,
        }

        if len(valid_samples) < self.min_lidar_samples:
            return summary

        # Tomar la muestra más cercana del sector (peor caso = obstáculo más próximo)
        nearest_index, nearest_range = min(valid_samples, key=lambda item: item[1])
        nearest_angle_rad = scan.angle_min + (nearest_index * scan.angle_increment)  # índice → ángulo
        summary["lidar_confirmed"] = True
        summary["distance_m"] = round(nearest_range, 3)
        summary["scan_angle_deg"] = round(math.degrees(nearest_angle_rad), 2)
        return summary

    def _maybe_fuse(self) -> None:
        """Intenta fusionar detecciones y scan actuales si ambos están disponibles y sus timestamps son suficientemente cercanos."""
        if self._last_detections_msg is None or self._last_detections_stamp_s is None:
            self._last_summary = {
                "state": "waiting_for_detections",
                "objects": [],
                "pairing_delta_s": None,
                "stop_active": False,
                "updated_at_monotonic_s": time.monotonic(),
            }
            return
        if self._last_scan_msg is None or self._last_scan_stamp_s is None:
            self._last_summary = {
                "state": "waiting_for_scan",
                "objects": [],
                "pairing_delta_s": None,
                "stop_active": False,
                "updated_at_monotonic_s": time.monotonic(),
            }
            return

        # Verificar sincronía temporal: detecciones y scan deben tener timestamps cercanos
        pairing_delta_s = abs(self._last_detections_stamp_s - self._last_scan_stamp_s)
        if pairing_delta_s > self.pairing_slop_s:
            self._last_summary = {
                "state": "out_of_sync",
                "objects": [],
                "pairing_delta_s": round(pairing_delta_s, 4),
                "stop_active": False,
                "updated_at_monotonic_s": time.monotonic(),
            }
            return

        fused_objects = [
            self._fuse_detection(detection, self._last_scan_msg)
            for detection in self._last_detections_msg.detections
        ]
        # stop_active: True si al menos un objeto peligroso está confirmado por LiDAR dentro del umbral
        stop_active = any(
            obj["lidar_confirmed"]
            and obj["dangerous_class"]
            and obj["distance_m"] is not None
            and float(obj["distance_m"]) <= self.stop_distance_m
            for obj in fused_objects
        )

        self._last_summary = {
            "state": "paired",
            "scan_topic": self.scan_topic,
            "detections_topic": self.detections_topic,
            "pairing_delta_s": round(pairing_delta_s, 4),
            "detections_count": len(self._last_detections_msg.detections),
            "objects": fused_objects,
            "stop_active": stop_active,
            "updated_at_monotonic_s": time.monotonic(),
        }

    def _summary_payload(self) -> str:
        """Serializa el resumen de fusión actual a una cadena JSON compacta."""
        return json.dumps(self._last_summary, separators=(",", ":"), sort_keys=True)

    def _make_marker(self, marker_id: int, marker_type: int, ns: str) -> Marker:
        """Crea y retorna un Marker base con frame_id, timestamp, namespace e id configurados."""
        marker = Marker()
        marker.header.frame_id = self.output_frame_id
        marker.header.stamp = self.get_clock().now().to_msg()
        marker.ns = ns
        marker.id = marker_id
        marker.type = marker_type
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.color.a = 1.0
        return marker

    def _build_markers(self) -> MarkerArray:
        """Construye y retorna un MarkerArray con el estado de fusión y una esfera por cada objeto confirmado por LiDAR."""
        markers = MarkerArray()

        delete_all = Marker()
        delete_all.action = Marker.DELETEALL
        markers.markers.append(delete_all)

        status_rgb = (0.2, 0.8, 0.2)
        state = str(self._last_summary.get("state", "unknown"))
        if state == "out_of_sync":
            status_rgb = (1.0, 0.8, 0.2)
        elif state != "paired":
            status_rgb = (0.9, 0.3, 0.3)

        status_marker = self._make_marker(0, Marker.TEXT_VIEW_FACING, "vision_fusion_text")
        status_marker.pose.position = Point(x=0.0, y=0.0, z=0.55)
        status_marker.scale.z = 0.16
        status_marker.color.r, status_marker.color.g, status_marker.color.b = status_rgb
        status_marker.text = (
            f"fusion={state} | delta={self._last_summary.get('pairing_delta_s')} s | "
            f"stop={self._last_summary.get('stop_active')}"
        )
        markers.markers.append(status_marker)

        for index, obj in enumerate(self._last_summary.get("objects", []), start=1):
            if not obj.get("lidar_confirmed"):
                continue

            distance_m = float(obj["distance_m"])
            angle_deg = float(obj["scan_angle_deg"])
            angle_rad = math.radians(angle_deg)
            # Convertir coordenadas polares (distancia, ángulo) a cartesianas en el frame del mapa
            x = distance_m * math.cos(angle_rad)
            y = distance_m * math.sin(angle_rad)

            is_danger = bool(obj.get("dangerous_class")) and (
                distance_m <= self.stop_distance_m
            )
            color = (0.95, 0.2, 0.2) if is_danger else (0.2, 0.7, 1.0)

            sphere = self._make_marker(index * 2, Marker.SPHERE, "vision_fusion_state")
            sphere.pose.position = Point(x=x, y=y, z=0.18)
            sphere.scale.x = 0.22
            sphere.scale.y = 0.22
            sphere.scale.z = 0.22
            sphere.color.a = 0.9
            sphere.color.r, sphere.color.g, sphere.color.b = color
            markers.markers.append(sphere)

            text = self._make_marker(index * 2 + 1, Marker.TEXT_VIEW_FACING, "vision_fusion_text")
            text.pose.position = Point(x=x, y=y, z=0.42)
            text.scale.z = 0.12
            text.color.r, text.color.g, text.color.b = color
            text.text = (
                f"{obj['class_id']} | {distance_m:.2f} m | "
                f"cam={obj['camera_angle_deg']} deg"
            )
            markers.markers.append(text)

        return markers

    def _tick(self) -> None:
        """Publica periódicamente el resumen de fusión, el estado, la señal de stop y los markers en todos los tópicos de salida."""
        # Exposa una salida constante para que el debug no dependa de que lleguen
        # mensajes justo en el momento en que abrimos RViz o hacemos echo.
        summary_json = self._summary_payload()

        summary_msg = String()
        summary_msg.data = summary_json
        self._summary_pub.publish(summary_msg)

        status_msg = String()
        status_msg.data = str(self._last_summary.get("state", "unknown"))
        self._status_pub.publish(status_msg)

        stop_msg = Bool()
        stop_msg.data = bool(self._last_summary.get("stop_active", False))
        self._stop_pub.publish(stop_msg)

        markers = self._build_markers()
        self._markers_pub.publish(markers)
        self._compat_markers_pub.publish(markers)


def main(args: Optional[list[str]] = None) -> None:
    """Punto de entrada del nodo: inicializa rclpy, crea el nodo de fusión y lo mantiene en spin hasta interrupción."""
    rclpy.init(args=args)
    node = VisionLidarFusionNode()
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
