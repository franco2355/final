#!/usr/bin/env python3
"""Publish synthetic Detection2DArray messages for local fusion tests."""

from __future__ import annotations

from typing import Optional

import rclpy
from rclpy.node import Node
from vision_msgs.msg import BoundingBox2D, Detection2D, Detection2DArray, ObjectHypothesisWithPose


class MockDetectionsNode(Node):
    """Small helper to drive the fusion pipeline before the real detector exists."""

    def __init__(self) -> None:
        """Inicializa el nodo, declara los parámetros configurables y crea el publicador y el timer de publicación."""
        super().__init__("mock_detections")

        self.declare_parameter("output_topic", "/vision/detections")
        self.declare_parameter("publish_hz", 5.0)
        self.declare_parameter("image_frame_id", "camera")
        self.declare_parameter("class_id", "person")
        self.declare_parameter("score", 0.95)
        self.declare_parameter("detection_id", "mock_front_object")
        self.declare_parameter("bbox_center_x_px", 640.0)
        self.declare_parameter("bbox_center_y_px", 360.0)
        self.declare_parameter("bbox_width_px", 240.0)
        self.declare_parameter("bbox_height_px", 360.0)

        self.output_topic = str(self.get_parameter("output_topic").value)
        self.publish_hz = max(1.0, float(self.get_parameter("publish_hz").value))
        self.image_frame_id = str(self.get_parameter("image_frame_id").value)
        self.class_id = str(self.get_parameter("class_id").value)
        self.score = max(0.0, min(1.0, float(self.get_parameter("score").value)))
        self.detection_id = str(self.get_parameter("detection_id").value)
        self.bbox_center_x_px = float(self.get_parameter("bbox_center_x_px").value)
        self.bbox_center_y_px = float(self.get_parameter("bbox_center_y_px").value)
        self.bbox_width_px = max(1.0, float(self.get_parameter("bbox_width_px").value))
        self.bbox_height_px = max(
            1.0, float(self.get_parameter("bbox_height_px").value)
        )

        self._pub = self.create_publisher(Detection2DArray, self.output_topic, 10)
        self.create_timer(1.0 / self.publish_hz, self._tick)

        self.get_logger().info(
            "mock_detections ready "
            f"(topic={self.output_topic}, class={self.class_id}, center_x={self.bbox_center_x_px})"
        )

    def _tick(self) -> None:
        """Construye y publica un Detection2DArray con una única detección frontal sintética en cada ciclo del timer."""
        # Construir un Detection2DArray con una única detección frontal sintética
        msg = Detection2DArray()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.image_frame_id

        detection = Detection2D()
        detection.header = msg.header  # mismo timestamp que el array padre para sincronía
        detection.id = self.detection_id

        # Hipótesis de clasificación: clase y confianza configurables por parámetro
        result = ObjectHypothesisWithPose()
        result.hypothesis.class_id = self.class_id
        result.hypothesis.score = self.score
        detection.results.append(result)

        # Bounding box en coordenadas de píxel (centro + tamaño)
        bbox = BoundingBox2D()
        bbox.center.position.x = self.bbox_center_x_px
        bbox.center.position.y = self.bbox_center_y_px
        bbox.size_x = self.bbox_width_px
        bbox.size_y = self.bbox_height_px
        detection.bbox = bbox

        msg.detections.append(detection)
        self._pub.publish(msg)


def main(args: Optional[list[str]] = None) -> None:
    """Punto de entrada del nodo: inicializa rclpy, crea el nodo de detecciones sintéticas y lo mantiene en spin hasta interrupción."""
    rclpy.init(args=args)
    node = MockDetectionsNode()
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
