# BFB Deportes

**Béisbol · Fútbol · Basketball — todo en un mismo lugar**

Plataforma deportiva full-stack: HTML/CSS/JS (frontend) + FastAPI + PostgreSQL (backend), con datos reales desde APIs deportivas.

---

## 1. Estado actual del proyecto

| Módulo | Estado |
|---|---|
| Backend (FastAPI + PostgreSQL) | ✅ Completo y funcional |
| Autenticación (registro/login, cookie httpOnly) | ✅ Completo |
| Sistema de puntos BFB (predicciones) | ✅ Completo |
| Favoritos (equipo/jugador/liga) | ✅ Completo |
| **MLB (Béisbol)** — posiciones, jugadores hoy, en vivo, resultados con detalle de pitchers, noticias | ✅ **Funcional de extremo a extremo**, con datos reales de la MLB Stats API (gratuita, sin API key) |
| Fútbol / Basketball / Mundial 2026 | 🟡 Backend y frontend ya construidos y listos; requieren que tú configures `BALLDONTLIE_API_KEY` (ver sección 4) |
| Estadísticas por equipo/jugador | 🟡 Versión básica (búsqueda por ID); pendiente búsqueda por nombre |
| Selector de idioma (ES/EN) | ✅ Completo |

Todo el código fue revisado (`py_compile` en Python, `node --check` en JS, validación de JSON, y cruce de IDs HTML↔JS) antes de esta entrega, sin encontrar errores.

---

## 2. Por qué esta arquitectura

- **MLB Stats API** (oficial, gratuita, sin key): fuente de béisbol. Incluye pitcher ganador/perdedor/salvamento, algo que una API genérica no siempre da con este nivel de detalle gratis.
- **balldontlie.io**: basketball (NBA, WNBA, NCAAB). Su nivel gratuito **no** cubre la mayoría de ligas de fútbol ni el Mundial (da 401 Unauthorized si se intenta) — por eso el fútbol usa un proveedor distinto.
- **football-data.org**: fútbol (EPL, La Liga, Serie A, Bundesliga, Ligue 1, Champions League) y el Mundial. Gratis para siempre según su propio creador, sin tarjeta de crédito, e incluye el logo real de cada equipo directo en la respuesta.
- **ESPN RSS**: noticias reales con imagen, gratis, respetando sus términos (se enlaza siempre al artículo completo y se atribuye la fuente).

Esta es la opción que consideré más equilibrada entre costo, calidad de datos y mantenimiento. Si prefieres otro proveedor (ej. API-Football de pago para más detalle de fútbol), el código está aislado en `app/services/` y se puede sustituir sin tocar el resto del sistema.

---

## 3. Seguridad implementada

- Contraseñas con **bcrypt** (nunca texto plano).
- Sesión con **JWT en cookie httpOnly + SameSite=Lax** (no accesible desde JS → mitiga robo por XSS; SameSite mitiga CSRF).
- **CORS restringido** a orígenes explícitos (nunca `*`).
- Todo acceso a datos vía **ORM de SQLAlchemy** (sin SQL concatenado → sin inyección SQL).
- **Rate limiting** en `/auth/login` y `/auth/register` contra fuerza bruta.
- Mensajes de error genéricos en login (no se revela si el usuario existe o no).
- Validación de entradas con Pydantic (usuario, contraseña mínimo 8 caracteres, email válido, idioma restringido a es/en).
- Secretos (`SECRET_KEY`, `BALLDONTLIE_API_KEY`, credenciales de BD) solo en `.env`, nunca en el código ni en el repositorio.

---

## 4. Cómo ejecutarlo

