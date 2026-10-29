"""
Modelos ORM de Base de Datos para el Sistema de Facturación Electrónica
"""

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, Date, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from app.db.database import Base


class ClientModel(Base):
    """Catálogo de Clientes"""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    tipo_doc = Column(String(2), nullable=False)  # 6=RUC, 1=DNI, etc.
    num_doc = Column(String(15), unique=True, index=True, nullable=False)
    razon_social = Column(String(150), nullable=False)
    direccion = Column(String(200), nullable=True)
    email = Column(String(100), nullable=True)
    telefono = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductModel(Base):
    """Catálogo de Productos y Servicios"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, index=True, nullable=False)
    descripcion = Column(String(250), nullable=False)
    unidad_medida = Column(String(5), default="NIU")  # NIU = Unidad, ZZ = Servicio
    valor_unitario = Column(Numeric(12, 4), nullable=False)  # Sin IGV
    precio_unitario = Column(Numeric(12, 2), nullable=False)  # Con IGV
    tipo_afectacion = Column(String(2), default="10")  # 10=Gravado, 20=Exonerado, 30=Inafecto
    porcentaje_igv = Column(Numeric(5, 2), default=Decimal("10.50"))
    categoria = Column(String(50), default="Platos de Fondo", nullable=True)
    imagen_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class InvoiceSeriesModel(Base):
    """Control de Series y Correlativos Automáticos"""
    __tablename__ = "invoice_series"

    id = Column(Integer, primary_key=True, index=True)
    tipo_documento = Column(String(2), nullable=False)  # 01=Factura, 03=Boleta, 07=NC, 08=ND
    serie = Column(String(4), unique=True, index=True, nullable=False)  # F001, B001, FC01, BC01
    ultimo_correlativo = Column(Integer, default=0)


class InvoiceModel(Base):
    """Registro Maestro de Comprobantes Emitidos"""
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    tipo_documento = Column(String(2), nullable=False, index=True)  # 01, 03, 07, 08
    serie = Column(String(4), nullable=False)
    correlativo = Column(Integer, nullable=False)
    document_id = Column(String(20), unique=True, index=True, nullable=False)  # F001-00000001
    fecha_emision = Column(Date, default=date.today)
    moneda = Column(String(3), default="PEN")
    forma_pago = Column(String(20), default="Contado")

    # Totales monetarios
    total_gravado = Column(Numeric(12, 2), default=Decimal("0.00"))
    total_exonerado = Column(Numeric(12, 2), default=Decimal("0.00"))
    total_inafecto = Column(Numeric(12, 2), default=Decimal("0.00"))
    total_igv = Column(Numeric(12, 2), default=Decimal("0.00"))
    total_pagar = Column(Numeric(12, 2), default=Decimal("0.00"))

    # Datos criptográficos y fiscales de SUNAT
    hash_cpe = Column(String(60), nullable=True)
    sunat_status = Column(String(20), default="PENDIENTE")  # ACEPTADO, RECHAZADO, ERROR, PENDIENTE
    sunat_code = Column(String(10), nullable=True)  # 0 = Aceptado
    sunat_description = Column(Text, nullable=True)

    # Datos del cliente en el momento de la venta
    cliente_tipo_doc = Column(String(2), nullable=False)
    cliente_num_doc = Column(String(15), nullable=False)
    cliente_razon_social = Column(String(150), nullable=False)
    cliente_direccion = Column(String(200), nullable=True)

    # Documento de referencia si es Nota de Crédito / Débito
    doc_afectado_id = Column(String(20), nullable=True)
    motivo_nota = Column(String(100), nullable=True)

    # Rutas de almacenamiento
    xml_path = Column(String(255), nullable=True)
    zip_path = Column(String(255), nullable=True)
    cdr_path = Column(String(255), nullable=True)
    pdf_a4_path = Column(String(255), nullable=True)
    pdf_ticket_path = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("InvoiceItemModel", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItemModel(Base):
    """Detalle de Ítems por Comprobante"""
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    codigo = Column(String(50), nullable=True)
    descripcion = Column(String(250), nullable=False)
    unidad_medida = Column(String(5), default="NIU")
    cantidad = Column(Numeric(12, 2), nullable=False)
    valor_unitario = Column(Numeric(12, 4), nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    igv_linea = Column(Numeric(12, 2), nullable=False)
    valor_venta = Column(Numeric(12, 2), nullable=False)

    invoice = relationship("InvoiceModel", back_populates="items")


class UserModel(Base):
    """Catálogo de Usuarios y Perfiles de Acceso (Admin, Cajero, Mozo, Cocina)"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    nombre_completo = Column(String(100), nullable=False)
    rol = Column(String(20), nullable=False, default="MOZO")  # ADMIN, CAJERO, MOZO, COCINA
    pin = Column(String(10), nullable=False, default="1234")
    password = Column(String(100), nullable=False, default="123456")
    email = Column(String(100), nullable=True)
    telefono = Column(String(30), nullable=True)
    zona_asignada = Column(String(50), default="Todas", nullable=True)
    permisos_json = Column(Text, default="", nullable=True)
    activo = Column(Boolean, default=True)
    avatar_color = Column(String(30), default="amber")
    created_at = Column(DateTime, default=datetime.utcnow)

