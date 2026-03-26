# aeye-ros-workspace

Workspace ROS 2 Humble para el robot Salus, un cuatriciclo grande de patrullaje autonomo con direccion Ackermann, navegacion GPS, LiDAR RoboSense, Pixhawk y una consola web para zonas de exclusion, teleoperacion y estado de navegacion.

Este README intenta explicar el estado actual del codigo fuente de `src/` y de los scripts del workspace. La idea es que sirva como documento de referencia tecnica del proyecto, no solo como guia rapida.

## 1. Que es este repo

Este workspace junta varias capas del sistema:

- simulacion en Gazebo Sim (`ros_gz`)
- localizacion con `robot_localization`
- navegacion con Nav2
- drivers de sensores reales
- backend ROS 2 para consola web
- control real de actuadores por UART hacia ESP32
- una capa experimental de seguridad por vision + LiDAR

No es una sola aplicacion monolitica. Es un grafo de nodos ROS 2 distribuidos en varios paquetes.

## 2. Estado actual y fuente de verdad

Hay documentacion vieja en el repo que menciona launches y nodos que ya no existen. Para entender el sistema actual, la fuente de verdad es:

- los paquetes en `src/`
- los launches existentes en `src/*/launch/`
- este README

En particular, hoy los entry points principales que existen realmente en el arbol fuente son:

- `ros2 launch navegacion_gps simulacion.launch.py`
- `ros2 launch navegacion_gps real.launch.py`
- `ros2 launch navegacion_gps rviz_real.launch.py`
- `ros2 launch sensores pixhawk.launch.py`
- `ros2 launch sensores rs16.launch.py`
- `ros2 launch map_tools no_go_editor.launch.py`
- `ros2 launch controller_server controller_server.launch.py`
- `ros2 launch vision_safety vision_safety_passive.launch.py`
- `ros2 launch vision_safety vision_safety_simulation_passive.launch.py`
- `ros2 launch vision_safety vision_safety_simulation_gate.launch.py`

## 3. Estructura general del workspace

### 3.1 Root del workspace

- `docker-compose.yml`
  define el contenedor principal `ros2`, con red `host`, modo `privileged`, montaje de `src`, `build`, `install`, `log`, `tools` y acceso a `/dev`
- `Dockerfile`
  construye la imagen base con ROS 2 Humble, Nav2, robot_localization, ros_gz, RViz, MAVROS, pointcloud_to_laserscan y dependencias Python del proyecto
- `entrypoint.sh`
  hace `source` de `/opt/ros/humble/setup.bash` y de `/ros2_ws/install/setup.bash`
- `tools/`
  wrappers para compilar, abrir shell en el contenedor, levantar navegacion real, lanzar RViz, probar LiDAR y ejecutar herramientas auxiliares
- `src/`
  codigo fuente real de los paquetes ROS 2
- `build/`, `install/`, `log/`
  artefactos de `colcon`

### 3.2 Paquetes en `src/`

- `navegacion_gps`
  orquestacion principal del stack, launches, configuracion Nav2/EKF, backend de navegacion, keepout y snapshots
- `navegacion_gps_interfaces`
  mensajes y servicios custom para la UI web y el backend de navegacion
- `sensores`
  Pixhawk por MAVLink, wrapper del LiDAR RS16 y servidor web de telemetria de sensores
- `map_tools`
  backend WebSocket para editar zonas no-go y mandar comandos desde la UI web
- `controller_server`
  control real por UART hacia ESP32; consume `/cmd_vel_safe`
- `vision_safety`
  fusion vision + LiDAR y gate experimental de velocidad
- `rslidar_sdk`
  driver C++ del LiDAR RoboSense
- `rslidar_msg`
  mensajes del driver RoboSense

## 4. Modelo mental del sistema

### 4.1 Flujo real

```text
Pixhawk (/imu/data, /gps/fix, /odom) ----\
                                          \
LiDAR (/scan_3d) --------------------------> robot_localization + Nav2
                                             |
                                             v
                                     collision_monitor
                                             |
                                             v
                                       /cmd_vel_safe
                                             |
                                             +--> controller_server --> UART --> ESP32
                                             |
                                             +--> backend web / telemetria / debug
```

### 4.2 Flujo de simulacion

```text
Gazebo Sim --> ros_gz_bridge --> topics *_raw --> frame_id_stripper --> /imu/data /gps/fix /odom /scan_3d
                                                                   |
                                                                   v
                                                          pointcloud_to_laserscan --> /scan
                                                                   |
                                                                   v
                                                      robot_localization + Nav2 + collision_monitor
                                                                   |
                                                                   v
                                                              /cmd_vel_safe
                                                                   |
                                                                   v
                                                         ros_gz_bridge --> /cmd_vel_steer
```

### 4.3 Flujo web

```text
Browser <--> WebSocket <--> map_tools/web_zone_server
                               |
                               +--> keepout_manager services
                               +--> nav_command_server services
                               +--> nav_snapshot_server service
                               +--> /cmd_vel_teleop
```

## 5. Capas funcionales del proyecto

### 5.1 Sensado

Los datos base del robot vienen de:

- Pixhawk:
  IMU, GPS y odometria local
- LiDAR RS16:
  nube 3D del entorno
- en simulacion:
  Gazebo publica esos datos virtuales y luego se bridguean a ROS

### 5.2 Normalizacion de frames

En simulacion algunos sensores salen con nombres de frame o namespaces que Nav2 y EKF no esperan. Para eso existe `frame_id_stripper.py`, que limpia topics `*_raw` y publica versiones "normalizadas".

### 5.3 Localizacion

La localizacion usa dos EKF y un `navsat_transform_node`.

- EKF odom:
  fusiona odometria base + IMU y produce `/odometry/local`
- navsat_transform:
  convierte GPS a odometria GPS usando IMU + odometria local
- EKF map:
  fusiona `/odometry/local` con `/odometry/gps` y sostiene el frame global `map`

### 5.4 Navegacion

Nav2 corre sin mapa estatico fijo. El planner y los costmaps usan:

- `/scan`
- TF `map -> odom -> base_footprint`
- footprint del robot
- una mascara keepout publicada por `keepout_manager`

### 5.5 Seguridad

Hay dos capas:

- `nav2_collision_monitor`
  capa actual y principal de seguridad en navegacion
- `vision_safety`
  capa experimental, sobre todo pensada para simulacion y pruebas de fusion vision + LiDAR

### 5.6 Backend web

La UI web no habla directo con Nav2. Habla con un backend ROS 2 (`web_zone_server.py`) que:

- consulta estado del robot
- manda goals GPS
- cancela goals
- activa freno
- alterna modo manual
- manda teleop
- sube o recarga zonas keepout
- pide snapshots del costmap

### 5.7 Actuacion real

La salida final del stack es `/cmd_vel_safe`.

En hardware real ese topic lo consume `controller_server`, que:

- recibe `Twist`
- lo traduce a velocidad, direccion y freno
- lo serializa en un protocolo binario UART
- lo manda al ESP32

## 6. Paquetes y archivos Python

Esta seccion enumera los `.py` relevantes del proyecto y explica que hace cada uno.

### 6.1 `navegacion_gps`

Paquete principal del stack.

#### Launches

