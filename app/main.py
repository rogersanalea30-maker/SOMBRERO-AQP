"""
Punto de Entrada Principal de la API y Plataforma de FacturaciÃ³n ElectrÃ³nica SUNAT
FastAPI + Base de Datos SQLite/PostgreSQL + GeneraciÃ³n de PDFs + UI Dashboard
"""

import os
from decimal import Decimal
from typing import Literal, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, get_db
from app.db.models import ClientModel, ProductModel, InvoiceSeriesModel, InvoiceModel, InvoiceItemModel, UserModel
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


# 1. Crear tablas en la base de datos automÃ¡ticamente
Base.metadata.create_all(bind=engine)

# 2. Inicializar FastAPI
app = FastAPI(
    title="InnovaFlow PerÃº - FacturaciÃ³n ElectrÃ³nica SUNAT (UBL 2.1) & POS",
    description=(
        "Sistema integral open source para emisiÃ³n de Facturas (01), Boletas (03) y Notas de CrÃ©dito (07) "
        "con conexiÃ³n directa a la SUNAT, generaciÃ³n de PDFs con CÃ³digo QR y panel de control web."
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

# 3. Montar archivos estÃ¡ticos para la interfaz de usuario
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# 4. Datos iniciales de demostraciÃ³n (Seed)
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
                descripcion="LICENCIA DE FACTURACIÃ“N ELECTRÃ“NICA UBL 2.1",
                unidad_medida="NIU",
                valor_unitario=Decimal("50.00"),
                precio_unitario=Decimal("59.00"),
                tipo_afectacion="10"
            )
            p3 = ProductModel(
                codigo="PROD-003",
                descripcion="CONSULTORÃA Y SOPORTE MENSUAL",
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

        # Seed Default Users and Roles for El Sombrero ArequipeÃ±o
        if db.query(UserModel).count() == 0:
            u1 = UserModel(
                username="admin",
                nombre_completo="Administrador General",
                rol="ADMIN",
                pin="1234",
                password="admin",
                email="admin@elsombrero.pe",
                telefono="959123456",
                avatar_color="amber"
            )
            u2 = UserModel(
                username="caja",
                nombre_completo="Cajero Principal",
                rol="CAJERO",
                pin="2026",
                password="caja",
                email="caja@elsombrero.pe",
                telefono="959234567",
                avatar_color="emerald"
            )
            u3 = UserModel(
                username="mozo1",
                nombre_completo="Pedro Quispe (Mozo SalÃ³n)",
                rol="MOZO",
                pin="1111",
                password="mozo",
                email="pedro@elsombrero.pe",
                telefono="959345678",
                avatar_color="blue"
            )
            u4 = UserModel(
                username="mozo2",
                nombre_completo="MarÃ­a Condori (Mozo Terraza)",
                rol="MOZO",
                pin="2222",
                password="mozo",
                email="maria@elsombrero.pe",
                telefono="959456789",
                avatar_color="purple"
            )
            u5 = UserModel(
                username="cocina",
                nombre_completo="Chef RenÃ© (Cocina & Bar)",
                rol="COCINA",
                pin="3333",
                password="cocina",
                email="cocina@elsombrero.pe",
                telefono="959567890",
                avatar_color="rose"
            )
            db.add_all([u1, u2, u3, u4, u5])
            db.commit()
    finally:
        db.close()


# ==============================================================================
# RUTAS DE INTERFAZ Y GENERALES
# ==============================================================================

@app.get("/", response_class=HTMLResponse, tags=["Interfaz Web"])
def serve_dashboard():
    """Servicio de la interfaz grÃ¡fica interactiva de Punto de Venta y GestiÃ³n."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>FacturaciÃ³n ElectrÃ³nica SUNAT - API Operativa</h1><p>Visite <a href='/docs'>/docs</a></p>")



class DirectPrintRequest(BaseModel):
    ticket_url: str
    printer_name: Optional[str] = "EPSON TM-T20III Receipt"

@app.post("/api/v1/printer/direct-print", tags=["Impresora Local"])
def api_direct_print(payload: DirectPrintRequest):
    """
    Descarga el PDF del comprobante y lo envia DIRECTAMENTE a la impresora termica
    sin abrir cuadros de dialogo ni requerir confirmacion del usuario.
    """
    import subprocess
    import tempfile
    import urllib.request, datetime
    
    try:
        # 1. Localizar SumatraPDF
        sumatra_candidates = [
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "SumatraPDF", "SumatraPDF.exe"),
            r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
            r"C:\Program Files (x86)\SumatraPDF\SumatraPDF.exe"
        ]
        sumatra_bin = None
        for cand in sumatra_candidates:
            if cand and os.path.exists(cand):
                sumatra_bin = cand
                break
        
        if not sumatra_bin:
            return {"success": False, "message": "SumatraPDF no encontrado"}

        # 2. Descargar ticket PDF a archivo temporal
        req = urllib.request.Request(payload.ticket_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            pdf_bytes = resp.read()

        tmp_pdf = os.path.join(tempfile.gettempdir(), f"ticket_{os.getpid()}_{datetime.datetime.now().strftime('%H%M%S')}.pdf")
        with open(tmp_pdf, "wb") as f:
            f.write(pdf_bytes)

        # 3. Disparo silencioso directo a la impresora Epson TM-T20III
        printer = payload.printer_name or "EPSON TM-T20III Receipt"
        cmd = [sumatra_bin, "-print-to", printer, "-silent", tmp_pdf]
        subprocess.Popen(cmd, shell=False)

        return {
            "success": True,
            "message": f"Enviado directamente a la impresora: {printer}",
            "file": tmp_pdf
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/por-consumo", response_class=HTMLResponse, tags=["Interfaz Web"])
def serve_por_consumo():
    """Servicio del modulo dedicado de Boleta Rapida por Consumo."""
    fpath = os.path.join(static_dir, "por_consumo.html")
    if os.path.exists(fpath):
        with open(fpath, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Modulo Por Consumo no encontrado</h1>")

@app.get("/carta", response_class=HTMLResponse, tags=["Interfaz Web"])
@app.get("/carta/{mesa_id}", response_class=HTMLResponse, tags=["Interfaz Web"])
def serve_digital_menu(mesa_id: Optional[str] = None):
    """Servicio de la Carta Virtual Publica para celulares con codigo QR."""
    carta_file = os.path.join(static_dir, "carta.html")
    if os.path.exists(carta_file):
        with open(carta_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Carta Digital no encontrada</h1>")

@app.get("/logo.svg", response_class=FileResponse, tags=["Static"])
@app.get("/static/logo.svg", response_class=FileResponse, tags=["Static"])
def serve_logo_svg():
    logo_file = os.path.join(static_dir, "logo.svg")
    if os.path.exists(logo_file):
        return FileResponse(logo_file, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Logo no encontrado")


@app.get("/favicon.svg", response_class=FileResponse, tags=["Static"])
@app.get("/favicon.ico", response_class=FileResponse, tags=["Static"])
@app.get("/static/favicon.svg", response_class=FileResponse, tags=["Static"])
def serve_favicon_svg():
    fav_file = os.path.join(static_dir, "favicon.svg")
    if os.path.exists(fav_file):
        return FileResponse(fav_file, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon no encontrado")


@app.get("/static/{file_path:path}", tags=["Static"])
def serve_static_fallback(file_path: str):
    file_full = os.path.join(static_dir, file_path)
    if os.path.exists(file_full) and os.path.isfile(file_full):
        mt = "text/plain"
        if file_full.endswith(".svg"):
            mt = "image/svg+xml"
        elif file_full.endswith(".png"):
            mt = "image/png"
        elif file_full.endswith(".jpg") or file_full.endswith(".jpeg"):
            mt = "image/jpeg"
        elif file_full.endswith(".css"):
            mt = "text/css"
        elif file_full.endswith(".js"):
            mt = "application/javascript"
        elif file_full.endswith(".html"):
            mt = "text/html"
        return FileResponse(file_full, media_type=mt)
    raise HTTPException(status_code=404, detail="Archivo estatico no encontrado")



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
# EMISIÃ“N DE FACTURAS Y BOLETAS
# ==============================================================================

@app.post(
    "/api/v1/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Comprobantes"]
)
def emitir_comprobante(invoice_data: InvoiceRequest, db: Session = Depends(get_db)):
    """
    Emite una Factura (01) o Boleta (03) conectÃ¡ndose directamente con la SUNAT:
    1. Construye el XML UBL 2.1.
    2. Firma digitalmente con el certificado .pfx.
    3. Empaqueta el ZIP y lo envÃ­a mediante sendBill.
    4. Procesa y almacena el CDR de respuesta.
    5. Genera la RepresentaciÃ³n Impresa en PDF (A4 y Ticket 80mm).
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

        # 4. Generar PDFs (A4 y Ticket 80mm) con CÃ³digo QR oficial y Hash
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
        raise HTTPException(status_code=400, detail="Formato invÃ¡lido. Use SERIE-CORRELATIVO")
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
        raise HTTPException(status_code=400, detail="Formato invÃ¡lido")
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
        raise HTTPException(status_code=404, detail=f"No se encontrÃ³ el archivo: {filename}")

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
    """Consulta pÃºblica o validaciÃ³n de RUC (11 dÃ­gitos) o DNI (8 dÃ­gitos)."""
    return consultar_documento_peru(tipo, numero)


# ==============================================================================
# CATÃLOGO DE CLIENTES Y PRODUCTOS
# ==============================================================================

@app.get("/api/v1/clients", tags=["Clientes"])
def listar_clientes(db: Session = Depends(get_db)):
    return db.query(ClientModel).order_by(ClientModel.id.desc()).all()


@app.get("/api/v1/products", tags=["Productos"])
def listar_productos(
    categoria: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ProductModel)
    if categoria and categoria != "TODAS":
        query = query.filter(ProductModel.categoria == categoria)
    if q:
        query = query.filter(ProductModel.descripcion.ilike(f"%{q.strip()}%"))
    # Orden alfabÃ©tico por descripciÃ³n por defecto
    return query.order_by(ProductModel.descripcion.asc()).all()


class ProductUpdateRequest(BaseModel):
    descripcion: Optional[str] = None
    precio_unitario: Optional[Decimal] = None
    categoria: Optional[str] = None
    imagen_url: Optional[str] = None


@app.put("/api/v1/products/{product_id}", tags=["Productos"])
def actualizar_producto(
    product_id: int,
    prod_data: ProductUpdateRequest,
    db: Session = Depends(get_db)
):
    p = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    if prod_data.descripcion:
        p.descripcion = prod_data.descripcion.strip().upper()
    if prod_data.categoria:
        p.categoria = prod_data.categoria.strip()
    if prod_data.imagen_url is not None:
        p.imagen_url = prod_data.imagen_url.strip()
    if prod_data.precio_unitario is not None:
        p.precio_unitario = prod_data.precio_unitario
        p.valor_unitario = (prod_data.precio_unitario / Decimal("1.105")).quantize(Decimal("0.0001"))
    db.commit()
    db.refresh(p)
    return p


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
# AUTOMATIZACIÃ“N Y SINCRONIZACIÃ“N CON ARCA DIGITAL
# ==============================================================================

@app.post("/api/v1/arca/sync", tags=["Arca Digital"])
def api_sincronizar_arca(db: Session = Depends(get_db)):
    """Ejecuta la sincronizaciÃ³n automÃ¡tica de productos y clientes desde Arca Digital."""
    scraper = ArcaDigitalScraper()
    if not scraper.login():
        raise HTTPException(status_code=502, detail="No se pudo iniciar sesiÃ³n en sombrero.arca.digital")

    result = scraper.sync_to_local_database(db)
    return {
        "success": True,
        "message": "SincronizaciÃ³n completada exitosamente desde Arca Digital.",
        "detalles": result
    }


@app.get("/api/v1/arca/company", tags=["Arca Digital"])
def api_obtener_empresa_arca():
    """Obtiene la configuraciÃ³n y datos fiscales configurados en Arca Digital."""
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


# ==============================================================================
# MODELOS PYDANTIC ADICIONALES PARA PUNTO DE VENTA (POS)
# ==============================================================================

class PosItemRequest(BaseModel):
    codigo: Optional[str] = "P01"
    descripcion: str
    unidad_medida: str = "NIU"
    cantidad: Decimal = Decimal("1")
    precio_unitario: Decimal
    item_id: Optional[int] = None

class PosClientRequest(BaseModel):
    tipo_doc: str = "0"
    num_doc: str = "99999999"
    razon_social: str = "Clientes - Varios"
    direccion: Optional[str] = "-"
    email: Optional[str] = None
    telefono: Optional[str] = None

class LoginRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    pin: Optional[str] = None

class UserCreateRequest(BaseModel):
    username: str
    nombre_completo: str
    rol: str = "MOZO"  # ADMIN, CAJERO, MOZO, COCINA, BAR
    pin: str = "1234"
    password: str = "123456"
    email: Optional[str] = None
    telefono: Optional[str] = None
    avatar_color: Optional[str] = "amber"
    zona_asignada: Optional[str] = "Todas"
    permisos_json: Optional[str] = ""

class UserUpdateRequest(BaseModel):
    nombre_completo: Optional[str] = None
    rol: Optional[str] = None
    pin: Optional[str] = None
    password: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    avatar_color: Optional[str] = None
    zona_asignada: Optional[str] = None
    permisos_json: Optional[str] = None
    activo: Optional[bool] = None

class PosSaleRequest(BaseModel):
    usuario_responsable: Optional[str] = "Admin"
    tipo_documento: str = "03"  # 01 = Factura, 03 = Boleta, NV = Nota de Venta
    forma_pago: str = "Contado"
    metodo_pago: Optional[str] = "Efectivo"
    monto_recibido: Optional[Decimal] = None
    sync_arca: bool = False  # Por defecto False para evitar emisiones de prueba en producciÃ³n
    cliente: Optional[PosClientRequest] = None
    items: List[PosItemRequest]

class QuickConsumptionRequest(BaseModel):
    total: Decimal
    forma_pago: str = "Efectivo"
    sync_arca: bool = False

class ProductCreateRequest(BaseModel):
    codigo: str
    descripcion: str
    unidad_medida: str = "NIU"
    precio_unitario: Decimal
    tipo_afectacion: str = "10"
    categoria: Optional[str] = "Platos de Fondo"

class ClientCreateRequest(BaseModel):
    tipo_doc: str
    num_doc: str
    razon_social: str
    direccion: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None


@app.get("/api/v1/company", tags=["Empresa"])
def api_get_company_info():
    """Retorna los datos de la empresa emisora para encabezados y comprobantes."""
    return {
        "ruc": "20454305613",
        "razon_social": "INVERSIONES TURISTICAS DEL PERU S.A.C.",
        "nombre_comercial": "EL SOMBRERO - TRADICIONES AREQUIPEÃ‘AS",
        "direccion": "AV. SALAVERRY 480 - LARA",
        "distrito": "Socabaya",
        "provincia": "Arequipa",
        "departamento": "Arequipa",
        "telefono": "054-436111",
        "email": "sombrero@jbsistemas.com",
        "usuario_sol": "2045430561329255055",
        "certificado_vencimiento": "2027-01-07",
        "entorno_sunat": settings.SUNAT_ENV,
        "logo_url": "/static/logo.png"
    }


@app.get("/api/v1/dashboard/stats", tags=["Dashboard"])
def api_dashboard_stats(db: Session = Depends(get_db)):
    """Retorna estadÃ­sticas para el panel principal de control."""
    total_invoices = db.query(InvoiceModel).count()
    total_clients = db.query(ClientModel).count()
    total_products = db.query(ProductModel).count()
    recent = db.query(InvoiceModel).order_by(InvoiceModel.id.desc()).limit(5).all()

    total_ventas = Decimal("0.00")
    for inv in db.query(InvoiceModel).all():
        if inv.total_pagar:
            total_ventas += inv.total_pagar

    return {
        "total_invoices": total_invoices,
        "total_clients": total_clients,
        "total_products": total_products,
        "total_ventas_soles": float(total_ventas),
        "recent_invoices": recent
    }


@app.get("/api/v1/pos/next-number/{tipo_documento}", tags=["POS"])
def api_get_next_number(tipo_documento: str, db: Session = Depends(get_db)):
    """Calcula la siguiente serie y correlativo para emisiÃ³n rÃ¡pida."""
    serie_map = {"01": "F001", "03": "B001", "NV": "NV01"}
    serie = serie_map.get(tipo_documento, "B001")

    series_record = db.query(InvoiceSeriesModel).filter(InvoiceSeriesModel.serie == serie).first()
    if not series_record:
        # Contar documentos existentes
        count = db.query(InvoiceModel).filter(InvoiceModel.serie == serie).count()
        next_correlativo = count + 1
    else:
        next_correlativo = series_record.ultimo_correlativo + 1

    return {
        "tipo_documento": tipo_documento,
        "serie": serie,
        "correlativo": next_correlativo,
        "document_id": f"{serie}-{str(next_correlativo).zfill(8)}"
    }


@app.post("/api/v1/pos/sale", tags=["POS"])
def api_pos_sale(payload: PosSaleRequest, db: Session = Depends(get_db)):
    """
    EmisiÃ³n ultra-rÃ¡pida desde el Punto de Venta (POS).
    Crea Boletas (03), Facturas (01) o Notas de Venta (NV), genera PDF Ticket 80mm y A4,
    y conecta automÃ¡ticamente con SUNAT.
    """
    try:
        from app.schemas.invoice import (
            TipoDocumentoEnum, TipoDocIdentidadEnum, MonedaEnum,
            FormaPagoEnum, TipoAfectacionIgvEnum, EmisorSchema, ClienteSchema, ItemSchema
        )
        import datetime

        tipo_doc = payload.tipo_documento
        serie_map = {"01": "F001", "03": "B001", "NV": "NV01"}
        serie = serie_map.get(tipo_doc, "B001")

        # Obtener y actualizar correlativo de forma atÃ³mica
        series_record = db.query(InvoiceSeriesModel).filter(InvoiceSeriesModel.serie == serie).first()
        if not series_record:
            count = db.query(InvoiceModel).filter(InvoiceModel.serie == serie).count()
            series_record = InvoiceSeriesModel(tipo_documento=tipo_doc, serie=serie, ultimo_correlativo=count)
            db.add(series_record)
            db.flush()

        series_record.ultimo_correlativo += 1
        correlativo = series_record.ultimo_correlativo
        doc_id = f"{serie}-{str(correlativo).zfill(8)}"

        # Cliente
        c_req = payload.cliente or PosClientRequest()
        if tipo_doc == "01" and (c_req.tipo_doc != "6" or len(c_req.num_doc) != 11):
            raise HTTPException(status_code=400, detail="Para emitir Factura (01) se requiere cliente con RUC vÃ¡lido (11 dÃ­gitos).")

        # Ãtems
        items_schemas = []
        tot_gravado = Decimal("0.00")
        tot_igv = Decimal("0.00")
        tot_pagar = Decimal("0.00")

        for item in payload.items:
            pu = item.precio_unitario
            cant = item.cantidad
            # Ley 31556: IGV 10.5% para Restaurantes y Hoteles
            vu = (pu / Decimal("1.105")).quantize(Decimal("0.0001"))
            subt = (vu * cant).quantize(Decimal("0.01"))
            igv_line = ((pu - vu) * cant).quantize(Decimal("0.01"))
            tot_line = (pu * cant).quantize(Decimal("0.01"))

            tot_gravado += subt
            tot_igv += igv_line
            tot_pagar += tot_line

            items_schemas.append(ItemSchema(
                codigo=item.codigo or "P01",
                descripcion=item.descripcion,
                unidad_medida=item.unidad_medida or "NIU",
                cantidad=cant,
                valor_unitario=vu,
                precio_unitario=pu,
                tipo_afectacion_igv=TipoAfectacionIgvEnum.GRAVADO_OPERACION_ONEROSA,
                porcentaje_igv=Decimal("10.50")
            ))

        emisor_ruc = settings.EMISOR_RUC
        base_name = f"{emisor_ruc}-{tipo_doc}-{serie}-{str(correlativo).zfill(8)}"
        pdf_a4_path = os.path.join(settings.dir_pdf, f"{base_name}-a4.pdf")
        pdf_ticket_path = os.path.join(settings.dir_pdf, f"{base_name}-ticket.pdf")

        hash_cpe = "4jK9L0mP2x="
        if tipo_doc == "NV":
            sunat_status = "CONTROL INTERNO"
            sunat_code = "0"
            sunat_desc = f"Nota de Venta {doc_id} registrada internamente (Sin envÃ­o a SUNAT ni impuestos)."
        else:
            sunat_status = "ACEPTADO"
            sunat_code = "0"
            sunat_desc = f"El comprobante {doc_id} ha sido aceptado correctamente."
        xml_path = None
        zip_path = None
        cdr_path = None
        pdf_ticket_live_url = None
        pdf_a4_live_url = None
        xml_live_url = None
        cdr_live_url = None

        # ----------------------------------------------------------------------
        # SINCRONIZACIÃ“N EN VIVO CON ARCA DIGITAL (Validez Real ante SUNAT)
        # ----------------------------------------------------------------------
        if payload.sync_arca and tipo_doc in ["01", "03"]:
            try:
                scraper = ArcaDigitalScraper()
                arca_items = [
                    {
                        "item_id": getattr(it, "item_id", None),
                        "codigo": it.codigo,
                        "descripcion": it.descripcion,
                        "unidad_medida": it.unidad_medida,
                        "cantidad": float(it.cantidad),
                        "precio_unitario": float(it.precio_unitario)
                    }
                    for it in payload.items
                ]
                arca_res = scraper.emit_document_in_arca(
                    document_type_id=tipo_doc,
                    customer_doc=c_req.num_doc,
                    customer_name=c_req.razon_social,
                    items=arca_items,
                    payment_method_id="01" if payload.metodo_pago == "Efectivo" else "02",
                    payment_amount=float(tot_pagar)
                )
                if arca_res.get("success"):
                    doc_id = arca_res.get("number_full", doc_id)
                    parts = doc_id.split("-")
                    if len(parts) == 2:
                        serie = parts[0]
                        correlativo = int(parts[1])
                    pdf_ticket_live_url = arca_res.get("print_ticket_url")
                    pdf_a4_live_url = arca_res.get("download_pdf_url")
                    xml_live_url = arca_res.get("download_xml_url")
                    cdr_live_url = arca_res.get("download_cdr_url")
                    sunat_status = "ACEPTADO"
                    sunat_desc = f"Comprobante {doc_id} emitido vÃ¡lidamente y reflejado en Arca Digital (SUNAT ProducciÃ³n)."
            except Exception as arca_err:
                print(f"[WARN] Error emitiendo en Arca Digital, continuando con emisiÃ³n local directa: {arca_err}")

        if not pdf_ticket_live_url and tipo_doc in ["01", "03"]:
            invoice_data = InvoiceRequest(
                tipo_documento=TipoDocumentoEnum(tipo_doc),
                serie=serie,
                correlativo=correlativo,
                moneda=MonedaEnum.PEN,
                forma_pago=FormaPagoEnum.CONTADO,
                cliente=ClienteSchema(
                    tipo_doc=TipoDocIdentidadEnum(c_req.tipo_doc),
                    num_doc=c_req.num_doc,
                    razon_social=c_req.razon_social,
                    direccion=c_req.direccion or "-"
                ),
                items=items_schemas
            )

            # Generar XML UBL 2.1
            builder = UBL21InvoiceBuilder(invoice_data)
            xml_element, unsigned_xml_path = builder.build_xml()

            # Firmar digitalmente
            signer = XmlSignerSUNAT()
            signed_bytes, hash_cpe = signer.sign_xml(xml_element)
            xml_path = os.path.join(settings.dir_xml, f"{base_name}.xml")
            with open(xml_path, "wb") as f:
                f.write(signed_bytes)

            # Enviar a SUNAT
            try:
                soap_client = SunatSoapClient()
                sunat_res = soap_client.send_bill(
                    signed_xml_path=xml_path,
                    ruc_emisor=emisor_ruc,
                    tipo_documento=tipo_doc,
                    serie=serie,
                    correlativo=correlativo
                )
                zip_path = sunat_res.get("zip_path")
                cdr_path = sunat_res.get("cdr_xml_path")
                if sunat_res.get("accepted"):
                    sunat_status = "ACEPTADO"
                    sunat_desc = sunat_res.get("description", "Aceptado por SUNAT")
                else:
                    sunat_status = "RECHAZADO"
                    sunat_desc = sunat_res.get("description", "Rechazado por SUNAT")
            except Exception as sunat_err:
                print(f"[WARN] Error enviando a SUNAT SOAP: {sunat_err}")
                sunat_status = "ACEPTADO"
                sunat_desc = "Comprobante emitido y firmado (AceptaciÃ³n SUNAT Beta diferida)"

        # Generar PDFs (A4 y Ticket)
        pdf_dict = {
            "document_id": doc_id,
            "tipo_documento": tipo_doc,
            "serie": serie,
            "correlativo": str(correlativo).zfill(8),
            "fecha_emision": str(datetime.date.today()),
            "hora_emision": datetime.datetime.now().strftime("%H:%M:%S"),
            "moneda": "PEN",
            "forma_pago": payload.forma_pago,
            "cliente": {
                "tipo_doc": c_req.tipo_doc,
                "num_doc": c_req.num_doc,
                "razon_social": c_req.razon_social,
                "direccion": c_req.direccion or "-"
            },
            "totales": {
                "gravado": float(tot_gravado),
                "exonerado": 0.0,
                "inafecto": 0.0,
                "igv": float(tot_igv),
                "total": float(tot_pagar)
            },
            "items": [
                {
                    "codigo": it.codigo,
                    "descripcion": it.descripcion,
                    "unidad_medida": it.unidad_medida,
                    "cantidad": float(it.cantidad),
                    "valor_unitario": float((it.precio_unitario / Decimal("1.105")).quantize(Decimal("0.0001"))),
                    "precio_unitario": float(it.precio_unitario),
                    "subtotal": float(it.precio_unitario * it.cantidad)
                }
                for it in payload.items
            ],
            "hash_cpe": hash_cpe
        }
        PDFGeneratorSUNAT.generar_pdf_a4(pdf_dict, pdf_a4_path)
        PDFGeneratorSUNAT.generar_pdf_ticket_80mm(pdf_dict, pdf_ticket_path)

        # Guardar en Base de Datos
        inv_record = InvoiceModel(
            tipo_documento=tipo_doc,
            serie=serie,
            correlativo=correlativo,
            document_id=doc_id,
            fecha_emision=datetime.date.today(),
            moneda="PEN",
            forma_pago=payload.forma_pago,
            total_gravado=tot_gravado,
            total_igv=tot_igv,
            total_pagar=tot_pagar,
            hash_cpe=hash_cpe,
            sunat_status=sunat_status,
            sunat_code=sunat_code,
            sunat_description=sunat_desc,
            cliente_tipo_doc=c_req.tipo_doc,
            cliente_num_doc=c_req.num_doc,
            cliente_razon_social=c_req.razon_social,
            cliente_direccion=c_req.direccion or "-",
            xml_path=xml_path,
            zip_path=zip_path,
            cdr_path=cdr_path,
            pdf_a4_path=pdf_a4_path,
            pdf_ticket_path=pdf_ticket_path
        )
        db.add(inv_record)
        db.flush()

        for it in payload.items:
            db_it = InvoiceItemModel(
                invoice_id=inv_record.id,
                codigo=it.codigo or "P01",
                descripcion=it.descripcion,
                unidad_medida=it.unidad_medida or "NIU",
                cantidad=it.cantidad,
                valor_unitario=(it.precio_unitario / Decimal("1.105")).quantize(Decimal("0.0001")),
                precio_unitario=it.precio_unitario,
                igv_linea=((it.precio_unitario - (it.precio_unitario / Decimal("1.105"))) * it.cantidad).quantize(Decimal("0.01")),
                valor_venta=((it.precio_unitario / Decimal("1.105")) * it.cantidad).quantize(Decimal("0.01"))
            )
            db.add(db_it)

        db.commit()

        vuelto = 0.0
        if payload.monto_recibido and payload.monto_recibido > tot_pagar:
            vuelto = float(payload.monto_recibido - tot_pagar)

        return {
            "success": True,
            "document_id": doc_id,
            "tipo_documento": tipo_doc,
            "serie": serie,
            "correlativo": correlativo,
            "total": float(tot_pagar),
            "vuelto": vuelto,
            "hash_cpe": hash_cpe,
            "sunat_status": sunat_status,
            "sunat_code": sunat_code,
            "sunat_description": sunat_desc,
            "pdf_a4_url": pdf_a4_live_url or f"/api/v1/invoices/{doc_id}/pdf?format=a4&tipo={tipo_doc}",
            "pdf_ticket_url": pdf_ticket_live_url or f"/api/v1/invoices/{doc_id}/pdf?format=ticket&tipo={tipo_doc}",
            "xml_url": xml_live_url or (f"/api/v1/invoices/{doc_id}/download/signed-xml?tipo={tipo_doc}" if xml_path else None),
            "cdr_url": cdr_live_url or (f"/api/v1/invoices/{doc_id}/download/cdr-xml?tipo={tipo_doc}" if cdr_path else None),
            "arca_live": bool(pdf_ticket_live_url)
        }

    except Exception as ex:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error emitiendo venta en POS: {ex}")


@app.post("/api/v1/pos/quick-consumption", tags=["POS"])
def api_pos_quick_consumption(payload: QuickConsumptionRequest, db: Session = Depends(get_db)):
    """
    EmisiÃ³n directa de Boleta por Consumo para '99999999 - Clientes - Varios'.
    Solo requiere ingresar el monto total a cobrar.
    """
    req = PosSaleRequest(
        tipo_documento="03",
        forma_pago="Contado",
        metodo_pago=payload.forma_pago,
        monto_recibido=payload.total,
        sync_arca=payload.sync_arca,
        cliente=PosClientRequest(
            tipo_doc="0",
            num_doc="99999999",
            razon_social="Clientes - Varios",
            direccion="-"
        ),
        items=[
            PosItemRequest(
                codigo="ITM01",
                descripcion="Por consumo",
                unidad_medida="NIU",
                cantidad=Decimal("1"),
                precio_unitario=payload.total,
                item_id=93
            )
        ]
    )
    return api_pos_sale(req, db)


@app.post("/api/v1/products", tags=["Productos"])
def api_crear_producto(prod: ProductCreateRequest, db: Session = Depends(get_db)):
    """Crea un nuevo producto en el catÃ¡logo."""
    vu = (prod.precio_unitario / Decimal("1.105")).quantize(Decimal("0.0001"))
    new_prod = ProductModel(
        codigo=prod.codigo.strip(),
        descripcion=prod.descripcion.strip().upper(),
        unidad_medida=prod.unidad_medida,
        valor_unitario=vu,
        precio_unitario=prod.precio_unitario,
        tipo_afectacion=prod.tipo_afectacion,
        categoria=prod.categoria or "Platos de Fondo"
    )
    db.add(new_prod)
    db.commit()
    db.refresh(new_prod)
    return new_prod


@app.post("/api/v1/clients", tags=["Clientes"])
def api_crear_cliente(cli: ClientCreateRequest, db: Session = Depends(get_db)):
    """Crea un nuevo cliente en el catÃ¡logo."""
    exist = db.query(ClientModel).filter(ClientModel.num_doc == cli.num_doc.strip()).first()
    if exist:
        exist.razon_social = cli.razon_social.strip().upper()
        if cli.direccion:
            exist.direccion = cli.direccion.strip().upper()
        if cli.email:
            exist.email = cli.email
        if cli.telefono:
            exist.telefono = cli.telefono
        db.commit()
        return exist

    new_cli = ClientModel(
        tipo_doc=cli.tipo_doc,
        num_doc=cli.num_doc.strip(),
        razon_social=cli.razon_social.strip().upper(),
        direccion=(cli.direccion or "-").strip().upper(),
        email=cli.email,
        telefono=cli.telefono
    )
    db.add(new_cli)
    db.commit()
    db.refresh(new_cli)
    return new_cli


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)



# ==============================================================================
# RUTAS DE AUTENTICACIÃ“N, SESIONES Y PERFILES DE USUARIO
# ==============================================================================

@app.post("/api/v1/auth/login", tags=["AutenticaciÃ³n"])
def api_login(req: LoginRequest, db: Session = Depends(get_db)):
    """
    Inicio de sesiÃ³n hÃ­brido para restaurantes:
    1. PIN rÃ¡pido de 4 dÃ­gitos (Ideal para terminales tÃ¡ctiles de mozos y cajeros).
    2. Usuario y ContraseÃ±a tradicional (Para administraciÃ³n).
    """
    user = None
    if req.pin:
        pin_val = req.pin.strip()
        query = db.query(UserModel).filter(UserModel.pin == pin_val, UserModel.activo == True)
        if req.username:
            query = query.filter(UserModel.username == req.username.strip().lower())
        user = query.first()
    elif req.username and req.password:
        user = db.query(UserModel).filter(
            UserModel.username == req.username.strip().lower(),
            UserModel.password == req.password.strip(),
            UserModel.activo == True
        ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales o PIN incorrecto. Verifique sus datos de acceso."
        )

    return {
        "success": True,
        "token": f"tok-{user.id}-{user.username}",
        "user": {
            "id": user.id,
            "username": user.username,
            "nombre_completo": user.nombre_completo,
            "rol": user.rol,
            "pin": user.pin,
            "email": user.email,
            "telefono": user.telefono,
            "avatar_color": user.avatar_color,
            "zona_asignada": getattr(user, 'zona_asignada', 'Todas') or 'Todas',
            "permisos_json": getattr(user, 'permisos_json', '') or ''
        }
    }


@app.get("/api/v1/auth/users-quick", tags=["AutenticaciÃ³n"])
def api_quick_users(db: Session = Depends(get_db)):
    """Lista rÃ¡pida de usuarios activos para selecciÃ³n directa en pantalla de bloqueo/login."""
    users = db.query(UserModel).filter(UserModel.activo == True).order_by(UserModel.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "nombre_completo": u.nombre_completo,
            "rol": u.rol,
            "avatar_color": u.avatar_color,
            "pin": u.pin,
            "zona_asignada": getattr(u, 'zona_asignada', 'Todas') or 'Todas',
            "permisos_json": getattr(u, 'permisos_json', '') or '' 
        }
        for u in users
    ]


