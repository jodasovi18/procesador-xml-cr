"""Cliente HTTP del backend: login (JWT) y subida de lotes a /api/ingesta/lote."""
from pathlib import Path
import httpx


class ApiError(Exception):
    """Error de comunicación con el backend."""


class NoAutorizado(ApiError):
    """El backend respondió 401 (token inválido o expirado)."""


class ApiClient:
    def __init__(self, base_url: str, client: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=60.0)

    def login(self, usuario: str, clave: str) -> str:
        r = self._client.post(f"{self.base_url}/auth/login",
                              data={"username": usuario, "password": clave})
        if r.status_code != 200:
            raise ApiError(f"login falló: HTTP {r.status_code}")
        return r.json()["access_token"]

    def subir_lote(self, token: str, rutas: list[Path]) -> dict:
        files = [("archivos", (p.name, p.read_bytes(), "application/xml")) for p in rutas]
        r = self._client.post(f"{self.base_url}/api/ingesta/lote", files=files,
                              headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 401:
            raise NoAutorizado("token inválido o expirado")
        if r.status_code != 200:
            raise ApiError(f"subir_lote falló: HTTP {r.status_code}")
        return r.json()
