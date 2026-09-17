"""Registro detallado de ingresos y egresos diarios."""
from datetime import date

import streamlit as st

from core import queries
from core.auth import get_current_user_id, require_auth
from core.background import render_world_map_background
from core.database import init_db

st.set_page_config(
    page_title="Movimientos",
    page_icon=":material/receipt_long:",
    layout="wide",
)
render_world_map_background()

init_db()
authenticator = require_auth()
usuario_id = get_current_user_id()

with st.sidebar:
    st.markdown(f"**:material/person: {st.session_state.get('name', '')}**")
    authenticator.logout("Cerrar sesión", "sidebar")

st.title("Ingresos y egresos", icon=":material/receipt_long:")

# "Tipo" va FUERA del form a propósito: la lista de categorías depende de
# él, y los widgets dentro de un st.form no disparan un rerun hasta que se
# envía el formulario - si "Tipo" estuviera adentro, la categoría mostrada
# quedaría desfasada (podrías guardar una categoría de ingreso en un egreso
# sin darte cuenta).
tipo = st.selectbox("Tipo", options=["ingreso", "egreso"], key="mov_tipo_nuevo")

with st.form("nuevo_movimiento", clear_on_submit=True, border=True):
    c1, c2, c3 = st.columns(3)
    with c1:
        fecha = st.date_input("Fecha", value=date.today())
        categorias = queries.listar_categorias(tipo=tipo)
        categoria = st.selectbox("Categoría", options=categorias)
    with c2:
        monto = st.number_input("Monto", min_value=0.0, step=1.0, format="%.2f")
    with c3:
        descripcion = st.text_input("Descripción (opcional)")

    enviado = st.form_submit_button(
        "Agregar movimiento", icon=":material/add:", width="stretch"
    )
    if enviado:
        if monto <= 0:
            st.error("El monto debe ser mayor a 0.")
        else:
            queries.agregar_movimiento(usuario_id, fecha, tipo, categoria, descripcion, monto)
            st.toast("Movimiento agregado.", icon=":material/check_circle:")
            st.rerun()

st.subheader("Historial", icon=":material/history:")

with st.container(horizontal=True):
    anios = queries.anios_disponibles(usuario_id)
    categorias_todas = queries.listar_categorias()
    anio_sel = st.selectbox("Año", options=["Todos"] + anios, key="mov_anio")
    mes_sel = st.selectbox(
        "Mes",
        options=["Todos"] + list(range(1, 13)),
        format_func=lambda m: m if m == "Todos" else f"{m:02d}",
        key="mov_mes",
    )
    categoria_sel = st.selectbox(
        "Categoría", options=["Todas"] + categorias_todas, key="mov_categoria"
    )

df = queries.listar_movimientos(
    usuario_id,
    anio=None if anio_sel == "Todos" else anio_sel,
    mes=None if mes_sel == "Todos" else mes_sel,
    categoria=None if categoria_sel == "Todas" else categoria_sel,
)

if df.empty:
    st.caption("No hay movimientos para este filtro todavía.")
else:
    st.dataframe(
        df.rename(
            columns={
                "fecha": "Fecha",
                "tipo": "Tipo",
                "categoria": "Categoría",
                "descripcion": "Descripción",
                "monto": "Monto",
            }
        ).drop(columns=["id"]),
        width="stretch",
        hide_index=True,
    )

    with st.expander("Eliminar un movimiento", icon=":material/delete:"):
        opciones = {
            f"#{row.id} · {row.fecha} · {row.tipo} · ${row.monto:,.2f} · {row.descripcion or ''}": row.id
            for row in df.itertuples()
        }
        seleccion = st.selectbox(
            "Selecciona el movimiento a eliminar", options=list(opciones.keys())
        )
        if st.button("Eliminar", icon=":material/delete:", type="secondary"):
            queries.eliminar_movimiento(usuario_id, opciones[seleccion])
            st.toast("Movimiento eliminado.", icon=":material/check_circle:")
            st.rerun()
