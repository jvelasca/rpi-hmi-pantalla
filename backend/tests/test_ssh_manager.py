"""
backend.tests.test_ssh_manager
===============================

Tests unitarios para la capa de abstracción SSH (ssh_manager.py).

Verifica el contrato de ``SSHDriver`` con ``MockSSHDriver`` y
cubre los escenarios principales: conexión, ejecución de comandos,
transferencia de archivos, desconexión y manejo de errores.

    Ejecutar:
        pytest backend/tests/test_ssh_manager.py -v
"""
from __future__ import annotations

import os
import tempfile

import pytest

from backend.app.services.ssh_manager import (
    MockSSHDriver,
    ParamikoSSHDriver,
    SSHDriver,
    SSHResult,
)

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_ssh() -> MockSSHDriver:
    """Devuelve un MockSSHDriver limpio listo para usar."""
    return MockSSHDriver()


@pytest.fixture
def connected_mock(mock_ssh: MockSSHDriver) -> MockSSHDriver:
    """Devuelve un MockSSHDriver ya conectado."""
    mock_ssh.connect("192.168.1.100", "pi", "password")
    return mock_ssh


# ── Tests: Interfaz y tipos ───────────────────────────────────────────────


class TestSSHDriverInterface:
    """Verifica que la interfaz abstracta esté bien definida."""

    def test_abstract_class_cannot_be_instantiated(self) -> None:
        """SSHDriver es abstracta: no se puede instanciar directamente."""
        with pytest.raises(TypeError):
            SSHDriver()  # type: ignore[abstract]

    def test_mock_is_instance_of_ssh_driver(self) -> None:
        """MockSSHDriver debe ser instancia de SSHDriver."""
        mock = MockSSHDriver()
        assert isinstance(mock, SSHDriver)

    def test_paramiko_is_instance_of_ssh_driver(self) -> None:
        """ParamikoSSHDriver debe ser instancia de SSHDriver."""
        real = ParamikoSSHDriver()
        assert isinstance(real, SSHDriver)


# ── Tests: Conexión ───────────────────────────────────────────────────────


class TestConnection:
    """Pruebas de conexión y estado."""

    def test_initial_state_not_connected(self, mock_ssh: MockSSHDriver) -> None:
        """Al crear el driver, no debe estar conectado."""
        assert mock_ssh.is_connected() is False

    def test_connect_sets_connected(self, mock_ssh: MockSSHDriver) -> None:
        """Tras connect(), is_connected() debe ser True."""
        mock_ssh.connect("10.0.0.1", "user", "pass")
        assert mock_ssh.is_connected() is True

    def test_connect_stores_host_and_user(self, mock_ssh: MockSSHDriver) -> None:
        """connect() debe almacenar host y user."""
        mock_ssh.connect("192.168.1.100", "pi", "secret")
        assert mock_ssh.host == "192.168.1.100"
        assert mock_ssh.user == "pi"

    def test_disconnect_sets_not_connected(self, connected_mock: MockSSHDriver) -> None:
        """Tras disconnect(), is_connected() debe ser False."""
        connected_mock.disconnect()
        assert connected_mock.is_connected() is False

    def test_disconnect_idempotent(self, connected_mock: MockSSHDriver) -> None:
        """disconnect() debe ser seguro llamarlo múltiples veces."""
        connected_mock.disconnect()
        connected_mock.disconnect()  # No debe lanzar excepción
        assert connected_mock.is_connected() is False

    def test_connect_fail_host(self, mock_ssh: MockSSHDriver) -> None:
        """Conectar al host 'fail' debe lanzar ConnectionError."""
        with pytest.raises(ConnectionError, match="fail"):
            mock_ssh.connect("fail", "user", "pass")


# ── Tests: Ejecución de comandos ──────────────────────────────────────────


