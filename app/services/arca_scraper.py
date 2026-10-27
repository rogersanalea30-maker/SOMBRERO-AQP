"""
Módulo de Automatización y Extracción Web para Arca Digital / Facturador PRO.
Permite autenticación automática, persistencia de sesión, extracción estructurada
de comprobantes, catálogo de clientes, productos y sincronización con base de datos local.
"""

import os
import re
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
import requests
from lxml import html

from app.config import settings

# Configurar logging
logger = logging.getLogger("arca_scraper")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [ArcaScraper] %(message)s"))
    logger.addHandler(ch)


class ArcaDigitalScraper:
    """Cliente de automatización y scraping para Arca Digital (Facturador PRO)."""

    def __init__(
        self,
        base_url: str = "https://sombrero.arca.digital",
        email: str = "sombrero@jbsistemas.com",
        password: str = "@Arequipa456@",
        screenshots_dir: Optional[str] = None
    ):
        self.base_url = base_url.rstrip("/")
        self.email = email
        self.password = password
        self.screenshots_dir = screenshots_dir or os.path.join(settings.STORAGE_DIR, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        })
        self.is_authenticated = False

    def login(self) -> bool:
        """
        Inicia sesión en la plataforma Arca Digital resolviendo tokens CSRF
        y guardando las cookies de sesión activa.
        """
        login_url = f"{self.base_url}/login"
        logger.info(f"Iniciando flujo de autenticación en {login_url}...")

        try:
            # 1. Obtener la página de login para extraer el token CSRF
            r_get = self.session.get(login_url, timeout=15)
            if r_get.status_code != 200:
                logger.error(f"Error cargando login page. HTTP Status: {r_get.status_code}")
                return False

            tree = html.fromstring(r_get.text)
            token_match = tree.xpath("//input[@name='_token']/@value")
            if not token_match:
                token_match = tree.xpath("//meta[@name='csrf-token']/@content")

            csrf_token = token_match[0] if token_match else None
            if not csrf_token:
                logger.error("No se encontró el token CSRF en el formulario de login.")
                return False

            logger.info("Token CSRF obtenido satisfactoriamente.")

            # 2. Enviar credenciales
            login_payload = {
                "_token": csrf_token,
                "email": self.email,
                "password": self.password,
                "remember": "on"
            }

            r_post = self.session.post(login_url, data=login_payload, timeout=20, allow_redirects=True)

            # Verificar si redireccionó fuera de /login (comúnmente /dashboard)
            if "/login" not in r_post.url and r_post.status_code == 200:
                self.is_authenticated = True
                logger.info(f"¡Autenticación exitosa! Sesión redirigida a: {r_post.url}")
                return True
            else:
                logger.error(f"Fallo de inicio de sesión. URL resultante: {r_post.url}")
                return False

        except Exception as e:
            logger.error(f"Excepción durante login: {e}", exc_info=True)
            return False

    def ensure_session(self) -> bool:
        """Verifica si la sesión sigue viva; si expiró, vuelve a autenticarse."""
        if not self.is_authenticated:
            return self.login()

        # Probar endpoint ligero para verificar sesión activa
        try:
            r = self.session.get(f"{self.base_url}/companies/record", timeout=10)
            if r.status_code == 200 and "data" in r.text:
                return True
        except Exception:
            pass

        logger.warning("La sesión ha expirado o no responde. Reautenticando...")
        return self.login()

    def get_company_profile(self) -> Dict[str, Any]:
        """Extrae los datos de la empresa, RUC, y credenciales SOL de SUNAT configuradas."""
        self.ensure_session()
        try:
            r = self.session.get(f"{self.base_url}/companies/record", timeout=10)
            if r.status_code == 200:
                data = r.json().get("data", {})
                return {
                    "ruc": data.get("number"),
                    "razon_social": data.get("name"),
                    "nombre_comercial": data.get("trade_name"),
                    "usuario_sol": data.get("soap_username"),
                    "clave_sol": data.get("soap_password"),
                    "certificado": data.get("certificate"),
                    "certificado_vencimiento": data.get("certificate_due"),
                    "entorno_soap": "PRODUCCION" if data.get("soap_type_id") == "02" else "DEMO"
                }
        except Exception as e:
            logger.error(f"Error al obtener perfil de empresa: {e}")
        return {}

    def get_documents(self, page: int = 1) -> List[Dict[str, Any]]:
        """Extrae comprobantes de pago (Facturas, Boletas, Notas) de la plataforma."""
        self.ensure_session()
        url = f"{self.base_url}/documents/records?page={page}"
        try:
            r = self.session.get(url, timeout=15)
            if r.status_code == 200:
                res_json = r.json()
                raw_docs = res_json.get("data", [])
                parsed_docs = []
                for doc in raw_docs:
                    parsed_docs.append({
                        "id": doc.get("id"),
                        "tipo_documento": doc.get("document_type_id"),
                        "tipo_documento_desc": doc.get("document_type_description"),
                        "numero": doc.get("number"),
                        "fecha_emision": doc.get("date_of_issue"),
                        "cliente_doc": doc.get("customer_number"),
                        "cliente_nombre": doc.get("customer_name"),
                        "moneda": doc.get("currency_type_id"),
                        "total_gravado": doc.get("total_taxed"),
                        "total_igv": doc.get("total_igv"),
                        "total": doc.get("total"),
                        "estado_sunat": doc.get("state_type_description"),
                        "download_xml": doc.get("download_xml"),
                        "download_pdf": doc.get("download_pdf"),
                        "download_cdr": doc.get("download_cdr"),
                        "filename": doc.get("filename")
                    })
                return parsed_docs
        except Exception as e:
            logger.error(f"Error extrayendo documentos: {e}")
        return []

    def get_items(self) -> List[Dict[str, Any]]:
        """Extrae el catálogo completo de productos y servicios."""
        self.ensure_session()
        url = f"{self.base_url}/items/records"
        try:
            r = self.session.get(url, timeout=15)
            if r.status_code == 200:
                raw_items = r.json().get("data", [])
                parsed_items = []
                for item in raw_items:
                    parsed_items.append({
                        "id": item.get("id"),
                        "codigo": item.get("internal_id") or f"P{item.get('id')}",
                        "descripcion": item.get("description"),
                        "unidad_medida": item.get("unit_type_id") or "NIU",
                        "precio_unitario": item.get("amount_sale_unit_price") or 0.0,
                        "valor_unitario": float(Decimal(str(item.get("amount_sale_unit_price", 0))) / Decimal("1.18")),
                        "tipo_afectacion": item.get("sale_affectation_igv_type_id") or "10",
                        "activo": item.get("active", True)
                    })
                return parsed_items
        except Exception as e:
            logger.error(f"Error extrayendo ítems: {e}")
        return []

    def get_customers(self) -> List[Dict[str, Any]]:
        """Extrae el directorio de clientes registrados y desde el histórico de comprobantes."""
        self.ensure_session()
        parsed_clients = {}

        # 1. Intentar endpoint de clientes si responde JSON
        try:
            r = self.session.get(f"{self.base_url}/persons/records/customers", timeout=8)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                data = r.json()
                raw_list = data.get("data", []) if isinstance(data, dict) else data
                for p in raw_list:
                    doc_num = str(p.get("number") or "").strip()
                    if doc_num:
                        parsed_clients[doc_num] = {
                            "id": p.get("id"),
                            "tipo_doc": "6" if len(doc_num) == 11 else "1",
                            "num_doc": doc_num,
                            "razon_social": p.get("name") or f"CLIENTE {doc_num}",
                            "direccion": p.get("address"),
                            "email": p.get("email"),
                            "telefono": p.get("telephone")
                        }
        except Exception:
            pass

        # 2. Extraer clientes desde el listado oficial de comprobantes emitidos
        try:
            docs = self.get_documents(page=1)
            for d in docs:
                num = str(d.get("cliente_doc") or "").strip()
                name = str(d.get("cliente_nombre") or "").strip()
                if num and num not in parsed_clients:
                    tipo_doc = "6" if len(num) == 11 else "1"
                    parsed_clients[num] = {
                        "id": None,
                        "tipo_doc": tipo_doc,
                        "num_doc": num,
                        "razon_social": name,
                        "direccion": "",
                        "email": None,
                        "telefono": None
                    }
        except Exception as e:
            logger.error(f"Error extrayendo clientes desde documentos: {e}")

        return list(parsed_clients.values())

    def sync_to_local_database(self, db_session) -> Dict[str, int]:
        """
        Sincroniza todos los productos y clientes de Arca Digital directamente
        en la base de datos local SQLite de la aplicación.
        """
        from app.db.models import ProductModel, ClientModel, InvoiceModel

        self.ensure_session()
        counts = {"products_imported": 0, "clients_imported": 0}

        # 1. Sincronizar productos
        items = self.get_items()
        for it in items:
            existing = db_session.query(ProductModel).filter(ProductModel.codigo == it["codigo"]).first()
            if not existing:
                p = ProductModel(
                    codigo=it["codigo"],
                    descripcion=it["descripcion"],
                    unidad_medida=it["unidad_medida"],
                    valor_unitario=Decimal(str(round(it["valor_unitario"], 4))),
                    precio_unitario=Decimal(str(it["precio_unitario"])),
                    tipo_afectacion=it["tipo_afectacion"]
                )
                db_session.add(p)
                counts["products_imported"] += 1
            else:
                existing.descripcion = it["descripcion"]
                existing.precio_unitario = Decimal(str(it["precio_unitario"]))

        # 2. Sincronizar clientes
        clients = self.get_customers()
        for cl in clients:
            if not cl["num_doc"]:
                continue
            existing_c = db_session.query(ClientModel).filter(ClientModel.num_doc == cl["num_doc"]).first()
            if not existing_c:
                c = ClientModel(
                    tipo_doc=cl["tipo_doc"],
                    num_doc=cl["num_doc"],
                    razon_social=cl["razon_social"] or f"CLIENTE {cl['num_doc']}",
                    direccion=cl["direccion"],
                    email=cl["email"],
                    telefono=cl["telefono"]
                )
                db_session.add(c)
                counts["clients_imported"] += 1

        db_session.commit()
        logger.info(f"Sincronización completada: {counts}")
        return counts

    def run_playwright_browser_flow(self, headless: bool = True) -> Dict[str, Any]:
        """
        Automatización de navegador visual mediante Playwright:
        Abre el navegador, ingresa a https://sombrero.arca.digital/login,
        completa credenciales con esperas explícitas, toma capturas de pantalla
        y retorna el resultado.
        """
        from playwright.sync_api import sync_playwright

        screenshot_path = os.path.join(self.screenshots_dir, "arca_login_result.png")
        result = {"success": False, "screenshot": screenshot_path, "current_url": ""}

        with sync_playwright() as p:
            # Iniciar navegador Chromium
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()

            try:
                logger.info(f"Navegando a {self.base_url}/login con Playwright...")
                page.goto(f"{self.base_url}/login", wait_until="networkidle", timeout=25000)

                # Esperas explícitas por los selectores
                page.wait_for_selector("#email", timeout=10000)
                page.wait_for_selector("#password", timeout=10000)

                # Rellenar credenciales
                page.fill("#email", self.email)
                page.fill("#password", self.password)

                # Clic en botón Iniciar Sesión
                page.click("#btnSignin")

                # Esperar navegación o elemento clave de dashboard
                page.wait_for_url("**/dashboard**", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=10000)

                result["current_url"] = page.url
                result["success"] = ("/dashboard" in page.url)

                # Tomar captura de pantalla de éxito
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"Captura guardada en: {screenshot_path}")

            except Exception as e:
                logger.error(f"Error en flujo Playwright: {e}")
                err_screenshot = os.path.join(self.screenshots_dir, "arca_error.png")
                page.screenshot(path=err_screenshot)
                result["error"] = str(e)
                result["screenshot"] = err_screenshot
            finally:
                browser.close()

        return result
