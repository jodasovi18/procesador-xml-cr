# Agente local 1C-3a: token de agente — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar la clave en texto plano del agente por un token de agente emitido por el backend (largo, revocable, acotado a la ingesta): tabla `agent_tokens`, `get_actor` que acepta JWT o token en las rutas de ingesta, endpoints admin para emitir/listar/revocar, y el agente usando el token (sin login).

**Architecture:** Backend (FastAPI/SQLAlchemy): modelo `AgentToken` (guarda `sha256` del token), dep `get_actor` (JWT→Usuario o token→AgentToken, solo ingesta), endpoints `/api/agent-tokens` (admin). Agente (standalone): `config.token` opcional; `run` usa el token y omite el login.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, pytest (backend); httpx + stdlib (agente). Postgres local 5433.

> **Diseño:** `docs/plans/2026-06-22-agente-token-design.md`.

---

## Contexto y entorno (CRÍTICO)

- **Backend tests** (desde `backend/` del worktree): `PYTHONPATH`=worktree `backend/`, intérprete `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe`, `... -m pytest -q`. Migraciones con `.venv\Scripts\alembic.exe`. Nunca `python` pelado.
- **Agent tests** (desde la raíz del worktree): `PYTHONPATH`=worktree `agent/`, mismo intérprete, `... -m pytest agent/tests -q`.
- Suites actuales: **backend 75 verdes**, **agente 27 verdes**.
- Reutiliza: `auth/deps.py` (`get_current_user`, `oauth2_scheme`); `auth/security.py` (`hash_password`); `models/usuario.py` (`es_admin`); `routers/ingesta.py` (endpoints con `get_current_user`); fixture `backend/tests/fixtures/fe_almacen_leon.xml`. Agente: `config.py`, `run.py`, `cliente_api.py` (`ApiClient.subir_lote(token, rutas)`).

## File Structure

Backend:
- Create: `backend/app/models/agent_token.py`; Modify: `backend/app/models/__init__.py`; Create (autogen): migración.
- Create: `backend/app/auth/tokens.py` (`generar_token`, `hash_token`).
- Modify: `backend/app/auth/deps.py` (`get_actor`, `requiere_admin`).
- Modify: `backend/app/routers/ingesta.py` (ingesta usa `get_actor`).
- Create: `backend/app/schemas/agent_token.py`, `backend/app/routers/agent_tokens.py`; Modify: `backend/app/main.py`.
- Test: `backend/tests/test_agent_token.py`, `backend/tests/test_agent_tokens_endpoint.py`.

Agente:
- Modify: `agent/sxml_agent/config.py`, `agent/sxml_agent/run.py`, `agent/agent.example.toml`.
- Test: `agent/tests/test_config.py` (agregar), `agent/tests/test_run.py` (agregar).

---

## Tarea 1: Modelo `AgentToken` + migración

**Files:**
- Create: `backend/app/models/agent_token.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_agent_token.py`

- [ ] **Step 1: Test que falla** `backend/tests/test_agent_token.py`

```python
from sqlalchemy import select
from app.models.agent_token import AgentToken

def test_persistir_agent_token(db_session):
    db_session.add(AgentToken(token_hash="a" * 64, label="PC-contador"))
    db_session.commit()
    t = db_session.scalar(select(AgentToken))
    assert t.token_hash == "a" * 64
    assert t.label == "PC-contador"
    assert t.created_at is not None
```

- [ ] **Step 2: Correr, confirmar FALLA**

Run (desde `backend/`): `... -m pytest tests/test_agent_token.py -q` → FAIL `ModuleNotFoundError: No module named 'app.models.agent_token'`.

- [ ] **Step 3: Crear `backend/app/models/agent_token.py`**

```python
from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class AgentToken(Base):
    __tablename__ = "agent_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
```

- [ ] **Step 4: Registrar** en `backend/app/models/__init__.py` (al final)