- `src/navegacion_gps/launch/real.launch.py`
  launch principal para robot real. Arranca `robot_state_publisher`, Pixhawk opcional, LiDAR opcional, EKF, `navsat_transform`, Nav2, `keepout_manager`, `nav_command_server`, `nav_snapshot_server`, la pasarela web y, si corresponde, RViz o Mapviz.

- `src/navegacion_gps/launch/simulacion.launch.py`
  launch principal de simulacion. Levanta Gazebo Sim, `ros_gz_bridge`, spawn del robot, `frame_id_stripper`, `pointcloud_to_laserscan`, EKF, Nav2, `collision_monitor`, backend web y herramientas de visualizacion.

- `src/navegacion_gps/launch/rviz_real.launch.py`
  launch pequeño para ver el robot en RViz con el URDF real y `robot_state_publisher`, sin levantar el resto del stack.

#### Nodos Python

- `src/navegacion_gps/navegacion_gps/frame_id_stripper.py`
  nodo de normalizacion de `frame_id`.
  Consume:
  `/imu/data_raw`, `/gps/fix_raw`, `/scan_3d_raw`, `/odom_raw` y varios ultrasonidos `*_raw`.
  Publica:
  `/imu/data`, `/gps/fix`, `/scan_3d`, `/odom` y ultrasonidos limpios.

- `src/navegacion_gps/navegacion_gps/keepout_manager.py`
  backend de zonas no-go.
  Hace varias cosas:
  - lee zonas desde `config/no_go_zones.yaml`
  - acepta nuevas zonas por servicio
  - convierte poligonos lat/lon a XY usando `/fromLL`
  - rasteriza una mascara `OccupancyGrid`
  - publica `/keepout_filter_mask`
  - publica `/costmap_filter_info`
  - expone servicios para set/get/reload de zonas

- `src/navegacion_gps/navegacion_gps/keepout_mask_utils.py`
  utilidades puras usadas por `keepout_manager`.
  No es un nodo.
  Implementa:
  - rasterizacion de poligonos en una grilla
  - degradado de costo alrededor de las zonas keepout

- `src/navegacion_gps/navegacion_gps/nav_command_server.py`
  backend ROS 2 de comandos de navegacion.
  Hace de puente entre UI/web y Nav2.
  Sus funciones principales son:
  - recibir un goal GPS en lat/lon/yaw
  - convertirlo a `map` con `/fromLL`
  - enviar la action `NavigateToPose`
  - cancelar el goal actual
  - aplicar freno de emergencia
  - activar o desactivar modo manual
  - reenviar teleop manual a `/cmd_vel_safe`
  - publicar `NavTelemetry`

- `src/navegacion_gps/navegacion_gps/nav_snapshot_server.py`
  servicio que construye una imagen PNG del estado local de navegacion.
  Toma:
  costmap local, costmap global, mask keepout, footprint, stop zone, poligonos del collision monitor, scan y plan.
  Devuelve:
  una imagen PNG por servicio custom.

#### Soporte de paquete

- `src/navegacion_gps/setup.py`
  empaquetado del paquete.
  Instala launch/config/modelos/worlds y declara entry points.
  Ojo:
  todavia menciona entry points a archivos que hoy no existen (`teleop`, `gps_waypoint_logger`, `yaml_waypoints_from_ll`, `interactive_waypoint_follower`).

- `src/navegacion_gps/navegacion_gps/__init__.py`
  marcador de paquete Python; no tiene logica.

### 6.2 `navegacion_gps_interfaces`

No tiene `.py`, pero es clave porque define la interfaz entre backend y frontend.

#### Mensajes

- `NavTelemetry.msg`
  estado de goal activo, modo manual, ultimo comando, y posicion GPS del robot
- `NoGoPoint.msg`
  punto simple lat/lon
- `NoGoZone.msg`
  zona no-go con id, tipo, flag `enabled` y poligono
- `NavSnapshotLayers.msg`
  flags de capas presentes en un snapshot

#### Servicios

- `SetNavGoalLL.srv`
  mandar goal GPS
- `CancelNavGoal.srv`
  cancelar navegacion
- `BrakeNav.srv`
  freno
- `GetNavState.srv`
  estado actual de navegacion
- `SetManualMode.srv`
  activar/desactivar modo manual
- `SetManualCmd.srv`
  comando manual
- `SetKeepoutZones.srv`
  reemplazar zonas keepout
- `GetKeepoutState.srv`
  leer estado actual de zonas
- `GetNavSnapshot.srv`
  pedir PNG del entorno

### 6.3 `sensores`

Paquete de drivers y wrappers de sensores reales.

#### Launches

- `src/sensores/launch/pixhawk.launch.py`
  arranca `pixhawk_driver` y opcionalmente `sensores_web`.
  Expone argumentos para puerto serie, baudrate y nombres de frame.

- `src/sensores/launch/rs16.launch.py`
  wrapper del driver RS16 actual.
  Arranca `rslidar_sdk_node` y opcionalmente RViz.
  Este es el launch que usa el resto del proyecto.

#### Nodos Python

- `src/sensores/sensores/pixhawk_driver.py`
  nodo MAVLink -> ROS 2.
  Lee el Pixhawk por puerto serie.
  Convierte:
  - NED -> ENU
  - FRD -> FLU
  Publica:
  - `/imu/data`
  - `/gps/fix`
  - `/odom`
  - `/velocity`

- `src/sensores/sensores/web_server.py`
  servidor HTTP + WebSocket de telemetria de sensores.
  Sirve un HTML local y entrega snapshots JSON con IMU, GPS, velocidad y odometria.

#### Soporte de paquete

- `src/sensores/setup.py`
  instala `pixhawk_driver` y `sensores_web`.

- `src/sensores/sensores/__init__.py`
  marcador de paquete Python.

### 6.4 `map_tools`

Backend ROS 2 de la consola web.

#### Launches

- `src/map_tools/launch/no_go_editor.launch.py`
  arranca `web_zone_server` con nombres de servicios/topics configurables.

#### Nodos Python

- `src/map_tools/map_tools/web_zone_server.py`
  gateway WebSocket entre el navegador y ROS 2.
  Hace:
  - suscripcion a GPS y `NavTelemetry`
  - clientes a servicios de `keepout_manager`
  - clientes a servicios de `nav_command_server`
  - cliente al servicio `GetNavSnapshot`
  - publicacion de `Twist` para teleop manual
  - broadcast de estado y eventos a clientes WebSocket

#### Soporte de paquete

- `src/map_tools/setup.py`
  instala el backend y el contenido web.

- `src/map_tools/map_tools/__init__.py`
  marcador de paquete Python.

### 6.5 `controller_server`

Paquete de actuacion real por UART.

#### Launches

- `src/controller_server/launch/controller_server.launch.py`
  arranca `controller_server_node` con los parametros base del enlace UART y del mapeo de direccion.

#### Nodos Python

- `src/controller_server/controller_server/controller_server_node.py`
  nodo ROS 2 principal de actuacion.
  Consume:
  `/cmd_vel_safe`
  Publica:
  `/controller/status`
  `/controller/telemetry`
  Internamente usa `CommsClient` para hablar con el ESP32.

