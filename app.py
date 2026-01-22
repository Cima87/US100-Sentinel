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

# ==========================================
# 🎨 STATIC CSS
# ==========================================
st.set_page_config(page_title="US100 Sentinel Pro", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Montserrat', sans-serif; }
    header, footer {visibility: hidden;}
    
    .traffic-container { display: flex; flex-direction: column; align-items: center; margin-top: -20px; margin-bottom: 25px; }
    .traffic-light { width: 90px; height: 90px; border-radius: 50%; margin-bottom: 15px; transition: background-color 0.5s ease; }
    .status-text { font-size: 24px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
    
    .dashboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 25px; }
    .stat-box { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; text-align: center; }
    .label { font-size: 11px; color: #888; letter-spacing: 1px; margin-bottom: 5px; font-weight: 600; }
    .value { font-size: 20px; font-weight: 600; }
    
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
# 🧠 LOGIC ENGINE
# ==========================================

def get_market_data():
    try:
        tickers = yf.Tickers("NQ=F SEK=X")
        nq = tickers.tickers['NQ=F'].history(period="1d", interval="1m")
        if not nq.empty:
            price = nq['Close'].iloc[-1]
            change = price - nq['Open'].iloc[0]
            pct = (change / nq['Open'].iloc[0]) * 100
        else:
            price, change, pct = 0, 0, 0
        
        sek = tickers.tickers['SEK=X'].history(period="1d", interval="1m")
        sek_val = sek['Close'].iloc[-1] if not sek.empty else 0
        return price, change, pct, sek_val
    except:
        return 0, 0, 0, 0

def get_latest_headlines():
    rss_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        "https://www.investing.com/rss/news_25.rss"
    ]
    headlines = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:6]: # Get a few more for the daily summary
                headlines.append({"title": entry.title, "link": entry.link})
        except: pass
    return headlines

def get_current_est_time():
    tz = pytz.timezone('US/Eastern')
    return datetime.now(tz)

def run_gemini_analysis(headlines_text, is_end_of_day=False):
    if not AI_AVAILABLE:
        return "#555", "API ERROR", "Key Missing", None

    try:
        if is_end_of_day:
            # --- SPECIAL 6 PM SUMMARY PROMPT ---
            prompt = f"""
            Act as a Senior Wall Street Analyst. The market just closed.
            Analyze these headlines from the day: {headlines_text}
            
            Task:
            1. Write a 'Daily Wrap-Up' (Max 3 sentences). Summarize the main theme of the day (e.g. "Tech led the rally," or "Yields crushed equities").
            2. End with exactly this phrase: "Markets closed. AI is sleeping now."
            3. Set color to #333 (Grey) since market is closed.
            
            Output format: COLOR|SUMMARY|NONE
            """
        else:
            # --- STANDARD TRADING DAY PROMPT ---
            prompt = f"""
            Act as a Senior Wall Street Futures Trader. Analyze these headlines for NASDAQ-100 (US100):
            {headlines_text}
            
            Task:
            1. Determine Sentiment (GREEN=Bullish, RED=Bearish, ORANGE=Mixed).
            2. Write a Situation Report (Max 30 words). Identify the specific catalyst.
            3. CHECK FOR BREAKING 3-STAR EVENTS (War, Rate Hike, Crash). If none, write "NONE".
            
            Output format strictly: COLOR|SUMMARY|BREAKING_EVENT
            """

        response = model.generate_content(prompt)
        text = response.text.strip()
        parts = text.split('|')
        
        if len(parts) >= 2:
            color_ref = parts[0].upper()
            summary = parts[1]
            breaking = parts[2] if len(parts) > 2 and "NONE" not in parts[2] else None
        else:
            color_ref, summary, breaking = "ORANGE", text, None

        # Color mapping
        if "#333" in color_ref: final_color = "#333333" # End of day grey
        elif "GREEN" in color_ref: final_color = "#00FF00"
        elif "RED" in color_ref: final_color = "#FF0000"
        else: final_color = "#FFA500"
        
        # Status Text logic
        if is_end_of_day:
            status_text = "MARKET CLOSED"
        else:
            status_text = "BULLISH" if "GREEN" in color_ref else "BEARISH" if "RED" in color_ref else "NEUTRAL"
            
        return final_color, status_text, summary, breaking

    except Exception as e:
        return "#FFA500", "AI ERROR", f"Offline: {str(e)}", None

# ==========================================
# 🔄 MAIN LOOP
# ==========================================

