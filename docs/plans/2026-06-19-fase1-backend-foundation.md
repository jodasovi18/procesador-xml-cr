# Fase 1 — Plan 1A: Fundación del backend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Levantar un backend FastAPI con PostgreSQL, modelos de datos tipados, autenticación por login, y el CRUD de clientes — la base sobre la que se montan el motor, la ingesta, el frontend y los reportes.

**Architecture:** Monorepo nuevo (`sistema-xml-web/`) separado del Flask actual. Backend FastAPI + SQLAlchemy 2.0 (sync) + PostgreSQL 16 + Alembic. Auth con JWT bearer (OAuth2PasswordBearer) y hashing bcrypt. Pydantic v2 para validación. Todo cubierto con pytest contra una base de datos de prueba real.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, psycopg 3, Alembic, Pydantic v2 + pydantic-settings, passlib[bcrypt], python-jose[cryptography], pytest, httpx, Docker Compose (Postgres local).

---

## Contexto del proyecto (leer antes de empezar)

Este es un **rebuild desde cero** del "Sistema XML CR" (procesador de comprobantes electrónicos de Costa Rica para una firma contable). El sistema viejo es un monolito Flask (`app.py` 4.256 líneas + `parse_xml.py` 2.970 líneas + `index.html` 5.055 líneas) con estado en archivos JSON. Esta Fase 1A construye la fundación del reemplazo.

**Decisiones ya tomadas (no re-litigar):**
- Una sola firma (single-tenant). Sin multi-tenant.
- Ingesta por agente local + subida manual (se construye en el Plan 1C/1B, no acá).
- El período de un comprobante sale de la **fecha del XML**, no del nombre de carpeta.
- El rol (compra/venta) se decide comparando la cédula del cliente contra emisor/receptor.
- Color de marca del frontend: teal (no aplica a este plan, es backend).

**Roadmap de la Fase 1 (este plan es el 1A):**
- **1A — Fundación backend** (este documento): FastAPI + Postgres + auth + CRUD clientes.
- **1B — Motor + ingesta:** portar `parse_xml.py` a módulos tipados con golden tests; endpoint de ingesta (recibe XML → identifica cliente/rol → parsea → upsert por clave → clasifica → guarda).
- **1C — Agente local:** programa Python que vigila carpetas OneDrive y sube XML al endpoint de ingesta.
- **1D — Frontend React:** app React + TypeScript con las pantallas (resumen, clientes, comprobantes, clasificación, D-150, entradas manuales).
- **1E — Reportes:** portar generación Excel/PDF y endpoints de exportación.

**Prerrequisito de entorno:** Docker Desktop instalado (para Postgres local). Si no hay Docker, alternativa: Postgres 16 instalado localmente y ajustar `DATABASE_URL`. Verificar con `docker --version` antes de la Tarea 2.

---

## Estructura de archivos (se crea en este plan)

```
sistema-xml-web/                      # raíz del nuevo proyecto (git init acá)
  docker-compose.yml                  # Postgres local para desarrollo
  backend/
    pyproject.toml                    # deps y config del paquete
    .env.example                      # plantilla de variables de entorno
    .gitignore
    alembic.ini                       # config de migraciones
    alembic/
      env.py                          # entorno de migraciones (lee metadata)
      versions/                       # migraciones generadas
    app/
      __init__.py
      main.py                         # crea la app FastAPI, incluye routers
      config.py                       # Settings (pydantic-settings)
      db.py                           # engine, SessionLocal, Base, get_db
      models/
        __init__.py                   # importa todos los modelos (para Alembic)
        usuario.py                    # modelo ORM Usuario
        cliente.py                    # modelo ORM Cliente
      schemas/
        __init__.py
        auth.py                       # Token, schemas de login
        cliente.py                    # ClienteCreate, ClienteOut
      auth/
        __init__.py
        security.py                   # hash de password, crear/verificar JWT
        deps.py                       # dependencia get_current_user
        router.py                     # POST /auth/login
      routers/
        __init__.py
        clientes.py                   # /api/clientes (CRUD protegido)
    tests/
      __init__.py
      conftest.py                     # fixtures: test DB + TestClient
      test_health.py
      test_auth.py
      test_clientes.py
```

**Responsabilidad de cada archivo:**
- `config.py` — única fuente de configuración (DB URL, secret JWT, expiración). Nada de constantes mágicas dispersas.
- `db.py` — única definición del engine/sesión/Base. Todos los modelos heredan de su `Base`.
- `models/*` — una tabla por archivo. Sin lógica de negocio, solo el esquema.
- `schemas/*` — contratos de entrada/salida de la API (Pydantic). Separados de los modelos ORM.
- `auth/*` — todo lo de autenticación junto (cambia junto).
- `routers/*` — un archivo por recurso de la API.

