# Agente local 1C-1: CLI de un disparo — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un agente CLI standalone que escanea carpetas, sube los XML nuevos al backend (`POST /api/ingesta/lote`) evitando re-subir lo ya enviado (dedup por hash), y reporta un resumen. Se corre de un disparo (agendable con Tarea Programada).

**Architecture:** Paquete `agent/sxml_agent/` que solo depende de `httpx` + stdlib (no comparte código con `backend/`; habla por HTTP). Componentes pequeños y aislados: `escaner`, `estado`, `config`, `cliente_api`, `run`, `__main__`. Tests con `httpx.MockTransport` (sin backend vivo).

**Tech Stack:** Python 3.11, `httpx` (ya en el venv), `tomllib` (stdlib), pytest.

> **Diseño:** `docs/plans/2026-06-22-agente-cli-design.md`.

---

## Contexto y entorno (CRÍTICO)

- **Venv:** no hay `.venv` propio en el worktree. Correr con `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe` (tiene `httpx` y `pytest`). Nunca el `python` pelado.
- **Correr los tests del agente** (desde la raíz del worktree), con `PYTHONPATH` apuntando a `agent/` (NO a backend — el agente no importa `app`):
  - PowerShell: `$env:PYTHONPATH="C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\.claude\worktrees\priceless-engelbart-569a52\agent"; & "C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe" -m pytest agent/tests -q`
- El agente es **standalone**: importa solo `httpx` + stdlib; NO importa nada de `backend/app`. Su suite de tests es independiente de la del backend (75 verdes, no se tocan).
- Endpoints del backend que consume: `POST /auth/login` (form `username`/`password` → `{access_token}`) y `POST /api/ingesta/lote` (multipart, campo `archivos`; devuelve `{total, nuevos, actualizados, omitidos, errores, archivos:[...]}`).

## File Structure

```
agent/
  sxml_agent/
    __init__.py
    escaner.py       # escanear(carpetas)->list[Path]; hash_archivo(path)->str
    estado.py        # Estado: cargar/ya_subido/marcar/guardar (JSON de hashes)
    config.py        # Config (dataclass) + cargar_config(path)->Config (tomllib)
    cliente_api.py   # ApiClient(base_url, client=None): login/subir_lote; ApiError, NoAutorizado
    run.py           # ejecutar(config_path, api=None)->dict (resumen)
    __main__.py      # CLI: python -m sxml_agent --config agent.toml
  agent.example.toml
  tests/
    test_escaner.py
    test_estado.py
    test_config.py
    test_cliente_api.py
    test_run.py
```

---

## Tarea 1: Paquete + `escaner`

**Files:**
- Create: `agent/sxml_agent/__init__.py` (vacío)
- Create: `agent/sxml_agent/escaner.py`
- Test: `agent/tests/test_escaner.py`

- [ ] **Step 1: Escribir el test que falla** `agent/tests/test_escaner.py`

```python
from sxml_agent.escaner import escanear, hash_archivo

def test_escanear_solo_xml_recursivo(tmp_path):
    (tmp_path / "a.xml").write_text("<a/>", encoding="utf-8")
    (tmp_path / "nota.pdf").write_bytes(b"%PDF")
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "b.xml").write_text("<b/>", encoding="utf-8")
    (sub / "c.txt").write_text("x", encoding="utf-8")
    res = escanear([str(tmp_path)])
    assert sorted(p.name for p in res) == ["a.xml", "b.xml"]

def test_escanear_carpeta_inexistente_se_omite(tmp_path):
    (tmp_path / "a.xml").write_text("<a/>", encoding="utf-8")
    res = escanear([str(tmp_path), str(tmp_path / "noexiste")])
    assert [p.name for p in res] == ["a.xml"]

def test_hash_archivo_estable_y_sensible(tmp_path):
    f = tmp_path / "x.xml"; f.write_text("<a/>", encoding="utf-8")
    h1 = hash_archivo(f)
    assert h1 == hash_archivo(f)
    assert len(h1) == 64
    f.write_text("<b/>", encoding="utf-8")
    assert hash_archivo(f) != h1
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `... -m pytest agent/tests/test_escaner.py -q` (con el env descrito arriba).
Expected: FAIL — `ModuleNotFoundError: No module named 'sxml_agent'`.

- [ ] **Step 3: Crear el paquete y `escaner`**

`agent/sxml_agent/__init__.py`: archivo vacío.

`agent/sxml_agent/escaner.py`:
```python
"""Escaneo de carpetas: encuentra los .xml (recursivo) y calcula su hash de contenido."""
import hashlib
from pathlib import Path


