# Agente local 1C-1: CLI de un disparo (scan + upload) — Diseño

> Documento de diseño (spec). El plan de implementación con pasos TDD va aparte:
> `docs/plans/2026-06-22-agente-cli.md`. Primera rebanada del agente local (1C).

## Objetivo

Un **agente CLI** que corre en la máquina del contador, **escanea carpetas**
configuradas buscando XML de comprobantes, y **sube los nuevos** al backend vía
`POST /api/ingesta/lote`, evitando re-subir lo ya enviado. Corre de un disparo (se
agenda con Tarea Programada de Windows). Es la primera rebanada de 1C.

## Contexto

- **No existe `agent/`** todavía (el repo tiene `backend/`, `docs/`).
- Los XML del cliente viven en OneDrive `OFICINA/CONTAS/IVA/<cliente>/<año>/...`,
  **mezclados con ruido** (PDFs de Acuse/Detalle/Constancia, subcarpetas BCR/BNCR,
  `.backups/`). El agente busca los `.xml` recursivamente.
- El backend ya expone lo necesario: `POST /auth/login` (form `username`/`password` →
  `access_token`) y `POST /api/ingesta/lote` (campo multipart `archivos`, rutea por
  cédula, omite MensajeHacienda, idempotente, devuelve resumen + detalle por archivo).
- El agente es **standalone**: solo depende de `httpx` (ya en el venv) + stdlib;
  habla con el backend por HTTP, **sin compartir código** con `backend/`.

## Decisiones de diseño

1. **Un disparo (run-and-exit).** Sin loop ni watcher; se agenda externamente. El
   watcher continuo es 1C-2.
2. **Dedup por hash de contenido (sha256) + estado local JSON.** Un archivo cuyo hash
   ya está en el estado se omite (no se lee entero de nuevo ni se sube). La
   idempotencia del backend es la red de seguridad (si se pierde el estado, re-subir
   es inofensivo).
3. **Sube todos los `.xml`; el backend filtra/rutea.** El agente no mira el tipo de
   comprobante ni la cédula — sube y el backend omite MensajeHacienda y asigna
   cliente/rol. Tras una tanda POST exitosa (HTTP 200) se **marcan todos** los hashes
   de esa tanda, sin importar el `estado` por archivo del backend (un XML inválido con
   ese mismo contenido fallaría igual; si lo corrigen, cambia el hash y se re-sube).
4. **Login una vez por corrida.** `POST /auth/login` al inicio; el JWT se usa para
   todas las tandas. Ante 401 en una tanda, re-login una vez y reintentar esa tanda.
5. **Tandas de `lote_size`** (default 100) archivos por request, para no mandar miles
   de archivos en un solo POST.
6. **Config TOML** (`tomllib`, stdlib) con `backend_url`, `usuario`, `clave`,
   `carpetas: [...]`, `lote_size`, `estado_path`. **Credenciales en texto plano**
   (aceptable para una corrida desatendida en una firma interna; keyring/token de
   agente diferido).

## Componentes (`agent/sxml_agent/`)

```
agent/
  sxml_agent/
    __init__.py
    config.py       # Config (dataclass) + cargar_config(path) -> Config  (tomllib)
    escaner.py      # escanear(carpetas) -> list[Path] (recursivo *.xml); hash_archivo(path) -> str (sha256)
    estado.py       # Estado: cargar(path), ya_subido(h), marcar(h), guardar()  (set de hashes en JSON)
    cliente_api.py  # ApiClient(base_url, client=None): login(usuario,clave)->token; subir_lote(token,rutas)->dict; ApiError
    run.py          # ejecutar(config_path, client=None) -> dict (resumen)
    __main__.py     # CLI: python -m sxml_agent --config agent.toml
  agent.example.toml
  tests/
```

- **`ApiClient`** acepta un `httpx.Client` inyectable (para tests con `MockTransport`).
  `login` hace `POST {base}/auth/login` (form) y devuelve `access_token`, o lanza
  `ApiError`. `subir_lote` hace `POST {base}/api/ingesta/lote` con los archivos como
  multipart `archivos` y `Authorization: Bearer`, devuelve el JSON del backend.
