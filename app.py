"""
CyberFeed v10 — Fully Streamlit-native, works on Streamlit Cloud free tier.

Architecture:
- NO components.v1.html iframe at all
- Pure Streamlit widgets: st.columns, st.markdown, st.button
- Feed = styled st.markdown cards with st.button triggers
- Reader = full-page Streamlit markdown render
- Theme stored in st.session_state, applied via CSS injection

This is the only approach guaranteed to work everywhere including
Streamlit Cloud free, since it has zero iframe/JS cross-origin issues.
"""

import streamlit as st
import feedparser
import requests
import trafilatura
from datetime import datetime, timezone
import re
import concurrent.futures
import json

st.set_page_config(
    page_title="CyberFeed",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── SESSION STATE INIT ────────────────────────────────────────────────────────
if "theme"        not in st.session_state: st.session_state.theme        = "Midnight"
if "cat"          not in st.session_state: st.session_state.cat          = "All"
if "page"         not in st.session_state: st.session_state.page         = 0
if "src_filter"   not in st.session_state: st.session_state.src_filter   = []
if "reader_url"   not in st.session_state: st.session_state.reader_url   = None
if "reader_title" not in st.session_state: st.session_state.reader_title = ""
if "reader_src"   not in st.session_state: st.session_state.reader_src   = ""
if "reader_color" not in st.session_state: st.session_state.reader_color = "#00C2FF"

# ── THEMES ────────────────────────────────────────────────────────────────────
THEMES = {
    "Midnight": dict(bg="#070A12", sf="#0D1220", sf2="#111827",
                     bd="rgba(255,255,255,0.07)", bdh="rgba(0,194,255,0.4)",
                     tx="#D0DCF0", dim="rgba(208,220,240,0.5)", fnt="rgba(208,220,240,0.28)",
                     ac="#00C2FF", gw="rgba(0,194,255,0.13)"),
    "Obsidian": dict(bg="#0A0A0A", sf="#141414", sf2="#1C1C1C",
                     bd="rgba(255,255,255,0.07)", bdh="rgba(160,120,255,0.4)",
                     tx="#E0D8FF", dim="rgba(224,216,255,0.5)", fnt="rgba(224,216,255,0.25)",
                     ac="#A078FF", gw="rgba(160,120,255,0.13)"),
    "Terminal":  dict(bg="#010B01", sf="#051505", sf2="#081A08",
                     bd="rgba(0,255,65,0.1)", bdh="rgba(0,255,65,0.4)",
                     tx="#B0FFB8", dim="rgba(176,255,184,0.5)", fnt="rgba(176,255,184,0.25)",
                     ac="#00FF41", gw="rgba(0,255,65,0.1)"),
    "Crimson":   dict(bg="#0C0608", sf="#180B0E", sf2="#200E12",
                     bd="rgba(255,255,255,0.06)", bdh="rgba(255,60,80,0.4)",
                     tx="#FFD0D8", dim="rgba(255,208,216,0.5)", fnt="rgba(255,208,216,0.25)",
                     ac="#FF3C50", gw="rgba(255,60,80,0.13)"),
    "Arctic":    dict(bg="#EEF2FA", sf="#FFFFFF", sf2="#F5F8FF",
                     bd="rgba(0,0,0,0.08)", bdh="rgba(0,100,255,0.4)",
                     tx="#1A2540", dim="rgba(26,37,64,0.55)", fnt="rgba(26,37,64,0.32)",
                     ac="#0064FF", gw="rgba(0,100,255,0.1)"),
}

CAT_COLORS = {
    "Threats":        "#FF4B6E",
    "Vulnerabilities":"#00C2FF",
    "Breaches":       "#FF8C00",
    "CVE":            "#E74C3C",
    "Analysis":       "#A78BFA",
}
CATEGORIES = ["All", "Threats", "Vulnerabilities", "Breaches", "CVE", "Analysis"]
PER_PAGE   = 15

# ── FEEDS ─────────────────────────────────────────────────────────────────────
FEEDS = [
    dict(name="The Hacker News",     url="https://feeds.feedburner.com/TheHackersNews",                  cat="Threats",         color="#FF4B6E", icon="📡"),
    dict(name="BleepingComputer",     url="https://www.bleepingcomputer.com/feed/",                       cat="Breaches",        color="#FF8C00", icon="💻"),
    dict(name="Krebs on Security",    url="https://krebsonsecurity.com/feed/",                            cat="Breaches",        color="#9B59B6", icon="🔍"),
    dict(name="Dark Reading",         url="https://www.darkreading.com/rss.xml",                          cat="Threats",         color="#E74C3C", icon="🌑"),
    dict(name="SecurityWeek",         url="https://feeds.feedburner.com/securityweek",                    cat="Threats",         color="#1ABC9C", icon="🗞️"),
    dict(name="SANS ISC",             url="https://isc.sans.edu/rssfeed_full.xml",                        cat="Vulnerabilities",  color="#F39C12", icon="📊"),
    dict(name="Schneier on Security", url="https://www.schneier.com/feed/atom/",                          cat="Analysis",        color="#3498DB", icon="🧠"),
    dict(name="Unit 42",              url="https://unit42.paloaltonetworks.com/feed/",                    cat="Analysis",        color="#27AE60", icon="🔬"),
    dict(name="Google Project Zero",  url="https://googleprojectzero.blogspot.com/feeds/posts/default",   cat="Vulnerabilities",  color="#4285F4", icon="⓪"),
    dict(name="Malwarebytes Labs",     url="https://www.malwarebytes.com/blog/feed/",                      cat="Threats",         color="#D35400", icon="🦠"),
    dict(name="WeLiveSecurity",       url="https://www.welivesecurity.com/feed/",                         cat="Analysis",        color="#16A085", icon="🛡️"),
    dict(name="NIST NVD",             url="https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss-analyzed.xml", cat="CVE",             color="#C0392B", icon="📋"),
    dict(name="Exploit-DB",           url="https://www.exploit-db.com/rss.xml",                           cat="CVE",             color="#922B21", icon="💥"),
    dict(name="Troy Hunt",            url="https://www.troyhunt.com/rss/",                                cat="Breaches",        color="#E91E63", icon="🔓"),
    dict(name="Graham Cluley",        url="https://grahamcluley.com/feed/",                               cat="Breaches",        color="#607D8B", icon="📰"),
    dict(name="Recorded Future",      url="https://www.recordedfuture.com/feed",                          cat="Analysis",        color="#8E44AD", icon="🎯"),
    dict(name="Threatpost",           url="https://threatpost.com/feed/",                                 cat="Threats",         color="#E67E22", icon="⚠️"),
    dict(name="HackerOne",            url="https://hackerone.com/hacktivity.rss",                         cat="CVE",             color="#FF6B35", icon="🏆"),
]

# ── FETCH RSS ─────────────────────────────────────────────────────────────────
def parse_date(entry):
    for a in ("published_parsed","updated_parsed","created_parsed"):
        v = getattr(entry, a, None)
        if v:
            try: return datetime(*v[:6], tzinfo=timezone.utc)
            except: pass
    return datetime(2000,1,1,tzinfo=timezone.utc)

def time_ago(dt):
    s = max(0, int((datetime.now(timezone.utc)-dt).total_seconds()))
    if s<60:    return f"{s}s ago"
    if s<3600:  return f"{s//60}m ago"
    if s<86400: return f"{s//3600}h ago"
    d = s//86400
    return f"{d}d ago" if d<30 else dt.strftime("%b %d")

def clean(txt):
    txt = re.sub(r'<[^>]+',' ', txt or '')
    txt = re.sub(r'\s+',' ', txt).strip()
    return txt[:260]+"…" if len(txt)>260 else txt

def fetch_one(feed):
    try:
        r = requests.get(feed["url"], timeout=8, headers={"User-Agent":"CyberFeed/10.0"})
        r.raise_for_status()
        parsed = feedparser.parse(r.text)
        out = []
        for e in parsed.entries[:20]:
            dt = parse_date(e)
            out.append(dict(
                title   = (e.get("title") or "Untitled").strip(),
                url     = e.get("link","#"),
                summary = clean(e.get("summary") or e.get("description") or ""),
                src=feed["name"], cat=feed["cat"],
                color=feed["color"], icon=feed["icon"],
                ts=int(dt.timestamp()), ago=time_ago(dt),
                fresh=(datetime.now(timezone.utc)-dt).total_seconds()<14400,
            ))
        return out, None
    except Exception as ex:
        return [], f"{feed['name']}: {str(ex)[:60]}"

@st.cache_data(ttl=300, show_spinner=False)
def fetch_all():
    arts, errs = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futs = {pool.submit(fetch_one,f): f["name"] for f in FEEDS}
        done, pending = concurrent.futures.wait(futs, timeout=20)
        for f in done:
            items, err = f.result()
            arts.extend(items)
            if err: errs.append(err)
        for f in pending:
            errs.append(f"{futs[f]}: timeout")
            f.cancel()
    arts.sort(key=lambda x: x["ts"], reverse=True)
    return arts, errs

@st.cache_data(ttl=600, show_spinner=False)
def fetch_article(url: str) -> dict:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        }
        resp = requests.get(url, timeout=12, headers=headers, allow_redirects=True)
        resp.raise_for_status()
        text = trafilatura.extract(
            resp.text, include_comments=False,
            include_tables=True, favor_recall=True,
            output_format="txt",
        )
        if not text or len(text.strip()) < 80:
            return {"ok": False, "error": "Content could not be extracted. The site may require JavaScript or a subscription."}
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        return {"ok": True, "paragraphs": paragraphs, "word_count": len(text.split())}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "Request timed out (12s)."}
    except requests.exceptions.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:120]}

