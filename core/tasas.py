"""Tasas de cambio del día (BCV oficial y paralelo/Binance), vía dolarapi.com.

Fuente: https://ve.dolarapi.com - gratis, sin API key, mantenido activamente.
La tasa "paralelo" es la referencia de mercado paralelo (lo que en Venezuela
se suele llamar indistintamente "paralelo" o "Binance", ya que el P2P de
Binance es su principal insumo) - dolarapi.com no expone un monitor
"binance" separado y nombrado como tal.

Son datos puramente informativos para el Dashboard: si la API falla (sin
internet, caída del servicio, cambio de formato) se devuelve None y el
Dashboard muestra "No disponible" en vez de romperse - ninguna otra parte
de la app depende de estos valores.
"""
from typing import Optional

import requests
import streamlit as st

_URL = "https://ve.dolarapi.com/v1/dolares/{fuente}"


@st.cache_data(ttl=3600, show_spinner=False)
def _obtener_tasa(fuente: str) -> Optional[dict]:
    try:
        resp = requests.get(_URL.format(fuente=fuente), timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return {
            "promedio": float(data["promedio"]),
            "fecha": data.get("fechaActualizacion"),
        }
    except Exception:
        return None


def tasa_bcv() -> Optional[dict]:
    return _obtener_tasa("oficial")


def tasa_paralelo() -> Optional[dict]:
    return _obtener_tasa("paralelo")
