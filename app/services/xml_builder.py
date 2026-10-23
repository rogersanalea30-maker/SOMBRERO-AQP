"""
Generador de XML bajo el estándar UBL 2.1 para Facturación Electrónica SUNAT (Perú).
Soporta Factura (01) y Boleta de Venta (03) con operaciones Gravadas, Exoneradas e Inafectas.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Tuple, Dict, Any
from lxml import etree

from app.config import settings
from app.schemas.invoice import (
    InvoiceRequest,
    TipoAfectacionIgvEnum,
    FormaPagoEnum
)
from app.services.number_to_letter import monto_en_letras


# Espacios de nombres oficiales UBL 2.1 SUNAT
NSMAP = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ccts": "urn:un:unece:uncefact:documentation:2",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "qdt": "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2",
    "udt": "urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

CAC = f"{{{NSMAP['cac']}}}"
CBC = f"{{{NSMAP['cbc']}}}"
EXT = f"{{{NSMAP['ext']}}}"


class UBL21InvoiceBuilder:
    """Constructor de comprobantes UBL 2.1 para Facturas y Boletas de SUNAT."""

    def __init__(self, invoice_data: InvoiceRequest):
        self.data = invoice_data
        self.moneda = self.data.moneda.value
        self._resolver_emisor()
        self._calcular_totales()

    def _resolver_emisor(self):
        """Asigna los datos del emisor desde el payload o toma los valores por defecto del sistema."""
        emisor = self.data.emisor
        self.emisor_ruc = emisor.ruc if emisor else settings.EMISOR_RUC
        self.emisor_razon_social = emisor.razon_social if emisor else settings.EMISOR_RAZON_SOCIAL
        self.emisor_nombre_comercial = (emisor.nombre_comercial if emisor and emisor.nombre_comercial 
                                       else settings.EMISOR_NOMBRE_COMERCIAL)
        self.emisor_ubigeo = emisor.ubigeo if emisor else settings.EMISOR_UBIGEO
        self.emisor_direccion = emisor.direccion if emisor else settings.EMISOR_DIRECCION
        self.emisor_codigo_establecimiento = (emisor.codigo_establecimiento if emisor 
                                              else settings.EMISOR_CODIGO_ESTABLECIMIENTO)

    def _calcular_totales(self):
        """Calcula subtotales, impuestos y totales generales del comprobante."""
        self.total_gravado = Decimal("0.00")
        self.total_exonerado = Decimal("0.00")
        self.total_inafecto = Decimal("0.00")
        self.total_igv = Decimal("0.00")
        self.lineas_calculadas = []

        for item in self.data.items:
            cantidad = item.cantidad
            valor_unitario = item.valor_unitario.quantize(Decimal("0.0001"))
            # Valor de venta de la línea = cantidad * valor_unitario
            valor_venta = (cantidad * valor_unitario).quantize(Decimal("0.01"))
            
            tipo_afec = item.tipo_afectacion_igv.value
            porcentaje_igv = item.porcentaje_igv

            if tipo_afec in ("10", "11", "12", "13", "14", "15", "16", "17"):
                # Operaciones gravadas
                igv_linea = (valor_venta * (porcentaje_igv / Decimal("100"))).quantize(Decimal("0.01"))
                self.total_gravado += valor_venta
                self.total_igv += igv_linea
                tributo_codigo = "1000"
                tributo_nombre = "IGV"
                tributo_tipo = "VAT"
                categoria_id = "S"
            elif tipo_afec == "20":
                # Exonerado
                igv_linea = Decimal("0.00")
                self.total_exonerado += valor_venta
                tributo_codigo = "9997"
                tributo_nombre = "EXO"
                tributo_tipo = "VAT"
                categoria_id = "E"
            else:
                # Inafecto / Gratuito
                igv_linea = Decimal("0.00")
                self.total_inafecto += valor_venta
                tributo_codigo = "9998"
                tributo_nombre = "INA"
                tributo_tipo = "FRE"
                categoria_id = "O"

            precio_unitario = item.precio_unitario.quantize(Decimal("0.01")) if item.precio_unitario else (
                (valor_unitario * (Decimal("1") + porcentaje_igv / Decimal("100"))).quantize(Decimal("0.01"))
            )

            self.lineas_calculadas.append({
                "item": item,
                "valor_unitario": valor_unitario,
                "precio_unitario": precio_unitario,
                "valor_venta": valor_venta,
                "igv_linea": igv_linea,
                "tributo_codigo": tributo_codigo,
                "tributo_nombre": tributo_nombre,
                "tributo_tipo": tributo_tipo,
                "categoria_id": categoria_id
            })

        self.total_valor_venta = (self.total_gravado + self.total_exonerado + self.total_inafecto).quantize(Decimal("0.01"))
        self.total_precio_venta = (self.total_valor_venta + self.total_igv).quantize(Decimal("0.01"))
        self.total_a_pagar = self.total_precio_venta

    def build_xml(self) -> Tuple[etree._Element, bytes]:
        """Construye y serializa el árbol XML conforme al estándar UBL 2.1."""
        root = etree.Element("Invoice", nsmap=NSMAP)

        # 1. Contenedor de Extensiones UBL para la Firma Digital
        ubl_extensions = etree.SubElement(root, f"{EXT}UBLExtensions")
        ubl_extension = etree.SubElement(ubl_extensions, f"{EXT}UBLExtension")
        etree.SubElement(ubl_extension, f"{EXT}ExtensionContent")

        # 2. Versión de UBL y Personalización SUNAT
        ubl_version = etree.SubElement(root, f"{CBC}UBLVersionID")
        ubl_version.text = "2.1"

        customization = etree.SubElement(root, f"{CBC}CustomizationID")
        customization.text = "2.0"

        # 3. Identificador de Comprobante (Serie-Correlativo)
        doc_id = etree.SubElement(root, f"{CBC}ID")
        doc_id.text = self.data.id_comprobante

        # 4. Fechas y Horas de Emisión
        fecha_emision = self.data.fecha_emision or date.today()
        issue_date = etree.SubElement(root, f"{CBC}IssueDate")
        issue_date.text = fecha_emision.strftime("%Y-%m-%d")

        hora_emision = self.data.hora_emision or datetime.now().time()
        issue_time = etree.SubElement(root, f"{CBC}IssueTime")
        issue_time.text = hora_emision.strftime("%H:%M:%S")

        if self.data.fecha_vencimiento:
            due_date = etree.SubElement(root, f"{CBC}DueDate")
            due_date.text = self.data.fecha_vencimiento.strftime("%Y-%m-%d")

        # 5. Tipo de Documento (Catálogo 01: 01=Factura, 03=Boleta)
        invoice_type = etree.SubElement(
            root,
            f"{CBC}InvoiceTypeCode",
            listAgencyName="PE:SUNAT",
            listName="Tipo de Documento",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01",
            listID="0101"  # Catálogo 51: Venta interna
        )
        invoice_type.text = self.data.tipo_documento.value

        # 6. Leyenda: Monto en Letras (Catálogo 52: 1000 = Monto en Letras)
        monto_letras = monto_en_letras(self.total_a_pagar, self.moneda)
        note = etree.SubElement(root, f"{CBC}Note", languageLocaleID="1000")
        note.text = monto_letras

        # Observaciones adicionales
        if self.data.observaciones:
            note_obs = etree.SubElement(root, f"{CBC}Note")
            note_obs.text = self.data.observaciones

        # 7. Moneda del Documento (Catálogo 02)
        doc_currency = etree.SubElement(
            root,
            f"{CBC}DocumentCurrencyCode",
            listID="ISO 4217 Alpha",
            listName="Currency",
            listAgencyName="United Nations Economic Commission for Europe"
        )
        doc_currency.text = self.moneda

        # 8. Declaración de Firma
        signature = etree.SubElement(root, f"{CAC}Signature")
        sig_id = etree.SubElement(signature, f"{CBC}ID")
        sig_id.text = "SignSUNAT"

        signatory_party = etree.SubElement(signature, f"{CAC}SignatoryParty")
        party_id = etree.SubElement(signatory_party, f"{CAC}PartyIdentification")
        p_id = etree.SubElement(party_id, f"{CBC}ID")
        p_id.text = self.emisor_ruc

        party_name = etree.SubElement(signatory_party, f"{CAC}PartyName")
        p_name = etree.SubElement(party_name, f"{CBC}Name")
        p_name.text = etree.CDATA(self.emisor_razon_social)

        sig_attachment = etree.SubElement(signature, f"{CAC}DigitalSignatureAttachment")
        ext_ref = etree.SubElement(sig_attachment, f"{CAC}ExternalReference")
        ext_uri = etree.SubElement(ext_ref, f"{CBC}URI")
        ext_uri.text = "#SignSUNAT"

        # 9. Datos del Emisor (AccountingSupplierParty)
        supplier = etree.SubElement(root, f"{CAC}AccountingSupplierParty")
        party_supplier = etree.SubElement(supplier, f"{CAC}Party")
        
        sup_party_id = etree.SubElement(party_supplier, f"{CAC}PartyIdentification")
        sup_id = etree.SubElement(
            sup_party_id,
            f"{CBC}ID",
            schemeID="6",
            schemeName="Documento de Identidad",
            schemeAgencyName="PE:SUNAT",
            schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06"
        )
        sup_id.text = self.emisor_ruc

        if self.emisor_nombre_comercial:
            sup_party_name = etree.SubElement(party_supplier, f"{CAC}PartyName")
            sup_p_name = etree.SubElement(sup_party_name, f"{CBC}Name")
            sup_p_name.text = etree.CDATA(self.emisor_nombre_comercial)

        sup_legal_entity = etree.SubElement(party_supplier, f"{CAC}PartyLegalEntity")
        sup_reg_name = etree.SubElement(sup_legal_entity, f"{CBC}RegistrationName")
        sup_reg_name.text = etree.CDATA(self.emisor_razon_social)

        sup_reg_address = etree.SubElement(sup_legal_entity, f"{CAC}RegistrationAddress")
        sup_address_type = etree.SubElement(sup_reg_address, f"{CBC}AddressTypeCode")
        sup_address_type.text = self.emisor_codigo_establecimiento

        sup_address_line = etree.SubElement(sup_reg_address, f"{CAC}AddressLine")
        sup_line = etree.SubElement(sup_address_line, f"{CBC}Line")
        sup_line.text = etree.CDATA(self.emisor_direccion)

        # 10. Datos del Cliente / Receptor (AccountingCustomerParty)
        customer = etree.SubElement(root, f"{CAC}AccountingCustomerParty")
        party_customer = etree.SubElement(customer, f"{CAC}Party")

        cust_party_id = etree.SubElement(party_customer, f"{CAC}PartyIdentification")
        cust_id = etree.SubElement(
            cust_party_id,
            f"{CBC}ID",
            schemeID=self.data.cliente.tipo_doc.value,
            schemeName="Documento de Identidad",
            schemeAgencyName="PE:SUNAT",
            schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06"
        )
        cust_id.text = self.data.cliente.num_doc

        cust_legal_entity = etree.SubElement(party_customer, f"{CAC}PartyLegalEntity")
        cust_reg_name = etree.SubElement(cust_legal_entity, f"{CBC}RegistrationName")
        cust_reg_name.text = etree.CDATA(self.data.cliente.razon_social)

        if self.data.cliente.direccion:
            cust_reg_address = etree.SubElement(cust_legal_entity, f"{CAC}RegistrationAddress")
            cust_address_line = etree.SubElement(cust_reg_address, f"{CAC}AddressLine")
            cust_line = etree.SubElement(cust_address_line, f"{CBC}Line")
            cust_line.text = etree.CDATA(self.data.cliente.direccion)

        # 11. Forma de Pago (PaymentTerms)
        payment_terms = etree.SubElement(root, f"{CAC}PaymentTerms")
        pay_id = etree.SubElement(payment_terms, f"{CBC}ID")
        pay_id.text = "FormaPago"

        pay_means = etree.SubElement(payment_terms, f"{CBC}PaymentMeansID")
        pay_means.text = self.data.forma_pago.value

        pay_amount = etree.SubElement(payment_terms, f"{CBC}Amount", currencyID=self.moneda)
        pay_amount.text = f"{self.total_a_pagar:.2f}"

        if self.data.forma_pago == FormaPagoEnum.CREDITO and self.data.cuotas:
            for cuota in self.data.cuotas:
                cuota_terms = etree.SubElement(root, f"{CAC}PaymentTerms")
                c_id = etree.SubElement(cuota_terms, f"{CBC}ID")
                c_id.text = "FormaPago"
                c_means = etree.SubElement(cuota_terms, f"{CBC}PaymentMeansID")
                c_means.text = cuota.cuota
                c_amount = etree.SubElement(cuota_terms, f"{CBC}Amount", currencyID=self.moneda)
                c_amount.text = f"{cuota.monto:.2f}"
                c_date = etree.SubElement(cuota_terms, f"{CBC}PaymentDueDate")
                c_date.text = cuota.fecha_vencimiento.strftime("%Y-%m-%d")

        # 12. Totales de Impuestos (TaxTotal)
        tax_total = etree.SubElement(root, f"{CAC}TaxTotal")
        tax_amount = etree.SubElement(tax_total, f"{CBC}TaxAmount", currencyID=self.moneda)
        tax_amount.text = f"{self.total_igv:.2f}"

        # Subtotal Gravado
        if self.total_gravado > 0 or (self.total_exonerado == 0 and self.total_inafecto == 0):
            self._crear_tax_subtotal(tax_total, self.total_gravado, self.total_igv, "S", "1000", "IGV", "VAT")

        # Subtotal Exonerado
        if self.total_exonerado > 0:
            self._crear_tax_subtotal(tax_total, self.total_exonerado, Decimal("0.00"), "E", "9997", "EXO", "VAT")

        # Subtotal Inafecto
        if self.total_inafecto > 0:
            self._crear_tax_subtotal(tax_total, self.total_inafecto, Decimal("0.00"), "O", "9998", "INA", "FRE")

        # 13. Totales Monetarios Legales (LegalMonetaryTotal)
        monetary_total = etree.SubElement(root, f"{CAC}LegalMonetaryTotal")
        
        line_ext = etree.SubElement(monetary_total, f"{CBC}LineExtensionAmount", currencyID=self.moneda)
        line_ext.text = f"{self.total_valor_venta:.2f}"

        tax_inclusive = etree.SubElement(monetary_total, f"{CBC}TaxInclusiveAmount", currencyID=self.moneda)
        tax_inclusive.text = f"{self.total_precio_venta:.2f}"

        payable_amount = etree.SubElement(monetary_total, f"{CBC}PayableAmount", currencyID=self.moneda)
        payable_amount.text = f"{self.total_a_pagar:.2f}"

        # 14. Líneas de Ítems (InvoiceLine)
        for idx, linea in enumerate(self.lineas_calculadas, start=1):
            item = linea["item"]
            inv_line = etree.SubElement(root, f"{CAC}InvoiceLine")

            line_id = etree.SubElement(inv_line, f"{CBC}ID")
            line_id.text = str(idx)

            qty = etree.SubElement(
                inv_line,
                f"{CBC}InvoicedQuantity",
                unitCode=item.unidad_medida,
                unitCodeListID="UN/ECE rec 20",
                unitCodeListAgencyName="United Nations Economic Commission for Europe"
            )
            qty.text = f"{item.cantidad:.2f}"

            line_ext_amount = etree.SubElement(inv_line, f"{CBC}LineExtensionAmount", currencyID=self.moneda)
            line_ext_amount.text = f"{linea['valor_venta']:.2f}"

            # PricingReference
            pricing_ref = etree.SubElement(inv_line, f"{CAC}PricingReference")
            alt_cond = etree.SubElement(pricing_ref, f"{CAC}AlternativeConditionPrice")
            price_amount = etree.SubElement(alt_cond, f"{CBC}PriceAmount", currencyID=self.moneda)
            price_amount.text = f"{linea['precio_unitario']:.2f}"
            price_type = etree.SubElement(
                alt_cond,
                f"{CBC}PriceTypeCode",
                listName="Tipo de Precio",
                listAgencyName="PE:SUNAT",
                listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16"
            )
            price_type.text = "01"  # Catálogo 16: Precio unitario incluye tributos

            # TaxTotal de la línea
            line_tax_total = etree.SubElement(inv_line, f"{CAC}TaxTotal")
            line_tax_amt = etree.SubElement(line_tax_total, f"{CBC}TaxAmount", currencyID=self.moneda)
            line_tax_amt.text = f"{linea['igv_linea']:.2f}"

            line_tax_sub = etree.SubElement(line_tax_total, f"{CAC}TaxSubtotal")
            taxable_amt = etree.SubElement(line_tax_sub, f"{CBC}TaxableAmount", currencyID=self.moneda)
            taxable_amt.text = f"{linea['valor_venta']:.2f}"
            sub_tax_amt = etree.SubElement(line_tax_sub, f"{CBC}TaxAmount", currencyID=self.moneda)
            sub_tax_amt.text = f"{linea['igv_linea']:.2f}"

            tax_cat = etree.SubElement(line_tax_sub, f"{CAC}TaxCategory")
            tax_cat_id = etree.SubElement(
                tax_cat,
                f"{CBC}ID",
                schemeID="UN/ECE 5305",
                schemeName="Tax Category Identifier",
                schemeAgencyName="United Nations Economic Commission for Europe"
            )
            tax_cat_id.text = linea["categoria_id"]

            tax_percent = etree.SubElement(tax_cat, f"{CBC}Percent")
            tax_percent.text = f"{item.porcentaje_igv:.2f}"

            exemption_code = etree.SubElement(
                tax_cat,
                f"{CBC}TaxExemptionReasonCode",
                listAgencyName="PE:SUNAT",
                listName="Afectacion del IGV",
                listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07"
            )
            exemption_code.text = item.tipo_afectacion_igv.value

            tax_scheme = etree.SubElement(tax_cat, f"{CAC}TaxScheme")
            scheme_id = etree.SubElement(tax_scheme, f"{CBC}ID", schemeID="UN/ECE 5153", schemeAgencyID="6")
            scheme_id.text = linea["tributo_codigo"]
            scheme_name = etree.SubElement(tax_scheme, f"{CBC}Name")
            scheme_name.text = linea["tributo_nombre"]
            scheme_type = etree.SubElement(tax_scheme, f"{CBC}TaxTypeCode")
            scheme_type.text = linea["tributo_tipo"]

            # Item
            item_elem = etree.SubElement(inv_line, f"{CAC}Item")
            desc = etree.SubElement(item_elem, f"{CBC}Description")
            desc.text = etree.CDATA(item.descripcion)

            if item.codigo:
                sellers_id = etree.SubElement(item_elem, f"{CAC}SellersItemIdentification")
                s_id = etree.SubElement(sellers_id, f"{CBC}ID")
                s_id.text = item.codigo

            # Price (Valor unitario sin IGV)
            price_elem = etree.SubElement(inv_line, f"{CAC}Price")
            val_unit = etree.SubElement(price_elem, f"{CBC}PriceAmount", currencyID=self.moneda)
            val_unit.text = f"{linea['valor_unitario']:.4f}"

        # Serialización a bytes con encoding UTF-8 y declaración XML
        xml_bytes = etree.tostring(
            root,
            pretty_print=True,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=False
        )
        return root, xml_bytes

    def _crear_tax_subtotal(self, parent: etree._Element, taxable: Decimal, tax: Decimal,
                           cat_id: str, scheme_code: str, scheme_name_str: str, scheme_type_str: str):
        """Crea un nodo cac:TaxSubtotal dentro de cac:TaxTotal."""
        tax_subtotal = etree.SubElement(parent, f"{CAC}TaxSubtotal")
        
        taxable_amt = etree.SubElement(tax_subtotal, f"{CBC}TaxableAmount", currencyID=self.moneda)
        taxable_amt.text = f"{taxable:.2f}"

        sub_tax_amt = etree.SubElement(tax_subtotal, f"{CBC}TaxAmount", currencyID=self.moneda)
        sub_tax_amt.text = f"{tax:.2f}"

        tax_cat = etree.SubElement(tax_subtotal, f"{CAC}TaxCategory")
        tax_cat_id = etree.SubElement(
            tax_cat,
            f"{CBC}ID",
            schemeID="UN/ECE 5305",
            schemeName="Tax Category Identifier",
            schemeAgencyName="United Nations Economic Commission for Europe"
        )
        tax_cat_id.text = cat_id

        tax_scheme = etree.SubElement(tax_cat, f"{CAC}TaxScheme")
        scheme_id = etree.SubElement(tax_scheme, f"{CBC}ID", schemeID="UN/ECE 5153", schemeAgencyID="6")
        scheme_id.text = scheme_code
        scheme_name = etree.SubElement(tax_scheme, f"{CBC}Name")
        scheme_name.text = scheme_name_str
        scheme_type = etree.SubElement(tax_scheme, f"{CBC}TaxTypeCode")
        scheme_type.text = scheme_type_str
