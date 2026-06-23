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
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"subidos": sorted(self._hashes)}, ensure_ascii=False),
            encoding="utf-8")