### Requisitos
- Python 3.11+
- PostgreSQL 14+
- Una API key gratuita de [balldontlie.io](https://balldontlie.io) (opcional, solo si quieres activar fútbol/basketball/Mundial)

### Pasos

```bash
# 1. Crear la base de datos
createdb bfb_deportes

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edita .env: DATABASE_URL, SECRET_KEY (genera una con el comando de abajo)
python -c "import secrets; print(secrets.token_hex(32))"

# 3. Levantar el servidor (crea las tablas automáticamente al iniciar)
uvicorn app.main:app --reload
```

Abre **http://localhost:8000** — el mismo servidor sirve el frontend (carpeta `backend/frontend/`) y la API (`/api/v1/...`).

La primera vez que arranca, el servidor sincroniza automáticamente equipos, posiciones y calendario de la MLB, y noticias. La sincronización se repite cada 5 minutos en segundo plano.

### Activar basketball
1. Crea una cuenta gratuita en https://balldontlie.io
2. Copia tu API key a `BALLDONTLIE_API_KEY` en `.env`

### Activar fútbol y Mundial
1. Crea una cuenta gratuita en https://www.football-data.org/client/register (sin tarjeta)
2. Copia tu token a `FOOTBALL_DATA_API_KEY` en `.env`
3. Reinicia el servidor

> **Nota:** las posiciones del Mundial no se sincronizan a propósito (es una competencia por grupos, no una tabla de liga tradicional) — solo se muestran sus partidos.

---

## 5. Despliegue en Railway

Railway provee PostgreSQL como servicio y te entrega la conexión mediante variable de entorno, que es justo lo que este backend espera (`DATABASE_URL`).

### Paso a paso

1. **Sube el proyecto a GitHub** (con el `.gitignore` ya incluido, así que tu `.env` real nunca se sube).

2. **Crea el proyecto en Railway** → "New Project" → "Deploy from GitHub repo" → selecciona tu repositorio.

3. **Agrega PostgreSQL**: dentro del proyecto, "New" → "Database" → "Add PostgreSQL". Railway crea la base de datos y expone su propia variable `DATABASE_URL` internamente.

4. **Configura el servicio del backend** (⚠️ este paso es obligatorio, no opcional — si lo saltas, Railway lanza el error `Railpack could not determine how to build the app` porque Railway no adivina en qué carpeta está el proyecto a construir):
   - En la pestaña *Settings* del servicio → sección *Source* → define **Root Directory** = `backend`
   - Railway detecta el `Procfile` y el `railway.json` (ambos ya incluidos dentro de `backend/`) automáticamente y usa `uvicorn app.main:app --host 0.0.0.0 --port $PORT` para arrancar.
   - Si ya creaste el servicio sin este ajuste y te salió ese error: solo entra a *Settings* → *Source*, pon el Root Directory, y Railway vuelve a desplegar solo.

5. **Variables de entorno del servicio backend** (pestaña *Variables*):
   ```
   ENV=production
   DATABASE_URL=${{Postgres.DATABASE_URL}}
   SECRET_KEY=<genera una con: python -c "import secrets; print(secrets.token_hex(32))">
   BALLDONTLIE_API_KEY=<tu clave real>
   CORS_ORIGINS=["https://TU-APP.up.railway.app"]
   ```
   - `${{Postgres.DATABASE_URL}}` es una referencia a la variable del servicio de Postgres que creaste en el paso 3 (Railway te la sugiere al escribir `$`).
   - `CORS_ORIGINS` debe ser un **arreglo JSON válido** (con corchetes y comillas exactamente así), o el backend no arrancará. Actualízalo con tu dominio real de Railway una vez que Railway te lo asigne (puedes desplegar primero, ver la URL, y luego actualizar esta variable y redesplegar).
   - `ENV=production` es importante: activa la bandera `Secure` en la cookie de sesión, correcta porque Railway sirve todo por HTTPS.

6. **Deploy**. En el primer arranque, la app crea las tablas automáticamente y empieza a sincronizar MLB (y fútbol/basketball si configuraste la API key). Puedes verlo en los *Logs* del servicio.

7. **Verifica**: abre la URL pública de Railway. Deberías ver el sitio y, en `/api/health`, un `{"status":"ok",...}`.

### Notas de seguridad para producción
- Nunca reutilices el `SECRET_KEY` de ejemplo ni la API key que ya compartiste en este chat — genera/rota claves nuevas para el entorno real.
- Railway gestiona el volumen de PostgreSQL automáticamente; no necesitas configurar backups para probar, pero revisa la política de backups de tu plan antes de usar datos reales de usuarios.
- Si más adelante escalas a varios workers/instancias, reemplaza el rate limiter en memoria (`app/core/rate_limit.py`) por uno con Redis, como ya se anota en ese archivo.

---

## 5.1. Despliegue en Render + Neon (alternativa a Railway)

Este proyecto también se puede desplegar en **Render** (hosting del backend) + **Neon** (PostgreSQL). El repo ya incluye `render.yaml` en la raíz, así que Render detecta la configuración automáticamente sin que tengas que llenar formularios a mano.

### Paso a paso

1. **Crea la base de datos en Neon**: entra a https://neon.tech → crea un proyecto → copia el **connection string** que te dan (ya viene en formato `postgresql://usuario:password@ep-xxxx.región.aws.neon.tech/dbname?sslmode=require` — cópialo tal cual, con el `?sslmode=require` incluido, Neon lo exige).

2. **Crea el servicio en Render**:
   - Ve a https://dashboard.render.com → **New** → **Blueprint**
   - Conecta tu repositorio de GitHub
   - Render detecta `render.yaml` solo y te muestra el servicio `bfb-deportes` listo para crear (ya configurado con Root Directory=backend, comando de build y de arranque — no necesitas tocar esos campos)

3. **Variables de entorno**: en la sección *Environment* del servicio, pega:
   ```
   DATABASE_URL=<el connection string de Neon del paso 1>
   SECRET_KEY=<genera una con: python -c "import secrets; print(secrets.token_hex(32))">
   BALLDONTLIE_API_KEY=<tu key de balldontlie, para basketball>
   FOOTBALL_DATA_API_KEY=<tu token de football-data.org, para fútbol/Mundial>
   CORS_ORIGINS=["https://TU-APP.onrender.com"]
   ```
   `ENV=production` y `PYTHON_VERSION=3.12.8` ya vienen incluidos en `render.yaml`, no hace falta agregarlos a mano. Igual que en Railway, `CORS_ORIGINS` debe ser un arreglo JSON válido (con corchetes y comillas), y puedes actualizarlo con tu dominio real de Render una vez que te lo asignen.

   ⚠️ **Si tu servicio ya existía antes de este cambio** (creado antes de que `render.yaml` incluyera `PYTHON_VERSION`), Render puede no releer automáticamente ese campo nuevo. Verifícalo a mano: *Environment* → agrega `PYTHON_VERSION` = `3.12.8` directamente, y vuelve a desplegar (*Manual Deploy* → *Deploy latest commit*). Esto corrige un error real que vimos (`psycopg2` incompatible con Python 3.14, que Render usa por defecto si no se fija la versión).

4. **Deploy**. Render instala dependencias, crea las tablas automáticamente en tu base de Neon al arrancar, y empieza a sincronizar.

### Diferencia importante con Railway: el plan gratis de Render se "duerme"

En el **plan gratis**, Render apaga el servicio tras ~15 minutos sin tráfico. Esto significa:
- El sitio tarda unos segundos más en responder la primera vez que alguien lo visita después de estar dormido (arranca de nuevo).
- La sincronización automática cada 5 minutos (MLB, basketball, fútbol, noticias) **solo corre mientras el servicio está despierto** — si nadie visita el sitio por un rato, el ciclo de sincronización se pausa hasta que alguien vuelva a entrar.
- Esto no es un error del proyecto, es el comportamiento normal del plan gratis de Render. Si esto llega a ser un problema, la solución es subir a un plan pago (Starter en adelante), que no se duerme.

### Nota sobre `.python-version`
Se agregó una copia de este archivo tanto en la raíz del repositorio como dentro de `backend/`, porque la documentación de Render no deja 100% claro si lo busca en la raíz real del repo o en el Root Directory del servicio — así queda cubierto de cualquier forma, sin arriesgar el mismo tipo de error de versión de Python que tuvimos al desplegar en Railway.

---

## 6. Próximos pasos sugeridos

1. Conectar de verdad fútbol/basketball con tu API key y probar los endpoints reales.
2. Añadir Alembic para migraciones (ahora mismo las tablas se crean con `create_all`, adecuado para desarrollo).
3. Búsqueda de jugador/equipo por nombre (autocompletado) en vez de por ID.
4. Reemplazar el rate limiter en memoria por uno con Redis si despliegas con varios workers.
5. Servir el frontend por separado (Nginx/CDN) en producción, en vez de `StaticFiles` de FastAPI.

---

## 7. Estructura del proyecto

```
bfb-deportes/
└── backend/
    ├── app/
    │   ├── core/          # config, seguridad, base de datos, rate limit
    │   ├── models/        # tablas SQLAlchemy
    │   ├── schemas/       # validación Pydantic
    │   ├── api/routes/    # endpoints (auth, leagues, games, news, favorites, predictions, stats)
    │   ├── services/      # integraciones externas + sincronización
    │   └── main.py
    ├── frontend/          # HTML/CSS/JS — vive aquí (no al lado de backend/) para que
    │   ├── index.html     # Railway lo incluya al usar Root Directory=backend
    │   ├── css/styles.css
    │   ├── js/ (api, i18n, auth, main, stats)
    │   └── i18n/ (es.json, en.json)
    ├── requirements.txt
    ├── railway.json
    ├── Procfile
    └── .env.example
```

> **Nota de este cambio:** originalmente `frontend/` estaba al lado de `backend/` (como hermanos). Se movió dentro de `backend/` porque, en Railway, el servicio está configurado con **Root Directory = backend** — solo lo que está dentro de esa carpeta llega al build. Si `frontend/` se queda afuera, Railway lo ignora por completo (esto fue justo lo que causó el "Not Found" al abrir el sitio). El código de `main.py` ya está actualizado para buscarlo en la nueva ubicación.

Cualquier cambio futuro debe respetar esta estructura y estos nombres, salvo que se avise explícitamente.
