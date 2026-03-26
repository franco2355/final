# RTK Testing Complete Guide

## Quick Start (5 minutes)

### 1. Build the package

```bash
cd ~/franco/german/aeye-ros-workspace
colcon build --packages-select sensores
source install/setup.bash
```

### 2. Start Pixhawk driver + NTRIP client in terminal 1

```bash
ros2 launch sensores pixhawk.launch.py
```

Expected output:
```
[pixhawk_driver]: Connecting MAVLink on /dev/ttyACM0 @ 921600...
[pixhawk_driver]: Heartbeat OK (sys=1, comp=0)
[pixhawk_driver]: Subscribed to /rtcm (Message)
[pixhawk_driver]: Node initialized.
```

### 3. Run RTK accuracy test in terminal 2

```bash
ros2 run sensores rtk_accuracy_test
```

The test will collect GPS samples for 60 seconds and print results.

---

## Detailed Test Procedures

### Test A: Verify RTK is working (before doing anything else)

**Objective:** Ensure RTK_FIXED is achievable

**Procedure:**

1. **Check GPS is alive**
   ```bash
   ros2 topic echo /gps/fix -n 1
   ```
   You should see: `status: {status: 0}` (not 0 is good, -1 means no fix)

2. **Check fix_type transitions**
   ```bash
   watch -n 0.5 "ros2 topic echo /gps/fix_type -n 1 | grep data"
   ```
   Should see: 0 → 1 → 2 → 3 → 5 → 6 (progression to RTK_FIXED)

3. **Check RTCM is arriving**
   ```bash
   ros2 topic hz /rtcm
   ```
   Should show 1-5 Hz message rate

4. **Check RTCM age**
   ```bash
   watch -n 1 "ros2 topic echo /gps/rtcm_age_s -n 1 | grep data"
   ```
   Should show: 0-2 seconds (indicates fresh corrections)

5. **If RTK doesn't converge after 2 minutes:**
   - Check: `ros2 topic echo /gps/rtcm_received_count` (should be increasing)
   - Check: `ros2 topic echo /gps/satellites_visible` (need > 8)
   - Check: `ros2 topic echo /gps/hdop` (should be < 2.0)

---

### Test B: Precision measurement (main test)

**Objective:** Quantify centimeter-level accuracy

**Procedure:**

1. **Wait for RTK convergence** (if not already RTK_FIXED)
   ```bash
   # Watch for fix_type = 6
   watch -n 0.5 "ros2 topic echo /gps/fix_type -n 1"
   ```

2. **Run 60-second test**
   ```bash
   ros2 run sensores rtk_accuracy_test
   ```

3. **Expected output** (RTK_FIXED):
   - Samples: 240+
   - Error: < 3 cm
   - 95% radius: < 0.5 cm
   - Classification: 🟢 EXCELLENT

4. **If error > 10 cm:**
   - Rerun test (variation is normal)
   - Check if RTK_FLOAT: likely not fully converged
   - Run longer test: `--ros-args -p duration_seconds:=180`

---

### Test C: RTK convergence time measurement

**Objective:** Measure how long RTK takes to converge

**Procedure:**

```bash
# Terminal 1: Watch fix_type with timestamp
ros2 topic echo /gps/fix_type | awk '{print systime()" "$0}'

# Terminal 2: Run test (shows progression)
ros2 run sensores rtk_accuracy_test --ros-args -p duration_seconds:=180
```

**Expected:**
- 0-5 sec: NO_GPS
- 5-15 sec: 3D_FIX
- 15-40 sec: RTK_FLOAT
- 40+ sec: RTK_FIXED

**If > 60 seconds to RTK_FIXED:**
- Weak satellite geometry (bad HDOP)
- Poor NTRIP signal (high latency)
- Check receiver firmware

---

### Test D: RTK stability test (30 minute continuous)

**Objective:** Verify RTK doesn't drop out unexpectedly

**Procedure:**