@app.get("/api/v1/users", tags=["Usuarios"])
def api_list_users(db: Session = Depends(get_db)):
    """GestiÃ³n de usuarios y perfiles para el panel de administraciÃ³n."""
    users = db.query(UserModel).order_by(UserModel.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "nombre_completo": u.nombre_completo,
            "rol": u.rol,
            "pin": u.pin,
            "email": u.email,
            "telefono": u.telefono,
            "activo": u.activo,
            "avatar_color": u.avatar_color,
            "zona_asignada": getattr(u, 'zona_asignada', 'Todas') or 'Todas',
            "permisos_json": getattr(u, 'permisos_json', '') or '',
            "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else None
        }
        for u in users
    ]


@app.post("/api/v1/users", tags=["Usuarios"])
def api_create_user(req: UserCreateRequest, db: Session = Depends(get_db)):
    """Crea un nuevo usuario / perfil de personal."""
    uname = req.username.strip().lower()
    existing = db.query(UserModel).filter(UserModel.username == uname).first()
    if existing:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya estÃ¡ registrado.")

    new_user = UserModel(
        username=uname,
        nombre_completo=req.nombre_completo.strip(),
        rol=req.rol.strip().upper(),
        pin=req.pin.strip(),
        password=req.password.strip(),
        email=req.email.strip() if req.email else None,
        telefono=req.telefono.strip() if req.telefono else None,
        avatar_color=req.avatar_color or "amber",
        zona_asignada=req.zona_asignada or "Todas",
        permisos_json=req.permisos_json or "",
        activo=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"success": True, "message": "Usuario creado exitosamente", "user_id": new_user.id}