# ── CSS INJECTION ─────────────────────────────────────────────────────────────
def inject_css(t):
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > .main,
section[data-testid="stMain"],
.main .block-container,
[data-testid="block-container"] {{
    background: {t['bg']} !important;
    color: {t['tx']} !important;
}}
[data-testid="block-container"] {{
    padding: 0 !important;
    max-width: 100% !important;
}}
[data-testid="stVerticalBlock"] {{ gap: 0 !important; }}
header[data-testid="stHeader"],
[data-testid="stSidebar"],
#MainMenu, .stDeployButton, footer,
.stStatusWidget, [data-testid="stToolbar"] {{ display: none !important; }}

/* Remove top padding Streamlit adds */
.main .block-container {{ padding-top: 0 !important; }}

/* Buttons */
.stButton > button {{
    background: {t['gw']} !important;
    border: 1px solid {t['bdh']} !important;
    border-radius: 6px !important;
    color: {t['ac']} !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    padding: 3px 10px !important;
    transition: all .18s !important;
    white-space: nowrap !important;
}}
.stButton > button:hover {{
    background: {t['ac']} !important;
    color: {t['bg']} !important;
}}

/* Read button variant */
.read-variant > button {{
    background: {t['sf2']} !important;
    border: 1px solid {t['bd']} !important;
    color: {t['tx']} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 10px !important;
    font-weight: 500 !important;
}}
.read-variant > button:hover {{
    border-color: {t['bdh']} !important;
    color: {t['ac']} !important;
    background: {t['gw']} !important;
}}

