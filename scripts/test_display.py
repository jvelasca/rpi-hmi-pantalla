"""Check all deps and test display app on Pi."""
import paramiko, time

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.88.211", port=22, username="pi", password="RaspberryB+2026!", timeout=15)

# Check evdev and websocket
cmd = "/home/pi/rpi_hmi/venv/bin/python3 -c 'import evdev; print(\"evdev OK\"); import websocket; print(\"ws OK\"); import requests; print(\"requests OK\")'"
stdin, stdout, stderr = c.exec_command(cmd)
print("[DEPS]", stdout.read().decode("utf-8","replace").strip())
err = stderr.read().decode("utf-8","replace").strip()
if err: print("[STDERR]", err[:300])

# Quick test run (5 sec timeout, mock mode to avoid DRM issues)
print("\n[RUNTEST] Running display app (5s)...")
cmd = "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi timeout 6 /home/pi/rpi_hmi/venv/bin/python3 display/app.py --debug 2>&1 || true"
stdin, stdout, stderr = c.exec_command(cmd, timeout=10)
out = stdout.read().decode("utf-8","replace")
err_out = stderr.read().decode("utf-8","replace")
print(out[-600:])
if err_out:
    print("[STDERR]", err_out[-400:])

c.close()
