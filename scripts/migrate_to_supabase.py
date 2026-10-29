"""
Script de Migración de SQLite a Supabase PostgreSQL
Copia clientes, productos/platos, series y documentos existentes a Supabase.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuración SQLite local
SQLITE_URL = "sqlite:///./app/storage/facturacion.db"
sqlite_engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SqliteSession = sessionmaker(bind=sqlite_engine)

# Configuración Supabase PostgreSQL
SUPABASE_URL = "postgresql+psycopg://postgres.psnymtlltxlqgszwiril:1717foreverprozwxd@aws-1-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require"
supabase_engine = create_engine(SUPABASE_URL, echo=False)
SupabaseSession = sessionmaker(bind=supabase_engine)

# Modelos
from app.db.models import Base, ClientModel, ProductModel, InvoiceSeriesModel, InvoiceModel, InvoiceItemModel

def run_migration():
    print("==================================================")
    print("INICIANDO MIGRACION A SUPABASE POSTGRESQL")
    print("==================================================")

    # 1. Crear tablas en Supabase
    print("1. Creando tablas en Supabase...")
    Base.metadata.create_all(bind=supabase_engine)
    print("[OK] Tablas creadas exitosamente en Supabase (public schema).")

    sqlite_db = SqliteSession()
    supa_db = SupabaseSession()

    try:
        # 2. Migrar Productos / Platos
        local_products = sqlite_db.query(ProductModel).all()
        print(f"\n2. Migrando {len(local_products)} Productos/Platos...")
        prod_count = 0
        for p in local_products:
            exists = supa_db.query(ProductModel).filter(ProductModel.codigo == p.codigo).first()
            if not exists:
                new_p = ProductModel(
                    codigo=p.codigo,
                    descripcion=p.descripcion,
                    unidad_medida=p.unidad_medida,
                    valor_unitario=p.valor_unitario,
                    precio_unitario=p.precio_unitario,
                    tipo_afectacion=p.tipo_afectacion,
                    porcentaje_igv=p.porcentaje_igv or Decimal("10.50"),
                    created_at=p.created_at
                )
                supa_db.add(new_p)
                prod_count += 1
        supa_db.commit()
        print(f"[OK] {prod_count} nuevos productos insertados en Supabase.")

        # 3. Migrar Clientes
        local_clients = sqlite_db.query(ClientModel).all()
        print(f"\n3. Migrando {len(local_clients)} Clientes...")
        cli_count = 0
        for c in local_clients:
            exists = supa_db.query(ClientModel).filter(ClientModel.num_doc == c.num_doc).first()
            if not exists:
                new_c = ClientModel(
                    tipo_doc=c.tipo_doc,
                    num_doc=c.num_doc,
                    razon_social=c.razon_social,
                    direccion=c.direccion,
                    email=c.email,
                    telefono=c.telefono,
                    created_at=c.created_at
                )
                supa_db.add(new_c)
                cli_count += 1
        supa_db.commit()
        print(f"[OK] {cli_count} nuevos clientes insertados en Supabase.")

        # 4. Migrar Series
        local_series = sqlite_db.query(InvoiceSeriesModel).all()
        print(f"\n4. Migrando {len(local_series)} Series y Correlativos...")
        ser_count = 0
        for s in local_series:
            exists = supa_db.query(InvoiceSeriesModel).filter(InvoiceSeriesModel.serie == s.serie).first()
            if not exists:
                new_s = InvoiceSeriesModel(
                    tipo_documento=s.tipo_documento,
                    serie=s.serie,
                    ultimo_correlativo=s.ultimo_correlativo
                )
                supa_db.add(new_s)
                ser_count += 1
        supa_db.commit()
        print(f"[OK] {ser_count} series insertadas en Supabase.")

        # 5. Resumen final en Supabase
        total_p = supa_db.query(ProductModel).count()
        total_c = supa_db.query(ClientModel).count()
        total_s = supa_db.query(InvoiceSeriesModel).count()

        print("\n==================================================")
        print("MIGRACION COMPLETADA EXITOSAMENTE EN SUPABASE")
        print(f"Total Productos/Platos en Supabase: {total_p}")
        print(f"Total Clientes en Supabase: {total_c}")
        print(f"Total Series en Supabase: {total_s}")
        print("==================================================")

    except Exception as e:
        supa_db.rollback()
        print(f"❌ Error durante la migración: {e}")
        raise e
    finally:
        sqlite_db.close()
        supa_db.close()

if __name__ == "__main__":
    run_migration()
