# Agente local 1C-2: watcher continuo (polling) — Diseño

> Documento de diseño (spec). El plan de implementación con pasos TDD va aparte:
> `docs/plans/2026-06-22-agente-watcher.md`. Segunda rebanada del agente local (1C).

## Objetivo

Que el agente corra **de forma continua**, re-escaneando las carpetas cada cierto
`intervalo` y subiendo los XML nuevos, sin que el operador tenga que dispararlo cada
vez. Reutiliza toda la lógica de 1C-1 (`run.ejecutar`): cada pasada es un disparo
completo con dedup por hash.

## Contexto

1C-1 dejó el agente standalone (`agent/sxml_agent/`): `run.ejecutar(config_path,
api=None) -> dict` hace una pasada (login → escanear → dedup por hash → subir por
tandas → resumen). `cargar_config` lee el TOML. El CLI `python -m sxml_agent
--config agent.toml` corre una pasada y sale. Suite del agente: 20 verdes.

## Decisiones de diseño

1. **Polling, no watchdog.** Un bucle que llama a `run.ejecutar` cada `intervalo`
   segundos. Razones: reutiliza 1C-1 (ya testeado); **sin dependencia nueva**
   (watchdog requeriría `pip` y la red bloquea el cert de PyPI); robusto ante eventos
   perdidos y la sync parcial de OneDrive (cada pasada re-escanea, el hash evita
   re-subir); fácil de testear. watchdog (tiempo real) queda diferido.
2. **Resiliencia por pasada.** Una pasada que falla (backend caído, error de red →
   ya envuelto en `ApiError` por 1C-1) se **loguea y el bucle continúa** a la
   siguiente; el watcher no muere por un fallo transitorio.
3. **Config se relee cada pasada** (lo hace `ejecutar` internamente), así editar
   `agent.toml` (p.ej. agregar carpetas) se toma sin reiniciar. El `intervalo` se lee
   una vez al inicio (cambiarlo requiere reiniciar — aceptable).
4. **Fail-fast al inicio.** `vigilar` valida la config una vez antes del bucle (un
   TOML mal configurado sale de inmediato, no entra en un bucle inútil).
5. **Logging** con el módulo `logging` (stdout, timestamped). El operador redirige a
   archivo o lo captura la Tarea Programada. Rotación de logs diferida.

## Componentes

- `config.py`: agregar campo `intervalo: int = 300` (segundos) + leerlo en
  `cargar_config` (`data.get("intervalo", 300)`). Agregar `intervalo` a
  `agent.example.toml`.
- `watcher.py` (nuevo):
  ```python
  def vigilar(config_path: str, *, intervalo: int | None = None, api=None,
              max_corridas: int | None = None, dormir=time.sleep) -> int:
      # valida config (fail-fast) y obtiene el intervalo efectivo
      # bucle: ejecutar(config_path, api) → log resumen / log error → dormir(intervalo)
      # max_corridas: None = indefinido; un entero acota el bucle (tests)
      # devuelve el número de corridas hechas
  ```
  Usa `from sxml_agent import run` y llama `run.ejecutar(...)` (parcheable en tests).
  `intervalo` efectivo = `intervalo` (override CLI) si se da, si no `cfg.intervalo`.
- `__main__.py`: agregar flags `--watch` (modo continuo) y `--intervalo` (override).
  Con `--watch` → configura `logging.basicConfig(level=INFO, timestamped)` y llama
  `watcher.vigilar(args.config, intervalo=args.intervalo)`; sin `--watch` → el disparo
  único actual. Ctrl+C (`KeyboardInterrupt`) → mensaje limpio, exit 0.

## Flujo (modo --watch)

```
cargar_config (fail-fast, intervalo)
  → bucle:
       ejecutar(config_path, api)   # 1C-1: login→escanear→dedup→tandas→resumen
       log.info(resumen)  |  log.error(si falla, y sigue)
       dormir(intervalo)
     (repetir; Ctrl+C → salir)
```

## Manejo de errores

- **Config inválida al inicio** → `vigilar` la propaga (el CLI imprime ERROR, exit 2);
  no se entra al bucle.
- **Pasada falla** (login/red/HTTP) → `except Exception` en el bucle → `log.error` →
  continúa a la próxima pasada (no aborta el watcher).
- **Ctrl+C** → salida limpia (exit 0), sin traceback.

## Estrategia de pruebas (TDD)

Con `max_corridas` + `dormir` inyectable (no-op) para acotar y no dormir de verdad;
`run.ejecutar` parcheado (monkeypatch) para no escanear/HTTP de verdad. Corren con el
venv del repo principal + `PYTHONPATH=agent`.

1. **`config.intervalo`** — default 300; leído del TOML cuando está.
2. **`vigilar` corre N veces** — `max_corridas=3`, `dormir` no-op, `run.ejecutar`
   parcheado → se llamó 3 veces.
3. **`vigilar` continúa si una pasada falla** — `run.ejecutar` lanza en la 1ª pasada
   → se loguea y el bucle sigue (2ª pasada corre).
4. **CLI `--watch`** — `main(["--config","x.toml","--watch"])` parcheando
   `watcher.vigilar` → se invoca con el config path; exit 0.

## Fuera de alcance (rebanadas siguientes)

- **watchdog / tiempo real** (1C-2b, si el polling resulta insuficiente).
- **Rotación de logs** a archivo.
- **1C-3:** empaquetado `.exe` + correr como servicio/Tarea Programada + endurecer
  credenciales.

## Riesgos / supuestos

- **Latencia = intervalo:** un XML nuevo se sube en la próxima pasada (hasta
  `intervalo` segundos después). Aceptable para el flujo de una firma (default 300s,
  configurable).
- **Solapamiento de pasadas:** el bucle es secuencial (una pasada termina antes de la
  siguiente), así que no hay corridas concurrentes; si una pasada tarda más que el
  intervalo, simplemente la próxima arranca al terminar + dormir. Sin riesgo de
  concurrencia.