/* Selectbox */
.stSelectbox label {{ display: none !important; }}
[data-baseweb="select"] > div {{
    background: {t['sf2']} !important;
    border: 1px solid {t['bd']} !important;
    border-radius: 7px !important;
    color: {t['tx']} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important;
    min-height: 34px !important;
}}
[data-baseweb="select"] > div:focus-within {{
    border-color: {t['bdh']} !important;
    box-shadow: 0 0 0 2px {t['gw']} !important;
}}
[data-baseweb="popover"] ul {{
    background: {t['sf']} !important;
    border: 1px solid {t['bd']} !important;
}}
[data-baseweb="popover"] li {{
    color: {t['tx']} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 11px !important;
}}
[data-baseweb="popover"] li:hover {{ background: {t['gw']} !important; }}

/* Text input */
.stTextInput label {{ display: none !important; }}
.stTextInput > div > div > input {{
    background: {t['sf2']} !important;
    border: 1px solid {t['bd']} !important;
    border-radius: 7px !important;
    color: {t['tx']} !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 12px !important;
    height: 34px !important;
}}
.stTextInput > div > div > input:focus {{
    border-color: {t['bdh']} !important;
    box-shadow: 0 0 0 2px {t['gw']} !important;
}}
.stTextInput > div > div > input::placeholder {{ color: {t['fnt']} !important; }}

