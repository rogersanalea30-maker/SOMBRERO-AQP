# -*- coding: utf-8 -*-
import sys
import os
import shutil
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Renderizando PNGs de alta resolución a partir de los vectores SVG de InnovaFlow Perú...")

    # Copy AI generated logo if available
    ai_logo = r'C:\Users\USER\.gemini\antigravity\brain\bcf435aa-b945-41db-b6ef-854b43d0564c\innovaflow_peru_logo_1793281515203.jpg'
    if os.path.exists(ai_logo):
        shutil.copy2(ai_logo, 'app/static/logo_ai.jpg')
        print("✓ Copied AI logo to app/static/logo_ai.jpg")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 800, 'height': 400}, device_scale_factor=2)

        # 1. Render Horizontal Logo
        svg_abs = os.path.abspath('app/static/logo.svg').replace('\\', '/')
        page.goto(f'file:///{svg_abs}')
        page.wait_for_timeout(300)

        # Screenshot svg element with transparency
        svg_el = page.locator('svg')
        svg_el.screenshot(path='app/static/logo.png', omit_background=True)
        print(f"✓ Generated app/static/logo.png ({os.path.getsize('app/static/logo.png')} bytes)")

        # 2. Render Square Icon / Favicon
        icon_abs = os.path.abspath('app/static/logo_icon.svg').replace('\\', '/')
        page.goto(f'file:///{icon_abs}')
        page.wait_for_timeout(300)

        page.locator('svg').screenshot(path='app/static/logo_icon.png', omit_background=True)
        print(f"✓ Generated app/static/logo_icon.png ({os.path.getsize('app/static/logo_icon.png')} bytes)")

        # Favicon 64x64
        shutil.copy2('app/static/logo_icon.png', 'app/static/favicon.png')

        browser.close()

    print("¡Logos PNG y SVG listos y optimizados!")

if __name__ == '__main__':
    main()