def escanear(carpetas: list[str]) -> list[Path]:
    """Devuelve todos los .xml (recursivo) de las carpetas dadas, sin duplicados,
    ordenados. Las carpetas inexistentes se omiten."""
    vistos: set[Path] = set()
    for carpeta in carpetas:
        base = Path(carpeta)
        if not base.is_dir():
            continue
        for p in base.rglob("*.xml"):
            if p.is_file():
                vistos.add(p.resolve())
    return sorted(vistos)


def hash_archivo(path: Path) -> str:
    """sha256 hex del contenido del archivo (lectura por bloques)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: `... -m pytest agent/tests/test_escaner.py -q`. Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add agent && git commit -m "feat(agente): paquete sxml_agent + escaner (.xml recursivo + hash)"
```

---

## Tarea 2: `estado` (hashes ya subidos)

**Files:**
- Create: `agent/sxml_agent/estado.py`
- Test: `agent/tests/test_estado.py`

- [ ] **Step 1: Escribir el test que falla** `agent/tests/test_estado.py`

```python
from sxml_agent.estado import Estado

def test_estado_vacio_si_no_existe(tmp_path):
    e = Estado.cargar(str(tmp_path / "estado.json"))
    assert e.ya_subido("abc") is False

def test_estado_marcar_guardar_recargar(tmp_path):
    ruta = str(tmp_path / "estado.json")
    e = Estado.cargar(ruta)
    e.marcar("abc"); e.guardar()
    e2 = Estado.cargar(ruta)
    assert e2.ya_subido("abc") is True
    assert e2.ya_subido("xyz") is False
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `... -m pytest agent/tests/test_estado.py -q`. Expected: FAIL — `ModuleNotFoundError: No module named 'sxml_agent.estado'`.

- [ ] **Step 3: Crear `agent/sxml_agent/estado.py`**

```python
"""Estado local: conjunto de hashes de archivos ya subidos, persistido en JSON."""
import json
from pathlib import Path


class Estado:
    def __init__(self, path: str, hashes: set[str]):
        self._path = Path(path)
        self._hashes = hashes

    @classmethod
    def cargar(cls, path: str) -> "Estado":
        p = Path(path)
        if p.is_file():
            data = json.loads(p.read_text(encoding="utf-8"))
            return cls(path, set(data.get("subidos", [])))
        return cls(path, set())

    def ya_subido(self, h: str) -> bool:
        return h in self._hashes

    def marcar(self, h: str) -> None:
        self._hashes.add(h)

    def guardar(self) -> None:
        self._path.write_text(
            json.dumps({"subidos": sorted(self._hashes)}, ensure_ascii=False),
            encoding="utf-8")
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: `... -m pytest agent/tests/test_estado.py -q`. Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add agent && git commit -m "feat(agente): estado local de hashes subidos (JSON)"
```

---

## Tarea 3: `config` (TOML)

**Files:**
- Create: `agent/sxml_agent/config.py`
- Create: `agent/agent.example.toml`
- Test: `agent/tests/test_config.py`

- [ ] **Step 1: Escribir el test que falla** `agent/tests/test_config.py`

```python
from sxml_agent.config import cargar_config

def test_cargar_config(tmp_path):
    f = tmp_path / "agent.toml"
    f.write_text(
        'backend_url = "http://localhost:8000/"\n'
        'usuario = "agente"\n'
        'clave = "secreta"\n'
        'carpetas = ["C:/datos/a", "C:/datos/b"]\n'
        'lote_size = 50\n',
        encoding="utf-8")
    cfg = cargar_config(str(f))
    assert cfg.backend_url == "http://localhost:8000"   # sin barra final
    assert cfg.usuario == "agente"
    assert cfg.clave == "secreta"
    assert cfg.carpetas == ["C:/datos/a", "C:/datos/b"]
    assert cfg.lote_size == 50
    assert cfg.estado_path == "estado.json"   # default
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `... -m pytest agent/tests/test_config.py -q`. Expected: FAIL — `ModuleNotFoundError: No module named 'sxml_agent.config'`.

- [ ] **Step 3: Crear `agent/sxml_agent/config.py`**

```python
"""Carga de configuración del agente desde un archivo TOML."""
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    backend_url: str
    usuario: str
    clave: str
    carpetas: list[str]
    lote_size: int = 100
    estado_path: str = "estado.json"


def cargar_config(path: str) -> Config:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return Config(
        backend_url=str(data["backend_url"]).rstrip("/"),
        usuario=str(data["usuario"]),
        clave=str(data["clave"]),
        carpetas=[str(c) for c in data["carpetas"]],
        lote_size=int(data.get("lote_size", 100)),
        estado_path=str(data.get("estado_path", "estado.json")),
    )
```

- [ ] **Step 4: Crear `agent/agent.example.toml`** (config de ejemplo)

```toml
# Configuración del agente de subida de XML. Copiar a agent.toml y completar.
backend_url = "http://localhost:8000"
usuario = "agente"
clave = "CAMBIAR"
# Carpetas a escanear recursivamente buscando .xml:
carpetas = [
  "C:/Users/Usuario/OneDrive/OFICINA/CONTAS/IVA",
]
lote_size = 100
estado_path = "estado.json"
```

- [ ] **Step 5: Correr, confirmar que PASA**

Run: `... -m pytest agent/tests/test_config.py -q`. Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add agent && git commit -m "feat(agente): config TOML + ejemplo"
```

---

## Tarea 4: `cliente_api` (login + subir_lote, httpx)

**Files:**
- Create: `agent/sxml_agent/cliente_api.py`
- Test: `agent/tests/test_cliente_api.py`

- [ ] **Step 1: Escribir el test que falla** `agent/tests/test_cliente_api.py`

```python
import httpx
import pytest
from sxml_agent.cliente_api import ApiClient, ApiError, NoAutorizado

def _api(handler):
    return ApiClient("http://x", client=httpx.Client(transport=httpx.MockTransport(handler)))

def test_login_ok():
    def handler(req):
        assert req.url.path == "/auth/login"
        return httpx.Response(200, json={"access_token": "TOK"})
    assert _api(handler).login("u", "p") == "TOK"

def test_login_falla_lanza_apierror():
    api = _api(lambda req: httpx.Response(401))
    with pytest.raises(ApiError):
        api.login("u", "bad")

def test_subir_lote_ok(tmp_path):
    f = tmp_path / "a.xml"; f.write_text("<a/>", encoding="utf-8")
    def handler(req):
        assert req.url.path == "/api/ingesta/lote"
        assert req.headers["authorization"] == "Bearer TOK"
        return httpx.Response(200, json={"total": 1, "nuevos": 1, "actualizados": 0,
                                         "omitidos": 0, "errores": 0, "archivos": []})
    rep = _api(handler).subir_lote("TOK", [f])
    assert rep["nuevos"] == 1

def test_subir_lote_401_lanza_noautorizado(tmp_path):
    f = tmp_path / "a.xml"; f.write_text("<a/>", encoding="utf-8")
    api = _api(lambda req: httpx.Response(401))
    with pytest.raises(NoAutorizado):
        api.subir_lote("TOK", [f])
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `... -m pytest agent/tests/test_cliente_api.py -q`. Expected: FAIL — `ModuleNotFoundError: No module named 'sxml_agent.cliente_api'`.

- [ ] **Step 3: Crear `agent/sxml_agent/cliente_api.py`**

```python
"""Cliente HTTP del backend: login (JWT) y subida de lotes a /api/ingesta/lote."""
from pathlib import Path
import httpx


class ApiError(Exception):
    """Error de comunicación con el backend."""


class NoAutorizado(ApiError):
    """El backend respondió 401 (token inválido o expirado)."""


class ApiClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=60.0)

    def login(self, usuario: str, clave: str) -> str:
        r = self._client.post(f"{self.base_url}/auth/login",
                              data={"username": usuario, "password": clave})
        if r.status_code != 200:
            raise ApiError(f"login falló: HTTP {r.status_code}")
        return r.json()["access_token"]

    def subir_lote(self, token: str, rutas: list[Path]) -> dict:
        files = [("archivos", (p.name, p.read_bytes(), "application/xml")) for p in rutas]
        r = self._client.post(f"{self.base_url}/api/ingesta/lote", files=files,
                              headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 401:
            raise NoAutorizado("token inválido o expirado")
        if r.status_code != 200:
            raise ApiError(f"subir_lote falló: HTTP {r.status_code}")
        return r.json()
```

- [ ] **Step 4: Correr, confirmar que PASA**

Run: `... -m pytest agent/tests/test_cliente_api.py -q`. Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add agent && git commit -m "feat(agente): cliente_api (login + subir_lote) con httpx"
```

---

## Tarea 5: `run` + `__main__` (orquestación + CLI)

**Files:**
- Create: `agent/sxml_agent/run.py`
- Create: `agent/sxml_agent/__main__.py`
- Test: `agent/tests/test_run.py`

- [ ] **Step 1: Escribir el test que falla** `agent/tests/test_run.py`

```python
import httpx
from pathlib import Path
from sxml_agent.run import ejecutar
from sxml_agent import run as run_mod
from sxml_agent import __main__ as cli
from sxml_agent.cliente_api import ApiClient
from sxml_agent.estado import Estado
from sxml_agent.escaner import hash_archivo

def _api(handler):
    return ApiClient("http://x", client=httpx.Client(transport=httpx.MockTransport(handler)))

def _cfg(tmp_path, carpeta, estado_path, lote_size=10):
    f = tmp_path / "agent.toml"
    f.write_text(
        f'backend_url = "http://x"\nusuario = "u"\nclave = "p"\n'
        f'carpetas = [{carpeta!r}]\nlote_size = {lote_size}\nestado_path = {estado_path!r}\n',
        encoding="utf-8")
    return str(f)

def _ok_handler(req):
    if req.url.path == "/auth/login":
        return httpx.Response(200, json={"access_token": "TOK"})
    if req.url.path == "/api/ingesta/lote":
        return httpx.Response(200, json={"total": 2, "nuevos": 2, "actualizados": 0,
                                         "omitidos": 0, "errores": 0, "archivos": []})
    return httpx.Response(404)

def test_run_sube_nuevos_y_omite_en_segunda_corrida(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    (datos / "b.xml").write_text("<b/>", encoding="utf-8")
    estado_path = str(tmp_path / "estado.json")
    cfg = _cfg(tmp_path, str(datos), estado_path)
    r1 = ejecutar(cfg, api=_api(_ok_handler))
    assert r1["escaneados"] == 2
    assert r1["enviados"] == 2
    assert r1["nuevos"] == 2
    assert r1["ya_subidos_local"] == 0
    r2 = ejecutar(cfg, api=_api(_ok_handler))
    assert r2["enviados"] == 0
    assert r2["ya_subidos_local"] == 2

def test_run_tanda_fallida_no_marca(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    estado_path = str(tmp_path / "estado.json")
    cfg = _cfg(tmp_path, str(datos), estado_path)
    def handler(req):
        if req.url.path == "/auth/login":
            return httpx.Response(200, json={"access_token": "TOK"})
        return httpx.Response(500)
    r = ejecutar(cfg, api=_api(handler))
    assert r["tandas_fallidas"] == 1
    assert r["enviados"] == 0
    e = Estado.cargar(estado_path)
    assert e.ya_subido(hash_archivo(datos / "a.xml")) is False

def test_run_relogin_en_401(tmp_path):
    datos = tmp_path / "datos"; datos.mkdir()
    (datos / "a.xml").write_text("<a/>", encoding="utf-8")
    cfg = _cfg(tmp_path, str(datos), str(tmp_path / "estado.json"))
    llamadas = {"login": 0, "lote": 0}
    def handler(req):
        if req.url.path == "/auth/login":
            llamadas["login"] += 1
            return httpx.Response(200, json={"access_token": "TOK"})
        llamadas["lote"] += 1
        if llamadas["lote"] == 1:
            return httpx.Response(401)
        return httpx.Response(200, json={"total": 1, "nuevos": 1, "actualizados": 0,
                                         "omitidos": 0, "errores": 0, "archivos": []})
    r = ejecutar(cfg, api=_api(handler))
    assert llamadas["login"] == 2
    assert r["enviados"] == 1
    assert r["nuevos"] == 1

def test_main_exit_code_ok(monkeypatch):
    monkeypatch.setattr(run_mod, "ejecutar", lambda cfg: {"tandas_fallidas": 0})
    assert cli.main(["--config", "x.toml"]) == 0

def test_main_exit_code_con_fallidas(monkeypatch):
    monkeypatch.setattr(run_mod, "ejecutar", lambda cfg: {"tandas_fallidas": 1})
    assert cli.main(["--config", "x.toml"]) == 1
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `... -m pytest agent/tests/test_run.py -q`. Expected: FAIL — `ModuleNotFoundError: No module named 'sxml_agent.run'`.

- [ ] **Step 3: Crear `agent/sxml_agent/run.py`**

```python
"""Orquestación de una corrida del agente: login, escaneo, dedup por hash, subida
por tandas y resumen."""
from itertools import islice
from sxml_agent.config import cargar_config
from sxml_agent.escaner import escanear, hash_archivo
from sxml_agent.estado import Estado
from sxml_agent.cliente_api import ApiClient, ApiError, NoAutorizado


def _tandas(items: list, n: int):
    it = iter(items)
    while (lote := list(islice(it, n))):
        yield lote


def ejecutar(config_path: str, api: ApiClient | None = None) -> dict:
    cfg = cargar_config(config_path)
    api = api or ApiClient(cfg.backend_url)
    token = api.login(cfg.usuario, cfg.clave)
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
                token = api.login(cfg.usuario, cfg.clave)   # re-login una vez
                rep = api.subir_lote(token, rutas)
        except ApiError:
            resumen["tandas_fallidas"] += 1
            continue   # no marcar: se reintenta la próxima corrida
        resumen["enviados"] += len(rutas)
        for _, h in tanda:
            estado.marcar(h)
        for k in ("nuevos", "actualizados", "omitidos", "errores"):
            resumen[k] += rep.get(k, 0)

    estado.guardar()
    return resumen
```

- [ ] **Step 4: Crear `agent/sxml_agent/__main__.py`**

```python
"""CLI del agente: python -m sxml_agent --config agent.toml"""
import argparse
import json
import sys
from sxml_agent import run


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sxml_agent",
                                     description="Sube los XML nuevos al backend Sistema XML.")
    parser.add_argument("--config", default="agent.toml", help="ruta al TOML de configuración")
    args = parser.parse_args(argv)
    try:
        resumen = run.ejecutar(args.config)
    except Exception as e:  # noqa: BLE001 - el CLI reporta cualquier fallo y sale con código
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    return 1 if resumen.get("tandas_fallidas") else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Correr, confirmar que PASA**

Run: `... -m pytest agent/tests/test_run.py -q`. Expected: PASS (5 passed).
Suite completa del agente: `... -m pytest agent/tests -q` → Expected: 15 passed.

- [ ] **Step 6: Commit**

```bash
git add agent && git commit -m "feat(agente): run (orquestacion) + CLI __main__"
```

---

## Self-Review (cobertura del spec)

- **Escaneo recursivo de `.xml` (ignora ruido) + hash de contenido** → Tarea 1. ✅
- **Estado local de hashes (dedup, persistente)** → Tarea 2. ✅
- **Config TOML (backend_url, usuario, clave, carpetas, lote_size, estado_path)** → Tarea 3 + `agent.example.toml`. ✅
- **Login (JWT) + subir_lote (multipart, Bearer) + 401→NoAutorizado** → Tarea 4. ✅
- **Orquestación: login→escanear→filtrar por hash→tandas→marcar tras 200→resumen; re-login en 401; tanda fallida no marca** → Tarea 5 (`run`). ✅
- **CLI un disparo + exit code** → Tarea 5 (`__main__`). ✅
- **Standalone (solo httpx+stdlib), tests con MockTransport** → todas; suite `agent/tests` independiente. ✅

**Consistencia de tipos:** `escanear(list[str])->list[Path]`, `hash_archivo(Path)->str`; `Estado.cargar(str)`, `ya_subido(str)->bool`, `marcar(str)`, `guardar()`; `Config`/`cargar_config(str)->Config`; `ApiClient(base_url, client=None)` con `login(u,c)->str` y `subir_lote(token, list[Path])->dict`, excepciones `ApiError`/`NoAutorizado`; `ejecutar(config_path, api=None)->dict` (resumen con `escaneados/ya_subidos_local/enviados/nuevos/actualizados/omitidos/errores/tandas_fallidas`); `__main__.main(argv)->int` llama `run.ejecutar`. Usados consistentemente. ✅

**Sin placeholders:** todo el código completo; comandos y valores esperados explícitos. ✅

## Diferido (rebanadas siguientes)
1C-2 watcher continuo; 1C-3 empaquetado `.exe` + Tarea Programada; 1C-4 UI/bandeja; endurecer credenciales (keyring/token de agente); reintentos con backoff.
