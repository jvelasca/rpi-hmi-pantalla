"""
backend.tests.test_deploy_service
==================================

Tests unitarios para el servicio de despliegue (deploy_service.py).

Verifica las operaciones de despliegue usando ``MockSSHDriver`` para
simular una Raspberry Pi remota sin necesidad de hardware real.

    Ejecutar:
        pytest backend/tests/test_deploy_service.py -v
"""
from __future__ import annotations

import pytest

from backend.app.services.ssh_manager import MockSSHDriver, SSHResult
from backend.app.services.deploy_service import (
    DeployService,
    DeployStatus,
    NetworkScanner,
    ScanResult,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_ssh() -> MockSSHDriver:
    """Devuelve un MockSSHDriver conectado a una Pi simulada."""
    ssh = MockSSHDriver()
    ssh.connect("192.168.1.100", "pi", "password")
    return ssh


@pytest.fixture
def deploy_service(mock_ssh: MockSSHDriver) -> DeployService:
    """Devuelve un DeployService con driver mock conectado."""
    return DeployService(mock_ssh, remote_root="/home/pi/Rpi_Pantalla_V1")


# ── Tests: NetworkScanner ─────────────────────────────────────────────────


class TestNetworkScanner:
    """Pruebas para el escáner de red local."""

    def test_get_local_subnets_returns_list(self) -> None:
        """_get_local_subnets debe devolver una lista de subredes."""
        subnets = NetworkScanner._get_local_subnets()
        assert isinstance(subnets, list)
        assert len(subnets) > 0
        # Cada subred debe tener formato X.X.X (tres octetos)
        for subnet in subnets:
            parts = subnet.split(".")
            assert len(parts) == 3

    def test_check_ssh_localhost_closed(self) -> None:
        """Verificar SSH en localhost:22 — puede estar cerrado o abierto."""
        # Este test depende del entorno. Si el PC tiene SSH, devolverá True.
        result = NetworkScanner._check_ssh("127.0.0.1", port=22, timeout=0.5)
        # Solo verificamos que devuelve un bool
        assert isinstance(result, bool)

    def test_scan_returns_list(self) -> None:
        """scan() debe devolver una lista de ScanResult."""
        results = NetworkScanner.scan(timeout=0.3, max_hosts=3)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, ScanResult)
            assert r.ssh_available is True


# ── Tests: DeployService ──────────────────────────────────────────────────


class TestDeployService:
    """Pruebas para el servicio de despliegue."""

    def test_initialization(self, deploy_service: DeployService) -> None:
        """Debe inicializarse con remote_root y status_log vacío."""
        assert deploy_service.remote_root == "/home/pi/Rpi_Pantalla_V1"
        assert deploy_service.status_log == []

    def test_detect_raspberry_pi(self, deploy_service: DeployService) -> None:
        """detect_raspberry_pi() debe devolver una lista de ScanResult."""
        results = deploy_service.detect_raspberry_pi(timeout=0.3)
        assert isinstance(results, list)
        # Debe registrar el paso en status_log
        assert len(deploy_service.status_log) >= 1
        assert deploy_service.status_log[0].step == "detect"

    def test_setup_environment(self, deploy_service: DeployService) -> None:
        """setup_environment() debe ejecutar los 4 pasos."""
        steps = deploy_service.setup_environment()
        assert len(steps) == 4
        assert steps[0].step == "mkdir"
        assert steps[1].step == "install_system_deps"
        assert steps[2].step == "create_venv"
        assert steps[3].step == "pip_install"

    def test_deploy_app_empty(self, deploy_service: DeployService) -> None:
        """deploy_app() sin archivos locales devuelve fallos controlados."""
        # Usar un directorio temporal vacío como project_root
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            steps = deploy_service.deploy_app(project_root=tmpdir)
            # Todos los archivos deben fallar porque no existen
            assert len(steps) > 0
            # Al menos algunos deben tener success=False
            assert any(not s.success for s in steps)

    def test_run_diagnostics(self, deploy_service: DeployService) -> None:
        """run_diagnostics() debe devolver un DeployStatus."""
        status = deploy_service.run_diagnostics()
        assert isinstance(status, DeployStatus)
        assert status.step == "diagnostics"

    def test_health_check(self, deploy_service: DeployService) -> None:
        """health_check() debe devolver un DeployStatus."""
        status = deploy_service.health_check()
        assert isinstance(status, DeployStatus)
        assert status.step == "health_check"

    def test_start_backend(self, deploy_service: DeployService) -> None:
        """start_backend() debe devolver un DeployStatus con PID."""
        status = deploy_service.start_backend()
        assert isinstance(status, DeployStatus)
        assert status.step == "start_backend"

    def test_stop_backend(self, deploy_service: DeployService) -> None:
        """stop_backend() debe devolver un DeployStatus."""
        status = deploy_service.stop_backend()
        assert isinstance(status, DeployStatus)
        assert status.step == "stop_backend"

    def test_full_deploy(self, deploy_service: DeployService) -> None:
        """full_deploy() debe devolver diccionario con 4 claves."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            result = deploy_service.full_deploy(project_root=tmpdir)
            assert isinstance(result, dict)
            assert "environment" in result
            assert "deploy" in result
            assert "start" in result
            assert "health" in result

    def test_status_log_accumulates(self, deploy_service: DeployService) -> None:
        """Cada operación debe añadir entradas a status_log."""
        initial_count = len(deploy_service.status_log)
        deploy_service.health_check()
        deploy_service.run_diagnostics()
        assert len(deploy_service.status_log) >= initial_count + 2


# ── Tests: DeployStatus ───────────────────────────────────────────────────


class TestDeployStatus:
    """Pruebas para el dataclass DeployStatus."""

    def test_default_values(self) -> None:
        """Valores por defecto correctos."""
        status = DeployStatus(step="test", success=True, message="ok")
        assert status.output == ""
        assert status.duration_ms == 0.0

    def test_with_output(self) -> None:
        """Debe aceptar output y duration_ms."""
        status = DeployStatus(
            step="deploy",
            success=False,
            message="fallo",
            output="error details",
            duration_ms=150.5,
        )
        assert status.output == "error details"
        assert status.duration_ms == 150.5
