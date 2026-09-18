"""Dashboard principal: KPIs, tasas del día, gráficos, compras programadas
y alertas/calendario de cuotas por pagar.

El login, el fondo decorativo y la barra lateral (usuario + cerrar sesión)
ya se resuelven una sola vez en app.py (el router de navegación) antes de
llegar aquí - esta página solo necesita el usuario_id para filtrar sus
propios datos.
"""
from datetime import date, timedelta

import plotly.express as px
import streamlit as st

from core import queries
from core.auth import get_current_user_id
from core.calendario import render_calendario_cuotas
from core.tasas import tasa_bcv, tasa_paralelo

usuario_id = get_current_user_id()

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

# --- Tasas del día ---
st.subheader("Tasas del día", icon=":material/currency_exchange:")
bcv = tasa_bcv()
paralelo = tasa_paralelo()
with st.container(horizontal=True):
    st.metric(
        "BCV (oficial)",
        f"Bs {bcv['promedio']:,.2f}" if bcv else "No disponible",
        icon=":material/account_balance:",
        border=True,
    )
    st.metric(
        "Paralelo / Binance",
        f"Bs {paralelo['promedio']:,.2f}" if paralelo else "No disponible",
        icon=":material/currency_bitcoin:",
        border=True,
    )
st.caption(
    "Tasas de referencia vía dolarapi.com, actualizadas cada hora - "
    "\"Paralelo/Binance\" es la tasa de mercado paralelo (el P2P de Binance "
    "es su principal insumo). Son informativas: no afectan ningún cálculo "
    "de esta app."
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

# --- Compras programadas ---
st.subheader("Compras programadas", icon=":material/shopping_cart:")
totales_compras = queries.total_programado_por_moneda(usuario_id)
with st.container(horizontal=True):
    st.metric(
        "Programado en USD",
        f"$ {totales_compras.get('USD', 0):,.2f}",
        icon=":material/attach_money:",
        border=True,
    )
    st.metric(
        "Programado en VES",
        f"Bs {totales_compras.get('VES', 0):,.2f}",
        icon=":material/payments:",
        border=True,
    )

df_compras = queries.listar_compras_programadas(usuario_id)
pendientes_compras = (
    df_compras[df_compras["saldo_pendiente"] > 0] if not df_compras.empty else df_compras
)
if pendientes_compras.empty:
    st.caption(
        "No tienes compras programadas pendientes. Agrégalas desde la "
        "página Compras programadas."
    )
else:
    simbolo = {"USD": "$", "VES": "Bs"}
    df_mostrar = pendientes_compras.copy()
    df_mostrar["saldo_pendiente"] = df_mostrar.apply(
        lambda r: f"{simbolo.get(r['moneda'], '')} {r['saldo_pendiente']:,.2f}", axis=1
    )
    st.dataframe(
        df_mostrar[["nombre", "moneda", "saldo_pendiente", "notas"]].rename(
            columns={
                "nombre": "Compra",
                "moneda": "Moneda",
                "saldo_pendiente": "Saldo pendiente",
                "notas": "Notas",
            }
        ),
        width="stretch",
        hide_index=True,
    )

# --- Alertas y calendario de cuotas programadas ---
st.subheader("Alertas de cuotas programadas", icon=":material/notifications_active:")
df_cuotas = queries.listar_cuotas_programadas(usuario_id)
df_pendientes = df_cuotas[df_cuotas["estado"] != "Pagado"] if not df_cuotas.empty else df_cuotas

if df_pendientes.empty:
    st.caption("No tienes cuotas programadas pendientes ni vencidas.")
else:
    vencidas = df_pendientes[df_pendientes["estado"] == "Vencido"].sort_values("fecha_pago")
    limite_proximas = date.today() + timedelta(days=7)
    proximas = df_pendientes[
        (df_pendientes["estado"] == "Pendiente")
        & (df_pendientes["fecha_pago"] <= limite_proximas)
    ].sort_values("fecha_pago")

    simbolo = {"USD": "$", "VES": "Bs"}
    for row in vencidas.itertuples():
        st.error(
            f"Vencida: {row.compra} · {simbolo.get(row.moneda, '')}{row.monto:,.2f} "
            f"{row.moneda} · venció el {row.fecha_pago:%d/%m/%Y}",
            icon=":material/error:",
        )
    for row in proximas.itertuples():
        dias_restantes = (row.fecha_pago - date.today()).days
        cuando = "hoy" if dias_restantes == 0 else f"en {dias_restantes} día{'s' if dias_restantes != 1 else ''}"
        st.warning(
            f"Próxima: {row.compra} · {simbolo.get(row.moneda, '')}{row.monto:,.2f} "
            f"{row.moneda} · vence el {row.fecha_pago:%d/%m/%Y} ({cuando})",
            icon=":material/schedule:",
        )
    if vencidas.empty and proximas.empty:
        st.caption("No tienes cuotas vencidas ni próximas a vencer en los próximos 7 días.")

st.subheader("Calendario de pagos", icon=":material/calendar_month:")
_meses_nombre = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
c1, c2 = st.columns(2)
with c1:
    mes_cal = st.selectbox(
        "Mes",
        options=list(range(1, 13)),
        format_func=lambda m: _meses_nombre[m - 1],
        index=date.today().month - 1,
        key="dash_cal_mes",
    )
with c2:
    anio_actual = date.today().year
    anio_cal = st.selectbox(
        "Año",
        options=list(range(anio_actual - 1, anio_actual + 3)),
        index=1,
        key="dash_cal_anio",
    )
render_calendario_cuotas(df_pendientes, anio_cal, mes_cal)
st.caption(
    "🔴 Cuota vencida · 🟠 Cuota pendiente con fecha de pago marcada. "
    "Gestiona tus compras y cuotas desde la página Compras programadas."
)

st.caption(
    "Usa las páginas del menú lateral para registrar movimientos, "
    "gestionar deudas/pagos y compras programadas, administrar usuarios, "
    "o cambiar tu contraseña."
)
