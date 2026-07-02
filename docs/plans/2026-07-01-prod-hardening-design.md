# Producción — Hardening de seguridad (diseño)

**Fecha:** 2026-07-01
**Estado:** diseño aprobado (brainstorming), pendiente de plan de implementación.

## Objetivo

Cerrar los dos "TODO de seguridad antes de desplegar" documentados en CLAUDE.md, como
prerrequisito de código para cualquier despliegue. Slice **solo backend**, autónoma, sin
dependencias de infra:

1. Exigir `JWT_SECRET` desde el entorno en producción (rechazar el default y secretos cortos).
2. Validar los dominios de `tipo_cedula` / `regimen` en los schemas de cliente.

Esta slice es el bloque **A** (hardening). El bloque **B** (despliegue + DB robusta: hosting,
Postgres administrado, HTTPS, migraciones en prod, CORS/headers, servir el build) es una fase
aparte que se planea cuando se elija el destino de infra.

## Alcance

### En alcance (backend)
- `app/config.py`: setting `env` + enforcement de `jwt_secret` gated por `env == "production"`.
- `app/schemas/cliente.py`: validadores de dominio para `tipo_cedula` y `regimen`.
- `CLAUDE.md`: marcar los dos TODO como hechos + nota de variables de producción.

### Fuera de alcance (bloque B / futuro)
- CORS explícito, headers de seguridad, servir el frontend build.
- Migraciones Alembic en prod, hosting, Postgres administrado, backups, HTTPS.
- Cambios de frontend (los Selects ya ofrecen solo valores válidos).

## Config — `ENV` + enforcement de `JWT_SECRET`

`app/config.py` hoy: `jwt_secret: str = "dev-secret-change-me"` (default inseguro), sin
enforcement. La suite de tests y el dev dependen de ese default.

Diseño:
- Agregar `env: str = "dev"` (lee la variable de entorno `ENV`; default `"dev"`).
- Agregar un `model_validator(mode="after")` en `Settings` que, **solo cuando `env == "production"`**,
  rechaza:
  - `jwt_secret == "dev-secret-change-me"` (el default), y
  - `len(jwt_secret) < 32`.
  Si falla, `raise ValueError(...)` con mensaje claro (aborta el arranque de la app).
- En `env` distinto de `"production"` (dev/test), no exige nada → la suite sigue verde con el default.
- Constante para el default (p.ej. `_DEFAULT_JWT_SECRET = "dev-secret-change-me"`) para no repetir el literal.

Efecto: en producción, arrancar sin `JWT_SECRET` propio (≥32 chars) y `ENV=production` falla
de inmediato, en vez de correr con un secreto conocido.

## Schemas — dominios de cliente

`app/schemas/cliente.py` `ClienteCreate` hoy no valida `tipo_cedula` / `regimen` (strings libres).

Diseño:
- `field_validator("tipo_cedula")`: normaliza (`strip`) y exige pertenecer a
  `{"fisica", "juridica", "dimex", "nite"}`; si no, `ValueError` → `422`.
- `field_validator("regimen")`: idem con `{"tradicional", "simplificado"}`.
- Definir los conjuntos como constantes a nivel de módulo (`TIPOS_CEDULA_VALID`, `REGIMENES_VALID`)
  para reusarlas en los validadores y tenerlas explícitas.

El frontend ya restringe con Selects a esos valores, así que no hay cambio de UI; el backend
pasa a garantizarlo (defensa en el borde de la API).

## Docs

- En `CLAUDE.md`, sección "TODO de seguridad antes de desplegar": marcar ambos ítems como hechos
  (o moverlos a "Hecho"), y anotar que producción requiere `ENV=production` + `JWT_SECRET` (≥32 chars).

## Errores

- Config: en producción con secreto inválido → `ValueError` al instanciar `Settings` (falla el arranque, comportamiento deseado).
- Cliente: `tipo_cedula`/`regimen` fuera de dominio → `422` (Pydantic).

## Testing (pytest, TDD)

- **Config** (`backend/tests/test_config.py`, nuevo):
  - `Settings(env="production", jwt_secret="dev-secret-change-me")` → levanta `ValueError`.
  - `Settings(env="production", jwt_secret="x"*10)` (corto) → levanta.
  - `Settings(env="production", jwt_secret="x"*40)` → OK (no levanta).
  - `Settings(env="dev", jwt_secret="dev-secret-change-me")` → OK (no exige).
- **Cliente** (extender `backend/tests/test_clientes.py`):
  - `POST /api/clientes` con `tipo_cedula="foo"` → `422`.
  - con `regimen="foo"` → `422`.
  - con `tipo_cedula="dimex"`, `regimen="simplificado"` → `201` (valores válidos nuevos).
  - Los tests existentes (juridica/tradicional) siguen en `201`.
- La suite completa del backend sigue verde.

## Notas

- Fiel al repo: `Decimal`/validaciones en schemas, TDD, un commit por unidad.
- Verificar que ningún test o fixture use un `tipo_cedula`/`regimen` fuera de los dominios
  nuevos (romperían al validar). El `_cliente` de conftest usa `juridica`/`tradicional` (válidos).
