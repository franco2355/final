# Diagnostico de navegacion

## Copia usada para comparar

- Carpeta actual: `/home/franco/german/aeye-ros-workspace/src/navegacion_gps`
- Copia "semana pasada": `/home/franco/german/aeye-ros-workspace/compare/navegacion_gps_semana_pasada`
- Origen de la copia: `/home/franco/aeye-ros-workspace/src/navegacion_gps`

## Que paso

La carpeta actual de `navegacion_gps` quedo en un estado intermedio de cambios locales + merge/autostash incompleto.

Evidencia:

- `git status` actual:
  - `UU config/dual_ekf_navsat_params.yaml`
  - `M package.xml`
  - `M setup.py`
  - archivos nuevos sin trackear en `navegacion_gps/`
- `git log` actual:
  - `main` local esta en `d0adec2`
  - `origin/main` esta 3 commits adelante (`261d83b`, `1c20f0b`, `f89d4ca`)
  - aparece `refs/stash`, consistente con un autostash/merge parcial

## Hallazgos fuertes

### 1. El YAML de localizacion esta roto

Archivo actual:

- `/home/franco/german/aeye-ros-workspace/src/navegacion_gps/config/dual_ekf_navsat_params.yaml`

Problema:

- tiene marcadores de conflicto git sin resolver:
  - `<<<<<<< Updated upstream`
  - `=======`
  - `>>>>>>> Stashed changes`

Impacto:

- la configuracion de `robot_localization/navsat_transform` ya no es un YAML valido
- eso por si solo puede romper o volver inconsistente el arranque de localizacion/navegacion

La copia de semana pasada no tiene ese problema.

### 2. Cambio fuerte en EKF/GPS respecto a semana pasada

Entre la copia vieja y la actual cambiaron estos parametros:

- `odom1_config`
  - antes: no fusionaba XY de `/odometry/gps`
  - ahora: si fusiona XY de `/odometry/gps`
- `odom1_pose_rejection_threshold`
  - antes: `1.0`
  - ahora: `25.0`

Impacto:

- aunque el YAML estuviera limpio, la localizacion hoy no se comporta igual que la semana pasada
- hubo un cambio real de estrategia en como entra el GPS al EKF global

### 3. La arquitectura nueva espera `nav_command_server`, pero `real.launch.py` no lo lanza

El stack web nuevo espera estos servicios:

- `/nav_command_server/set_goal_ll`
- `/nav_command_server/cancel_goal`
- `/nav_command_server/set_manual_mode`
- `/nav_command_server/get_state`

Eso aparece en:

- `/home/franco/german/aeye-ros-workspace/src/map_tools/map_tools/web_zone_server.py`

Pero en:

- `/home/franco/german/aeye-ros-workspace/src/navegacion_gps/launch/real.launch.py`

no aparece ningun `Node(... executable="nav_command_server" ...)`.

Impacto:

- la web/manual puede quedar levantada
- pero sin el nodo que arbitra manual/auto y expone servicios de navegacion
- eso deja el stack inconsistente

### 4. El paquete actual esta a medio migrar

En la actual se agregaron varias piezas nuevas respecto a la copia vieja:

- `zones_manager`
- `nav_command_server`
- `nav_snapshot_server`
- `joystick_node`
- dependencias nuevas en `package.xml`
- cambios grandes en `real.launch.py`

Impacto:

- la carpeta actual no es solo "la misma navegacion que antes"
- es una version mas nueva con integraciones nuevas, pero localmente quedo a medio estado

## Conclusion

La navegacion actual no parece fallar por un solo parametro aislado. Hay dos problemas estructurales:

1. `src/navegacion_gps` quedo roto por una integracion incompleta de cambios
2. la arquitectura nueva de web/manual/navegacion no esta cerrada del todo en `real.launch.py`

La causa mas directa y objetiva es el conflicto sin resolver en `dual_ekf_navsat_params.yaml`.

## Recomendacion

Si queres recuperar una base confiable para comparar o volver a arrancar:

1. usar la copia limpia en `compare/navegacion_gps_semana_pasada` como referencia
2. comparar y reintroducir cambios nuevos de a uno
3. resolver primero:
   - `dual_ekf_navsat_params.yaml`
   - integracion de `nav_command_server` en el launch real
