"""Capa de acceso a datos: motor de conexión y modelos ORM.

La URL de conexión se resuelve en este orden:
1. st.secrets["DATABASE_URL"]        (recomendado para despliegue en la nube)
2. variable de entorno DATABASE_URL  (recomendado para Docker/local)
3. sqlite local en ./data/finanzas.db (por defecto, solo para desarrollo)

SQLite local NO sirve para Streamlit Community Cloud (su almacenamiento es
efímero y se borra en cada redeploy) - para producción usa el DATABASE_URL
de un proyecto de Supabase (ver .streamlit/secrets.toml.example).
"""
import os
from datetime import datetime

import streamlit as st
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    username = Column(String(60), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(120), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)


class Categoria(Base):
    __tablename__ = "categorias"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False)
    tipo = Column(String(10), nullable=False)  # 'ingreso' | 'egreso'
    color = Column(String(7), default="#6366f1")

    __table_args__ = (
        UniqueConstraint("nombre", "tipo", name="uq_categoria_nombre_tipo"),
        CheckConstraint("tipo IN ('ingreso', 'egreso')", name="ck_categoria_tipo"),
    )


class Movimiento(Base):
    __tablename__ = "movimientos"
    id = Column(Integer, primary_key=True)
    fecha = Column(Date, nullable=False)
    tipo = Column(String(10), nullable=False)  # 'ingreso' | 'egreso'
    categoria_id = Column(Integer, ForeignKey("categorias.id"))
    descripcion = Column(String(255), default="")
    monto = Column(Numeric(14, 2), nullable=False)
    creado_en = Column(DateTime, default=datetime.utcnow)

    categoria = relationship("Categoria")

    __table_args__ = (
        CheckConstraint("tipo IN ('ingreso', 'egreso')", name="ck_movimiento_tipo"),
    )


class Deuda(Base):
    __tablename__ = "deudas"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(120), nullable=False)
    monto_total = Column(Numeric(14, 2), nullable=False)
    saldo_pendiente = Column(Numeric(14, 2), nullable=False)
    notas = Column(String(255), default="")
    creado_en = Column(DateTime, default=datetime.utcnow)


class Pago(Base):
    __tablename__ = "pagos"
    id = Column(Integer, primary_key=True)
    deuda_id = Column(Integer, ForeignKey("deudas.id", ondelete="CASCADE"), nullable=False)
    monto = Column(Numeric(14, 2), nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)
    fecha_pago = Column(Date, nullable=True)  # NULL = aun no pagado
    notas = Column(String(255), default="")

    deuda = relationship("Deuda")


DEFAULT_CATEGORIAS = [
    ("Salario", "ingreso"),
    ("Otros ingresos", "ingreso"),
    ("Comida", "egreso"),
    ("Transporte", "egreso"),
    ("Servicios", "egreso"),
    ("Entretenimiento", "egreso"),
    ("Salud", "egreso"),
    ("Otros gastos", "egreso"),
]


def _get_database_url() -> str:
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    return os.environ.get("DATABASE_URL", "sqlite:///data/finanzas.db")


def _build_engine():
    url = _get_database_url()
    if url.startswith("sqlite"):
        os.makedirs("data", exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


engine = _build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def init_db() -> None:
    """Crea las tablas si no existen y siembra categorías por defecto.

    Idempotente: Streamlit puede correr varias sesiones en paralelo sobre el
    mismo proceso, así que se ignora el caso puntual de "already exists" en
    vez de tumbar la app.
    """
    try:
        Base.metadata.create_all(engine)
    except OperationalError as exc:
        if "already exists" not in str(exc):
            raise
    with SessionLocal() as session:
        if session.query(Categoria).count() == 0:
            session.add_all(
                [Categoria(nombre=n, tipo=t) for n, t in DEFAULT_CATEGORIAS]
            )
        session.commit()
