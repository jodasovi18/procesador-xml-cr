# Agente local 1C-3b: empaquetado (.exe + Tarea Programada) — Diseño

> Documento de diseño (spec). Fase atípica: entregable de **scripts + docs** (sin tests
> unitarios; verificación por revisión). El build/instalación reales se hacen en la
> máquina de despliegue.

## Objetivo

Permitir desplegar el agente en la máquina del contador como un **`.exe` autónomo**
(sin requerir Python instalado) que corre **automáticamente** vía el Programador de
tareas de Windows, subiendo los XML nuevos cada cierto intervalo.

## Contexto

- El agente (`agent/sxml_agent/`, 1C-1/1C-2/1C-3a) es un CLI standalone: `python -m
  sxml_agent --config agent.toml` corre un disparo (escanea + sube); `--watch` corre en
  bucle. Auth por `token` de agente (1C-3a) o usuario/clave. Depende solo de `httpx` +
  stdlib.
- No hay config de build todavía. PyInstaller no está instalado en el venv.
- Decisiones del usuario para esta fase: **scripts + docs** (sin construir el `.exe`
  acá); **run model = Tarea Programada de un disparo cada N min** (el scheduler es el
  bucle; no se usa `--watch` en el despliegue).

## Decisiones de diseño

1. **Entry point dedicado `run_agent.py`** para PyInstaller (en vez de empaquetar el
   `__main__.py` de un paquete, que tiene sutilezas de path). Reusa el CLI: `from
   sxml_agent.__main__ import main; raise SystemExit(main())`. Sin duplicar lógica.
2. **Build one-file** con PyInstaller → `dist/sxml_agent.exe`. Script `build.ps1` que
   instala pyinstaller si falta (con los `--trusted-host` de la red) y corre el build.
3. **Tarea Programada de un disparo cada N min** (`Register-ScheduledTask`): corre
   `sxml_agent.exe --config <ruta>` (sin `--watch`). El scheduler maneja el intervalo,
   los reinicios y la supervivencia a reboots. Más robusto que un proceso largo.
4. **Sin tests unitarios** (es empaquetado + scripts + docs). Verificación por revisión
   de la sintaxis y los flags. El build/instalación reales se corren en la máquina de
   despliegue siguiendo el README.

## Componentes (en `agent/`)

### `run_agent.py`
```python
from sxml_agent.__main__ import main
raise SystemExit(main())
```
Entry point para el build (PyInstaller analiza desde `agent/`, así `sxml_agent` resuelve).

### `build.ps1`
- Verifica que pyinstaller esté disponible; si no, lo instala:
  `pip install pyinstaller --trusted-host pypi.org --trusted-host files.pythonhosted.org`
  (usando el intérprete del venv; documentar cuál).
- Corre desde `agent/`: `pyinstaller --onefile --name sxml_agent --clean run_agent.py`.
- Resultado: `agent/dist/sxml_agent.exe`. Imprime la ruta final y un recordatorio de
  copiar `agent.toml` junto al `.exe`.
- Parámetros: `-Python` (ruta al intérprete; default el venv del repo).

### `instalar-tarea.ps1`
- `-Accion install|uninstall` (default install); `-ExePath`, `-ConfigPath`,
  `-IntervaloMin` (default 30), `-NombreTarea` (default "SistemaXML-Agente").
- **install**: crea una acción `sxml_agent.exe --config <ConfigPath>`, un trigger que
  repite cada `IntervaloMin` minutos (indefinido), corre con el usuario actual,
  `-StartWhenAvailable` (recupera corridas perdidas tras suspensión), y registra con
  `Register-ScheduledTask` (reemplaza si ya existe). Valida que `ExePath`/`ConfigPath`
  existan.
- **uninstall**: `Unregister-ScheduledTask -TaskName <NombreTarea> -Confirm:$false`.
- Imprime el estado resultante (`Get-ScheduledTask`).

### `README.md` (guía del operador)
Secciones: **Requisitos** (para build: Python + el venv; para correr: solo el `.exe`).
**Build** (`build.ps1`). **Configurar** `agent.toml` (`backend_url`, `token` obtenido con
`POST /api/agent-tokens` —admin—, `carpetas`; alternativa usuario/clave). **Instalar** la
Tarea Programada (`instalar-tarea.ps1`) + cómo desinstalar. **Operar**: dónde queda
`estado.json` (dedup por hash de contenido), cómo ver el resultado (redirigir la salida a
un log), idempotencia (re-subir es inofensivo). **Revocar** el token (`DELETE
/api/agent-tokens/{id}`). **Troubleshooting** (errores comunes: config inválida, backend
inalcanzable, token revocado → 401, carpeta inexistente).

## Verificación

Por **revisión** (no hay tests automáticos): sintaxis PowerShell válida; flags de
PyInstaller (`--onefile --name --clean`) correctos; `Register-ScheduledTask` con trigger
de repetición y acción correctos; `run_agent.py` importa el `main` existente; el README es
completo y los comandos coinciden con los scripts. El build real (`build.ps1`) y la
instalación (`instalar-tarea.ps1`) se ejecutan en la máquina de despliegue.

## Fuera de alcance / diferido

- **Firma de código** del `.exe` (evita warnings de SmartScreen) e **instalador MSI**.
- Correr como **servicio de Windows** (en vez de Tarea Programada).
- **keyring** para el token (hoy en `agent.toml` en texto plano, revocable).
- CI que construya el `.exe` automáticamente.

## Riesgos / supuestos

- **No verificado por ejecución acá:** los scripts se entregan revisados pero el build y
  la instalación se prueban recién en la máquina de despliegue. El README guía ese paso.
- **PyInstaller + red:** instalar pyinstaller requiere los `--trusted-host`; si la red de
  despliegue también bloquea PyPI, el operador necesita pyinstaller pre-instalado o un
  wheel local (documentar como nota).
- **SmartScreen:** un `.exe` sin firmar puede disparar advertencias de Windows; se
  documenta cómo proceder (firma de código queda diferida).