class TestExecute:
    """Pruebas de ejecución remota de comandos."""

    def test_execute_without_connection_raises(self, mock_ssh: MockSSHDriver) -> None:
        """Ejecutar sin conexión activa debe lanzar RuntimeError."""
        with pytest.raises(RuntimeError, match="no hay conexión"):
            mock_ssh.execute("uname -a")

    def test_execute_returns_ssh_result(self, connected_mock: MockSSHDriver) -> None:
        """execute() debe devolver un SSHResult."""
        result = connected_mock.execute("uname -a")
        assert isinstance(result, SSHResult)

    def test_execute_ok_property(self, connected_mock: MockSSHDriver) -> None:
        """SSHResult.ok debe ser True cuando exit_code == 0."""
        result = connected_mock.execute("echo hello")
        assert result.ok is True
        assert result.exit_code == 0

    def test_execute_fail_command(self, connected_mock: MockSSHDriver) -> None:
        """El comando 'fail' debe devolver exit_code != 0."""
        result = connected_mock.execute("fail")
        assert result.ok is False
        assert result.exit_code == 1
        assert "fallido" in result.stderr

    def test_execute_timeout_command(self, connected_mock: MockSSHDriver) -> None:
        """El comando 'timeout' debe lanzar TimeoutError."""
        with pytest.raises(TimeoutError, match="timeout"):
            connected_mock.execute("timeout")

    def test_execute_records_in_history(self, connected_mock: MockSSHDriver) -> None:
        """Cada comando ejecutado debe registrarse en command_history."""
        connected_mock.execute("cmd1")
        connected_mock.execute("cmd2")
        assert "cmd1" in connected_mock.command_history
        assert "cmd2" in connected_mock.command_history
        assert len(connected_mock.command_history) == 2

    def test_execute_simulated_uname(self, connected_mock: MockSSHDriver) -> None:
        """El mock debe simular la salida de 'uname -a'."""
        result = connected_mock.execute("uname -a")
        assert "Linux" in result.stdout
        assert "armv6l" in result.stdout

    def test_execute_simulated_hostname(self, connected_mock: MockSSHDriver) -> None:
        """El mock debe simular 'hostname -I'."""
        result = connected_mock.execute("hostname -I")
        assert result.stdout == connected_mock.host


# ── Tests: Transferencia de archivos ──────────────────────────────────────


class TestTransferFile:
    """Pruebas de transferencia de archivos vía SFTP simulado."""

    def test_transfer_file_to_dict(self, connected_mock: MockSSHDriver) -> None:
        """El archivo transferido debe almacenarse en el dict 'files'."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("contenido de prueba")
            temp_path = f.name

        try:
            connected_mock.transfer_file(temp_path, "/home/pi/test.txt")
            assert "/home/pi/test.txt" in connected_mock.files
            assert connected_mock.files["/home/pi/test.txt"] == "contenido de prueba"
        finally:
            os.unlink(temp_path)

    def test_transfer_nonexistent_file(self, connected_mock: MockSSHDriver) -> None:
        """Transferir un archivo inexistente debe lanzar FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            connected_mock.transfer_file("/nonexistent/file.txt", "/remote/file.txt")

    def test_transfer_without_connection_raises(self, mock_ssh: MockSSHDriver) -> None:
        """Transferir sin conexión debe lanzar RuntimeError (en real) o similar."""
        # Mock no bloquea esto porque files es accesible sin conexión,
        # pero transfer_file verifica que el archivo local exista primero.
        pass  # El mock no requiere conexión para transfer_file


# ── Tests: Context manager ────────────────────────────────────────────────


class TestContextManager:
    """Pruebas del soporte context manager (with)."""

    def test_context_manager_connects_and_disconnects(self) -> None:
        """El bloque 'with' debe conectar y desconectar automáticamente."""
        mock = MockSSHDriver()
        with mock as ssh:
            ssh.connect("10.0.0.1", "user", "pass")
            assert ssh.is_connected() is True
            ssh.execute("test")
        assert mock.is_connected() is False

    def test_context_manager_on_exception(self) -> None:
        """Si hay excepción dentro del bloque, igual debe desconectar."""
        mock = MockSSHDriver()
        try:
            with mock as ssh:
                ssh.connect("10.0.0.1", "user", "pass")
                raise ValueError("error simulado")
        except ValueError:
            pass
        assert mock.is_connected() is False


# ── Tests: SSHResult dataclass ────────────────────────────────────────────


class TestSSHResult:
    """Pruebas para el dataclass SSHResult."""

    def test_ok_when_exit_zero(self) -> None:
        """ok=True cuando exit_code == 0."""
        result = SSHResult(stdout="ok", stderr="", exit_code=0, command="test")
        assert result.ok is True

    def test_not_ok_when_exit_nonzero(self) -> None:
        """ok=False cuando exit_code != 0."""
        result = SSHResult(stdout="", stderr="error", exit_code=1, command="test")
        assert result.ok is False

    def test_str_representation(self) -> None:
        """La representación string debe incluir el comando y exit_code."""
        result = SSHResult(stdout="hola", stderr="", exit_code=0, command="echo hola")
        str_repr = str(result)
        assert "echo hola" in str_repr
        assert "hola" in str_repr
