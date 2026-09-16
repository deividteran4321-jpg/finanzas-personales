# Finanzas Personales

Sistema de control financiero personal con login, dashboard interactivo,
registro de ingresos/egresos y módulo de deudas con estados de pago. Hecho
con Streamlit + SQLAlchemy, pensado para correr en **Streamlit Community
Cloud** con una base de datos **Postgres en Supabase** (gratis), para que
puedas modificarlo desde tu PC y revisarlo desde el teléfono con los mismos
datos.

> Este proyecto es independiente de la app de finanzas HTML/JS que ya existe
> en la carpeta raíz de `Balances/` - no la toca ni depende de ella.

## Estructura

```
app.py                  Dashboard principal (requiere login)
core/
  database.py           Modelos SQLAlchemy + conexión (Postgres o SQLite local)
  auth.py                Login, hashing bcrypt, cambio de credenciales
  queries.py             Agregaciones y CRUD (todo lo que consulta la BD)
pages/
  1_Movimientos.py       Registrar ingresos/egresos
  2_Deudas.py             Deudas, cuotas/pagos y sus estados
  3_Admin.py              Cambiar tu usuario/contraseña
.streamlit/
  config.toml             Tema oscuro
  secrets.toml.example    Plantilla de credenciales (copiar a secrets.toml)
```

## Cómo correrlo en local

```powershell
cd finanzas-personales
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```

Edita `.streamlit\secrets.toml` con al menos `ADMIN_USERNAME`,
`ADMIN_PASSWORD` y `AUTH_COOKIE_KEY` (puedes dejar `DATABASE_URL` sin
definir para probar primero contra un SQLite local en `data/finanzas.db`).

```powershell
.venv\Scripts\streamlit run app.py
```

La primera vez que arranca sin usuarios en la BD, crea automáticamente el
admin con `ADMIN_USERNAME`/`ADMIN_PASSWORD` de tus secrets. Después de tu
primer login, cambia la contraseña desde la página **Admin** - esos valores
de secrets ya no se vuelven a usar una vez que existe al menos un usuario.

## Configurar Supabase (base de datos real)

1. Crea una cuenta gratis en [supabase.com](https://supabase.com) y un
   proyecto nuevo.
2. En el **SQL Editor** del proyecto, ejecuta:

   ```sql
   CREATE TABLE usuarios (
       id            SERIAL PRIMARY KEY,
       username      VARCHAR(60)  UNIQUE NOT NULL,
       password_hash VARCHAR(255) NOT NULL,
       nombre        VARCHAR(120) NOT NULL,
       creado_en     TIMESTAMP DEFAULT NOW()
   );

   CREATE TABLE categorias (
       id        SERIAL PRIMARY KEY,
       nombre    VARCHAR(80) NOT NULL,
       tipo      VARCHAR(10) NOT NULL CHECK (tipo IN ('ingreso', 'egreso')),
       color     VARCHAR(7)  DEFAULT '#6366f1',
       UNIQUE (nombre, tipo)
   );

   CREATE TABLE movimientos (
       id            SERIAL PRIMARY KEY,
       fecha         DATE NOT NULL,
       tipo          VARCHAR(10) NOT NULL CHECK (tipo IN ('ingreso', 'egreso')),
       categoria_id  INTEGER REFERENCES categorias(id),
       descripcion   VARCHAR(255) DEFAULT '',
       monto         NUMERIC(14, 2) NOT NULL,
       creado_en     TIMESTAMP DEFAULT NOW()
   );

   CREATE TABLE deudas (
       id               SERIAL PRIMARY KEY,
       nombre           VARCHAR(120) NOT NULL,
       monto_total      NUMERIC(14, 2) NOT NULL,
       saldo_pendiente  NUMERIC(14, 2) NOT NULL,
       notas            VARCHAR(255) DEFAULT '',
       creado_en        TIMESTAMP DEFAULT NOW()
   );

   CREATE TABLE pagos (
       id                 SERIAL PRIMARY KEY,
       deuda_id           INTEGER NOT NULL REFERENCES deudas(id) ON DELETE CASCADE,
       monto              NUMERIC(14, 2) NOT NULL,
       fecha_vencimiento  DATE NOT NULL,
       fecha_pago         DATE,
       notas              VARCHAR(255) DEFAULT ''
   );
   ```

   (`init_db()` en `core/database.py` también las crea solo si no existen,
   así que este paso es opcional pero recomendado para tener control directo
   del esquema desde el principio.)

3. Ve a **Project Settings → Database → Connection string → URI**, copia esa
   cadena (reemplaza `[YOUR-PASSWORD]` por tu contraseña real) y pégala como
   `DATABASE_URL` en tus secrets.

## Desplegar en Streamlit Community Cloud

1. Crea un repo de GitHub **privado** (son tus datos financieros) solo para
   esta carpeta (`git init` aquí dentro, con el `.gitignore` ya incluido).
2. Súbelo a GitHub.
3. En [share.streamlit.io](https://share.streamlit.io), conecta el repo,
   selecciona `app.py` como archivo principal.
4. En **Settings → Secrets** de la app (no en el repo), pega el contenido de
   tu `secrets.toml` real (con el `DATABASE_URL` de Supabase).
5. Deploy. Abre la URL desde tu teléfono - Streamlit ya es responsivo, las
   columnas se apilan solas en pantallas angostas.

## Notas de diseño

- El **estado de un pago** (Pendiente/Vencido/Pagado) nunca se guarda en la
  base de datos - se calcula siempre a partir de `fecha_pago` y
  `fecha_vencimiento` en `core/queries.py`, para que nunca quede
  desincronizado.
- La sesión se recuerda automáticamente por 30 días vía cookie
  (`streamlit-authenticator`) - no hay que volver a loguearse cada vez que
  abres la app en el mismo navegador.
- Los filtros de Año/Mes/Categoría del dashboard actualizan los gráficos al
  instante (Streamlit re-ejecuta el script al cambiar cualquier selector).
