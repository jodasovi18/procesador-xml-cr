# Sistema XML — Procesador de Comprobantes Electrónicos CR (rebuild)

Reconstrucción web del "Sistema XML CR": procesa comprobantes electrónicos (XML de Hacienda Costa Rica) para una firma contable, clasifica gastos/ventas y genera la declaración de IVA (D-150). Single-tenant (una firma). Reemplaza un monolito Flask viejo en `C:\Users\Usuario\Desktop\Sistemas\Sistema XML` (ese sigue siendo producción y la fuente del port — NO borrarlo).

## Stack
- **Backend:** FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL. Auth JWT (bcrypt directo).
- **Frontend (futuro):** React + TypeScript, color de marca teal.
- **Ingesta:** agente local + subida manual. El **período** sale de la fecha del XML (no de la carpeta); el **rol** (compra/venta) de la cédula emisor/receptor.

## Estructura
- `backend/app/` — `main.py`, `config.py`, `db.py`, `models/`, `schemas/`, `auth/`, `routers/`, `motor/`.
- `backend/app/motor/` — el motor tributario: `parser.py` (XML→Pydantic, valores crudos), `tarifa.py` (tratamiento IVA efectivo por línea; código 10/11 → "No Sujeto" SIN "Combustibles"), `transforms.py` (signo NC, USD→CRC, Bienes/Servicios), `ingesta.py` (pipeline + persistencia idempotente por clave), `resumen.py` (agregación por categoría).
- `docs/plans/` — planes de implementación por fase (leer el de la fase en curso antes de codear).
- `frontend/`, `agent/` — futuros.

## Entorno de desarrollo (Windows — CRÍTICO, no obvio)
- **PostgreSQL 17 local**, puerto **5433**, rol `sistemaxml` / clave `devpassword`, base `sistemaxml` (con CREATEDB). Las pruebas crean/borran `sistemaxml_test`. psql en `C:\Program Files\PostgreSQL\17\bin\psql.exe`. **No hay Docker.**
- **Python 3.11**: usar SIEMPRE el venv `backend\.venv\Scripts\python.exe`. El comando `python` pelado es un stub roto de la Microsoft Store (sale 9009) — **nunca usarlo**. (Anaconda base es 3.9, muy vieja.)
- **pip** necesita `--trusted-host pypi.org --trusted-host files.pythonhosted.org` (la red bloquea el certificado de PyPI). **winget** necesita `--source winget`.
- `passlib 1.7.4` es incompatible con `bcrypt 5.x` → se usa `bcrypt` directo para el hashing.

## Comandos
- Pruebas: `cd backend && .venv\Scripts\python.exe -m pytest -q`
- Migración: `.venv\Scripts\alembic.exe revision --autogenerate -m "..."` luego `.venv\Scripts\alembic.exe upgrade head`
- Servidor: `.venv\Scripts\uvicorn app.main:app --reload` → http://localhost:8000/docs
- GitHub: remoto `origin` = https://github.com/jodasovi18/procesador-xml-cr (rama `main`).

## Convenciones
- **TDD estricto** (test que falla → confirmar que falla → implementar → confirmar que pasa → commit). Un commit por unidad.
- **Dinero siempre `Decimal` / `Numeric`** — es una app tributaria, la precisión decimal es la razón de usar Postgres.
- Planes en `docs/plans/` antes de implementar.
- **Corregir los bugs que se encuentren sin preguntar primero** (preferencia del usuario), siempre verificando con pruebas reales.

## Estado (fases de la Fase 1B)
Hecho: **1A** backend (auth + CRUD clientes), **1B-1** parser, **1B-2** tarifa+transforms (fix de "No Sujeto" sin "Combustibles", verificado sobre venta agropecuaria real), **1B-3** ingesta (`POST /api/ingesta`, idempotente, maneja XML inválido→422 y omite MensajeHacienda), **1B-4** resumen (`GET /api/resumen`), **1B-5** clasificación (tabla `reglas_clasificacion` + engine de lookup por prioridad en `motor/clasificacion.py` + `build_resumen` clasificación-aware + `build_resumen_clasificacion` + `POST`/`GET /api/reglas` + `GET /api/resumen/clasificacion`), **1B-6** D-150 (`motor/d150.py`: `build_d150` débito/crédito/liquidación + `d150_ovi` doble presentación Decimal preciso + entero OVI-Tribu; tiquetes/No Deducibles/No Sujeto fuera del crédito; tabla `entradas_manuales` con `rol` para ventas y compras manuales —incl. subastas— mezcladas en el D-150; `GET /api/d150` + `POST`/`GET`/`DELETE /api/entradas-manuales`), **subida masiva** (`POST /api/ingesta/lote`: ZIP y/o múltiples XML, expansión de ZIP con topes anti-zip-bomb, éxito parcial con savepoint por archivo, reporte por archivo `nuevo/actualizado/omitido/error`; en `motor/ingesta_lote.py`), **1C-1** agente local CLI (`agent/sxml_agent/`: escaneo recursivo de `.xml` + dedup por hash de contenido + estado local JSON + login JWT + subida por tandas a `/api/ingesta/lote` con éxito parcial y re-login en 401; CLI `python -m sxml_agent --config agent.toml`; standalone, solo httpx + stdlib), **1C-2** watcher continuo (polling: `watcher.vigilar` corre `ejecutar` cada `intervalo` con resiliencia por pasada —una pasada que falla se loguea y sigue—; CLI `--watch`/`--intervalo`). **75 pruebas backend + 27 del agente, verdes.**

**Reconciliación contra datos reales (Agrofinca mayo 2026):** las **VENTAS cuadran exacto al colón** (bienes 1% 34.749.173,64 / 13% 1.824.800 / no sujeto 699.750 / total 37.273.723,64 / IVA 584.715,74) — valida el motor completo, incluido el No Sujeto agropecuario que era el bug original. Las **COMPRAS**: el total crudo coincide exacto (39.352.345,45), pero el desglose por categoría difiere porque el sistema viejo aplica la capa de **CLASIFICACIÓN** (excluye No Deducibles; reclasifica Combustibles código 08/13% como No Sujeto vía sub-clasificación). **1B-5 agrega esta capa** (clasificación al vuelo desde `reglas_clasificacion`; No Deducibles segregado; Combustibles→No Sujeto con IVA 0 sin importar la tarifa, según la intención documentada — el `build_resumen` viejo solo lo hacía a 0%). Falta la reconciliación completa de compras: requiere el `clasificaciones.json` real del contador, que **no está en esta máquina** (las carpetas de Agrofinca sí existen en OneDrive `OFICINA/CONTAS/IVA/...`, pero sin las reglas). 1B-5 se validó con golden tests controlados sobre el fixture real `fe_almacen_leon.xml`.

**Próximo:** reconciliación completa de compras + D-150 contra el oracle real (Agrofinca/Solis Feb 2026 en `run_d150_oracle.py`) cuando estén las reglas/manuales reales → **1C-3** empaquetado `.exe`/Tarea Programada + endurecer credenciales (keyring/token de agente) → **1D** frontend (incl. CRUD completo de reglas + auto-preclasificación por CABYS + edición de entradas manuales, diferidos) → **1E** reportes Excel/PDF. Diferidos del D-150: **prorrata** de crédito por uso mixto (hoy crédito pleno, fiel al sistema viejo), entradas manuales en la vista de clasificación.

## TODO de seguridad antes de desplegar
- Exigir `JWT_SECRET` desde el entorno (rechazar el default `dev-secret-change-me`, mínimo 32 chars).
- Validar los dominios de `tipo_cedula` / `regimen` en los schemas.