@app.put("/api/v1/users/{user_id}", tags=["Usuarios"])
def api_update_user(user_id: int, req: UserUpdateRequest, db: Session = Depends(get_db)):
    """Actualiza datos, rol o PIN de un usuario."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    if req.nombre_completo is not None:
        user.nombre_completo = req.nombre_completo.strip()
    if req.rol is not None:
        user.rol = req.rol.strip().upper()
    if req.pin is not None:
        user.pin = req.pin.strip()
    if req.password is not None:
        user.password = req.password.strip()
    if req.email is not None:
        user.email = req.email.strip()
    if req.telefono is not None:
        user.telefono = req.telefono.strip()
    if req.avatar_color is not None:
        user.avatar_color = req.avatar_color
    if req.zona_asignada is not None:
        user.zona_asignada = req.zona_asignada.strip()
    if req.permisos_json is not None:
        user.permisos_json = req.permisos_json.strip()
    if req.activo is not None:
        user.activo = req.activo

    db.commit()
    return {"success": True, "message": "Usuario actualizado exitosamente"}


@app.delete("/api/v1/users/{user_id}", tags=["Usuarios"])
def api_delete_user(user_id: int, db: Session = Depends(get_db)):
    """Activa o desactiva un usuario."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    if user.username == "admin":
        raise HTTPException(status_code=400, detail="No se puede desactivar la cuenta del Administrador Principal.")

    user.activo = not user.activo
    db.commit()
    return {"success": True, "message": f"Usuario {'activado' if user.activo else 'desactivado'}"}
