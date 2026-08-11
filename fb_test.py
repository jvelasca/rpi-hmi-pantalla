#!/usr/bin/env python3
"""Quick framebuffer test pattern."""
import sys
sys.path.insert(0, '/home/pi/rpi_hmi')
import json
import fb_ui
import mmap, os

params = fb_ui.detect_fb_params("/dev/fb0")
print("FB params:", json.dumps(params, indent=2))

fd = os.open("/dev/fb0", os.O_RDWR)
buf = mmap.mmap(fd, params["size"], mmap.MAP_SHARED, mmap.PROT_WRITE | mmap.PROT_READ)
pw = fb_ui.PixelWriter(buf, params)

# Test pattern
pw.fill_rect(0, 0, params["width"], params["height"], 0, 0, 0)
pw.fill_rect(10, 10, params["width"]-20, params["height"]-20, 30, 30, 60)
fb_ui.draw_text(pw, 50, 50, "HMI TEST", 255, 255, 255, 2)
pw.fill_rect(100, 100, 300, 100, 200, 0, 0)
fb_ui.draw_text(pw, 110, 130, "SI VES ESTO", 255, 255, 255, 1)
fb_ui.draw_text(pw, 110, 150, "FUNCIONA!", 255, 255, 0, 2)
pw.fill_rect(params["width"]//2, params["height"]-40, 60, 30, 0, 200, 80)
fb_ui.draw_text(pw, params["width"]//2 + 10, params["height"]-35, "OK", 255, 255, 255, 1)

print("Test pattern written to framebuffer.")
print(f"Resolution: {params['width']}x{params['height']} @ {params['bpp']}bpp")

buf.close()
os.close(fd)
