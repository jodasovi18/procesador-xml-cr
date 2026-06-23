import httpx
import pytest
from sxml_agent.cliente_api import ApiClient, ApiError, NoAutorizado

def _api(handler):
    return ApiClient("http://x", client=httpx.Client(transport=httpx.MockTransport(handler)))

def test_login_ok():
    def handler(req):
        assert req.url.path == "/auth/login"
        return httpx.Response(200, json={"access_token": "TOK"})
    assert _api(handler).login("u", "p") == "TOK"

def test_login_falla_lanza_apierror():
    api = _api(lambda req: httpx.Response(401))
    with pytest.raises(ApiError):
        api.login("u", "bad")

def test_subir_lote_ok(tmp_path):
    f = tmp_path / "a.xml"; f.write_text("<a/>", encoding="utf-8")
    def handler(req):
        assert req.url.path == "/api/ingesta/lote"
        assert req.headers["authorization"] == "Bearer TOK"
        return httpx.Response(200, json={"total": 1, "nuevos": 1, "actualizados": 0,
                                         "omitidos": 0, "errores": 0, "archivos": []})
    rep = _api(handler).subir_lote("TOK", [f])
    assert rep["nuevos"] == 1

def test_subir_lote_401_lanza_noautorizado(tmp_path):
    f = tmp_path / "a.xml"; f.write_text("<a/>", encoding="utf-8")
    api = _api(lambda req: httpx.Response(401))
    with pytest.raises(NoAutorizado):
        api.subir_lote("TOK", [f])

def test_subir_lote_500_lanza_apierror(tmp_path):
    f = tmp_path / "a.xml"; f.write_text("<a/>", encoding="utf-8")
    api = _api(lambda req: httpx.Response(500, text="boom"))
    with pytest.raises(ApiError):
        api.subir_lote("TOK", [f])

def test_subir_lote_error_conexion_lanza_apierror(tmp_path):
    f = tmp_path / "a.xml"; f.write_text("<a/>", encoding="utf-8")
    def handler(req):
        raise httpx.ConnectError("sin red")
    with pytest.raises(ApiError):
        _api(handler).subir_lote("TOK", [f])
