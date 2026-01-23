import streamlit as st
import yfinance as yf
import feedparser
import time
import google.generativeai as genai
import hashlib
from datetime import datetime
import pytz

# ==========================================
# 🔑 CONFIGURATION
# ==========================================
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-3-pro-preview') 
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False

# ==========================================
# 🧠 MEMORY
# ==========================================
if 'last_run' not in st.session_state: st.session_state.last_run = 0
if 'cached_ai_summary' not in st.session_state: st.session_state.cached_ai_summary = "Waiting for Market Open..."
if 'cached_ai_color' not in st.session_state: st.session_state.cached_ai_color = "#333" 
if 'cached_ai_status' not in st.session_state: st.session_state.cached_ai_status = "STANDBY"
if 'cached_breaking' not in st.session_state: st.session_state.cached_breaking = None
# Default currency selection
if 'selected_currency' not in st.session_state: st.session_state.selected_currency = "SEK"

# ==========================================
# 🎨 STATIC CSS
# ==========================================
st.set_page_config(page_title="Global Sentinel Pro", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Montserrat', sans-serif; }
    header, footer {visibility: hidden;}
    
    /* TRAFFIC LIGHT */
    .traffic-container { display: flex; flex-direction: column; align-items: center; margin-top: -20px; margin-bottom: 25px; }
    .traffic-light { width: 90px; height: 90px; border-radius: 50%; margin-bottom: 15px; transition: background-color 0.5s ease; }
    .status-text { font-size: 24px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
    
    /* GLOBAL MARKETS GRID */
    .global-grid { 
        display: grid; 
        grid-template-columns: repeat(5, 1fr); 
        gap: 5px; 
        margin-bottom: 20px; 
        background: #111;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #333;
    }
    .global-item { text-align: center; }
    .global-name { font-size: 9px; color: #888; margin-bottom: 2px; }
    .global-val { font-size: 12px; font-weight: 600; }
    
    /* CONVERTER BOX */
    .converter-box { 
        background-color: #111; border: 1px solid #333; border-radius: 8px; 
        padding: 15px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;
    }
    .conv-label { font-size: 11px; color: #888; letter-spacing: 1px; }
    .conv-value { font-size: 20px; font-weight: 600; color: #FFF; }

    /* AI & NEWS */
    .ai-box { margin-bottom: 30px; padding: 15px; border-left: 4px solid #333; background: #080808; }
    .ai-text { font-size: 16px; color: #EEE; line-height: 1.6; font-weight: 400; }
    
    .breaking-box { 
        background-color: #330000; border: 2px solid #FF0000; color: #FF4444; 
        padding: 15px; text-align: center; font-size: 18px; font-weight: 800; 
        margin-bottom: 30px; border-radius: 5px; text-transform: uppercase;
        animation: pulse 2s infinite;
    }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }

    .news-header { font-size: 12px; color: #666; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #222; padding-bottom: 8px; margin-bottom: 15px;}
    .news-item { margin-bottom: 14px; font-size: 14px; border-left: 2px solid #333; padding-left: 12px; }
    .news-item a { color: #CCC; text-decoration: none; }
    .news-item a:hover { color: #4da6ff; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 DATA ENGINE
# ==========================================

def get_financial_data():
    try:
        # 1. INDICES (The "Stock Markets")
        # NQ=F (US Tech), ^GDAXI (Germany/Euro), ^FTSE (UK), ^N225 (Japan), ^OMX (Sweden)
        # 2. CURRENCIES (vs USD)
        # EURUSD=X, GBPUSD=X, JPY=X (USD/JPY), SEK=X (USD/SEK)
        
        tickers = yf.Tickers("NQ=F ^GDAXI ^FTSE ^N225 ^OMX EURUSD=X GBPUSD=X JPY=X SEK=X")
        data = tickers.history(period="1d") # Get mostly recent close
        
        def get_change(symbol):
            if symbol not in data['Close'].columns: return 0.0
            closes = data['Close'][symbol].dropna()
            opens = data['Open'][symbol].dropna()
            if closes.empty: return 0.0
            # Simple % change calculation (Today's movement)
            return ((closes.iloc[-1] - opens.iloc[-1]) / opens.iloc[-1]) * 100

        def get_price(symbol):
            if symbol not in data['Close'].columns: return 0.0
            closes = data['Close'][symbol].dropna()
            return closes.iloc[-1] if not closes.empty else 0.0

        market_performance = {
            "US": get_change("NQ=F"),
            "EU": get_change("^GDAXI"),
            "UK": get_change("^FTSE"),
            "JP": get_change("^N225"),
            "SE": get_change("^OMX")
        }
        
        currency_rates = {
            "EUR": get_price("EURUSD=X"),  # 1 EUR = X USD
            "GBP": get_price("GBPUSD=X"),  # 1 GBP = X USD
            "JPY": get_price("JPY=X"),     # 1 USD = X JPY (Needs inversion for consistency usually, but we keep raw)
            "SEK": get_price("SEK=X")      # 1 USD = X SEK
        }
        
        return market_performance, currency_rates
    except:
        return {}, {}

def get_latest_headlines():
    rss_urls = ["https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910", "https://www.investing.com/rss/news_25.rss"]
    headlines = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]: 
                headlines.append({"title": entry.title, "link": entry.link})
        except: pass
    return headlines

def get_current_est_time():
    tz = pytz.timezone('US/Eastern')
    return datetime.now(tz)

def run_gemini_analysis(headlines_text, is_end_of_day=False):
    if not AI_AVAILABLE: return "#555", "API ERROR", "Key Missing", None
    try:
        if is_end_of_day:
            prompt = f"Act as a Senior Wall Street Analyst. Market Closed. Analyze these headlines: {headlines_text}. Task: 1. Daily Wrap-Up (Max 3 sentences). 2. End with 'Markets closed. AI is sleeping now.' 3. Color #333. Output: COLOR|SUMMARY|NONE"
        else:
            prompt = f"Act as a Wall Street Futures Trader. Analyze these US100 headlines: {headlines_text}. Task: 1. Sentiment (GREEN/RED/ORANGE). 2. Situation Report (Max 30 words). 3. CHECK BREAKING 3-STAR EVENTS (War, Crash). Output: COLOR|SUMMARY|BREAKING_EVENT"
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        parts = text.split('|')
        
        if len(parts) >= 2: color_ref, summary, breaking = parts[0].upper(), parts[1], (parts[2] if len(parts) > 2 and "NONE" not in parts[2] else None)
        else: color_ref, summary, breaking = "ORANGE", text, None

        if "#333" in color_ref: final_color = "#333333"
        elif "GREEN" in color_ref: final_color = "#00FF00"
        elif "RED" in color_ref: final_color = "#FF0000"
        else: final_color = "#FFA500"
        
        status_text = "MARKET CLOSED" if is_end_of_day else ("BULLISH" if "GREEN" in color_ref else "BEARISH" if "RED" in color_ref else "NEUTRAL")
        return final_color, status_text, summary, breaking
    except Exception as e: return "#FFA500", "AI ERROR", f"Offline: {str(e)}", None

# ==========================================
# 🔄 UI LOOP
# ==========================================

@st.fragment(run_every=60)
def main_dashboard_loop():
    # 1. SETUP PLACEHOLDERS
    traffic_ph = st.empty()
    global_ph = st.empty()
    converter_ph = st.empty()
    breaking_ph = st.empty()
    ai_ph = st.empty()
    news_ph = st.empty()
    
    # 2. RENDER CACHED AI DATA
    with traffic_ph.container():
        st.markdown(f"""
        <div class="traffic-container">
            <div class="traffic-light" style="background-color: {st.session_state.cached_ai_color}; box-shadow: 0 0 60px {st.session_state.cached_ai_color};"></div>
            <div class="status-text" style="color: {st.session_state.cached_ai_color};">{st.session_state.cached_ai_status}</div>
        </div>
        """, unsafe_allow_html=True)

    with ai_ph.container():
        st.markdown('<div class="label">GEMINI SITUATION REPORT</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-box" style="border-left-color: {st.session_state.cached_ai_color};"><div class="ai-text">{st.session_state.cached_ai_summary}</div></div>', unsafe_allow_html=True)

    if st.session_state.cached_breaking:
        breaking_ph.markdown(f'<div class="breaking-box">⚠ {st.session_state.cached_breaking}</div>', unsafe_allow_html=True)
    else:
        breaking_ph.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)

    # 3. GET FRESH DATA
    markets, rates = get_financial_data()
    news_items = get_latest_headlines()
    
    # 4. RENDER GLOBAL MARKETS (THE NEW GRID)
    def color(val): return "#00FF00" if val >= 0 else "#FF4444"
    
    with global_ph.container():
        st.markdown('<div class="label" style="text-align:center;">GLOBAL PULSE (INDICES)</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="global-grid">
            <div class="global-item"><div class="global-name">🇺🇸 US</div><div class="global-val" style="color:{color(markets.get('US',0))}">{markets.get('US',0):+.1f}%</div></div>
            <div class="global-item"><div class="global-name">🇪🇺 EU</div><div class="global-val" style="color:{color(markets.get('EU',0))}">{markets.get('EU',0):+.1f}%</div></div>
            <div class="global-item"><div class="global-name">🇬🇧 UK</div><div class="global-val" style="color:{color(markets.get('UK',0))}">{markets.get('UK',0):+.1f}%</div></div>
            <div class="global-item"><div class="global-name">🇯🇵 JP</div><div class="global-val" style="color:{color(markets.get('JP',0))}">{markets.get('JP',0):+.1f}%</div></div>
            <div class="global-item"><div class="global-name">🇸🇪 SE</div><div class="global-val" style="color:{color(markets.get('SE',0))}">{markets.get('SE',0):+.1f}%</div></div>
        </div>
        """, unsafe_allow_html=True)

    # 5. RENDER CURRENCY CONVERTER (INTERACTIVE)
    with converter_ph.container():
        col1, col2 = st.columns([1, 2])
        with col1:
            # Dropdown menu
            curr = st.selectbox("VS DOLLAR", ["SEK", "EUR", "GBP", "JPY"], key="currency_selector")
        with col2:
            # Logic to display rate
            if curr == "SEK": 
                val = rates.get("SEK", 0)
                display = f"1 $ = {val:.2f} kr"
            elif curr == "JPY": 
                val = rates.get("JPY", 0)
                display = f"1 $ = {val:.2f} ¥"
            elif curr == "EUR": 
                val = rates.get("EUR", 0)
                display = f"1 € = {val:.3f} $" # EUR/GBP are usually inverted (1 Euro = X Dollar)
            elif curr == "GBP": 
                val = rates.get("GBP", 0)
                display = f"1 £ = {val:.3f} $"

            st.markdown(f"""
            <div style="text-align: right; padding-top: 10px;">
                <div class="conv-value">{display}</div>
            </div>
            """, unsafe_allow_html=True)

    with news_ph.container():
        st.markdown('<div class="news-header">LIVE WIRE (UPDATED)</div>', unsafe_allow_html=True)
        for item in news_items:
            st.markdown(f'<div class="news-item"><a href="{item["link"]}" target="_blank">{item["title"]}</a></div>', unsafe_allow_html=True)

    # 6. TIME & AI LOGIC
    now = get_current_est_time()
    current_time_ts = time.time()
    is_weekday = now.weekday() <= 4
    is_trading_hours = 9 <= now.hour < 18
    is_closing_time = now.hour == 18
    
    should_run_standard = is_weekday and is_trading_hours and ((current_time_ts - st.session_state.last_run) > 1800)
    last_run_hour = datetime.fromtimestamp(st.session_state.last_run, pytz.timezone('US/Eastern')).hour
    should_run_closing = is_weekday and is_closing_time and (last_run_hour < 18)
    should_run_fresh = (st.session_state.last_run == 0) and (is_trading_hours or is_closing_time)

    if should_run_standard or should_run_closing or should_run_fresh:
        news_text = str([h['title'] for h in news_items])
        is_eod_run = should_run_closing or (is_closing_time and should_run_fresh)
        color, status, summary, breaking = run_gemini_analysis(news_text, is_end_of_day=is_eod_run)
        
        st.session_state.cached_ai_color = color
        st.session_state.cached_ai_status = status
        st.session_state.cached_ai_summary = summary
        st.session_state.cached_breaking = breaking
        st.session_state.last_run = current_time_ts
        st.rerun() # Force redraw to update AI box instantly

main_dashboard_loop()