/* Multiselect */
.stMultiSelect label {{ display: none !important; }}
.stMultiSelect [data-baseweb="select"] > div {{
    background: {t['sf2']} !important;
    border: 1px solid {t['bd']} !important;
    border-radius: 7px !important;
    min-height: 34px !important;
}}
span[data-baseweb="tag"] {{
    background: {t['gw']} !important;
    border: 1px solid {t['bdh']} !important;
    border-radius: 4px !important;
    color: {t['ac']} !important;
}}

/* Divider */
hr {{ border-color: {t['bd']} !important; margin: 6px 0 !important; }}

/* Scrollbar */
::-webkit-scrollbar {{ width: 4px; height: 4px; }}
::-webkit-scrollbar-track {{ background: {t['bg']}; }}
::-webkit-scrollbar-thumb {{ background: {t['bdh']}; border-radius: 2px; }}

/* Columns gap */
[data-testid="stHorizontalBlock"] {{ gap: 8px !important; align-items: center !important; }}
</style>
""", unsafe_allow_html=True)

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
with st.spinner("Fetching security feeds…"):
    articles, errors = fetch_all()

t = THEMES[st.session_state.theme]
inject_css(t)

# ═══════════════════════════════════════════════════════════════
# READER PAGE
# ═══════════════════════════════════════════════════════════════
if st.session_state.reader_url:
    color = st.session_state.reader_color

    # Header row
    col_back, col_orig = st.columns([2, 7])
    with col_back:
        st.markdown('<div style="padding:10px 0 4px 16px">', unsafe_allow_html=True)
        if st.button("← Back to feed", key="back_btn"):
            st.session_state.reader_url = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with col_orig:
        st.markdown(f"""
        <div style="padding:14px 0 4px;font-family:'JetBrains Mono',monospace;
            font-size:10px;color:{t['fnt']};letter-spacing:.5px;">
            READING · <span style="color:{color};font-weight:700">{st.session_state.reader_src}</span>
        </div>""", unsafe_allow_html=True)

    # Article header box
    url_safe = st.session_state.reader_url.replace('"','%22')
    title_safe = st.session_state.reader_title.replace('<','&lt;').replace('>','&gt;')
    st.markdown(f"""
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <div style="
        background:{t['sf']};border:1px solid {color}33;
        border-radius:12px;overflow:hidden;
        box-shadow:0 8px 40px rgba(0,0,0,.5);
        margin:0 16px 4px;
    ">
        <div style="
            background:linear-gradient(135deg,{color}18,{color}05);
            border-bottom:1px solid {color}22;
            padding:20px 28px;
            display:flex;align-items:flex-start;justify-content:space-between;gap:16px;
        ">
            <div style="flex:1">
                <div style="
                    font-family:'JetBrains Mono',monospace;font-size:10px;
                    font-weight:700;letter-spacing:2px;color:{color};
                    text-transform:uppercase;margin-bottom:10px;
                ">{st.session_state.reader_src}</div>
                <div style="
                    font-size:20px;font-weight:800;color:{t['tx']};
                    line-height:1.4;font-family:'Inter',sans-serif;
                ">{title_safe}</div>
            </div>
            <a href="{url_safe}" target="_blank" style="
                flex-shrink:0;margin-top:4px;
                font-family:'JetBrains Mono',monospace;font-size:10px;
                font-weight:700;color:{color};text-decoration:none;
                padding:7px 14px;border:1px solid {color}44;
                border-radius:7px;background:{color}12;white-space:nowrap;
            ">↗ Original</a>
        </div>
    """, unsafe_allow_html=True)

    # Fetch content
    with st.spinner("Extracting article…"):
        content = fetch_article(st.session_state.reader_url)

    if content["ok"]:
        wc = content["word_count"]
        rm = max(1, round(wc / 200))
        st.markdown(f"""
        <div style="padding:20px 28px 0;">
        <div style="font-family:'JetBrains Mono',monospace;font-size:9px;
            color:{t['fnt']};letter-spacing:.8px;margin-bottom:20px;">
            {wc:,} words · ~{rm} min read
        </div>""", unsafe_allow_html=True)

        for p in content["paragraphs"]:
            p_e = p.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            is_h = (len(p) < 100 and not p.endswith(('.', ',', ':'))
                    and len(p) > 8 and not p[0].islower())
            if is_h:
                st.markdown(f"""<div style="
                    font-family:'Inter',sans-serif;font-size:17px;font-weight:700;
                    color:{t['tx']};margin:26px 28px 10px;line-height:1.4;
                ">{p_e}</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<p style="
                    font-family:'Inter',sans-serif;font-size:14px;
                    color:rgba(208,220,240,.78);line-height:1.9;
                    margin:0 28px 14px;
                ">{p_e}</p>""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center;padding:52px 24px;">
            <div style="font-size:40px;opacity:.2;margin-bottom:14px;">📄</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;
                color:{t['fnt']};margin-bottom:8px;">Could not extract content</div>
            <div style="font-family:'Inter',sans-serif;font-size:11px;
                color:{t['fnt']};opacity:.7;max-width:480px;margin:0 auto 20px;line-height:1.6;">
                {content['error']}
            </div>
            <a href="{url_safe}" target="_blank" style="
                font-family:'Inter',sans-serif;font-size:12px;color:{color};
                text-decoration:none;padding:9px 22px;border:1px solid {color}44;
                border-radius:8px;background:{color}12;">
                Open original in browser →
            </a>
        </div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # close card
    st.markdown("---")
    # Show feed below reader too
    show_feed = True
