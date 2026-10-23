"""
Punto de Entrada Principal de la API de Facturación Electrónica SUNAT (FastAPI)
Permite emitir Facturas (01) y Boletas de Venta (03) conectándose directamente a SUNAT.
"""

import os
from typing import Literal
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.schemas.invoice import InvoiceRequest
from app.schemas.response import (
    InvoiceResponse,
    PreviewXmlResponse,
    CdrDetails,
    FileReferences,
)
from app.services.xml_builder import UBL21InvoiceBuilder
from app.services.signer import XmlSignerSUNAT
from app.services.sunat_client import SunatSoapClient


app = FastAPI(
    title="Sistema de Facturación Electrónica SUNAT (UBL 2.1)",
    description=(
        "Backend modular y gratuito en Python + FastAPI para emisión directa de "
        "Facturas (01) y Boletas de Venta (03) ante los Web Services de la SUNAT (sin OSEs ni intermediarios)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Habilitar CORS para permitir conexión desde cualquier frontend web o móvil
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["General"])
def read_root():
    """Ruta raíz de bienvenida e información del servicio."""
    return {
        "sistema": "Facturación Electrónica SUNAT UBL 2.1",
        "estado": "Operativo",
        "entorno": settings.SUNAT_ENV,
        "emisor_configurado": {
            "ruc": settings.EMISOR_RUC,
            "razon_social": settings.EMISOR_RAZON_SOCIAL,
            "usuario_secundario": settings.sunat_auth_username
        },
        "documentacion": "/docs"
    }


@app.get("/health", tags=["General"])
def health_check():
    """Verifica el estado del servicio y la presencia del certificado digital."""
    cert_exists = os.path.exists(settings.CERT_PATH)
    return {
        "status": "ok",
        "sunat_env": settings.SUNAT_ENV,
        "sunat_endpoint": settings.sunat_service_url,
        "certificate_loaded": cert_exists,
        "certificate_path": settings.CERT_PATH
    }


@app.post(
    "/api/v1/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Comprobantes"]
)
def emitir_comprobante(invoice_data: InvoiceRequest):
    """
    Emite una Factura (01) o Boleta de Venta (03):
    1. Valida el payload según catálogos de SUNAT.
    2. Construye el XML UBL 2.1.
    3. Firma digitalmente el XML usando el certificado .pfx.
    4. Empaqueta el XML firmado en un archivo ZIP.
    5. Envía el comprobante directamente a SUNAT vía Web Service SOAP (sendBill).
    6. Procesa la Constancia de Recepción (CDR) y retorna el estado de aprobación.
    """
    try:
        # 1. Resolver emisor y nombres de archivo
        emisor_ruc = invoice_data.emisor.ruc if invoice_data.emisor else settings.EMISOR_RUC
        doc_id = invoice_data.id_comprobante
        tipo_doc = invoice_data.tipo_documento.value
        base_name = f"{emisor_ruc}-{tipo_doc}-{invoice_data.serie}-{invoice_data.correlativo_str}"

        # 2. Construir XML UBL 2.1
        builder = UBL21InvoiceBuilder(invoice_data)
        xml_element, unsigned_xml_bytes = builder.build_xml()

        # Guardar XML sin firmar
        unsigned_xml_path = os.path.join(settings.dir_xml, f"{base_name}-unsigned.xml")
        with open(unsigned_xml_path, "wb") as f:
            f.write(unsigned_xml_bytes)

        # 3. Firmar digitalmente con Certificado .pfx
        signer = XmlSignerSUNAT()
        signed_xml_bytes, hash_cpe = signer.sign_xml(xml_element)

        # Guardar XML firmado oficial
        signed_xml_path = os.path.join(settings.dir_xml, f"{base_name}.xml")
        with open(signed_xml_path, "wb") as f:
            f.write(signed_xml_bytes)

        # 4. Enviar a SUNAT mediante Zeep SOAP BillService
        soap_client = SunatSoapClient()
        sunat_result = soap_client.send_bill(
            ruc_emisor=emisor_ruc,
            tipo_documento=tipo_doc,
            serie=invoice_data.serie,
            correlativo_str=invoice_data.correlativo_str,
            signed_xml_bytes=signed_xml_bytes
        )

        cdr: CdrDetails = sunat_result["cdr"]

        file_refs = FileReferences(
            xml=unsigned_xml_path,
            signed_xml=signed_xml_path,
            zip=sunat_result["zip_path"],
            cdr_zip=sunat_result["cdr_zip_path"],
            cdr_xml=sunat_result["cdr_xml_path"]
        )

        msg = "Comprobante aceptado por SUNAT" if cdr.accepted else "Comprobante rechazado por SUNAT"

        return InvoiceResponse(
            success=cdr.accepted,
            message=f"{msg}: {cdr.description}",
            document_id=doc_id,
            tipo_documento=tipo_doc,
            hash_cpe=hash_cpe,
            cdr=cdr,
            files=file_refs
        )

    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(val_err))
    except FileNotFoundError as fnf_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(fnf_err))
    except ConnectionError as conn_err:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(conn_err))
    except RuntimeError as run_err:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(run_err))
    except Exception as ex:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno no controlado durante la emisión: {ex}"
        )


