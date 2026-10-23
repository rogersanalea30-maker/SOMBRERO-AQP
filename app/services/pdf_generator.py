"""
Generador de Representación Impresa en PDF para Comprobantes Electrónicos SUNAT.
Soporta dos formatos estándar:
1. Formato A4 Corporativo
2. Formato Ticket Térmico (80mm) para puntos de venta (POS)
Incluye Código QR oficial SUNAT, resumen Hash (DigestValue) y montos en letras.
"""

import io
import os
from decimal import Decimal
from typing import Dict, Any, List
from fpdf import FPDF
import qrcode
from PIL import Image

from app.config import settings
from app.services.number_to_letter import monto_en_letras


def generar_qr_sunat(
    ruc_emisor: str,
    tipo_documento: str,
    serie: str,
    correlativo: str,
    igv: Decimal | float,
    total: Decimal | float,
    fecha_emision: str,
    tipo_doc_cliente: str,
    num_doc_cliente: str,
    hash_cpe: str
) -> io.BytesIO:
    """
    Genera el código QR oficial exigido por SUNAT con la cadena de control:
    RUC|TipoDoc|Serie|Correlativo|IGV|Total|Fecha|TipoDocCliente|NumDocCliente|Hash|
    """
    qr_data = (
        f"{ruc_emisor}|"
        f"{tipo_documento}|"
        f"{serie}|"
        f"{correlativo}|"
        f"{float(igv):.2f}|"
        f"{float(total):.2f}|"
        f"{fecha_emision}|"
        f"{tipo_doc_cliente}|"
        f"{num_doc_cliente}|"
        f"{hash_cpe}|"
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    return img_buffer


class PDFGeneratorSUNAT:
    """Generador de PDFs en formatos A4 y Ticket 80mm."""

    @staticmethod
    def get_tipo_comprobante_texto(tipo_documento: str) -> str:
        mapping = {
            "01": "FACTURA ELECTRÓNICA",
            "03": "BOLETA DE VENTA ELECTRÓNICA",
            "07": "NOTA DE CRÉDITO ELECTRÓNICA",
            "08": "NOTA DE DÉBITO ELECTRÓNICA",
        }
        return mapping.get(tipo_documento, "COMPROBANTE ELECTRÓNICO")

    @classmethod
    def generar_pdf_a4(cls, invoice_data: Dict[str, Any], output_path: str) -> str:
        """Genera el PDF en formato A4 estándar."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_margins(12, 12, 12)

        # 1. Cabecera (Datos de la Empresa vs Recuadro RUC)
        emisor = invoice_data.get("emisor") or {}
        emisor_ruc = emisor.get("ruc") if emisor and emisor.get("ruc") else settings.EMISOR_RUC
        emisor_rs = emisor.get("razon_social") if emisor and emisor.get("razon_social") else settings.EMISOR_RAZON_SOCIAL
        emisor_dir = emisor.get("direccion") if emisor and emisor.get("direccion") else settings.EMISOR_DIRECCION

        # Nombre y datos de la empresa (Columna izquierda)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(24, 43, 73)
        pdf.cell(115, 6, emisor_rs, ln=True)

        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(80, 80, 80)
        pdf.multi_cell(115, 4, f"Dirección: {emisor_dir}\nTeléfono: (01) 500-1234 | Email: contacto@empresa.pe\nLima - Perú")

        # Recuadro RUC y Tipo de Documento (Columna derecha)
        tipo_texto = cls.get_tipo_comprobante_texto(invoice_data["tipo_documento"])
        serie = invoice_data["serie"]
        correlativo = str(invoice_data["correlativo"]).zfill(8)

        pdf.set_xy(135, 12)
        pdf.set_draw_color(24, 43, 73)
        pdf.set_line_width(0.5)
        pdf.rect(132, 12, 66, 26)

        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.set_xy(132, 15)
        pdf.cell(66, 5, f"R.U.C. {emisor_ruc}", align="C", ln=True)
        
        pdf.set_font("helvetica", "B", 9)
        pdf.set_xy(132, 21)
        pdf.cell(66, 5, tipo_texto, align="C", ln=True)

        pdf.set_font("helvetica", "B", 11)
        pdf.set_xy(132, 28)
        pdf.cell(66, 6, f"Nº {serie}-{correlativo}", align="C", ln=True)

        pdf.ln(12)

        # 2. Datos del Cliente
        cliente = invoice_data["cliente"]
        pdf.set_fill_color(245, 247, 250)
        pdf.rect(12, 43, 186, 24, "F")
        pdf.rect(12, 43, 186, 24, "D")

        pdf.set_xy(14, 45)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(26, 4, "FECHA EMISIÓN:", ln=False)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(50, 4, str(invoice_data.get("fecha_emision", "Hoy")), ln=False)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(20, 4, "MONEDA:", ln=False)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(30, 4, invoice_data.get("moneda", "PEN"), ln=False)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(25, 4, "FORMA PAGO:", ln=False)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(30, 4, invoice_data.get("forma_pago", "Contado"), ln=True)

        pdf.set_x(14)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(26, 4, "SEÑOR(ES):", ln=False)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(150, 4, cliente["razon_social"], ln=True)

        pdf.set_x(14)
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(26, 4, "DOC. IDENTIDAD:", ln=False)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(60, 4, f"{cliente['num_doc']} (Tipo {cliente['tipo_doc']})", ln=False)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(20, 4, "DIRECCIÓN:", ln=False)
        pdf.set_font("helvetica", "", 8)
        pdf.cell(75, 4, cliente.get("direccion", "-") or "-", ln=True)

        pdf.ln(8)

        # 3. Tabla de Productos / Servicios
        pdf.set_fill_color(24, 43, 73)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 8)

        # Encabezados
        col_w = [18, 16, 92, 20, 20, 20]
        headers = ["CANT.", "UNIDAD", "DESCRIPCIÓN", "V. UNIT", "P. UNIT", "TOTAL"]
        for i, h in enumerate(headers):
            pdf.cell(col_w[i], 6, h, border=1, align="C", fill=True)
        pdf.ln()

        # Filas de ítems
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("helvetica", "", 8)

        total_gravado = Decimal("0.00")
        total_igv = Decimal("0.00")
        total_pagar = Decimal("0.00")

        fill_row = False
        for item in invoice_data["items"]:
            pdf.set_fill_color(250, 250, 250) if fill_row else pdf.set_fill_color(255, 255, 255)
            cantidad = Decimal(str(item["cantidad"]))
            v_unit = Decimal(str(item["valor_unitario"]))
            p_unit = Decimal(str(item.get("precio_unitario") or (v_unit * Decimal("1.18"))))
            v_venta = (cantidad * v_unit).quantize(Decimal("0.01"))
            igv_line = (v_venta * Decimal("0.18")).quantize(Decimal("0.01"))
            p_total = (v_venta + igv_line).quantize(Decimal("0.01"))

            total_gravado += v_venta
            total_igv += igv_line
            total_pagar += p_total

            pdf.cell(col_w[0], 5, f"{cantidad:.2f}", border="LR", align="C", fill=fill_row)
            pdf.cell(col_w[1], 5, item.get("unidad_medida", "NIU"), border="LR", align="C", fill=fill_row)
            pdf.cell(col_w[2], 5, item["descripcion"][:55], border="LR", align="L", fill=fill_row)
            pdf.cell(col_w[3], 5, f"{v_unit:.2f}", border="LR", align="R", fill=fill_row)
            pdf.cell(col_w[4], 5, f"{p_unit:.2f}", border="LR", align="R", fill=fill_row)
            pdf.cell(col_w[5], 5, f"{p_total:.2f}", border="LR", align="R", fill=fill_row)
            pdf.ln()
            fill_row = not fill_row

        # Línea de cierre inferior de la tabla
        pdf.cell(sum(col_w), 1, "", border="T", ln=True)
        pdf.ln(4)

        # 4. Sección Inferior: Monto en Letras, Código QR y Totales
        y_bottom_start = pdf.get_y()

        # Monto en letras
        letras = monto_en_letras(total_pagar, invoice_data.get("moneda", "PEN"))
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(120, 5, letras, ln=True)

        # Generar código QR
        qr_buf = generar_qr_sunat(
            ruc_emisor=emisor_ruc,
            tipo_documento=invoice_data["tipo_documento"],
            serie=serie,
            correlativo=correlativo,
            igv=total_igv,
            total=total_pagar,
            fecha_emision=str(invoice_data.get("fecha_emision", "2026-10-23")),
            tipo_doc_cliente=cliente["tipo_doc"],
            num_doc_cliente=cliente["num_doc"],
            hash_cpe=invoice_data.get("hash_cpe", "")
        )

        pdf.image(qr_buf, x=14, y=pdf.get_y() + 2, w=28)

        # Resumen Hash y aviso legal al lado del QR
        pdf.set_xy(45, pdf.get_y() + 4)
        pdf.set_font("helvetica", "B", 7)
        pdf.cell(85, 4, f"Código Hash: {invoice_data.get('hash_cpe', '-')}", ln=True)
        pdf.set_x(45)
        pdf.set_font("helvetica", "", 6)
        pdf.multi_cell(
            85, 3,
            "Representación impresa del Comprobante de Pago Electrónico.\n"
            "Emitido directamente conforme a la normativa SUNAT UBL 2.1.\n"
            "Consulte la validez de este comprobante en: www.sunat.gob.pe"
        )

        # Totales alineados a la derecha
        pdf.set_xy(135, y_bottom_start)
        pdf.set_font("helvetica", "B", 8)
        
        pdf.cell(30, 5, "OP. GRAVADA:", border=1, fill=True)
        pdf.cell(23, 5, f"{total_gravado:.2f}", border=1, align="R", ln=True)
        pdf.set_x(135)
        pdf.cell(30, 5, "I.G.V. (18%):", border=1, fill=True)
        pdf.cell(23, 5, f"{total_igv:.2f}", border=1, align="R", ln=True)
        pdf.set_x(135)
        pdf.set_font("helvetica", "B", 9)
        pdf.set_fill_color(24, 43, 73)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(30, 6, "TOTAL:", border=1, fill=True)
        pdf.cell(23, 6, f"{total_pagar:.2f}", border=1, align="R", fill=True, ln=True)

        pdf.output(output_path)
        return output_path

    @classmethod
    def generar_pdf_ticket_80mm(cls, invoice_data: Dict[str, Any], output_path: str) -> str:
        """Genera el comprobante en formato Ticket Térmico de 80mm para puntos de venta."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # 80mm de ancho x 220mm de alto
        pdf = FPDF(orientation="P", unit="mm", format=(80, 220))
        pdf.set_margins(4, 4, 4)
        pdf.set_auto_page_break(auto=True, margin=6)
        pdf.add_page()

        emisor = invoice_data.get("emisor") or {}
        emisor_ruc = emisor.get("ruc") if emisor and emisor.get("ruc") else settings.EMISOR_RUC
        emisor_rs = emisor.get("razon_social") if emisor and emisor.get("razon_social") else settings.EMISOR_RAZON_SOCIAL
        emisor_dir = emisor.get("direccion") if emisor and emisor.get("direccion") else settings.EMISOR_DIRECCION

        # Encabezado
        pdf.set_font("helvetica", "B", 10)
        pdf.cell(72, 4, emisor_rs[:30], align="C", ln=True)
        pdf.set_font("helvetica", "", 7)
        pdf.cell(72, 3, f"RUC: {emisor_ruc}", align="C", ln=True)
        pdf.multi_cell(72, 3, emisor_dir, align="C")
        pdf.ln(1)
        pdf.cell(72, 1, "-" * 50, align="C", ln=True)

        # Tipo y Serie
        tipo_texto = cls.get_tipo_comprobante_texto(invoice_data["tipo_documento"])
        serie = invoice_data["serie"]
        correlativo = str(invoice_data["correlativo"]).zfill(8)

        pdf.set_font("helvetica", "B", 8)
        pdf.cell(72, 4, tipo_texto, align="C", ln=True)
        pdf.cell(72, 4, f"{serie}-{correlativo}", align="C", ln=True)
        pdf.cell(72, 1, "-" * 50, align="C", ln=True)

        # Datos de Cliente
        cliente = invoice_data["cliente"]
        pdf.set_font("helvetica", "", 7)
        pdf.cell(72, 3, f"Fecha: {invoice_data.get('fecha_emision', 'Hoy')}", ln=True)
        pdf.cell(72, 3, f"Cliente: {cliente['razon_social'][:35]}", ln=True)
        pdf.cell(72, 3, f"Doc: {cliente['num_doc']}", ln=True)
        pdf.cell(72, 1, "-" * 50, align="C", ln=True)

        # Ítems
        pdf.set_font("helvetica", "B", 6)
        pdf.cell(10, 3, "CANT", ln=False)
        pdf.cell(42, 3, "DESCRIPCIÓN", ln=False)
        pdf.cell(20, 3, "TOTAL", align="R", ln=True)
        pdf.set_font("helvetica", "", 6)

        total_pagar = Decimal("0.00")
        for item in invoice_data["items"]:
            cant = Decimal(str(item["cantidad"]))
            v_unit = Decimal(str(item["valor_unitario"]))
            p_unit = Decimal(str(item.get("precio_unitario") or (v_unit * Decimal("1.18"))))
            p_total = (cant * p_unit).quantize(Decimal("0.01"))
            total_pagar += p_total

            pdf.cell(10, 3, f"{cant:.1f}", ln=False)
            pdf.cell(42, 3, item["descripcion"][:28], ln=False)
            pdf.cell(20, 3, f"{p_total:.2f}", align="R", ln=True)

        pdf.cell(72, 1, "-" * 50, align="C", ln=True)

        # Totales
        pdf.set_font("helvetica", "B", 8)
        pdf.cell(45, 4, "TOTAL A PAGAR:", ln=False)
        pdf.cell(27, 4, f"{invoice_data.get('moneda', 'PEN')} {total_pagar:.2f}", align="R", ln=True)

        # Monto en letras
        pdf.set_font("helvetica", "", 6)
        pdf.multi_cell(72, 3, monto_en_letras(total_pagar, invoice_data.get("moneda", "PEN")), align="C")

        # QR y Hash
        qr_buf = generar_qr_sunat(
            ruc_emisor=emisor_ruc,
            tipo_documento=invoice_data["tipo_documento"],
            serie=serie,
            correlativo=correlativo,
            igv=total_pagar * Decimal("0.18"),
            total=total_pagar,
            fecha_emision=str(invoice_data.get("fecha_emision", "2026-10-23")),
            tipo_doc_cliente=cliente["tipo_doc"],
            num_doc_cliente=cliente["num_doc"],
            hash_cpe=invoice_data.get("hash_cpe", "")
        )
        pdf.image(qr_buf, x=26, y=pdf.get_y() + 1, w=28)
        pdf.set_y(pdf.get_y() + 30)

        pdf.set_font("helvetica", "", 5)
        pdf.cell(72, 3, f"Hash: {invoice_data.get('hash_cpe', '-')}", align="C", ln=True)
        pdf.cell(72, 3, "Consulte su comprobante en www.sunat.gob.pe", align="C", ln=True)

        pdf.output(output_path)
        return output_path
