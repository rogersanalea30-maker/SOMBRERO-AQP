"""
Constructor de Notas de Crédito Electrónicas (07) bajo el estándar UBL 2.1 de SUNAT.
Permite anular o corregir Facturas (01) y Boletas de Venta (03).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Tuple, Dict, Any, List
from lxml import etree

from app.config import settings
from app.services.number_to_letter import monto_en_letras

# Namespaces oficiales UBL 2.1 para CreditNote
NSMAP_CN = {
    None: "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ccts": "urn:un:unece:uncefact:documentation:2",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "qdt": "urn:oasis:names:specification:ubl:schema:xsd:QualifiedDatatypes-2",
    "udt": "urn:un:unece:uncefact:data:specification:UnqualifiedDataTypesSchemaModule:2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

CAC = f"{{{NSMAP_CN['cac']}}}"
CBC = f"{{{NSMAP_CN['cbc']}}}"
EXT = f"{{{NSMAP_CN['ext']}}}"


class UBL21CreditNoteBuilder:
    """Constructor de Notas de Crédito (07) UBL 2.1."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.moneda = data.get("moneda", "PEN")
        self.emisor_ruc = settings.EMISOR_RUC
        self.emisor_rs = settings.EMISOR_RAZON_SOCIAL
        self.emisor_dir = settings.EMISOR_DIRECCION
        self.emisor_ubigeo = settings.EMISOR_UBIGEO
        self.emisor_cod_est = settings.EMISOR_CODIGO_ESTABLECIMIENTO

    def build_xml(self) -> Tuple[etree._Element, bytes]:
        root = etree.Element("CreditNote", nsmap=NSMAP_CN)

        # 1. Contenedor de Extensiones UBL para la Firma Digital
        ubl_extensions = etree.SubElement(root, f"{EXT}UBLExtensions")
        ubl_extension = etree.SubElement(ubl_extensions, f"{EXT}UBLExtension")
        etree.SubElement(ubl_extension, f"{EXT}ExtensionContent")

        # 2. Versión UBL y Personalización
        ubl_ver = etree.SubElement(root, f"{CBC}UBLVersionID")
        ubl_ver.text = "2.1"
        cust_id = etree.SubElement(root, f"{CBC}CustomizationID")
        cust_id.text = "2.0"

        # 3. ID de la Nota de Crédito (ej. FC01-00000001 o BC01-00000001)
        doc_id = etree.SubElement(root, f"{CBC}ID")
        doc_id.text = f"{self.data['serie']}-{str(self.data['correlativo']).zfill(8)}"

        # 4. Fechas y Horas
        issue_date = etree.SubElement(root, f"{CBC}IssueDate")
        issue_date.text = str(self.data.get("fecha_emision", date.today().strftime("%Y-%m-%d")))

        issue_time = etree.SubElement(root, f"{CBC}IssueTime")
        issue_time.text = datetime.now().strftime("%H:%M:%S")

        # 5. Motivo de Discrepancia (Catálogo 09: 01=Anulación de la operación, etc.)
        doc_afectado = self.data["documento_afectado"]
        motivo_codigo = self.data.get("motivo_codigo", "01")
        motivo_desc = self.data.get("motivo_descripcion", "ANULACION DE LA OPERACION")

        discrepancy = etree.SubElement(root, f"{CAC}DiscrepancyResponse")
        ref_id = etree.SubElement(discrepancy, f"{CBC}ReferenceID")
        ref_id.text = doc_afectado["document_id"]
        resp_code = etree.SubElement(
            discrepancy,
            f"{CBC}ResponseCode",
            listAgencyName="PE:SUNAT",
            listName="Tipo de nota de credito",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo09"
        )
        resp_code.text = motivo_codigo
        desc_el = etree.SubElement(discrepancy, f"{CBC}Description")
        desc_el.text = etree.CDATA(motivo_desc)

        # 6. Referencia del Documento Afectado (BillingReference)
        billing_ref = etree.SubElement(root, f"{CAC}BillingReference")
        inv_ref = etree.SubElement(billing_ref, f"{CAC}InvoiceDocumentReference")
        inv_id = etree.SubElement(inv_ref, f"{CBC}ID")
        inv_id.text = doc_afectado["document_id"]
        inv_type = etree.SubElement(
            inv_ref,
            f"{CBC}DocumentTypeCode",
            listAgencyName="PE:SUNAT",
            listName="Tipo de Documento",
            listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01"
        )
        inv_type.text = doc_afectado["tipo_documento"]

        # 7. Signature
        sig = etree.SubElement(root, f"{CAC}Signature")
        s_id = etree.SubElement(sig, f"{CBC}ID")
        s_id.text = "SignSUNAT"
        signatory = etree.SubElement(sig, f"{CAC}SignatoryParty")
        p_id = etree.SubElement(signatory, f"{CAC}PartyIdentification")
        p_id_c = etree.SubElement(p_id, f"{CBC}ID")
        p_id_c.text = self.emisor_ruc
        p_name = etree.SubElement(signatory, f"{CAC}PartyName")
        p_name_c = etree.SubElement(p_name, f"{CBC}Name")
        p_name_c.text = etree.CDATA(self.emisor_rs)

        attach = etree.SubElement(sig, f"{CAC}DigitalSignatureAttachment")
        ext_ref = etree.SubElement(attach, f"{CAC}ExternalReference")
        uri = etree.SubElement(ext_ref, f"{CBC}URI")
        uri.text = "#SignSUNAT"

        # 8. Emisor
        supplier = etree.SubElement(root, f"{CAC}AccountingSupplierParty")
        party_sup = etree.SubElement(supplier, f"{CAC}Party")
        sup_id_p = etree.SubElement(party_sup, f"{CAC}PartyIdentification")
        s_ruc = etree.SubElement(
            sup_id_p, f"{CBC}ID",
            schemeID="6",
            schemeName="Documento de Identidad",
            schemeAgencyName="PE:SUNAT",
            schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06"
        )
        s_ruc.text = self.emisor_ruc
        sup_entity = etree.SubElement(party_sup, f"{CAC}PartyLegalEntity")
        reg_name = etree.SubElement(sup_entity, f"{CBC}RegistrationName")
        reg_name.text = etree.CDATA(self.emisor_rs)

        # 9. Cliente
        cliente = self.data["cliente"]
        customer = etree.SubElement(root, f"{CAC}AccountingCustomerParty")
        party_cust = etree.SubElement(customer, f"{CAC}Party")
        cust_id_p = etree.SubElement(party_cust, f"{CAC}PartyIdentification")
        c_doc = etree.SubElement(
            cust_id_p, f"{CBC}ID",
            schemeID=cliente["tipo_doc"],
            schemeName="Documento de Identidad",
            schemeAgencyName="PE:SUNAT",
            schemeURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06"
        )
        c_doc.text = cliente["num_doc"]
        cust_entity = etree.SubElement(party_cust, f"{CAC}PartyLegalEntity")
        c_name = etree.SubElement(cust_entity, f"{CBC}RegistrationName")
        c_name.text = etree.CDATA(cliente["razon_social"])

        # 10. Totales e Ítems
        total_gravado = Decimal(str(self.data.get("total_gravado", "0.00")))
        total_igv = Decimal(str(self.data.get("total_igv", "0.00")))
        total_pagar = Decimal(str(self.data.get("total_pagar", "0.00")))

        # TaxTotal
        tax_total = etree.SubElement(root, f"{CAC}TaxTotal")
        t_amt = etree.SubElement(tax_total, f"{CBC}TaxAmount", currencyID=self.moneda)
        t_amt.text = f"{total_igv:.2f}"

        tax_sub = etree.SubElement(tax_total, f"{CAC}TaxSubtotal")
        taxable = etree.SubElement(tax_sub, f"{CBC}TaxableAmount", currencyID=self.moneda)
        taxable.text = f"{total_gravado:.2f}"
        tax_a = etree.SubElement(tax_sub, f"{CBC}TaxAmount", currencyID=self.moneda)
        tax_a.text = f"{total_igv:.2f}"
        tax_cat = etree.SubElement(tax_sub, f"{CAC}TaxCategory")
        cat_id = etree.SubElement(tax_cat, f"{CBC}ID", schemeID="UN/ECE 5305", schemeName="Tax Category Identifier", schemeAgencyName="United Nations Economic Commission for Europe")
        cat_id.text = "S"
        scheme = etree.SubElement(tax_cat, f"{CAC}TaxScheme")
        sch_id = etree.SubElement(scheme, f"{CBC}ID", schemeID="UN/ECE 5153", schemeAgencyID="6")
        sch_id.text = "1000"
        sch_name = etree.SubElement(scheme, f"{CBC}Name")
        sch_name.text = "IGV"
        sch_type = etree.SubElement(scheme, f"{CBC}TaxTypeCode")
        sch_type.text = "VAT"

        # LegalMonetaryTotal
        leg_total = etree.SubElement(root, f"{CAC}LegalMonetaryTotal")
        l_ext = etree.SubElement(leg_total, f"{CBC}LineExtensionAmount", currencyID=self.moneda)
        l_ext.text = f"{total_gravado:.2f}"
        t_inc = etree.SubElement(leg_total, f"{CBC}TaxInclusiveAmount", currencyID=self.moneda)
        t_inc.text = f"{total_pagar:.2f}"
        p_amt = etree.SubElement(leg_total, f"{CBC}PayableAmount", currencyID=self.moneda)
        p_amt.text = f"{total_pagar:.2f}"

        # CreditNoteLines
        for idx, item in enumerate(self.data["items"], start=1):
            cn_line = etree.SubElement(root, f"{CAC}CreditNoteLine")
            line_id = etree.SubElement(cn_line, f"{CBC}ID")
            line_id.text = str(idx)

            c_qty = etree.SubElement(
                cn_line, f"{CBC}CreditedQuantity",
                unitCode=item.get("unidad_medida", "NIU"),
                unitCodeListID="UN/ECE rec 20",
                unitCodeListAgencyName="United Nations Economic Commission for Europe"
            )
            c_qty.text = f"{Decimal(str(item['cantidad'])):.2f}"

            v_unit = Decimal(str(item["valor_unitario"]))
            cant = Decimal(str(item["cantidad"]))
            v_venta = (cant * v_unit).quantize(Decimal("0.01"))
            igv_line = (v_venta * Decimal("0.18")).quantize(Decimal("0.01"))

            l_amt = etree.SubElement(cn_line, f"{CBC}LineExtensionAmount", currencyID=self.moneda)
            l_amt.text = f"{v_venta:.2f}"

            # PricingReference
            pr_ref = etree.SubElement(cn_line, f"{CAC}PricingReference")
            alt_pr = etree.SubElement(pr_ref, f"{CAC}AlternativeConditionPrice")
            p_amt_el = etree.SubElement(alt_pr, f"{CBC}PriceAmount", currencyID=self.moneda)
            p_amt_el.text = f"{(v_unit * Decimal('1.18')):.2f}"
            p_type = etree.SubElement(alt_pr, f"{CBC}PriceTypeCode", listName="Tipo de Precio", listAgencyName="PE:SUNAT", listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16")
            p_type.text = "01"

            # TaxTotal
            l_tax = etree.SubElement(cn_line, f"{CAC}TaxTotal")
            l_t_amt = etree.SubElement(l_tax, f"{CBC}TaxAmount", currencyID=self.moneda)
            l_t_amt.text = f"{igv_line:.2f}"
            l_sub = etree.SubElement(l_tax, f"{CAC}TaxSubtotal")
            l_taxable = etree.SubElement(l_sub, f"{CBC}TaxableAmount", currencyID=self.moneda)
            l_taxable.text = f"{v_venta:.2f}"
            l_sub_amt = etree.SubElement(l_sub, f"{CBC}TaxAmount", currencyID=self.moneda)
            l_sub_amt.text = f"{igv_line:.2f}"
            l_cat = etree.SubElement(l_sub, f"{CAC}TaxCategory")
            l_c_id = etree.SubElement(l_cat, f"{CBC}ID", schemeID="UN/ECE 5305", schemeName="Tax Category Identifier", schemeAgencyName="United Nations Economic Commission for Europe")
            l_c_id.text = "S"
            l_pct = etree.SubElement(l_cat, f"{CBC}Percent")
            l_pct.text = "18.00"
            l_ex = etree.SubElement(l_cat, f"{CBC}TaxExemptionReasonCode", listAgencyName="PE:SUNAT", listName="Afectacion del IGV", listURI="urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07")
            l_ex.text = "10"
            l_sch = etree.SubElement(l_cat, f"{CAC}TaxScheme")
            l_s_id = etree.SubElement(l_sch, f"{CBC}ID", schemeID="UN/ECE 5153", schemeAgencyID="6")
            l_s_id.text = "1000"
            l_s_name = etree.SubElement(l_sch, f"{CBC}Name")
            l_s_name.text = "IGV"
            l_s_type = etree.SubElement(l_sch, f"{CBC}TaxTypeCode")
            l_s_type.text = "VAT"

            # Item
            it_el = etree.SubElement(cn_line, f"{CAC}Item")
            it_desc = etree.SubElement(it_el, f"{CBC}Description")
            it_desc.text = etree.CDATA(item["descripcion"])

            # Price
            pr_el = etree.SubElement(cn_line, f"{CAC}Price")
            p_val = etree.SubElement(pr_el, f"{CBC}PriceAmount", currencyID=self.moneda)
            p_val.text = f"{v_unit:.4f}"

        xml_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8")
        return root, xml_bytes
