# Hardening de producción — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar los dos TODO de seguridad pre-deploy: exigir `JWT_SECRET` propio en producción y validar los dominios de `tipo_cedula`/`regimen`.

**Architecture:** Solo backend. `config.py` gana un `env` y un `model_validator` que exige un `jwt_secret` seguro cuando `env == "production"` (en dev/test no exige, la suite no se rompe). `schemas/cliente.py` gana validadores de dominio (422). Docs actualizados.

**Tech Stack:** FastAPI, pydantic v2 / pydantic-settings, pytest. Sin cambios de frontend.

---

## Convenciones

- Spec: `docs/plans/2026-07-01-prod-hardening-design.md`.
- Worktree: `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\.claude\worktrees\reverent-lederberg-08f91d`. Rama `claude/prod-hardening` (desde main).
- **Backend tests:** `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q`. Requiere PostgreSQL :5433 para los tests de endpoint (los de config son puros, no necesitan DB). Si Postgres está caído para los de endpoint, reportar BLOCKED.
- Dominios (confirmados): `tipo_cedula ∈ {fisica, juridica, dimex, nite}`, `regimen ∈ {tradicional, simplificado}`. Todos los fixtures existentes usan `juridica`/`tradicional` (válidos) — no rompen.
- Commits: uno por tarea, español.

## Estructura de archivos

```
backend/app/config.py            # + env, + model_validator de JWT_SECRET en prod
backend/tests/test_config.py     # nuevo: tests del enforcement (puros)
backend/app/schemas/cliente.py   # + validadores de dominio tipo_cedula/regimen
backend/tests/test_clientes.py   # + tests 422/201 de dominios
CLAUDE.md                        # marcar TODOs de seguridad como hechos + nota ENV/JWT_SECRET
```

---

### Task 1: Config — `ENV` + enforcement de `JWT_SECRET`

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config.py` (nuevo)

- [ ] **Step 1: Escribir el test que falla** (`backend/tests/test_config.py`)

```python
import pytest
from pydantic import ValidationError
from app.config import Settings


def test_prod_rechaza_secreto_default():
    with pytest.raises(ValidationError):
        Settings(env="production", jwt_secret="dev-secret-change-me")


def test_prod_rechaza_secreto_corto():
    with pytest.raises(ValidationError):
        Settings(env="production", jwt_secret="x" * 10)


def test_prod_acepta_secreto_valido():
    s = Settings(env="production", jwt_secret="x" * 40)
    assert s.env == "production"
    assert len(s.jwt_secret) >= 32


def test_dev_permite_default():
    s = Settings(env="dev", jwt_secret="dev-secret-change-me")
    assert s.jwt_secret == "dev-secret-change-me"
```

Nota: `Settings(...)` con kwargs los toma con prioridad sobre `.env`/entorno. Un `model_validator(mode="after")` que hace `raise ValueError` se propaga como `ValidationError` de pydantic. Si en este entorno se propagara como `ValueError` crudo, cambiar el `pytest.raises(ValidationError)` a `pytest.raises((ValidationError, ValueError))` (ajuste de test, no de implementación).

- [ ] **Step 2: Correr y verificar que falla**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_config.py -q`
Expected: FAIL — hoy no hay enforcement (los dos primeros no levantan).

- [ ] **Step 3: Implementar** — reemplazar `backend/app/config.py` por:

```python
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    env: str = "dev"  # "production" activa el enforcement de secretos
    database_url: str = "postgresql+psycopg://sistemaxml:devpassword@localhost:5433/sistemaxml"
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_expire_minutes: int = 480  # 8 h; acortar cuando se implemente refresh tokens.
    jwt_algorithm: str = "HS256"

    @model_validator(mode="after")
    def _exigir_secreto_en_prod(self):
        if self.env == "production" and (
            self.jwt_secret == _DEFAULT_JWT_SECRET or len(self.jwt_secret) < 32
        ):
            raise ValueError(
                "En producción (ENV=production), JWT_SECRET debe ser propio y de al menos 32 caracteres."
            )
        return self


settings = Settings()
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_config.py -q`
Expected: PASS (4 tests). Correr también la suite completa para confirmar que `settings = Settings()` (env dev por default) sigue instanciando sin error y nada se rompe.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(backend): exigir JWT_SECRET propio en produccion (ENV=production)"
```

---

### Task 2: Schemas — dominios de `tipo_cedula`/`regimen`

**Files:**
- Modify: `backend/app/schemas/cliente.py`
- Test: `backend/tests/test_clientes.py`

- [ ] **Step 1: Escribir los tests que fallan** — agregar a `backend/tests/test_clientes.py` (reusar los helpers de auth que ya existen en ese archivo para el POST; si se llaman distinto, usar los del archivo)

```python
def test_crear_cliente_tipo_cedula_invalido_422(client, db_session):
    token = _token(client, db_session)
    payload = {"cedula": "3101777777", "nombre": "X S.A.", "tipo_cedula": "foo", "regimen": "tradicional"}
    assert client.post("/api/clientes", json=payload, headers=_auth(token)).status_code == 422


