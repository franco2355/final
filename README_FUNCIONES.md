# Referencia exhaustiva de funciones - aeye-ros-workspace

Este documento explica las funciones, metodos y entry points Python mas relevantes del workspace `aeye-ros-workspace`.
La idea no es solo listar nombres, sino dejar claro:

- para que existe cada funcion
- cuando se ejecuta
- que entradas consume
- que salida, efecto lateral o contrato ROS 2 produce
- como encaja en el flujo real del sistema

## Alcance

Se cubren los archivos Python del workspace en estas categorias:

- `runtime`: nodos y utilidades que participan en la ejecucion normal del sistema
- `launch`: funciones que ensamblan la topologia ROS 2
- `tools`: scripts de prueba y soporte
- `tests`: pruebas unitarias y checks de calidad
- `historico`: scripts o launches heredados que siguen presentes en el repo

No se documentan en detalle los archivos sin logica ejecutable real, como la mayoria de los `__init__.py`, ni los `setup.py` salvo cuando ayudan a entender entry points.

## Como leer este documento

- Si quieres entender el robot en marcha, empieza por `navegacion_gps`, `sensores`, `map_tools` y `controller_server`.
- Si quieres entender la capa de seguridad por vision, lee `vision_safety`.
- Si quieres saber como se levanta todo, mira las subsecciones `launch`.
- Si quieres saber como se prueba el hardware o el protocolo UART, ve a `controller_server` y `tools`.

---

## Indice

