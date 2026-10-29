# -*- coding: utf-8 -*-
import sys
import os
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    print("Analizando https://posrestaurantes.com/ a profundidad...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1400, 'height': 1000})

        try:
            page.goto("https://posrestaurantes.com/", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)

            title = page.title()
            print(f"Title: {title}")

            # Take full page screenshot to analyze design, UI patterns, color schemes
            ss_path = "app/static/ref_posrestaurantes_home.png"
            page.screenshot(path=ss_path, full_page=True)
            print(f"✓ Screenshot saved to {ss_path}")

            # Extract text, headings, sections, image URLs, CSS styles
            data = page.evaluate("""() => {
                const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4')).map(h => ({
                    tag: h.tagName,
                    text: h.innerText.trim()
                }));
                const images = Array.from(document.querySelectorAll('img')).map(img => ({
                    src: img.src,
                    alt: img.alt
                })).filter(img => img.src && !img.src.includes('data:image'));
                const links = Array.from(document.querySelectorAll('a')).map(a => ({
                    text: a.innerText.trim(),
                    href: a.href
                })).filter(l => l.text);
                return { headings, images, links };
            }""")

            print(f"Encontrados {len(data['headings'])} encabezados y {len(data['images'])} imágenes de interfaz.")
            for h in data['headings'][:25]:
                print(f"  [{h['tag']}] {h['text']}")

            print("\nImágenes clave de interfaz:")
            for img in data['images'][:15]:
                print(f"  Img: {img['alt']} -> {img['src']}")

        except Exception as e:
            print("Error durante análisis con Playwright:", e)

        browser.close()

if __name__ == '__main__':
    main()
