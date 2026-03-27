"""
Central application settings loaded from environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DatabaseSettings:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    name: str = os.getenv("DB_NAME", "phoenician")
    user: str = os.getenv("DB_USER", "phoenician")
    password: str = os.getenv("DB_PASSWORD", "")
    ssl: str = os.getenv("DB_SSL", "")

    @property
    def dsn(self) -> str:
        from urllib.parse import quote_plus
        base = f"postgresql+asyncpg://{quote_plus(self.user)}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.name}"
        if self.ssl:
            base += f"?ssl={self.ssl}"
        return base

    @property
    def sync_dsn(self) -> str:
        from urllib.parse import quote_plus
        base = f"postgresql://{quote_plus(self.user)}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.name}"
        if self.ssl:
            base += f"?sslmode={self.ssl}"
        return base


@dataclass(frozen=True)
class RedisSettings:
    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    db: int = int(os.getenv("REDIS_DB", "0"))

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass(frozen=True)
class LLMSettings:
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    perplexity_api_key: str = os.getenv("PERPLEXITY_API_KEY", "")

    # Model choices
    primary_model: str = os.getenv("PRIMARY_LLM", "claude-sonnet-4-6")
    memo_model: str = os.getenv("MEMO_LLM", "claude-opus-4-6")
    extraction_model: str = os.getenv("EXTRACTION_LLM", "gpt-4.1-mini")
    perplexity_model: str = os.getenv("PERPLEXITY_MODEL", "sonar-deep-research")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "1536"))


@dataclass(frozen=True)
class VectorStoreSettings:
    backend: str = os.getenv("VECTOR_BACKEND", "pgvector")  # "pgvector" | "qdrant"
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    collection_name: str = os.getenv("VECTOR_COLLECTION", "documents")


@dataclass(frozen=True)
class IngestionSettings:
    sec_edgar_user_agent: str = os.getenv("SEC_EDGAR_USER_AGENT", "PhoenicianCapital admin@phoenician.capital")
    sec_rate_limit_rps: float = float(os.getenv("SEC_RATE_LIMIT_RPS", "10"))
    news_api_key: str = os.getenv("NEWS_API_KEY", "")
    polygon_api_key: str = os.getenv("POLYGON_API_KEY", "")
    fmp_api_key: str = os.getenv("FMP_API_KEY", "")


@dataclass(frozen=True)
class ScoringSettings:
    weights_file: Path = _ROOT / "src" / "config" / "scoring_weights.yaml"
    # Single authoritative market cap range — used everywhere
    min_market_cap: float = float(os.getenv("MIN_MARKET_CAP", "100_000_000"))
    max_market_cap: float = float(os.getenv("MAX_MARKET_CAP", "5_000_000_000"))
    # Kept for backward compat — alias to min/max
    @property
    def hard_min_market_cap(self) -> float:
        return self.min_market_cap
    @property
    def hard_max_market_cap(self) -> float:
        return self.max_market_cap


@dataclass(frozen=True)
class EmailSettings:
    smtp_host: str = os.getenv("SMTP_HOST", "smtp.office365.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "rr@phoeniciancapital.com")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    from_address: str = os.getenv("EMAIL_FROM", "rr@phoeniciancapital.com")
    digest_recipient: str = os.getenv("DIGEST_RECIPIENT", "roy.rizkallah@hotmail.com")

    @property
    def configured(self) -> bool:
        return bool(self.smtp_password and self.smtp_user)


@dataclass(frozen=True)
class Settings:
    project_root: Path = _ROOT
    env: str = os.getenv("APP_ENV", "development")
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    vector: VectorStoreSettings = field(default_factory=VectorStoreSettings)
    ingestion: IngestionSettings = field(default_factory=IngestionSettings)
    scoring: ScoringSettings = field(default_factory=ScoringSettings)
    email: EmailSettings = field(default_factory=EmailSettings)


settings = Settings()
