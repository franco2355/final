# Instalación de ROS 2 para Joystick Xbox

Tu sistema: **Ubuntu Plucky (25.04)** → Instalar **ROS 2 Jazzy**

## Opción 1: Instalación automática (RECOMENDADA)

```bash
cd ~/german/aeye-ros-workspace
./install_ros2.sh
```

Seguir las instrucciones. Requiere sudo.

---

## Opción 2: Instalación manual paso a paso

### Paso 1: Configurar locale

```bash
sudo apt update
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
```

### Paso 2: Agregar repositorio ROS 2

```bash
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo curl -sSL https://repo.ros2.org/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu plucky main" | sudo tee /etc/apt/sources.list.d/ros2.list
```

### Paso 3: Instalar ROS 2 Jazzy

```bash
sudo apt update
sudo apt install ros-jazzy-desktop ros-jazzy-dev
```

(Esto descarga ~2GB, puede tomar 5-10 minutos)

### Paso 4: Instalar herramientas

```bash
sudo apt install python3-colcon-common-extensions
sudo apt install ros-jazzy-joy
```

### Paso 5: Agregar a ~/.bashrc (PERMANENTE)

```bash
echo "source /opt/ros/jazzy/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

---

## Verificar instalación

```bash
ros2 --version
```

Debe mostrar: `ROS 2 jazzy`

---

## Compilar navegacion_gps

```bash
cd ~/german/aeye-ros-workspace
colcon build --packages-select navegacion_gps
source install/setup.bash
```

---

## Verificar que todo funciona

```bash
./check_joystick.sh
```

Debe mostrar: **"✓ SISTEMA LISTO PARA USAR"**

---

## Ejecutar

```bash
./start_joystick.sh
```

---

## Problemas?

### Error: "sudo: apt command not found"
→ Ejecutar los comandos sin "sudo" (ya tienes permisos)

### Error: "E: Unable to locate package ros-jazzy..."
→ Verificar que agregaste el repositorio correctamente (Paso 2)

### Error: "ModuleNotFoundError: No module named 'rclpy'"
→ Ejecutar: `source /opt/ros/jazzy/setup.bash`

---

**Tiempo estimado:** 10-15 minutos (incluida descarga)