- `src/controller_server/controller_server/control_logic.py`
  logica pura de conversion de `Twist` a comando discreto.
  Implementa:
  - clamp de velocidad/direccion
  - activacion de estop cuando `linear.x == 0`
  - freno mecanico al parar
  - watchdog de freshness del comando

#### Submodulo UART `rpy_esp32_comms`

- `src/controller_server/controller_server/rpy_esp32_comms/controller.py`
  define `CommandState`, el estado deseado hacia el ESP32.

- `src/controller_server/controller_server/rpy_esp32_comms/protocol.py`
  define el protocolo binario UART Pi <-> ESP32:
  - encode de frame Pi -> ESP32
  - decode de frame ESP32 -> Pi
  - CRC8
  - parser streaming con resincronizacion

- `src/controller_server/controller_server/rpy_esp32_comms/telemetry.py`
  define el dataclass `Telemetry` y la interpretacion de bits de estado recibidos desde el ESP32.

- `src/controller_server/controller_server/rpy_esp32_comms/transport.py`
  implementa `CommsClient`.
  Abre el puerto serial y corre:
  - un hilo TX periodico
  - un hilo RX con parser de frames
  - locks de estado/telemetria/estadisticas

- `src/controller_server/controller_server/rpy_esp32_comms/cli.py`
  consola interactiva para testear el protocolo UART sin ROS 2.

- `src/controller_server/controller_server/rpy_esp32_comms/__main__.py`
  entry point para ejecutar la CLI como modulo.

- `src/controller_server/controller_server/rpy_esp32_comms/__init__.py`
  reexporta clases y funciones del submodulo UART.

#### Scripts y tests historicos del paquete

- `src/controller_server/controller_server/controller/artifacts/run_uart_e2e.py`
  script historico E2E que combina `CommsClient` con telnet al ESP32 y guarda evidencias en JSON/log.

- `src/controller_server/controller_server/controller/tests/test_controller.py`
  tests unitarios del `CommandState`.

- `src/controller_server/controller_server/controller/tests/test_protocol.py`
  tests del protocolo UART y del parser de frames.

#### Soporte de paquete

- `src/controller_server/setup.py`
  empaquetado del paquete; instala `controller_server_node`.

### 6.6 `vision_safety`

Capa experimental de fusion vision + LiDAR y gate de velocidad.

#### Launches

- `src/vision_safety/launch/vision_safety_passive.launch.py`
  arranca solo la fusion y mocks opcionales.
  Publica la senal de stop, pero no bloquea el movimiento.

- `src/vision_safety/launch/vision_safety_simulation_passive.launch.py`
  wrapper que arranca la simulacion normal y encima la capa de vision pasiva.

- `src/vision_safety/launch/vision_safety_simulation_gate.launch.py`
  wrapper activo:
  - arranca simulacion sin collision monitor base
  - levanta un collision monitor propio con salida `/cmd_vel_nav_safe`
  - levanta fusion vision + LiDAR
  - levanta un gate que puede detener o retroceder

#### Nodos Python

- `src/vision_safety/vision_safety/vision_lidar_fusion_node.py`
  fusion aproximada de `Detection2DArray` con `LaserScan`.
  Toma el centro horizontal del bbox, calcula un sector angular del LiDAR y busca la muestra valida mas cercana.
  Publica:
  - resumen JSON
  - estado JSON
  - Bool de stop confirmado
  - markers para RViz

- `src/vision_safety/vision_safety/cmd_vel_gate_node.py`
  gate de velocidad con maquina de estados:
  - `passthrough`
  - `stopping`
  - `reversing`
  - `wait_clear`
  Intercepta `cmd_vel` upstream y decide si lo deja pasar, lo anula o manda retroceso.

- `src/vision_safety/vision_safety/mock_detections_node.py`
  genera detecciones 2D sintéticas.

- `src/vision_safety/vision_safety/mock_laserscan_node.py`
  genera un `LaserScan` sintético con un obstaculo configurable.

- `src/vision_safety/vision_safety/vision_safety_viz_node.py`
  publica markers para RViz con el estado del gate y el flujo de velocidades.

#### Soporte de paquete

- `src/vision_safety/setup.py`
  empaquetado del paquete y declaracion de entry points.

- `src/vision_safety/vision_safety/__init__.py`
  marcador de paquete Python.

### 6.7 `rslidar_sdk`

El runtime principal del LiDAR viene del ejecutable C++ `rslidar_sdk_node`, no de Python. Los `.py` que hay aca son launches heredados del driver:

- `src/rslidar_sdk/launch/start.py`
  launch generico del driver con `config_path` vacio.

- `src/rslidar_sdk/launch/elequent_start.py`
  launch viejo usando una API antigua de ROS 2.

- `src/rslidar_sdk/launch/humble_start.py`
  launch heredado que intenta instalar Cyclone DDS si hace falta.
  No parece ser el camino canonico del proyecto actual.

## 7. Interfaces ROS 2 principales

### 7.1 Topics principales

#### Sensores y localizacion

- `/imu/data`
- `/gps/fix`
- `/odom`
- `/velocity`
- `/odometry/local`
- `/odometry/gps`
- `/scan_3d`
- `/scan`

#### Navegacion y seguridad

- `/cmd_vel_nav`
- `/cmd_vel_safe`
- `/collision_monitor_state`
- `/keepout_filter_mask`
- `/costmap_filter_info`
- `/plan`
- `/local_costmap/costmap`
- `/global_costmap/costmap`
- `/nav_command_server/telemetry`

#### Web y teleop

- `/cmd_vel_teleop`
- `/controller/status`
- `/controller/telemetry`

#### Vision safety

- `/vision/detections`
- `/vision/fused_objects`
- `/vision/fusion/status`
- `/vision/fused_stop_active`
- `/vision/fused_markers`
- `/vision_safety/gate/state`

### 7.2 Servicios principales

#### Keepout

- `/keepout_manager/set_zones`
- `/keepout_manager/get_state`
- `/keepout_manager/reload_zones`

#### Navegacion

- `/nav_command_server/set_goal_ll`
- `/nav_command_server/cancel_goal`
- `/nav_command_server/brake`
- `/nav_command_server/set_manual_mode`
- `/nav_command_server/get_state`

#### Snapshot

- `/nav_snapshot_server/get_nav_snapshot`

#### Geodesia

- `/fromLL`
- `/navsat_transform/fromLL`

### 7.3 Action principal

- `navigate_to_pose`
  action de Nav2 usada por `nav_command_server`

### 7.4 Frames TF

Frames esperados por el stack:

- `map`
- `odom`
- `base_footprint`
- `base_link`
- `imu_link`
- `gps_link`
- `lidar_link`

Arbol logico:

```text
map -> odom -> base_footprint -> base_link
```

## 8. Configuracion importante

### 8.1 `dual_ekf_navsat_params.yaml`

Define:

- frames de localizacion
- sensores usados por EKF
- `datum`
- comportamiento de `navsat_transform`

Archivo:

- `src/navegacion_gps/config/dual_ekf_navsat_params.yaml`

### 8.2 `nav2_no_map_params.yaml`

Define:

- planner
- controller
- behavior server
- costmaps
- footprint
- velocity smoother
- lifecycle manager

Archivo:

- `src/navegacion_gps/config/nav2_no_map_params.yaml`

### 8.3 `collision_monitor.yaml`

Define:

