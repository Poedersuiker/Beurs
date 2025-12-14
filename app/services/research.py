import google.generativeai as genai
from duckduckgo_search import DDGS
from flask import current_app
import json
import logging

logger = logging.getLogger(__name__)

def get_market_news(query):
    try:
        # Fetching news. 'd' gives past day. 'w' gives past week.
        # We use 'w' to ensure we get enough data, assuming 'last 48 hours' is covered.
        with DDGS() as ddgs:
            news_results = list(ddgs.news(keywords=query, region="wt-wt", safesearch="off", timelimit="w", max_results=10))
        return news_results
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return []

def analyze_with_gemini(stock_symbol, news_data):
    api_key = current_app.config.get('GOOGLE_API_KEY')

    if not api_key:
        logger.warning("GOOGLE_API_KEY not found. Returning mock data.")
        return mock_analysis(stock_symbol, news_data)

    try:
        genai.configure(api_key=api_key)
        # Using gemini-1.5-flash as it is fast and capable.
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
         logger.error(f"Error configuring Gemini: {e}")
         # Attempt fallback if initialization fails
         return mock_analysis(stock_symbol, news_data)

    news_text = ""
    for i, item in enumerate(news_data):
        news_text += f"{i+1}. Title: {item.get('title')}\n   Source: {item.get('source')}\n   Date: {item.get('date')}\n   Snippet: {item.get('body')}\n   URL: {item.get('url')}\n\n"

    prompt = f"""
    You are an expert financial analyst.
    Perform a deep research analysis on "{stock_symbol}" based strictly on the provided news items below (which are from the recent timeframe).

    News Items:
    {news_text}

    Task:
    1. Analyze the sentiment and recent events.
    2. Predict the stock movement (Rise, Fall, or Neutral) for the following timeframes:
       - Coming Day
       - Coming Week
       - Coming Month
       - Coming Quarter
    3. For each timeframe, provide:
       - Prediction (Rise/Fall/Neutral)
       - Confidence (0.0 to 1.0)
       - Reasoning (concise explanation)
    4. Determine the overall "Stock Emotion" (e.g., Optimistic, Panic, Greed, Fear, Neutral).
    5. Identify which of the provided news sources were most relevant to your prediction.

    Output must be valid JSON in the following format:
    {{
        "stock": "{stock_symbol}",
        "emotion": "...",
        "predictions": [
            {{
                "timeframe": "day",
                "prediction": "...",
                "confidence": 0.8,
                "reasoning": "..."
            }},
            {{
                "timeframe": "week",
                "prediction": "...",
                "confidence": 0.7,
                "reasoning": "..."
            }},
            {{
                "timeframe": "month",
                "prediction": "...",
                "confidence": 0.6,
                "reasoning": "..."
            }},
            {{
                "timeframe": "quarter",
                "prediction": "...",
                "confidence": 0.5,
                "reasoning": "..."
            }}
        ],
        "relevant_sources": [
            {{
                "url": "...",
                "title": "...",
                "snippet": "..."
            }}
        ]
    }}
    Do not include markdown formatting (like ```json), just the raw JSON string.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text
        # Clean up response if it contains markdown
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
             text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"Error calling Gemini: {e}")
        return None

def mock_analysis(stock_symbol, news_data):
    """Returns mock data for testing without API key."""
    return {
        "stock": stock_symbol,
        "emotion": "Cautiously Optimistic (Mock)",
        "predictions": [
            {
                "timeframe": "day",
                "prediction": "Rise",
                "confidence": 0.65,
                "reasoning": "Recent positive news cycle implies short term gain."
            },
            {
                "timeframe": "week",
                "prediction": "Rise",
                "confidence": 0.7,
                "reasoning": "Strong quarterly earnings report expected."
            },
            {
                "timeframe": "month",
                "prediction": "Neutral",
                "confidence": 0.5,
                "reasoning": "Market volatility may offset gains."
            },
            {
                "timeframe": "quarter",
                "prediction": "Fall",
                "confidence": 0.4,
                "reasoning": "Macroeconomic factors may weigh down."
            }
        ],
        "relevant_sources": [
            {
                "url": item.get('url'),
                "title": item.get('title'),
                "snippet": item.get('body')
            } for item in news_data[:3]
        ]
    }
