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
