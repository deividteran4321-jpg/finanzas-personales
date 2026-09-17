"""Punto de entrada: exige login y luego renderiza el Dashboard principal."""
import plotly.express as px
import streamlit as st

from core import queries
from core.auth import get_current_user_id, require_auth
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
usuario_id = get_current_user_id()

# --- A partir de aquí, el usuario ya está autenticado ---
with st.sidebar:
    st.markdown(f"**:material/person: {st.session_state.get('name', '')}**")
    authenticator.logout("Cerrar sesión", "sidebar")
    st.caption(
        "La sesión se recuerda automáticamente en este navegador durante 30 días."
    )

st.title("Panel financiero", icon=":material/dashboard:")

# --- Filtros dinámicos ---
anios = queries.anios_disponibles(usuario_id)
categorias = queries.listar_categorias()

with st.container(horizontal=True):
    anio_sel = st.selectbox("Año", options=["Todos"] + anios)
    mes_sel = st.selectbox(
        "Mes",
        options=["Todos"] + list(range(1, 13)),
        format_func=lambda m: m if m == "Todos" else f"{m:02d}",
    )
    categoria_sel = st.selectbox("Categoría", options=["Todas"] + categorias)

anio_f = None if anio_sel == "Todos" else anio_sel
mes_f = None if mes_sel == "Todos" else mes_sel
categoria_f = None if categoria_sel == "Todas" else categoria_sel

# --- KPIs ---
saldo = queries.saldo_actual(usuario_id)
total_deudas = queries.total_deudas(usuario_id)
proximo = queries.proximo_pago(usuario_id)
historico = queries.saldo_historico_mensual(usuario_id)

with st.container(horizontal=True):
    st.metric(
        "Saldo actual",
        f"${saldo:,.2f}",
        icon=":material/account_balance:",
        border=True,
        chart_data=historico if len(historico) > 1 else None,
        chart_type="line",
    )
    st.metric(
        "Total de deudas",
        f"${total_deudas:,.2f}",
        icon=":material/credit_card:",
        border=True,
    )
    if proximo:
        st.metric(
            "Próximo pago a vencer",
            f"${proximo['monto']:,.2f}",
            delta=f"{proximo['deuda']} · vence {proximo['fecha_vencimiento']:%d/%m/%Y}",
            delta_color="off",
            icon=":material/warning:" if proximo["estado"] == "Vencido" else ":material/event:",
            border=True,
        )
    else:
        st.metric(
            "Próximo pago a vencer",
            "—",
            delta="Sin pagos pendientes",
            delta_color="off",
            icon=":material/event_available:",
            border=True,
        )

# --- Gráficos ---
g1, g2 = st.columns([3, 2])

with g1:
    with st.container(border=True):
        st.subheader("Ingresos vs. egresos por mes", icon=":material/bar_chart:")
        df_mensual = queries.movimientos_por_mes(usuario_id, anio_f, mes_f, categoria_f)
        if df_mensual.empty:
            st.caption("Aún no hay movimientos registrados para este filtro.")
        else:
            fig = px.bar(
                df_mensual,
                x="periodo",
                y="monto",
                color="tipo",
                barmode="group",
                # Verde/rojo con significado semantico (ingreso/egreso), no
                # el color de categoria generico del tema.
                color_discrete_map={"ingreso": "#34D399", "egreso": "#F87171"},
                labels={"periodo": "Mes", "monto": "Monto", "tipo": "Tipo"},
            )
            fig.update_layout(legend_title_text="")
            # "periodo" es texto tipo "2026-09"; sin esto Plotly lo detecta
            # como fecha y dibuja un eje temporal continuo con timestamps raros.
            fig.update_xaxes(type="category")
            st.plotly_chart(fig, width="stretch")

with g2:
    with st.container(border=True):
        st.subheader("Gastos por categoría", icon=":material/donut_small:")
        df_cat = queries.distribucion_por_categoria(usuario_id, anio_f, mes_f)
        if df_cat.empty:
            st.caption("Aún no hay egresos registrados para este filtro.")
        else:
            fig2 = px.pie(df_cat, names="categoria", values="monto", hole=0.55)
            st.plotly_chart(fig2, width="stretch")

st.caption(
    "Usa las páginas del menú lateral para registrar movimientos, "
    "gestionar deudas/pagos y compras programadas, administrar usuarios, "
    "o cambiar tu contraseña."
)