@app.post(
    "/api/v1/invoices/preview-xml",
    response_model=PreviewXmlResponse,
    tags=["Comprobantes"]
)
def previsualizar_xml_firmado(invoice_data: InvoiceRequest):
    """
    Genera y firma el XML UBL 2.1 sin enviarlo a la SUNAT.
    Útil para auditorías, inspección de etiquetas y pruebas de firmado offline.
    """
    try:
        emisor_ruc = invoice_data.emisor.ruc if invoice_data.emisor else settings.EMISOR_RUC
        doc_id = invoice_data.id_comprobante
        tipo_doc = invoice_data.tipo_documento.value
        base_name = f"{emisor_ruc}-{tipo_doc}-{invoice_data.serie}-{invoice_data.correlativo_str}"

        builder = UBL21InvoiceBuilder(invoice_data)
        xml_element, _ = builder.build_xml()

        signer = XmlSignerSUNAT()
        signed_xml_bytes, hash_cpe = signer.sign_xml(xml_element)

        signed_xml_path = os.path.join(settings.dir_xml, f"{base_name}.xml")
        with open(signed_xml_path, "wb") as f:
            f.write(signed_xml_bytes)

        return PreviewXmlResponse(
            success=True,
            document_id=doc_id,
            tipo_documento=tipo_doc,
            hash_cpe=hash_cpe,
            xml_content=signed_xml_bytes.decode("utf-8"),
            signed_xml_path=signed_xml_path
        )
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))


@app.get(
    "/api/v1/invoices/{document_id}/download/{file_type}",
    tags=["Archivos"]
)
def descargar_archivo_comprobante(
    document_id: str,
    file_type: Literal["xml", "signed-xml", "zip", "cdr-zip", "cdr-xml"],
    emisor_ruc: str = settings.EMISOR_RUC,
    tipo_documento: str = "01"
):
    """
    Descarga archivos generados asociados a un comprobante:
    - xml: XML original sin firmar
    - signed-xml: XML firmado digitalmente
    - zip: Archivo ZIP enviado a SUNAT
    - cdr-zip: Archivo ZIP de respuesta recibido de SUNAT
    - cdr-xml: Archivo XML extraído del CDR
    """
    parts = document_id.split("-")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El document_id debe tener el formato SERIE-CORRELATIVO (ej. F001-00000001)"
        )
    serie, correlativo = parts[0], parts[1].zfill(8)
    base_name = f"{emisor_ruc}-{tipo_documento}-{serie}-{correlativo}"

    mapping = {
        "xml": (settings.dir_xml, f"{base_name}-unsigned.xml", "application/xml"),
        "signed-xml": (settings.dir_xml, f"{base_name}.xml", "application/xml"),
        "zip": (settings.dir_zip, f"{base_name}.zip", "application/zip"),
        "cdr-zip": (settings.dir_cdr, f"R-{base_name}.zip", "application/zip"),
        "cdr-xml": (settings.dir_cdr, f"R-{base_name}.xml", "application/xml"),
    }

    folder, filename, media_type = mapping[file_type]
    file_path = os.path.join(folder, filename)

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró el archivo solicitado: {filename}"
        )

    return FileResponse(path=file_path, filename=filename, media_type=media_type)


@app.get(
    "/api/v1/invoices/{document_id}/cdr",
    response_model=CdrDetails,
    tags=["Comprobantes"]
)
def consultar_cdr_almacenado(
    document_id: str,
    emisor_ruc: str = settings.EMISOR_RUC,
    tipo_documento: str = "01"
):
    """Lee y parsea la Constancia de Recepción (CDR) previamente almacenada en disco."""
    parts = document_id.split("-")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato inválido. Use SERIE-CORRELATIVO (ej. F001-00000001)"
        )
    serie, correlativo = parts[0], parts[1].zfill(8)
    cdr_xml_file = os.path.join(settings.dir_cdr, f"R-{emisor_ruc}-{tipo_documento}-{serie}-{correlativo}.xml")

    if not os.path.exists(cdr_xml_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe CDR registrado para el comprobante {document_id}"
        )

    with open(cdr_xml_file, "rb") as f:
        cdr_bytes = f.read()

    return SunatSoapClient._parse_cdr_xml(cdr_bytes)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
