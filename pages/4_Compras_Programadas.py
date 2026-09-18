"""Compras programadas: planificación de compras futuras en VES o USD,
con posibilidad de dividirlas en cuotas con fecha de pago."""
from datetime import date

import streamlit as st

from core import queries
from core.auth import get_current_user_id

usuario_id = get_current_user_id()

st.title("Compras programadas", icon=":material/shopping_cart:")
st.caption(
    "Planifica compras futuras en bolívares o dólares. Si la vas a pagar en "
    "cuotas, agrega cada una con su monto y fecha de pago."
)

SIMBOLO = {"VES": "Bs", "USD": "$"}

tab_resumen, tab_nueva_compra, tab_nueva_cuota = st.tabs(
    [
        ":material/summarize: Resumen",
        ":material/add_shopping_cart: Nueva compra programada",
        ":material/event_repeat: Agregar cuota/pago",
    ]
)

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
with tab_resumen:
    totales = queries.total_programado_por_moneda(usuario_id)
    with st.container(horizontal=True):
        st.metric(
            "Total programado (USD)",
            f"$ {totales.get('USD', 0):,.2f}",
            icon=":material/attach_money:",
            border=True,
        )
        st.metric(
            "Total programado (VES)",
            f"Bs {totales.get('VES', 0):,.2f}",
            icon=":material/payments:",
            border=True,
        )

    df_todas = queries.listar_cuotas_programadas(usuario_id)

    if df_todas.empty:
        st.caption("No hay cuotas/pagos registrados todavía.")
    else:
        conteos = df_todas["estado"].value_counts()
        with st.container(horizontal=True):
            st.badge(
                f"{conteos.get('Vencido', 0)} vencidas",
                icon=":material/error:",
                color="red",
            )
            st.badge(
                f"{conteos.get('Pendiente', 0)} pendientes",
                icon=":material/schedule:",
                color="orange",
            )
            st.badge(
                f"{conteos.get('Pagado', 0)} pagadas",
                icon=":material/check_circle:",
                color="green",
            )

        filtro_estado = st.segmented_control(
            "Filtrar por estado",
            options=["Todos", "Pendiente", "Vencido", "Pagado"],
            default="Todos",
            label_visibility="collapsed",
        )
        df_cuotas = df_todas if filtro_estado in (None, "Todos") else df_todas[
            df_todas["estado"] == filtro_estado
        ]

        df_mostrar = df_cuotas.copy()
        df_mostrar["fecha_pago_real"] = df_mostrar["fecha_pago_real"].apply(
            lambda f: f if f else "—"
        )
        st.dataframe(
            df_mostrar.rename(
                columns={
                    "compra": "Compra",
                    "moneda": "Moneda",
                    "monto": "Monto",
                    "fecha_pago": "Fecha planeada",
                    "fecha_pago_real": "Pagada el",
                    "estado": "Estado",
                }
            ).drop(columns=["id"]),
            width="stretch",
            hide_index=True,
        )

        pendientes = df_cuotas[df_cuotas["estado"] != "Pagado"]
        if not pendientes.empty:
            st.subheader("Marcar una cuota como pagada", icon=":material/task_alt:")
            opciones = {
                f"#{row.id} · {row.compra} · {SIMBOLO.get(row.moneda, '')} {row.monto:,.2f} · {row.fecha_pago}": row.id
                for row in pendientes.itertuples()
            }
            seleccion = st.selectbox("Selecciona la cuota", options=list(opciones.keys()))
            fecha_pago_real = st.date_input("Fecha de pago", value=date.today())
            if st.button(
                "Marcar como pagada", icon=":material/task_alt:", type="primary"
            ):
                queries.marcar_cuota_pagada(usuario_id, opciones[seleccion], fecha_pago_real)
                st.toast("Cuota registrada como pagada.", icon=":material/check_circle:")
                st.rerun()

    st.subheader("Compras programadas registradas", icon=":material/list_alt:")
    df_compras = queries.listar_compras_programadas(usuario_id)
    if df_compras.empty:
        st.caption("Aún no has programado ninguna compra.")
    else:
        df_compras_mostrar = df_compras.copy()
        df_compras_mostrar["monto_total"] = df_compras_mostrar.apply(
            lambda r: f"{SIMBOLO.get(r['moneda'], '')} {r['monto_total']:,.2f}", axis=1
        )
        df_compras_mostrar["saldo_pendiente"] = df_compras_mostrar.apply(
            lambda r: f"{SIMBOLO.get(r['moneda'], '')} {r['saldo_pendiente']:,.2f}", axis=1
        )
        st.dataframe(
            df_compras_mostrar.rename(
                columns={
                    "nombre": "Nombre",
                    "moneda": "Moneda",
                    "monto_total": "Monto total",
                    "saldo_pendiente": "Saldo pendiente",
                    "notas": "Notas",
                }
            ).drop(columns=["id"]),
            width="stretch",
            hide_index=True,
        )

# ---------------------------------------------------------------------------
# Nueva compra programada
# ---------------------------------------------------------------------------
with tab_nueva_compra:
    with st.form("nueva_compra_programada", clear_on_submit=True):
        nombre = st.text_input(
            "¿Qué quieres comprar? (ej. Laptop nueva, Viaje a Margarita)"
        )
        c1, c2 = st.columns(2)
        with c1:
            moneda = st.selectbox("Moneda", options=["USD", "VES"])
        with c2:
            monto_total = st.number_input(
                "Total a gastar", min_value=0.0, step=1.0, format="%.2f"
            )
        notas = st.text_area("Notas (opcional)")
        enviado = st.form_submit_button(
            "Programar compra", icon=":material/add_shopping_cart:", width="stretch"
        )
        if enviado:
            if not nombre or monto_total <= 0:
                st.error("Ingresa un nombre y un total a gastar mayor a 0.")
            else:
                queries.agregar_compra_programada(usuario_id, nombre, moneda, monto_total, notas)
                st.toast(f'"{nombre}" programada.', icon=":material/check_circle:")
                st.rerun()

# ---------------------------------------------------------------------------
# Agregar cuota/pago
# ---------------------------------------------------------------------------
with tab_nueva_cuota:
    df_compras = queries.listar_compras_programadas(usuario_id)
    if df_compras.empty:
        st.caption(
            "Primero programa una compra en la pestaña «Nueva compra programada»."
        )
    else:
        with st.form("nueva_cuota_programada", clear_on_submit=True):
            opciones_compra = {
                f"{row.nombre} ({SIMBOLO.get(row.moneda, '')} {row.saldo_pendiente:,.2f} {row.moneda} restante)": row.id
                for row in df_compras.itertuples()
            }
            compra_sel = st.selectbox("Compra programada", options=list(opciones_compra.keys()))
            monto = st.number_input(
                "Monto de la cuota/pago", min_value=0.0, step=1.0, format="%.2f"
            )
            fecha_pago = st.date_input("Fecha de pago", value=date.today())
            notas = st.text_input("Notas (opcional)")
            enviado = st.form_submit_button(
                "Agregar cuota", icon=":material/event_repeat:", width="stretch"
            )
            if enviado:
                if monto <= 0:
                    st.error("El monto debe ser mayor a 0.")
                else:
                    queries.agregar_cuota_programada(
                        usuario_id, opciones_compra[compra_sel], monto, fecha_pago, notas
                    )
                    st.toast("Cuota agregada.", icon=":material/check_circle:")
                    st.rerun()
