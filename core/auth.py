"""Autenticación: login, hashing de contraseñas y gestión de credenciales.

Se usa streamlit-authenticator SOLO para el mecanismo de login + cookie de
sesión ("recordarme" automático por N días) - probado y seguro. El cambio
de usuario/contraseña propio (página Admin) se maneja a mano contra la
tabla `usuarios`, para no depender de los métodos internos de esa librería
(que cambian entre versiones) y tener control total sobre qué se persiste.
"""
import os
from typing import Optional

import bcrypt
import streamlit as st
import streamlit_authenticator as stauth

from core.database import SessionLocal, Usuario


def _get_secret(name: str, default=None):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _seed_admin_if_empty() -> None:
    with SessionLocal() as session:
        if session.query(Usuario).count() > 0:
            return
        username = _get_secret("ADMIN_USERNAME", "admin")
        password = _get_secret("ADMIN_PASSWORD")
        if not password:
            st.error(
                "No hay usuarios creados y falta ADMIN_PASSWORD en "
                "secrets.toml (o como variable de entorno) para crear el "
                "admin inicial. Revisa .streamlit/secrets.toml.example."
            )
            st.stop()
        session.add(
            Usuario(
                username=username,
                password_hash=hash_password(password),
                nombre="Administrador",
            )
        )
        session.commit()


def _load_credentials() -> dict:
    _seed_admin_if_empty()
    with SessionLocal() as session:
        usuarios = session.query(Usuario).all()
        return {
            "usernames": {
                u.username: {"name": u.nombre, "password": u.password_hash}
                for u in usuarios
            }
        }


def get_authenticator() -> stauth.Authenticate:
    credentials = _load_credentials()
    cookie_key = _get_secret(
        "AUTH_COOKIE_KEY", "cambia-esta-clave-en-secrets-toml"
    )
    return stauth.Authenticate(
        credentials,
        cookie_name="finanzas_auth",
        cookie_key=cookie_key,
        cookie_expiry_days=30,
    )


def cambiar_credenciales(
    username_actual: str, nuevo_username: str, nuevo_password: str
) -> None:
    """Actualiza usuario/contraseña en la BD. Llamar solo tras verificar la
    contraseña actual con verify_password()."""
    with SessionLocal() as session:
        usuario = session.query(Usuario).filter_by(username=username_actual).first()
        if usuario is None:
            raise ValueError("Usuario no encontrado")
        usuario.username = nuevo_username
        usuario.password_hash = hash_password(nuevo_password)
        session.commit()


def obtener_hash(username: str) -> Optional[str]:
    with SessionLocal() as session:
        usuario = session.query(Usuario).filter_by(username=username).first()
        return usuario.password_hash if usuario else None


def require_auth() -> stauth.Authenticate:
    """Exige sesión iniciada antes de seguir. Debe llamarse al inicio de
    app.py Y de cada página en pages/, porque Streamlit permite navegar
    directo a la URL de una página sin pasar por app.py primero.

    Si ya hay cookie de sesión válida, streamlit-authenticator autentica
    solo sin pedir credenciales de nuevo. Si no, muestra el formulario de
    login y detiene la ejecución de la página actual.
    """
    authenticator = get_authenticator()
    authenticator.login(
        fields={
            "Form name": "Iniciar sesión",
            "Username": "Usuario",
            "Password": "Contraseña",
            "Login": "Ingresar",
        }
    )

    auth_status = st.session_state.get("authentication_status")
    if auth_status is False:
        st.error("Usuario o contraseña incorrectos")
        st.stop()
    elif auth_status is None:
        st.info("Ingresa tus credenciales para continuar")
        st.stop()

    return authenticator
