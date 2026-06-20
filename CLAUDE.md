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
Hecho: **1A** backend (auth + CRUD clientes), **1B-1** parser, **1B-2** tarifa+transforms (fix de "No Sujeto" sin "Combustibles", verificado sobre venta agropecuaria real), **1B-3** ingesta (`POST /api/ingesta`, idempotente, maneja XML inválido→422 y omite MensajeHacienda), **1B-4** resumen (`GET /api/resumen`). **31 pruebas verdes.**

**Reconciliación contra datos reales (Agrofinca mayo 2026):** las **VENTAS cuadran exacto al colón** (bienes 1% 34.749.173,64 / 13% 1.824.800 / no sujeto 699.750 / total 37.273.723,64 / IVA 584.715,74) — valida el motor completo, incluido el No Sujeto agropecuario que era el bug original. Las **COMPRAS**: el total crudo coincide exacto (39.352.345,45), pero el desglose por categoría difiere porque el sistema viejo aplica la capa de **CLASIFICACIÓN** (excluye No Deducibles; reclasifica Combustibles código 08/13% como No Sujeto vía sub-clasificación) que el motor nuevo aún no tiene.

**Próximo:** **clasificación** (reglas por proveedor/CABYS → Compras/Gastos/Bienes de Capital/No Deducibles + sub-clasificación Combustibles→No Sujeto; es lo que falta para que las compras reconcilien) → **D-150** (débito/crédito/saldo sobre el resumen) → subida manual ZIP → **1C** agente local → **1D** frontend → **1E** reportes Excel/PDF.

## TODO de seguridad antes de desplegar
- Exigir `JWT_SECRET` desde el entorno (rechazar el default `dev-secret-change-me`, mínimo 32 chars).
- Validar los dominios de `tipo_cedula` / `regimen` en los schemas.
