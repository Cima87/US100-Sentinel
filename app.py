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
    # Using Flagship Gemini 3 Pro (Tier 1)
    model = genai.GenerativeModel('gemini-3-pro-preview') 
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False

# ==========================================
# 🧠 MEMORY (Session State)
# ==========================================
if 'last_run' not in st.session_state: st.session_state.last_run = 0
if 'cached_ai_summary' not in st.session_state: st.session_state.cached_ai_summary = "Initializing System..."
if 'cached_ai_color' not in st.session_state: st.session_state.cached_ai_color = "#333" 
if 'cached_ai_status' not in st.session_state: st.session_state.cached_ai_status = "STANDBY"
if 'cached_breaking' not in st.session_state: st.session_state.cached_breaking = None

# ==========================================
# 🎨 STATIC CSS (The "Vortex" Theme)
# ==========================================
st.set_page_config(page_title="US100 VORTEX", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Montserrat', sans-serif; }
    header, footer {visibility: hidden;}
    
    /* 1. SLICK HEADER (Updated: Solid White & Bigger) */
    .vortex-header {
        text-align: center;
        font-size: 10px;
        letter-spacing: 4px;
        color: #666;
        margin-top: -30px;
        margin-bottom: 0px;
        text-transform: uppercase;
    }
    .vortex-title {
        text-align: center;
        font-size: 42px;  /* Bigger */
        font-weight: 700; /* Bold but clean */
        color: #FFFFFF;   /* Solid White */
        margin-bottom: 15px;
        letter-spacing: -1px;
    }

    /* 2. THE HERO PRICE (Updated: Smaller & Tighter) */
    .hero-container {
        text-align: center;
        margin-bottom: 25px;
        padding: 12px; /* Less padding */
        background: radial-gradient(circle at center, #111 0%, #000 70%);
        border: 1px solid #222;
        border-radius: 10px;
        width: 60%; /* Limit width to make it look smaller */
        margin-left: auto;
        margin-right: auto;
    }
    .hero-label { font-size: 10px; color: #888; letter-spacing: 2px; margin-bottom: 2px; }
    .hero-price { font-size: 32px; font-weight: 700; color: #FFF; line-height: 1.1; } /* Smaller font */
    .hero-change { font-size: 14px; font-weight: 600; margin-top: 2px; }
    
    /* 3. TRAFFIC LIGHT (Investment Climate) */
    .traffic-container { display: flex; flex-direction: column; align-items: center; margin-bottom: 25px; }
    .traffic-light { 
        width: 100px; height: 100px; border-radius: 50%; margin-bottom: 15px; 
        transition: background-color 0.5s ease, box-shadow 0.5s ease; 
        border: 4px solid #111;
    }
    .status-text { font-size: 20px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
    
    /* 4. GLOBAL GRID (Compact) */
    .global-grid { 
        display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; 
        margin-bottom: 25px; background: #080808; padding: 8px; 
        border-radius: 8px; border: 1px solid #222;
    }
    .global-item { text-align: center; padding: 5px 0; border-right: 1px solid #222; }
    .global-item:last-child { border-right: none; }
    .g-flag { font-size: 10px; color: #666; margin-bottom: 2px; font-weight: 800; }
    .g-price { font-size: 11px; font-weight: 600; color: #DDD; }
    .g-change { font-size: 10px; font-weight: 600; margin-bottom: 2px; }

    /* 5. AI & NEWS */
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
        # We need NQ for the Hero Section, and others for the grid
        symbols = "NQ=F ^GDAXI ^FTSE ^N225 DX-Y.NYB"
        tickers = yf.Tickers(symbols)
        data = tickers.history(period="2d")
        
        def get_metrics(symbol):
            if symbol not in data['Close'].columns: return 0, 0
            price = data['Close'][symbol].dropna().iloc[-1]
            open_price = data['Open'][symbol].dropna().iloc[-1]
            change_pct = ((price - open_price) / open_price) * 100
            return price, change_pct

        # Hero Data
        hero_p, hero_c = get_metrics("NQ=F")
        
        # Grid Data
        metrics = {
            'US100': {'p': hero_p, 'c': hero_c},
            'DAX':   get_metrics("^GDAXI"),
            'FTSE':  get_metrics("^FTSE"),
            'NI225': get_metrics("^N225"),
            'DXY':   get_metrics("DX-Y.NYB") # Dollar Index
        }
        return metrics
    except:
        return {}

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
            # End of Day Prompt
            prompt = f"Act as a Senior Wall Street Analyst. Market Closed. Analyze these headlines: {headlines_text}. Task: 1. Daily Wrap-Up (Max 3 sentences). 2. End with 'Markets closed. AI is sleeping now.' 3. Color #333. Output: COLOR|SUMMARY|NONE"
        else:
            # ==========================================
            # 🤖 UPDATED PROMPT (The 3-Factor Logic)
            # ==========================================
            prompt = f"""
            Act as a Senior NASDAQ Futures Trader. Analyze these headlines: {headlines_text}
            
            Task 1: Determine Investment Climate (Traffic Light):
            - GREEN (#00FF00) = BULLISH (Growth, Earnings Beat, Rate Cuts, Tech Rally).
            - RED (#FF0000) = BEARISH (Inflation, War, Rate Hikes, Tech Sell-off).
            - ORANGE (#FFA500) = NEUTRAL or CHOPPY.
            *CRITICAL: Do not mark 'Volatility' as Red unless it is Downside Volatility.*
            
            Task 2: Situation Report (Max 60 words):
            - Identify the single biggest catalyst moving the NQ futures right now.
            - Also mention two other factors that play a role in the movement of the NQ futures right now.
            
            Task 3: Check for BREAKING 3-STAR EVENTS (Crash, War, Fed Decision). 
            - If found, output event name. Else "NONE".
            
            Output strictly: COLOR|SUMMARY|BREAKING_EVENT
            """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        parts = text.split('|')
        
        if len(parts) >= 2: color_ref, summary, breaking = parts[0].upper(), parts[1], (parts[2] if len(parts) > 2 and "NONE" not in parts[2] else None)
        else: color_ref, summary, breaking = "ORANGE", text, None

        # Clean Hex Codes
        if "#333" in color_ref: final_color = "#333333"
        elif "GREEN" in color_ref: final_color = "#00FF00"
        elif "RED" in color_ref: final_color = "#FF0000"
        else: final_color = "#FFA500"
        
        # Status Text
        if is_end_of_day: status_text = "MARKET CLOSED"
        elif "GREEN" in color_ref: status_text = "BULLISH CLIMATE"
        elif "RED" in color_ref: status_text = "BEARISH CLIMATE"
        else: status_text = "NEUTRAL / CHOP"
            
        return final_color, status_text, summary, breaking
    except Exception as e: return "#FFA500", "AI ERROR", f"Offline: {str(e)}", None

# ==========================================
# 🔄 UI LOOP
# ==========================================

@st.fragment(run_every=60)
def main_dashboard_loop():
    # 1. SETUP PLACEHOLDERS
    header_ph = st.empty()
    traffic_ph = st.empty()
    global_ph = st.empty()
    breaking_ph = st.empty()
    ai_ph = st.empty()
    news_ph = st.empty()
    
    # 2. GET FRESH DATA
    data = get_financial_data()
    news_items = get_latest_headlines()
    
    # 3. RENDER HEADER & HERO PRICE
    nq_p, nq_c = data.get('US100', (0,0)).values()
    hero_color = "#00FF00" if nq_c >= 0 else "#FF4444"
    hero_sign = "+" if nq_c >= 0 else ""
    
    with header_ph.container():
        st.markdown('<div class="vortex-header">ALGORITHMIC NEWS FILTER</div>', unsafe_allow_html=True)
        st.markdown('<div class="vortex-title">US100 VORTEX</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="hero-container">
            <div class="hero-label">NASDAQ 100 FUTURES</div>
            <div class="hero-price" style="color: {hero_color}; text-shadow: 0 0 20px {hero_color}44;">{nq_p:,.2f}</div>
            <div class="hero-change" style="color: {hero_color};">{hero_sign}{nq_c:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)

    # 4. RENDER TRAFFIC LIGHT (Using Cached AI)
    with traffic_ph.container():
        st.markdown(f"""
        <div class="traffic-container">
            <div class="traffic-light" style="background-color: {st.session_state.cached_ai_color}; box-shadow: 0 0 80px {st.session_state.cached_ai_color};"></div>
            <div class="status-text" style="color: {st.session_state.cached_ai_color};">{st.session_state.cached_ai_status}</div>
        </div>
        """, unsafe_allow_html=True)

    # 5. RENDER GLOBAL GRID
    def color(val): return "#00FF00" if val >= 0 else "#FF4444"
    def fmt_item(label, key):
        p, c = data.get(key, (0,0))
        return f"""
        <div class="global-item">
            <div class="g-flag">{label}</div>
            <div class="g-price">{p:,.0f}</div>
            <div class="g-change" style="color:{color(c)}">{c:+.1f}%</div>
        </div>
        """
    
    with global_ph.container():
        st.markdown(f"""
        <div class="global-grid">
            {fmt_item("🇪🇺 DAX", "DAX")}
            {fmt_item("🇬🇧 FTSE", "FTSE")}
            {fmt_item("🇯🇵 NIKKEI", "NI225")}
            {fmt_item("🇺🇸 DXY", "DXY")}
        </div>
        """, unsafe_allow_html=True)

    # 6. RENDER AI & NEWS
    with ai_ph.container():
        st.markdown('<div class="label">GEMINI SITUATION REPORT</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-box" style="border-left-color: {st.session_state.cached_ai_color};"><div class="ai-text">{st.session_state.cached_ai_summary}</div></div>', unsafe_allow_html=True)

    if st.session_state.cached_breaking:
        breaking_ph.markdown(f'<div class="breaking-box">⚠ {st.session_state.cached_breaking}</div>', unsafe_allow_html=True)
    
    with news_ph.container():
        st.markdown('<div class="news-header">LIVE WIRE (UPDATED)</div>', unsafe_allow_html=True)
        for item in news_items:
            st.markdown(f'<div class="news-item"><a href="{item["link"]}" target="_blank">{item["title"]}</a></div>', unsafe_allow_html=True)

    # 7. TIME & AI LOGIC
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
        st.rerun() 

main_dashboard_loop()