---

## Tarea 1: Scaffold del proyecto y FastAPI mínimo

**Files:**
- Create: `sistema-xml-web/backend/pyproject.toml`
- Create: `sistema-xml-web/backend/.gitignore`
- Create: `sistema-xml-web/backend/app/__init__.py` (vacío)
- Create: `sistema-xml-web/backend/app/main.py`
- Create: `sistema-xml-web/backend/tests/__init__.py` (vacío)
- Create: `sistema-xml-web/backend/tests/test_health.py`

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "sistema-xml-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.30",
    "sqlalchemy>=2.0",
    "psycopg[binary]>=3.1",
    "alembic>=1.13",
    "pydantic>=2.7",
    "pydantic-settings>=2.3",
    "passlib[bcrypt]>=1.7",
    "python-jose[cryptography]>=3.3",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "httpx>=0.27"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Crear `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
```

- [ ] **Step 3: Crear el entorno virtual e instalar**

Run (desde `sistema-xml-web/backend/`):
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```
Expected: instala FastAPI y dependencias sin error.

- [ ] **Step 4: Escribir el test que falla (`tests/test_health.py`)**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 5: Correr el test y verificar que falla**

Run: `.venv/Scripts/python -m pytest tests/test_health.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.main'`.

- [ ] **Step 6: Crear `app/__init__.py` vacío y `app/main.py`**

`app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="Sistema XML")

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Correr el test y verificar que pasa**

Run: `.venv/Scripts/python -m pytest tests/test_health.py -v`
Expected: PASS (1 passed).

- [ ] **Step 8: Commit**

```bash
cd sistema-xml-web && git init && git add backend
git commit -m "feat(backend): scaffold FastAPI con endpoint /health"
```

---

## Tarea 2: Configuración y conexión a PostgreSQL

**Files:**
- Create: `sistema-xml-web/docker-compose.yml`
- Create: `sistema-xml-web/backend/.env.example`
- Create: `sistema-xml-web/backend/app/config.py`
- Create: `sistema-xml-web/backend/app/db.py`
- Create: `sistema-xml-web/backend/tests/conftest.py`

- [ ] **Step 1: Crear `docker-compose.yml` (raíz del proyecto)**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: sistemaxml
      POSTGRES_PASSWORD: devpassword
      POSTGRES_DB: sistemaxml
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

- [ ] **Step 2: Levantar Postgres**

Run (desde `sistema-xml-web/`): `docker compose up -d`
Expected: contenedor `db` corriendo; `docker compose ps` lo muestra "running" en el puerto 5433.

- [ ] **Step 3: Crear `.env.example` y `.env`**

`.env.example`:
```env
DATABASE_URL=postgresql+psycopg://sistemaxml:devpassword@localhost:5433/sistemaxml
JWT_SECRET=cambiar-esto-en-produccion
JWT_EXPIRE_MINUTES=480
```
Copiar a `.env`: `cp .env.example .env` (desde `backend/`).

- [ ] **Step 4: Crear `app/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://sistemaxml:devpassword@localhost:5433/sistemaxml"
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 480
    jwt_algorithm: str = "HS256"

settings = Settings()
```

- [ ] **Step 5: Crear `app/db.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 6: Crear `tests/conftest.py` (DB de prueba aislada por test)**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.config import settings
from app.db import Base, get_db
from app.main import app
import app.models  # registra todos los modelos en Base.metadata

TEST_DB_URL = settings.database_url + "_test"

@pytest.fixture(scope="session")
def engine():
    from sqlalchemy_utils import create_database, database_exists, drop_database
    if database_exists(TEST_DB_URL):
        drop_database(TEST_DB_URL)
    create_database(TEST_DB_URL)
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(eng)
    yield eng
    drop_database(TEST_DB_URL)

@pytest.fixture
def db_session(engine):
    conn = engine.connect()
    txn = conn.begin()
    TestingSession = sessionmaker(bind=conn)
    session = TestingSession()
    yield session
    session.close()
    txn.rollback()
    conn.close()

