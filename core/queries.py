"""Consultas y agregaciones sobre la base de datos, listas para pandas/Streamlit.

El estado de un pago (Pendiente/Vencido/Pagado) siempre se calcula aquí a
partir de fecha_pago/fecha_vencimiento - nunca se guarda en la BD, para que
nunca quede desincronizado.
"""
from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy import extract, func

from core.database import Categoria, Deuda, Movimiento, Pago, SessionLocal

# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------


def listar_categorias(tipo: Optional[str] = None) -> list:
    with SessionLocal() as session:
        q = session.query(Categoria.nombre)
        if tipo:
            q = q.filter(Categoria.tipo == tipo)
        return [n for (n,) in q.order_by(Categoria.nombre).all()]


# ---------------------------------------------------------------------------
# Movimientos (ingresos/egresos)
# ---------------------------------------------------------------------------


def anios_disponibles() -> list:
    with SessionLocal() as session:
        anios = session.query(extract("year", Movimiento.fecha)).distinct().all()
        return sorted({int(a[0]) for a in anios if a[0] is not None}, reverse=True)


def agregar_movimiento(
    fecha: date, tipo: str, categoria_nombre: str, descripcion: str, monto: float
) -> None:
    with SessionLocal() as session:
        cat = (
            session.query(Categoria)
            .filter_by(nombre=categoria_nombre, tipo=tipo)
            .first()
        )
        session.add(
            Movimiento(
                fecha=fecha,
                tipo=tipo,
                categoria_id=cat.id if cat else None,
                descripcion=descripcion,
                monto=monto,
            )
        )
        session.commit()


def eliminar_movimiento(movimiento_id: int) -> None:
    with SessionLocal() as session:
        mov = session.get(Movimiento, movimiento_id)
        if mov:
            session.delete(mov)
            session.commit()


def listar_movimientos(
    anio: Optional[int] = None,
    mes: Optional[int] = None,
    categoria: Optional[str] = None,
) -> pd.DataFrame:
    with SessionLocal() as session:
        q = session.query(
            Movimiento.id,
            Movimiento.fecha,
            Movimiento.tipo,
            Categoria.nombre.label("categoria"),
            Movimiento.descripcion,
            Movimiento.monto,
        ).outerjoin(Categoria, Movimiento.categoria_id == Categoria.id)

        if anio:
            q = q.filter(extract("year", Movimiento.fecha) == anio)
        if mes:
            q = q.filter(extract("month", Movimiento.fecha) == mes)
        if categoria:
            q = q.filter(Categoria.nombre == categoria)

        rows = q.order_by(Movimiento.fecha.desc()).all()
        df = pd.DataFrame(
            rows, columns=["id", "fecha", "tipo", "categoria", "descripcion", "monto"]
        )
        if not df.empty:
            df["monto"] = df["monto"].astype(float)
        return df


def saldo_actual() -> float:
    with SessionLocal() as session:
        ingresos = (
            session.query(func.coalesce(func.sum(Movimiento.monto), 0))
            .filter(Movimiento.tipo == "ingreso")
            .scalar()
        )
        egresos = (
            session.query(func.coalesce(func.sum(Movimiento.monto), 0))
            .filter(Movimiento.tipo == "egreso")
            .scalar()
        )
        return float(ingresos) - float(egresos)


