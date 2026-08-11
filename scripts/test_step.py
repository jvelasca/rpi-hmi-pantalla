"""Quick test of display app on Pi - step by step."""
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.88.211", port=22, username="pi", password="RaspberryB+2026!", timeout=15)

def run(cmd, timeout=15):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("ascii","replace").strip()
    err = stderr.read().decode("ascii","replace").strip()
    return out, err

# Test 1: widget imports with font fallback
print("=== Test 1: widget fonts ===")
o, e = run("cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi /home/pi/rpi_hmi/venv/bin/python3 -c "
    "'from display.ui.widgets import LedIndicator, ButtonWidget; import pygame; "
    "print(\"HAS_FREETYPE=\", hasattr(pygame,\"freetype\")); "
    "print(\"font_init=\", pygame.font.get_init()); "
    "pygame.font.init(); l = LedIndicator(10,50,180,230); "
    "print(\"widget OK\")' 2>&1")
print("out:", o)
print("err:", e[:200] if e else "none")

# Test 2: screen init with mock
print("\n=== Test 2: screen mock ===")
o, e = run("cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi /home/pi/rpi_hmi/venv/bin/python3 -c "
    "'from display.ui.screen import Screen; s=Screen(mock=True); ok=s.init(); "
    "print(\"screen:\", ok, s.width, s.height, s.driver); s.cleanup()' 2>&1")
print("out:", o)
print("err:", e[:200] if e else "none")

# Test 3: DisplayApp import
print("\n=== Test 3: DisplayApp import ===")
o, e = run("cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi /home/pi/rpi_hmi/venv/bin/python3 -c "
    "'from display.app import DisplayApp; print(\"DisplayApp imported OK\")' 2>&1")
print("out:", o)
print("err:", e[:200] if e else "none")

# Test 4: Run app briefly (2s)
print("\n=== Test 4: app run 3s ===")
stdin, stdout, stderr = c.exec_command(
    "cd /home/pi/rpi_hmi && PYTHONPATH=/home/pi/rpi_hmi "
    "timeout 3 /home/pi/rpi_hmi/venv/bin/python3 display/app.py 2>&1; echo '---DONE---'",
    timeout=8
)
out = stdout.read().decode("ascii","replace")
err = stderr.read().decode("ascii","replace")
# Show both
print("stdout:", out[:400])
if err:
    print("stderr:", err[:400])

c.close()
