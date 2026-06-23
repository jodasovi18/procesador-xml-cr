# Agente local 1C-2: watcher continuo (polling) — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el agente corra en bucle (polling): re-escanea las carpetas cada `intervalo` segundos y sube los XML nuevos, reutilizando `run.ejecutar` (dedup por hash). Modo `--watch` en el CLI; el disparo único actual queda igual.

**Architecture:** Un módulo `watcher.py` con `vigilar()` que llama `run.ejecutar` en un bucle, durmiendo `intervalo` entre pasadas, logueando cada resumen y continuando ante fallos transitorios. `dormir`/`max_corridas` inyectables para tests. Sin dependencias nuevas.

**Tech Stack:** Python 3.11, stdlib (`time`, `logging`), pytest. (httpx ya presente, vía 1C-1.)

> **Diseño:** `docs/plans/2026-06-22-agente-watcher-design.md`.

---

## Contexto y entorno (CRÍTICO)

- **Venv:** `C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe`. Nunca `python` pelado.
- **Tests del agente** (desde la raíz del worktree, `PYTHONPATH`=`agent/`):
  - PowerShell: `$env:PYTHONPATH="C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\.claude\worktrees\priceless-engelbart-569a52\agent"; & "C:\Users\Usuario\Desktop\Sistemas\sistema-xml-web\backend\.venv\Scripts\python.exe" -m pytest agent/tests -q`
- Suite del agente actual: **20 verdes**. No romperlas.
- Reusa de 1C-1: `run.ejecutar(config_path, api=None) -> dict` (resumen con `tandas_fallidas`, etc.); `config.cargar_config(path) -> Config`. El CLI `__main__.main(argv)` corre una pasada y sale.

## File Structure

- Modify: `agent/sxml_agent/config.py` — agregar campo `intervalo`.
- Modify: `agent/agent.example.toml` — agregar `intervalo`.
- Create: `agent/sxml_agent/watcher.py` — `vigilar(...)`.
- Modify: `agent/sxml_agent/__main__.py` — flags `--watch` / `--intervalo`.
- Test: `agent/tests/test_config.py` (agregar), `agent/tests/test_watcher.py` (nuevo), `agent/tests/test_run.py` (agregar test de `--watch`).

---

## Tarea 1: `config.intervalo` + `watcher.vigilar`

**Files:**
- Modify: `agent/sxml_agent/config.py`
- Modify: `agent/agent.example.toml`
- Create: `agent/sxml_agent/watcher.py`
- Test: `agent/tests/test_config.py` (agregar), `agent/tests/test_watcher.py` (nuevo)

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `agent/tests/test_config.py`:
```python
def test_cargar_config_intervalo(tmp_path):
    f = tmp_path / "agent.toml"
    f.write_text('backend_url="http://x"\nusuario="u"\nclave="p"\ncarpetas=[]\n', encoding="utf-8")
    assert cargar_config(str(f)).intervalo == 300   # default
    f.write_text('backend_url="http://x"\nusuario="u"\nclave="p"\ncarpetas=[]\nintervalo=60\n',
                 encoding="utf-8")
    assert cargar_config(str(f)).intervalo == 60
```

Crear `agent/tests/test_watcher.py`:
```python
from sxml_agent import run, watcher

def _cfg(tmp_path, intervalo=300):
    f = tmp_path / "agent.toml"
    f.write_text(
        f'backend_url = "http://x"\nusuario = "u"\nclave = "p"\n'
        f'carpetas = []\nintervalo = {intervalo}\n', encoding="utf-8")
    return str(f)

def test_vigilar_corre_max_corridas(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    llamadas = []
    def fake(p, api=None):
        llamadas.append(p)
        return {"tandas_fallidas": 0}
    monkeypatch.setattr(run, "ejecutar", fake)
    n = watcher.vigilar(cfg, max_corridas=3, dormir=lambda s: None)
    assert n == 3
    assert len(llamadas) == 3

def test_vigilar_continua_si_una_pasada_falla(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    llamadas = []
    def fake(p, api=None):
        llamadas.append(p)
        if len(llamadas) == 1:
            raise RuntimeError("backend caído")
        return {"tandas_fallidas": 0}
    monkeypatch.setattr(run, "ejecutar", fake)
    n = watcher.vigilar(cfg, max_corridas=2, dormir=lambda s: None)
    assert n == 2          # siguió pese al fallo en la 1ª pasada
    assert len(llamadas) == 2
```

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `... -m pytest agent/tests/test_watcher.py agent/tests/test_config.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'sxml_agent.watcher'` (y `AttributeError`/assert en el test de intervalo si corriera config solo).

- [ ] **Step 3: Agregar `intervalo` a `agent/sxml_agent/config.py`**

En la dataclass `Config`, agregar el campo (después de `estado_path`):
```python
    intervalo: int = 300  # segundos entre pasadas en modo watch
```
En `cargar_config`, agregar al `Config(...)` que se construye:
```python
        intervalo=int(data.get("intervalo", 300)),
```

- [ ] **Step 4: Crear `agent/sxml_agent/watcher.py`**

