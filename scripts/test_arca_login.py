import requests
import re
from lxml import html

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
})

# 1. Obtener CSRF Token de la página de Login
r = session.get('https://sombrero.arca.digital/login', timeout=15)
tree = html.fromstring(r.text)
token_input = tree.xpath("//input[@name='_token']/@value")
csrf_token = token_input[0] if token_input else ''
print("CSRF Token obtenido:", csrf_token)

# 2. Enviar credenciales
login_payload = {
    '_token': csrf_token,
    'email': 'sombrero@jbsistemas.com',
    'password': '@Arequipa456@',
    'remember': 'on'
}

resp = session.post('https://sombrero.arca.digital/login', data=login_payload, timeout=15, allow_redirects=True)
print("Código HTTP:", resp.status_code)
print("URL resultante:", resp.url)

if "/login" not in resp.url:
    print("¡Inicio de sesión exitoso en https://sombrero.arca.digital!")
    
    # Probar endpoints estándar de Facturador PRO / Arca Digital
    endpoints = [
        ('/companies/record', 'Datos de Empresa'),
        ('/configurations/record', 'Configuración del Sistema'),
        ('/documents/records', 'Listado de Comprobantes'),
        ('/items/records', 'Listado de Productos/Servicios'),
        ('/persons/records/customers', 'Listado de Clientes')
    ]
    for ep, label in endpoints:
        r_test = session.get(f'https://sombrero.arca.digital{ep}', timeout=10)
        print(f"\n--- {label} ({ep}) ---")
        print("Status:", r_test.status_code)
        try:
            data = r_test.json()
            if isinstance(data, dict):
                print("Claves JSON:", list(data.keys())[:8])
                if "data" in data and isinstance(data["data"], list):
                    print("Total registros:", len(data["data"]))
                    if len(data["data"]) > 0:
                        print("Primer registro ejemplo:", data["data"][0])
            elif isinstance(data, list):
                print("Total registros lista:", len(data))
                if len(data) > 0:
                    print("Primer registro ejemplo:", data[0])
        except Exception:
            print("Texto respuesta (primeros 200 car.):", r_test.text[:200])
else:
    print("No se pudo iniciar sesión. Verifique credenciales.")
