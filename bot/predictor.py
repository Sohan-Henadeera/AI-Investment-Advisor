# =============================================================================
# bot/predictor.py — ONE JOB: AI PROBABILITY ESTIMATION
# =============================================================================
# Sends each flagged market to your local Ollama model and gets a probability.
# Parses the response, calculates edge vs market price, saves to database.
#
# TO CHANGE THE AI MODEL: edit OLLAMA_MODEL in config.py
# TO CHANGE THE PROMPT: edit build_prompt() below
# TO ADD A SECOND MODEL: add another call in predict_market() and average them
# =============================================================================

import requests
import re
from datetime import datetime
from config import OLLAMA_MODEL, OLLAMA_URL, MIN_EDGE
from database import save_prediction


def ask_ollama(prompt: str) -> str:
    """
    Sends a prompt to your locally running Ollama model.
    Returns the raw text response, or an error string starting with 'ERROR:'.
    """
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model":  OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,  # Low = more consistent
                    "num_predict": 400,
                }
            },
            timeout=90
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return f"ERROR: Ollama returned status {response.status_code}"
    except requests.exceptions.ConnectionError:
        return "ERROR: Ollama is not running. Start it with: ollama serve"
    except Exception as e:
        return f"ERROR: {e}"


def extract_probability(text: str) -> float | None:
    """
    Pulls a probability number out of the AI's response text.
    Looks for patterns like '65%', '0.65', 'probability: 65', etc.
    Returns a float between 0.01 and 0.99, or None if nothing found.
    """
    patterns = [
        r'MY PROBABILITY ESTIMATE[:\s]+(\d{1,2})%',
        r'MY PROBABILITY[:\s]+(\d{1,2})%',
        r'\b(0\.\d{1,2})\b',
        r'\b(\d{1,2})%',
        r'(\d{1,2})\s*percent',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            val = float(match.group(1))
            if val > 1:
                val = val / 100
            if 0.01 <= val <= 0.99:
                return round(val, 3)
    return None


def build_prompt(market: dict) -> str:
    """
    Builds the prompt sent to the AI for probability estimation.
    Edit this to change how the AI reasons about markets.
    """
    return f"""You are a calibrated prediction market analyst. Estimate the TRUE probability of this event.

MARKET: {market['title']}
CURRENT MARKET PRICE: {market['yes_price']:.0%} (market says there's a {market['yes_price']:.0%} chance of YES)
DAYS UNTIL RESOLUTION: {market['days_to_expiry']}

Think through:
1. What is the base rate for this type of event?
2. What factors push probability HIGHER?
3. What factors push probability LOWER?
4. Is the market price too high, too low, or about right?

Be concise. End your response with exactly this line:
MY PROBABILITY ESTIMATE: [number]%"""


def predict_market(market: dict) -> dict | None:
    """
    Runs AI prediction on a single market.
    Returns a prediction dict with edge calculation, or None on failure.
    """
    print(f"  Predicting: {market['title'][:55]}...")

    prompt      = build_prompt(market)
    ai_response = ask_ollama(prompt)

    if ai_response.startswith("ERROR"):
        print(f"    ✗ {ai_response}")
        return None

    our_prob = extract_probability(ai_response)
    if our_prob is None:
        print(f"    ✗ Could not extract probability from AI response")
        return None

    market_price = market["yes_price"]
    edge         = round(our_prob - market_price, 4)

    prediction = {
        "market_id":        market["id"],
        "our_probability":  our_prob,
        "market_price":     market_price,
        "edge":             edge,
        "reasoning":        ai_response[:800],  # Save up to 800 chars of reasoning
    }
    save_prediction(prediction)

    signal = "✅ SIGNAL" if abs(edge) >= MIN_EDGE else "—"
    print(f"    Market: {market_price:.0%}  |  AI: {our_prob:.0%}  |  Edge: {edge:+.1%}  {signal}")
    return prediction


def run_predictions(markets: list) -> list:
    """
    Runs predictions on all flagged markets.
    Returns a list of signals where abs(edge) >= MIN_EDGE.
    """
    flagged = [m for m in markets if m.get("flagged")]
    if not flagged:
        print("  No flagged markets to predict on")
        return []

    print(f"  Running AI on {len(flagged)} flagged markets...")
    signals = []

    for market in flagged:
        result = predict_market(market)
        if result and abs(result["edge"]) >= MIN_EDGE:
            signals.append({**market, **result})

    print(f"  ✓ {len(signals)} trade signals found")
    return signals