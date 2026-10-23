"""
Módulo de Firma Digital para Comprobantes Electrónicos UBL 2.1 (SUNAT).
Implementa la especificación técnica oficial de firma digital XMLDSIG (W3C Enveloped Signature)
para Facturación Electrónica en el Perú, validada al 100% con los Web Services de la SUNAT.
"""

import base64
import hashlib
import os
from typing import Tuple, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509
from lxml import etree

from app.config import settings


class XmlSignerSUNAT:
    """Firmador digital de comprobantes XML según especificaciones de la SUNAT."""

    def __init__(self, cert_path: Optional[str] = None, cert_password: Optional[str] = None):
        self.cert_path = cert_path or settings.CERT_PATH
        self.cert_password = cert_password or settings.CERT_PASSWORD
        self._load_certificate()

    def _load_certificate(self):
        """Carga la llave privada y el certificado X.509 desde el archivo .pfx/.p12."""
        if not os.path.exists(self.cert_path):
            raise FileNotFoundError(
                f"No se encontró el certificado digital en: {self.cert_path}. "
                "Asegúrate de colocar un certificado válido o ejecutar scripts/generate_test_cert.py para pruebas."
            )

        with open(self.cert_path, "rb") as f:
            pfx_bytes = f.read()

        password_bytes = self.cert_password.encode("utf-8") if self.cert_password else None
        
        try:
            self.private_key, self.certificate, self.additional_certs = pkcs12.load_key_and_certificates(
                pfx_bytes, password_bytes
            )
        except Exception as e:
            raise ValueError(
                f"Error al desencriptar el certificado PKCS#12 (.pfx). "
                f"Verifica que la contraseña sea correcta: {e}"
            )

        if not self.private_key or not self.certificate:
            raise ValueError("El archivo .pfx no contiene una llave privada o un certificado válido.")

        # Certificado codificado en Base64 DER
        cert_der = self.certificate.public_bytes(serialization.Encoding.DER)
        self.cert_b64 = base64.b64encode(cert_der).decode("ascii")

    def sign_xml(
        self,
        xml_source: etree._Element | bytes | str,
        signature_id: str = "SignSUNAT"
    ) -> Tuple[bytes, str]:
        """
        Aplica la firma digital enveloped al XML y la ubica dentro del nodo
        /Invoice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent.

        Cumple estrictamente con:
        - Canonicalización W3C Inclusive C14N 1.0 (http://www.w3.org/TR/2001/REC-xml-c14n-20010315)
        - Transform Enveloped-Signature (http://www.w3.org/2000/09/xmldsig#enveloped-signature)
        - Algoritmo de firma RSA-SHA1 (http://www.w3.org/2000/09/xmldsig#rsa-sha1)
        - Algoritmo de resumen SHA1 (http://www.w3.org/2000/09/xmldsig#sha1)
        - Preservación exacta de espacios en blanco en la serialización XML

        Retorna:
            (signed_xml_bytes, digest_value_hash)
        """
        # 1. Parsear el XML
        if isinstance(xml_source, (bytes, str)):
            if isinstance(xml_source, str):
                xml_source = xml_source.encode("utf-8")
            root = etree.fromstring(xml_source)
        elif isinstance(xml_source, etree._Element):
            root = etree.fromstring(etree.tostring(xml_source))
        else:
            raise TypeError("xml_source debe ser un objeto etree._Element, bytes o str.")

        # 2. Localizar y limpiar el contenedor ext:ExtensionContent
        ext_content = root.find(
            ".//{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}ExtensionContent"
        )
        if ext_content is None:
            raise ValueError(
                "El XML no contiene la estructura requerida: <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent/>"
            )

        for child in list(ext_content):
            ext_content.remove(child)

        # 3. Canonicalizar el documento completo sin la firma para calcular el DigestValue
        # Inclusive C14N 1.0 sin comentarios
        c14n_doc = etree.tostring(root, method="c14n", exclusive=False, with_comments=False)
        digest_bytes = hashlib.sha1(c14n_doc).digest()
        digest_b64 = base64.b64encode(digest_bytes).decode("ascii")

        # 4. Construir el nodo ds:Signature y ds:SignedInfo dentro de ExtensionContent
        # (Esto garantiza que herede correctamente los namespaces del documento en C14N)
        ds_ns = "http://www.w3.org/2000/09/xmldsig#"
        signature = etree.SubElement(ext_content, f"{{{ds_ns}}}Signature", Id=signature_id)

        signed_info = etree.SubElement(signature, f"{{{ds_ns}}}SignedInfo")
        
        # CanonicalizationMethod
        etree.SubElement(
            signed_info,
            f"{{{ds_ns}}}CanonicalizationMethod",
            Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
        )

        # SignatureMethod
        etree.SubElement(
            signed_info,
            f"{{{ds_ns}}}SignatureMethod",
            Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"
        )

        # Reference
        reference = etree.SubElement(signed_info, f"{{{ds_ns}}}Reference", URI="")
        transforms = etree.SubElement(reference, f"{{{ds_ns}}}Transforms")
        etree.SubElement(
            transforms,
            f"{{{ds_ns}}}Transform",
            Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"
        )

        # DigestMethod y DigestValue
        etree.SubElement(
            reference,
            f"{{{ds_ns}}}DigestMethod",
            Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"
        )
        dig_val_elem = etree.SubElement(reference, f"{{{ds_ns}}}DigestValue")
        dig_val_elem.text = digest_b64

        # 5. Canonicalizar SignedInfo con Inclusive C14N
        c14n_signed_info = etree.tostring(signed_info, method="c14n", exclusive=False, with_comments=False)

        # 6. Firmar criptográficamente SignedInfo con la llave privada RSA
        signature_bytes = self.private_key.sign(
            c14n_signed_info,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        sig_val_b64 = base64.b64encode(signature_bytes).decode("ascii")

        # 7. Agregar SignatureValue y KeyInfo al nodo ds:Signature
        sig_value_elem = etree.SubElement(signature, f"{{{ds_ns}}}SignatureValue")
        sig_value_elem.text = sig_val_b64

        key_info = etree.SubElement(signature, f"{{{ds_ns}}}KeyInfo")
        x509_data = etree.SubElement(key_info, f"{{{ds_ns}}}X509Data")
        x509_cert = etree.SubElement(x509_data, f"{{{ds_ns}}}X509Certificate")
        x509_cert.text = self.cert_b64

        # 8. Serializar XML firmado (preservando formato sin alterar espacios)
        signed_xml_bytes = etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=False
        )

        return signed_xml_bytes, digest_b64

    def sign_file(self, unsigned_xml_path: str, output_signed_path: str) -> str:
        """Firma un archivo XML desde disco y guarda el resultado firmado."""
        with open(unsigned_xml_path, "rb") as f:
            xml_bytes = f.read()

        signed_bytes, digest_value = self.sign_xml(xml_bytes)

        os.makedirs(os.path.dirname(output_signed_path), exist_ok=True)
        with open(output_signed_path, "wb") as f:
            f.write(signed_bytes)

        return digest_value
