import streamlit as st
import yfinance as yf
import feedparser
import time
import google.generativeai as genai
import hashlib
from datetime import datetime
import pytz
import plotly.graph_objects as go # New Charting Tool

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
# CHANGED: Better default message so you know why it's quiet
if 'cached_ai_summary' not in st.session_state: st.session_state.cached_ai_summary = "System Standby. Waiting for US Market Open (09:00 EST)..."
if 'cached_ai_color' not in st.session_state: st.session_state.cached_ai_color = "#333" 
if 'cached_ai_status' not in st.session_state: st.session_state.cached_ai_status = "OFFLINE"
if 'cached_breaking' not in st.session_state: st.session_state.cached_breaking = None

# Chart State
if 'chart_period' not in st.session_state: st.session_state.chart_period = "1d"

# ==========================================
# 🎨 CSS
# ==========================================
st.set_page_config(page_title="US100 VORTEX", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Montserrat', sans-serif; }
    header, footer {visibility: hidden;}
    
    /* DASHBOARD */
    .vortex-header { text-align: center; font-size: 10px; letter-spacing: 4px; color: #666; margin-top: -30px; text-transform: uppercase; }
    .vortex-title { text-align: center; font-size: 42px; font-weight: 700; color: #FFFFFF; margin-bottom: 15px; letter-spacing: -1px; }

    /* HERO LINK */
    .hero-link { text-decoration: none; display: block; transition: transform 0.1s; }
    .hero-link:hover { transform: scale(1.02); }
    .hero-container {
        text-align: center; margin-bottom: 25px; padding: 12px;
        background: radial-gradient(circle at center, #111 0%, #000 70%);
        border: 1px solid #222; border-radius: 10px;
        width: 60%; margin-left: auto; margin-right: auto;
    }
    .hero-label { font-size: 10px; color: #888; letter-spacing: 2px; margin-bottom: 2px; }
    .hero-price { font-size: 32px; font-weight: 700; color: #FFF; line-height: 1.1; }
    .hero-change { font-size: 14px; font-weight: 600; margin-top: 2px; }

    /* COMPONENTS */
    .traffic-container { display: flex; flex-direction: column; align-items: center; margin-bottom: 25px; }
    .traffic-light { width: 100px; height: 100px; border-radius: 50%; margin-bottom: 15px; border: 4px solid #111; }
    .status-text { font-size: 20px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }

    .global-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin-bottom: 25px; background: #080808; padding: 8px; border-radius: 8px; border: 1px solid #222; }
    .global-item { text-align: center; padding: 5px 0; border-right: 1px solid #222; }
    .global-item:last-child { border-right: none; }
    .g-flag { font-size: 10px; color: #666; margin-bottom: 2px; font-weight: 800; }
    .g-price { font-size: 11px; font-weight: 600; color: #DDD; }
    .g-change { font-size: 10px; font-weight: 600; margin-bottom: 2px; }

    .ai-box { margin-bottom: 30px; padding: 15px; border-left: 4px solid #333; background: #080808; }
    .ai-text { font-size: 16px; color: #EEE; line-height: 1.6; font-weight: 400; }
    .breaking-box { background-color: #330000; border: 2px solid #FF0000; color: #FF4444; padding: 15px; text-align: center; font-size: 18px; font-weight: 800; margin-bottom: 30px; border-radius: 5px; text-transform: uppercase; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.7; } 100% { opacity: 1; } }
    
    .news-header { font-size: 12px; color: #666; letter-spacing: 1px; text-transform: uppercase; border-bottom: 1px solid #222; padding-bottom: 8px; margin-bottom: 15px;}
    .news-item { margin-bottom: 14px; font-size: 14px; border-left: 2px solid #333; padding-left: 12px; }
    .news-item a { color: #CCC; text-decoration: none; }
    .news-item a:hover { color: #4da6ff; }

    /* CHART PAGE */
    .back-btn { font-size: 12px; color: #888; text-decoration: none; border: 1px solid #333; padding: 8px 15px; border-radius: 5px; background: #111; }
    .chart-btn-group { display: flex; justify-content: flex-end; gap: 10px; margin-top: 10px; }
    /* Streamlit Button Override to make them small and sleek */
    .stButton > button {
        background-color: #111; color: white; border: 1px solid #333; font-size: 12px; padding: 5px 15px;
    }
    .stButton > button:hover { border-color: #666; color: #FFF; }
    .stButton > button:focus { border-color: #FFF; color: #FFF; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 FUNCTIONS
# ==========================================
def get_current_est_time():
    tz = pytz.timezone('US/Eastern')
    return datetime.now(tz)

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

def get_financial_data():
    try:
        symbols = "NQ=F ^GDAXI ^FTSE ^N225 DX-Y.NYB"
        tickers = yf.Tickers(symbols)
        data = tickers.history(period="2d")
        def get_metrics(symbol):
            if symbol not in data['Close'].columns: return 0, 0
            price = data['Close'][symbol].dropna().iloc[-1]
            open_price = data['Open'][symbol].dropna().iloc[-1]
            change_pct = ((price - open_price) / open_price) * 100
            return price, change_pct
        hero_p, hero_c = get_metrics("NQ=F")
        metrics = {
            'US100': {'p': hero_p, 'c': hero_c},
            'DAX':   get_metrics("^GDAXI"),
            'FTSE':  get_metrics("^FTSE"),
            'NI225': get_metrics("^N225"),
            'DXY':   get_metrics("DX-Y.NYB")
        }
        return metrics
    except: return {}

def run_gemini_analysis(headlines_text, is_end_of_day=False):
    if not AI_AVAILABLE: return "#555", "API ERROR", "Key Missing", None
    try:
        if is_end_of_day:
            prompt = f"Act as a Senior Wall Street Analyst. Market Closed. Analyze these headlines: {headlines_text}. Task: 1. Daily Wrap-Up (Max 3 sentences). 2. End with 'Markets closed. AI is sleeping now.' 3. Color #333. Output: COLOR|SUMMARY|NONE"
        else:
            prompt = f"""
            Act as a Senior NASDAQ Futures Trader. Analyze these headlines: {headlines_text}
            Task 1: Determine Investment Climate (Traffic Light): GREEN=BULLISH, RED=BEARISH, ORANGE=NEUTRAL. *Do not mark Volatility as Red unless Downside.*
            Task 2: Situation Report (Max 60 words): Identify biggest catalyst for NQ futures. Mention 2 other factors.
            Task 3: Check BREAKING 3-STAR EVENTS. Output strictly: COLOR|SUMMARY|BREAKING_EVENT
            """
        response = model.generate_content(prompt)
        text = response.text.strip()
        parts = text.split('|')
        if len(parts) >= 2: color_ref, summary, breaking = parts[0].upper(), parts[1], (parts[2] if len(parts) > 2 and "NONE" not in parts[2] else None)
        else: color_ref, summary, breaking = "ORANGE", text, None
        
        if "#333" in color_ref: final_color = "#333333"
        elif "GREEN" in color_ref: final_color = "#00FF00"
        elif "RED" in color_ref: final_color = "#FF0000"
        else: final_color = "#FFA500"
        
        status_text = "MARKET CLOSED" if is_end_of_day else ("BULLISH CLIMATE" if "GREEN" in color_ref else "BEARISH CLIMATE" if "RED" in color_ref else "NEUTRAL / CHOP")
        return final_color, status_text, summary, breaking
    except Exception as e: return "#FFA500", "AI ERROR", f"Offline: {str(e)}", None

# ==========================================
# 📊 VIEW 1: THE CHART PAGE (Redesigned)
# ==========================================
def show_chart_page():
    # 1. Header with Back Button
    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown('<br><a href="?view=dashboard" target="_self" class="back-btn">← BACK</a>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="vortex-title" style="text-align: right; font-size: 24px;">US100 PERFORMANCE</div>', unsafe_allow_html=True)
    
    st.markdown("---")

    # 2. Determine Data Request based on Button State
    p_map = {"1d": ("1d", "5m"), "7d": ("5d", "15m"), "1mo": ("1mo", "60m"), "1y": ("1y", "1d")}
    yf_period, yf_interval = p_map.get(st.session_state.chart_period, ("1d", "5m"))

    # 3. Fetch Data
    try:
        ticker = yf.Ticker("NQ=F")
        hist = ticker.history(period=yf_period, interval=yf_interval)
        
        if not hist.empty:
            # 4. Create Custom Black Chart (Plotly)
            fig = go.Figure()
            
            # Add Line (White)
            fig.add_trace(go.Scatter(
                x=hist.index, 
                y=hist['Close'], 
                mode='lines', 
                line=dict(color='white', width=2),
                fill='tozeroy', # Optional: faint fill
                fillcolor='rgba(255, 255, 255, 0.1)' 
            ))

            # Styling the Black Box
            fig.update_layout(
                paper_bgcolor='black',
                plot_bgcolor='black',
                margin=dict(l=10, r=10, t=10, b=10),
                height=400,
                xaxis=dict(
                    showgrid=False, 
                    color='#666', 
                    gridcolor='#222'
                ),
                yaxis=dict(
                    showgrid=True, 
                    color='#666', 
                    gridcolor='#222',
                    side='right' # Price on right is standard for trading
                )
            )
            
            # Render the Chart
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
        else:
            st.warning("Chart data unavailable.")
    except:
        st.error("Connection Error.")

    # 5. Bottom Right Buttons
    # Use columns to push buttons to the right
    c1, c2, c3, c4, c5 = st.columns([6, 1, 1, 1, 1])
    
    # Logic: If button clicked, update state and rerun
    with c2:
        if st.button("24h"): 
            st.session_state.chart_period = "1d"
            st.rerun()
    with c3:
        if st.button("7d"): 
            st.session_state.chart_period = "7d"
            st.rerun()
    with c4:
        if st.button("1M"): 
            st.session_state.chart_period = "1mo"
            st.rerun()
    with c5:
        if st.button("1Y"): 
            st.session_state.chart_period = "1y"
            st.rerun()

# ==========================================
# 🏠 VIEW 2: THE DASHBOARD (Main Loop)
# ==========================================
@st.fragment(run_every=60)
def main_dashboard_loop():
    # Placeholders
    header_ph = st.empty()
    traffic_ph = st.empty()
    global_ph = st.empty()
    breaking_ph = st.empty()
    ai_ph = st.empty()
    news_ph = st.empty()
    
    # Logic
    data = get_financial_data()
    news_items = get_latest_headlines()
    
    nq_p, nq_c = data.get('US100', (0,0)).values()
    hero_color = "#00FF00" if nq_c >= 0 else "#FF4444"
    hero_sign = "+" if nq_c >= 0 else ""
    
    # RENDER HEADER (Now with Link!)
    with header_ph.container():
        st.markdown('<div class="vortex-header">ALGORITHMIC NEWS FILTER</div>', unsafe_allow_html=True)
        st.markdown('<div class="vortex-title">US100 VORTEX</div>', unsafe_allow_html=True)
        # The Link Wrapper: ?view=chart triggers the page switch
        st.markdown(f"""
        <a href="?view=chart" target="_self" class="hero-link">
            <div class="hero-container">
                <div class="hero-label">NASDAQ 100 FUTURES (CLICK FOR CHART)</div>
                <div class="hero-price" style="color: {hero_color}; text-shadow: 0 0 20px {hero_color}44;">{nq_p:,.2f}</div>
                <div class="hero-change" style="color: {hero_color};">{hero_sign}{nq_c:.2f}%</div>
            </div>
        </a>
        """, unsafe_allow_html=True)

    with traffic_ph.container():
        st.markdown(f"""
        <div class="traffic-container">
            <div class="traffic-light" style="background-color: {st.session_state.cached_ai_color}; box-shadow: 0 0 80px {st.session_state.cached_ai_color};"></div>
            <div class="status-text" style="color: {st.session_state.cached_ai_color};">{st.session_state.cached_ai_status}</div>
        </div>
        """, unsafe_allow_html=True)

    def color(val): return "#00FF00" if val >= 0 else "#FF4444"
    def fmt_item(label, key):
        p, c = data.get(key, (0,0))
        return f'<div class="global-item"><div class="g-flag">{label}</div><div class="g-price">{p:,.0f}</div><div class="g-change" style="color:{color(c)}">{c:+.1f}%</div></div>'
    
    with global_ph.container():
        st.markdown(f'<div class="global-grid">{fmt_item("🇪🇺 DAX", "DAX")}{fmt_item("🇬🇧 FTSE", "FTSE")}{fmt_item("🇯🇵 NIKKEI", "NI225")}{fmt_item("🇺🇸 DXY", "DXY")}</div>', unsafe_allow_html=True)

    with ai_ph.container():
        st.markdown('<div class="label">GEMINI SITUATION REPORT</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ai-box" style="border-left-color: {st.session_state.cached_ai_color};"><div class="ai-text">{st.session_state.cached_ai_summary}</div></div>', unsafe_allow_html=True)

    if st.session_state.cached_breaking:
        breaking_ph.markdown(f'<div class="breaking-box">⚠ {st.session_state.cached_breaking}</div>', unsafe_allow_html=True)
    
    with news_ph.container():
        st.markdown('<div class="news-header">LIVE WIRE (UPDATED)</div>', unsafe_allow_html=True)
        for item in news_items:
            st.markdown(f'<div class="news-item"><a href="{item["link"]}" target="_blank">{item["title"]}</a></div>', unsafe_allow_html=True)

    # Time & AI Logic
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

# ==========================================
# 🚦 ROUTER
# ==========================================
params = st.query_params
if params.get("view") == "chart":
    show_chart_page()
else:
    main_dashboard_loop()
