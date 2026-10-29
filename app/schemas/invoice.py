"""
Modelos Pydantic para la Validación de Solicitudes de Facturación Electrónica UBL 2.1
"""

from datetime import date, time
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class TipoDocumentoEnum(str, Enum):
    FACTURA = "01"
    BOLETA = "03"


class TipoDocIdentidadEnum(str, Enum):
    SIN_DOCUMENTO = "0"
    DNI = "1"
    CARNET_EXTRANJERIA = "4"
    RUC = "6"
    PASAPORTE = "7"


class MonedaEnum(str, Enum):
    PEN = "PEN"
    USD = "USD"


class FormaPagoEnum(str, Enum):
    CONTADO = "Contado"
    CREDITO = "Credito"


class TipoAfectacionIgvEnum(str, Enum):
    # Catálogo 07 SUNAT
    GRAVADO_OPERACION_ONEROSA = "10"
    GRAVADO_RETIRO_PREMIO = "11"
    GRAVADO_RETIRO_DONACION = "12"
    EXONERADO_OPERACION_ONEROSA = "20"
    INAFECTO_OPERACION_ONEROSA = "30"
    EXPORTACION = "40"


class EmisorSchema(BaseModel):
    """Datos de la empresa emisora (opcional si se usan los de .env)"""
    ruc: str = Field(..., min_length=11, max_length=11, description="RUC del emisor (11 dígitos)")
    razon_social: str = Field(..., max_length=100, description="Razón Social del emisor")
    nombre_comercial: Optional[str] = Field(None, max_length=100)
    ubigeo: str = Field("150101", min_length=6, max_length=6, description="Código de Ubigeo")
    direccion: str = Field(..., max_length=100, description="Dirección fiscal")
    codigo_establecimiento: str = Field("0000", description="Código de local anexo asignado por SUNAT (0000 = Principal)")


class ClienteSchema(BaseModel):
    """Datos del cliente / receptor del comprobante"""
    tipo_doc: TipoDocIdentidadEnum = Field(..., description="Tipo de documento (Catálogo 06: 6=RUC, 1=DNI, etc.)")
    num_doc: str = Field(..., min_length=1, max_length=15, description="Número de documento de identidad")
    razon_social: str = Field(..., min_length=2, max_length=100, description="Nombre o Razón Social")
    direccion: Optional[str] = Field(None, max_length=100, description="Dirección del cliente")


class CuotaCreditoSchema(BaseModel):
    """Detalle de cuotas si la forma de pago es Crédito"""
    cuota: str = Field("Cuota001", description="Identificador de la cuota")
    monto: Decimal = Field(..., gt=0, description="Monto de la cuota")
    fecha_vencimiento: date = Field(..., description="Fecha de vencimiento de la cuota")


class ItemSchema(BaseModel):
    """Detalle de cada producto o servicio facturado"""
    codigo: Optional[str] = Field(None, max_length=30, description="Código interno del producto")
    descripcion: str = Field(..., min_length=1, max_length=250, description="Descripción del bien o servicio")
    unidad_medida: str = Field("NIU", min_length=2, max_length=5, description="Unidad de medida (NIU=Unidad, ZZ=Servicio, KGM=Kilo, etc.)")
    cantidad: Decimal = Field(..., gt=0, description="Cantidad")
    valor_unitario: Decimal = Field(..., ge=0, description="Valor unitario SIN IGV")
    precio_unitario: Optional[Decimal] = Field(None, description="Precio unitario CON IGV (se calcula automáticamente si no se envía)")
    tipo_afectacion_igv: TipoAfectacionIgvEnum = Field(
        TipoAfectacionIgvEnum.GRAVADO_OPERACION_ONEROSA,
        description="Código de afectación al IGV (Catálogo 07: 10=Gravado, 20=Exonerado, etc.)"
    )
    porcentaje_igv: Decimal = Field(Decimal("10.50"), description="Tasa de IGV Especial Restaurantes Ley 31556 (10.50%)")

    @model_validator(mode="after")
    def compute_fields(self):
        # Si no se envió precio_unitario, calcularlo: valor_unitario * (1 + porcentaje_igv / 100)
        if self.precio_unitario is None:
            if self.tipo_afectacion_igv == TipoAfectacionIgvEnum.GRAVADO_OPERACION_ONEROSA:
                tasa = Decimal("1") + (self.porcentaje_igv / Decimal("100"))
                self.precio_unitario = (self.valor_unitario * tasa).quantize(Decimal("0.01"))
            else:
                self.precio_unitario = self.valor_unitario
        return self


