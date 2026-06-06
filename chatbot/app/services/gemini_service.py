import requests
from app.utils.logger import logger
from typing import List, Dict, Optional
import os

# ── Initialize Groq ───────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"


def build_rag_prompt(
    user_name: str,
    user_query: str,
    rag_context: List[Dict],
    db_data: Optional[Dict] = None,
    signal_data: Optional[Dict] = None,
    news_data: Optional[List] = None,
    forecast_data: Optional[Dict] = None,
) -> str:

    # Format RAG context
    rag_text = ""
    if rag_context:
        rag_text = "\n\n### Retrieved Knowledge:\n"
        for i, doc in enumerate(rag_context):
            rag_text += f"{i+1}. {doc['text']}\n"

    # Format live stock data
    stock_text = ""
    if db_data:
        if 'gainers' in db_data:
            stock_text = "\n### Top Gainers Today:\n"
            for s in db_data['gainers']:
                stock_text += (
                    f"- {s['ticker']}: Open PKR {s['open_price']} → "
                    f"Close PKR {s['close']} | Change: +{s['change_pct']}% | "
                    f"Volume: {s['volume']}\n"
                )

        elif 'losers' in db_data:
            stock_text = "\n### Top Losers Today:\n"
            for s in db_data['losers']:
                stock_text += (
                    f"- {s['ticker']}: Open PKR {s['open_price']} → "
                    f"Close PKR {s['close']} | Change: {s['change_pct']}% | "
                    f"Volume: {s['volume']}\n"
                )

        elif 'buy_signals' in db_data:
            stock_text = "\n### Current BUY Signals:\n"
            for s in db_data['buy_signals']:
                stock_text += (
                    f"- {s['ticker']}: Signal={s['signal']} | "
                    f"Confidence={round(s['confidence'] * 100, 1)}% | "
                    f"Sentiment={s.get('dominant_sentiment', 'N/A')} | "
                    f"Reason: {s.get('reason', 'N/A')}\n"
                )

        else:
            open_price = db_data.get('open_price') or 0
            close = db_data.get('close') or 0
            change_pct = 0
            if open_price > 0:
                change_pct = round(((close - open_price) / open_price) * 100, 2)

            stock_text = f"""
        ### Live Market Data:
        - Open Price: PKR {open_price or 'N/A'}
        - Close Price: PKR {close or 'N/A'}
        - High: PKR {db_data.get('high') or 'N/A'}
        - Low: PKR {db_data.get('low') or 'N/A'}
        - Volume: {db_data.get('volume') or 'N/A'}
        - Daily Change: {change_pct}%
        - Date: {db_data.get('date') or 'N/A'}
        """

    # Format forecast data
    forecast_text = ""
    if forecast_data:
        forecast_text = f"""
        ### AI Price Forecast:
        - Direction: {forecast_data.get('direction', 'N/A')}
        - Predicted Price: PKR {forecast_data.get('predicted_price', 'N/A')}
        - Expected Change: {forecast_data.get('expected_change_pct', 'N/A')}%
        - Confidence: {round(forecast_data.get('confidence', 0) * 100, 1)}%
        - Model Used: {forecast_data.get('model_used', 'N/A')}
        - Forecast Date: {forecast_data.get('forecast_date', 'N/A')}
        """

    # Format signal data
    signal_text = ""
    if signal_data:
        signal_text = f"""
        ### AI Trading Signal:
        - Signal: {signal_data.get('signal', 'N/A')}
        - Confidence: {round(signal_data.get('confidence', 0) * 100, 1)}%
        - Reason: {signal_data.get('reason', 'N/A')}
        - Forecast Score: {signal_data.get('forecast_score', 'N/A')}
        - Sentiment Score: {signal_data.get('sentiment_score', 'N/A')}
        - Dominant Sentiment: {signal_data.get('dominant_sentiment', 'N/A')}
        """

    # Format news data
    news_text = ""
    if news_data:
        news_text = "\n### Latest News & Sentiment:\n"
        for news in news_data:
            news_text += f"- {news.get('headline', '')} [{news.get('sentiment', '')}]\n"

    prompt = f"""
    You are AIVA, a professional and intelligent AI financial assistant for FinMate,
    a Pakistani stock market application. You are speaking with {user_name}.

    Your personality:
    - Professional, confident and helpful
    - You speak directly to {user_name} by name
    - You give clear, structured, and actionable financial insights
    - You are fintech-focused and knowledgeable about Pakistani stock market
    - You always add a disclaimer at the end

    {rag_text}
    {stock_text}
    {forecast_text}
    {signal_text}
    {news_text}

    ### User Question:
    {user_name} asks: "{user_query}"

    ### Instructions:
    - Address {user_name} by name in your response
    - Use ONLY the real data provided above — never make up numbers
    - If no data is provided for a field say "data not available"
    - Structure your response clearly
    - If giving BUY/SELL/HOLD recommendation explain WHY using actual numbers
    - Mention the forecast direction and predicted price if available
    - Keep response under 300 words
    - End with: "⚠️ Disclaimer: This is not financial advice. Always do your own research."

    ### Response:
    """
    print("Prompt built for Groq:", prompt)  # Debugging line to check the prompt content
    return prompt


async def generate_response(prompt: str) -> str:
    try:
        logger.info("Sending prompt to Groq...")
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1024
        }
        response = requests.post(GROQ_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            answer = data["choices"][0]["message"]["content"].strip()
            logger.info("Groq responded successfully!")
            return answer
        else:
            logger.error(f"Groq error: {response.status_code} - {response.text}")
            return "I apologize, I am having trouble right now. Please try again. ⚠️ Disclaimer: This is not financial advice."
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return "I apologize, I am having trouble right now. Please try again. ⚠️ Disclaimer: This is not financial advice."


def detect_ticker(message: str) -> Optional[str]:
    common_tickers = [
        "PSO", "NBP", "FFC", "ENGRO", "OGDC", "PPL", "HBL",
        "MCB", "UBL", "LUCK", "EFERT", "HUBC", "KAPCO", "KEL",
        "MARI", "POL", "TRG", "SYS", "NETSOL", "UNITY", "BAHL",
        "MEBL", "FABL", "SILK", "PIOC", "MLCF", "CHCC", "DGKC",
        "MUGHAL", "SSGC", "SINDM", "WHALE", "CYAN", "META"
    ]
    message_upper = message.upper()
    for ticker in common_tickers:
        if ticker in message_upper:
            return ticker
    return None


def is_stock_query(message: str) -> bool:
    stock_keywords = [
        "stock", "share", "price", "buy", "sell", "hold",
        "invest", "trading", "market", "signal", "forecast",
        "moving average", "ticker", "company", "predict"
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in stock_keywords)