- **`run.ejecutar`** orquesta y devuelve el resumen; `__main__` lo imprime y fija el
  exit code (0 si no hubo errores de tanda, ≠0 si alguna tanda falló).

## Flujo

```
cargar_config → ApiClient.login → Estado.cargar
  → escanear(carpetas) = todos los .xml
  → nuevos = [p for p in todos if not estado.ya_subido(hash_archivo(p))]
  → para cada tanda de lote_size en nuevos:
        rep = api.subir_lote(token, rutas)        # 401 → re-login una vez y reintentar
        marcar(hash) de cada archivo de la tanda  # tras POST 200
        acumular rep["archivos"] al resumen
  → estado.guardar()
  → devolver resumen
```

**Resumen** (dict): `escaneados`, `ya_subidos_local` (omitidos por hash), `enviados`,
y del backend agregados `nuevos`, `actualizados`, `omitidos`, `errores`, más
`tandas_fallidas` (tandas que no pudieron postear).

## Manejo de errores

- **Config inválida / faltante** → mensaje claro, exit ≠ 0.
- **Login falla** → `ApiError`, mensaje, exit ≠ 0 (no se escanea).
- **Tanda falla** (red / 5xx) → se registra en `tandas_fallidas`, **no se marcan** esos
  hashes (se reintentan la próxima corrida), y se continúa con las demás tandas.
- **401 en una tanda** → re-login una vez y reintentar esa tanda; si sigue fallando,
  cuenta como tanda fallida.
- **Carpeta inexistente** en `carpetas` → se omite con aviso, no aborta.

## Estrategia de pruebas (TDD)

Todo con stdlib + `httpx` (ya en el venv). Corren con el venv del repo principal y
`PYTHONPATH` incluyendo `agent/` (ver memoria worktree-venv).

1. **`escaner`** — carpeta temporal con `.xml` (incl. anidados) + `.pdf` + subcarpeta →
   `escanear` devuelve solo los `.xml`; `hash_archivo` estable y sensible al contenido.
2. **`estado`** — `cargar` de archivo inexistente → vacío; `marcar` + `guardar` +
   recargar → `ya_subido` True; persistencia round-trip.
3. **`config`** — `cargar_config` de un TOML de ejemplo → campos correctos y defaults.
4. **`cliente_api`** — con `httpx.MockTransport`: `login` parsea `access_token`;
   `login` con 401 → `ApiError`; `subir_lote` postea multipart `archivos` con Bearer y
   devuelve el JSON simulado.
5. **`run` end-to-end** — `httpx.MockTransport` que simula login + `/lote`, carpeta
   temporal con 2 XML, estado temporal: 1ª corrida sube 2 (resumen) y marca hashes; 2ª
   corrida los omite (`ya_subidos_local == 2`, `enviados == 0`). Tanda que falla → no
   marca y aparece en `tandas_fallidas`.

## Fuera de alcance (rebanadas siguientes)

- **1C-2:** watcher continuo (watchdog, debounce, tiempo real).
- **1C-3:** empaquetado `.exe` (PyInstaller) + instalación como Tarea Programada/servicio.
- **1C-4:** UI/bandeja (estado, configuración visual) — posiblemente parte de 1D.
- Endurecimiento de credenciales (keyring del SO o token de agente del backend).
- Reintentos con backoff / cola persistente de fallidos.

## Riesgos / supuestos

- **Credenciales en texto plano** en `agent.toml` — aceptable para herramienta interna
  mono-firma en la máquina del contador; endurecer luego.
- **OneDrive sync:** un archivo a medio sincronizar podría leerse parcial. El hash de
  contenido lo detecta como distinto en la próxima corrida (se re-sube cuando esté
  completo); el backend valida el XML (un parcial → `error`, se reintenta al cambiar el
  hash). Aceptable para el modelo de un disparo.
- **Escaneo inicial grande:** la primera corrida puede subir años de XML; las tandas y
  el estado por hash lo hacen incremental de ahí en adelante.
