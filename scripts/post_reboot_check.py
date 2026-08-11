"""Check Pi after reboot - verify HMI services and backend."""
import time
import paramiko

print("Connecting to Pi...")
for attempt in range(10):
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect("192.168.88.211", 22, "pi", "RaspberryB+2026!", timeout=10)
        print(f"Connected on attempt {attempt + 1}")
        break
    except Exception:
        if attempt < 9:
            print(f"  Attempt {attempt + 1} failed, retrying...")
            time.sleep(5)
        else:
            print("ERROR: Could not connect to Pi")
            exit(1)

def sh(cmd, timeout=15):
    i, o, e = c.exec_command(cmd, timeout=timeout)
    out = o.read().decode("ascii", "replace").strip()
    err = e.read().decode("ascii", "replace").strip()
    return out, err

print("\n=== Systemd services ===")
out, err = sh("systemctl is-active rpi-hmi-backend.service")
print(f"  backend: {out}")
out, err = sh("systemctl is-active rpi-hmi-display.service")
print(f"  display: {out}")
out, err = sh("systemctl is-active lightdm")
print(f"  lightdm: {out}")

print("\n=== Backend health ===")
out, err = sh("curl -s http://localhost:8000/health")
print(f"  {out}")

print("\n=== Display DRM ===")
out, err = sh("sudo fuser /dev/dri/card0 2>/dev/null | xargs ps -p 2>/dev/null | tail -5 || echo 'free'")
print(f"  card0 users:\n  {out}")

print("\n=== IP ===")
out, err = sh("hostname -I")
print(f"  {out.strip()}")

print("\n=== Web server test ===")
out, err = sh("curl -s http://localhost:8000/ | head -5 || echo 'no-content'")
print(f"  {out[:200]}")

c.close()
print("\n[DONE]")