```python
from app.models.agent_token import AgentToken  # noqa: F401
```

- [ ] **Step 5: Correr, confirmar PASA**

Run: `... -m pytest tests/test_agent_token.py -q` → PASS (1 passed).

- [ ] **Step 6: Migración** (desde `backend/`)

Run: `.venv\Scripts\alembic.exe revision --autogenerate -m "crear tabla agent_tokens"`; revisar (solo `create_table("agent_tokens", ...)` con índice único en `token_hash`; sin cambios espurios); `.venv\Scripts\alembic.exe upgrade head`. (Si la BD de dev no conecta: reportar BLOCKED, no fabricar la migración a mano.)

- [ ] **Step 7: Suite + commit**

Run: `... -m pytest -q` → 76 passed.
```bash
git add backend && git commit -m "feat(token-agente): modelo AgentToken + migracion"
```

---

## Tarea 2: `auth/tokens` + `get_actor` + ingesta acepta token

**Files:**
- Create: `backend/app/auth/tokens.py`
- Modify: `backend/app/auth/deps.py`
- Modify: `backend/app/routers/ingesta.py`
- Test: `backend/tests/test_agent_token.py` (agregar)

- [ ] **Step 1: Agregar tests que fallan** en `backend/tests/test_agent_token.py`

```python
from pathlib import Path
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.auth.security import hash_password
from app.auth.tokens import generar_token, hash_token

FIXT = Path(__file__).parent / "fixtures"

def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c

def _files():
    return [("archivos", ("fe.xml", (FIXT / "fe_almacen_leon.xml").read_bytes(), "application/xml"))]

def test_tokens_helpers():
    assert len(generar_token()) >= 32
    assert generar_token() != generar_token()
    assert hash_token("abc") == hash_token("abc")
    assert len(hash_token("abc")) == 64

def test_ingesta_lote_acepta_agent_token(client, db_session):
    db_session.add(AgentToken(token_hash=hash_token("MITOKEN"), label="x")); db_session.commit()
    _cliente(db_session)
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": "Bearer MITOKEN"})
    assert r.status_code == 200
    assert r.json()["nuevos"] == 1

def test_ingesta_lote_bearer_invalido_401(client):
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": "Bearer basura"})
    assert r.status_code == 401

def test_ingesta_lote_token_revocado_401(client, db_session):
    at = AgentToken(token_hash=hash_token("REVOK"), label="x")
    db_session.add(at); db_session.commit()
    db_session.delete(at); db_session.commit()   # revocado
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": "Bearer REVOK"})
    assert r.status_code == 401
```

- [ ] **Step 2: Correr, confirmar FALLA**

Run: `... -m pytest tests/test_agent_token.py -q` → FAIL (`No module named 'app.auth.tokens'`; y la ingesta con token da 401 hasta cambiarla).

- [ ] **Step 3: Crear `backend/app/auth/tokens.py`**

