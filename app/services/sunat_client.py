"""
Cliente SOAP para el Web Service BillService de la SUNAT utilizando la librería Zeep.
Empaqueta el XML firmado en ZIP, gestiona la autenticación WS-Security,
ejecuta la llamada sendBill y procesa la Constancia de Recepción (CDR).
"""

import io
import os
import zipfile
import base64
from typing import Dict, Any, List, Optional
from lxml import etree
import requests
import zeep
from zeep.wsse.username import UsernameToken
from zeep.transports import Transport
from zeep.exceptions import Fault

from app.config import settings
from app.schemas.response import CdrDetails


class SunatSoapClient:
    """Cliente SOAP para comunicación con los Web Services de Facturación de SUNAT."""

    def __init__(
        self,
        wsdl_path: Optional[str] = None,
        service_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 60
    ):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.wsdl_path = wsdl_path or os.path.join(base_dir, "wsdl", "billService.wsdl")
        self.service_url = service_url or settings.sunat_service_url
        self.username = username or settings.sunat_auth_username
        self.password = password or settings.SUNAT_PASSWORD
        self.timeout = timeout
        self._init_zeep_client()

    def _init_zeep_client(self):
        """Inicializa el cliente Zeep cargando el WSDL local y configurando el endpoint."""
        session = requests.Session()
        session.verify = False  # En entornos SUNAT Beta y algunos proxies locales
        transport = Transport(session=session, timeout=self.timeout)

        # Autenticación WS-Security con UsernameToken
        wsse = UsernameToken(self.username, self.password)

        self.client = zeep.Client(
            wsdl=self.wsdl_path,
            wsse=wsse,
            transport=transport
        )

        # Reemplazar la URL del endpoint según la configuración activa (Beta o Producción)
        self.service = self.client.create_service(
            "{http://service.gem.factura.comppago.registro.servicio.sunat.gob.pe/}BillServicePortBinding",
            self.service_url
        )

    @staticmethod
    def create_zip(filename_xml: str, xml_bytes: bytes) -> bytes:
        """Comprime el archivo XML firmado dentro de un ZIP en memoria."""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(filename_xml, xml_bytes)
        return zip_buffer.getvalue()

    def send_bill(
        self,
        ruc_emisor: str,
        tipo_documento: str,
        serie: str,
        correlativo_str: str,
        signed_xml_bytes: bytes
    ) -> Dict[str, Any]:
        """
        Envía un comprobante electrónico (Factura 01 o Boleta 03) a la SUNAT.

        Argumentos:
            ruc_emisor: RUC del emisor (11 dígitos)
            tipo_documento: "01" (Factura) o "03" (Boleta)
            serie: Serie del documento (ej. "F001")
            correlativo_str: Correlativo formateado a 8 dígitos (ej. "00000001")
            signed_xml_bytes: Contenido del XML firmado digitalmente

        Retorna:
            Diccionario con el resultado del envío, estado de aceptación y detalles del CDR.
        """
        base_name = f"{ruc_emisor}-{tipo_documento}-{serie}-{correlativo_str}"
        xml_filename = f"{base_name}.xml"
        zip_filename = f"{base_name}.zip"

        # 1. Empaquetar XML firmado en archivo ZIP
        zip_bytes = self.create_zip(xml_filename, signed_xml_bytes)

        # Guardar copia local del ZIP enviado
        local_zip_path = os.path.join(settings.dir_zip, zip_filename)
        with open(local_zip_path, "wb") as f:
            f.write(zip_bytes)

        # 2. Invocación SOAP a la operación sendBill
        try:
            # sendBill(fileName, contentFile)
            response_cdr_bytes = self.service.sendBill(
                fileName=zip_filename,
                contentFile=zip_bytes
            )
        except Fault as soap_fault:
            # Capturar errores SOAP de SUNAT (ej. código 1033, 2000, 3000, etc.)
            error_code = str(soap_fault.code) if soap_fault.code else "SOAP_FAULT"
            error_msg = str(soap_fault.message) if soap_fault.message else "Error en el servidor de SUNAT"
            raise RuntimeError(f"Rechazo SOAP SUNAT [{error_code}]: {error_msg}") from soap_fault
        except requests.exceptions.RequestException as req_err:
            raise ConnectionError(f"Error de red o conexión al conectar con SUNAT: {req_err}") from req_err
        except Exception as ex:
            raise RuntimeError(f"Error inesperado al enviar comprobante a SUNAT: {ex}") from ex

        if not response_cdr_bytes:
            raise RuntimeError("SUNAT respondió sin contenido de CDR (applicationResponse vacío).")

        # 3. Procesar archivo CDR (Constancia de Recepción)
        cdr_info = self._process_cdr(base_name, response_cdr_bytes)

        return {
            "success": cdr_info.accepted,
            "cdr": cdr_info,
            "zip_path": local_zip_path,
            "cdr_zip_path": os.path.join(settings.dir_cdr, f"R-{base_name}.zip"),
            "cdr_xml_path": os.path.join(settings.dir_cdr, f"R-{base_name}.xml")
        }

    def _process_cdr(self, base_name: str, cdr_bytes: bytes) -> CdrDetails:
        """Descomprime y analiza el XML de la Constancia de Recepción (CDR)."""
        # Guardar el ZIP del CDR recibido
        cdr_zip_filename = f"R-{base_name}.zip"
        cdr_zip_path = os.path.join(settings.dir_cdr, cdr_zip_filename)
        with open(cdr_zip_path, "wb") as f:
            f.write(cdr_bytes)

        # Extraer el XML del CDR desde el archivo ZIP
        cdr_xml_filename = f"R-{base_name}.xml"
        cdr_xml_bytes = None

        with zipfile.ZipFile(io.BytesIO(cdr_bytes), mode="r") as zf:
            # En ocasiones el nombre en el zip puede variar ligeramente en mayúsculas/minúsculas
            for name in zf.namelist():
                if name.lower().endswith(".xml"):
                    cdr_xml_bytes = zf.read(name)
                    break

        if not cdr_xml_bytes:
            raise RuntimeError("El archivo ZIP de CDR no contiene ningún archivo XML de respuesta.")

        # Guardar XML del CDR en disco
        cdr_xml_path = os.path.join(settings.dir_cdr, cdr_xml_filename)
        with open(cdr_xml_path, "wb") as f:
            f.write(cdr_xml_bytes)

        # 4. Parsear contenido del XML de CDR
        return self._parse_cdr_xml(cdr_xml_bytes)

    @staticmethod
    def _parse_cdr_xml(cdr_xml_bytes: bytes) -> CdrDetails:
        """Extrae el código de respuesta, descripción y observaciones del CDR de SUNAT."""
        root = etree.fromstring(cdr_xml_bytes)

        # Namespaces comunes en el CDR de SUNAT
        namespaces = {
            "ar": "urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2",
            "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
            "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        }

        # Extraer ResponseDate y ResponseTime
        date_elem = root.find(".//cbc:ResponseDate", namespaces)
        time_elem = root.find(".//cbc:ResponseTime", namespaces)
        response_date = date_elem.text if date_elem is not None else None
        response_time = time_elem.text if time_elem is not None else None

        # Extraer ResponseCode y Description
        code_elem = root.find(".//cac:DocumentResponse/cac:Response/cbc:ResponseCode", namespaces)
        if code_elem is None:
            # Búsqueda alternativa sin namespace estricto
            code_elem = root.find(".//{*}ResponseCode")

        desc_elem = root.find(".//cac:DocumentResponse/cac:Response/cbc:Description", namespaces)
        if desc_elem is None:
            desc_elem = root.find(".//{*}Description")

        response_code = code_elem.text.strip() if code_elem is not None and code_elem.text else "-1"
        description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else "Sin descripción"

        # Extraer Observaciones / Notas si existen
        notes = []
        for note_elem in root.findall(".//cac:DocumentResponse/cac:Response/cbc:Note", namespaces):
            if note_elem is not None and note_elem.text:
                notes.append(note_elem.text.strip())

        accepted = (response_code == "0")

        return CdrDetails(
            response_code=response_code,
            description=description,
            notes=notes,
            response_date=response_date,
            response_time=response_time,
            accepted=accepted
        )
