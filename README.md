# 🏆 BFB Sports

## Website Online:
https://bfbdeportes.onrender.com (Render Free Plan)

<p align="center">
  <strong>A modern sports platform featuring live scores, match predictions, statistics, and the latest sports news.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black"/>
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white"/>
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white"/>
  <img src="https://img.shields.io/badge/PostgreSQL-336791?style=for-the-badge&logo=postgresql&logoColor=white"/>
</p>

---

## 📖 About

**BFB Sports** is a modern sports web application that allows users to follow their favorite competitions in real time. The platform offers live scores, match predictions, statistics, news, and personalized features for sports fans.

---

## ✨ Features

- ⚽ Real-time **Live Scores**
- 🏀 Follow **NBA**, **MLB**, and **Soccer**
- 📅 Match schedules
- 📊 Team and match statistics (career and current-season stats for NBA; MLB batting/pitching; top-scorer stats for soccer)
- 🎯 User prediction system, with a BFB points history and win/loss notifications
- ❤️ Favorite teams and competitions
- 👤 Secure user authentication
- 🌎 Multi-language support
- 📰 Latest sports news
- 🛠️ Admin panel for manual data cleanup
- 📲 Discreet "Add to Home Screen" install prompt

---

## 🛠️ Tech Stack

### Backend

- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- JWT Authentication

### Frontend

- HTML5
- CSS3
- JavaScript

---

## 🔐 Security

The project follows modern security best practices:

- JWT Authentication
- Password hashing with bcrypt
- HttpOnly Cookies
- Data validation using Pydantic
- SQL Injection protection through SQLAlchemy
- Secure CORS configuration

---

## 🏅 Supported Sports

- ⚾ Major League Baseball (MLB)
- 🏀 National Basketball Association (NBA)
- ⚽ Soccer

---

## 🚀 Project Goal

The goal of **BFB Sports** is to provide sports fans with a fast, modern, and engaging platform where they can stay updated with live scores, follow their favorite teams, and compete with friends through match predictions.

---

## 📈 Project Status

🚧 **Actively under development**

New features and improvements are continuously being added.

---

## ❤️ Built With

- FastAPI
- PostgreSQL
- SQLAlchemy
- Pydantic
- JavaScript

---

<p align="center">
Made by Juan Reyes
</p>

---

# 📚 Documentación técnica (setup, despliegue, arquitectura)

> Esta sección se mantiene actualizada a medida que se agregan funciones nuevas al proyecto.

## Estado actual del proyecto

| Módulo | Estado |
|---|---|
| Backend (FastAPI + PostgreSQL) | ✅ Completo y funcional |
| Autenticación (registro/login, cookie httpOnly) | ✅ Completo |
| Sistema de puntos BFB (predicciones, gana o pierde puntos según probabilidad) | ✅ Completo |
| Historial de predicciones + aviso de ganaste/perdiste | ✅ Completo |
| Favoritos (equipo/jugador/liga) | ✅ Completo |
| **MLB (Béisbol)** — posiciones, jugadores hoy, en vivo, resultados, estadísticas reales de bateo/pitcheo | ✅ Funcional de extremo a extremo (MLB Stats API, gratuita, sin key) |
| **NBA (Basketball)** — equipos vigentes (se filtran franquicias históricas), posiciones reales calculadas de los partidos, roster de jugadores activos (sin retirados, vía `/players/active`), estadísticas reales de carrera y temporada actual | ✅ Funcional (balldontlie para equipos/roster/partidos + stats.nba.com para estadísticas — ver sección de arquitectura) |
| **Fútbol** (EPL, La Liga, Serie A, Bundesliga, Ligue 1, Champions League) — equipos, posiciones, partidos, goleadores con goles/asistencias reales | ✅ Funcional (football-data.org) |
| Estadísticas detalladas de jugador de fútbol (tarjetas, minutos, calificación — vía API-Football) | ✅ Conectado — solo falta que `API_FOOTBALL_KEY` esté configurada en las variables de entorno de Render |
| Panel de administración (borrar/restaurar equipos incorrectos a mano) | ✅ Completo — 5 taps en el footer, solo funcional para usuarios en `ADMIN_USERNAMES` |
| Botón de "instalar app" (agregar a pantalla principal) | ✅ Completo |
| Selector de idioma (ES/EN) | ✅ Completo |

Todo el código se revisa (`py_compile` en Python, `node --check` en JS, validación de JSON, balance de tags HTML) antes de cada entrega.

## Por qué esta arquitectura

