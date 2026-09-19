"""Punto de entrada: define la navegación entre páginas y sus títulos.

IMPORTANTE: aquí no debe haber nada que pueda detener el script (como un
require_auth() con st.stop()) antes de llegar a st.navigation(). Si
Streamlit nunca llega a ejecutar st.navigation() en un run, cae de vuelta
al descubrimiento automático "legado" de pages/ - y ese modo permite entrar
directo a la URL de cualquier página (ej. /Movimientos o /Admin) sin pasar
por el login para nada. Por eso el login, la base de datos y el fondo se
resuelven en cada página (pages/*.py) y no aquí: así quedan protegidos sin
importar por qué ruta interna Streamlit termine sirviendo esa página.
"""
import streamlit as st

st.set_page_config(
    page_title="Finanzas personales",
    page_icon=":material/account_balance_wallet:",
    layout="wide",
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
