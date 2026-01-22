import streamlit as st
import yfinance as yf
import feedparser
import time
import google.generativeai as genai

# ==========================================
# 🔑 SECURE CONFIGURATION
# ==========================================
# This pulls the key from the "Secrets Vault" on Streamlit Cloud
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GOOGLE_API_KEY)
    AI_AVAILABLE = True
except:
    AI_AVAILABLE = False # Runs in "Safe Mode" if key is missing

# ==========================================
# 🎨 DESIGN & CSS (Dark Mode / Montserrat)
# ==========================================
st.set_page_config(page_title="US100 Sentinel", layout="centered")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');
    
    .stApp { background-color: #000000; color: #FFFFFF; font-family: 'Montserrat', sans-serif; }
    header, footer {visibility: hidden;}
    
    /* TRAFFIC LIGHT */
    .traffic-container { display: flex; flex-direction: column; align-items: center; margin-top: -30px; margin-bottom: 30px; }
    .traffic-light { width: 100px; height: 100px; border-radius: 50%; margin-bottom: 15px; }
    .status-text { font-size: 24px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; }
    
    /* METRICS BOX */
    .dashboard-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 30px; }
    .stat-box { background-color: #111; border: 1px solid #333; border-radius: 8px; padding: 15px; text-align: center; }
    .label { font-size: 10px; color: #888; letter-spacing: 1px; margin-bottom: 5px; }
    .value { font-size: 18px; font-weight: 600; }
    .ai-text { font-size: 12px; color: #CCC; line-height: 1.4; text-align: left; }
    
    /* NEWS FEED */
    .news-section { border-top: 1px solid #222; padding-top: 15px; }
    .news-item { margin-bottom: 12px; font-size: 14px; border-left: 2px solid #333; padding-left: 10px; }
    .news-item a { color: #DDD; text-decoration: none; }
    .news-item a:hover { color: #4da6ff; }
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

def get_ai_sentiment():
    rss_urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
        "https://www.investing.com/rss/news_25.rss"
    ]
    headlines = []
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: headlines.append(entry.title)
        except: pass

    if not AI_AVAILABLE:
        return headlines, "#555", "API KEY MISSING", "Add GOOGLE_API_KEY in Streamlit Secrets to activate AI."

    try:
        # Using the absolute flagship Gemini 3 Pro (Preview)
model = genai.GenerativeModel('gemini-3-pro-preview')
        prompt = f"""
        Act as a Wall Street algorithm. Analyze these news headlines for NASDAQ-100 Futures:
        {headlines}
        Output format strictly: COLOR|One sentence summary
        Rules: Green=Bullish, Red=Bearish, Orange=Neutral/Mixed.
        Example: RED|Tariff fears are weighing on tech stocks.
        """
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if "|" in text: color_ref, summary = text.split('|', 1)
        else: color_ref, summary = "ORANGE", text

        if "GREEN" in color_ref.upper(): return headlines, "#00FF00", "BULLISH", summary
        elif "RED" in color_ref.upper(): return headlines, "#FF0000", "BEARISH", summary
        else: return headlines, "#FFA500", "NEUTRAL", summary

    except Exception as e:
        return headlines, "#FFA500", "AI OFFLINE", f"Error: {str(e)}"

# ==========================================
# 🚀 APP EXECUTION
# ==========================================
price, change, pct, sek = get_market_data()
news_list, color, status, ai_summary = get_ai_sentiment()

st.markdown(f"""
<div class="traffic-container">
    <div class="traffic-light" style="background-color: {color}; box-shadow: 0 0 50px {color};"></div>
    <div class="status-text" style="color: {color};">{status}</div>
</div>
<div class="dashboard-grid">
    <div class="stat-box">
        <div class="label">US100 FUTURES</div>
        <div class="value" style="color: {'#00FF00' if change >= 0 else '#FF4444'};">{price:,.0f}</div>
        <div style="font-size: 12px; color: {'#00FF00' if change >= 0 else '#FF4444'};">{'+' if change >= 0 else ''}{change:.1f} ({'+' if change >= 0 else ''}{pct:.1f}%)</div>
    </div>
    <div class="stat-box">
        <div class="label">USD / SEK</div>
        <div class="value" style="color: white;">{sek:.2f} kr</div>
    </div>
</div>
<div class="stat-box" style="margin-bottom: 30px; text-align: left;">
    <div class="label" style="margin-bottom: 10px;">AI SITUATION REPORT</div>
    <div class="ai-text">"{ai_summary}"</div>
</div>
<div class="label">LIVE WIRE</div>
<div class="news-section">
""", unsafe_allow_html=True)

for item in news_list:
    st.markdown(f'<div class="news-item"><a href="#" target="_blank">{item}</a></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

time.sleep(60)
st.rerun()