def movimientos_por_mes(
    anio: Optional[int] = None,
    mes: Optional[int] = None,
    categoria: Optional[str] = None,
) -> pd.DataFrame:
    df = listar_movimientos(anio=anio, mes=mes, categoria=categoria)
    if df.empty:
        return pd.DataFrame(columns=["periodo", "tipo", "monto"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["periodo"] = df["fecha"].dt.strftime("%Y-%m")
    resumen = df.groupby(["periodo", "tipo"], as_index=False)["monto"].sum()
    return resumen.sort_values("periodo")


def distribucion_por_categoria(
    anio: Optional[int] = None, mes: Optional[int] = None, tipo: str = "egreso"
) -> pd.DataFrame:
    # Nota: no filtra por categoría a propósito - un gráfico de distribución
    # filtrado a una sola categoría no tendría sentido.
    df = listar_movimientos(anio=anio, mes=mes)
    if df.empty:
        return pd.DataFrame(columns=["categoria", "monto"])
    df = df[df["tipo"] == tipo].copy()
    if df.empty:
        return pd.DataFrame(columns=["categoria", "monto"])
    df["categoria"] = df["categoria"].fillna("Sin categoría")
    resumen = df.groupby("categoria", as_index=False)["monto"].sum()
    return resumen.sort_values("monto", ascending=False)


# ---------------------------------------------------------------------------
# Deudas y pagos
# ---------------------------------------------------------------------------


def agregar_deuda(nombre: str, monto_total: float, notas: str = "") -> int:
    with SessionLocal() as session:
        deuda = Deuda(
            nombre=nombre, monto_total=monto_total, saldo_pendiente=monto_total, notas=notas
        )
        session.add(deuda)
        session.commit()
        session.refresh(deuda)
        return deuda.id


def agregar_pago(
    deuda_id: int, monto: float, fecha_vencimiento: date, notas: str = ""
) -> None:
    with SessionLocal() as session:
        session.add(
            Pago(
                deuda_id=deuda_id,
                monto=monto,
                fecha_vencimiento=fecha_vencimiento,
                notas=notas,
            )
        )
        session.commit()


def marcar_pagado(pago_id: int, fecha_pago: Optional[date] = None) -> None:
    with SessionLocal() as session:
        pago = session.get(Pago, pago_id)
        if not pago:
            return
        pago.fecha_pago = fecha_pago or date.today()
        deuda = session.get(Deuda, pago.deuda_id)
        if deuda:
            deuda.saldo_pendiente = max(
                float(deuda.saldo_pendiente) - float(pago.monto), 0
            )
        session.commit()


def listar_deudas() -> pd.DataFrame:
    with SessionLocal() as session:
        rows = session.query(Deuda).order_by(Deuda.creado_en.desc()).all()
        return pd.DataFrame(
            [
                {
                    "id": d.id,
                    "nombre": d.nombre,
                    "monto_total": float(d.monto_total),
                    "saldo_pendiente": float(d.saldo_pendiente),
                    "notas": d.notas,
                }
                for d in rows
            ]
        )


def _calcular_estado(fecha_pago, fecha_vencimiento) -> str:
    if fecha_pago is not None:
        return "Pagado"
    if fecha_vencimiento < date.today():
        return "Vencido"
    return "Pendiente"


def listar_pagos(estado: Optional[str] = None) -> pd.DataFrame:
    with SessionLocal() as session:
        rows = (
            session.query(Pago, Deuda.nombre.label("deuda_nombre"))
            .join(Deuda, Pago.deuda_id == Deuda.id)
            .order_by(Pago.fecha_vencimiento)
            .all()
        )
        data = []
        for pago, deuda_nombre in rows:
            data.append(
                {
                    "id": pago.id,
                    "deuda": deuda_nombre,
                    "monto": float(pago.monto),
                    "fecha_vencimiento": pago.fecha_vencimiento,
                    "fecha_pago": pago.fecha_pago,
                    "estado": _calcular_estado(pago.fecha_pago, pago.fecha_vencimiento),
                }
            )
        df = pd.DataFrame(
            data,
            columns=["id", "deuda", "monto", "fecha_vencimiento", "fecha_pago", "estado"],
        )
        if estado and not df.empty:
            df = df[df["estado"] == estado]
        return df


def total_deudas() -> float:
    with SessionLocal() as session:
        total = session.query(func.coalesce(func.sum(Deuda.saldo_pendiente), 0)).scalar()
        return float(total)


def proximo_pago() -> Optional[dict]:
    df = listar_pagos()
    if df.empty:
        return None
    pendientes = df[df["estado"].isin(["Pendiente", "Vencido"])].sort_values(
        "fecha_vencimiento"
    )
    if pendientes.empty:
        return None
    fila = pendientes.iloc[0]
    return {
        "deuda": fila["deuda"],
        "monto": fila["monto"],
        "fecha_vencimiento": fila["fecha_vencimiento"],
        "estado": fila["estado"],
    }
