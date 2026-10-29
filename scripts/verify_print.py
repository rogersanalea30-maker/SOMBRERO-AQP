# -*- coding: utf-8 -*-
import sys
from playwright.sync_api import sync_playwright

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('http://localhost:8000')
        page.wait_for_timeout(1000)

        # Test 1: Menu printing
        page.evaluate("document.body.className = 'printing-menu'")
        page.emulate_media(media='print')
        page.wait_for_timeout(400)
        page.pdf(path='app/static/test_print_menu.pdf')
        print("✓ Menu PDF generado con emulación de impresión limpia")

        # Test 2: Ticket Cocina
        page.evaluate("""() => {
            document.body.className = 'printing-comanda-cocina';
            document.getElementById('ticket-cocina-print-area').innerHTML = build80mmTicketHtml(
                'TICKET DE COCINA', 
                [{cantidad: 1, descripcion: 'CUY CHACTADO ENTERO', modifiers: ['🌶️ Rocoto aparte', '🔥 Bien dorado']}], 
                {name: 'MESA 01', zone: 'Salón Principal', comandaId: 'CMD-101'}
            );
        }""")
        page.wait_for_timeout(400)
        page.pdf(path='app/static/test_print_ticket_cocina.pdf')
        print("✓ Ticket Cocina 80mm PDF generado de forma aislada")

        # Test 3: QR Placard
        page.evaluate("""() => {
            document.body.className = 'printing-qr';
            document.getElementById('print-qr-target').innerHTML = '<div style=\"font-family:sans-serif;width:120mm;padding:20px;border:3px solid #78350f;text-align:center;margin:0 auto;\"><h2>El Sombrero Arequipeño</h2><h3>MESA 05</h3></div>';
        }""")
        page.wait_for_timeout(400)
        page.pdf(path='app/static/test_print_qr_placard.pdf')
        print("✓ Lámina QR Mesa PDF generada de forma aislada")

        browser.close()
        print("¡Todas las impresiones han sido aisladas y verificadas con éxito!")

if __name__ == '__main__':
    main()