- **MLB Stats API** (oficial, gratuita, sin key): fuente de béisbol, incluye estadísticas de bateo/pitcheo en vivo.
- **balldontlie.io**: equipos, roster y partidos de NBA. Su plan gratuito **no incluye estadísticas de jugador** (eso exige un plan de pago ALL-STAR/GOAT) — devuelve además TODO el historial de franquicias de la NBA (equipos ya desaparecidos), por lo que el código filtra por la conferencia asignada para quedarse solo con los 30 equipos vigentes.
- **stats.nba.com**: estadísticas reales de jugador de NBA (carrera y temporada actual). Es una API **no oficial** (no publicada ni soportada por la NBA, sin sistema de llaves) — se usa porque es la única fuente gratuita real que existe para esto; puede cambiar o bloquear solicitudes sin aviso. Se consulta solo en vivo, al buscar un jugador específico, nunca en la sincronización periódica.
- **football-data.org**: equipos, posiciones y partidos de fútbol. Su plan gratuito solo da estadísticas de jugador vía el listado de goleadores (goles/asistencias de los destacados de cada liga), no la plantilla completa.
- **API-Football (api-sports.io)**: estadísticas detalladas de jugador de fútbol (tarjetas, minutos, calificación), en vivo al buscar un jugador — complementa a football-data.org, que en su plan gratuito solo da goles/asistencias de los goleadores destacados. Plan gratuito: 100 peticiones/día, sin tarjeta de crédito. Se consulta solo bajo demanda (nunca en la sincronización periódica) para no agotar ese límite. Requiere `API_FOOTBALL_KEY` en las variables de entorno.
- **ESPN RSS**: noticias reales con imagen, gratis, respetando sus términos.

## Seguridad implementada

- Contraseñas con **bcrypt** (versión fijada a `4.3.0` en `requirements.txt` — versiones más nuevas rompen una auto-prueba interna de `passlib`).
- Sesión con **JWT en cookie httpOnly + SameSite=Lax**.
- **CORS restringido** a orígenes explícitos.
- Todo acceso a datos vía **ORM de SQLAlchemy** (sin SQL concatenado).
- **Rate limiting** en `/auth/login` y `/auth/register`.
- Mensajes de error genéricos en login (no revela si el usuario existe).
- Validación de entradas con Pydantic (contraseña entre 8 y 72 caracteres — límite real de bcrypt).
- Panel de administración protegido por sesión + lista de usernames en `ADMIN_USERNAMES` (no por una segunda contraseña).
- Secretos solo en `.env`, nunca en el código ni en el repositorio.

## Cómo ejecutarlo localmente

```bash
createdb bfb_deportes
cd backend
python -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"   # para SECRET_KEY

uvicorn app.main:app --reload
```

Abre **http://localhost:8000**. La primera vez que arranca, sincroniza automáticamente MLB/NBA/fútbol/noticias, y se repite cada 5 minutos en segundo plano (en su propio hilo, para no bloquear el servidor mientras sincroniza).

### Variables de entorno relevantes (`.env`)
- `BALLDONTLIE_API_KEY` — activa NBA.
- `FOOTBALL_DATA_API_KEY` — activa fútbol/Mundial.
- `API_FOOTBALL_KEY` — (pendiente de conectar) activaría estadísticas completas de jugadores de fútbol.
- `ADMIN_USERNAMES` — tu(s) username(s) con acceso al panel de administración, separados por coma.

## Despliegue

Actualmente en **Render** (plan gratis) — `bfbdeportes.onrender.com`. El repo incluye `render.yaml` en la raíz para que Render detecte la configuración solo.

**Importante del plan gratis de Render:** el servicio se "duerme" tras ~15 minutos sin tráfico (tarda unos segundos en despertar con la siguiente visita), y la sincronización de 5 minutos solo corre mientras el servicio está despierto. No es un error del proyecto, es el comportamiento normal de ese plan.

También se puede desplegar en **Railway** (Root Directory = `backend`, variables de entorno equivalentes).

## Estructura del proyecto

```
bfb-deportes/
└── backend/
    ├── app/
    │   ├── core/          # config, seguridad, base de datos, rate limit, migraciones ligeras
    │   ├── models/        # tablas SQLAlchemy (sport, prediction, user, favorite)
    │   ├── schemas/       # validación Pydantic
    │   ├── api/routes/    # auth, leagues, games, news, favorites, predictions, stats, admin
    │   ├── services/      # integraciones externas + sincronización
    │   │   ├── mlb_service.py, balldontlie_service.py, football_data_service.py
    │   │   ├── nba_stats_service.py      # estadísticas reales de NBA (stats.nba.com)
    │   │   ├── probability_service.py    # probabilidad de victoria + puntos BFB
    │   │   └── sync_service.py           # orquesta toda la sincronización periódica
    │   └── main.py
    ├── frontend/
    │   ├── index.html
    │   ├── css/styles.css
    │   ├── js/ (api, i18n, auth, predictions, stats, main, admin, pwa-install)
    │   └── i18n/ (es.json, en.json)
    ├── requirements.txt
    ├── render.yaml
    └── .env.example
```

## Próximos pasos sugeridos

1. Añadir Alembic para migraciones versionadas (ahora se usan migraciones ligeras + `create_all`).
2. Reemplazar el rate limiter en memoria por uno con Redis si se despliega con varios workers.