- [vision_safety](#vision_safety)
- [navegacion_gps](#navegacion_gps)
- [map_tools](#map_tools)
- [sensores](#sensores)
- [controller_server](#controller_server)
- [tools](#tools)
- [tests-y-chequeos-de-calidad](#tests-y-chequeos-de-calidad)
- [archivos-sin-funciones-o-con-logica-minima](#archivos-sin-funciones-o-con-logica-minima)

---

## vision_safety

Paquete de seguridad activa basado en la fusion entre detecciones de vision y `LaserScan`. Tiene dos modos de uso:

- modo pasivo: publica diagnostico y markers, pero no bloquea el movimiento
- modo activo: inserta un gate entre navegacion y actuacion, y puede frenar o retroceder

### `vision_safety/cmd_vel_gate_node.py`

Rol general:
Este archivo implementa la maquina de estados que decide si un comando de velocidad puede pasar, debe convertirse en stop, o debe reemplazarse por una maniobra de reversa. Es la pieza que convierte una alerta de vision en una accion concreta sobre `cmd_vel`.

- `_zero()`: construye un `Twist` completamente en cero. Se usa como salida segura cuando el gate quiere inmovilizar el robot o no hay un comando valido que reenviar.
- `_reverse(speed)`: construye un `Twist` de retroceso puro. La funcion fuerza el signo negativo de `linear.x`, de modo que el codigo que la usa no dependa de recordar si la velocidad ya venia negativa.
- `CmdVelGateNode.__init__()`: declara parametros, define topics de entrada y salida, crea publishers, subscribers y el timer del ciclo de control. Tambien inicializa el estado interno de la maquina (`PASSTHROUGH`, `STOPPING`, `REVERSING`, `WAIT_CLEAR`) y contadores como confirmacion de stop, despeje y cooldown.
- `_on_nav_cmd(msg)`: callback del comando de navegacion entrante. No decide nada por si mismo; solo cachea el ultimo `Twist` para que `_tick()` pueda usarlo cuando el estado del gate permita el paso.
- `_on_vision_stop(msg)`: callback de la senal booleana de vision. Actualiza el flag de stop y guarda el instante de recepcion para que el gate pueda saber si la senal sigue fresca o ya expiro.
- `_vision_is_fresh(now)`: implementa la politica `fail-open` del gate. Si la senal de vision no llega dentro del timeout, la considera caduca y el gate deja de bloquear por vision para no inmovilizar el sistema por una falla de comunicacion.
- `_tick()`: es el corazon del nodo. En cada iteracion evalua si hay stop fresco, cuantos frames consecutivos lo confirman, si corresponde entrar en freno, si ya debe iniciar la reversa, si tiene que esperar despeje o si debe volver a pasar los comandos normales. Toda la logica de seguridad activa vive aca.
- `_publish_nav_cmd()`: publica el ultimo comando de navegacion disponible o un `Twist` cero si no hay ninguno cacheado. Es el camino normal de salida cuando el gate esta en modo paso libre.
- `_reset_to_pass()`: limpia estado y contadores para volver a `PASSTHROUGH`. Se usa al finalizar un ciclo de bloqueo o cuando la situacion deja de requerir intervencion.
- `_publish_state(now, vision_fresh, stop_active)`: serializa el estado interno del gate en un JSON legible por humanos y por la capa de visualizacion. Ese payload permite diagnosticar si el gate esta bloqueando por vision real, por timeout, por cooldown o por espera de despeje.
- `main()`: entry point del nodo. Inicializa `rclpy`, crea el nodo, arranca el spin y garantiza el cierre limpio ante `KeyboardInterrupt`.

### `vision_safety/vision_lidar_fusion_node.py`

Rol general:
Fusiona una deteccion 2D de camara con un sector angular del `LaserScan`. La idea es responder una pregunta mas fuerte que "la camara vio algo": "la camara vio algo y el LiDAR confirma que hay un obstaculo dentro de una distancia peligrosa".

- `_stamp_to_s(sec, nanosec)`: convierte timestamps ROS a segundos en coma flotante. Se usa para comparar frescura temporal entre detecciones y scans sin trabajar con objetos `Time`.
- `_safe_float(value, default)`: helper defensivo que convierte a `float` y cae a un valor por defecto ante `None` o valores invalidos. Reduce el ruido en codigo de parsing y fusion.
- `VisionLidarFusionNode.__init__()`: define parametros geometricos y temporales de la fusion, crea subscribers para detecciones y scan, publishers de objetos fusionados, estado, markers y stop confirmado, y arma timers. Tambien reserva estructuras para cachear la ultima deteccion, el ultimo scan y el ultimo resultado fusionado.
- `_on_detections(msg)`: almacena el ultimo `Detection2DArray` y dispara un intento de fusion. La fusion no se hace "a ciegas"; se ejecuta solo si tambien hay un scan suficientemente reciente.
- `_on_scan(msg)`: almacena el ultimo `LaserScan` y vuelve a intentar fusion. Igual que el callback de detecciones, por si el scan llega despues.
- `_best_hypothesis(detection)`: de una deteccion con varias hipotesis, elige la de mayor score. Eso simplifica la salida y evita mezclar varias clases sobre un mismo bbox.
- `_scan_samples_for_detection(detection, scan)`: proyecta el ancho horizontal del bounding box al FOV de la camara y de ahi a indices del `LaserScan`. Devuelve las muestras LiDAR candidatas para esa deteccion, filtrando infinitos y valores invalidos.
- `_fuse_detection(detection, scan)`: toma una deteccion individual y produce un objeto fusionado con clase, score, angulo aproximado, estadisticos de distancia y decision de peligrosidad. Es la pieza que convierte "bbox + scan" en un dato util para frenado.
- `_maybe_fuse()`: valida que haya entradas suficientes, que no esten demasiado desfasadas en tiempo y, recien entonces, ejecuta la fusion completa. Si la sincronizacion temporal falla, evita generar falsas confirmaciones.
- `_summary_payload()`: empaqueta el ultimo resultado fusionado a JSON compacto. Esta salida esta pensada para logs, dashboards o canales ligeros donde no conviene mandar mensajes ROS complejos.
- `_make_marker(marker_id, marker_type, ns)`: fabrica un `Marker` base con campos comunes ya listos. Es una funcion de conveniencia para que `_build_markers()` no repita configuracion.
- `_build_markers()`: genera el `MarkerArray` completo para RViz. Suele incluir puntos o esferas para objetos confirmados y elementos visuales que resaltan si alguno es peligroso.
- `_tick()`: publicacion periodica de estado. Incluso si no hay datos nuevos en ese instante, permite que los consumidores tengan una referencia estable del ultimo resultado.
- `main(args=None)`: entry point del nodo.

### `vision_safety/mock_detections_node.py`

Rol general:
Genera una deteccion sintetica para probar la fusion sin detector real.

- `MockDetectionsNode.__init__()`: declara parametros del bbox sintetico, clase, confianza y topic de salida. Su funcion principal es hacer reproducibles las pruebas.
- `_tick()`: construye un `Detection2DArray` con una sola deteccion sintentica y la publica periodicamente. Con esto se puede probar la proyeccion bbox -> sector LiDAR y la logica de stop sin camara.
- `main(args=None)`: entry point del mock.

### `vision_safety/mock_laserscan_node.py`

Rol general:
Genera un `LaserScan` sintetico con un obstaculo configurable.

- `MockLaserScanNode.__init__()`: define la geometria del scan, su resolucion angular, alcance y la forma del obstaculo sintetico que quiere inyectar.
- `_tick()`: construye el scan de salida, rellena el entorno "libre" y luego inserta el obstaculo en el sector configurado. Sirve para probar la fusion sin LiDAR fisico ni Gazebo.
- `main(args=None)`: entry point del mock de scan.

### `vision_safety/vision_safety_viz_node.py`

Rol general:
Nodo de visualizacion para RViz. No toma decisiones de control; se dedica a hacer visible el estado del gate, la senal de stop y la diferencia entre comando de entrada y salida.

- `_point(x, y, z)`: helper que devuelve un `Point` ROS a partir de coordenadas escalares. Simplifica la construccion de markers.
- `VisionSafetyVizNode.__init__()`: declara parametros, se subscribe a `cmd_vel` de entrada y salida, al stop de vision y al JSON del gate, y crea un timer de renderizado.
- `_on_input_cmd(msg)`: cachea el ultimo comando de entrada al gate. Permite dibujar que queria hacer Nav2.
- `_on_output_cmd(msg)`: cachea el ultimo comando de salida. Permite ver si el gate dejo pasar, anuló o reemplazo el comando.
- `_on_vision_stop(msg)`: guarda el estado actual del stop por vision para usarlo en indicadores visuales.
- `_on_gate_state(msg)`: parsea el JSON del gate y actualiza flags como `blocked`, `degraded` o el nombre del estado actual.
- `_make_text_marker(...)`: construye un marker de texto para mostrar etiquetas, estados y diagnostico directamente en RViz.
- `_make_sphere_marker(...)`: construye un marker esferico, util para semaforos visuales o indicadores compactos.
- `_make_cube_marker(...)`: construye un marker cubico con escala no uniforme. Se usa para barras, paneles o indicadores de estado.
- `_make_arrow_marker(...)`: traduce un `Twist` a una flecha visual. Es muy util para comparar de un vistazo el vector de entrada con el de salida.
- `_tick()`: recompone el `MarkerArray` completo y lo publica. Toda la escena de RViz del paquete se refresca desde aca.
- `main(args=None)`: entry point del nodo.

### `vision_safety/launch/vision_safety_passive.launch.py`

Rol general:
Launch pasivo que solo levanta fusion y, opcionalmente, detecciones mock. No toca la linea de actuacion.

- `generate_launch_description()`: declara argumentos como `scan_topic`, `stop_distance_m` y `use_mock_detections`, crea el nodo de fusion, crea el mock si se pide y devuelve el `LaunchDescription`. Su contrato es simple: observar y publicar diagnostico, no bloquear movimiento.

### `vision_safety/launch/vision_safety_simulation_passive.launch.py`

Rol general:
Wrapper que combina la simulacion canonica con la vision pasiva.

- `generate_launch_description()`: incluye `simulacion.launch.py` sin alterar el pipeline de control, reemplaza solo el RViz por uno que ya trae displays de vision y despues incluye `vision_safety_passive.launch.py`.

### `vision_safety/launch/vision_safety_simulation_gate.launch.py`

Rol general:
Wrapper de simulacion activa. Inserta la seguridad por vision dentro del pipeline de velocidad.

- `generate_launch_description()`: levanta la simulacion base con el `collision_monitor` original deshabilitado, crea un `collision_monitor` propio que sale por `/cmd_vel_nav_safe`, incluye la vision pasiva y agrega el `cmd_vel_gate_node` que publica finalmente en `/cmd_vel_safe`.

---

## navegacion_gps

Paquete principal del proyecto. Orquesta localizacion, navegacion, zonas keepout, snapshots y parte de la interfaz con la web.

### `navegacion_gps/launch/real.launch.py`

Rol general:
Es el launch principal para robot real. Desde aca se ensambla la mayor parte del stack de ROS 2.

- `_read_file(path)`: lee archivos de texto completos, sobre todo URDF y XML de behavior trees, para inyectarlos como parametros.
- `_resolve_zones_file_path(package_share_dir)`: intenta usar primero el YAML de zonas dentro del arbol fuente del workspace y, si no puede, cae al archivo instalado del paquete. Esto ayuda a que editar `src/.../no_go_zones.yaml` tenga efecto directo sin reinstalar.
- `_build_robot_state_publisher(context)`: `OpaqueFunction` que decide dinamicamente si debe crear `robot_state_publisher` y con que URDF. Devuelve una lista de acciones porque en launch no siempre se construye todo de forma declarativa pura.
- `generate_launch_description()`: declara todos los argumentos, reescribe parametros de Nav2 para apuntar a BT XML locales, crea EKF, `navsat_transform`, Nav2, `collision_monitor`, backend keepout, backend de comandos, snapshots, consola web y opcionales como RViz, LiDAR, Pixhawk o `frame_id_stripper`.

### `navegacion_gps/launch/simulacion.launch.py`

Rol general:
Equivalente de `real.launch.py`, pero para Gazebo Sim.

- `_read_file(path)`: mismo patron que en `real.launch.py`; se usa para cargar el URDF del robot.
- `_resolve_zones_file_path(package_share_dir)`: misma idea que en el launch real, para que la simulacion use las zonas del source tree cuando existen.
- `_spawn_robot(context)`: crea `robot_state_publisher` y el proceso `ros_gz_sim create` que inserta el robot en Gazebo. Es la funcion que materializa el modelo dentro del mundo.
- `_build_gz_bridge(context, bridge_config)`: arma el bridge `ros_gz_bridge` con el YAML de configuracion correspondiente. Gracias a esto los topics de Gazebo se traducen a mensajes ROS 2 y viceversa.
- `_build_joint_state_bridge(context)`: opcion para puentear `joint_state` desde Gazebo solo si el argumento correspondiente esta activo. Es util para inspeccion o visualizacion, pero no siempre necesario.
- `generate_launch_description()`: declara argumentos de simulacion, mundo, modelo, RViz, joints y seguridad; incluye Gazebo, bridge, spawn, EKF, Nav2, keepout, backend web y demas nodos del stack.

### `navegacion_gps/launch/rviz_real.launch.py`

Rol general:
Launch liviano para inspeccionar el robot real en RViz sin arrancar toda la navegacion.

- `_read_file(path)`: lee el URDF.
- `_build_robot_state_publisher(context)`: crea el `robot_state_publisher` usando el URDF elegido por argumento.
- `generate_launch_description()`: declara argumentos de `use_sim_time`, `rviz_config` y `custom_urdf`, y levanta solo `robot_state_publisher` + RViz.

### `navegacion_gps/frame_id_stripper.py`

Rol general:
Corrige `frame_id` y `child_frame_id` de mensajes que llegan con prefijos o nombres incompatibles con el resto del stack.

- `FrameIdStripper.__init__()`: declara topics de entrada y salida, `frame_id` de override por sensor y crea todos los publishers/subscribers del nodo.
- `_strip(frame_id)`: elimina el prefijo estilo C++ `namespace::frame` cuando `strip_prefix` esta habilitado. Sirve sobre todo para mensajes que vienen de Gazebo o drivers que ensucian el nombre del frame.
- `_resolve_frame(incoming, override)`: decide el `frame_id` final. Si hay override configurado, gana el override; si no, aplica `_strip()` al nombre entrante.
- `_imu_cb(msg)`: corrige el `header.frame_id` del `Imu` y republica en el topic limpio.
- `_gps_cb(msg)`: corrige el `frame_id` de `NavSatFix`.
- `_lidar_cb(msg)`: corrige el `frame_id` del `PointCloud2` del LiDAR.
- `_ultrasound_rear_center_cb(msg)`: corrige y republica el ultrasonido trasero central.
- `_ultrasound_rear_left_cb(msg)`: corrige y republica el ultrasonido trasero izquierdo.
- `_ultrasound_rear_right_cb(msg)`: corrige y republica el ultrasonido trasero derecho.
- `_ultrasound_front_left_cb(msg)`: corrige y republica el ultrasonido frontal izquierdo.
- `_ultrasound_front_right_cb(msg)`: corrige y republica el ultrasonido frontal derecho.
- `_odom_cb(msg)`: corrige tanto el `header.frame_id` como el `child_frame_id` de la odometria, que es el caso mas delicado para TF.
- `main()`: entry point del nodo.

### `navegacion_gps/keepout_mask_utils.py`

Rol general:
Funciones puras para transformar zonas polygonales en una mascara de costo utilizable por Nav2.

- `exponential_gradient_from_core(core_mask, resolution, radius_m, edge_cost, min_cost, use_l2)`: toma una mascara binaria del nucleo keepout y genera un gradiente decreciente alrededor. Esto permite que Nav2 no solo respete el nucleo prohibido, sino que tambien tienda a evitar sus bordes.
- `rasterize_polygons_core(zones_xy, width, height, resolution, origin_x, origin_y)`: convierte poligonos en coordenadas metricas del mapa a una imagen raster binaria de `OccupancyGrid`. Tambien reporta zonas recortadas o completamente fuera del grid, que es clave para diagnosticar por que una zona no aparece donde se espera.

### `navegacion_gps/keepout_manager.py`

Rol general:
Backend de zonas no-go. Traduce zonas geograficas a coordenadas de mapa, genera la mascara keepout y la publica para que la consuma Nav2.

- `KeepoutManagerNode.__init__()`: configura parametros, publishers, servicios y clientes ROS necesarios, y finalmente intenta cargar las zonas iniciales desde disco.
- `_resolve_zones_file(configured)`: decide que archivo YAML usar como persistencia. Prioriza el parametro del usuario, pero puede caer a una ruta por defecto del paquete.
- `_sanitize_degrade_params()`: valida radio y costos del gradiente para evitar configuraciones inconsistentes o fuera de rango.
- `_sanitize_mask_grid_params()`: valida resolucion, ancho, alto y origen del grid de mascara cuando se trabaja con dimensiones fijas.
- `_build_fixed_mask_metadata()`: arma un `MapMetaData` consistente para el caso en que la mascara no se derive del costmap global y deba usar parametros fijos.
- `_wait_for_future(future, timeout_sec)`: helper bloqueante para esperar respuestas de servicios ROS 2 con timeout controlado.
- `_call_from_ll(lat, lon)`: usa el servicio `fromLL` activo para convertir latitud y longitud a coordenadas `map`.
- `_resolve_fromll_client()`: elige entre cliente primario y fallback de `fromLL`, en funcion de cual este disponible.
- `_maybe_log_active_fromll(service_name)`: reduce spam de logs. Solo informa el servicio `fromLL` activo cuando realmente cambia.
- `_get_global_costmap()`: consulta el costmap global para intentar deducir el area sobre la que debe construirse la mascara keepout.
- `_resolve_mask_grid_spec()`: decide con que origen, resolucion y tamano se va a rasterizar la mascara. Puede tomar esa informacion del costmap global o de parametros fijos.
- `_convert_zones_to_xy(zones)`: recorre las zonas cargadas, filtra las invalidadas o deshabilitadas, llama `fromLL` para cada vertice y produce una representacion en coordenadas metricas del frame `map`.
- `_rasterize_mask(zones_xy, grid_spec)`: aplica `rasterize_polygons_core()` y el gradiente de costo para producir los datos del `OccupancyGrid` final.
- `_publish_filter_info()`: publica el mensaje companero que describe como debe interpretarse la mascara dentro del framework de costmap filters de Nav2.
- `_save_zones_to_disk()`: persiste el estado actual de zonas en YAML.
- `_apply_zones(zones)`: operacion principal del backend. Valida zonas, resuelve conversiones, rasteriza, publica, actualiza estado interno y devuelve exito o error.
- `_load_zones_from_disk()`: lee el YAML de disco y llama `_apply_zones()`. Es el punto de entrada para bootstrapping y recarga.
- `load_initial_zones()`: envoltorio de arranque. Existe para separar la inicializacion del nodo de la carga inicial de zonas.
- `_zone_msg_to_dict(zone_msg)`: adapta un mensaje `NoGoZone` a estructura Python serializable para persistencia o respuesta de servicios.
- `_zone_dict_to_msg(zone)`: hace la conversion inversa hacia mensaje ROS.
- `_on_set_zones(request, response)`: callback del servicio de escritura de zonas. Valida, aplica y persiste.
- `_on_get_state(request, response)`: callback del servicio de lectura de estado. Devuelve zonas actuales, si hay mascara lista y de donde provino.
- `_on_reload_zones(request, response)`: callback de recarga desde archivo. Es util cuando el usuario edita el YAML a mano.
- `main()`: entry point del backend keepout.

### `navegacion_gps/nav_command_server.py`

Rol general:
Es la puerta de entrada programatica a la navegacion. Convierte goals GPS a `NavigateToPose`, gestiona modo manual, expone servicios y publica telemetria unificada.

- `NavCommandServerNode.__init__()`: declara parametros, crea servicios, action client de Nav2, clientes `fromLL`, publishers de teleop y telemetria, subscribers de GPS y `cmd_vel_safe`, y timers como el watchdog del modo manual.
- `_wait_for_future(future, timeout_sec)`: helper de espera con timeout para llamadas async de ROS 2 que el nodo quiere usar de manera sincronica.
- `_call_from_ll(lat, lon)`: convierte coordenadas geograficas a `map`, con reintentos y fallback entre servicios.
- `_resolve_fromll_client()`: elige el cliente `fromLL` disponible.
- `_maybe_log_active_fromll(service_name)`: registra cambios del servicio `fromLL` activo.
- `_yaw_to_quaternion(yaw_deg)`: convierte yaw en grados a un `Quaternion` ROS para goals de Nav2.
- `_cmd_vel_safe_payload_locked()`: serializa la ultima velocidad segura conocida a un diccionario; esta pensada para ejecutarse bajo lock.
- `_manual_control_payload_locked()`: serializa el estado del modo manual y su ultimo comando.
- `_fill_get_state_response(response)`: rellena la respuesta del servicio `GetNavState` usando el estado interno actual del nodo.
- `_publish_telemetry(force=False)`: publica el mensaje de telemetria consolidado del backend. Respeta limite de frecuencia salvo que se fuerce una emision inmediata.
- `_on_gps_fix(msg)`: actualiza la ultima posicion GPS del robot y dispara telemetria.
- `_on_cmd_vel_safe(msg)`: actualiza el ultimo comando seguro efectivamente producido por la capa de navegacion y seguridad.
- `_on_teleop_cmd(msg)`: recibe `Twist` de teleop desde la web y solo lo reenvia si el modo manual esta habilitado. Este control evita que un topic de teleop se convierta en actuacion accidental cuando el sistema sigue en automatico.
- `_publish_manual_twist(linear_x, angular_z)`: construye y publica el `Twist` manual concreto.
- `_publish_manual_stop()`: publica un `Twist` cero para detener el robot manualmente.
- `send_nav2_goal(lat, lon, yaw_deg=0.0)`: convierte lat/lon a `map`, construye el `NavigateToPose.Goal` y lo envia al action server de Nav2.
- `_on_goal_result_done(future)`: callback del resultado del goal. Libera el handle activo, actualiza banderas y publica telemetria.
- `cancel_current_goal()`: cancela el goal activo si existe.
- `apply_brake()`: cancela el goal y publica varios `Twist` cero para aumentar la probabilidad de frenado efectivo aun ante perdidas o latencia.
- `set_manual_mode(enabled)`: activa o desactiva el modo manual. Al activarlo suele cancelar el goal automatico; al desactivarlo limpia comandos residuales.
- `set_manual_cmd(linear_x, angular_z)`: valida y aplica un comando manual, registrando tambien el tiempo de llegada para el watchdog.
- `_manual_watchdog_tick()`: si el modo manual esta activo pero los comandos dejaron de llegar, publica stop automaticamente.
- `_on_set_goal(request, response)`: callback del servicio para mandar un goal GPS.
- `_on_cancel_goal(request, response)`: callback del servicio para cancelar goal.
- `_on_brake(request, response)`: callback del servicio de freno.
- `_on_set_manual_mode(request, response)`: callback del servicio que activa o desactiva control manual.
- `_on_get_state(request, response)`: callback del servicio que expone el estado completo del backend.
- `main()`: entry point con `MultiThreadedExecutor`.

### `navegacion_gps/nav_snapshot_server.py`

Rol general:
Genera snapshots PNG del entorno de navegacion combinando costmaps, keepout, plan, scan, footprint y markers del `collision_monitor`.

- `NavSnapshotServerNode.__init__()`: declara parametros de render, crea el servicio principal, se subscribe a todas las capas que pueden aparecer en la imagen y arma el listener TF.
- `_on_local_costmap(msg)`: cachea el costmap local.
- `_on_global_costmap(msg)`: cachea el costmap global.
- `_on_keepout_mask(msg)`: cachea la mascara keepout.
- `_on_local_footprint(msg)`: cachea el footprint local del robot.
- `_on_stop_zone(msg)`: cachea la zona de stop publicada por `collision_monitor`.
- `_on_collision_polygons(msg)`: cachea el `MarkerArray` con poligonos y figuras de `collision_monitor`.
- `_on_scan(msg)`: cachea el `LaserScan`.
- `_on_plan(msg)`: cachea el plan actual de Nav2.
- `_on_get_snapshot(request, response)`: callback del servicio. Orquesta la construccion de la imagen, la codifica y rellena la respuesta.
- `_dict_to_layers(layers)`: convierte un diccionario Python de flags de capas al mensaje `NavSnapshotLayers`.
- `_build_snapshot_payload(...)`: funcion central del render. Elige ventana, recopila capas disponibles, dibuja la composicion final y empaqueta bytes PNG mas metadatos.
- `_resolve_robot_position(local_costmap, local_frame)`: intenta ubicar el robot en el frame de la ventana usando TF; si no puede, usa un fallback razonable.
- `_lookup_transform(target_frame, source_frame)`: wrapper tolerante de TF2 que retorna `None` si no encuentra transform valida.
- `_transform_2d_from_tf(tf, x, y)`: aplica traslacion y rotacion 2D a puntos o arrays.
- `_grid_data_top_left(grid)`: reorganiza los datos del `OccupancyGrid` a un array 2D orientado como imagen.
- `_sample_grid_to_window(grid, window, border_value)`: remuestrea un `OccupancyGrid` en la ventana elegida del snapshot. Si hace falta, transforma entre frames.
- `_occupancy_to_color(occ)`: traduce valores de occupancy a colores BGR para poder dibujar el mapa base.
- `_overlay_keepout(canvas, keepout_cost)`: mezcla sobre el canvas una capa roja semitransparente segun el costo keepout.
- `_world_to_px(x, y, window)`: convierte coordenadas del mundo a pixeles del snapshot.
- `_transform_points_2d(pts_xy, src_frame, tgt_frame)`: transforma conjuntos de puntos entre frames usando TF.
- `_draw_polyline(canvas, pts_xy, window, color_bgr, thickness, closed)`: dibuja una polilinea genrica en el canvas.
- `_draw_polygon_stamped(canvas, poly_msg, window, color_bgr, thickness)`: version especializada para `PolygonStamped`.
- `_draw_collision_markers(canvas, msg, window)`: interpreta `MarkerArray` del `collision_monitor` y dibuja lineas, poligonos o circulos segun el tipo de marker.
- `_draw_scan(canvas, scan, window)`: transforma el `LaserScan` a puntos del mundo y los dibuja.
- `_draw_path(canvas, path, window, color_bgr, thickness)`: dibuja el plan de Nav2.
- `_draw_global_inset(canvas, global_costmap, plan, keepout_mask)`: crea una miniatura del costmap global para dar contexto al snapshot local.
- `_grid_world_to_pixel(grid, x, y)`: helper para mapear coordenadas metricas a pixeles dentro de un `OccupancyGrid` especifico.
- `main()`: entry point del servicio de snapshots.

### `navegacion_gps/test/test_keepout_mask_utils.py`

Rol general:
Pruebas unitarias de las funciones puras del backend keepout.

- `test_rasterize_core_fills_polygon()`: verifica que un poligono simple se rasterice como area ocupada y no aparezca ni recortado ni fuera del grid.
- `test_rasterize_reports_outside_zone()`: comprueba que una zona completamente fuera del grid sea reportada como `outside` y no pinte celdas ocupadas.
- `test_exponential_gradient_decreases_with_distance()`: valida que el gradiente keepout realmente decrezca al alejarse del nucleo.
- `test_outside_radius_is_zero()`: verifica que el gradiente se corte en cero fuera del radio configurado.

### `navegacion_gps/test/test_flake8.py`

- `test_flake8()`: ejecuta el check de estilo `flake8` sobre el paquete.

### `navegacion_gps/test/test_pep257.py`

- `test_pep257()`: ejecuta el chequeo de docstrings PEP 257.

### `navegacion_gps/test/test_copyright.py`

- `test_copyright()`: verifica cabeceras o licencias donde corresponde.

---

## map_tools

Paquete que conecta la UI web con ROS 2. Su pieza central es un gateway WebSocket que habla con keepout, navegacion, teleop y snapshots.

### `map_tools/launch/no_go_editor.launch.py`

Rol general:
Launch del backend web.

- `generate_launch_description()`: declara argumentos de host, puerto, topics y nombres de servicios, y levanta `web_zone_server` con esa parametrizacion.

### `map_tools/web_zone_server.py`

Rol general:
Gateway ROS 2 <-> WebSocket. Es el backend que la pagina web usa para consultar estado, editar zonas, mandar goals, frenar, teleoperar y pedir snapshots.

#### `WebZoneServerNode`

- `WebZoneServerNode.__init__(loop)`: declara parametros de red, timeouts, nombres de servicios y topics; crea subscribers, clientes de servicio, publisher de teleop y las estructuras internas del estado compartido.
- `add_client(ws)`: agrega un WebSocket al conjunto de clientes conectados y actualiza logs.
- `remove_client(ws)`: elimina un cliente desconectado.
- `snapshot_state()`: devuelve un diccionario con el estado consolidado del backend, incluyendo zonas, disponibilidad de mascara, pose robot, velocidad segura y estado manual.
- `_build_nav_telemetry_payload()`: prepara un payload sintetico de telemetria para broadcast.
- `_broadcast(payload)`: envia un mismo JSON a todos los clientes y elimina conexiones caidas. Es el mecanismo de push de estado hacia la UI.
- `_on_gps_fix(msg)`: actualiza la pose robot en coordenadas GPS y, si paso el intervalo minimo, dispara un broadcast de `robot_pose`.
- `_on_nav_telemetry(msg)`: actualiza el estado de telemetria de navegacion, incluyendo `cmd_vel_safe`, modo manual y si hay goal activo.
- `_wait_for_future(future, timeout_s)`: helper sincronico para esperar un future ROS.
- `_call_service(client, request, timeout_s)`: envoltorio generico para invocar servicios desde el backend.
- `_zone_dict_to_msg(zone)`: traduce un diccionario JSON recibido por la web a mensaje ROS `NoGoZone`.
- `_zone_msg_to_dict(zone_msg)`: traduce un `NoGoZone` ROS a diccionario JSON serializable.
- `_update_keepout_state(response)`: actualiza cache local de zonas, mascara y fuente de mascara a partir de la respuesta del backend keepout.
- `_update_nav_state(response)`: actualiza cache local del estado de navegacion.
- `get_keepout_state()`: consulta al backend keepout y actualiza cache local.
- `set_keepout_zones(zones)`: envia nuevas zonas al backend keepout y devuelve si hubo publicacion efectiva.
- `reload_keepout_zones()`: fuerza recarga de zonas desde disco.
- `get_nav_state()`: consulta el backend de navegacion.
- `set_nav_goal(lat, lon, yaw_deg)`: llama al servicio que manda un goal GPS.
- `cancel_nav_goal()`: cancela el goal activo via servicio.
- `brake_nav()`: invoca el freno de emergencia del backend de navegacion.
- `set_manual_mode(enabled)`: habilita o deshabilita modo manual.
- `set_manual_cmd(linear_x, angular_z)`: publica teleop manual si el backend lo permite.
- `get_nav_snapshot()`: pide un snapshot al servicio correspondiente, decodifica bytes si hace falta y arma un payload listo para la web.
- `bootstrap_backend_state()`: consulta keepout y navegacion al inicio para que el primer cliente WebSocket no arranque a ciegas.

#### `WebSocketApi`

- `WebSocketApi.__init__(node)`: guarda la referencia al nodo ROS que resuelve toda la logica de backend.
- `handle(ws, path=None)`: administra el ciclo de vida de una conexion WebSocket: registra el cliente, le envia el estado inicial y luego procesa mensajes entrantes.
- `_handle_message(ws, raw)`: parsea el JSON de entrada, valida parametros y despacha segun `op`. Soporta operaciones como `get_state`, `set_zones_ll`, `set_goal_ll`, `cancel_goal`, `brake`, `set_manual_mode`, `set_manual_cmd` y `get_nav_snapshot`.

#### Entry points

- `async_main()`: inicializa ROS 2, arranca el executor en un hilo, hace bootstrap del estado y finalmente levanta el servidor WebSocket asincrono.
- `main()`: lanza `async_main()` y captura `KeyboardInterrupt`.

---

## sensores

Paquete que mete sensores reales al grafo ROS 2 y ofrece un dashboard web simple para telemetria.

### `sensores/launch/pixhawk.launch.py`

Rol general:
Launch del driver Pixhawk y, opcionalmente, del dashboard web.

- `generate_launch_description()`: declara puerto serie, baudrate, frames y el flag `launch_web`, luego crea `pixhawk_driver` y, si corresponde, `sensores_web`.

### `sensores/launch/rs16.launch.py`

Rol general:
Launch actual del driver RoboSense RS16 usado por el proyecto.

- `generate_launch_description()`: declara `config_path`, `rviz` y `use_cyclone_dds`, ajusta `RMW_IMPLEMENTATION` si hace falta y levanta `rslidar_sdk_node` mas RViz opcional.

### `sensores/pixhawk_driver.py`

Rol general:
Traduce MAVLink a ROS 2 y convierte convenciones de referencia de piloto automatico a convenciones ROS (`NED/FRD` -> `ENU/FLU`).

#### Helpers matematicos

- `quat_norm(q)`: normaliza un cuaternion a norma unitaria. Es importante porque varias conversiones posteriores asumen cuaterniones bien formados.
- `quat_mul(q1, q2)`: producto de Hamilton entre cuaterniones.
- `quat_conj(q)`: conjugado del cuaternion. Para cuaterniones unitarios sirve como inversa.
- `rotvec_by_quat(v, q)`: rota un vector 3D por cuaternion. Se usa para conversiones de orientacion y cambio de ejes.
- `ros_quat_from_tuple(q)`: adapta una tupla `(w, x, y, z)` a `geometry_msgs/Quaternion`.
- `vec_ned_to_enu(v_ned)`: cambia un vector del mundo NED a ENU.
- `vec_frd_to_flu(v_frd)`: cambia un vector del frame corporal FRD a FLU.
- `quat_from_rotation_matrix(R)`: convierte una matriz de rotacion 3x3 a cuaternion.
- `rotation_matrix_from_quat(q)`: convierte un cuaternion a matriz de rotacion.
- `mat_mul(A, B)`: multiplica dos matrices 3x3. Existe para mantener el modulo autocontenido sin depender de `numpy`.
- `transpose(A)`: transpone una matriz 3x3.
- `quat_ned_frd_to_enu_flu(q_ned_frd)`: conversion clave del paquete. Toma la actitud de Pixhawk en convencion autopiloto y la lleva a la convencion esperada por ROS.

#### Nodo MAVLink

- `PixhawkMavlinkNode.__init__()`: abre la conexion MAVLink, declara parametros de frames y tasas de mensajes, crea publishers ROS y reserva caches de datos parciales.
- `_set_message_rate(msg_name, hz)`: pide al Pixhawk una frecuencia de emision concreta para un tipo de mensaje MAVLink.
- `_spin_once()`: drena mensajes pendientes del enlace MAVLink y los despacha a handlers especializados.
- `_handle_scaled_imu(msg)`: procesa acelerometro y giroscopo, convirtiendo de FRD a FLU.
- `_handle_attitude_quaternion(msg)`: procesa la actitud del autopiloto y las velocidades angulares, convirtiendolas a la convencion ROS.
- `_handle_local_position_ned(msg)`: convierte posicion y velocidad locales desde NED a ENU.
- `_handle_gps_raw_int(msg)`: arma y publica `NavSatFix` a partir del GPS bruto de MAVLink.
- `_publish_imu_if_ready()`: publica `Imu` solo cuando ya hay suficientes piezas coherentes para hacerlo.
- `_publish_odom_if_ready()`: publica `Odometry` y `TwistStamped` cuando hay posicion y velocidad consistentes.
- `main(args=None)`: entry point del driver.

### `sensores/web_server.py`

Rol general:
Servidor HTTP + WebSocket para ver telemetria de Pixhawk en navegador.

- `_stamp_to_float(stamp)`: convierte un timestamp ROS a segundos float.
- `PixhawkWebServer.__init__()`: crea las subscripciones a sensores, inicializa estructuras de datos compartidas y arranca los servidores HTTP y WebSocket.
- `_load_html(html_path)`: lee el HTML del dashboard desde disco.
- `_start_http_server(host, port)`: crea el servidor HTTP en un hilo daemon.
- `Handler.do_GET()`: metodo del handler HTTP interno; sirve `index.html`, JSON de datos o `404` segun la ruta pedida.
- `Handler._send_response(code, content_type, body)`: helper de respuesta HTTP para el handler interno.
- `Handler.log_message(format, *args)`: silencia o simplifica el logging del servidor HTTP base.
- `_get_snapshot()`: serializa el estado actual del dashboard a JSON.
- `_start_ws_server(host, port)`: crea el loop `asyncio` y el hilo donde correra el WebSocket.
- `_run_ws_loop(host, port)`: instala el event loop y ejecuta la corrutina principal.
- `_ws_main(host, port)`: levanta el servidor WebSocket y la tarea de broadcast periodico.
- `_ws_handler(websocket)`: agrega y quita clientes WebSocket.
- `_ws_broadcast()`: envia el snapshot JSON de sensores a todos los clientes cada cierto intervalo.
- `_imu_cb(msg)`: actualiza el bloque `imu` del dashboard.
- `_gps_cb(msg)`: actualiza el bloque `gps`.
- `_velocity_cb(msg)`: actualiza el bloque de velocidades.
- `_odom_cb(msg)`: actualiza el bloque de odometria.
- `destroy_node()`: detiene servidores auxiliares antes de destruir el nodo ROS.
- `main(args=None)`: entry point del dashboard.

### `rslidar_sdk/launch/start.py`

Rol general:
Launch heredado del driver RoboSense.

- `generate_launch_description()`: crea un `rslidar_sdk_node` con un `config_path` placeholder y abre RViz. Es mas una plantilla antigua que el camino recomendado del workspace.

### `rslidar_sdk/launch/elequent_start.py`

Rol general:
Launch antiguo para una API previa de ROS 2.

- `generate_launch_description()`: levanta `rslidar_sdk_node` y RViz usando una sintaxis historica de `launch_ros`.

### `rslidar_sdk/launch/humble_start.py`

Rol general:
Launch heredado que intenta preparar Cyclone DDS automaticamente.

- `install_cyclone_dds()`: comprueba si el paquete de Cyclone DDS esta instalado, y si no lo esta intenta instalarlo via `sudo apt-get`. Es una funcion invasiva y claramente historica; no es la opcion preferida en este repo.
- `generate_launch_description()`: si detecta ROS 2 Humble intenta forzar Cyclone DDS, luego levanta el nodo de LiDAR y RViz.

---

## controller_server

Paquete de actuacion real. Convierte `cmd_vel_safe` en un protocolo binario UART hacia el ESP32 y publica estado y telemetria del enlace.

### `controller_server/launch/controller_server.launch.py`

Rol general:
Launch minimo del actuador real.

- `generate_launch_description()`: crea un unico nodo `controller_server_node` con parametros de puerto, baudrate, frecuencia de TX, limites de direccion y politicas de conversion desde `cmd_vel`.

### `controller_server/control_logic.py`

Rol general:
Modulo puro de logica. No depende de ROS; recibe `linear_x` y `angular_z` y devuelve un comando listo para bajar al nivel UART.

#### Tipos

- `DesiredCommand`: dataclass que representa el comando deseado ya convertido a `drive_enabled`, `estop`, `speed_mps`, `steer_pct` y `brake_pct`.
- `ArbitrationResult`: dataclass que representa el resultado de arbitracion del comando efectivo, incluyendo fuente y frescura.

#### Funciones

- `clamp(value, low, high)`: limitador generico usado por el resto del modulo.
- `safe_command()`: devuelve un `DesiredCommand` completamente seguro, pensado para watchdogs y timeouts.
- `command_from_cmd_vel(...)`: traduce un `Twist` a comando de actuacion. Aplica saturacion de velocidad, limite de reversa, deadband, velocidad minima efectiva para vencer inercia, normalizacion de direccion, inversion opcional del servo y politicas de freno/estop.
- `select_effective_command(now_s, auto_cmd, auto_stamp_s, auto_timeout_s)`: decide si el ultimo comando automatico sigue fresco o si ya vencio el watchdog y debe reemplazarse por `safe_command()`.

### `controller_server/controller_server_node.py`

Rol general:
Nodo ROS 2 que consume `/cmd_vel_safe`, usa `control_logic.py` para traducirlo a comando de actuacion y lo entrega al `CommsClient` UART.

- `_load_comms_client_class()`: import diferido del `CommsClient`. Mantiene desacoplado el modulo principal del backend serial hasta el momento de instanciacion.
- `ControllerServerNode.__init__()`: declara parametros del enlace serial y de conversion `cmd_vel -> UART`, inicializa estado interno, arranca el `CommsClient`, crea subscriber a `/cmd_vel_safe`, publishers de estado y telemetria, y timers de control y telemetria.
- `_on_cmd_vel_safe(msg)`: convierte el `Twist` recibido a `DesiredCommand`, lo guarda como ultimo comando automatico y registra su timestamp.
- `_apply_to_controller(cmd)`: copia un `DesiredCommand` al `CommsClient`, campo por campo.
- `_control_tick()`: resuelve el comando efectivo usando `select_effective_command()`, aplica politicas de `estop`, lo baja al cliente UART y publica un JSON de estado del controlador.
- `_telemetry_tick()`: toma la telemetria mas reciente del ESP32, las estadisticas del enlace y publica un JSON consolidado.
- `destroy_node()`: detiene el cliente UART antes de destruir el nodo ROS.
- `main(args=None)`: entry point del actuador.

### `controller_server/rpy_esp32_comms/controller.py`

Rol general:
Representa el estado de comando deseado del lado Raspberry Pi.

- `_clamp(value, low, high)`: helper de saturacion.
- `CommandState`: dataclass central del protocolo, con campos para traccion, `estop`, direccion, velocidad y freno, mas limites maximos de avance y reversa.
- `CommandState.set_speed_mps(value)`: aplica clamp a la velocidad teniendo en cuenta avance y reversa.
- `CommandState.set_steer_pct(value)`: limita la direccion a `[-100, 100]`.
- `CommandState.set_brake_pct(value)`: limita el freno a `[0, 100]`.
- `CommandState.set_drive_enabled(enabled)`: habilita o deshabilita traccion.
- `CommandState.set_estop(enabled)`: activa o desactiva la parada de emergencia.
- `CommandState.safe_reset()`: lleva el estado a condicion segura.
- `CommandState.to_dict()`: serializa todo el estado a diccionario.

### `controller_server/rpy_esp32_comms/telemetry.py`

Rol general:
Define la estructura de telemetria recibida desde el ESP32 y los bits de estado derivados.

- `ControlSource`: enum de la fuente de control reportada por el ESP32 (`NONE`, `PI`, `RC`, `TEL`).
- `Telemetry`: dataclass con campos crudos de la telemetria.
- `Telemetry.ready`: propiedad derivada; indica si el ESP32 esta listo.
- `Telemetry.estop_active`: indica si el ESP32 esta en emergencia.
- `Telemetry.failsafe_active`: indica si el watchdog del microcontrolador se disparo.
- `Telemetry.pi_fresh`: indica si la ultima trama de la Pi fue valida y reciente.
- `Telemetry.control_source`: decodifica la fuente de control activa.
- `Telemetry.overspeed_active`: indica si el ESP32 detecta sobrevelocidad.
- `Telemetry.as_dict()`: serializa tanto campos crudos como propiedades derivadas.

### `controller_server/rpy_esp32_comms/protocol.py`

Rol general:
Implementa el protocolo binario UART Pi <-> ESP32.

- `crc8_maxim(data)`: calcula el CRC-8/MAXIM usado por ambas direcciones del protocolo.
- `encode_pi_frame(state)`: empaqueta un `CommandState` en una trama de 7 bytes, codificando version, flags, direccion, velocidad y freno.
- `decode_esp_frame(frame, rx_monotonic_s=None)`: valida header y CRC del frame ESP32, interpreta sentinelas de no-disponible y devuelve un objeto `Telemetry`.
- `EspFrameParser.__init__()`: inicializa el parser streaming y sus contadores de resincronizacion.
- `EspFrameParser.reset()`: limpia buffer y estado acumulado.
- `EspFrameParser.feed(data)`: recibe un chunk arbitrario de bytes, busca headers validos, re-sincroniza ante basura o CRC erroneo y extrae frames completos validos.
- `decode_stream_chunks(chunks)`: helper de conveniencia para pruebas; procesa multiples chunks y devuelve la telemetria resultante.

### `controller_server/rpy_esp32_comms/transport.py`

Rol general:
Encapsula el puerto serial real y la mecanica de transmision/recepcion en hilos.

#### Tipos

- `CommsStats`: dataclass con contadores de TX correcto, errores de TX, RX valido, errores CRC y descartes de parsing.

#### Cliente serial

- `CommsClient.__init__(...)`: valida parametros, prepara locks, crea el `CommandState`, inicializa contadores y deja el puerto serial aun sin abrir.
- `CommsClient.start()`: abre el puerto serial, resetea buffers, resetea estado a seguro y arranca los hilos TX y RX.
- `CommsClient.stop()`: pone el estado en seguro, detiene los hilos, manda algunas tramas seguras extra y cierra el puerto.
- `set_speed_mps(value)`: setter thread-safe de velocidad.
- `set_steer_pct(value)`: setter thread-safe de direccion.
- `set_brake_pct(value)`: setter thread-safe de freno.
- `set_drive_enabled(value)`: setter thread-safe de traccion.
- `set_estop(value)`: setter thread-safe de emergencia.
- `set_log_enabled(enabled)`: habilita logs crudos de TX y RX por consola.
- `get_latest_telemetry()`: retorna la ultima telemetria conocida.
- `get_command_state()`: retorna una copia del estado de comando deseado.
- `get_stats()`: retorna una copia de estadisticas del enlace.
- `_set_safe_state()`: fuerza el estado seguro bajo lock.
- `_state_snapshot()`: toma una foto inmutable del `CommandState` actual para transmitir sin depender del lock durante toda la codificacion.
- `_serial_write(payload)`: escribe bytes al serial y falla si el puerto no esta listo.
- `_write_current_frame()`: codifica y transmite el estado actual, actualizando contadores de TX.
- `_send_safe_frames(count)`: manda varias tramas seguras consecutivas, util al cerrar o ante transiciones delicadas.
- `_tx_loop()`: hilo periodico que transmite frames a `tx_hz`.
- `_rx_loop()`: hilo que lee bytes, usa `EspFrameParser`, actualiza telemetria y contadores, y opcionalmente imprime logs decodificados.

### `controller_server/rpy_esp32_comms/cli.py`

Rol general:
CLI interactiva para probar el protocolo UART sin ROS 2.

#### Logging de sesion

- `SessionLogger.__init__(path)`: prepara un archivo JSONL opcional para guardar cada comando ejecutado y la telemetria asociada.
- `SessionLogger.write(event, command, telemetry, extra=None)`: agrega una linea JSON con timestamp UTC y contexto del comando.
- `SessionLogger.close()`: cierra el archivo de log si estaba abierto.

#### Helpers de CLI

- `_parse_on_off(raw)`: traduce `on` o `off` a booleano y falla si la entrada es invalida.
- `_format_telemetry(telemetry)`: renderiza la telemetria en una linea humana para consola.
- `_watch_loop(client, stop_event, enabled_ref, period_s)`: hilo auxiliar que imprime telemetria periodicamente cuando `watch` esta habilitado.

#### Flujo principal

- `run_cli(args)`: arranca el `CommsClient`, inicia el hilo de watch, entra en un loop REPL y soporta comandos como `status`, `drive`, `estop`, `speed`, `steer`, `brake`, `watch`, `log` y `quit`.
- `build_arg_parser()`: declara los argumentos CLI del cliente UART.

### `controller_server/rpy_esp32_comms/__main__.py`

Rol general:
Punto de entrada para ejecutar la CLI como modulo Python.

- `main()`: crea el parser, parsea argumentos y delega en `run_cli()`.

### `controller_server/controller/artifacts/run_uart_e2e.py`

Rol general:
Script historico de prueba extremo a extremo entre Raspberry Pi y ESP32 usando UART y un canal telnet hacia el microcontrolador.

#### Captura telnet

- `TelnetCapture.__init__(host, port=23, timeout_s=3.0)`: prepara la captura de logs remotos del ESP32.
- `TelnetCapture.connect()`: abre el socket, lanza el hilo lector y deja un margen para que empiecen a llegar lineas.
- `TelnetCapture.close()`: corta el hilo lector y cierra el socket.
- `TelnetCapture.send(cmd)`: envia un comando ASCII por telnet.
- `TelnetCapture.line_count()`: retorna cuantas lineas de log hay acumuladas.
- `TelnetCapture.lines_since(index)`: devuelve una copia de las lineas nuevas desde cierto indice.
- `TelnetCapture._append_line(line)`: agrega una linea con timestamp local.
- `TelnetCapture._reader_loop()`: lee del socket, recompone lineas, maneja parciales y las acumula.

#### Helpers del experimento

- `telemetry_to_dict(tlm)`: serializa la telemetria si existe.
- `snapshot(client)`: toma una instantanea del estado deseado, telemetria y estadisticas del cliente UART.
- `capture_status(capture, extra_cmds=None, wait_s=0.35)`: dispara `comms.status` y comandos extra, espera un poco y devuelve las lineas nuevas de telnet.

#### Flujo principal

- `main()`: ejecuta un escenario de pasos de velocidad, direccion, freno y `estop`, captura snapshots y logs telnet, y guarda resultados JSON y log de lineas para analisis posterior.

### `controller_server/controller/tests/test_protocol.py`

Rol general:
Pruebas del protocolo UART.

- `make_esp_frame(status, speed_raw, steer_raw, brake)`: helper de test que construye una trama ESP32 valida con CRC correcto.
- `test_encode_pi_frame_fields_and_crc()`: verifica que `encode_pi_frame()` arme bytes y CRC correctos.
- `test_decode_esp_frame_ok()`: verifica el camino nominal de decodificacion.
- `test_decode_esp_frame_sentinels()`: comprueba que sentinelas de "N/A" se traduzcan a `None`.
- `test_decode_esp_frame_bad_crc_raises()`: asegura que un CRC incorrecto dispare error.
- `test_parser_resync_after_corrupt_bytes()`: prueba la resincronizacion del parser ante flujo corrupto.
- `test_parser_does_not_drop_on_payload_0x55()`: valida que un byte `0x55` dentro del payload no rompa el parser.
- `test_encode_pi_frame_negative_speed_sets_rev_req()`: verifica el flag de reversa al codificar velocidad negativa.
- `test_encode_pi_frame_zero_speed_clears_rev_req()`: verifica que velocidad cero no marque reversa.

### `controller_server/controller/tests/test_controller.py`

- `test_state_clamps()`: valida los clamps de `CommandState`.
- `test_safe_reset()`: valida que `safe_reset()` deje el estado en condicion segura.

---

## tools

Scripts utilitarios del workspace que no forman parte del runtime principal, pero si de los ensayos y verificaciones de campo.

### `tools/closed_loop_step_publisher.py`

Rol general:
Publicador deterministico de escalones sobre un topic ROS, pensado para ensayos de lazo cerrado.

- `Step`: dataclass inmutable que representa una etapa del experimento (`label`, velocidad, objetivo km/h y duracion).
- `_build_parser()`: define argumentos CLI como topic, frecuencia y CSV de eventos.
- `_write_event(writer, step, start_epoch)`: escribe en CSV el inicio de cada etapa para luego correlacionar comandos con logs externos.
- `main()`: ejecuta la secuencia de pasos, publica el `Twist` a frecuencia fija, registra transiciones y emite frames finales de stop.

### `tools/uart_step_sender.py`

Rol general:
Script deterministico de envio UART directo al ESP32, sin ROS, con inspeccion simple de telemetria binaria.

- `UartStep`: dataclass de una etapa del ensayo UART.
- `crc8_maxim(data)`: version local del CRC usado por el script.
- `int8_to_u8(value)`: adapta un entero firmado a representacion `uint8`, validando rango.
- `build_command_frame(steer, accel, brake, flags)`: construye una trama UART simple del script de ensayo.
- `parse_status_frames(rx_buffer, stats)`: escanea el buffer de recepcion, detecta cabeceras, valida CRC y extrae pares `(status, telemetry)` validos.
- `_build_parser()`: define argumentos CLI del ensayo UART.
- `main()`: abre el serial, ejecuta la secuencia de pasos, transmite frames a frecuencia fija, parsea respuestas, imprime estadisticas y opcionalmente falla si no hay telemetria durante fases con aceleracion.

---

## tests y chequeos de calidad

Ademas de las pruebas ya descritas dentro de sus paquetes, el workspace contiene tests de calidad muy pequenos cuyo comportamiento es practicamente obvio por nombre:

### `controller_server/test/test_control_logic.py`

- `test_command_from_cmd_vel_clamps_and_scales()`: valida saturacion de velocidad y direccion en avance.
- `test_command_from_cmd_vel_negative_speed_maps_to_reverse()`: valida mapeo de velocidad negativa a reversa.
- `test_command_from_cmd_vel_negative_speed_is_clamped_by_max_reverse()`: valida el limite maximo de reversa.
- `test_command_from_cmd_vel_zero_speed_brakes()`: valida que velocidad cero active freno y `estop`.
- `test_command_from_cmd_vel_invert_steer()`: valida inversion opcional de direccion.
- `test_command_from_cmd_vel_below_deadband_maps_to_zero()`: valida supresion de microcomandos.
- `test_command_from_cmd_vel_between_deadband_and_min_maps_to_min()`: valida salto al minimo efectivo.
- `test_command_from_cmd_vel_above_min_keeps_value()`: valida que una velocidad ya suficiente no sea alterada.
- `test_command_from_cmd_vel_min_effective_is_clamped_by_max_speed()`: valida que el minimo efectivo no exceda la maxima configurada.
- `test_select_effective_command_auto_timeout()`: valida el watchdog del comando automatico.
- `test_select_effective_command_auto_fresh()`: valida el caso nominal del watchdog.

### `controller_server/test/test_flake8.py`

- `test_flake8()`: ejecuta `flake8` sobre el paquete.

### `controller_server/test/test_pep257.py`

- `test_pep257()`: ejecuta el check de docstrings.

### `controller_server/test/test_copyright.py`

- `test_copyright()`: verifica cabeceras o licencias.

### `navegacion_gps/test/test_flake8.py`

- `test_flake8()`: ejecuta `flake8` sobre `navegacion_gps`.

### `navegacion_gps/test/test_pep257.py`

- `test_pep257()`: ejecuta el check de docstrings sobre `navegacion_gps`.

### `navegacion_gps/test/test_copyright.py`

- `test_copyright()`: verifica cabeceras o licencias del paquete.

---

## archivos sin funciones o con logica minima

Estos archivos siguen siendo utiles para orientarse, pero no aportan funciones que documentar en profundidad:

- `__init__.py` de los paquetes Python: solo marcan paquetes importables o reexportan simbolos.
- `setup.py`: describe instalacion y entry points, pero no contiene logica operacional central.
- varios `README.md`, YAML, RViz, worlds y URDF: son fundamentales para configurar el sistema, aunque no definen funciones Python.

---

## Cierre

Si lees este documento junto con:

- `README.md` para la vista de workspace y operaciones
- `real.launch.py` o `simulacion.launch.py` para el ensamblado del grafo
- `nav_command_server.py`, `keepout_manager.py`, `web_zone_server.py`, `controller_server_node.py` para el flujo completo

vas a tener una imagen bastante completa de como el proyecto pasa:

- de sensores a localizacion
- de localizacion a planificacion
- de planificacion a seguridad
- de seguridad a actuacion
- y de la web al robot real o a la simulacion

Este archivo esta pensado como referencia de estudio: cuando no recuerdes "que hacia exactamente este metodo", deberia ser el primer lugar al que vuelvas.
