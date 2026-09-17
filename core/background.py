"""Fondo decorativo: mapa mundial en SVG, muy sutil, sin tocar el color de
fondo del tema. Se aplica como `background-image` sobre `.stApp` (el
contenedor raiz de Streamlit) - así se pinta encima del `background-color`
del tema sin reemplazarlo ni depender de trucos de z-index/stacking-context
con un `<div>` inyectado, que en Streamlit terminan quedando ocultos detrás
del propio fondo de `.stApp`.

Mapa: "Simple World Map" de Al MacDonald / editado por Fritz Lekschas,
licencia CC BY-SA 3.0 - https://github.com/flekschas/simple-world-map
"""
import base64
import re
from pathlib import Path

import streamlit as st

_SVG_PATH = Path(__file__).resolve().parent.parent / "static" / "world-map.svg"


@st.cache_data
def _load_map_svg_data_uri(color: str = "#94A3B8", opacity: float = 0.07) -> str:
    svg = _SVG_PATH.read_text(encoding="utf-8")
    # El SVG original no trae fill en los <path>; se lo damos al elemento
    # raiz para que todos lo hereden, ya con la opacidad baja incluida
    # (así el color de fondo del tema no se toca en absoluto).
    svg = re.sub(
        r"<svg ",
        f'<svg fill="{color}" fill-opacity="{opacity}" ',
        svg,
        count=1,
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def render_world_map_background() -> None:
    data_uri = _load_map_svg_data_uri()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("{data_uri}");
            background-repeat: no-repeat;
            background-position: center 20%;
            background-size: 140% auto;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
