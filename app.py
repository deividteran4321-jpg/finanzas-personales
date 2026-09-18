"""Punto de entrada: exige login y define la navegación entre páginas.

El título/ícono de cada página (mostrados en la barra lateral y en la
pestaña del navegador) se declaran una sola vez aquí, vía st.Page - por
eso las páginas en pages/ ya no llaman a st.set_page_config() por su
cuenta. Login, fondo decorativo y la barra lateral de usuario también se
resuelven aquí una sola vez para toda la sesión.
"""
import streamlit as st

from core.auth import require_auth
from core.background import render_world_map_background
from core.database import init_db

st.set_page_config(
    page_title="Finanzas personales",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
)
render_world_map_background()

init_db()
authenticator = require_auth()

with st.sidebar:
    st.markdown(f"**:material/person: {st.session_state.get('name', '')}**")
    authenticator.logout("Cerrar sesión", "sidebar")
    st.caption(
        "La sesión se recuerda automáticamente en este navegador durante 30 días."
    )

pg = st.navigation(
    [
        st.Page(
            "pages/0_Dashboard.py",
            title="Dashboard",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            "pages/1_Movimientos.py",
            title="Movimientos",
            icon=":material/receipt_long:",
        ),
        st.Page(
            "pages/2_Deudas.py",
            title="Deudas",
            icon=":material/request_quote:",
        ),
        st.Page(
            "pages/4_Compras_Programadas.py",
            title="Compras programadas",
            icon=":material/shopping_cart:",
        ),
        st.Page(
            "pages/3_Admin.py",
            title="Admin",
            icon=":material/admin_panel_settings:",
        ),
    ]
)
pg.run()