def test_crear_cliente_regimen_invalido_422(client, db_session):
    token = _token(client, db_session)
    payload = {"cedula": "3101777778", "nombre": "Y S.A.", "tipo_cedula": "juridica", "regimen": "foo"}
    assert client.post("/api/clientes", json=payload, headers=_auth(token)).status_code == 422


def test_crear_cliente_dimex_simplificado_201(client, db_session):
    token = _token(client, db_session)
    payload = {"cedula": "155812345678", "nombre": "Z", "tipo_cedula": "dimex", "regimen": "simplificado"}
    r = client.post("/api/clientes", json=payload, headers=_auth(token))
    assert r.status_code == 201
    assert r.json()["tipo_cedula"] == "dimex"
    assert r.json()["regimen"] == "simplificado"
```

Nota: leer el encabezado de `test_clientes.py` para reusar sus helpers de token/auth (`_token`/`_auth` o como se llamen). No inventar helpers nuevos.

- [ ] **Step 2: Correr y verificar que fallan**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_clientes.py -q`
Expected: FAIL — hoy no hay validación de dominio (los 422 dan 201).

- [ ] **Step 3: Implementar** — reemplazar `backend/app/schemas/cliente.py` por:

```python
from pydantic import BaseModel, ConfigDict, field_validator

TIPOS_CEDULA_VALID = {"fisica", "juridica", "dimex", "nite"}
REGIMENES_VALID = {"tradicional", "simplificado"}


class ClienteCreate(BaseModel):
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str = "tradicional"

    @field_validator("cedula", "nombre")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("tipo_cedula")
    @classmethod
    def _tipo_cedula(cls, v: str) -> str:
        v = v.strip()
        if v not in TIPOS_CEDULA_VALID:
            raise ValueError(f"tipo_cedula inválido: {v}")
        return v

    @field_validator("regimen")
    @classmethod
    def _regimen(cls, v: str) -> str:
        v = v.strip()
        if v not in REGIMENES_VALID:
            raise ValueError(f"regimen inválido: {v}")
        return v


class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str
```

- [ ] **Step 4: Correr y verificar que pasa**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest tests/test_clientes.py -q`
Expected: PASS (los 3 nuevos + los existentes, que usan juridica/tradicional).

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/cliente.py backend/tests/test_clientes.py
git commit -m "feat(backend): validar dominios de tipo_cedula y regimen (422)"
```

---

### Task 3: Docs + verificación final

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Actualizar CLAUDE.md**

En `CLAUDE.md`, sección **"## TODO de seguridad antes de desplegar"**, reemplazar los dos ítems pendientes por su forma "hecha" y una nota de producción. Es decir, cambiar:

```markdown
## TODO de seguridad antes de desplegar
- Exigir `JWT_SECRET` desde el entorno (rechazar el default `dev-secret-change-me`, mínimo 32 chars).
- Validar los dominios de `tipo_cedula` / `regimen` en los schemas.
```

por:

```markdown
## Seguridad
- **Hecho:** `JWT_SECRET` exigido en producción (`ENV=production` rechaza el default y <32 chars, en `config.py`).
- **Hecho:** dominios de `tipo_cedula` (`fisica|juridica|dimex|nite`) y `regimen` (`tradicional|simplificado`) validados en `schemas/cliente.py`.
- **Producción:** setear `ENV=production` y `JWT_SECRET` (≥32 chars) en el entorno. (Pendiente fase de deploy: CORS/headers, servir el build, migraciones en prod, Postgres administrado, HTTPS, backups.)
```

(Si el encabezado o el texto exacto difieren, ubicar los dos ítems por su contenido y reemplazarlos manteniendo el estilo del archivo.)

- [ ] **Step 2: Suite completa del backend**

Run: `cd backend && PYTHONPATH="$(pwd)" "/c/Users/Usuario/Desktop/Sistemas/sistema-xml-web/backend/.venv/Scripts/python.exe" -m pytest -q`
Expected: toda la suite verde (incluye `test_config.py` nuevo + los de clientes).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: marcar hechos los TODO de seguridad pre-deploy + nota de produccion"
```

---

## Self-Review (cobertura del spec)

- `env` + enforcement de `JWT_SECRET` gated por producción → Task 1. ✔
- No rompe dev/test (default permitido con `env=dev`) → Task 1 (test `test_dev_permite_default` + suite). ✔
- Dominios `tipo_cedula`/`regimen` validados (422) → Task 2. ✔
- Valores nuevos (`dimex`/`simplificado`) aceptados → Task 2 (test 201). ✔
- Fixtures existentes (juridica/tradicional) siguen válidos → verificado (grep previo). ✔
- Docs actualizados → Task 3. ✔
- Sin cambios de frontend (los Selects ya restringen) → por diseño. ✔

Riesgos: la forma exacta en que pydantic-settings propaga el error del `model_validator` (ValidationError vs ValueError) — el test lo contempla (ajustar el `raises` si hace falta, sin tocar la implementación).