- poligonos de seguridad
- input/output de `cmd_vel`
- fuentes de observacion (`/scan` y ultrasonidos)

Archivo:

- `src/navegacion_gps/config/collision_monitor.yaml`

### 8.4 `bridge_config.yaml`

Solo aplica a simulacion.
Define el bridge ROS <-> Gazebo para:

- `/cmd_vel_safe` -> `/cmd_vel_steer`
- `/odom_raw`
- `/scan_3d_raw`
- `/imu/data_raw`
- `/gps/fix_raw`
- ultrasonidos raw

Archivo:

- `src/navegacion_gps/config/bridge_config.yaml`

## 9. Como correr el workspace

### 9.1 Flujo Docker recomendado

Levantar contenedor:

```bash
docker compose up -d --build
```

Compilar todo:

```bash
./tools/compile-ros.sh
```

Compilar paquetes puntuales:

```bash
./tools/compile-ros.sh navegacion_gps sensores controller_server map_tools vision_safety
```

Abrir shell:

```bash
./tools/exec.sh
```

### 9.2 Simulacion canonica

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch navegacion_gps simulacion.launch.py"
```

Con RViz:

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch navegacion_gps simulacion.launch.py use_rviz:=True"
```

### 9.3 Navegacion real

Wrapper existente:

```bash
./tools/launch_real_nav.sh
```

Equivalente:

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp; ros2 launch navegacion_gps real.launch.py"
```

### 9.4 RViz del robot real

Wrapper existente:

```bash
./tools/launch_real_rviz.sh
```

### 9.5 Actuador real por UART

Importante:
`real.launch.py` no levanta `controller_server`.
Si quieres el pipeline real completo, normalmente necesitas otra terminal con:

```bash
./tools/ws-bridge.sh
```

o equivalente:

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch controller_server controller_server.launch.py"
```

### 9.6 Pixhawk solo

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch sensores pixhawk.launch.py"
```

### 9.7 LiDAR solo

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch sensores rs16.launch.py"
```

### 9.8 Vision safety

