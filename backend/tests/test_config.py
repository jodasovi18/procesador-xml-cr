import pytest
from pydantic import ValidationError
from app.config import Settings


def test_prod_rechaza_secreto_default():
    with pytest.raises(ValidationError):
        Settings(env="production", jwt_secret="dev-secret-change-me")


def test_prod_rechaza_secreto_corto():
    with pytest.raises(ValidationError):
        Settings(env="production", jwt_secret="x" * 10)


def test_prod_acepta_secreto_valido():
    s = Settings(env="production", jwt_secret="x" * 40)
    assert s.env == "production"
    assert len(s.jwt_secret) >= 32


def test_dev_permite_default():
    s = Settings(env="dev", jwt_secret="dev-secret-change-me")
    assert s.jwt_secret == "dev-secret-change-me"
