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
