"""Módulo de deudas y cuentas por pagar, con estados Pendiente/Vencido/Pagado."""
from datetime import date

import streamlit as st

from core import queries
from core.auth import get_current_user_id, require_auth
from core.background import render_world_map_background
from core.database import init_db

render_world_map_background()
init_db()
authenticator = require_auth()
usuario_id = get_current_user_id()

with st.sidebar:
    st.markdown(f"**:material/person: {st.session_state.get('name', '')}**")
    authenticator.logout("Cerrar sesión", "sidebar")

st.title("Deudas y cuentas por pagar", icon=":material/request_quote:")

tab_resumen, tab_nueva_deuda, tab_nuevo_pago = st.tabs(
    [
        ":material/summarize: Resumen de pagos",
        ":material/add_card: Nueva deuda",
        ":material/event_repeat: Agregar pago/cuota",
    ]
)

# ---------------------------------------------------------------------------
# Resumen de pagos
# ---------------------------------------------------------------------------
with tab_resumen:
    df_todos = queries.listar_pagos(usuario_id)

    if df_todos.empty:
        st.caption("No hay pagos registrados todavía.")
    else:
        conteos = df_todos["estado"].value_counts()
        with st.container(horizontal=True):
            st.badge(
                f"{conteos.get('Vencido', 0)} vencidos",
                icon=":material/error:",
                color="red",
            )
            st.badge(
                f"{conteos.get('Pendiente', 0)} pendientes",
                icon=":material/schedule:",
                color="orange",
            )
            st.badge(
                f"{conteos.get('Pagado', 0)} pagados",
                icon=":material/check_circle:",
                color="green",
            )

        filtro_estado = st.segmented_control(
            "Filtrar por estado",
            options=["Todos", "Pendiente", "Vencido", "Pagado"],
            default="Todos",
            label_visibility="collapsed",
        )
        df_pagos = df_todos if filtro_estado in (None, "Todos") else df_todos[
            df_todos["estado"] == filtro_estado
        ]

        df_mostrar = df_pagos.copy()
        df_mostrar["fecha_pago"] = df_mostrar["fecha_pago"].apply(
            lambda f: f if f else "—"
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
            width="stretch",
            hide_index=True,
        )

        pendientes = df_pagos[df_pagos["estado"] != "Pagado"]
        if not pendientes.empty:
            st.subheader("Marcar un pago como pagado", icon=":material/task_alt:")
            opciones = {
                f"#{row.id} · {row.deuda} · ${row.monto:,.2f} · vence {row.fecha_vencimiento}": row.id
                for row in pendientes.itertuples()
            }
            seleccion = st.selectbox("Selecciona el pago", options=list(opciones.keys()))
            fecha_pago = st.date_input("Fecha de pago", value=date.today())
            if st.button(
                "Marcar como pagado", icon=":material/task_alt:", type="primary"
            ):
                queries.marcar_pagado(usuario_id, opciones[seleccion], fecha_pago)
                st.toast("Pago registrado.", icon=":material/check_circle:")
                st.rerun()

    st.subheader("Deudas registradas", icon=":material/credit_card:")
    df_deudas = queries.listar_deudas(usuario_id)
    if df_deudas.empty:
        st.caption("Aún no has registrado ninguna deuda.")
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
            width="stretch",
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
        enviado = st.form_submit_button(
            "Crear deuda", icon=":material/add_card:", width="stretch"
        )
        if enviado:
            if not nombre or monto_total <= 0:
                st.error("Ingresa un nombre y un monto total mayor a 0.")
            else:
                queries.agregar_deuda(usuario_id, nombre, monto_total, notas)
                st.toast(f'Deuda "{nombre}" creada.', icon=":material/check_circle:")
                st.rerun()

# ---------------------------------------------------------------------------
# Nuevo pago/cuota
# ---------------------------------------------------------------------------
with tab_nuevo_pago:
    df_deudas = queries.listar_deudas(usuario_id)
    if df_deudas.empty:
        st.caption("Primero crea una deuda en la pestaña «Nueva deuda».")
    else:
        with st.form("nuevo_pago", clear_on_submit=True):
            opciones_deuda = {
                f"{row.nombre} (saldo ${row.saldo_pendiente:,.2f})": row.id
                for row in df_deudas.itertuples()
            }
            deuda_sel = st.selectbox("Deuda", options=list(opciones_deuda.keys()))
            monto = st.number_input(
                "Monto de la cuota/pago", min_value=0.0, step=1.0, format="%.2f"
            )
            fecha_vencimiento = st.date_input("Fecha de vencimiento", value=date.today())
            notas = st.text_input("Notas (opcional)")
            enviado = st.form_submit_button(
                "Agregar pago", icon=":material/event_repeat:", width="stretch"
            )
            if enviado:
                if monto <= 0:
                    st.error("El monto debe ser mayor a 0.")
                else:
                    queries.agregar_pago(
                        usuario_id, opciones_deuda[deuda_sel], monto, fecha_vencimiento, notas
                    )
                    st.toast("Pago/cuota agregado.", icon=":material/check_circle:")
                    st.rerun()
