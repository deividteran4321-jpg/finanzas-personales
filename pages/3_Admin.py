"""Permite al admin cambiar su propio usuario y contraseña."""
import streamlit as st

from core.auth import cambiar_credenciales, obtener_hash, require_auth, verify_password
from core.database import init_db

st.set_page_config(page_title="Admin", page_icon="🔑", layout="wide")

init_db()
authenticator = require_auth()

with st.sidebar:
    st.markdown(f"### 👋 {st.session_state.get('name', '')}")
    authenticator.logout("Cerrar sesión", "sidebar")

st.title("🔑 Administrar mi cuenta")

username_actual = st.session_state.get("username", "")

with st.form("cambiar_credenciales"):
    st.write(f"Usuario actual: **{username_actual}**")
    password_actual = st.text_input("Contraseña actual", type="password")
    nuevo_username = st.text_input("Nuevo usuario (déjalo igual si no quieres cambiarlo)", value=username_actual)
    nuevo_password = st.text_input("Nueva contraseña", type="password")
    confirmar_password = st.text_input("Confirmar nueva contraseña", type="password")

    enviado = st.form_submit_button("Guardar cambios", type="primary")

    if enviado:
        hash_guardado = obtener_hash(username_actual)

        if not hash_guardado or not verify_password(password_actual, hash_guardado):
            st.error("La contraseña actual no es correcta.")
        elif not nuevo_username.strip():
            st.error("El usuario no puede estar vacío.")
        elif len(nuevo_password) < 6:
            st.error("La nueva contraseña debe tener al menos 6 caracteres.")
        elif nuevo_password != confirmar_password:
            st.error("La nueva contraseña y su confirmación no coinciden.")
        else:
            cambiar_credenciales(username_actual, nuevo_username.strip(), nuevo_password)
            st.success(
                "Credenciales actualizadas. Cierra sesión y vuelve a entrar con "
                "tu nuevo usuario/contraseña."
            )