@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
```

Nota: agregar `sqlalchemy-utils>=0.41` a las dev-deps en `pyproject.toml` y reinstalar (`.venv/Scripts/python -m pip install -e ".[dev]"`).

- [ ] **Step 7: Crear `app/models/__init__.py` vacío (se llena en Tarea 4)**

Crear el archivo vacío para que el import en conftest no falle todavía. Se llenará en la Tarea 4.

- [ ] **Step 8: Verificar que la suite existente sigue verde**

Run: `.venv/Scripts/python -m pytest -v`
Expected: `test_health_ok` PASS (la conexión a DB aún no se usa en ningún test, solo se preparó la infraestructura).

- [ ] **Step 9: Commit**

```bash
git add backend docker-compose.yml
git commit -m "feat(backend): config, conexión Postgres y fixtures de test"
```

---

## Tarea 3: Migraciones con Alembic

**Files:**
- Create: `sistema-xml-web/backend/alembic.ini`
- Create: `sistema-xml-web/backend/alembic/env.py`

- [ ] **Step 1: Inicializar Alembic**

Run (desde `backend/`): `.venv/Scripts/alembic init alembic`
Expected: crea `alembic.ini` y la carpeta `alembic/`.

- [ ] **Step 2: Configurar `alembic/env.py` para usar nuestra metadata y URL**

Reemplazar el cuerpo relevante de `alembic/env.py` por:
```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from app.config import settings
from app.db import Base
import app.models  # registra modelos

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

- [ ] **Step 3: Verificar que Alembic conecta**

Run: `.venv/Scripts/alembic current`
Expected: no error; imprime el estado actual (sin migraciones aún).

- [ ] **Step 4: Commit**

```bash
git add backend/alembic.ini backend/alembic
git commit -m "feat(backend): configurar Alembic para migraciones"
```

Nota: la primera migración real se genera en la Tarea 4 (cuando existan modelos).

---

## Tarea 4: Modelo Usuario, hashing y login (JWT)

**Files:**
- Create: `sistema-xml-web/backend/app/models/usuario.py`
- Modify: `sistema-xml-web/backend/app/models/__init__.py`
- Create: `sistema-xml-web/backend/app/auth/__init__.py` (vacío)
- Create: `sistema-xml-web/backend/app/auth/security.py`
- Create: `sistema-xml-web/backend/app/schemas/__init__.py` (vacío)
- Create: `sistema-xml-web/backend/app/schemas/auth.py`
- Create: `sistema-xml-web/backend/app/auth/router.py`
- Modify: `sistema-xml-web/backend/app/main.py`
- Create: `sistema-xml-web/backend/tests/test_auth.py`

- [ ] **Step 1: Escribir el test que falla (`tests/test_auth.py`)**

```python
from app.models.usuario import Usuario
from app.auth.security import hash_password

def _crear_usuario(db, nombre="ana", password="secreta123", es_admin=True):
    u = Usuario(nombre=nombre, password_hash=hash_password(password), es_admin=es_admin)
    db.add(u); db.commit(); db.refresh(u)
    return u

def test_login_correcto_devuelve_token(client, db_session):
    _crear_usuario(db_session)
    resp = client.post("/auth/login", data={"username": "ana", "password": "secreta123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 20

def test_login_password_incorrecta_401(client, db_session):
    _crear_usuario(db_session)
    resp = client.post("/auth/login", data={"username": "ana", "password": "mala"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.models.usuario'`.

- [ ] **Step 3: Crear `app/models/usuario.py`**

```python
from sqlalchemy import Integer, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    es_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 4: Registrar el modelo en `app/models/__init__.py`**

```python
from app.models.usuario import Usuario  # noqa: F401
```

- [ ] **Step 5: Crear `app/auth/security.py`**

```python
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt
from app.config import settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain: str) -> str:
    return _pwd.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)

