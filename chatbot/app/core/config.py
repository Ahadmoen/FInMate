from functools import lru_cache
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────
    app_name: str = "AIVA FinMate"
    debug: bool = False
    admin_api_key: str = "change-me"

    # ── Supabase ───────────────────────────────────────────────
    supabase_url: str = ""
    supabase_key: str = ""
    # Direct PostgreSQL URL — preferred for asyncpg
    # Supabase Dashboard → Settings → Database → Connection string → URI
    supabase_db_url: str = ""
    # Django Simple JWT verification — must match SECRET_KEY in the Django BE.
    # The frontend sends the access token from the Django login response.
    # Copy the value of SECRET_KEY from D:\FYP\FinMate-BE\config\settings.py
    django_secret_key: str = ""

    # ── Qdrant ─────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "psx_documents"

    # ── Redis ──────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── LLM ───────────────────────────────────────────────────
    llm_provider: Literal["anthropic", "openai", "groq"] = "groq"
    # Main generation model (Groq free tier)
    llm_model: str = "llama-3.3-70b-versatile"
    # Router uses a lighter model for lower latency
    router_model: str = "llama-3.1-8b-instant"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""

    # ── Embeddings ─────────────────────────────────────────────
    # "local"  → sentence-transformers all-MiniLM-L6-v2 (free, no API key)
    # "openai" → text-embedding-3-large (requires OPENAI_API_KEY)
    embedding_provider: Literal["openai", "local"] = "local"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384              # all-MiniLM-L6-v2 output dim
    embedding_batch_size: int = 64

    # ── Reranker ───────────────────────────────────────────────
    # "local"  → cross-encoder/ms-marco-MiniLM-L-6-v2 (free, no API key)
    # "cohere" → Cohere Rerank API (requires COHERE_API_KEY)
    reranker_provider: Literal["cohere", "local"] = "local"
    local_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    cohere_api_key: str = ""
    reranker_model: str = "rerank-english-v3.0"
    reranker_top_k: int = 8

    # ── Retrieval ──────────────────────────────────────────────
    vector_search_limit: int = 50
    hybrid_alpha: float = 0.5  # 0=sparse only, 1=dense only
    news_recency_days: int = 90
    news_half_life_days: float = 14.0
    filing_half_life_days: float = 180.0

    # ── Cache TTLs (seconds) ───────────────────────────────────
    cache_embedding_ttl: int = 86400 * 30   # 30 days
    cache_news_response_ttl: int = 300       # 5 min
    cache_filing_response_ttl: int = 3600    # 1 hour

    # ── PSX ticker corpus ──────────────────────────────────────
    psx_tickers: list[str] = Field(default=[
        "PSO", "NBP", "FFC", "ENGRO", "OGDC", "PPL", "HBL",
        "MCB", "UBL", "LUCK", "EFERT", "HUBC", "KAPCO", "KEL",
        "MARI", "POL", "TRG", "SYS", "NETSOL", "UNITY", "BAHL",
        "MEBL", "FABL", "SILK", "PIOC", "MLCF", "CHCC", "DGKC",
        "MUGHAL", "SSGC", "SINDM", "WHALE", "CYAN", "META",
    ])

    psx_company_names: dict[str, str] = Field(default={
        "PSO": "Pakistan State Oil",
        "NBP": "National Bank of Pakistan",
        "FFC": "Fauji Fertilizer Company",
        "ENGRO": "Engro Corporation",
        "OGDC": "Oil & Gas Development Company",
        "PPL": "Pakistan Petroleum Limited",
        "HBL": "Habib Bank Limited",
        "MCB": "MCB Bank Limited",
        "UBL": "United Bank Limited",
        "LUCK": "Lucky Cement",
        "EFERT": "Engro Fertilizers",
        "HUBC": "Hub Power Company",
        "KAPCO": "Kot Addu Power Company",
        "KEL": "K-Electric Limited",
        "MARI": "Mari Petroleum Company",
        "POL": "Pakistan Oilfields Limited",
        "TRG": "TRG Pakistan Limited",
        "SYS": "Systems Limited",
        "NETSOL": "NetSol Technologies",
        "UNITY": "Unity Foods",
        "BAHL": "Bank AL Habib",
        "MEBL": "Meezan Bank",
        "FABL": "Faysal Bank",
        "SILK": "Silkbank",
        "PIOC": "Pioneer Cement",
        "MLCF": "Maple Leaf Cement",
        "CHCC": "Cherat Cement",
        "DGKC": "DG Khan Cement",
        "MUGHAL": "Mughal Iron & Steel",
        "SSGC": "Sui Southern Gas Company",
        "SINDM": "Sindh Modaraba",
        "WHALE": "Whale Industries",
        "CYAN": "Cyan Limited",
        "META": "Meta Holdings",
    })

    @field_validator("psx_tickers", mode="before")
    @classmethod
    def parse_tickers(cls, v):
        if isinstance(v, str):
            return [t.strip() for t in v.split(",")]
        return v

    def get_company_name(self, ticker: str) -> str:
        return self.psx_company_names.get(ticker.upper(), ticker)

    @property
    def use_asyncpg(self) -> bool:
        return bool(self.supabase_db_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
