cmake_minimum_required(VERSION 3.8)
project(navegacion_gps_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/NoGoPoint.msg"
  "msg/NoGoZone.msg"
  "msg/NavSnapshotLayers.msg"
  "msg/NavTelemetry.msg"
  "srv/SetKeepoutZones.srv"
  "srv/GetKeepoutState.srv"
  "srv/SetNavGoalLL.srv"
  "srv/CancelNavGoal.srv"
  "srv/BrakeNav.srv"
  "srv/SetManualMode.srv"
  "srv/SetManualCmd.srv"
  "srv/GetNavState.srv"
  "srv/GetNavSnapshot.srv"
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
