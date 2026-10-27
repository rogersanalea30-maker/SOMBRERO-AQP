"""
Punto de Entrada Principal de la API y Plataforma de Facturación Electrónica SUNAT
FastAPI + Base de Datos SQLite/PostgreSQL + Generación de PDFs + UI Dashboard
"""

import os
from decimal import Decimal
from typing import Literal, List, Optional
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, get_db
from app.db.models import ClientModel, ProductModel, InvoiceSeriesModel, InvoiceModel, InvoiceItemModel
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
from app.services.pdf_generator import PDFGeneratorSUNAT
from app.services.consulta_doc import consultar_documento_peru
from app.services.credit_note_builder import UBL21CreditNoteBuilder
from app.services.arca_scraper import ArcaDigitalScraper


# 1. Crear tablas en la base de datos automáticamente
Base.metadata.create_all(bind=engine)

# 2. Inicializar FastAPI
app = FastAPI(
    title="Plataforma de Facturación Electrónica SUNAT (UBL 2.1)",
    description=(
        "Sistema integral open source para emisión de Facturas (01), Boletas (03) y Notas de Crédito (07) "
        "con conexión directa a la SUNAT, generación de PDFs con Código QR y panel de control web."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Montar archivos estáticos para la interfaz de usuario
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 4. Datos iniciales de demostración (Seed)
@app.on_event("startup")
def startup_db_seed():
    db = next(get_db())
    try:
        if db.query(ProductModel).count() == 0:
            p1 = ProductModel(
                codigo="PROD-001",
                descripcion="DESARROLLO DE SOFTWARE MODULAR",
                unidad_medida="ZZ",
                valor_unitario=Decimal("100.00"),
                precio_unitario=Decimal("118.00"),
                tipo_afectacion="10"
            )
            p2 = ProductModel(
                codigo="PROD-002",
                descripcion="LICENCIA DE FACTURACIÓN ELECTRÓNICA UBL 2.1",
                unidad_medida="NIU",
                valor_unitario=Decimal("50.00"),
                precio_unitario=Decimal("59.00"),
                tipo_afectacion="10"
            )
            p3 = ProductModel(
                codigo="PROD-003",
                descripcion="CONSULTORÍA Y SOPORTE MENSUAL",
                unidad_medida="ZZ",
                valor_unitario=Decimal("200.00"),
                precio_unitario=Decimal("236.00"),
                tipo_afectacion="10"
            )
            db.add_all([p1, p2, p3])
            db.commit()

        if db.query(ClientModel).count() == 0:
            c1 = ClientModel(
                tipo_doc="6",
                num_doc="20555555551",
                razon_social="DISTRIBUIDORA LIMA S.A.C.",
                direccion="AV. AREQUIPA 1230 - LIMA",
                email="contacto@distribuidoralima.pe"
            )
            c2 = ClientModel(
                tipo_doc="1",
                num_doc="45678901",
                razon_social="MARIO VARGAS LLOSA",
                direccion="AV. PARDO 450 - MIRAFLORES",
                email="mario@correo.pe"
            )
            db.add_all([c1, c2])
            db.commit()
    finally:
        db.close()


# ==============================================================================
# RUTAS DE INTERFAZ Y GENERALES
# ==============================================================================

@app.get("/", response_class=HTMLResponse, tags=["Interfaz Web"])
def serve_dashboard():
    """Servicio de la interfaz gráfica interactiva de Punto de Venta y Gestión."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Facturación Electrónica SUNAT - API Operativa</h1><p>Visite <a href='/docs'>/docs</a></p>")


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


# ==============================================================================
# EMISIÓN DE FACTURAS Y BOLETAS
# ==============================================================================

@app.post(
    "/api/v1/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Comprobantes"]
)
def emitir_comprobante(invoice_data: InvoiceRequest, db: Session = Depends(get_db)):
    """
    Emite una Factura (01) o Boleta (03) conectándose directamente con la SUNAT:
    1. Construye el XML UBL 2.1.
    2. Firma digitalmente con el certificado .pfx.
    3. Empaqueta el ZIP y lo envía mediante sendBill.
    4. Procesa y almacena el CDR de respuesta.
    5. Genera la Representación Impresa en PDF (A4 y Ticket 80mm).
    6. Persiste la venta y los comprobantes en la base de datos.
    """
    try:
        emisor_ruc = invoice_data.emisor.ruc if invoice_data.emisor else settings.EMISOR_RUC
        doc_id = invoice_data.id_comprobante
        tipo_doc = invoice_data.tipo_documento.value
        base_name = f"{emisor_ruc}-{tipo_doc}-{invoice_data.serie}-{invoice_data.correlativo_str}"

        # 1. Construir XML UBL 2.1
        builder = UBL21InvoiceBuilder(invoice_data)
        xml_element, unsigned_xml_bytes = builder.build_xml()

        unsigned_xml_path = os.path.join(settings.dir_xml, f"{base_name}-unsigned.xml")
        with open(unsigned_xml_path, "wb") as f:
            f.write(unsigned_xml_bytes)

        # 2. Firmar digitalmente
        signer = XmlSignerSUNAT()
        signed_xml_bytes, hash_cpe = signer.sign_xml(xml_element)

        signed_xml_path = os.path.join(settings.dir_xml, f"{base_name}.xml")
        with open(signed_xml_path, "wb") as f:
            f.write(signed_xml_bytes)

        # 3. Enviar a SUNAT (sendBill)
        soap_client = SunatSoapClient()
        sunat_result = soap_client.send_bill(
            ruc_emisor=emisor_ruc,
            tipo_documento=tipo_doc,
            serie=invoice_data.serie,
            correlativo_str=invoice_data.correlativo_str,
            signed_xml_bytes=signed_xml_bytes
        )

        cdr: CdrDetails = sunat_result["cdr"]

        # 4. Generar PDFs (A4 y Ticket 80mm) con Código QR oficial y Hash
        pdf_dict = invoice_data.model_dump(mode="json")
        pdf_dict["hash_cpe"] = hash_cpe
        pdf_a4_path = os.path.join(settings.dir_pdf, f"{base_name}-a4.pdf")
        pdf_ticket_path = os.path.join(settings.dir_pdf, f"{base_name}-ticket.pdf")

        PDFGeneratorSUNAT.generar_pdf_a4(pdf_dict, pdf_a4_path)
        PDFGeneratorSUNAT.generar_pdf_ticket_80mm(pdf_dict, pdf_ticket_path)

        # 5. Persistir en Base de Datos
        try:
            # Guardar o actualizar cliente si no existe
            client_record = db.query(ClientModel).filter(ClientModel.num_doc == invoice_data.cliente.num_doc).first()
            if not client_record:
                client_record = ClientModel(
                    tipo_doc=invoice_data.cliente.tipo_doc.value,
                    num_doc=invoice_data.cliente.num_doc,
                    razon_social=invoice_data.cliente.razon_social,
                    direccion=invoice_data.cliente.direccion
                )
                db.add(client_record)

            # Registrar factura
            inv_db = InvoiceModel(
                tipo_documento=tipo_doc,
                serie=invoice_data.serie,
                correlativo=invoice_data.correlativo,
                document_id=doc_id,
                fecha_emision=invoice_data.fecha_emision,
                moneda=invoice_data.moneda.value,
                forma_pago=invoice_data.forma_pago.value,
                total_gravado=builder.total_gravado,
                total_exonerado=builder.total_exonerado,
                total_inafecto=builder.total_inafecto,
                total_igv=builder.total_igv,
                total_pagar=builder.total_a_pagar,
                hash_cpe=hash_cpe,
                sunat_status="ACEPTADO" if cdr.accepted else "RECHAZADO",
                sunat_code=cdr.response_code,
                sunat_description=cdr.description,
                cliente_tipo_doc=invoice_data.cliente.tipo_doc.value,
                cliente_num_doc=invoice_data.cliente.num_doc,
                cliente_razon_social=invoice_data.cliente.razon_social,
                cliente_direccion=invoice_data.cliente.direccion,
                xml_path=signed_xml_path,
                zip_path=sunat_result["zip_path"],
                cdr_path=sunat_result["cdr_xml_path"],
                pdf_a4_path=pdf_a4_path,
                pdf_ticket_path=pdf_ticket_path
            )
            db.add(inv_db)
            db.flush()

            for item in invoice_data.items:
                v_venta = item.cantidad * item.valor_unitario
                igv_line = v_venta * (item.porcentaje_igv / Decimal("100"))
                db_item = InvoiceItemModel(
                    invoice_id=inv_db.id,
                    codigo=item.codigo,
                    descripcion=item.descripcion,
                    unidad_medida=item.unidad_medida,
                    cantidad=item.cantidad,
                    valor_unitario=item.valor_unitario,
                    precio_unitario=item.precio_unitario or (item.valor_unitario * Decimal("1.18")),
                    igv_linea=igv_line,
                    valor_venta=v_venta
                )
                db.add(db_item)

            db.commit()
        except Exception as db_err:
            db.rollback()
            print(f"[WARN] No se pudo guardar en BD: {db_err}")

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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error interno: {ex}")


# ==============================================================================
# CONSULTA Y DESCARGA DE ARCHIVOS (PDF, XML, CDR)
# ==============================================================================

@app.get("/api/v1/invoices/{document_id}/pdf", tags=["Archivos"])
def ver_pdf_comprobante(
    document_id: str,
    format: Literal["a4", "ticket"] = Query("a4", description="Formato del PDF: 'a4' o 'ticket'"),
    tipo: str = "01",
    emisor_ruc: str = settings.EMISOR_RUC
):
    """Genera o entrega el archivo PDF del comprobante en formato A4 o Ticket 80mm."""
    parts = document_id.split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Formato inválido. Use SERIE-CORRELATIVO")
    serie, correlativo = parts[0], parts[1].zfill(8)
    base_name = f"{emisor_ruc}-{tipo}-{serie}-{correlativo}"

    filename = f"{base_name}-a4.pdf" if format == "a4" else f"{base_name}-ticket.pdf"
    file_path = os.path.join(settings.dir_pdf, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="El PDF solicitado no existe o no fue generado.")

    return FileResponse(path=file_path, filename=filename, media_type="application/pdf")


@app.get("/api/v1/invoices/{document_id}/download/{file_type}", tags=["Archivos"])
def descargar_archivo_comprobante(
    document_id: str,
    file_type: Literal["xml", "signed-xml", "zip", "cdr-zip", "cdr-xml"],
    emisor_ruc: str = settings.EMISOR_RUC,
    tipo: str = "01"
):
    """Descarga XML original, firmado, ZIP o CDR."""
    parts = document_id.split("-")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Formato inválido")
    serie, correlativo = parts[0], parts[1].zfill(8)
    base_name = f"{emisor_ruc}-{tipo}-{serie}-{correlativo}"

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
        raise HTTPException(status_code=404, detail=f"No se encontró el archivo: {filename}")

    return FileResponse(path=file_path, filename=filename, media_type=media_type)


@app.get("/api/v1/invoices/history", tags=["Comprobantes"])
def listar_historial_comprobantes(db: Session = Depends(get_db)):
    """Retorna la lista de comprobantes registrados en la base de datos."""
    return db.query(InvoiceModel).order_by(InvoiceModel.id.desc()).limit(50).all()


# ==============================================================================
# CONSULTA RUC / DNI
# ==============================================================================

@app.get("/api/v1/consultas/documento/{tipo}/{numero}", tags=["Consultas"])
def api_consultar_documento(tipo: str, numero: str):
    """Consulta pública o validación de RUC (11 dígitos) o DNI (8 dígitos)."""
    return consultar_documento_peru(tipo, numero)


# ==============================================================================
# CATÁLOGO DE CLIENTES Y PRODUCTOS
# ==============================================================================

@app.get("/api/v1/clients", tags=["Clientes"])
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(ClientModel).order_by(ClientModel.id.desc()).all()


@app.get("/api/v1/products", tags=["Productos"])
def listar_productos(db: Session = Depends(get_db)):
    return db.query(ProductModel).order_by(ProductModel.id.asc()).all()


# ==============================================================================
# PREVIEW OFFLINE
# ==============================================================================

@app.post("/api/v1/invoices/preview-xml", response_model=PreviewXmlResponse, tags=["Comprobantes"])
def previsualizar_xml_firmado(invoice_data: InvoiceRequest):
    """Genera y firma el XML UBL 2.1 sin enviarlo a SUNAT."""
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


# ==============================================================================
# AUTOMATIZACIÓN Y SINCRONIZACIÓN CON ARCA DIGITAL
# ==============================================================================

@app.post("/api/v1/arca/sync", tags=["Arca Digital"])
def api_sincronizar_arca(db: Session = Depends(get_db)):
    """Ejecuta la sincronización automática de productos y clientes desde Arca Digital."""
    scraper = ArcaDigitalScraper()
    if not scraper.login():
        raise HTTPException(status_code=502, detail="No se pudo iniciar sesión en sombrero.arca.digital")

    result = scraper.sync_to_local_database(db)
    return {
        "success": True,
        "message": "Sincronización completada exitosamente desde Arca Digital.",
        "detalles": result
    }


@app.get("/api/v1/arca/company", tags=["Arca Digital"])
def api_obtener_empresa_arca():
    """Obtiene la configuración y datos fiscales configurados en Arca Digital."""
    scraper = ArcaDigitalScraper()
    company = scraper.get_company_profile()
    if not company:
        raise HTTPException(status_code=502, detail="Error obteniendo perfil de empresa desde Arca Digital.")
    return company


@app.get("/api/v1/arca/documents", tags=["Arca Digital"])
def api_listar_documentos_arca(page: int = Query(1, ge=1)):
    """Obtiene el listado en vivo de comprobantes emitidos en Arca Digital."""
    scraper = ArcaDigitalScraper()
    docs = scraper.get_documents(page=page)
    return docs


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