else:
    show_feed = True

# ═══════════════════════════════════════════════════════════════
# FEED PAGE
# ═══════════════════════════════════════════════════════════════
if not show_feed:
    st.stop()

now_str = datetime.now().strftime("%d %b %Y %H:%M")

# ── NAVBAR ────────────────────────────────────────────────────
cc = {}
for a in articles: cc[a["cat"]] = cc.get(a["cat"], 0) + 1
fresh_n = sum(1 for a in articles if a["fresh"])
active  = len(FEEDS) - len(errors)

st.markdown(f"""
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<div style="
    background:{t['sf']};border-bottom:1px solid {t['bd']};
    height:46px;display:flex;align-items:center;padding:0 20px;gap:0;
    box-shadow:0 1px 20px rgba(0,0,0,.4);position:sticky;top:0;z-index:100;
">
    <div style="
        font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;
        letter-spacing:2px;color:{t['ac']};display:flex;align-items:center;gap:8px;flex-shrink:0;
    ">
        <div style="width:7px;height:7px;border-radius:50%;background:{t['ac']};
            box-shadow:0 0 8px {t['ac']};animation:blink 2s ease-in-out infinite;"></div>
        CYBERFEED
    </div>
    <div style="display:flex;align-items:center;margin-left:20px;flex:1;overflow:hidden;">
        <div style="display:flex;align-items:baseline;gap:4px;padding:0 14px;border-right:1px solid {t['bd']};flex-shrink:0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:{t['ac']};">{len(articles)}</span>
            <span style="font-family:'Inter',sans-serif;font-size:9px;color:{t['fnt']};text-transform:uppercase;letter-spacing:1px;">Articles</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;padding:0 14px;border-right:1px solid {t['bd']};flex-shrink:0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#00D68F;">{active}/{len(FEEDS)}</span>
            <span style="font-family:'Inter',sans-serif;font-size:9px;color:{t['fnt']};text-transform:uppercase;letter-spacing:1px;">Feeds</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;padding:0 14px;border-right:1px solid {t['bd']};flex-shrink:0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#FF4B6E;">{fresh_n}</span>
            <span style="font-family:'Inter',sans-serif;font-size:9px;color:{t['fnt']};text-transform:uppercase;letter-spacing:1px;">New 4h</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;padding:0 14px;border-right:1px solid {t['bd']};flex-shrink:0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#FF4B6E;">{cc.get('Threats',0)}</span>
            <span style="font-family:'Inter',sans-serif;font-size:9px;color:{t['fnt']};text-transform:uppercase;letter-spacing:1px;">Threats</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;padding:0 14px;border-right:1px solid {t['bd']};flex-shrink:0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:{t['ac']};">{cc.get('Vulnerabilities',0)}</span>
            <span style="font-family:'Inter',sans-serif;font-size:9px;color:{t['fnt']};text-transform:uppercase;letter-spacing:1px;">Vulns</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;padding:0 14px;border-right:1px solid {t['bd']};flex-shrink:0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#E74C3C;">{cc.get('CVE',0)}</span>
            <span style="font-family:'Inter',sans-serif;font-size:9px;color:{t['fnt']};text-transform:uppercase;letter-spacing:1px;">CVE</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:4px;padding:0 14px;border-right:1px solid {t['bd']};flex-shrink:0;">
            <span style="font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:#FF8C00;">{cc.get('Breaches',0)}</span>
            <span style="font-family:'Inter',sans-serif;font-size:9px;color:{t['fnt']};text-transform:uppercase;letter-spacing:1px;">Breaches</span>
        </div>
    </div>
    <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{t['fnt']};flex-shrink:0;">{now_str}</div>
</div>
<style>@keyframes blink{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.2;transform:scale(.55)}}}}</style>
""", unsafe_allow_html=True)