@st.fragment(run_every=60)
def main_dashboard_loop():
    # 1. SETUP PLACEHOLDERS
    traffic_ph = st.empty()
    metrics_ph = st.empty()
    breaking_ph = st.empty()
    ai_ph = st.empty()
    news_ph = st.empty()
    
    # 2. RENDER CACHED DATA
    with traffic_ph.container():
        st.markdown(f"""
        <div class="traffic-container">
            <div class="traffic-light" style="background-color: {st.session_state.cached_ai_color}; box-shadow: 0 0 60px {st.session_state.cached_ai_color};"></div>
            <div class="status-text" style="color: {st.session_state.cached_ai_color};">{st.session_state.cached_ai_status}</div>
        </div>
        """, unsafe_allow_html=True)

    with ai_ph.container():
        st.markdown('<div class="label">GEMINI SITUATION REPORT</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="ai-box" style="border-left-color: {st.session_state.cached_ai_color};">
            <div class="ai-text">{st.session_state.cached_ai_summary}</div>
        </div>
        """, unsafe_allow_html=True)

    if st.session_state.cached_breaking:
        breaking_ph.markdown(f'<div class="breaking-box">⚠ {st.session_state.cached_breaking}</div>', unsafe_allow_html=True)
    else:
        breaking_ph.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)

    # 3. FAST UPDATES
    price, change, pct, sek = get_market_data()
    news_items = get_latest_headlines()
    
    sign = "+" if change >= 0 else ""
    p_color = "#00FF00" if change >= 0 else "#FF4444"
    
    metrics_ph.markdown(f"""
    <div class="dashboard-grid">
        <div class="stat-box">
            <div class="label">US100 FUTURES</div>
            <div class="value" style="color: {p_color};">{price:,.0f}</div>
            <div style="font-size: 12px; color: {p_color};">{sign}{change:.1f} ({sign}{pct:.1f}%)</div>
        </div>
        <div class="stat-box">
            <div class="label">USD / SEK</div>
            <div class="value" style="color: white;">{sek:.2f} kr</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with news_ph.container():
        st.markdown('<div class="news-header">LIVE WIRE (UPDATED)</div>', unsafe_allow_html=True)
        for item in news_items:
            st.markdown(f'<div class="news-item"><a href="{item["link"]}" target="_blank">{item["title"]}</a></div>', unsafe_allow_html=True)

    # 4. TIME LOGIC
    now = get_current_est_time()
    current_time_ts = time.time()
    
    # Define Time Blocks
    is_weekday = now.weekday() <= 4
    is_trading_hours = 9 <= now.hour < 18  # 9:00 - 17:59
    is_closing_time = now.hour == 18       # 18:00 - 18:59 (The 6 PM Hour)
    
    # 5. EXECUTION LOGIC
    # Case A: Normal Trading (Every 30 mins)
    should_run_standard = is_weekday and is_trading_hours and ((current_time_ts - st.session_state.last_run) > 1800)
    
    # Case B: Closing Bell (Run once at 6 PM if we haven't already)
    # We check if it's 6PM AND the last run was done BEFORE 6PM (meaning we haven't done the closing summary yet)
    last_run_hour = datetime.fromtimestamp(st.session_state.last_run, pytz.timezone('US/Eastern')).hour
    should_run_closing = is_weekday and is_closing_time and (last_run_hour < 18)

    # Case C: Fresh Start (First load)
    should_run_fresh = (st.session_state.last_run == 0) and (is_trading_hours or is_closing_time)

    if should_run_standard or should_run_closing or should_run_fresh:
        
        news_text = str([h['title'] for h in news_items])
        
        # Determine if this is the "End of Day" run
        is_eod_run = should_run_closing or (is_closing_time and should_run_fresh)
        
        color, status, summary, breaking = run_gemini_analysis(news_text, is_end_of_day=is_eod_run)
        
        # Save to Memory
        st.session_state.cached_ai_color = color
        st.session_state.cached_ai_status = status
        st.session_state.cached_ai_summary = summary
        st.session_state.cached_breaking = breaking
        st.session_state.last_run = current_time_ts
        
        # Redraw
        with traffic_ph.container():
            st.markdown(f"""
            <div class="traffic-container">
                <div class="traffic-light" style="background-color: {color}; box-shadow: 0 0 60px {color};"></div>
                <div class="status-text" style="color: {color};">{status}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with ai_ph.container():
            st.markdown('<div class="label">GEMINI SITUATION REPORT</div>', unsafe_allow_html=True)
            st.markdown(f"""
            <div class="ai-box" style="border-left-color: {color};">
                <div class="ai-text">{summary}</div>
            </div>
            """, unsafe_allow_html=True)

main_dashboard_loop()
