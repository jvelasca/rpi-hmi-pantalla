"""Tests unitarios para la validacion de coherencia de red estatica.

Valida el helper privado ``_validate_static`` y la integracion con
``apply_static`` sin invocar ``nmcli`` real.
"""

from __future__ import annotations

from backend.app.services.network_service import _validate_static, network_service


class TestValidateStatic:
    """Tests del helper privado _validate_static."""

    def test_valid_ip_and_gateway_pass(self) -> None:
        """IP + gateway coherentes dentro de la misma subred -> None."""
        assert _validate_static("192.168.1.50", 24, "192.168.1.1") is None

    def test_gateway_outside_subnet_fails(self) -> None:
        """Gateway fuera de la subred -> mensaje de error."""
        error = _validate_static("192.168.1.250", 24, "10.0.0.1")
        assert error is not None
        assert "puerta de enlace" in error

    def test_ip_is_network_address_fails(self) -> None:
        """IP igual a la direccion de red -> error."""
        error = _validate_static("192.168.1.0", 24, "192.168.1.1")
        assert error is not None
        assert "red" in error

    def test_ip_is_broadcast_address_fails(self) -> None:
        """IP igual a la direccion de broadcast -> error."""
        error = _validate_static("192.168.1.255", 24, "192.168.1.1")
        assert error is not None
        assert "broadcast" in error

    def test_invalid_ip_fails(self) -> None:
        """IP invalida -> error claro (sin excepcion)."""
        error = _validate_static("999.999.999.999", 24, "192.168.1.1")
        assert error is not None
        assert "invalidos" in error

    def test_invalid_gateway_fails(self) -> None:
        """Gateway invalido -> error claro (sin excepcion)."""
        error = _validate_static("192.168.1.50", 24, "no-es-una-ip")
        assert error is not None
        assert "invalidos" in error

    def test_ipv6_rejected(self) -> None:
        """Una direccion IPv6 se rechaza como no IPv4."""
        error = _validate_static("2001:db8::1", 64, "2001:db8::2")
        assert error is not None

    def test_prefix_32_edge_case(self) -> None:
        """Caso limite /32: la IP coincide con red y broadcast -> error."""
        error = _validate_static("10.0.0.1", 32, "10.0.0.1")
        assert error is not None

    def test_prefix_32_with_different_gateway_fails(self) -> None:
        """En /32 el gateway no puede estar en otra direccion."""
        error = _validate_static("10.0.0.1", 32, "10.0.0.2")
        assert error is not None


class TestApplyStaticValidation:
    """La validacion se aplica en apply_static antes de tocar nmcli."""

    def test_incoherent_config_rejected_without_nmcli(self, monkeypatch) -> None:
        """Config incoherente -> success=False sin llamar a _run (nmcli)."""
        calls: list[list[str]] = []

        def fake_run(cmd: list[str], timeout: int = 10, sudo: bool = False) -> tuple[int, str, str]:
            calls.append(cmd)
            return 0, "", ""

        monkeypatch.setattr(network_service, "_run", fake_run)

        result = network_service.apply_static("192.168.1.250", 24, "10.0.0.1", None)

        assert result.success is False
        assert "puerta de enlace" in result.message
        assert calls == []
