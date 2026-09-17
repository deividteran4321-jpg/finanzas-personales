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
from sqlalchemy.exc import IntegrityError

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
        try:
            session.commit()
        except IntegrityError:
            # Streamlit a veces ejecuta el script dos veces casi en
            # paralelo al arrancar (primera carga); si otra ejecucion ya
            # sembro el admin en ese instante, no es un error real.
            session.rollback()


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


def get_current_user_id() -> Optional[int]:
    """Id del usuario logueado (según st.session_state["username"]).

    Todas las tablas de datos financieros (movimientos, deudas, compras
    programadas) se filtran por este id - cada usuario ve solo lo suyo.
    """
    username = st.session_state.get("username")
    if not username:
        return None
    with SessionLocal() as session:
        usuario = session.query(Usuario).filter_by(username=username).first()
        return usuario.id if usuario else None


def listar_usuarios() -> list:
    with SessionLocal() as session:
        usuarios = session.query(Usuario).order_by(Usuario.username).all()
        return [{"id": u.id, "username": u.username, "nombre": u.nombre} for u in usuarios]


def crear_usuario(username: str, nombre: str, password: str) -> None:
    with SessionLocal() as session:
        if session.query(Usuario).filter_by(username=username).first():
            raise ValueError(f'El usuario "{username}" ya existe.')
        session.add(
            Usuario(username=username, nombre=nombre, password_hash=hash_password(password))
        )
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise ValueError(f'El usuario "{username}" ya existe.') from exc


def require_auth() -> stauth.Authenticate:
    """Exige sesión iniciada antes de seguir. Debe llamarse al inicio de
    app.py Y de cada página en pages/, porque Streamlit permite navegar
    directo a la URL de una página sin pasar por app.py primero.

    Si ya hay cookie de sesión válida, streamlit-authenticator autentica
    solo sin pedir credenciales de nuevo. Si no, muestra el formulario de
    login y detiene la ejecución de la página actual.
    """
    authenticator = get_authenticator()
    login_fields = {
        "Form name": "Iniciar sesión",
        "Username": "Usuario",
        "Password": "Contraseña",
        "Login": "Ingresar",
    }
    try:
        authenticator.login(fields=login_fields)
    except stauth.utilities.exceptions.LoginError:
        # La cookie del navegador apunta a un usuario que ya no existe (se
        # borro/renombro la BD, o el usuario cambio su propio username).
        # Se borra esa cookie invalida en vez de tumbar la app con un
        # traceback - pero el borrado del lado del navegador para este
        # componente es asincrono y no siempre se refleja con solo recargar,
        # así que se pide limpiar cookies del sitio como salida segura.
        authenticator.cookie_controller.delete_cookie()
        st.session_state.clear()
        st.warning(
            "Tu sesión guardada ya no es válida (la cuenta cambió o ya no "
            "existe). Borra las cookies de este sitio, o ábrelo en una "
            "ventana de incógnito, y vuelve a iniciar sesión.",
            icon=":material/warning:",
        )
        st.stop()

    auth_status = st.session_state.get("authentication_status")
    if auth_status is False:
        st.error("Usuario o contraseña incorrectos")
        st.stop()
    elif auth_status is None:
        st.info("Ingresa tus credenciales para continuar")
        st.stop()

    return authenticator
