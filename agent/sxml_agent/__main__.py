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