# ── TICKER ─────────────────────────────────────────────────────
cat_icons = {"Threats":"🔴","CVE":"🟠","Breaches":"🟡","Vulnerabilities":"🔵","Analysis":"🟣"}
ticker_items = "".join([
    f'<span style="font-family:Inter,sans-serif;font-size:11px;color:{t["dim"]};margin-right:28px;">'
    f'{cat_icons.get(a["cat"],"⚪")} {a["title"][:65]}{"…" if len(a["title"])>65 else ""}</span>'
    f'<span style="color:{t["ac"]};opacity:.2;margin-right:28px;">·</span>'
    for a in articles[:22]
])
st.markdown(f"""
<div style="background:{t['sf']};border-bottom:1px solid {t['bd']};
    height:26px;display:flex;align-items:center;overflow:hidden;">
    <div style="font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;
        color:{t['ac']};letter-spacing:2px;padding:0 11px;flex-shrink:0;
        border-right:1px solid {t['bd']};white-space:nowrap;">LIVE</div>
    <div style="flex:1;overflow:hidden;">
        <div style="display:inline-block;white-space:nowrap;animation:scroll-t 100s linear infinite;">
            {ticker_items}{ticker_items}
        </div>
    </div>
</div>
<style>@keyframes scroll-t{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}</style>
""", unsafe_allow_html=True)

# ── TOOLBAR ────────────────────────────────────────────────────
tc1, tc2, tc3, tc4, tc5 = st.columns([4, 1.4, 1.5, 1.4, 0.9])
with tc1:
    search = st.text_input("s", placeholder="🔍  Search headlines, CVEs, threat actors, APTs…",
                           label_visibility="collapsed", key="search_input")
with tc2:
    cat_idx = CATEGORIES.index(st.session_state.cat) if st.session_state.cat in CATEGORIES else 0
    new_cat = st.selectbox("cat", CATEGORIES, index=cat_idx, label_visibility="collapsed", key="cat_sel")
    if new_cat != st.session_state.cat:
        st.session_state.cat  = new_cat
        st.session_state.page = 0
        st.rerun()
with tc3:
    all_src = sorted(set(a["src"] for a in articles))
    new_srcs = st.multiselect("src", all_src, default=st.session_state.src_filter,
                               placeholder="All sources", label_visibility="collapsed", key="src_ms")
    if new_srcs != st.session_state.src_filter:
        st.session_state.src_filter = new_srcs
        st.session_state.page = 0
        st.rerun()
with tc4:
    th_names = list(THEMES.keys())
    new_th = st.selectbox("theme", th_names,
                           index=th_names.index(st.session_state.theme),
                           label_visibility="collapsed", key="theme_sel")
    if new_th != st.session_state.theme:
        st.session_state.theme = new_th
        st.rerun()
with tc5:
    if st.button("↻ REFRESH", key="refresh_btn"):
        st.cache_data.clear()
        st.rerun()

