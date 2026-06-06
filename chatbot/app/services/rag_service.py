from app.services.vector_store import search_documents, add_documents
from app.services.supabase_service import (
    get_stock_data,
    get_stock_signal,
    get_stock_forecast,
    get_stock_news,
    get_top_gainers,
    get_top_losers,
    get_buy_signals
)
from app.services.gemini_service import (
    build_rag_prompt,
    generate_response,
    detect_ticker,
    is_stock_query
)
from app.utils.logger import logger
from typing import Dict, Optional, Tuple
import uuid


async def process_chat(
    message: str,
    user_name: str,
    user_id: Optional[str] = None
) -> Dict:

    logger.info(f"Processing chat from {user_name}: {message}")

    # ── Step 1: Detect ticker and query type ──────────────────
    ticker = detect_ticker(message)
    stock_query = is_stock_query(message)
    query_type = "stock" if (ticker or stock_query) else "general"

    logger.info(f"Query type: {query_type}, Ticker: {ticker}")
    print(f"[DEBUG] detect_ticker result: '{ticker}' | is_stock_query: {stock_query}")

    # ── Step 2: RAG - Search vector store ─────────────────────
    rag_context = search_documents(message, n_results=3)

    # ── Step 3: Fetch live data from Supabase ─────────────────
    db_data = None
    signal_data = None
    news_data = None
    forecast_data = None
    stock_card = None

    if ticker:
        db_data = get_stock_data(ticker)
        signal_data = get_stock_signal(ticker)
        forecast_data = get_stock_forecast(ticker)
        news_data = get_stock_news(ticker, limit=3)

        # Build stock card for UI
        if db_data:
            open_price = db_data.get('open_price', 0)
            close = db_data.get('close', 0)
            change_pct = 0
            if open_price and open_price > 0:
                change_pct = round(((close - open_price) / open_price) * 100, 2)

            stock_card = {
                "type": "stock_card",
                "data": {
                    "company_name": get_company_name(ticker),
                    "symbol": ticker,
                    "open_price": db_data.get("open_price"),
                    "close_price": db_data.get("close"),
                    "high": db_data.get("high"),
                    "low": db_data.get("low"),
                    "volume": db_data.get("volume"),
                    "change_pct": change_pct,
                    "signal": signal_data.get("signal") if signal_data else None,
                    "signal_confidence": round(signal_data.get("confidence", 0) * 100, 1) if signal_data else None,
                    "forecast_direction": forecast_data.get("direction") if forecast_data else None,
                    "predicted_price": forecast_data.get("predicted_price") if forecast_data else None,
                    "forecast_confidence": round(forecast_data.get("confidence", 0) * 100, 1) if forecast_data else None,
                }
            }

    elif "gainer" in message.lower():
        print("Fetching gainers...")
        db_data = {"gainers": get_top_gainers(5)}
        query_type = "gainers"

    elif "loser" in message.lower():
        db_data = {"losers": get_top_losers(5)}
        query_type = "losers"

    elif "buy signal" in message.lower():
        db_data = {"buy_signals": get_buy_signals(5)}
        query_type = "signals"

    print("db data123..." , db_data)    

    # ── Step 4: Build prompt ───────────────────────────────────
    prompt = build_rag_prompt(
        user_name=user_name,
        user_query=message,
        rag_context=rag_context,
        db_data=db_data,
        signal_data=signal_data,
        news_data=news_data,
        forecast_data=forecast_data,
    )

    # ── Step 5: Generate response ──────────────────────────────
    answer = await generate_response(prompt)

    logger.info(f"Query logged | User: {user_name} | Type: {query_type} | Ticker: {ticker}")

    return {
        "answer": answer,
        "card": stock_card,
        "query_type": query_type,
        "sources": [doc["metadata"] for doc in rag_context] if rag_context else []
    }


def get_company_name(ticker: str) -> str:
    company_names = {
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
        "MUGHAL": "Mughal Iron & Steel",
        "SSGC": "Sui Southern Gas Company",
        "WHALE": "Whale Industries",
    }
    return company_names.get(ticker.upper(), ticker)


async def ingest_text(
    text: str,
    source: str,
    metadata: Optional[Dict] = None
) -> Tuple[bool, int]:
    try:
        chunks = split_into_chunks(text, chunk_size=500, overlap=50)
        logger.info(f"Split text into {len(chunks)} chunks")

        metadatas = []
        ids = []
        for i, chunk in enumerate(chunks):
            metadatas.append({
                "source": source,
                "chunk_index": i,
                **(metadata or {})
            })
            ids.append(f"{source}_{uuid.uuid4().hex[:8]}_{i}")

        success = add_documents(chunks, metadatas, ids)
        return success, len(chunks)

    except Exception as e:
        logger.error(f"Error ingesting text: {e}")
        return False, 0


def split_into_chunks(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks