"""
Módulo de Configuración de la Aplicación.
Carga variables de entorno utilizando Pydantic Settings.
"""

import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Entorno de SUNAT
    SUNAT_ENV: Literal["BETA", "PRODUCTION"] = "BETA"
    SUNAT_BETA_URL: str = "https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService"
    SUNAT_PROD_URL: str = "https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService"

    # Datos fiscales del Emisor por defecto
    EMISOR_RUC: str = "20000000001"
    EMISOR_RAZON_SOCIAL: str = "EMPRESA DE PRUEBA S.A.C."
    EMISOR_NOMBRE_COMERCIAL: str = "MI TIENDA ONLINE"
    EMISOR_UBIGEO: str = "150101"
    EMISOR_DIRECCION: str = "AV. REPUBLICA DE PANAMA 3055 - SAN ISIDRO"
    EMISOR_CODIGO_ESTABLECIMIENTO: str = "0000"

    # Credenciales SOL (Usuario Secundario)
    SUNAT_USER: str = "MODDATOS"
    SUNAT_PASSWORD: str = "moddatos"

    # Certificado Digital PKCS#12 (.pfx / .p12)
    CERT_PATH: str = "app/certificates/certificate.pfx"
    CERT_PASSWORD: str = "123456"

    # Rutas de almacenamiento
    STORAGE_DIR: str = "app/storage"

    # Base de Datos SQLite por defecto (o PostgreSQL mediante DATABASE_URL)
    DATABASE_URL: str = "sqlite:///./app/storage/facturacion.db"

    # Parámetros del servidor
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def sunat_service_url(self) -> str:
        """Retorna la URL del Web Service según el entorno activo."""
        if self.SUNAT_ENV.upper() == "PRODUCTION":
            return self.SUNAT_PROD_URL
        return self.SUNAT_BETA_URL

    @property
    def sunat_auth_username(self) -> str:
        """
        Retorna el usuario con el formato requerido por SUNAT: {RUC}{USUARIO_SECUNDARIO}
        Por ejemplo: 20000000001MODDATOS
        """
        user = self.SUNAT_USER.strip()
        ruc = self.EMISOR_RUC.strip()
        if user.startswith(ruc):
            return user
        return f"{ruc}{user}"

    @property
    def dir_xml(self) -> str:
        path = os.path.join(self.STORAGE_DIR, "xml")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def dir_zip(self) -> str:
        path = os.path.join(self.STORAGE_DIR, "zip")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def dir_cdr(self) -> str:
        path = os.path.join(self.STORAGE_DIR, "cdr")
        os.makedirs(path, exist_ok=True)
        return path

    @property
    def dir_pdf(self) -> str:
        path = os.path.join(self.STORAGE_DIR, "pdf")
        os.makedirs(path, exist_ok=True)
        return path


settings = Settings()
