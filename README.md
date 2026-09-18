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
app.py                  Router: login + navegación (st.navigation/st.Page)
core/
  database.py           Modelos SQLAlchemy + conexión (Postgres o SQLite local)
  auth.py                Login, hashing bcrypt, cambio de credenciales
  queries.py             Agregaciones y CRUD (todo lo que consulta la BD)
  tasas.py               Tasas del día BCV/paralelo (dolarapi.com)
  calendario.py          Calendario HTML de cuotas programadas por pagar
pages/
  0_Dashboard.py            Panel principal (KPIs, tasas, compras, alertas)
  1_Movimientos.py          Registrar ingresos/egresos
  2_Deudas.py               Deudas, cuotas/pagos y sus estados
  3_Admin.py                Mi cuenta + crear usuarios
  4_Compras_Programadas.py  Planificar compras futuras (VES/USD) en cuotas
.streamlit/
  config.toml             Tema "Financial Dashboard" (nativo de Streamlit)
  secrets.toml.example    Plantilla de credenciales (copiar a secrets.toml)
static/
  world-map.svg           Mapa de fondo (ver licencia en "Notas de diseño")
```

`app.py` es el único archivo que Streamlit ejecuta directamente (el "main
file" en Streamlit Cloud sigue siendo `app.py` - no hace falta cambiar esa
configuración). Ahí se resuelven login, fondo y barra lateral una sola vez
por sesión, y luego `st.navigation()` arma el menú apuntando a los archivos
en `pages/`, con el título/ícono de cada uno declarado ahí mismo (por eso
esos archivos ya no llaman a `st.set_page_config()` por su cuenta).

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
       usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
       fecha         DATE NOT NULL,
       tipo          VARCHAR(10) NOT NULL CHECK (tipo IN ('ingreso', 'egreso')),
       categoria_id  INTEGER REFERENCES categorias(id),
       descripcion   VARCHAR(255) DEFAULT '',
       monto         NUMERIC(14, 2) NOT NULL,
       creado_en     TIMESTAMP DEFAULT NOW()
   );

   CREATE TABLE deudas (
       id               SERIAL PRIMARY KEY,
       usuario_id       INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
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

   CREATE TABLE compras_programadas (
       id               SERIAL PRIMARY KEY,
       usuario_id       INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
       nombre           VARCHAR(120) NOT NULL,
       moneda           VARCHAR(3) NOT NULL CHECK (moneda IN ('VES', 'USD')),
       monto_total      NUMERIC(14, 2) NOT NULL,
       saldo_pendiente  NUMERIC(14, 2) NOT NULL,
       notas            VARCHAR(255) DEFAULT '',
       creado_en        TIMESTAMP DEFAULT NOW()
   );

   CREATE TABLE cuotas_programadas (
       id               SERIAL PRIMARY KEY,
       compra_id        INTEGER NOT NULL REFERENCES compras_programadas(id) ON DELETE CASCADE,
       monto            NUMERIC(14, 2) NOT NULL,
       fecha_pago       DATE NOT NULL,
       fecha_pago_real  DATE,
       notas            VARCHAR(255) DEFAULT ''
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
- **Compras programadas** (VES o USD): igual que Deudas/Pagos, pero para
  compras futuras que aún no haces. El total programado se muestra por
  separado en cada moneda (USD y VES) - **nunca se suman entre sí**, porque
  son monedas distintas y esta app no hace conversión de tasas (eso vive en
  la otra app de finanzas del proyecto, con las tasas BCV/Binance).
- **Multiusuario con datos privados**: cualquier usuario puede crear otros
  usuarios desde Admin → Usuarios (no hay un rol "admin" especial, todos
  tienen el mismo acceso). Cada usuario ve solo sus propios movimientos,
  deudas y compras programadas - las categorías son la única tabla
  compartida entre todos. **No existe forma de eliminar un usuario desde la
  app** (a propósito, para que nadie borre por accidente los datos de otra
  cuenta); si hace falta, se hace a mano en la base de datos - al borrar la
  fila en `usuarios`, sus movimientos/deudas/compras se van detrás en
  cascada (`ON DELETE CASCADE`).
- **Usuarios siempre en minúsculas**: `streamlit-authenticator` normaliza a
  minúsculas el username que se escribe en el login antes de guardarlo en
  `session_state` (es case-insensitive por diseño de la librería). Por eso
  `crear_usuario()`, `cambiar_credenciales()` y toda búsqueda por username en
  `core/auth.py` fuerzan `.lower()` de forma consistente - si no, un usuario
  guardado con mayúsculas (ej. "Deivid") nunca hace match con lo que la
  librería busca ("deivid") y el login queda roto para esa cuenta. Si migras
  datos existentes con usernames en mayúsculas, corre una vez en el SQL
  Editor de Supabase: `UPDATE usuarios SET username = LOWER(username);`
- **Tasas del día (BCV/paralelo)**: el Dashboard consulta
  [dolarapi.com](https://dolarapi.com) (gratis, sin API key) para mostrar la
  tasa oficial BCV y la tasa de mercado paralelo (a la que en Venezuela se
  suele llamar indistintamente "paralelo" o "Binance", porque el P2P de
  Binance es su principal insumo). Se cachea 1 hora (`st.cache_data`) y si
  la API falla se muestra "No disponible" en vez de romper el Dashboard -
  son datos puramente informativos, ningún cálculo de la app depende de
  ellos.
- **Alertas y calendario de cuotas programadas**: el Dashboard lista las
  cuotas de Compras programadas vencidas o por vencer en los próximos 7
  días, y pinta un calendario del mes (`core/calendario.py`, HTML simple -
  Streamlit no trae un widget de calendario nativo) marcando en qué día hay
  que pagar qué. Vive en el Dashboard porque es donde el usuario ya ve el
  resto de sus alertas financieras; para crear/editar cuotas se sigue
  usando la página Compras programadas.
- **Fondo de mapa mundial**: puramente decorativo, vía `background-image`
  en `core/background.py` (no cambia el `background-color` del tema). El
  SVG (`static/world-map.svg`) es "Simple World Map" de Al MacDonald,
  editado por Fritz Lekschas, licencia CC BY-SA 3.0
  ([repo](https://github.com/flekschas/simple-world-map)).