def create_access_token(sub: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": sub, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
```

- [ ] **Step 6: Crear `app/schemas/auth.py`**

```python
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 7: Crear `app/auth/router.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.usuario import Usuario
from app.auth.security import verify_password, create_access_token
from app.schemas.auth import Token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == form.username))
    if not usuario or not verify_password(form.password, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Usuario o contraseña incorrectos")
    token = create_access_token(sub=usuario.nombre)
    return Token(access_token=token)
```

- [ ] **Step 8: Incluir el router en `app/main.py`**

```python
from fastapi import FastAPI
from app.auth.router import router as auth_router

app = FastAPI(title="Sistema XML")
app.include_router(auth_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Correr y verificar que pasa**

Run: `.venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: PASS (2 passed).

- [ ] **Step 10: Generar y aplicar la migración**

Run (desde `backend/`):
```bash
.venv/Scripts/alembic revision --autogenerate -m "crear tabla usuarios"
.venv/Scripts/alembic upgrade head
```
Expected: crea una migración en `alembic/versions/` con la tabla `usuarios` y la aplica sin error.

- [ ] **Step 11: Commit**

```bash
git add backend
git commit -m "feat(backend): modelo Usuario, hashing bcrypt y login JWT"
```

---

## Tarea 5: Dependencia de autenticación (get_current_user)

**Files:**
- Create: `sistema-xml-web/backend/app/auth/deps.py`
- Modify: `sistema-xml-web/backend/tests/test_auth.py`

- [ ] **Step 1: Agregar el test que falla a `tests/test_auth.py`**

```python
def test_endpoint_protegido_sin_token_401(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401

def test_endpoint_protegido_con_token_ok(client, db_session):
    _crear_usuario(db_session, nombre="beto", password="clave12345")
    login = client.post("/auth/login", data={"username": "beto", "password": "clave12345"})
    token = login.json()["access_token"]
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "beto"
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: FAIL (404 en `/auth/me`, la ruta no existe).

- [ ] **Step 3: Crear `app/auth/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Usuario:
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Credenciales inválidas",
                             headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        nombre = payload.get("sub")
        if nombre is None:
            raise cred_exc
    except JWTError:
        raise cred_exc
    usuario = db.scalar(select(Usuario).where(Usuario.nombre == nombre))
    if usuario is None:
        raise cred_exc
    return usuario
```

- [ ] **Step 4: Agregar la ruta `/auth/me` a `app/auth/router.py`**

Agregar al final de `app/auth/router.py`:
```python
from app.auth.deps import get_current_user

@router.get("/me")
def me(usuario: Usuario = Depends(get_current_user)):
    return {"id": usuario.id, "nombre": usuario.nombre, "es_admin": usuario.es_admin}
```

- [ ] **Step 5: Correr y verificar que pasa**

Run: `.venv/Scripts/python -m pytest tests/test_auth.py -v`
Expected: PASS (4 passed en total).

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat(backend): dependencia get_current_user y ruta /auth/me"
```

---

## Tarea 6: Modelo Cliente y CRUD protegido

**Files:**
- Create: `sistema-xml-web/backend/app/models/cliente.py`
- Modify: `sistema-xml-web/backend/app/models/__init__.py`
- Create: `sistema-xml-web/backend/app/schemas/cliente.py`
- Create: `sistema-xml-web/backend/app/routers/__init__.py` (vacío)
- Create: `sistema-xml-web/backend/app/routers/clientes.py`
- Modify: `sistema-xml-web/backend/app/main.py`
- Create: `sistema-xml-web/backend/tests/test_clientes.py`

- [ ] **Step 1: Escribir el test que falla (`tests/test_clientes.py`)**

```python
from app.models.usuario import Usuario
from app.auth.security import hash_password

def _token(client, db_session):
    db_session.add(Usuario(nombre="cata", password_hash=hash_password("clave12345"), es_admin=True))
    db_session.commit()
    r = client.post("/auth/login", data={"username": "cata", "password": "clave12345"})
    return r.json()["access_token"]

def _auth(token):
    return {"Authorization": f"Bearer {token}"}

def test_crear_y_listar_cliente(client, db_session):
    token = _token(client, db_session)
    nuevo = {"cedula": "3102858282", "nombre": "Agrofinca La Flor S&C Ltda",
             "tipo_cedula": "juridica", "regimen": "tradicional"}
    r = client.post("/api/clientes", json=nuevo, headers=_auth(token))
    assert r.status_code == 201
    assert r.json()["cedula"] == "3102858282"

    r2 = client.get("/api/clientes", headers=_auth(token))
    assert r2.status_code == 200
    cedulas = [c["cedula"] for c in r2.json()]
    assert "3102858282" in cedulas

def test_cedula_duplicada_409(client, db_session):
    token = _token(client, db_session)
    nuevo = {"cedula": "3101030042", "nombre": "Almacén León Rojas",
             "tipo_cedula": "juridica", "regimen": "tradicional"}
    assert client.post("/api/clientes", json=nuevo, headers=_auth(token)).status_code == 201
    dup = client.post("/api/clientes", json=nuevo, headers=_auth(token))
    assert dup.status_code == 409

def test_listar_sin_token_401(client):
    assert client.get("/api/clientes").status_code == 401
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `.venv/Scripts/python -m pytest tests/test_clientes.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.models.cliente'`.

- [ ] **Step 3: Crear `app/models/cliente.py`**

```python
from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base

class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cedula: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_cedula: Mapped[str] = mapped_column(String(20), nullable=False)
    regimen: Mapped[str] = mapped_column(String(40), nullable=False, default="tradicional")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Registrar el modelo en `app/models/__init__.py`**

```python
from app.models.usuario import Usuario  # noqa: F401
from app.models.cliente import Cliente  # noqa: F401
```

- [ ] **Step 5: Crear `app/schemas/cliente.py`**

```python
from pydantic import BaseModel, ConfigDict

class ClienteCreate(BaseModel):
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str = "tradicional"

class ClienteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cedula: str
    nombre: str
    tipo_cedula: str
    regimen: str
```

- [ ] **Step 6: Crear `app/routers/clientes.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.auth.deps import get_current_user
from app.models.usuario import Usuario
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate, ClienteOut

router = APIRouter(prefix="/api/clientes", tags=["clientes"])

@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def crear_cliente(data: ClienteCreate, db: Session = Depends(get_db),
                  _: Usuario = Depends(get_current_user)):
    cliente = Cliente(**data.model_dump())
    db.add(cliente)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Ya existe un cliente con esa cédula")
    db.refresh(cliente)
    return cliente

@router.get("", response_model=list[ClienteOut])
def listar_clientes(db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    return list(db.scalars(select(Cliente).order_by(Cliente.nombre)))
```

- [ ] **Step 7: Incluir el router en `app/main.py`**

```python
from fastapi import FastAPI
from app.auth.router import router as auth_router
from app.routers.clientes import router as clientes_router

app = FastAPI(title="Sistema XML")
app.include_router(auth_router)
app.include_router(clientes_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Correr y verificar que pasa**

Run: `.venv/Scripts/python -m pytest -v`
Expected: PASS (todos: health 1 + auth 4 + clientes 3 = 8 passed).

- [ ] **Step 9: Generar y aplicar la migración**

Run (desde `backend/`):
```bash
.venv/Scripts/alembic revision --autogenerate -m "crear tabla clientes"
.venv/Scripts/alembic upgrade head
```
Expected: migración con la tabla `clientes` aplicada sin error.

- [ ] **Step 10: Verificación manual (correr el servidor)**

Run: `.venv/Scripts/uvicorn app.main:app --reload`
Abrir `http://localhost:8000/docs`. Verificar que aparecen `/auth/login`, `/auth/me`, `POST /api/clientes`, `GET /api/clientes`. Probar el flujo: crear usuario por consola (o un script semilla), hacer login, autorizar con el token, crear y listar un cliente.

- [ ] **Step 11: Commit**

```bash
git add backend
git commit -m "feat(backend): modelo Cliente y CRUD protegido (crear/listar)"
```

---

## Self-Review (cobertura del plan 1A)

- **Scaffold FastAPI** → Tarea 1 (test `/health`). ✅
- **Conexión Postgres + fixtures de test** → Tarea 2. ✅
- **Migraciones** → Tarea 3 + pasos de migración en Tareas 4 y 6. ✅
- **Auth (login + protección)** → Tareas 4 y 5 (tests de login OK/KO y rutas protegidas). ✅
- **CRUD clientes** → Tarea 6 (crear, listar, duplicado 409, sin token 401). ✅
- **Consistencia de tipos:** `Usuario(nombre, password_hash, es_admin)`, `Cliente(cedula, nombre, tipo_cedula, regimen)`, `hash_password`/`verify_password`/`create_access_token`, `get_current_user`, `get_db`, `Base`/`SessionLocal`/`engine` — usados con los mismos nombres en todas las tareas. ✅
- **Sin placeholders:** cada paso de código trae el código completo y el comando exacto con su salida esperada. ✅

**Resultado de la Fase 1A:** un backend que arranca, con login funcionando y gestión de clientes, cubierto por 8 pruebas. Base lista para montar encima el motor y la ingesta (Plan 1B).

---

## Próximos planes de la Fase 1 (a escribir después de 1A)

- **1B — Motor + ingesta:** modelos `Comprobante` y `LineaComprobante`; portar `parse_xml.py` (del repo viejo `C:\Users\Usuario\Desktop\Sistemas\Sistema XML\parse_xml.py`) a `app/motor/` con golden tests sobre XML reales; endpoint `POST /api/ingesta` (recibe XML → identifica cliente/rol por cédula → parsea → upsert por `clave` → clasifica → guarda); endpoint de subida manual (ZIP/múltiples XML).
- **1C — Agente local:** `agent/` con watchdog sobre las carpetas de OneDrive, cola offline y subida autenticada al endpoint de ingesta.
- **1D — Frontend React:** `frontend/` con Vite + React + TypeScript; proxy a la API; las pantallas diseñadas (resumen, selector de clientes, comprobantes, clasificación, D-150, entradas manuales) con la marca teal.
- **1E — Reportes:** portar la generación Excel (`openpyxl`) y PDF (`reportlab`) del repo viejo; endpoints `GET /api/reportes/excel` y `/pdf`.