```python
"""Watcher continuo: corre run.ejecutar en bucle cada `intervalo` segundos (polling).
Reutiliza 1C-1; una pasada que falla se loguea y el bucle continúa."""
import logging
import time
from sxml_agent.config import cargar_config
from sxml_agent import run

log = logging.getLogger("sxml_agent")


def vigilar(config_path: str, *, intervalo: int | None = None, api=None,
            max_corridas: int | None = None, dormir=time.sleep) -> int:
    """Corre `run.ejecutar` en bucle. `intervalo` override (si None usa cfg.intervalo).
    `max_corridas` None = indefinido; un entero acota el bucle (tests). Una pasada que
    falla se loguea y el bucle continúa. Devuelve el número de corridas hechas."""
    cfg = cargar_config(config_path)  # fail-fast + intervalo por defecto
    espera = intervalo if intervalo is not None else cfg.intervalo
    corridas = 0
    while max_corridas is None or corridas < max_corridas:
        try:
            resumen = run.ejecutar(config_path, api=api)
            log.info("corrida ok: %s", resumen)
        except Exception as e:  # noqa: BLE001 - un fallo de pasada no debe matar el watcher
            log.error("corrida falló: %s", e)
        corridas += 1
        if max_corridas is None or corridas < max_corridas:
            dormir(espera)
    return corridas
```

- [ ] **Step 5: Agregar `intervalo` a `agent/agent.example.toml`** (debajo de `lote_size`)

```toml
intervalo = 300  # segundos entre pasadas en modo --watch
```

- [ ] **Step 6: Correr, confirmar que PASA**

Run: `... -m pytest agent/tests/test_watcher.py agent/tests/test_config.py -q`. Expected: PASS (test_watcher 2 + test_config 3 = 5 passed).
Full agent suite: `... -m pytest agent/tests -q` → expect 23 passed (20 + 3).

- [ ] **Step 7: Commit**

```bash
git add agent && git commit -m "feat(agente): config.intervalo + watcher.vigilar (polling continuo)"
```

---

## Tarea 2: CLI `--watch`

**Files:**
- Modify: `agent/sxml_agent/__main__.py`
- Test: `agent/tests/test_run.py` (agregar)

- [ ] **Step 1: Escribir el test que falla** — agregar al final de `agent/tests/test_run.py`

```python
from sxml_agent import watcher as watcher_mod

def test_main_watch_llama_vigilar(monkeypatch):
    capt = {}
    def fake_vigilar(p, intervalo=None):
        capt["p"] = p
        capt["intervalo"] = intervalo
    monkeypatch.setattr(watcher_mod, "vigilar", fake_vigilar)
    assert cli.main(["--config", "x.toml", "--watch", "--intervalo", "60"]) == 0
    assert capt["p"] == "x.toml"
    assert capt["intervalo"] == 60
```

(`cli` ya está importado en `test_run.py` como `from sxml_agent import __main__ as cli`.)

- [ ] **Step 2: Correr, confirmar que FALLA**

Run: `... -m pytest agent/tests/test_run.py::test_main_watch_llama_vigilar -q`
Expected: FAIL — `argparse` no reconoce `--watch` (SystemExit/exit code ≠ 0) o `cli.main` no invoca `vigilar`.

- [ ] **Step 3: Reescribir `agent/sxml_agent/__main__.py`** (contenido completo)

```python
"""CLI del agente: python -m sxml_agent --config agent.toml [--watch [--intervalo N]]"""
import argparse
import json
import logging
import sys
from sxml_agent import run, watcher


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sxml_agent",
                                     description="Sube los XML nuevos al backend Sistema XML.")
    parser.add_argument("--config", default="agent.toml", help="ruta al TOML de configuración")
    parser.add_argument("--watch", action="store_true", help="modo continuo (polling cada intervalo)")
    parser.add_argument("--intervalo", type=int, default=None,
                        help="override del intervalo en segundos (modo watch)")
    args = parser.parse_args(argv)

    if args.watch:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(message)s")
        try:
            watcher.vigilar(args.config, intervalo=args.intervalo)
        except KeyboardInterrupt:
            print("Watcher detenido.", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - el CLI reporta cualquier fallo y sale con código
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        return 0

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

- [ ] **Step 4: Correr, confirmar que PASA**

Run: `... -m pytest agent/tests/test_run.py -q`. Expected: PASS (los previos de run/main + el nuevo).
Full agent suite: `... -m pytest agent/tests -q` → expect 24 passed (23 + 1).

- [ ] **Step 5: Commit**

```bash
git add agent && git commit -m "feat(agente): CLI --watch (modo continuo) + --intervalo"
```

---

## Self-Review (cobertura del spec)

- **Polling: `vigilar` llama `run.ejecutar` en bucle, duerme `intervalo`** → Tarea 1. ✅
- **Resiliencia por pasada (falla → log + continúa)** → Tarea 1 (`except` en el bucle; `test_vigilar_continua_si_una_pasada_falla`). ✅
- **Fail-fast de config + `intervalo` (config + override)** → Tarea 1 (`cargar_config` al inicio; param `intervalo`). ✅
- **`config.intervalo` (default 300, leído del TOML)** → Tarea 1 (`test_cargar_config_intervalo`). ✅
- **CLI `--watch` / `--intervalo`; disparo único intacto; Ctrl+C limpio** → Tarea 2. ✅
- **Logging timestamped** → Tarea 2 (`logging.basicConfig`). ✅
- **Sin dependencias nuevas; reusa 1C-1** → todo. ✅

**Consistencia de tipos:** `Config.intervalo: int`; `vigilar(config_path, *, intervalo=None, api=None, max_corridas=None, dormir=time.sleep) -> int` llamando `run.ejecutar(config_path, api=api)`; `__main__.main` invoca `watcher.vigilar(args.config, intervalo=args.intervalo)`. Tests parchean `run.ejecutar` (Tarea 1) y `watcher.vigilar` (Tarea 2). Consistente. ✅

**Sin placeholders:** código completo; comandos y conteos explícitos. ✅

## Diferido
watchdog/tiempo real, rotación de logs a archivo, 1C-3 (empaquetado `.exe` + servicio/Tarea Programada + endurecer credenciales).
