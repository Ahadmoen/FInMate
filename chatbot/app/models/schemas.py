"""Backward-compatible schema aliases.

All new code should import from app.generation.schemas directly.
These aliases exist so any existing code importing from app.models.schemas
continues to work without modification.
"""
from app.generation.schemas import (
    LegacyChatRequest as ChatRequest,
    LegacyChatResponse as ChatResponse,
    LegacyIngestRequest as IngestRequest,
    LegacyIngestResponse as IngestResponse,
    LegacyStockCard as StockCard,
)

__all__ = ["ChatRequest", "ChatResponse", "IngestRequest", "IngestResponse", "StockCard"]
