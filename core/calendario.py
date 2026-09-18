"""Calendario mensual en HTML para marcar los días con cuotas programadas
por pagar. Streamlit no trae un widget de calendario nativo, así que se
arma con una tabla HTML simple, con los mismos colores del tema oscuro fijo
de la app (.streamlit/config.toml) para que combine con el resto.
"""
import calendar as _calendar
from collections import defaultdict
from datetime import date

import pandas as pd
import streamlit as st

_DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

_BORDE = "#334155"
_FONDO_CELDA = "#1E293B"
_FONDO_HOY = "#0F172A"
_TEXTO = "#F1F5F9"
_TEXTO_MUTED = "#94A3B8"
_ROJO = "#F87171"
_NARANJA = "#FB923C"
_SIMBOLO = {"USD": "$", "VES": "Bs"}


def _agrupar_por_dia(df_mes: pd.DataFrame) -> dict:
    dias = defaultdict(list)
    for row in df_mes.itertuples():
        dias[row.fecha_pago.day].append(
            (row.monto, row.moneda, row.compra, row.estado == "Vencido")
        )
    return dias


def render_calendario_cuotas(df_cuotas: pd.DataFrame, anio: int, mes: int) -> None:
    """Pinta un calendario del mes dado, marcando los días con cuotas
    pendientes o vencidas. `df_cuotas` debe traer las columnas de
    queries.listar_cuotas_programadas (ya filtradas a no-pagadas)."""
    if df_cuotas.empty:
        df_mes = df_cuotas
    else:
        fechas = pd.to_datetime(df_cuotas["fecha_pago"])
        df_mes = df_cuotas[(fechas.dt.year == anio) & (fechas.dt.month == mes)]

    dias_marcados = _agrupar_por_dia(df_mes) if not df_mes.empty else {}
    hoy = date.today()
    semanas = _calendar.Calendar(firstweekday=0).monthdayscalendar(anio, mes)

    filas_html = ""
    for semana in semanas:
        celdas = ""
        for dia in semana:
            if dia == 0:
                celdas += '<td style="border:none;padding:6px;"></td>'
                continue
            es_hoy = date(anio, mes, dia) == hoy
            pagos = dias_marcados.get(dia, [])
            vencido = any(p[3] for p in pagos)
            color_borde = _ROJO if vencido else (_NARANJA if pagos else _BORDE)
            fondo = _FONDO_HOY if es_hoy else _FONDO_CELDA

            contenido_pagos = ""
            if pagos:
                color_texto = _ROJO if vencido else _NARANJA
                lineas = "<br>".join(
                    f"{_SIMBOLO.get(moneda, '')}{monto:,.0f} · {compra}"
                    for monto, moneda, compra, _ in pagos
                )
                contenido_pagos = (
                    f'<div style="font-size:10px;line-height:1.35;margin-top:3px;'
                    f'color:{color_texto};font-weight:600;">{lineas}</div>'
                )

            celdas += (
                f'<td style="border:1.5px solid {color_borde};background:{fondo};'
                f"border-radius:6px;padding:6px;vertical-align:top;width:14.28%;"
                f'min-width:80px;">'
                f'<div style="font-size:12px;color:{_TEXTO};'
                f'font-weight:{"700" if es_hoy else "500"};">{dia}</div>'
                f"{contenido_pagos}</td>"
            )
        filas_html += f"<tr>{celdas}</tr>"

    encabezado = "".join(
        f'<th style="color:{_TEXTO_MUTED};font-size:11px;font-weight:600;'
        f'padding:4px 6px;text-align:left;">{d}</th>'
        for d in _DIAS
    )

    st.markdown(
        f"""
        <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:separate;border-spacing:4px;">
            <thead><tr>{encabezado}</tr></thead>
            <tbody>{filas_html}</tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )
