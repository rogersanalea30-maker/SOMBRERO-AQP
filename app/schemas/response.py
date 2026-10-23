"""
Modelos Pydantic para las Respuestas de la API
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class CdrDetails(BaseModel):
    """Detalles de la Constancia de Recepción (CDR) emitida por SUNAT"""
    response_code: str = Field(..., description="0 = Aceptado, >0 = Rechazado / Error")
    description: str = Field(..., description="Mensaje de respuesta oficial de la SUNAT")
    notes: List[str] = Field(default_factory=list, description="Observaciones o advertencias de SUNAT")
    response_date: Optional[str] = None
    response_time: Optional[str] = None
    accepted: bool = Field(..., description="True si response_code == '0'")


class FileReferences(BaseModel):
    """Rutas relativas de los archivos generados en storage"""
    xml: Optional[str] = None
    signed_xml: Optional[str] = None
    zip: Optional[str] = None
    cdr_zip: Optional[str] = None
    cdr_xml: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Respuesta completa del proceso de emisión y envío a SUNAT"""
    success: bool
    message: str
    document_id: str = Field(..., description="Identificador: Serie-Correlativo (ej. F001-00000001)")
    tipo_documento: str = Field(..., description="01 = Factura, 03 = Boleta")
    hash_cpe: str = Field(..., description="Código Hash (DigestValue) para el PDF / QR")
    cdr: Optional[CdrDetails] = None
    files: FileReferences
    errors: Optional[List[str]] = None


class PreviewXmlResponse(BaseModel):
    """Respuesta para generación y firmado de XML sin envío a SUNAT"""
    success: bool
    document_id: str
    tipo_documento: str
    hash_cpe: str
    xml_content: str
    signed_xml_path: str