```bash
# Run very long test
ros2 run sensores rtk_accuracy_test --ros-args -p duration_seconds:=1800
```

**Expected:**
- Fix type stays at 6 (RTK_FIXED) throughout
- Error stays < 5 cm
- No "FIX_TYPE_CHANGED" warnings

**If fix type drops:**
- Check NTRIP network stability
- Check for multipath interference (move away from reflective surfaces)
- Check receiver temperature (some drift if it heats up)

---

### Test E: Comparing RTK vs standard GPS (if NTRIP can be disabled)

**Procedure:**

1. **Run test WITH RTK** (NTRIP connected)
   ```bash
   ros2 run sensores rtk_accuracy_test --ros-args -p duration_seconds:=60
   ```
   Record error and 95% radius

2. **Disable NTRIP** (stop ntrip_client or block `/rtcm`)

3. **Run test WITHOUT RTK** (pure 3D_FIX)
   ```bash
   ros2 run sensores rtk_accuracy_test --ros-args -p duration_seconds:=60
   ```

4. **Compare:**
   | Metric | With RTK | Without RTK |
   |--------|----------|-----------|
   | Error | 0-3 cm | 1-10 m |
   | 95% radius | 0.5 cm | 50-500 cm |
   | Ratio | 1x | 100-1000x worse |

---

## Interpreting Results

### Green (✓ EXCELLENT < 3cm)

**What it means:**
- RTK is working perfectly
- Precision is centimeter-level
- Suitable for: autonomous landing, precision payload delivery, survey work

**What to do:**
- Deploy with confidence
- Use this as baseline for future tests
- Monitor HDOP and satellites to ensure stability

### Yellow (🟡 GOOD 3-10cm)

**What it means:**
- RTK is working but not optimal
- Likely RTK_FLOAT (not yet fully converged)
- Precision is still good for most robots

**What to do:**
- Wait longer for RTK_FIXED (usually 30+ seconds)
- Check satellite count (need > 10 for best results)
- Move to clearer area if HDOP > 2.0
- Rerun test after convergence

### Orange (🟠 ACCEPTABLE 10-50cm)

**What it means:**
- RTK partially working or degraded
- Likely lost RTK during test
- Check for interference or signal loss

**What to do:**
- Investigate cause of RTK loss
- Run longer test to see when fix type changes
- Check RTCM age spikes
- Move away from RF sources

### Red (🔴 POOR > 50cm)

**What it means:**
- RTK is NOT working
- Stuck at 3D_FIX or worse
- Pure GPS accuracy (1-10 meters)

**What to do:**

1. **Check NTRIP connection:**
   ```bash
   ros2 topic echo /rtcm -n 5
   # Should see messages, not "No such topic"
   ```

2. **Check RTCM age:**
   ```bash
   ros2 topic echo /gps/rtcm_age_s
   # Should be < 2 seconds, not 999.0
   ```

3. **Check fix_type progression:**
   ```bash
   watch -n 0.5 "ros2 topic echo /gps/fix_type -n 1"
   # Should reach 5 or 6, not stuck at 3
   ```

4. **Check satellite count:**
   ```bash
   ros2 topic echo /gps/satellites_visible
   # Should be > 8
   ```

5. **Verify receiver is RTK-capable:**
   - Check hardware documentation
   - Ensure receiver is configured for RTK
   - Check for firmware updates

---

## Automated Testing Script

Save as `run_rtk_tests.sh`:

```bash
#!/bin/bash

# Run multiple RTK tests and collect statistics

echo "=== RTK Accuracy Test Suite ==="
echo "Running 5 consecutive 60-second tests..."
echo

for i in {1..5}; do
    echo ">>> Test $i of 5 <<<"
    ros2 run sensores rtk_accuracy_test --ros-args -p duration_seconds:=60 > /tmp/test_$i.log 2>&1

    # Extract key metrics
    grep "CLASSIFICATION" /tmp/test_$i.log
    grep "Standard Deviation" /tmp/test_$i.log
    grep "95% Radius" /tmp/test_$i.log
    echo

    sleep 5
done

echo "=== All tests complete ==="
echo "Logs saved to /tmp/test_*.log"
```

