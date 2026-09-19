"""Consultas y agregaciones sobre la base de datos, listas para pandas/Streamlit.

El estado de un pago (Pendiente/Vencido/Pagado) siempre se calcula aquí a
partir de fecha_pago/fecha_vencimiento - nunca se guarda en la BD, para que
nunca quede desincronizado.

Toda tabla de datos financieros (movimientos, deudas, compras programadas)
tiene un `usuario_id` y cada función que lee o escribe esos datos lo recibe
como primer parámetro - cada usuario ve y modifica solo lo suyo. Las
categorías son la única tabla compartida entre todos los usuarios (son solo
una lista de etiquetas, no datos financieros privados).
"""
from datetime import date
from typing import Optional

import pandas as pd
from sqlalchemy import extract, func

from core.database import (
    Categoria,
    CompraProgramada,
    CuotaProgramada,
    Deuda,
    Movimiento,
    Pago,
    SessionLocal,
)

# ---------------------------------------------------------------------------
# Categorías (compartidas entre todos los usuarios)
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


def anios_disponibles(usuario_id: int) -> list:
    with SessionLocal() as session:
        anios = (
            session.query(extract("year", Movimiento.fecha))
            .filter(Movimiento.usuario_id == usuario_id)
            .distinct()
            .all()
        )
        return sorted({int(a[0]) for a in anios if a[0] is not None}, reverse=True)


def agregar_movimiento(
    usuario_id: int,
    fecha: date,
    tipo: str,
    categoria_nombre: str,
    descripcion: str,
    monto: float,
) -> None:
    with SessionLocal() as session:
        cat = (
            session.query(Categoria)
            .filter_by(nombre=categoria_nombre, tipo=tipo)
            .first()
        )
        session.add(
            Movimiento(
                usuario_id=usuario_id,
                fecha=fecha,
                tipo=tipo,
                categoria_id=cat.id if cat else None,
                descripcion=descripcion,
                monto=monto,
            )
        )
        session.commit()


def eliminar_movimiento(usuario_id: int, movimiento_id: int) -> None:
    with SessionLocal() as session:
        mov = session.get(Movimiento, movimiento_id)
        if mov and mov.usuario_id == usuario_id:
            session.delete(mov)
            session.commit()


def listar_movimientos(
    usuario_id: int,
    anio: Optional[int] = None,
    mes: Optional[int] = None,
    categoria: Optional[str] = None,
) -> pd.DataFrame:
    with SessionLocal() as session:
        q = (
            session.query(
                Movimiento.id,
                Movimiento.fecha,
                Movimiento.tipo,
                Categoria.nombre.label("categoria"),
                Movimiento.descripcion,
                Movimiento.monto,
            )
            .outerjoin(Categoria, Movimiento.categoria_id == Categoria.id)
            .filter(Movimiento.usuario_id == usuario_id)
        )

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


def saldo_actual(usuario_id: int) -> float:
    with SessionLocal() as session:
        base = session.query(func.coalesce(func.sum(Movimiento.monto), 0)).filter(
            Movimiento.usuario_id == usuario_id
        )
        ingresos = base.filter(Movimiento.tipo == "ingreso").scalar()
        egresos = base.filter(Movimiento.tipo == "egreso").scalar()
        return float(ingresos) - float(egresos)


