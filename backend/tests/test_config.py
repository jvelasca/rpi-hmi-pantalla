"""Tests para Settings de configuracion (pydantic-settings).
Valida defaults, seguridad, y carga de .env.
"""

from __future__ import annotations

import logging

from backend.app.config import Settings

# ── Helper: create a fresh Settings instance ───────────────────


def _new_settings(**overrides) -> Settings:
    """Crea una instancia de Settings con overrides, sin tocar el .env real."""
    return Settings(**overrides)


# ── Defaults ───────────────────────────────────────────────────


class TestSettingsDefaults:
    """Validacion de valores por defecto."""

    def test_default_values(self):
        """Los valores por defecto de Settings deben ser los esperados."""
        s = _new_settings(enable_admin_api=False)
        assert s.backend_host == "0.0.0.0"
        assert s.backend_port == 8000
        assert s.rpi_user == "pi"
        assert s.rpi_port == 22
        assert s.rpi_timeout == 15
        assert s.log_level == "info"
        assert s.enable_docs is False
        assert s.enable_admin_api is False
        assert s.db_path == "data/state.db"

    def test_cors_origin_list_splits_comma(self):
        """cors_origin_list debe dividir por coma y limpiar espacios."""
        s = _new_settings(cors_origins="a,b,c")
        assert s.cors_origin_list == ["a", "b", "c"]

    def test_cors_origin_list_empty_string(self):
        """Un string vacio produce lista vacia."""
        s = _new_settings(cors_origins="")
        assert s.cors_origin_list == []

    def test_cors_origin_list_trims_whitespace(self):
        """Los espacios alrededor de las comas se eliminan."""
        s = _new_settings(cors_origins=" http://a.com , http://b.com ")
        assert s.cors_origin_list == ["http://a.com", "http://b.com"]


# ── Seguridad ──────────────────────────────────────────────────


class TestSettingsSecurity:
    """Validaciones de seguridad en model_post_init."""

    def test_model_post_init_warns_no_api_key(self, caplog):
        """enable_admin_api=True sin admin_api_key debe loguear critical."""
        with caplog.at_level(logging.CRITICAL, logger="rpi_hmi.config"):
            _new_settings(enable_admin_api=True, admin_api_key="")
        assert "ADMIN_API_KEY no configurada" in caplog.text

    def test_model_post_init_warns_default_key(self, caplog):
        """admin_api_key con valor por defecto debe loguear critical."""
        with caplog.at_level(logging.CRITICAL, logger="rpi_hmi.config"):
            _new_settings(
                enable_admin_api=True,
                admin_api_key="cambia-esto-por-una-clave-segura",
            )
        assert "ADMIN_API_KEY tiene el valor por defecto" in caplog.text

    def test_model_post_init_warns_short_key(self, caplog):
        """admin_api_key de menos de 16 chars debe loguear warning."""
        with caplog.at_level(logging.WARNING, logger="rpi_hmi.config"):
            _new_settings(enable_admin_api=True, admin_api_key="corta123")
        assert "ADMIN_API_KEY es demasiado corta" in caplog.text
        assert "8 caracteres" in caplog.text

    def test_model_post_init_passes_long_key(self, caplog):
        """admin_api_key de 32+ chars no debe generar warning."""
        long_key = "a" * 32
        with caplog.at_level(logging.WARNING, logger="rpi_hmi.config"):
            _new_settings(enable_admin_api=True, admin_api_key=long_key)
        # No debe haber mensajes de warning ni critical sobre API key
        assert "ADMIN_API_KEY" not in caplog.text

    def test_model_post_init_no_warning_when_admin_disabled(self, caplog):
        """Sin enable_admin_api, no se valida la API key."""
        with caplog.at_level(logging.WARNING, logger="rpi_hmi.config"):
            _new_settings(enable_admin_api=False, admin_api_key="")
        assert "ADMIN_API_KEY" not in caplog.text


# ── Env loading ────────────────────────────────────────────────


class TestSettingsEnvLoading:
    """Pruebas de carga desde variables de entorno (pydantic-settings)."""

    def test_env_file_loading(self, monkeypatch):
        """Variables de entorno sobreescriben defaults en Settings."""
        monkeypatch.setenv("RPI_HOST", "192.168.1.100")
        monkeypatch.setenv("RPI_PORT", "2222")
        s = Settings()
        assert s.rpi_host == "192.168.1.100"
        assert s.rpi_port == 2222

    def test_env_file_overrides_defaults(self, monkeypatch):
        """Los valores de entorno sobreescriben los defaults."""
        monkeypatch.setenv("BACKEND_PORT", "9000")
        monkeypatch.setenv("LOG_LEVEL", "debug")
        s = Settings()
        assert s.backend_port == 9000
        assert s.log_level == "debug"
