"""Entry point para PyInstaller: empaqueta el CLI del agente como un ejecutable.

Se construye con build.ps1 (`pyinstaller --onefile run_agent.py`). Reusa el CLI de
`sxml_agent.__main__` sin duplicar lógica."""
from sxml_agent.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
