# Agente local 1C-3a: token de agente (auth revocable) — Diseño

> Documento de diseño (spec). El plan de implementación con pasos TDD va aparte:
> `docs/plans/2026-06-22-agente-token.md`. Endurecimiento de credenciales del agente
> (parte de 1C-3; el empaquetado `.exe` es 1C-3b, diferido).

## Objetivo

Reemplazar la **clave del contador en texto plano** en `agent.toml` por un **token de
agente** emitido por el backend: largo, aleatorio, **revocable**, y **acotado a la
ingesta**. Así no hay password en disco en la máquina del contador, y un token
filtrado se revoca centralmente sin cambiar la clave del usuario.

## Contexto (auth actual)

- `auth/deps.py::get_current_user(token=Depends(oauth2_scheme), db)` decodifica un JWT
  (`sub` = id de usuario) y devuelve el `Usuario`.
- `auth/router.py::POST /auth/login` valida usuario/clave (hash dummy de tiempo
  constante anti-enumeración) y emite el JWT.
- `Usuario`: `id, nombre (único), password_hash, es_admin, created_at`.
- Endpoints de ingesta (`POST /api/ingesta`, `POST /api/ingesta/lote`) hoy usan
  `Depends(get_current_user)` (JWT).
- El agente (1C-1/1C-2) hace `login(usuario, clave)` y usa el JWT para subir.

## Decisiones de diseño

1. **Token hasheado, revocar = borrar.** Se guarda solo `sha256(token)`; el token en
   claro se devuelve una sola vez al crearlo. Revocar = `DELETE` de la fila (existe ⟺
   válido). Sin flag `activo` (YAGNI).
2. **`get_actor` acepta JWT o token, solo en ingesta.** Una dependencia nueva que:
   intenta el JWT (lógica de `get_current_user` intacta) → `Usuario`; si no, busca el
   hash del Bearer en `agent_tokens` → `AgentToken`; si ninguno → 401. Solo las rutas
   de ingesta pasan a `get_actor`; el resto siguen JWT-only → el token queda **acotado
   a la ingesta** (no puede tocar reglas, D-150, clientes, etc.).
3. **Gestión de tokens solo admin.** `POST`/`GET`/`DELETE /api/agent-tokens` exigen
   `es_admin` (dep `requiere_admin`). No-admin → 403; sin token → 401.
4. **Agente: token opcional, retrocompatible.** `config.token` opcional. Si está, el
   agente lo usa como Bearer y **omite el login** (sin password en disco). Si no, cae
   al login usuario/clave actual. Un 401 con token estático **no re-loguea** (el token
   es la credencial; revocado/inválido → la tanda falla y se loguea).
5. **No se debilita el JWT.** La ruta JWT de `get_actor` es idéntica a
   `get_current_user`; el login y los demás endpoints no cambian.

## Componentes

### Backend

- **`models/agent_token.py`** + migración: `AgentToken(id, token_hash: str(64) unique
  index, label: str(120), created_at)`.
- **`auth/tokens.py`** (helpers): `generar_token() -> str` (`secrets.token_urlsafe(32)`);
  `hash_token(t: str) -> str` (`hashlib.sha256(t.encode()).hexdigest()`).
- **`auth/deps.py`**:
  - `get_actor(token=Depends(oauth2_scheme), db) -> Usuario | AgentToken`: JWT → user;
    si falla, `hash_token(token)` lookup en `agent_tokens`; si ninguno → 401.
  - `requiere_admin(usuario=Depends(get_current_user)) -> Usuario`: 403 si no `es_admin`.
- **`routers/ingesta.py`**: cambiar `Depends(get_current_user)` → `Depends(get_actor)`
  en ambos endpoints de ingesta. (Los tests JWT existentes siguen pasando.)
- **`routers/agent_tokens.py`** + `schemas/agent_token.py`:
  - `POST /api/agent-tokens` (admin) — body `{label}`; crea; responde
    `{id, label, token}` (token en claro, única vez).
  - `GET /api/agent-tokens` (admin) — lista `[{id, label, created_at}]` (sin token).
  - `DELETE /api/agent-tokens/{id}` (admin) — 204; revoca.
- `main.py`: incluir `agent_tokens_router`.

### Agente

- **`config.py`**: campo `token: str | None = None` (lee `data.get("token")`).
  `usuario`/`clave` pasan a opcionales (default `""`) — se requieren solo si no hay
  token. `agent.example.toml`: documentar `token` (alternativa a usuario/clave).
- **`run.py`**: el token efectivo = `cfg.token` si está, si no `api.login(usuario,
  clave)`. En el bucle de tandas, el re-login en 401 solo aplica si NO hay token
  estático (con token: 401 → cuenta como tanda fallida, sin re-login).
- **`cliente_api.py`**: sin cambios (ya recibe el token y lo manda como Bearer).

## Flujo

```
Admin: POST /api/agent-tokens {label} → {token}  (una vez)  → se pega en agent.toml
Agente: token = cfg.token (sin login) → subir_lote(token, ...) a /api/ingesta/lote
Backend ingesta: get_actor → JWT? no → hash(token) en agent_tokens → ok | 401
Revocar: DELETE /api/agent-tokens/{id} → el agente empieza a recibir 401 (tanda falla)
```

## Estrategia de pruebas (TDD)

**Backend** (suite backend; Postgres local):
1. Modelo `AgentToken` persiste; migración limpia.
2. `auth/tokens`: `hash_token` estable; `generar_token` largo/único.
3. `get_actor`: JWT válido → user; token válido → ok (ingesta responde 200); Bearer
   basura → 401; token revocado (borrado) → 401.
4. Ingesta con token: `POST /api/ingesta/lote` con `Authorization: Bearer <token>` →
   200 (reusa fixtures). Y que el JWT siga funcionando (no romper tests existentes).
5. Endpoints `/api/agent-tokens`: admin crea → token en claro; lista (sin token);
   DELETE revoca (luego ingesta con ese token → 401); no-admin → 403; sin token → 401.

**Agente** (suite agente; httpx MockTransport):
6. `config.token` se lee; usuario/clave opcionales cuando hay token.
7. `run.ejecutar` con `cfg.token`: NO llama `/auth/login` (el handler de login no se
   invoca) y usa el token en `subir_lote`; un 401 con token estático no re-loguea
   (tanda fallida).

## Fuera de alcance

- **1C-3b empaquetado** `.exe` (PyInstaller) + Tarea Programada/servicio (no
  testeable acá; build script + docs en fase aparte).
- `last_used_at` / expiración / rotación automática de tokens.
- Scopes por token más finos (hoy: ingesta vs no-ingesta por endpoint).
- UI de gestión de tokens (fase frontend 1D).

## Seguridad / riesgos

- **Token aleatorio de 256 bits, guardado hasheado** (sha256); revocable; acotado a
  ingesta. La ruta JWT no se toca.
- **`token` en `agent.toml` sigue en texto plano** — pero es un secreto revocable y
  de alcance limitado (no la clave del usuario). Combinarlo con keyring para el token
  queda como mejora futura.
- **Sin enumeración:** el lookup es por hash exacto (256 bits); un Bearer inválido
  cae al 401 estándar. No hay diferencia observable de timing relevante sobre un hash
  aleatorio.
- **Admin-only** para emitir/revocar: un token de agente (o un usuario no-admin) no
  puede crear ni listar tokens.
