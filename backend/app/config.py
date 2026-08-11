"""Configuracion de la aplicacion via variables de entorno.

Usa pydantic-settings para cargar configuracion desde .env
con validacion estricta en tiempo de arranque.

Variables de entorno:
    RPI_HOST: IP de la Raspberry Pi (para deploy remoto)
    RPI_USER: Usuario SSH
    RPI_PASSWORD: Password SSH
    RPI_KEY_PATH: Ruta a clave privada SSH (opcional)
    RPI_PORT: Puerto SSH (default: 22)
    BACKEND_HOST: Host de escucha del servidor (default: 0.0.0.0)
    BACKEND_PORT: Puerto de escucha (default: 8000)
    ADMIN_API_KEY: Clave API para endpoints administrativos
    CORS_ORIGINS: Origenes CORS permitidos (separados por coma)
    ENABLE_DOCS: Habilitar Swagger/Redoc (default: false)
    LOG_LEVEL: Nivel de logging (default: info)
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion global de la aplicacion.

    Carga automaticamente desde .env en la raiz del proyecto.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # SSH (para deploy remoto)
    rpi_host: str = Field(default="", description="IP de la Raspberry Pi")
    rpi_user: str = Field(default="pi", description="Usuario SSH")
    rpi_password: str = Field(default="", description="Password SSH")
    rpi_key_path: str = Field(default="", description="Ruta clave privada SSH")
    rpi_port: int = Field(default=22, ge=1, le=65535, description="Puerto SSH")
    rpi_timeout: int = Field(default=15, ge=1, description="Timeout SSH en segundos")

    # Servidor
    backend_host: str = Field(default="0.0.0.0", description="Host de escucha")
    backend_port: int = Field(default=8000, ge=1, le=65535, description="Puerto HTTP")

    # Seguridad
    admin_api_key: str = Field(
        default="",
        description="API key para proteger endpoints administrativos /admin/*",
    )
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:8000",
        description="Origenes CORS permitidos (separados por coma)",
    )
    enable_docs: bool = Field(default=False, description="Habilitar documentacion OpenAPI")

    # Logging
    log_level: str = Field(default="info", description="Nivel de logging")

    @property
    def cors_origin_list(self) -> list[str]:
        """Devuelve la lista de origenes CORS."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Singleton
settings = Settings()
"""Instancia unica de configuracion."""
