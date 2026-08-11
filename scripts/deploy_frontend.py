"""Deploy frontend build to Pi (SFTP dist/ -> backend/app/static/)."""
import paramiko
from pathlib import Path

HOST = "192.168.88.211"
PI_BASE = "/home/pi/rpi_hmi"
DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=22, username="pi", password="RaspberryB+2026!", timeout=15)

static_dir = f"{PI_BASE}/backend/app/static"

# Use shell to ensure directories exist
def sh(cmd):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=10)
    return stdout.read().decode("ascii","replace").strip()

sh(f"rm -rf {static_dir}/* && mkdir -p {static_dir}/assets")
print("  Cleaned static/")

# SFTP upload
sftp = c.open_sftp()
count = 0
for local_file in sorted(DIST.rglob("*")):
    if local_file.is_dir():
        continue
    rel = local_file.relative_to(DIST).as_posix()
    remote_path = f"{static_dir}/{rel}"
    try:
        sftp.put(str(local_file), remote_path)
        size = local_file.stat().st_size
        print(f"  OK  static/{rel} ({size}B)")
        count += 1
    except Exception as e:
        print(f"  ERR {rel}: {e}")
sftp.close()

# Verify
print("\n  Files on Pi:")
print(sh(f"find {static_dir} -type f -ls 2>/dev/null"))

# Check root page serves the new frontend
print("\n  Root page:")
stdin, stdout, stderr = c.exec_command("curl -s http://localhost:8000/")
html = stdout.read().decode("ascii","replace")
print("  " + html.split("\n")[0][:80])

c.close()
print(f"\n[DONE] {count} files -> http://{HOST}:8000/")