```python
"""Generación y hashing de tokens de agente."""
import hashlib
import secrets


def generar_token() -> str:
    """Token aleatorio url-safe (~43 chars, 256 bits de entropía)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """sha256 hex del token (lo que se guarda en la BD)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Modificar `backend/app/auth/deps.py`** — agregar imports y dos dependencias

Agregar a los imports:
```python
from sqlalchemy import select
from app.models.agent_token import AgentToken
from app.auth.tokens import hash_token
```
Agregar al final del archivo:
```python
def get_actor(token: str = Depends(oauth2_scheme),
              db: Session = Depends(get_db)) -> "Usuario | AgentToken":
    """Acepta un JWT de usuario o un token de agente. Usar solo en rutas de ingesta."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        if sub is not None:
            usuario = db.get(Usuario, int(sub))
            if usuario is not None:
                return usuario
    except (JWTError, ValueError):
        pass
    at = db.scalar(select(AgentToken).where(AgentToken.token_hash == hash_token(token)))
    if at is not None:
        return at
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Credenciales inválidas",
                        headers={"WWW-Authenticate": "Bearer"})


def requiere_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    if not usuario.es_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere admin")
    return usuario
```

- [ ] **Step 5: Modificar `backend/app/routers/ingesta.py`** — ingesta usa `get_actor`

Cambiar el import `from app.auth.deps import get_current_user` por `from app.auth.deps import get_actor`. Quitar el import `from app.models.usuario import Usuario` (queda sin uso). En AMBOS endpoints (`ingesta` y `ingesta_lote`), cambiar el parámetro `_: Usuario = Depends(get_current_user)` por `_=Depends(get_actor)`. (El resto del archivo igual.)

- [ ] **Step 6: Correr, confirmar PASA**

Run: `... -m pytest tests/test_agent_token.py -q` → PASS (4 passed).
Run la ingesta existente (no romper JWT): `... -m pytest tests/test_ingesta.py tests/test_ingesta_lote.py -q` → PASS.
Suite completa: `... -m pytest -q` → 80 passed.

- [ ] **Step 7: Commit**

```bash
git add backend && git commit -m "feat(token-agente): tokens helpers + get_actor (ingesta acepta JWT o token)"
```

---

## Tarea 3: Endpoints `/api/agent-tokens` (admin)

**Files:**
- Create: `backend/app/schemas/agent_token.py`
- Create: `backend/app/routers/agent_tokens.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent_tokens_endpoint.py`

- [ ] **Step 1: Test que falla** `backend/tests/test_agent_tokens_endpoint.py`

```python
from pathlib import Path
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.auth.security import hash_password

FIXT = Path(__file__).parent / "fixtures"

def _login(client, db_session, nombre, es_admin):
    db_session.add(Usuario(nombre=nombre, password_hash=hash_password("clave12345"), es_admin=es_admin))
    db_session.commit()
    return client.post("/auth/login", data={"username": nombre, "password": "clave12345"}).json()["access_token"]

def _auth(t):
    return {"Authorization": f"Bearer {t}"}

def _cliente(db):
    c = Cliente(cedula="3102858282", nombre="Agrofinca", tipo_cedula="juridica", regimen="tradicional")
    db.add(c); db.commit(); db.refresh(c)
    return c

def _files():
    return [("archivos", ("fe.xml", (FIXT / "fe_almacen_leon.xml").read_bytes(), "application/xml"))]

def test_crear_y_usar_token(client, db_session):
    adm = _login(client, db_session, "adm", True)
    r = client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(adm))
    assert r.status_code == 201
    plano = r.json()["token"]
    assert r.json()["label"] == "PC"
    _cliente(db_session)
    ri = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": f"Bearer {plano}"})
    assert ri.status_code == 200

def test_listar_no_expone_token(client, db_session):
    adm = _login(client, db_session, "adm", True)
    client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(adm))
    lst = client.get("/api/agent-tokens", headers=_auth(adm))
    assert lst.status_code == 200 and len(lst.json()) == 1
    assert "token" not in lst.json()[0]
    assert "token_hash" not in lst.json()[0]

def test_revocar_token(client, db_session):
    adm = _login(client, db_session, "adm", True)
    c = client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(adm))
    plano, tid = c.json()["token"], c.json()["id"]
    assert client.delete(f"/api/agent-tokens/{tid}", headers=_auth(adm)).status_code == 204
    r = client.post("/api/ingesta/lote", files=_files(), headers={"Authorization": f"Bearer {plano}"})
    assert r.status_code == 401   # revocado

def test_crear_no_admin_403(client, db_session):
    user = _login(client, db_session, "user", False)
    assert client.post("/api/agent-tokens", json={"label": "PC"}, headers=_auth(user)).status_code == 403

def test_agent_tokens_sin_token_401(client):
    assert client.get("/api/agent-tokens").status_code == 401
```

- [ ] **Step 2: Correr, confirmar FALLA**

Run: `... -m pytest tests/test_agent_tokens_endpoint.py -q` → FAIL (404 en `/api/agent-tokens`).

- [ ] **Step 3: Crear `backend/app/schemas/agent_token.py`**

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class AgentTokenCreate(BaseModel):
    label: str

    @field_validator("label")
    @classmethod
    def _label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("label requerido")
        return v


class AgentTokenCreated(BaseModel):
    id: int
    label: str
    token: str   # texto plano, devuelto una sola vez


class AgentTokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    created_at: datetime
```

- [ ] **Step 4: Crear `backend/app/routers/agent_tokens.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import requiere_admin
from app.models.usuario import Usuario
from app.models.agent_token import AgentToken
from app.auth.tokens import generar_token, hash_token
from app.schemas.agent_token import AgentTokenCreate, AgentTokenCreated, AgentTokenOut

router = APIRouter(prefix="/api/agent-tokens", tags=["agent-tokens"])

@router.post("", response_model=AgentTokenCreated, status_code=status.HTTP_201_CREATED)
def crear(data: AgentTokenCreate, db: Session = Depends(get_db),
          _: Usuario = Depends(requiere_admin)):
    token = generar_token()
    at = AgentToken(token_hash=hash_token(token), label=data.label)
    db.add(at)
    db.commit()
    db.refresh(at)
    return AgentTokenCreated(id=at.id, label=at.label, token=token)

@router.get("", response_model=list[AgentTokenOut])
def listar(db: Session = Depends(get_db), _: Usuario = Depends(requiere_admin)):
    return list(db.scalars(select(AgentToken).order_by(AgentToken.id)))

@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revocar(token_id: int, db: Session = Depends(get_db),
            _: Usuario = Depends(requiere_admin)):
    at = db.get(AgentToken, token_id)
    if at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no existe")
    db.delete(at)
    db.commit()
```

- [ ] **Step 5: Incluir router** en `backend/app/main.py`

Import junto a los demás: `from app.routers.agent_tokens import router as agent_tokens_router`
Inclusión junto a los demás: `app.include_router(agent_tokens_router)`

- [ ] **Step 6: Correr, confirmar PASA**

Run: `... -m pytest tests/test_agent_tokens_endpoint.py -q` → PASS (5 passed).
Suite completa: `... -m pytest -q` → 85 passed.

- [ ] **Step 7: Commit**

```bash
git add backend && git commit -m "feat(token-agente): endpoints /api/agent-tokens (admin: crear/listar/revocar)"
```

---

## Tarea 4: Agente usa el token (config + run)

**Files:**
- Modify: `agent/sxml_agent/config.py`
- Modify: `agent/sxml_agent/run.py`
- Modify: `agent/agent.example.toml`
- Test: `agent/tests/test_config.py` (agregar), `agent/tests/test_run.py` (agregar)

- [ ] **Step 1: Tests que fallan**

Agregar a `agent/tests/test_config.py` (tiene `import pytest` y `cargar_config`):
```python
def test_cargar_config_token(tmp_path):
    f = tmp_path / "agent.toml"
    f.write_text('backend_url="http://x"\ntoken="TOK"\ncarpetas=[]\n', encoding="utf-8")
    cfg = cargar_config(str(f))
    assert cfg.token == "TOK"
    assert cfg.usuario == ""   # opcional cuando hay token

def test_cargar_config_sin_token_ni_credenciales_falla(tmp_path):
    f = tmp_path / "agent.toml"
    f.write_text('backend_url="http://x"\ncarpetas=[]\n', encoding="utf-8")  # ni token ni usuario/clave
    with pytest.raises(ValueError):
        cargar_config(str(f))
```

Agregar a `agent/tests/test_run.py` (tiene `_api`, `ejecutar`, helpers):
```python
def _cfg_token(tmp_path, carpeta, token="TOK"):
    f = tmp_path / "agent.toml"
    f.write_text(
        f'backend_url = "http://x"\ntoken = {token!r}\n'
        f'carpetas = [{carpeta!r}]\nlote_size = 10\nestado_path = {str(tmp_path / "estado.json")!r}\n',
        encoding="utf-8")
    return str(f)

def test_run_con_token_omite_login(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    cfg = _cfg_token(tmp_path, str(datos))
    llamadas = {"login": 0, "lote": 0}
    def handler(req):
        if req.url.path == "/auth/login":
            llamadas["login"] += 1
            return httpx.Response(500)   # si se llamara, rompería
        llamadas["lote"] += 1
        assert req.headers["authorization"] == "Bearer TOK"
        return httpx.Response(200, json={"total": 1, "nuevos": 1, "actualizados": 0,
                                         "omitidos": 0, "errores": 0, "archivos": []})
    r = ejecutar(cfg, api=_api(handler))
    assert llamadas["login"] == 0      # NO se llamó login
    assert llamadas["lote"] == 1
    assert r["nuevos"] == 1

def test_run_con_token_401_no_reloguea(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    cfg = _cfg_token(tmp_path, str(datos))
    llamadas = {"login": 0, "lote": 0}
    def handler(req):
        if req.url.path == "/auth/login":
            llamadas["login"] += 1
            return httpx.Response(200, json={"access_token": "X"})
        llamadas["lote"] += 1
        return httpx.Response(401)
    r = ejecutar(cfg, api=_api(handler))
    assert llamadas["login"] == 0      # token estático → no re-login
    assert r["tandas_fallidas"] == 1
```

- [ ] **Step 2: Correr, confirmar FALLA**

Run (agente): `... -m pytest agent/tests/test_config.py agent/tests/test_run.py -q` → FAIL (config sin `token`; run llama login igual / `cfg.token` no existe).

- [ ] **Step 3: Modificar `agent/sxml_agent/config.py`**

Reemplazar la dataclass `Config` por esta (campos sin default primero; `usuario`/`clave` ahora opcionales; `token` agregado):
```python
@dataclass
class Config:
    backend_url: str
    carpetas: list[str]
    usuario: str = ""
    clave: str = ""
    lote_size: int = 100
    estado_path: str = "estado.json"
    intervalo: int = 300
    token: str | None = None  # token de agente (alternativa a usuario/clave)
```
Y reemplazar `cargar_config` por:
```python
def cargar_config(path: str) -> Config:
    ruta = Path(path)
    try:
        texto = ruta.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {ruta}")
    try:
        data = tomllib.loads(texto)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"TOML inválido en {ruta}: {e}") from e
    faltantes = {"backend_url", "carpetas"} - data.keys()
    if faltantes:
        raise ValueError(f"Faltan claves requeridas en {ruta}: {sorted(faltantes)}")
    token = data.get("token")
    usuario = str(data.get("usuario", ""))
    clave = str(data.get("clave", ""))
    if not token and not (usuario and clave):
        raise ValueError(f"En {ruta}: se requiere 'token' o ('usuario' y 'clave')")
    return Config(
        backend_url=str(data["backend_url"]).rstrip("/"),
        usuario=usuario,
        clave=clave,
        carpetas=[str(c) for c in data["carpetas"]],
        lote_size=int(data.get("lote_size", 100)),
        estado_path=str(data.get("estado_path", "estado.json")),
        intervalo=int(data.get("intervalo", 300)),
        token=str(token) if token else None,
    )
```
(Ajustar el orden de los campos en la dataclass para que `backend_url` y `carpetas` —sin default— vayan primero, y `usuario=""`, `clave=""`, `lote_size`, `estado_path`, `intervalo`, `token` después. La firma de `Config(...)` en la construcción usa keywords, así que el orden de los argumentos en la llamada no importa, pero la definición de la dataclass sí: todos los campos con default después de los sin default.)

- [ ] **Step 4: Modificar `agent/sxml_agent/run.py`** — usar el token estático si está

Reemplazar el inicio de `ejecutar` (la obtención del token) y el manejo de 401 en el bucle:
```python
def ejecutar(config_path: str, api: ApiClient | None = None) -> dict:
    cfg = cargar_config(config_path)
    api = api or ApiClient(cfg.backend_url)
    usa_token_estatico = bool(cfg.token)
    token = cfg.token if usa_token_estatico else api.login(cfg.usuario, cfg.clave)
    estado = Estado.cargar(cfg.estado_path)

    todos = escanear(cfg.carpetas)
    nuevos = [(p, h) for p in todos if not estado.ya_subido(h := hash_archivo(p))]

    resumen = {"escaneados": len(todos), "ya_subidos_local": len(todos) - len(nuevos),
               "enviados": 0, "nuevos": 0, "actualizados": 0, "omitidos": 0,
               "errores": 0, "tandas_fallidas": 0}

    for tanda in _tandas(nuevos, cfg.lote_size):
        rutas = [p for p, _ in tanda]
        try:
            try:
                rep = api.subir_lote(token, rutas)
            except NoAutorizado:
                if usa_token_estatico:
                    raise   # token estático: no re-login
                token = api.login(cfg.usuario, cfg.clave)
                rep = api.subir_lote(token, rutas)
        except ApiError:
            resumen["tandas_fallidas"] += 1
            continue
        resumen["enviados"] += len(rutas)
        for _, h in tanda:
            estado.marcar(h)
        for k in ("nuevos", "actualizados", "omitidos", "errores"):
            resumen[k] += rep.get(k, 0)

    estado.guardar()
    return resumen
```
(El resto del archivo —`_tandas` y los imports— queda igual.)

- [ ] **Step 5: Documentar en `agent/agent.example.toml`**

Agregar (debajo de `clave`), comentando la alternativa:
```toml
# Alternativa recomendada a usuario/clave: token de agente emitido por el backend
# (POST /api/agent-tokens). Si se define `token`, usuario/clave se ignoran.
# token = "PEGAR-TOKEN-DEL-BACKEND"
```

- [ ] **Step 6: Correr, confirmar PASA**

Run (agente): `... -m pytest agent/tests -q` → expect 31 passed (27 + 4). Verificar que los tests previos de `run` (usuario/clave) siguen verdes.

- [ ] **Step 7: Commit**

```bash
git add agent && git commit -m "feat(token-agente): agente usa config.token (omite login; sin re-login en 401)"
```

---

## Self-Review (cobertura del spec)

- **`AgentToken` (hash, label) + migración** → Tarea 1. ✅
- **`generar_token`/`hash_token`** → Tarea 2 (`auth/tokens.py`). ✅
- **`get_actor` (JWT o token, solo ingesta); JWT intacto; token inválido/revocado→401** → Tarea 2. ✅
- **`requiere_admin`** → Tarea 2; usado en Tarea 3. ✅
- **Endpoints `/api/agent-tokens` admin (crear→token en claro una vez / listar sin token / revocar)** → Tarea 3. ✅
- **Token acotado a ingesta** → solo ingesta usa `get_actor`; agent-tokens y el resto usan JWT/admin. ✅
- **Agente: `config.token` opcional + retrocompat; `run` usa token y omite login; 401 con token estático no re-loguea** → Tarea 4. ✅

**Consistencia de tipos:** `hash_token(str)->str`, `generar_token()->str`; `get_actor(...)->Usuario|AgentToken`; `requiere_admin(...)->Usuario`; `AgentTokenCreated{id,label,token}` / `AgentTokenOut{id,label,created_at}`; `Config.token: str|None`; `run.ejecutar` usa `cfg.token`. Consistente entre tareas y tests. ✅

**Sin placeholders:** código completo; comandos, conteos y rutas explícitos. ✅

## Diferido
1C-3b empaquetado `.exe`/Tarea Programada; `last_used_at`/rotación; UI de tokens (1D); keyring para el token.
