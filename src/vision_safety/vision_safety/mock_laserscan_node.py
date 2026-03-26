#!/usr/bin/env python3
"""Publish a synthetic LaserScan for local fusion demos."""

from __future__ import annotations

import math
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan


class MockLaserScanNode(Node):
    """Generate a simple frontal obstacle in a synthetic LaserScan."""

    def __init__(self) -> None:
        """Inicializa el nodo, declara los parámetros de geometría del scan sintético y crea el publicador y el timer."""
        super().__init__("mock_laserscan")

        self.declare_parameter("output_topic", "/scan")
        self.declare_parameter("publish_hz", 10.0)
        self.declare_parameter("frame_id", "map")
        self.declare_parameter("angle_min_rad", -1.57079632679)
        self.declare_parameter("angle_max_rad", 1.57079632679)
        self.declare_parameter("angle_increment_rad", 0.00872664626)
        self.declare_parameter("range_min_m", 0.2)
        self.declare_parameter("range_max_m", 20.0)
        self.declare_parameter("background_range_m", 10.0)
        self.declare_parameter("obstacle_distance_m", 1.5)
        self.declare_parameter("obstacle_angle_deg", 0.0)
        self.declare_parameter("obstacle_width_deg", 12.0)

        self.output_topic = str(self.get_parameter("output_topic").value)
        self.publish_hz = max(1.0, float(self.get_parameter("publish_hz").value))
        self.frame_id = str(self.get_parameter("frame_id").value)
        self.angle_min = float(self.get_parameter("angle_min_rad").value)
        self.angle_max = float(self.get_parameter("angle_max_rad").value)
        self.angle_increment = max(
            1e-4, float(self.get_parameter("angle_increment_rad").value)
        )
        self.range_min = max(0.01, float(self.get_parameter("range_min_m").value))
        self.range_max = max(
            self.range_min, float(self.get_parameter("range_max_m").value)
        )
        self.background_range = min(
            self.range_max,
            max(self.range_min, float(self.get_parameter("background_range_m").value)),
        )
        self.obstacle_distance = min(
            self.range_max,
            max(self.range_min, float(self.get_parameter("obstacle_distance_m").value)),
        )
        self.obstacle_angle_deg = float(self.get_parameter("obstacle_angle_deg").value)
        self.obstacle_width_deg = max(
            1.0, float(self.get_parameter("obstacle_width_deg").value)
        )

        self._pub = self.create_publisher(
            LaserScan, self.output_topic, qos_profile_sensor_data
        )
        self.create_timer(1.0 / self.publish_hz, self._tick)

        self.get_logger().info(
            "mock_laserscan ready "
            f"(topic={self.output_topic}, obstacle={self.obstacle_distance}m @ {self.obstacle_angle_deg}deg)"
        )

    def _tick(self) -> None:
        """Genera y publica un LaserScan sintético con fondo uniforme y un obstáculo en el sector configurado."""
        scan = LaserScan()
        scan.header.stamp = self.get_clock().now().to_msg()
        scan.header.frame_id = self.frame_id
        scan.angle_min = self.angle_min
        scan.angle_max = self.angle_max
        scan.angle_increment = self.angle_increment
        scan.scan_time = 1.0 / self.publish_hz
        scan.time_increment = 0.0
        scan.range_min = self.range_min
        scan.range_max = self.range_max

        # Número de rayos = rango angular / incremento + 1 (incluye ambos extremos del arco)
        sample_count = int(round((self.angle_max - self.angle_min) / self.angle_increment)) + 1
        scan.ranges = [self.background_range] * max(1, sample_count)  # inicializar fondo sin obstáculos

        # Calcular el rango de índices que cubre el obstáculo sintético en el sector frontal
        center_rad = math.radians(self.obstacle_angle_deg)
        half_width_rad = math.radians(self.obstacle_width_deg * 0.5)
        start_idx = max(
            0,
            int(math.floor((center_rad - half_width_rad - self.angle_min) / self.angle_increment)),
        )
        end_idx = min(
            len(scan.ranges) - 1,
            int(math.ceil((center_rad + half_width_rad - self.angle_min) / self.angle_increment)),
        )
        # Sobreescribir los rayos del sector con la distancia del obstáculo sintético
        for index in range(start_idx, end_idx + 1):
            scan.ranges[index] = self.obstacle_distance

        self._pub.publish(scan)


def main(args: Optional[list[str]] = None) -> None:
    """Punto de entrada del nodo: inicializa rclpy, crea el nodo de LaserScan sintético y lo mantiene en spin hasta interrupción."""
    rclpy.init(args=args)
    node = MockLaserScanNode()
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