# ── CAT TABS ───────────────────────────────────────────────────
tabs_html = f'<div style="background:{t["sf"]};border-bottom:1px solid {t["bd"]};padding:0 18px;display:flex;overflow-x:auto;margin-bottom:0;">'
for c in CATEGORIES:
    n   = len(articles) if c=="All" else cc.get(c,0)
    on  = c == st.session_state.cat
    col = t['ac'] if on else t['fnt']
    bdb = f"2px solid {t['ac']}" if on else "2px solid transparent"
    bg  = t['gw'] if on else "transparent"
    tabs_html += f"""<div style="
        font-family:'Inter',sans-serif;font-size:11px;font-weight:500;
        padding:9px 14px 7px;color:{col};border-bottom:{bdb};
        white-space:nowrap;background:{bg};
    ">{c}<span style="font-family:'JetBrains Mono',monospace;font-size:8px;opacity:.35;margin-left:3px;">({n})</span></div>"""
tabs_html += "</div>"
st.markdown(tabs_html, unsafe_allow_html=True)

# ── SOURCE PILLS ───────────────────────────────────────────────
pills_html = f'<div style="background:{t["bg"]};border-bottom:1px solid {t["bd"]};padding:5px 18px;display:flex;align-items:center;gap:5px;overflow-x:auto;flex-wrap:wrap;">'
pills_html += f'<span style="font-family:\'JetBrains Mono\',monospace;font-size:8px;color:{t["fnt"]};letter-spacing:1.5px;text-transform:uppercase;flex-shrink:0;">Sources</span>'
for s in all_src:
    on  = s in st.session_state.src_filter
    col = t['ac'] if on else t['dim']
    bd  = t['bdh'] if on else t['bd']
    bg  = t['gw'] if on else "transparent"
    pills_html += f'<span style="font-family:Inter,sans-serif;font-size:10px;padding:2px 8px;border-radius:20px;border:1px solid {bd};color:{col};background:{bg};flex-shrink:0;">{s}</span>'
pills_html += "</div>"
st.markdown(pills_html, unsafe_allow_html=True)

# ── FILTER ARTICLES ────────────────────────────────────────────
filtered = articles
if st.session_state.cat != "All":
    filtered = [a for a in filtered if a["cat"] == st.session_state.cat]
if st.session_state.src_filter:
    filtered = [a for a in filtered if a["src"] in st.session_state.src_filter]
if search and len(search) >= 2:
    q = search.lower()
    filtered = [a for a in filtered if q in a["title"].lower() or q in a["summary"].lower()]

