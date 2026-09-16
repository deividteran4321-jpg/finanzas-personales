"""Punto de entrada: exige login y luego renderiza el Dashboard principal."""
import plotly.express as px
import streamlit as st

from core import queries
from core.auth import require_auth
from core.database import init_db

st.set_page_config(page_title="Finanzas Personales", page_icon="💰", layout="wide")

CUSTOM_CSS = """
<style>
    #MainMenu, footer {visibility: hidden;}

    .kpi-card {
        border-radius: 16px;
        padding: 1.25rem 1.5rem;
        background: linear-gradient(145deg, #151b28 0%, #1b2333 100%);
        border: 1px solid #232b3b;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.35rem;
    }
    .kpi-value {
        font-size: clamp(1.3rem, 2.4vw, 1.9rem);
        font-weight: 700;
        line-height: 1.1;
        white-space: nowrap;
    }
    .kpi-value.positive { color: #22c55e; }
    .kpi-value.negative { color: #f87171; }
    .kpi-value.neutral  { color: #e2e8f0; }
    .kpi-sub {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 0.35rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

init_db()
authenticator = require_auth()

# --- A partir de aquí, el usuario ya está autenticado ---
with st.sidebar:
    st.markdown(f"### 👋 {st.session_state.get('name', '')}")
    authenticator.logout("Cerrar sesión", "sidebar")
    st.caption(
        "La sesión se recuerda automáticamente en este navegador durante "
        "30 días gracias a la cookie de inicio de sesión."
    )

st.title("💰 Panel Financiero")

# --- Filtros dinámicos ---
anios = queries.anios_disponibles()
categorias = queries.listar_categorias()

f_col1, f_col2, f_col3 = st.columns(3)
with f_col1:
    anio_sel = st.selectbox("Año", options=["Todos"] + anios)
with f_col2:
    mes_sel = st.selectbox(
        "Mes",
        options=["Todos"] + list(range(1, 13)),
        format_func=lambda m: m if m == "Todos" else f"{m:02d}",
    )
with f_col3:
    categoria_sel = st.selectbox("Categoría", options=["Todas"] + categorias)

anio_f = None if anio_sel == "Todos" else anio_sel
mes_f = None if mes_sel == "Todos" else mes_sel
categoria_f = None if categoria_sel == "Todas" else categoria_sel

st.divider()

# --- KPIs ---
saldo = queries.saldo_actual()
total_deudas = queries.total_deudas()
proximo = queries.proximo_pago()

k1, k2, k3 = st.columns(3)
with k1:
    clase = "positive" if saldo >= 0 else "negative"
    st.markdown(
        f"""<div class="kpi-card">
                <div class="kpi-label">Saldo Actual</div>
                <div class="kpi-value {clase}">${saldo:,.2f}</div>
            </div>""",
        unsafe_allow_html=True,
    )
with k2:
    st.markdown(
        f"""<div class="kpi-card">
                <div class="kpi-label">Total de Deudas</div>
                <div class="kpi-value neutral">${total_deudas:,.2f}</div>
            </div>""",
        unsafe_allow_html=True,
    )
with k3:
    if proximo:
        sub = f"{proximo['deuda']} · {proximo['estado']}"
        valor = f"${proximo['monto']:,.2f} — {proximo['fecha_vencimiento']:%d/%m/%Y}"
    else:
        sub = "Sin pagos pendientes"
        valor = "—"
    st.markdown(
        f"""<div class="kpi-card">
                <div class="kpi-label">Próximo Pago a Vencer</div>
                <div class="kpi-value neutral" style="font-size:1.3rem">{valor}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""",
        unsafe_allow_html=True,
    )

st.divider()

# --- Gráficos ---
g1, g2 = st.columns([3, 2])

with g1:
    st.subheader("Ingresos vs Egresos por mes")
    df_mensual = queries.movimientos_por_mes(anio_f, mes_f, categoria_f)
    if df_mensual.empty:
        st.info("Aún no hay movimientos registrados para este filtro.")
    else:
        fig = px.bar(
            df_mensual,
            x="periodo",
            y="monto",
            color="tipo",
            barmode="group",
            template="plotly_dark",
            color_discrete_map={"ingreso": "#22c55e", "egreso": "#f87171"},
            labels={"periodo": "Mes", "monto": "Monto", "tipo": "Tipo"},
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title_text="",
        )
        # "periodo" es texto tipo "2026-09"; sin esto Plotly lo detecta como
        # fecha y dibuja un eje temporal continuo con timestamps raros.
        fig.update_xaxes(type="category")
        st.plotly_chart(fig, use_container_width=True)

with g2:
    st.subheader("Distribución de gastos por categoría")
    df_cat = queries.distribucion_por_categoria(anio_f, mes_f)
    if df_cat.empty:
        st.info("Aún no hay egresos registrados para este filtro.")
    else:
        fig2 = px.pie(
            df_cat,
            names="categoria",
            values="monto",
            hole=0.55,
            template="plotly_dark",
        )
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", showlegend=True)
        st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "Usa las páginas del menú lateral para registrar movimientos, "
    "gestionar deudas/pagos, o cambiar tu usuario y contraseña."
)