class InvoiceRequest(BaseModel):
    """Payload principal para emitir Factura (01) o Boleta (03)"""
    tipo_documento: TipoDocumentoEnum = Field(..., description="01 = Factura, 03 = Boleta de Venta")
    serie: str = Field(..., min_length=4, max_length=4, description="Serie de 4 caracteres (Ej: F001, B001)")
    correlativo: int = Field(..., ge=1, le=99999999, description="Número correlativo (Ej: 1, 45, 120)")
    fecha_emision: Optional[date] = Field(None, description="Fecha de emisión (Por defecto: hoy)")
    hora_emision: Optional[time] = Field(None, description="Hora de emisión (Por defecto: hora actual)")
    fecha_vencimiento: Optional[date] = Field(None, description="Fecha de vencimiento")
    moneda: MonedaEnum = Field(MonedaEnum.PEN, description="Moneda: PEN (Soles) o USD (Dólares)")
    forma_pago: FormaPagoEnum = Field(FormaPagoEnum.CONTADO, description="Forma de pago: Contado o Credito")
    cuotas: Optional[List[CuotaCreditoSchema]] = Field(None, description="Cuotas en caso de pago al Crédito")
    
    emisor: Optional[EmisorSchema] = Field(None, description="Emisor (Opcional, toma valores por defecto del sistema si no se envía)")
    cliente: ClienteSchema = Field(..., description="Datos del receptor / cliente")
    items: List[ItemSchema] = Field(..., min_length=1, description="Lista de productos/servicios a facturar")
    observaciones: Optional[str] = Field(None, max_length=500, description="Observaciones adicionales")

    @field_validator("serie")
    @classmethod
    def validate_serie_format(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) != 4:
            raise ValueError("La serie debe tener exactamente 4 caracteres alfanuméricos.")
        return v

    @model_validator(mode="after")
    def validate_rules_sunat(self):
        # 1. Validación de serie según tipo de documento
        if self.tipo_documento == TipoDocumentoEnum.FACTURA:
            if not self.serie.startswith("F"):
                raise ValueError("Para Facturas (01), la serie debe iniciar con la letra 'F' (ej. F001).")
            # Para Factura, el cliente debe ser RUC (Catálogo 06 = '6')
            if self.cliente.tipo_doc != TipoDocIdentidadEnum.RUC:
                raise ValueError("Para emitir una Factura (01), el cliente debe poseer RUC (tipo_doc='6').")
            if len(self.cliente.num_doc) != 11:
                raise ValueError("El RUC del cliente debe tener exactamente 11 dígitos.")
        
        elif self.tipo_documento == TipoDocumentoEnum.BOLETA:
            if not self.serie.startswith("B"):
                raise ValueError("Para Boletas (03), la serie debe iniciar con la letra 'B' (ej. B001).")
        
        # 2. Validación de cuotas si forma_pago es Crédito
        if self.forma_pago == FormaPagoEnum.CREDITO:
            if not self.cuotas or len(self.cuotas) == 0:
                raise ValueError("Si la forma de pago es 'Credito', se debe especificar al menos una cuota en 'cuotas'.")

        return self

    @property
    def correlativo_str(self) -> str:
        """Formatea el correlativo con 8 dígitos como lo exige SUNAT (Ej: 00000001)"""
        return str(self.correlativo).zfill(8)

    @property
    def id_comprobante(self) -> str:
        """Retorna el identificador del comprobante: {SERIE}-{CORRELATIVO}"""
        return f"{self.serie}-{self.correlativo_str}"