total = len(filtered)
max_page = max(0, (total - 1) // PER_PAGE)
if st.session_state.page > max_page:
    st.session_state.page = 0
page_arts = filtered[st.session_state.page * PER_PAGE : (st.session_state.page + 1) * PER_PAGE]

# ── FEED HEADER + PAGINATION ───────────────────────────────────
lbl = f"{total} articles"
if search:                         lbl += f' · "{search}"'
if st.session_state.cat != "All": lbl += f" · {st.session_state.cat}"
if st.session_state.src_filter:   lbl += f" · {len(st.session_state.src_filter)} source(s)"

total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
cur = st.session_state.page

# Label + pagination in one row
hc1, hc2 = st.columns([3, 2])
with hc1:
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:{t['fnt']};
        text-transform:uppercase;letter-spacing:2px;padding:14px 18px 8px;
        display:flex;align-items:center;gap:10px;">
        {lbl}
        <span style="flex:1;height:1px;background:{t['bd']};display:inline-block;"></span>
    </div>""", unsafe_allow_html=True)
with hc2:
    if total_pages > 1:
        pc = st.columns(min(total_pages + 2, 12))
        with pc[0]:
            if st.button("‹", key="pg_prev", disabled=(cur==0)):
                st.session_state.page = cur - 1
                st.rerun()
        visible_pages = sorted(set(
            [0, total_pages-1] + list(range(max(0,cur-1), min(total_pages, cur+2)))
        ))
        col_i = 1
        prev_p = -1
        for p in visible_pages:
            if prev_p >= 0 and p - prev_p > 1 and col_i < len(pc)-1:
                with pc[col_i]: st.markdown(f'<div style="color:{t["fnt"]};font-size:10px;text-align:center;padding-top:6px;">…</div>', unsafe_allow_html=True)
                col_i += 1
            if col_i < len(pc) - 1:
                with pc[col_i]:
                    label = f"**{p+1}**" if p == cur else str(p+1)
                    if st.button(label, key=f"pg_{p}"):
                        st.session_state.page = p
                        st.rerun()
                col_i += 1
            prev_p = p
        if col_i < len(pc):
            with pc[col_i]:
                if st.button("›", key="pg_next", disabled=(cur>=total_pages-1)):
                    st.session_state.page = cur + 1
                    st.rerun()

# ── ERROR EXPANDER ─────────────────────────────────────────────
if errors:
    with st.expander(f"⚠ {len(errors)} feed(s) unreachable", expanded=False):
        for e in errors:
            st.markdown(f'<div style="font-family:JetBrains Mono,monospace;font-size:10px;color:#FF4B6E;padding:2px 0;">✗ {e}</div>', unsafe_allow_html=True)

# ── ARTICLE GRID ───────────────────────────────────────────────
if not page_arts:
    st.markdown(f'<div style="text-align:center;padding:60px;font-family:JetBrains Mono,monospace;font-size:11px;color:{t["fnt"]};">📡<br><br>No articles match your filters.</div>', unsafe_allow_html=True)
else:
    cols = st.columns(3, gap="small")
    for i, a in enumerate(page_arts):
        with cols[i % 3]:
            c   = a["color"]
            cc2 = CAT_COLORS.get(a["cat"], "#888")
            nb  = '<span style="display:inline-block;font-family:JetBrains Mono,monospace;font-size:7px;font-weight:700;letter-spacing:1px;color:#fff;background:#FF3C50;padding:2px 4px;border-radius:3px;margin-left:5px;vertical-align:middle;">NEW</span>' if a["fresh"] else ""
            title_e   = a["title"].replace("<","&lt;").replace(">","&gt;")
            summary_e = a["summary"].replace("<","&lt;").replace(">","&gt;")

            st.markdown(f"""
            <div style="
                background:{t['sf']};border:1px solid {t['bd']};
                border-radius:9px;padding:14px 15px 6px;
                position:relative;overflow:hidden;
                border-left:3px solid {c};
                transition:border-color .2s;
                margin-bottom:0;
            ">
                <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:8px;">
                    <div style="font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;
                        padding:2px 8px;border-radius:20px;
                        color:{c};border:1px solid {c}44;background:{c}14;
                        white-space:nowrap;flex-shrink:0;">
                        {a['icon']} {a['src']}
                    </div>
                    <div style="font-family:'JetBrains Mono',monospace;font-size:9px;color:{t['fnt']};white-space:nowrap;">{a['ago']}</div>
                </div>
                <div style="font-family:'Inter',sans-serif;font-size:13px;font-weight:600;
                    color:{t['tx']};line-height:1.5;margin-bottom:7px;
                    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                    {title_e}{nb}
                </div>
                <div style="font-family:'Inter',sans-serif;font-size:11px;color:{t['dim']};
                    line-height:1.6;margin-bottom:10px;
                    display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;">
                    {summary_e}
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;
                        text-transform:uppercase;letter-spacing:1.5px;padding:2px 7px;border-radius:4px;
                        color:{cc2};background:{cc2}18;">{a['cat']}</span>
                    <a href="{a['url']}" target="_blank" style="
                        font-family:'Inter',sans-serif;font-size:10px;font-weight:500;
                        color:{t['ac']};text-decoration:none;padding:3px 9px;
                        border:1px solid {t['bdh']};border-radius:5px;background:{t['gw']};">
                        ↗ Open
                    </a>
                </div>
            </div>""", unsafe_allow_html=True)

            # Read here button — NATIVE Streamlit button, zero iframe/JS issues
            btn_col = st.columns([1])[0]
            with btn_col:
                st.markdown(f'<div class="read-variant" style="margin:-4px 0 12px;">', unsafe_allow_html=True)
                if st.button(f"📖 Read here", key=f"read_{i}_{st.session_state.page}_{st.session_state.cat}"):
                    st.session_state.reader_url   = a["url"]
                    st.session_state.reader_title = a["title"]
                    st.session_state.reader_src   = a["src"]
                    st.session_state.reader_color = a["color"]
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