Modo pasivo:

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch vision_safety vision_safety_simulation_passive.launch.py"
```

Modo gate:

```bash
./tools/exec.sh "source /opt/ros/humble/setup.bash; source /ros2_ws/install/setup.bash; ros2 launch vision_safety vision_safety_simulation_gate.launch.py"
```

## 10. Scripts utiles en `tools/`

- `tools/exec.sh`
  abre shell o ejecuta un comando dentro del contenedor

- `tools/compile-ros.sh`
  compila con `colcon` dentro del contenedor

- `tools/root-exec.sh`
  shell como root dentro del contenedor

- `tools/launch_real_nav.sh`
  wrapper para `real.launch.py`

- `tools/launch_real_rviz.sh`
  wrapper para `rviz_real.launch.py`

- `tools/ws-bridge.sh`
  wrapper para `controller_server.launch.py`

- `tools/healthcheck-lidar.sh`
  chequea rapidamente `/scan_3d`, `/scan` y TF

- `tools/closed_loop_step_publisher.py`
  prueba ROS de escalones de velocidad

- `tools/uart_step_sender.py`
  prueba directa de escalones UART

## 11. Entorno Docker

### 11.1 `docker-compose.yml`

Aspectos importantes:

- servicio principal `ros2`
- red `host`
- `privileged: true`
- acceso a `/dev`
- montaje de `src`, `build`, `install`, `log`, `tools`
- X11 habilitado para RViz/Mapviz
- servicio adicional `netdata`

### 11.2 `Dockerfile`

La imagen instala:

- ROS 2 Humble base (`ros:humble-perception`)
- Nav2 y robot_localization
- ros_gz
- RViz y herramientas ROS
- MAVROS
- pointcloud_to_laserscan
- Python deps como `numpy`, `websockets`, `pyserial`, `pymavlink`

Mapviz se instala solo en `amd64`. En ARM64 se omite.

### 11.3 `entrypoint.sh`

Hace `source` automatico de:

- `/opt/ros/humble/setup.bash`
- `/ros2_ws/install/setup.bash`

## 12. Secuencias de operacion

### 12.1 Simulacion completa

1. Gazebo publica sensores virtuales
2. `ros_gz_bridge` los trae a ROS 2 como topics raw
3. `frame_id_stripper` los normaliza
4. `pointcloud_to_laserscan` genera `/scan`
5. EKF y `navsat_transform` arman la localizacion
6. Nav2 planifica y controla
7. `collision_monitor` filtra velocidad
8. `/cmd_vel_safe` vuelve a Gazebo como `/cmd_vel_steer`

### 12.2 Robot real

1. `pixhawk_driver` publica IMU/GPS/odom
2. `rslidar_sdk_node` publica nube 3D
3. `pointcloud_to_laserscan` genera `/scan`
4. EKF + `navsat_transform` generan `/odometry/local` y `/odometry/gps`
5. Nav2 produce la velocidad de navegacion
6. `collision_monitor` la filtra
7. `controller_server` consume `/cmd_vel_safe`
8. `controller_server` la manda al ESP32 por UART

### 12.3 Consola web

1. el navegador se conecta a `web_zone_server` por WebSocket
2. la UI pide estado inicial
3. el backend consulta:
   - keepout state
   - nav state
   - robot pose
4. la UI puede:
   - dibujar zonas
   - pedir goals GPS
   - cancelar goal
   - frenar
   - activar modo manual
   - mandar `Twist` manual
   - pedir snapshots PNG

## 13. Caveats y cosas que confunden

### 13.1 Hay documentacion vieja

Algunos archivos antiguos mencionan:

- `dual_ekf_navsat.launch.py`
- `mapviz.launch.py`
- `navegacion.launch.py`
- `teleop.py`
- `gps_waypoint_logger.py`
- `yaml_waypoints_from_ll.py`

Esos archivos no estan hoy en `src/`.

### 13.2 Hay dos cosas llamadas `controller_server`

- `controller_server` de Nav2:
  plugin/nodo de control de rutas dentro de Nav2
- paquete `controller_server` de este repo:
  actuador UART real hacia ESP32

No son lo mismo.

### 13.3 `real.launch.py` no arranca el actuador

`real.launch.py` deja el stack hasta `/cmd_vel_safe`, pero el consumo final hacia UART corre aparte con `controller_server.launch.py`.

### 13.4 Nested git repos

Cada paquete dentro de `src/` puede tener su propio `.git`.
Eso importa para status, ramas y cambios.

### 13.5 `setup.py` de `navegacion_gps` tiene drift

Todavia declara executables que ya no existen en el arbol fuente.

## 14. Donde tocar cada cosa

- si falla GPS/IMU/odom del Pixhawk:
  `src/sensores/sensores/pixhawk_driver.py`

- si falla el LiDAR:
  `src/sensores/launch/rs16.launch.py`
  `src/rslidar_sdk/`

- si falla TF o la localizacion:
  `src/navegacion_gps/config/dual_ekf_navsat_params.yaml`
  `src/navegacion_gps/launch/real.launch.py`
  `src/navegacion_gps/launch/simulacion.launch.py`

- si falla planeacion/control Nav2:
  `src/navegacion_gps/config/nav2_no_map_params.yaml`

- si falla la seguridad por collision monitor:
  `src/navegacion_gps/config/collision_monitor.yaml`

- si falla la UI web o las zonas no-go:
  `src/map_tools/map_tools/web_zone_server.py`
  `src/navegacion_gps/navegacion_gps/keepout_manager.py`
  `src/navegacion_gps/navegacion_gps/nav_command_server.py`

- si falla el snapshot del mapa:
  `src/navegacion_gps/navegacion_gps/nav_snapshot_server.py`

- si falla la actuacion real:
  `src/controller_server/controller_server/controller_server_node.py`
  `src/controller_server/controller_server/rpy_esp32_comms/`

- si falla la capa vision safety:
  `src/vision_safety/vision_safety/`

## 15. Comandos de debug utiles

Dentro del contenedor:

```bash
source /opt/ros/humble/setup.bash
source /ros2_ws/install/setup.bash
```

Listar topics:

```bash
ros2 topic list
```

Ver frecuencia de scan:

```bash
ros2 topic hz /scan
```

Ver odometria local:

```bash
ros2 topic echo /odometry/local --once
```

Ver telemetria del backend de navegacion:

```bash
ros2 topic echo /nav_command_server/telemetry --once
```

Ver estado del actuador:

```bash
ros2 topic echo /controller/status --once
ros2 topic echo /controller/telemetry --once
```

Ver servicios relevantes:

```bash
ros2 service list | grep nav_command_server
ros2 service list | grep keepout_manager
```

Ver actions:

```bash
ros2 action list
```

Ver TF:

```bash
ros2 run tf2_tools view_frames
ros2 run tf2_ros tf2_echo map base_footprint
```

Healthcheck del LiDAR:

```bash
./tools/healthcheck-lidar.sh
```

## 16. Resumen corto y contrato central

Si hubiera que resumir el proyecto en una frase:

este repo toma sensores reales o simulados, construye localizacion global, ejecuta Nav2, aplica una capa de seguridad, expone una consola web para operar el sistema y finalmente entrega un `/cmd_vel_safe` que en simulacion va a Gazebo y en hardware real va al ESP32 por UART.

Ese es el contrato central del workspace.

## 17. Launches en detalle

Esta seccion baja un nivel mas y describe cada launch importante como una composicion de nodos, servicios y archivos de configuracion.

### 17.1 `real.launch.py`

Ubicacion:

- `src/navegacion_gps/launch/real.launch.py`

Objetivo:

- levantar el stack de robot real sin Gazebo
- opcionalmente arrancar drivers de sensores desde el mismo launch
- dejar el sistema listo para navegar, operar desde web y visualizar

Componentes que arranca:

- `robot_state_publisher`
  si `use_robot_state_publisher:=True`
- `sensores/pixhawk.launch.py`
  si `start_pixhawk:=True`
- `sensores/rs16.launch.py`
  si `start_lidar:=True`
- `robot_localization/ekf_node`
  uno para `odometry/local`
- `robot_localization/ekf_node`
  otro para el frame global `map`
- `robot_localization/navsat_transform_node`
  si `use_navsat:=True`
- `nav2_bringup/navigation_launch.py`
- `navegacion_gps/keepout_manager`
- `navegacion_gps/nav_command_server`
- `navegacion_gps/nav_snapshot_server`
- `map_tools/no_go_editor.launch.py`
- `rviz2`
  si `use_rviz:=True`
- `mapviz`
  si `use_mapviz:=True`
- `nav2_collision_monitor/collision_monitor`
  si `use_collision_monitor:=True`
- `nav2_lifecycle_manager/lifecycle_manager`
  para el `collision_monitor`
- `navegacion_gps/frame_id_stripper`
  si `use_frame_id_stripper:=True`
- `pointcloud_to_laserscan/pointcloud_to_laserscan_node`
  si `use_pointcloud_to_laserscan:=True`

Argumentos principales:

- `use_sim_time`
  normalmente `False` en robot real
- `use_robot_state_publisher`
  publica el modelo del robot y el arbol TF fijo derivado del URDF
- `custom_urdf`
  ruta al URDF a usar, por defecto `models/cuatri_real.urdf`
- `use_rviz`
  arranca RViz
- `rviz_config`
  ruta al `.rviz`
- `use_mapviz`
  arranca Mapviz
- `use_navsat`
  decide si se arranca `navsat_transform_node`
- `use_collision_monitor`
  activa la capa de seguridad de Nav2
- `use_frame_id_stripper`
  normaliza topics raw si el origen de sensores publica frames con prefijos o nombres no esperados
- `use_pointcloud_to_laserscan`
  convierte `/scan_3d` a `/scan`
- `start_pixhawk`
  incluye el launch del Pixhawk
- `start_lidar`
  incluye el launch del RS16
- `launch_web`
  si se pasa al launch del Pixhawk, arranca el mini dashboard de sensores
- `lidar_config_path`
  ruta al YAML del RS16
- `ws_host`
  host del WebSocket del backend web
- `ws_port`
  puerto del WebSocket del backend web
- `gps_topic`
  topic GPS que usa el backend web y de navegacion
- `map_frame`
  frame global usado por los backends custom

Relaciones importantes dentro de este launch:

- el `keepout_manager` usa `/fromLL` o `/navsat_transform/fromLL`
  para convertir zonas GPS a XY
- el `nav_command_server` usa la action `navigate_to_pose`
  del `bt_navigator` de Nav2
- el `nav_snapshot_server` consume topics ya producidos por Nav2 y por `collision_monitor`
- el launch no arranca el actuador real
  eso queda separado en `controller_server.launch.py`

### 17.2 `simulacion.launch.py`

Ubicacion:

- `src/navegacion_gps/launch/simulacion.launch.py`

Objetivo:

- arrancar la simulacion completa del stack
- dejar Gazebo, sensores, localizacion, Nav2, UI web y seguridad funcionando en una sola composicion

Componentes que arranca:

- `ros_gz_sim/gz_sim.launch.py`
- `ros_gz_bridge/parameter_bridge`
  con `config/bridge_config.yaml`
- `robot_state_publisher`
- `ros_gz_sim/create`
  para spawnear el robot
- `robot_localization` completo
- Nav2
- `keepout_manager`
- `nav_command_server`
- `nav_snapshot_server`
- backend web
- RViz opcional
- Mapviz opcional
- `collision_monitor`
- `frame_id_stripper`
- `pointcloud_to_laserscan`
- bridge opcional de `joint_state`

Argumentos principales:

- `use_sim_time`
  por defecto `True`
- `custom_urdf`
  modelo del robot a spawnear
- `use_rviz`
- `rviz_config`
- `use_mapviz`
- `use_navsat`
- `use_collision_monitor`
- `use_frame_id_stripper`
- `use_joint_state_bridge`
- `world`
  archivo `.world` o `.sdf`
- `world_name`
  nombre logico del mundo, usado por algunos topics Gazebo
- `model_name`
  nombre del modelo spawneado
- `ws_host`
- `ws_port`
- `gps_topic`
- `map_frame`

Diferencias clave respecto a `real.launch.py`:

- en vez de sensores reales, los datos entran por `ros_gz_bridge`
- existen topics `*_raw` bridgueados desde Gazebo
- se usa `frame_id_stripper` casi siempre
- `/cmd_vel_safe` no va a un actuador UART
  sino de vuelta a Gazebo como `/cmd_vel_steer`

### 17.3 `rviz_real.launch.py`

Objetivo:

- abrir RViz con el modelo del robot y la configuracion visual actual
- no correr sensores ni navegacion

Sirve para:

- revisar el URDF
- validar que el `robot_description` carga bien
- probar RViz por separado del resto del stack

### 17.4 `pixhawk.launch.py`

Objetivo:

- arrancar el driver MAVLink del Pixhawk
- opcionalmente arrancar el dashboard web de telemetria

Argumentos:

- `launch_web`
- `serial_port`
- `baudrate`
- `odom_frame`
- `base_link_frame`
- `imu_frame`
- `gps_frame`

Es el punto de entrada natural si quieres aislar solo la parte Pixhawk.

### 17.5 `rs16.launch.py`

Objetivo:

- arrancar el driver del RS16 usando `rslidar_sdk_node`

Argumentos:

- `config_path`
- `rviz`
- `use_cyclone_dds`

Notas:

- este launch es el wrapper actual que usa el proyecto
- los launches dentro de `rslidar_sdk/launch/` son mas bien heredados del driver, no del stack del proyecto

### 17.6 `no_go_editor.launch.py`

Objetivo:

- arrancar solo el backend WebSocket de la consola web

Argumentos:

- `ws_host`
- `ws_port`
- `gps_topic`
- `map_frame`
- `keepout_set_zones_service`
- `keepout_get_state_service`
- `nav_set_goal_service`
- `nav_cancel_goal_service`
- `nav_brake_service`
- `nav_set_manual_mode_service`
- `teleop_cmd_topic`
- `nav_get_state_service`
- `nav_snapshot_service`
- `nav_telemetry_topic`
- timeouts varios

### 17.7 `controller_server.launch.py`

Objetivo:

- arrancar el actuador real que consume `/cmd_vel_safe` y habla con el ESP32

Parametros cargados por defecto:

- `serial_port`
- `serial_baud`
- `serial_tx_hz`
- `max_reverse_mps`
- `max_abs_angular_z`
- `vx_deadband_mps`
- `vx_min_effective_mps`
- `invert_steer_from_cmd_vel`

### 17.8 Launches de `vision_safety`

`vision_safety_passive.launch.py`

- fusion y mocks
- no modifica el flujo de velocidad

`vision_safety_simulation_passive.launch.py`

- arranca la simulacion original
- encima añade la fusion pasiva
- el comportamiento base sigue intacto

`vision_safety_simulation_gate.launch.py`

- desactiva el `collision_monitor` base de la simulacion
- levanta uno propio con `cmd_vel_out=/cmd_vel_nav_safe`
- despues pasa por `cmd_vel_gate_node`
- termina publicando en `/cmd_vel_safe`

## 18. Configuraciones YAML en detalle

### 18.1 `dual_ekf_navsat_params.yaml`

Archivo:

- `src/navegacion_gps/config/dual_ekf_navsat_params.yaml`

Secciones importantes:

- `ekf_filter_node_odom`
  - `world_frame: odom`
  - `base_link_frame: base_footprint`
  - `odom0: /odom`
  - `imu0: /imu/data`
  produce la odometria local y el TF cercano al robot

- `ekf_filter_node_map`
  - `world_frame: map`
  - `odom0: /odometry/local`
  - `odom1: /odometry/gps`
  - `imu0: /imu/data`
  mezcla odometria local con GPS para sostener el frame global

- `navsat_transform`
  - `world_frame: map`
  - `odom_frame: odom`
  - `base_link_frame: base_footprint`
  - `gps_frame: gps_link`
  - `imu_frame: imu_link`
  - `datum`
  este nodo es el puente entre lat/lon y coordenadas metricas del frame `map`

Que significa en la practica:

- si fallan los goals GPS, suele haber que mirar este archivo
- si el TF `map -> odom -> base_footprint` esta roto, este archivo es uno de los primeros sospechosos
- el `datum` define el origen geodesico de conversion para la operacion GPS

### 18.2 `nav2_no_map_params.yaml`

Archivo:

- `src/navegacion_gps/config/nav2_no_map_params.yaml`

Secciones importantes:

- `bt_navigator`
  - usa `map` como global y `odom` como local
  - consume `/odometry/local`
  - se le inyectan los BT XML por rewrite desde el launch

- `behavior_server`
  - tiene plugins de `backup`, `drive_on_heading` y `wait`
  - define aceleraciones y desaceleraciones

- `planner_server`
  - usa `SmacPlannerHybrid`
  - radio de giro `minimum_turning_radius: 2.2`
  - modelo `DUBIN`
  - orientado a un robot tipo vehiculo Ackermann

- `controller_server`
  - usa `RegulatedPurePursuitController`
  - velocidad deseada `1.2`
  - `allow_reversing: false`
  - `odom_topic: /odometry/local`

- `velocity_smoother`
  - suaviza velocidad antes del resto del pipeline
  - define maximos, minimos, deadband y timeout

- `local_costmap`
  - rolling window
  - usa `VoxelLayer`
  - usa `/scan`
  - incluye `KeepoutFilter`

- `global_costmap`
  - rolling window en frame `map`
  - usa `ObstacleLayer`
  - tambien incluye `KeepoutFilter`

- `lifecycle_manager_navigation`
  - maneja planner, controller, smoother, bt_navigator, behavior_server y waypoint_follower

Que tocar en este archivo dependiendo del problema:

- si el robot gira muy abierto o no puede maniobrar:
  `planner_server` y `controller_server`
- si el robot va demasiado rapido o demasiado lento:
  `controller_server` y `velocity_smoother`
- si el costmap local no detecta bien:
  `local_costmap`
- si el costmap global "olvida" o "borra" demasiado:
  `global_costmap`

### 18.3 `collision_monitor.yaml`

Archivo:

- `src/navegacion_gps/config/collision_monitor.yaml`

Rol:

- transformar un `cmd_vel` de navegacion en un `cmd_vel` seguro

Entradas importantes:

- `cmd_vel_in_topic: /cmd_vel_nav`
- `cmd_vel_out_topic: /cmd_vel_safe`
- `base_frame_id: base_footprint`
- `odom_frame_id: odom`

Poligonos:

- `footprint`
- `stop_zone`

Fuentes de observacion:

- `/scan`
- `/ultrasound/rear_center`
- `/ultrasound/rear_left`
- `/ultrasound/rear_right`
- `/ultrasound/front_left`
- `/ultrasound/front_right`

Interpretacion:

- en el flujo normal, este archivo es la capa final de seguridad antes del actuador o del bridge a Gazebo
- en `vision_safety_simulation_gate.launch.py` se reutiliza este mismo archivo, pero cambiando el topic de salida

### 18.4 `pointcloud_to_laserscan.yaml`

Archivo:

- `src/navegacion_gps/config/pointcloud_to_laserscan.yaml`

Rol:

- transformar `/scan_3d` en `/scan`

Parametros destacados:

- `target_frame: base_footprint`
- `min_height: 0.11`
- `max_height: 1.60`
- `angle_min` y `angle_max`
  aprox 180 grados frontales
- `range_min: 0.4`
- `range_max: 20.0`

Interpretacion:

- este archivo es importante si el robot "ve" demasiado suelo, demasiado techo o se pierde obstaculos por altura

### 18.5 `bridge_config.yaml`

Archivo:

- `src/navegacion_gps/config/bridge_config.yaml`

Rol:

- declarar todos los topics ROS <-> Gazebo relevantes en simulacion

Entradas importantes:

- `/cmd_vel_safe` -> `/cmd_vel_steer`
- `/odom_raw` <- `/odom`
- `/scan_3d_raw` <- `/lidar/points`
- `/imu/data_raw` <- `/imu/data`
- `/gps/fix_raw` <- `/gps/fix`
- ultrasonidos raw

Si algo no aparece en ROS 2 en simulacion:

- este archivo es uno de los primeros lugares a revisar

### 18.6 `default-waypoints.yaml`

Archivo:

- `src/navegacion_gps/config/default-waypoints.yaml`

Contiene:

- una lista de waypoints GPS de ejemplo en Cordoba

Hoy el repo no tiene los nodos antiguos de "waypoint follower" declarados en el `setup.py`, pero este archivo sigue siendo util como referencia de formato.

### 18.7 `no_go_zones.yaml`

Archivo:

- `src/navegacion_gps/config/no_go_zones.yaml`

Contiene:

- `frame_id: map`
- lista de zonas GPS con `id`, `type`, `enabled` y `polygon`

Observaciones:

- es la persistencia por defecto del `keepout_manager`
- se detecta una inconsistencia menor en el archivo actual:
  hay dos zonas con `id: zone_2`
  no rompe necesariamente el runtime, pero es una deuda de datos que conviene corregir

## 19. Recorridos de runtime paso a paso

### 19.1 Desde un click en la UI hasta el movimiento del robot

Secuencia conceptual:

1. el usuario hace click en el mapa del frontend
2. el frontend manda una operacion WebSocket `set_goal_ll`
3. `web_zone_server.py` recibe el JSON y llama al servicio ROS `SetNavGoalLL`
4. `nav_command_server.py` recibe lat/lon/yaw
5. `nav_command_server.py` usa `/fromLL` o `/navsat_transform/fromLL`
6. obtiene un punto XY en el frame `map`
7. crea un `NavigateToPose.Goal`
8. lo envia a la action `navigate_to_pose`
9. Nav2 planifica y empieza a publicar comandos de velocidad
10. `collision_monitor` inspecciona esos comandos junto con el entorno sensado
11. publica `/cmd_vel_safe`
12. en simulacion:
    `/cmd_vel_safe` va a Gazebo como `/cmd_vel_steer`
13. en robot real:
    `controller_server` consume `/cmd_vel_safe`
14. `controller_server` convierte a velocidad/direccion/freno
15. `transport.py` serializa el frame UART
16. el ESP32 recibe el comando y actua sobre el vehiculo

### 19.2 Desde teleop web hasta el movimiento

1. la UI manda por WebSocket un comando manual
2. `web_zone_server.py` publica `Twist` en `/cmd_vel_teleop`
3. `nav_command_server.py` escucha `/cmd_vel_teleop`
4. si `manual_enabled=True`, republica al `manual_cmd_topic`
5. por configuracion actual ese topic es `/cmd_vel_safe`
6. el resto del pipeline es el mismo que en el caso normal

Punto importante:

- `nav_command_server.py` tiene watchdog de comando manual
- si no llegan comandos frescos, publica `Twist` cero para no dejar el robot moviendose indefinidamente

### 19.3 Desde una zona no-go nueva hasta el costmap

1. la UI manda por WebSocket una operacion `set_zones_ll`
2. `web_zone_server.py` llama a `SetKeepoutZones`
3. `keepout_manager.py` recibe poligonos en lat/lon
4. usa `/fromLL` para convertir cada vertice a XY en `map`
5. rasteriza esos poligonos sobre una grilla
6. opcionalmente aplica degradado alrededor de las zonas
7. publica `OccupancyGrid` en `/keepout_filter_mask`
8. publica `CostmapFilterInfo` en `/costmap_filter_info`
9. Nav2 vuelve a incorporar esa informacion en local y global costmap

### 19.4 Desde un pedido de snapshot hasta el PNG

1. el frontend pide `get_nav_snapshot`
2. `web_zone_server.py` llama al servicio `GetNavSnapshot`
3. `nav_snapshot_server.py` toma la ultima copia disponible de:
   - costmap local
   - costmap global
   - keepout mask
   - footprint
   - stop zone
   - polygons del collision monitor
   - scan
   - plan
4. transforma todo al frame de snapshot
5. renderiza un canvas en memoria
6. codifica el PNG
7. devuelve bytes + metadatos por servicio
8. el backend web los reempaqueta para el navegador

### 19.5 Desde sensores simulados hasta `/scan`

1. Gazebo publica `/lidar/points`
2. `ros_gz_bridge` lo traduce a `/scan_3d_raw`
3. `frame_id_stripper` lo publica como `/scan_3d`
4. `pointcloud_to_laserscan` proyecta una rebanada 2D
5. sale `/scan`
6. `collision_monitor` y los costmaps de Nav2 ya pueden usarlo

## 20. Assets, modelos y mundos

### 20.1 URDFs y modelos

Carpeta:

- `src/navegacion_gps/models`

Archivos visibles:

- `cuatri.urdf`
- `cuatri_real.urdf`
- `cuatri_ultrasound.urdf`
- `modelo.urdf`
- `my_robot.urdf`

Interpretacion practica:

- `cuatri_real.urdf`
  es el modelo de referencia que usan los launches reales por defecto
- `cuatri_ultrasound.urdf`
  sugiere una variante con sensores ultrasonicos definidos
- el resto parecen variantes historicas o experimentales del modelo

### 20.2 Mundos de simulacion

Carpeta:

- `src/navegacion_gps/worlds`

Archivos visibles:

- `default.sdf`
- `pasillos_obstaculos.world`
- `tugbot_depot.world`
- `vacio.world`

Interpretacion:

- `pasillos_obstaculos.world`
  es el default usado por `simulacion.launch.py`
- `vacio.world`
  sirve para pruebas mas limpias
- `tugbot_depot.world`
  aporta otro escenario

### 20.3 Web frontend

Archivo principal:

- `src/map_tools/web/index.html`

Ese archivo no es un nodo ROS 2, pero es parte importante del sistema porque:

- habla por WebSocket con `web_zone_server`
- permite operar zonas no-go
- permite mandar goals de navegacion
- permite teleop manual
- consume snapshots y telemetria

### 20.4 RViz configs

Ejemplos:

- `src/navegacion_gps/config/rviz_nav2_full.rviz`
- `src/vision_safety/config/vision_safety_passive.rviz`

Su funcion es:

- preconfigurar displays para costmaps, robot model, scan, markers y estados del stack

## 21. Workflows de desarrollo

### 21.1 Si quieres cambiar un topic

Normalmente hay que revisar mas de un lugar:

1. el nodo que publica
2. el nodo que consume
3. el launch donde se parametriza
4. los YAML de configuracion
5. si aplica, la UI web o el backend web

Ejemplo:
si cambias `/scan`, no alcanza con tocar `pointcloud_to_laserscan`.
Tambien hay que revisar:

- `collision_monitor.yaml`
- `nav2_no_map_params.yaml`
- `nav_snapshot_server.py`
- `vision_safety` si esa capa usa `/scan`

### 21.2 Si quieres cambiar un frame

Revisa:

- URDF
- `dual_ekf_navsat_params.yaml`
- `pixhawk.launch.py`
- `frame_id_stripper.py`
- cualquier transformacion TF o config de Nav2

### 21.3 Si quieres cambiar la forma o tamano del robot

Revisa:

- URDF correspondiente
- footprint de local costmap
- footprint de global costmap
- poligonos de `collision_monitor`

Porque si actualizas solo el URDF:

- RViz puede verse bien
- pero Nav2 seguiria pensando que el robot tiene el footprint viejo

### 21.4 Si quieres cambiar velocidad, giro o comportamiento de seguimiento

Revisa:

- `nav2_no_map_params.yaml`
  en `planner_server`
  en `controller_server`
  en `velocity_smoother`
- `controller_server.launch.py`
  si el problema es el mapeo final a actuadores
- `control_logic.py`
  si la respuesta del ESP32 final no coincide con el `Twist`

### 21.5 Si quieres tocar la UI web

Revisa dos capas:

- frontend:
  `src/map_tools/web/index.html`
- backend:
  `src/map_tools/map_tools/web_zone_server.py`

Regla practica:

- si agregas un boton nuevo casi siempre necesitas tocar ambos

### 21.6 Si quieres tocar el protocolo UART

Revisa:

- `protocol.py`
- `telemetry.py`
- `transport.py`
- `cli.py`
- `controller_server_node.py`
- tests del paquete

Y ademas:

- el firmware del ESP32 debe cambiar en conjunto

## 22. Debugging por sintomas

### 22.1 "No aparece `/scan`"

Posibles lugares:

- driver LiDAR no corre
- `ros_gz_bridge` no esta publicando `/scan_3d_raw`
- `frame_id_stripper` no corre
- `pointcloud_to_laserscan` esta mal configurado

Orden recomendado:

1. mirar `/scan_3d_raw`
2. mirar `/scan_3d`
3. mirar `/scan`

### 22.2 "Hay GPS pero no navega a goals GPS"

Revisar:

- `/gps/fix`
- `/odometry/local`
- `/odometry/gps`
- disponibilidad de `/fromLL`
- `datum` de `navsat_transform`
- action `navigate_to_pose`

### 22.3 "La UI conecta pero no hace nada"

Revisar:

- que `web_zone_server` este corriendo
- `ws_host` y `ws_port`
- que existan los servicios del backend
- que los nombres de servicio no hayan cambiado
- que la UI este apuntando al WebSocket correcto

### 22.4 "Se mueve en simulacion pero no en real"

Muy probable:

- falta levantar `controller_server.launch.py`
- el topic `/cmd_vel_safe` existe, pero nadie lo consume

Tambien revisar:

- puerto serial
- permisos
- `controller/status`
- `controller/telemetry`

### 22.5 "El robot se frena demasiado"

Revisar:

- `collision_monitor.yaml`
- topics de ultrasonidos
- `/scan`
- si `vision_safety` esta metido en el pipeline
- footprint y stop zone

### 22.6 "El robot no frena nunca"

Revisar:

- si `collision_monitor` esta levantado
- si realmente el planner publica en el topic que ese nodo espera
- si `/scan` llega
- si los frames TF permiten transformar los datos

## 23. Deuda tecnica e inconsistencias actuales

### 23.1 Drift entre documentacion y codigo

Existe en varios lugares:

- README de `navegacion_gps`
- `setup.py` de `navegacion_gps`
- notas antiguas del root

Eso puede hacerte creer que existen launches o nodos que hoy no estan en `src/`.

### 23.2 `setup.py` desactualizado en `navegacion_gps`

Todavia declara entry points a archivos ausentes:

- `interactive_waypoint_follower`
- `gps_waypoint_logger`
- `teleop`
- `yaml_waypoints_from_ll`

### 23.3 `real.launch.py` y actuacion real desacoplados

El stack de navegacion y sensores vive en `real.launch.py`, pero el actuador real vive aparte. Eso obliga a saber que para operacion completa normalmente hacen falta dos procesos.

### 23.4 Duplicado de IDs en `no_go_zones.yaml`

Hay al menos dos zonas con el mismo `id`.

### 23.5 Multiples variantes de modelos y mundos

El repo tiene varios URDF y varios worlds sin que siempre quede claro cual es el canonico. Hoy el comportamiento real del stack depende de:

- `cuatri_real.urdf`
- `pasillos_obstaculos.world`

salvo que se pase otra cosa por argumento.

### 23.6 `rslidar_sdk` trae launches heredados

Los launches `start.py`, `elequent_start.py` y `humble_start.py` existen, pero no todos parecen alineados con el estilo actual del workspace.

### 23.7 Nombres potencialmente confusos

- `controller_server`
  puede referir al paquete UART de este repo
  o al nodo `controller_server` de Nav2 configurado por YAML

## 24. Orden recomendado para leer el repo

Si estas empezando desde cero, un orden practico es:

1. `README.md`
2. `src/navegacion_gps/launch/real.launch.py`
3. `src/navegacion_gps/launch/simulacion.launch.py`
4. `src/navegacion_gps/config/dual_ekf_navsat_params.yaml`
5. `src/navegacion_gps/config/nav2_no_map_params.yaml`
6. `src/navegacion_gps/config/collision_monitor.yaml`
7. `src/navegacion_gps/navegacion_gps/nav_command_server.py`
8. `src/navegacion_gps/navegacion_gps/keepout_manager.py`
9. `src/map_tools/map_tools/web_zone_server.py`
10. `src/sensores/sensores/pixhawk_driver.py`
11. `src/controller_server/controller_server/controller_server_node.py`
12. `src/controller_server/controller_server/rpy_esp32_comms/transport.py`

Si quieres entender solo navegacion:

1. launches de `navegacion_gps`
2. YAML de `navegacion_gps`
3. `nav_command_server.py`
4. `nav_snapshot_server.py`

Si quieres entender solo la parte web:

1. `src/map_tools/web/index.html`
2. `src/map_tools/map_tools/web_zone_server.py`
3. `src/navegacion_gps_interfaces/`
4. `keepout_manager.py`
5. `nav_command_server.py`

Si quieres entender solo actuacion real:

1. `controller_server.launch.py`
2. `controller_server_node.py`
3. `control_logic.py`
4. `rpy_esp32_comms/protocol.py`
5. `rpy_esp32_comms/transport.py`

## 25. Criterio practico para no perderse

Cuando dudes de "donde pasa algo", usa esta regla:

- si es simulacion o integracion general:
  mira `simulacion.launch.py`
- si es robot real:
  mira `real.launch.py`
- si es goal, teleop, web o freno:
  mira `nav_command_server.py` y `web_zone_server.py`
- si es zona prohibida:
  mira `keepout_manager.py`
- si es `/scan`:
  mira `rs16.launch.py`, `bridge_config.yaml` y `pointcloud_to_laserscan.yaml`
- si es `/cmd_vel_safe`:
  mira `collision_monitor.yaml` y `controller_server_node.py`
- si es UART:
  mira `rpy_esp32_comms/`

Con esa regla casi siempre caes en el archivo correcto rapidamente.
