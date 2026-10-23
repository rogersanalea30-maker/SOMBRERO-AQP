"""
Script de Pruebas de Integración End-to-End
Prueba la generación de XML UBL 2.1, firmado digital y endpoints de la API de FastAPI.
"""

import os
import sys
from decimal import Decimal

# Asegurar que el directorio raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    print("\n--- 1. Probando Endpoint /health ---")
    response = client.get("/health")
    assert response.status_code == 200, f"Error: {response.text}"
    print("Health response:", response.json())


def test_preview_factura_xml():
    print("\n--- 2. Probando Generación y Firmado de Factura (01) ---")
    factura_payload = {
        "tipo_documento": "01",
        "serie": "F001",
        "correlativo": 1,
        "moneda": "PEN",
        "forma_pago": "Contado",
        "cliente": {
            "tipo_doc": "6",
            "num_doc": "20555555551",
            "razon_social": "DISTRIBUIDORA LIMA S.A.C.",
            "direccion": "AV. AREQUIPA 123 - LIMA"
        },
        "items": [
            {
                "codigo": "PROD-001",
                "descripcion": "DESARROLLO DE SOFTWARE MODULAR",
                "unidad_medida": "ZZ",
                "cantidad": 1.0,
                "valor_unitario": 100.0,
                "tipo_afectacion_igv": "10",
                "porcentaje_igv": 18.0
            },
            {
                "codigo": "PROD-002",
                "descripcion": "LICENCIA DE FACTURACION ELECTRONICA",
                "unidad_medida": "NIU",
                "cantidad": 2.0,
                "valor_unitario": 50.0,
                "tipo_afectacion_igv": "10",
                "porcentaje_igv": 18.0
            }
        ]
    }

    response = client.post("/api/v1/invoices/preview-xml", json=factura_payload)
    assert response.status_code == 200, f"Error en preview: {response.text}"
    data = response.json()
    print("Comprobante:", data["document_id"])
    print("Hash CPE (DigestValue):", data["hash_cpe"])
    print("Ruta de archivo firmado:", data["signed_xml_path"])
    print("Longitud del XML generado:", len(data["xml_content"]), "caracteres")

    # Verificaciones en el XML
    xml_text = data["xml_content"]
    assert "F001-00000001" in xml_text
    assert "SignSUNAT" in xml_text
    assert "SON: DOSCIENTOS TREINTA Y SEIS CON 00/100 SOLES" in xml_text
    print("[OK] Factura 01 validada exitosamente con cálculo de IGV y firma digital!")


def test_preview_boleta_xml():
    print("\n--- 3. Probando Generación y Firmado de Boleta de Venta (03) ---")
    boleta_payload = {
        "tipo_documento": "03",
        "serie": "B001",
        "correlativo": 5,
        "moneda": "PEN",
        "forma_pago": "Contado",
        "cliente": {
            "tipo_doc": "1",
            "num_doc": "45678901",
            "razon_social": "JUAN PEREZ GONZALES",
            "direccion": "CALLE LOS PINOS 450"
        },
        "items": [
            {
                "codigo": "ART-010",
                "descripcion": "TECLADO MECANICO RGB",
                "unidad_medida": "NIU",
                "cantidad": 1.0,
                "valor_unitario": 84.75,
                "tipo_afectacion_igv": "10",
                "porcentaje_igv": 18.0
            }
        ]
    }

    response = client.post("/api/v1/invoices/preview-xml", json=boleta_payload)
    assert response.status_code == 200, f"Error en boleta: {response.text}"
    data = response.json()
    print("Comprobante:", data["document_id"])
    print("Hash CPE (DigestValue):", data["hash_cpe"])
    print("Ruta de archivo firmado:", data["signed_xml_path"])
    print("[OK] Boleta 03 validada exitosamente!")


def test_sunat_send_beta():
    print("\n--- 4. Probando Envío Directo al Web Service Beta de SUNAT ---")
    import random
    # Usar correlativo aleatorio para evitar error 1033 (comprobante ya registrado previamente)
    random_correlativo = random.randint(10000, 99999)
    factura_payload = {
        "tipo_documento": "01",
        "serie": "F001",
        "correlativo": random_correlativo,
        "moneda": "PEN",
        "forma_pago": "Contado",
        "cliente": {
            "tipo_doc": "6",
            "num_doc": "20555555551",
            "razon_social": "EMPRESA CLIENTE S.A.C.",
            "direccion": "AV. JAVIER PRADO ESTE 1000"
        },
        "items": [
            {
                "codigo": "SRV-BETA",
                "descripcion": "SERVICIO DE PRUEBA ENTORNO BETA",
                "unidad_medida": "ZZ",
                "cantidad": 1.0,
                "valor_unitario": 100.0,
                "tipo_afectacion_igv": "10",
                "porcentaje_igv": 18.0
            }
        ]
    }

    print(f"Enviando Factura F001-{random_correlativo} a SUNAT Beta...")
    response = client.post("/api/v1/invoices", json=factura_payload)
    print("Código HTTP:", response.status_code)
    try:
        resp_json = response.json()
        print("Respuesta SUNAT:", resp_json)
        assert resp_json["success"] is True
        assert resp_json["cdr"]["response_code"] == "0"
    except Exception as e:
        print("Respuesta:", response.text, "Error:", e)

    print("\n--- 5. Probando Envío de Boleta de Venta (03) a SUNAT Beta ---")
    random_boleta_correlativo = random.randint(10000, 99999)
    boleta_payload = {
        "tipo_documento": "03",
        "serie": "B001",
        "correlativo": random_boleta_correlativo,
        "moneda": "PEN",
        "forma_pago": "Contado",
        "cliente": {
            "tipo_doc": "1",
            "num_doc": "45678901",
            "razon_social": "MARIO VARGAS LLOSA",
            "direccion": "AV. PARDO 450 - MIRAFLORES"
        },
        "items": [
            {
                "codigo": "LIB-001",
                "descripcion": "LIBRO DE ARQUITECTURA DISTRIBUIDA EN PYTHON",
                "unidad_medida": "NIU",
                "cantidad": 1.0,
                "valor_unitario": 50.0,
                "tipo_afectacion_igv": "10",
                "porcentaje_igv": 18.0
            }
        ]
    }
    response_b = client.post("/api/v1/invoices", json=boleta_payload)
    print("\n--- 6. Probando Descarga de Archivos (XML, ZIP, CDR) ---")
    doc_id = resp_json["document_id"]
    res_xml = client.get(f"/api/v1/invoices/{doc_id}/download/signed-xml")
    assert res_xml.status_code == 200
    assert len(res_xml.content) > 0

    res_zip = client.get(f"/api/v1/invoices/{doc_id}/download/zip")
    assert res_zip.status_code == 200

    res_cdr = client.get(f"/api/v1/invoices/{doc_id}/download/cdr-zip")
    assert res_cdr.status_code == 200

    res_cdr_info = client.get(f"/api/v1/invoices/{doc_id}/cdr")
    assert res_cdr_info.status_code == 200
    assert res_cdr_info.json()["accepted"] is True
    print("[OK] Descargas y consulta de CDR verificadas exitosamente!")


if __name__ == "__main__":
    test_health_endpoint()
    test_preview_factura_xml()
    test_preview_boleta_xml()
    test_sunat_send_beta()
