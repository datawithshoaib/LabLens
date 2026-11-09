"""Validated application settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables without reading secrets into logs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "staging", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    frontend_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    database_url: str = "postgresql+asyncpg://lablens:lablens@localhost:5432/lablens"
    redis_url: str = "redis://localhost:6379/0"
    storage_backend: Literal["filesystem", "s3"] = "filesystem"
    storage_dir: Path = Path(".data/uploads")
    storage_bucket: str | None = None
    storage_endpoint_url: str | None = None
    storage_region: str = "us-east-1"
    storage_server_side_encryption: Literal["AES256", "aws:kms"] = "AES256"
    storage_kms_key_id: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    development_auth_token: SecretStr | None = None
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=100 * 1024 * 1024)
    max_pdf_pages: int = Field(default=100, ge=1, le=1000)
    upload_limit_per_hour: int = Field(default=10, ge=1, le=1000)

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/") or value.endswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/' and must not end with '/'")
        return value

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        safe_algorithms = {
            "RS256",
            "RS384",
            "RS512",
            "PS256",
            "PS384",
            "PS512",
            "ES256",
            "ES384",
            "ES512",
        }
        if not self.oidc_algorithms or not set(self.oidc_algorithms).issubset(safe_algorithms):
            raise ValueError("OIDC token verification must use asymmetric signing algorithms")
        if self.app_env == "production":
            oidc_issuer = self.oidc_issuer
            oidc_jwks_url = self.oidc_jwks_url
            required = {
                "OIDC_ISSUER": oidc_issuer,
                "OIDC_AUDIENCE": self.oidc_audience,
                "OIDC_JWKS_URL": oidc_jwks_url,
                "STORAGE_BUCKET": self.storage_bucket,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError("Production configuration is missing: " + ", ".join(missing))
            if self.development_auth_token is not None:
                raise ValueError("Development authentication must be disabled in production")
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("Production requires PostgreSQL with asyncpg")
            if "ssl=require" not in self.database_url and "ssl=true" not in self.database_url:
                raise ValueError("Production database connections must require TLS")
            if not self.redis_url.startswith("rediss://"):
                raise ValueError("Production Redis connections must use TLS")
            if self.storage_backend != "s3":
                raise ValueError("Production requires private S3-compatible object storage")
            if not oidc_issuer or not oidc_jwks_url:
                raise ValueError("Production OIDC issuer and JWKS URL are required")
            if self.storage_endpoint_url and not self.storage_endpoint_url.startswith("https://"):
                raise ValueError("Production object storage endpoints must use HTTPS")
            if not oidc_jwks_url.startswith("https://") or not oidc_issuer.startswith("https://"):
                raise ValueError("Production OIDC issuer and JWKS endpoints must use HTTPS")
            if not self.frontend_origins or any(
                not origin.startswith("https://") for origin in self.frontend_origins
            ):
                raise ValueError("Production frontend origins must use HTTPS")
            if not self.allowed_hosts or "*" in self.allowed_hosts:
                raise ValueError("Production allowed hosts must be explicitly configured")
            if self.storage_server_side_encryption == "aws:kms" and not self.storage_kms_key_id:
                raise ValueError("STORAGE_KMS_KEY_ID is required when KMS encryption is selected")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