Run with:
```bash
chmod +x run_rtk_tests.sh
./run_rtk_tests.sh
```

---

## Diagnostic Flowchart

```
┌─ Is GPS fix working?
│  ├─ No  → Check Pixhawk connection, serial port
│  └─ Yes ↓
│
├─ Is fix_type reaching 3 (3D_FIX)?
│  ├─ No  → Check satellite count, clear sky view
│  └─ Yes ↓
│
├─ Is /rtcm topic receiving data?
│  ├─ No  → Start NTRIP client, check network
│  └─ Yes ↓
│
├─ Is RTCM age < 2 seconds?
│  ├─ No  → Check NTRIP latency, network delay
│  └─ Yes ↓
│
├─ Is fix_type reaching 5-6 (RTK)?
│  ├─ No  → Wait longer, check receiver firmware
│  └─ Yes ↓
│
└─ Run accuracy test
   ├─ Error < 5 cm     → ✓ RTK WORKING
   ├─ Error 5-50 cm    → ⚠️  Marginal (check HDOP)
   └─ Error > 50 cm    → ✗ RTK NOT WORKING
```

---

## Common Error Messages & Solutions

### "Not enough samples (need at least 5)"

```bash
# Terminal 1: Check if GPS is publishing
ros2 topic echo /gps/fix -n 1
# If empty, pixhawk_driver is not running or GPS not connected

# Solution:
# 1. Check Pixhawk USB cable
# 2. Verify serial port: ls -la /dev/ttyACM*
# 3. Restart pixhawk_driver
```

### "RTK_FIXED was never achieved"

```bash
# Terminal 1: Monitor fix type progression
watch -n 0.5 "ros2 topic echo /gps/fix_type -n 1 | grep data"

# Terminal 2: Monitor RTCM arrival
watch -n 1 "ros2 topic echo /gps/rtcm_age_s -n 1 | grep data"

# If RTCM age stays 999.0:
# NTRIP is not connected. Start NTRIP client.

# If fix_type stuck at 3:
# Wait longer (RTK can take 1-3 minutes on first convergence)
# Check HDOP: should be < 2.0
```

### "matplotlib not installed"

```bash
pip install matplotlib
# Then rerun test
```

### "Fix type changed during test"

```bash
# This means RTK lost convergence. Causes:
# 1. NTRIP disconnected
# 2. Receiver too hot/cold
# 3. Satellite geometry changed
# 4. RF interference

# Solution:
# 1. Check NTRIP: ros2 topic hz /rtcm
# 2. Move away from RF sources
# 3. Wait for better satellite geometry
# 4. Rerun test in better conditions
```

---

## Performance Expectations by Application

| Application | Required Accuracy | Recommended Fix | Test Duration |
|-------------|------------------|-----------------|---|
| Route following | 10-50 cm | RTK_FLOAT OK | 60s |
| Autonomous landing | < 5 cm | RTK_FIXED required | 120s |
| Precision survey | < 3 cm | RTK_FIXED required | 180s |
| Obstacle avoidance | 50-100 cm | 3D_FIX OK | 30s |
| Geofencing | 1-5 m | 3D_FIX OK | 30s |

---

## Files Generated

After each test, these files are created:

- `/tmp/rtk_accuracy_test.png` — Scatter plot visualization
- ROS2 logs in `~/.ros/log/` — Full node logs
- Terminal output — Test report (copy/paste to save)

---

## Next Steps

1. ✅ Verify RTK is working (Test A)
2. ✅ Measure precision (Test B)
3. ✅ Check convergence time (Test C)
4. ✅ Verify stability (Test D if possible)
5. ✅ Deploy with confidence

For questions or issues, refer to the troubleshooting section in `RTK_TEST_GUIDE.md`.
