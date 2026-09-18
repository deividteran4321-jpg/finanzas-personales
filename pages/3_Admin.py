"""Cuenta propia (usuario/contraseña) y alta de nuevos usuarios.

Todos los usuarios tienen el mismo nivel de acceso - cualquiera puede crear
otros usuarios. Los datos financieros (movimientos, deudas, compras
programadas) son privados por usuario. No existe forma de eliminar un
usuario desde la app (a propósito, para que nadie borre por error los
datos de otra cuenta) - si hace falta, se hace directo en la base de datos.
"""
import streamlit as st

from core.auth import (
    cambiar_credenciales,
    crear_usuario,
    listar_usuarios,
    obtener_hash,
    verify_password,
)

st.title("Administración", icon=":material/admin_panel_settings:")

username_actual = st.session_state.get("username", "")

tab_cuenta, tab_usuarios = st.tabs(
    [":material/lock: Mi cuenta", ":material/group: Usuarios"]
)

# ---------------------------------------------------------------------------
# Mi cuenta
# ---------------------------------------------------------------------------
with tab_cuenta:
    with st.form("cambiar_credenciales"):
        st.write(f"Usuario actual: **{username_actual}**")
        password_actual = st.text_input("Contraseña actual", type="password")
        nuevo_username = st.text_input(
            "Nuevo usuario (déjalo igual si no quieres cambiarlo)",
            value=username_actual,
            help="Se guarda en minúsculas sin importar cómo lo escribas "
            "(el login no distingue mayúsculas/minúsculas).",
        )
        nuevo_password = st.text_input("Nueva contraseña", type="password")
        confirmar_password = st.text_input("Confirmar nueva contraseña", type="password")

        enviado = st.form_submit_button(
            "Guardar cambios", icon=":material/save:", type="primary"
        )

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
                    "tu nuevo usuario/contraseña.",
                    icon=":material/check_circle:",
                )

# ---------------------------------------------------------------------------
# Usuarios (crear / eliminar)
# ---------------------------------------------------------------------------
with tab_usuarios:
    st.caption(
        "Cada usuario tiene sus propios movimientos, deudas y compras "
        "programadas - son privados, no se comparten entre cuentas."
    )

    usuarios = listar_usuarios()
    st.dataframe(
        [{"Usuario": u["username"], "Nombre": u["nombre"]} for u in usuarios],
        width="stretch",
        hide_index=True,
    )

    with st.expander("Crear nuevo usuario", icon=":material/person_add:"):
        with st.form("nuevo_usuario", clear_on_submit=True):
            nuevo_user_username = st.text_input(
                "Usuario (para iniciar sesión)",
                help="Se guarda en minúsculas sin importar cómo lo escribas "
                "(el login no distingue mayúsculas/minúsculas).",
            )
            nuevo_user_nombre = st.text_input("Nombre a mostrar")
            nuevo_user_password = st.text_input("Contraseña", type="password")
            nuevo_user_confirmar = st.text_input("Confirmar contraseña", type="password")
            crear_enviado = st.form_submit_button(
                "Crear usuario", icon=":material/person_add:", type="primary"
            )
            if crear_enviado:
                if not nuevo_user_username.strip() or not nuevo_user_nombre.strip():
                    st.error("Usuario y nombre son obligatorios.")
                elif len(nuevo_user_password) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                elif nuevo_user_password != nuevo_user_confirmar:
                    st.error("La contraseña y su confirmación no coinciden.")
                else:
                    try:
                        crear_usuario(
                            nuevo_user_username.strip(),
                            nuevo_user_nombre.strip(),
                            nuevo_user_password,
                        )
                        st.toast(
                            f'Usuario "{nuevo_user_username}" creado.',
                            icon=":material/check_circle:",
                        )
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

    st.caption(
        "Por seguridad, ningún usuario puede eliminar a otro desde aquí "
        "(evita borrar por accidente los datos de alguien más)."
    )
