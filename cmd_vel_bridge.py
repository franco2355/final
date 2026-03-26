#!/usr/bin/env python3
"""
Bridge: reenvía /cmd_vel_teleop (local) a /cmd_vel_safe (Cuatri) vía SSH
"""
import subprocess
import json
import threading
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class CmdVelBridge(Node):
    def __init__(self):
        super().__init__("cmd_vel_bridge")

        self.cuatri_ip = "100.111.4.7"
        self.cuatri_user = "salus"
        self.cuatri_pass = "teamcit2024"

        self._sub = self.create_subscription(
            Twist, "/cmd_vel_teleop", self._on_cmd_vel, 10
        )

        self.get_logger().info(f"Bridge iniciado → {self.cuatri_ip}")

    def _on_cmd_vel(self, msg: Twist) -> None:
        """Envía comando al Cuatri vía SSH"""
        linear_x = msg.linear.x
        angular_z = msg.angular.z

        # Publicar en el Cuatri via SSH + docker exec
        cmd = (
            f'sshpass -p "{self.cuatri_pass}" ssh -o StrictHostKeyChecking=accept-new '
            f'{self.cuatri_user}@{self.cuatri_ip} '
            f'"docker exec ros2 bash -c \\"source /ros2_ws/install/setup.bash && '
            f'ros2 topic pub -1 /cmd_vel_safe geometry_msgs/msg/Twist '
            f'\'{{\\"linear\\": {{\\"x\\": {linear_x}, \\"y\\": 0.0, \\"z\\": 0.0}}, '
            f'\\"angular\\": {{\\"x\\": 0.0, \\"y\\": 0.0, \\"z\\": {angular_z}}}}}\'\\""\n'
        )

        # Ejecutar en thread para no bloquear
        threading.Thread(target=lambda: subprocess.run(cmd, shell=True, capture_output=True)).start()


def main():
    rclpy.init()
    node = CmdVelBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