def movimientos_por_mes(
    usuario_id: int,
    anio: Optional[int] = None,
    mes: Optional[int] = None,
    categoria: Optional[str] = None,
) -> pd.DataFrame:
    df = listar_movimientos(usuario_id, anio=anio, mes=mes, categoria=categoria)
    if df.empty:
        return pd.DataFrame(columns=["periodo", "tipo", "monto"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["periodo"] = df["fecha"].dt.strftime("%Y-%m")
    resumen = df.groupby(["periodo", "tipo"], as_index=False)["monto"].sum()
    return resumen.sort_values("periodo")


def distribucion_por_categoria(
    usuario_id: int,
    anio: Optional[int] = None,
    mes: Optional[int] = None,
    tipo: str = "egreso",
) -> pd.DataFrame:
    # Nota: no filtra por categoría a propósito - un gráfico de distribución
    # filtrado a una sola categoría no tendría sentido.
    df = listar_movimientos(usuario_id, anio=anio, mes=mes)
    if df.empty:
        return pd.DataFrame(columns=["categoria", "monto"])
    df = df[df["tipo"] == tipo].copy()
    if df.empty:
        return pd.DataFrame(columns=["categoria", "monto"])
    df["categoria"] = df["categoria"].fillna("Sin categoría")
    resumen = df.groupby("categoria", as_index=False)["monto"].sum()
    return resumen.sort_values("monto", ascending=False)


def saldo_historico_mensual(usuario_id: int) -> list:
    """Serie de saldo acumulado mes a mes, para el sparkline del KPI."""
    df = listar_movimientos(usuario_id)
    if df.empty:
        return []
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["signo"] = df["monto"].where(df["tipo"] == "ingreso", -df["monto"])
    df["periodo"] = df["fecha"].dt.strftime("%Y-%m")
    mensual = df.sort_values("fecha").groupby("periodo", as_index=False)["signo"].sum()
    mensual["acumulado"] = mensual["signo"].cumsum()
    return mensual["acumulado"].tolist()


# ---------------------------------------------------------------------------
# Deudas y pagos
# ---------------------------------------------------------------------------


def agregar_deuda(usuario_id: int, nombre: str, monto_total: float, notas: str = "") -> int:
    with SessionLocal() as session:
        deuda = Deuda(
            usuario_id=usuario_id,
            nombre=nombre,
            monto_total=monto_total,
            saldo_pendiente=monto_total,
            notas=notas,
        )
        session.add(deuda)
        session.commit()
        session.refresh(deuda)
        return deuda.id


def agregar_pago(
    usuario_id: int, deuda_id: int, monto: float, fecha_vencimiento: date, notas: str = ""
) -> None:
    with SessionLocal() as session:
        deuda = session.get(Deuda, deuda_id)
        if not deuda or deuda.usuario_id != usuario_id:
            return
        session.add(
            Pago(
                deuda_id=deuda_id,
                monto=monto,
                fecha_vencimiento=fecha_vencimiento,
                notas=notas,
            )
        )
        session.commit()


def marcar_pagado(usuario_id: int, pago_id: int, fecha_pago: Optional[date] = None) -> None:
    with SessionLocal() as session:
        pago = session.get(Pago, pago_id)
        if not pago:
            return
        deuda = session.get(Deuda, pago.deuda_id)
        if not deuda or deuda.usuario_id != usuario_id:
            return
        pago.fecha_pago = fecha_pago or date.today()
        deuda.saldo_pendiente = max(float(deuda.saldo_pendiente) - float(pago.monto), 0)
        session.commit()


def listar_deudas(usuario_id: int) -> pd.DataFrame:
    with SessionLocal() as session:
        rows = (
            session.query(Deuda)
            .filter(Deuda.usuario_id == usuario_id)
            .order_by(Deuda.creado_en.desc())
            .all()
        )
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


def listar_pagos(usuario_id: int, estado: Optional[str] = None) -> pd.DataFrame:
    with SessionLocal() as session:
        rows = (
            session.query(Pago, Deuda.nombre.label("deuda_nombre"))
            .join(Deuda, Pago.deuda_id == Deuda.id)
            .filter(Deuda.usuario_id == usuario_id)
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


def total_deudas(usuario_id: int) -> float:
    with SessionLocal() as session:
        total = (
            session.query(func.coalesce(func.sum(Deuda.saldo_pendiente), 0))
            .filter(Deuda.usuario_id == usuario_id)
            .scalar()
        )
        return float(total)


def proximo_pago(usuario_id: int) -> Optional[dict]:
    df = listar_pagos(usuario_id)
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


# ---------------------------------------------------------------------------
# Compras programadas (planificación de compras futuras, VES o USD)
# ---------------------------------------------------------------------------


def agregar_compra_programada(
    usuario_id: int, nombre: str, moneda: str, monto_total: float, notas: str = ""
) -> int:
    with SessionLocal() as session:
        compra = CompraProgramada(
            usuario_id=usuario_id,
            nombre=nombre,
            moneda=moneda,
            monto_total=monto_total,
            saldo_pendiente=monto_total,
            notas=notas,
        )
        session.add(compra)
        session.commit()
        session.refresh(compra)
        return compra.id


def listar_compras_programadas(usuario_id: int, moneda: Optional[str] = None) -> pd.DataFrame:
    with SessionLocal() as session:
        q = (
            session.query(CompraProgramada)
            .filter(CompraProgramada.usuario_id == usuario_id)
            .order_by(CompraProgramada.creado_en.desc())
        )
        if moneda:
            q = q.filter(CompraProgramada.moneda == moneda)
        rows = q.all()
        return pd.DataFrame(
            [
                {
                    "id": c.id,
                    "nombre": c.nombre,
                    "moneda": c.moneda,
                    "monto_total": float(c.monto_total),
                    "saldo_pendiente": float(c.saldo_pendiente),
                    "notas": c.notas,
                }
                for c in rows
            ]
        )


def agregar_cuota_programada(
    usuario_id: int, compra_id: int, monto: float, fecha_pago: date, notas: str = ""
) -> None:
    with SessionLocal() as session:
        compra = session.get(CompraProgramada, compra_id)
        if not compra or compra.usuario_id != usuario_id:
            return
        session.add(
            CuotaProgramada(
                compra_id=compra_id, monto=monto, fecha_pago=fecha_pago, notas=notas
            )
        )
        session.commit()


def marcar_cuota_pagada(
    usuario_id: int, cuota_id: int, fecha_pago_real: Optional[date] = None
) -> None:
    with SessionLocal() as session:
        cuota = session.get(CuotaProgramada, cuota_id)
        if not cuota:
            return
        compra = session.get(CompraProgramada, cuota.compra_id)
        if not compra or compra.usuario_id != usuario_id:
            return
        cuota.fecha_pago_real = fecha_pago_real or date.today()
        compra.saldo_pendiente = max(
            float(compra.saldo_pendiente) - float(cuota.monto), 0
        )
        session.commit()


def listar_cuotas_programadas(usuario_id: int, estado: Optional[str] = None) -> pd.DataFrame:
    with SessionLocal() as session:
        rows = (
            session.query(CuotaProgramada, CompraProgramada.nombre, CompraProgramada.moneda)
            .join(CompraProgramada, CuotaProgramada.compra_id == CompraProgramada.id)
            .filter(CompraProgramada.usuario_id == usuario_id)
            .order_by(CuotaProgramada.fecha_pago)
            .all()
        )
        data = []
        for cuota, nombre, moneda in rows:
            data.append(
                {
                    "id": cuota.id,
                    "compra": nombre,
                    "moneda": moneda,
                    "monto": float(cuota.monto),
                    "fecha_pago": cuota.fecha_pago,
                    "fecha_pago_real": cuota.fecha_pago_real,
                    "estado": _calcular_estado(cuota.fecha_pago_real, cuota.fecha_pago),
                }
            )
        df = pd.DataFrame(
            data,
            columns=["id", "compra", "moneda", "monto", "fecha_pago", "fecha_pago_real", "estado"],
        )
        if estado and not df.empty:
            df = df[df["estado"] == estado]
        return df


def eliminar_compra_programada(usuario_id: int, compra_id: int) -> None:
    """Elimina una compra programada y, en cascada (ON DELETE CASCADE en la
    BD), todas sus cuotas - para corregir una compra agregada por error."""
    with SessionLocal() as session:
        compra = session.get(CompraProgramada, compra_id)
        if compra and compra.usuario_id == usuario_id:
            session.delete(compra)
            session.commit()


def eliminar_cuota_programada(usuario_id: int, cuota_id: int) -> None:
    """Elimina una cuota puntual (por error al agregarla). Si la cuota ya
    estaba marcada como pagada, su monto se le devuelve al saldo_pendiente
    de la compra para no dejarlo desincronizado."""
    with SessionLocal() as session:
        cuota = session.get(CuotaProgramada, cuota_id)
        if not cuota:
            return
        compra = session.get(CompraProgramada, cuota.compra_id)
        if not compra or compra.usuario_id != usuario_id:
            return
        if cuota.fecha_pago_real is not None:
            compra.saldo_pendiente = float(compra.saldo_pendiente) + float(cuota.monto)
        session.delete(cuota)
        session.commit()


def marcar_compra_comprada(usuario_id: int, compra_id: int) -> Optional[dict]:
    """Cierra una compra programada de una vez: pone su saldo_pendiente en 0
    y marca todas sus cuotas pendientes como pagadas hoy (para que no sigan
    apareciendo en alertas). Si es en USD, además registra automáticamente
    un egreso en Movimientos por el saldo restante, para que el Saldo
    actual del Dashboard lo refleje - las compras en VES no generan ese
    movimiento porque el Dashboard maneja el saldo en USD (moneda distinta,
    esta app no hace conversión de tasas).

    Devuelve {"monto": float, "moneda": str, "genero_movimiento": bool} o
    None si la compra no existe / no es del usuario.
    """
    with SessionLocal() as session:
        compra = session.get(CompraProgramada, compra_id)
        if not compra or compra.usuario_id != usuario_id:
            return None
        monto_restante = float(compra.saldo_pendiente)
        moneda = compra.moneda
        nombre = compra.nombre
        compra.saldo_pendiente = 0
        hoy = date.today()
        session.query(CuotaProgramada).filter(
            CuotaProgramada.compra_id == compra_id,
            CuotaProgramada.fecha_pago_real.is_(None),
        ).update({CuotaProgramada.fecha_pago_real: hoy})
        session.commit()

    genero_movimiento = moneda == "USD" and monto_restante > 0
    if genero_movimiento:
        agregar_movimiento(
            usuario_id,
            date.today(),
            "egreso",
            "Otros gastos",
            f"Compra programada: {nombre}",
            monto_restante,
        )
    return {"monto": monto_restante, "moneda": moneda, "genero_movimiento": genero_movimiento}


def total_programado_por_moneda(usuario_id: int) -> dict:
    """Suma de saldo_pendiente de compras programadas, agrupada por moneda.

    No se combinan VES y USD en un solo total: son monedas distintas.
    """
    with SessionLocal() as session:
        rows = (
            session.query(
                CompraProgramada.moneda,
                func.coalesce(func.sum(CompraProgramada.saldo_pendiente), 0),
            )
            .filter(CompraProgramada.usuario_id == usuario_id)
            .group_by(CompraProgramada.moneda)
            .all()
        )
        return {moneda: float(total) for moneda, total in rows}
