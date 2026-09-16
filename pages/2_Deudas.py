"""Módulo de Deudas y Cuentas por Pagar, con estados Pendiente/Vencido/Pagado."""
from datetime import date

import streamlit as st

from core import queries
from core.auth import require_auth
from core.database import init_db

st.set_page_config(page_title="Deudas", page_icon="🧾", layout="wide")

init_db()
authenticator = require_auth()

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state.get('name', '')}")
    authenticator.logout("Cerrar sesión", "sidebar")

st.title("🧾 Deudas y Cuentas por Pagar")

tab_resumen, tab_nueva_deuda, tab_nuevo_pago = st.tabs(
    ["Resumen de pagos", "Nueva deuda", "Agregar pago/cuota"]
)

# ---------------------------------------------------------------------------
# Resumen de pagos
# ---------------------------------------------------------------------------
with tab_resumen:
    filtro_estado = st.radio(
        "Filtrar por estado",
        options=["Todos", "Pendiente", "Vencido", "Pagado"],
        horizontal=True,
    )
    df_pagos = queries.listar_pagos(
        estado=None if filtro_estado == "Todos" else filtro_estado
    )

    if df_pagos.empty:
        st.info("No hay pagos registrados para este filtro.")
    else:
        color_estado = {"Pendiente": "🟡", "Vencido": "🔴", "Pagado": "🟢"}
        df_mostrar = df_pagos.copy()
        df_mostrar["fecha_pago"] = df_mostrar["fecha_pago"].apply(
            lambda f: f if f else "—"
        )
        df_mostrar["estado"] = df_mostrar["estado"].map(
            lambda e: f"{color_estado.get(e, '')} {e}"
        )
        st.dataframe(
            df_mostrar.rename(
                columns={
                    "deuda": "Deuda",
                    "monto": "Monto",
                    "fecha_vencimiento": "Vence",
                    "fecha_pago": "Pagado el",
                    "estado": "Estado",
                }
            ).drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
        )

        pendientes = df_pagos[df_pagos["estado"] != "Pagado"]
        if not pendientes.empty:
            st.subheader("Marcar un pago como pagado")
            opciones = {
                f"#{row.id} · {row.deuda} · ${row.monto:,.2f} · vence {row.fecha_vencimiento}": row.id
                for row in pendientes.itertuples()
            }
            seleccion = st.selectbox("Selecciona el pago", options=list(opciones.keys()))
            fecha_pago = st.date_input("Fecha de pago", value=date.today())
            if st.button("Marcar como pagado", type="primary"):
                queries.marcar_pagado(opciones[seleccion], fecha_pago)
                st.success("Pago registrado.")
                st.rerun()

    st.divider()
    st.subheader("Deudas registradas")
    df_deudas = queries.listar_deudas()
    if df_deudas.empty:
        st.info("Aún no has registrado ninguna deuda.")
    else:
        st.dataframe(
            df_deudas.rename(
                columns={
                    "nombre": "Nombre",
                    "monto_total": "Monto total",
                    "saldo_pendiente": "Saldo pendiente",
                    "notas": "Notas",
                }
            ).drop(columns=["id"]),
            use_container_width=True,
            hide_index=True,
        )

# ---------------------------------------------------------------------------
# Nueva deuda
# ---------------------------------------------------------------------------
with tab_nueva_deuda:
    with st.form("nueva_deuda", clear_on_submit=True):
        nombre = st.text_input("Nombre de la deuda (ej. Tarjeta Banesco, Préstamo Juan)")
        monto_total = st.number_input("Monto total", min_value=0.0, step=1.0, format="%.2f")
        notas = st.text_area("Notas (opcional)")
        enviado = st.form_submit_button("Crear deuda", use_container_width=True)
        if enviado:
            if not nombre or monto_total <= 0:
                st.error("Ingresa un nombre y un monto total mayor a 0.")
            else:
                queries.agregar_deuda(nombre, monto_total, notas)
                st.success(f'Deuda "{nombre}" creada.')
                st.rerun()

# ---------------------------------------------------------------------------
# Nuevo pago/cuota
# ---------------------------------------------------------------------------
with tab_nuevo_pago:
    df_deudas = queries.listar_deudas()
    if df_deudas.empty:
        st.info("Primero crea una deuda en la pestaña 'Nueva deuda'.")
    else:
        with st.form("nuevo_pago", clear_on_submit=True):
            opciones_deuda = {
                f"{row.nombre} (saldo ${row.saldo_pendiente:,.2f})": row.id
                for row in df_deudas.itertuples()
            }
            deuda_sel = st.selectbox("Deuda", options=list(opciones_deuda.keys()))
            monto = st.number_input("Monto de la cuota/pago", min_value=0.0, step=1.0, format="%.2f")
            fecha_vencimiento = st.date_input("Fecha de vencimiento", value=date.today())
            notas = st.text_input("Notas (opcional)")
            enviado = st.form_submit_button("Agregar pago", use_container_width=True)
            if enviado:
                if monto <= 0:
                    st.error("El monto debe ser mayor a 0.")
                else:
                    queries.agregar_pago(
                        opciones_deuda[deuda_sel], monto, fecha_vencimiento, notas
                    )
                    st.success("Pago/cuota agregado.")
                    st.rerun()
