# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath('.'))
from app.db import engine, get_db
from app.db.models import UserModel
from sqlalchemy import text

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS zona_asignada VARCHAR(50) DEFAULT 'Todas';"))
        conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS permisos_json TEXT DEFAULT '';"))
        conn.commit()
        print("✓ Columns zona_asignada and permisos_json ready in Supabase PostgreSQL!")

    # Seed or update default users: ensure we have BAR / BEBIDAS user
    db = next(get_db())
    try:
        # Check if Bar user exists
        bar_user = db.query(UserModel).filter(UserModel.username == 'bar').first()
        if not bar_user:
            bar_user = UserModel(
                username="bar",
                nombre_completo="Estación Bar & Bebidas",
                rol="BAR",
                pin="4444",
                password="bar",
                email="bar@elsombrero.pe",
                telefono="959666111",
                avatar_color="blue",
                activo=True
            )
            db.add(bar_user)
            db.commit()
            print("✓ Created default user: bar (PIN: 4444, Rol: BAR)")

        # Update default permissions & zones
        users = db.query(UserModel).all()
        for u in users:
            if u.rol == 'MOZO':
                u.zona_asignada = u.zona_asignada or "Salón Principal"
            elif u.rol == 'BAR':
                u.zona_asignada = "Bar & Bebidas"
            elif u.rol == 'COCINA':
                u.zona_asignada = "Cocina Caliente & Fría"
            elif u.rol == 'CAJERO':
                u.zona_asignada = "Caja Principal"
            elif u.rol == 'ADMIN':
                u.zona_asignada = "Todas las Áreas"
        db.commit()
        print(f"✓ Updated zones for all {len(users)} users")

    finally:
        db.close()

if __name__ == '__main__':
    main()
