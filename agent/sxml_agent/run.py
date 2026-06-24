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
                    raise
                token = api.login(cfg.usuario, cfg.clave)
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
