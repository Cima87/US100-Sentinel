import streamlit as st
import yfinance as yf
import feedparser
import time
import google.generativeai as genai
import hashlib

# ==========================================
# 🔑 CONFIGURATION
# ==========================================
try:
    # Use the flagship Gemini 3 Pro model (Tier 1 access required)
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-3-pro-preview') 
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False

# ==========================================
# 🧠 SMART SESSION STATE (The "Memory")
# ==========================================
# This ensures we remember the news between updates
if 'last_run' not in st.session_state:
    st.session_state.last_run = 0
if 'cached_ai_summary' not in st.session_state:
    st.session_state.cached_ai_summary = "Initializing..."
if 'cached_ai_color' not in st.session_state:
    st.session_state.cached_ai_color = "#555"
if 'cached_ai_status' not in st.session_state:
    st.session_state.cached_ai_status = "WAITING..."
if 'cached_breaking' not in st.session_state:
    st.session_state.cached_breaking = None
if 'last_news_hash' not in st.session_state:
    st.session_state.last_news_hash = ""

# ==========================================
# 🎨 DESIGN & CSS (Pro Trading Terminal)
# ==========================================
st.set_page_config(page_title="US100 Sentinel Pro", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Montserrat', sans-serif; }
    header, footer {visibility: hidden;}
    
    /* TRAFFIC LIGHT */
    .traffic-container { display: flex; flex-direction: column; align-items: center; margin-top: -30px; margin-bottom: 20px; }
    .traffic-light { width: 90px; height: 90px; border-radius: 50%; margin-bottom: 15px; transition: all 0.5s ease; }
    .status-text { font-size: 26px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
    
    /* METRICS BOX */
    .dashboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px; }
    .stat-box { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; text-align: center; }
    .label { font-size: 11px; color: #888; letter-spacing: 1px; margin-bottom: 5px; font-weight: 600; }
    .value { font-size: 20px; font-weight: 600; }
    
    /* AI SITUATION REPORT (Bigger & Clearer) */
    .ai-box { margin-bottom: 20px; padding: 15px; border-left: 3px solid #333; }
    .ai-text { font-size: 16px; color: #EEE; line-height: 1.5; font-weight: 400; }
    
    /* BREAKING NEWS ALERT (Hidden by default) */
    .breaking-box { 
        background-color: #300; 
        border: 1px solid #FF0000; 
        color: #FF4444; 
        padding: 15px; 
        text-align: center; 
        font-size: 18px; 
        font-weight: 800; 
        margin-bottom: 30px; 
        border-radius: 5px;
        animation: pulse 2s infinite;
        text-transform: uppercase;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(255, 0, 0, 0); }
        100% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }
    }

    /* LIVE WIRE */
    .news-header { margin-top: 40px; margin-bottom: 10px; font-size: 12px; color: #666; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #222; padding-bottom: 5px;}
    .news-item { margin-bottom: 14px; font-size: 14px; border-left: 2px solid #333; padding-left: 12px; }
    .news-item a { color: #CCC; text-decoration: none; transition: color 0.2s; }
    .news-item a:hover { color: #4da6ff; }
    .time-tag { font-size: 10px; color: #555; display: block; margin-bottom: 2px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 FUNCTIONS
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
    # We fetch this every 60 seconds to keep the "Live Wire" fresh
    rss_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        "https://www.investing.com/rss/news_25.rss"
    ]
    headlines = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]: 
                headlines.append({"title": entry.title, "link": entry.link, "published": entry.get('published', '')})
        except: pass
    return headlines

def run_gemini_analysis(headlines_text):
    # This calls the EXPENSIVE Gemini 3 API (Only runs every 5 mins or if news changes)
    if not AI_AVAILABLE:
        return "#555", "API KEY MISSING", "Please add GOOGLE_API_KEY to Streamlit Secrets.", None

    try:
        prompt = f"""
        Act as a Senior Wall Street Futures Trader. Analyze these headlines for NASDAQ-100 (US100) impact:
        {headlines_text}
        
        Task:
        1. Determine Sentiment (GREEN=Bullish, RED=Bearish, ORANGE=Mixed/Neutral).
        2. Write a Situation Report (2 sentences max).
        3. CHECK FOR BREAKING 3-STAR EVENTS (War, Fed Rate Decision, Major Crash, Unexpected Inflation Data). 
           - If found, extract the event name.
           - If NOT found, write "NONE".
        
        Output format strictly: COLOR|SUMMARY|BREAKING_EVENT
        Example 1: RED|Inflation data came in hotter than expected.|CPI DATA MISS
        Example 2: GREEN|Tech stocks are rallying on Nvidia earnings.|NONE
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        parts = text.split('|')
        
        # Parse standard response
        if len(parts) >= 2:
            color_ref = parts[0].upper()
            summary = parts[1]
            breaking = parts[2] if len(parts) > 2 and "NONE" not in parts[2] else None
        else:
            color_ref = "ORANGE"
            summary = text
            breaking = None

        # Map Colors
        if "GREEN" in color_ref: final_color = "#00FF00"
        elif "RED" in color_ref: final_color = "#FF0000"
        else: final_color = "#FFA500"
        
        status_text = "BULLISH" if "GREEN" in color_ref else "BEARISH" if "RED" in color_ref else "NEUTRAL"
        
        return final_color, status_text, summary, breaking

    except Exception as e:
        return "#FFA500", "AI ERROR", f"Gemini 3 Offline: {str(e)}", None

# ==========================================
# 🚀 MAIN LOOP (Logic Engine)
# ==========================================

# 1. Always get Price & News (Fast)
price, change, pct, sek = get_market_data()
news_items = get_latest_headlines()

# 2. Check if we need to wake up the AI
current_time = time.time()
news_text_blob = str([h['title'] for h in news_items])
news_hash = hashlib.md5(news_text_blob.encode()).hexdigest()

# TRIGGER LOGIC: Run AI if (Time > 5 mins) OR (News has changed significantly)
time_since_last_run = current_time - st.session_state.last_run
news_changed = news_hash != st.session_state.last_news_hash

if time_since_last_run > 300 or news_changed:
    # RUN GEMINI 3 PRO
    color, status, summary, breaking = run_gemini_analysis(news_text_blob)
    
    # Save to memory (Cache)
    st.session_state.cached_ai_color = color
    st.session_state.cached_ai_status = status
    st.session_state.cached_ai_summary = summary
    st.session_state.cached_breaking = breaking
    st.session_state.last_run = current_time
    st.session_state.last_news_hash = news_hash

# ==========================================
# 🖥️ DASHBOARD DISPLAY
# ==========================================

# A. TRAFFIC LIGHT
st.markdown(f"""
<div class="traffic-container">
    <div class="traffic-light" style="background-color: {st.session_state.cached_ai_color}; box-shadow: 0 0 60px {st.session_state.cached_ai_color};"></div>
    <div class="status-text" style="color: {st.session_state.cached_ai_color};">{st.session_state.cached_ai_status}</div>
</div>
""", unsafe_allow_html=True)

# B. METRICS
sign = "+" if change >= 0 else ""
p_color = "#00FF00" if change >= 0 else "#FF4444"

st.markdown(f"""
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

# C. BREAKING NEWS (Conditional)
if st.session_state.cached_breaking:
    st.markdown(f"""
    <div class="breaking-box">
        ⚠ BREAKING: {st.session_state.cached_breaking}
    </div>
    """, unsafe_allow_html=True)
else:
    # Add empty space if no breaking news
    st.markdown('<div style="margin-bottom: 40px;"></div>', unsafe_allow_html=True)

# D. AI REPORT
st.markdown('<div class="label">GEMINI 3 SITUATION REPORT</div>', unsafe_allow_html=True)
st.markdown(f"""
<div class="ai-box" style="border-left-color: {st.session_state.cached_ai_color};">
    <div class="ai-text">{st.session_state.cached_ai_summary}</div>
</div>
""", unsafe_allow_html=True)

# E. LIVE WIRE
st.markdown('<div class="news-header">LIVE WIRE (UPDATED EVERY 60s)</div>', unsafe_allow_html=True)
for item in news_items:
    st.markdown(f"""
    <div class="news-item">
        <span class="time-tag">LATEST</span>
        <a href="{item['link']}" target="_blank">{item['title']}</a>
    </div>
    """, unsafe_allow_html=True)

# Force refresh every 60 seconds (for price & news)
time.sleep(60)
st.rerun()
