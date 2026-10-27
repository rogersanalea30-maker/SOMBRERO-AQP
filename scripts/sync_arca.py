"""
Script de Automatización y Sincronización con Arca Digital.
Ejecuta la extracción de comprobantes, productos y clientes y los guarda en JSON y en la BD local.
"""

import os
import sys
import json

# Asegurar que el directorio raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.arca_scraper import ArcaDigitalScraper
from app.db import SessionLocal


def main():
    print("=================================================================")
    print("  AUTOMATIZACIÓN Y EXTRACCIÓN DE DATOS: ARCA DIGITAL / FACTURADOR ")
    print("=================================================================")

    scraper = ArcaDigitalScraper(
        base_url="https://sombrero.arca.digital",
        email="sombrero@jbsistemas.com",
        password="@Arequipa456@"
    )

    # 1. Autenticación
    print("\n[1/5] Autenticando en https://sombrero.arca.digital...")
    if not scraper.login():
        print("[ERROR] No se pudo iniciar sesión. Verifique credenciales o conectividad.")
        return

    print("[OK] Sesión iniciada correctamente.")

    backup_dir = os.path.join("app", "storage", "arca_backup")
    os.makedirs(backup_dir, exist_ok=True)

    # 2. Extraer datos de la empresa
    print("\n[2/5] Extrayendo configuración y datos de la empresa...")
    company = scraper.get_company_profile()
    print("  - RUC:", company.get("ruc"))
    print("  - Razón Social:", company.get("razon_social"))
    print("  - Usuario Secundario SUNAT:", company.get("usuario_sol"))
    print("  - Entorno SUNAT:", company.get("entorno_soap"))

    with open(os.path.join(backup_dir, "company_profile.json"), "w", encoding="utf-8") as f:
        json.dump(company, f, indent=2, ensure_ascii=False)

    # 3. Extraer catálogo de productos/servicios
    print("\n[3/5] Extrayendo catálogo de productos y servicios...")
    items = scraper.get_items()
    print(f"  - Total productos encontrados: {len(items)}")
    with open(os.path.join(backup_dir, "items_catalog.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

    # 4. Extraer comprobantes de pago
    print("\n[4/5] Extrayendo listado de comprobantes emitidos...")
    documents = scraper.get_documents(page=1)
    print(f"  - Total comprobantes extraídos (página 1): {len(documents)}")
    if documents:
        primer_doc = documents[0]
        print(f"  - Último comprobante: {primer_doc['tipo_documento_desc']} {primer_doc['numero']}")
        print(f"  - Cliente: {primer_doc['cliente_nombre']} ({primer_doc['cliente_doc']})")
        print(f"  - Total: {primer_doc['moneda']} {primer_doc['total']}")
        print(f"  - Estado SUNAT: {primer_doc['estado_sunat']}")

    with open(os.path.join(backup_dir, "documents.json"), "w", encoding="utf-8") as f:
        json.dump(documents, f, indent=2, ensure_ascii=False)

    # 5. Sincronizar en la Base de Datos Local
    print("\n[5/5] Sincronizando datos en la base de datos SQLite local...")
    db = SessionLocal()
    try:
        res = scraper.sync_to_local_database(db)
        print(f"  - Productos importados/actualizados: {res['products_imported']}")
        print(f"  - Clientes importados/actualizados: {res['clients_imported']}")
        print("\n[EXITO] Sincronización completa finalizada con éxito.")
        print(f"Archivos de respaldo guardados en: {os.path.abspath(backup_dir)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
