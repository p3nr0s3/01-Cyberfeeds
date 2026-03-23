"""
CyberFeed v11
- Feed UI: full HTML in st.components (looks great)
- Reader trigger: window.top.location.search (same-origin, works on Streamlit Cloud)
- Reader render: pure Streamlit markdown (server-side fetch, works on Cloud)
- Toolbar, cards, ticker, tabs, sources: all in HTML iframe
"""

import streamlit as st
import feedparser
import requests
import trafilatura
from datetime import datetime, timezone
import re
import concurrent.futures
import json
from urllib.parse import unquote

st.set_page_config(
    page_title="CyberFeed",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Hide Streamlit chrome completely ─────────────────────────────────────────
st.markdown("""
<style>
*{margin:0;padding:0;box-sizing:border-box;}
html,body,.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"]>.main,
section[data-testid="stMain"],
section[data-testid="stMain"]>div,
[data-testid="block-container"],
.main .block-container{
  background:#070A12!important;
  padding:0!important;margin:0!important;
  max-width:100%!important;
}
header[data-testid="stHeader"],
[data-testid="stSidebar"],
#MainMenu,.stDeployButton,footer,
.stStatusWidget,[data-testid="stToolbar"]{display:none!important;}
[data-testid="stVerticalBlock"]{gap:0!important;}
iframe{border:none!important;display:block!important;width:100%!important;}
</style>
""", unsafe_allow_html=True)

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

# ── HELPERS ───────────────────────────────────────────────────────────────────
def parse_date(entry):
    for a in ("published_parsed","updated_parsed","created_parsed"):
        v = getattr(entry, a, None)
        if v:
            try: return datetime(*v[:6], tzinfo=timezone.utc)
            except: pass
    return datetime(2000,1,1,tzinfo=timezone.utc)

def time_ago(dt):
    s = max(0,int((datetime.now(timezone.utc)-dt).total_seconds()))
    if s<60:    return f"{s}s ago"
    if s<3600:  return f"{s//60}m ago"
    if s<86400: return f"{s//3600}h ago"
    d=s//86400
    return f"{d}d ago" if d<30 else dt.strftime("%b %d")

def clean(txt):
    txt=re.sub(r'<[^>]+',' ',txt or '')
    txt=re.sub(r'\s+',' ',txt).strip()
    return txt[:260]+"…" if len(txt)>260 else txt

def fetch_one(feed):
    try:
        r=requests.get(feed["url"],timeout=8,headers={"User-Agent":"CyberFeed/11.0"})
        r.raise_for_status()
        parsed=feedparser.parse(r.text)
        out=[]
        for e in parsed.entries[:20]:
            dt=parse_date(e)
            out.append(dict(
                title=(e.get("title") or "Untitled").strip(),
                url=e.get("link","#"),
                summary=clean(e.get("summary") or e.get("description") or ""),
                src=feed["name"],cat=feed["cat"],
                color=feed["color"],icon=feed["icon"],
                ts=int(dt.timestamp()),ago=time_ago(dt),
                fresh=(datetime.now(timezone.utc)-dt).total_seconds()<14400,
            ))
        return out,None
    except Exception as ex:
        return [],f"{feed['name']}: {str(ex)[:60]}"

@st.cache_data(ttl=300,show_spinner=False)
def fetch_all():
    arts,errs=[],[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futs={pool.submit(fetch_one,f):f["name"] for f in FEEDS}
        done,pending=concurrent.futures.wait(futs,timeout=20)
        for f in done:
            items,err=f.result()
            arts.extend(items)
            if err: errs.append(err)
        for f in pending:
            errs.append(f"{futs[f]}: timeout")
            f.cancel()
    arts.sort(key=lambda x:x["ts"],reverse=True)
    return arts,errs

@st.cache_data(ttl=600,show_spinner=False)
def fetch_article(url:str)->dict:
    try:
        r=requests.get(url,timeout=12,headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept":"text/html,application/xhtml+xml,*/*;q=0.8",
        },allow_redirects=True)
        r.raise_for_status()
        text=trafilatura.extract(r.text,include_comments=False,include_tables=True,
                                  favor_recall=True,output_format="txt")
        if not text or len(text.strip())<80:
            return {"ok":False,"error":"Content could not be extracted. This site may use JavaScript rendering or require a subscription."}
        paras=[p.strip() for p in text.split("\n") if p.strip()]
        return {"ok":True,"paragraphs":paras,"word_count":len(text.split())}
    except requests.exceptions.Timeout:
        return {"ok":False,"error":"Request timed out (12s)."}
    except requests.exceptions.HTTPError as e:
        return {"ok":False,"error":f"HTTP {e.response.status_code}: {e.response.reason}"}
    except Exception as e:
        return {"ok":False,"error":str(e)[:120]}

# ── LOAD DATA ─────────────────────────────────────────────────────────────────
with st.spinner("Fetching security feeds…"):
    articles, errors = fetch_all()

# ── READ QUERY PARAMS ─────────────────────────────────────────────────────────
qp           = st.query_params
reader_url   = unquote(qp.get("read",   ""))
reader_title = unquote(qp.get("rtitle", ""))
reader_src   = unquote(qp.get("rsrc",   ""))
reader_color = unquote(qp.get("rcolor", "#00C2FF"))

now_str = datetime.now().strftime("%d %b %Y %H:%M")

# ═══════════════════════════════════════════════════════════
# READER MODE
# ═══════════════════════════════════════════════════════════
if reader_url:
    # Back button — native Streamlit, always works
    if st.button("← Back to feed", key="back_btn"):
        st.query_params.clear()
        st.rerun()

    color = reader_color
    url_s = reader_url.replace('"','%22')
    title_s = reader_title.replace('<','&lt;').replace('>','&gt;').replace('&','&amp;')

    st.markdown(f"""
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
    .stButton>button{{
        background:rgba(0,194,255,.1)!important;
        border:1px solid rgba(0,194,255,.35)!important;
        border-radius:7px!important;color:#00C2FF!important;
        font-family:'JetBrains Mono',monospace!important;
        font-size:11px!important;font-weight:700!important;
        padding:6px 16px!important;margin:10px 0 16px!important;
    }}
    </style>
    <div style="background:#0D1220;border:1px solid {color}33;border-radius:12px;
        overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.5);margin-bottom:4px;">
        <div style="background:linear-gradient(135deg,{color}18,{color}05);
            border-bottom:1px solid {color}22;padding:20px 28px;
            display:flex;align-items:flex-start;justify-content:space-between;gap:16px;">
            <div style="flex:1">
                <div style="font-family:'JetBrains Mono',monospace;font-size:10px;
                    font-weight:700;letter-spacing:2px;color:{color};
                    text-transform:uppercase;margin-bottom:10px;">{reader_src}</div>
                <div style="font-size:20px;font-weight:800;color:#E8F0FB;
                    line-height:1.4;font-family:'Inter',sans-serif;">{title_s}</div>
            </div>
            <a href="{url_s}" target="_blank" style="flex-shrink:0;margin-top:4px;
                font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;
                color:{color};text-decoration:none;padding:7px 14px;
                border:1px solid {color}44;border-radius:7px;background:{color}12;
                white-space:nowrap;">↗ Original</a>
        </div>
    """, unsafe_allow_html=True)

    with st.spinner("Extracting article…"):
        content = fetch_article(reader_url)

    if content["ok"]:
        wc = content["word_count"]
        rm = max(1, round(wc/200))
        st.markdown(f"""
        <div style="padding:20px 28px 4px;">
        <div style="font-family:'JetBrains Mono',monospace;font-size:9px;
            color:rgba(208,220,240,.28);letter-spacing:.8px;margin-bottom:20px;">
            {wc:,} words · ~{rm} min read</div>""", unsafe_allow_html=True)

        for p in content["paragraphs"]:
            p_e = p.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
            is_h = len(p)<100 and not p.endswith(('.', ',', ':')) and len(p)>8 and not p[0].islower()
            if is_h:
                st.markdown(f'<div style="font-family:Inter,sans-serif;font-size:17px;font-weight:700;color:#D0DCF0;margin:26px 28px 10px;line-height:1.4;">{p_e}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<p style="font-family:Inter,sans-serif;font-size:14px;color:rgba(208,220,240,.78);line-height:1.9;margin:0 28px 14px;">{p_e}</p>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center;padding:52px 24px;">
            <div style="font-size:40px;opacity:.2;margin-bottom:14px;">📄</div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:rgba(208,220,240,.3);margin-bottom:8px;">
                Could not extract content</div>
            <div style="font-family:Inter,sans-serif;font-size:11px;color:rgba(208,220,240,.25);
                max-width:480px;margin:0 auto 20px;line-height:1.6;">{content['error']}</div>
            <a href="{url_s}" target="_blank" style="font-family:Inter,sans-serif;font-size:12px;
                color:{color};text-decoration:none;padding:9px 22px;
                border:1px solid {color}44;border-radius:8px;background:{color}12;">
                Open original in browser →</a>
        </div>""", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)  # close card

    # Show feed below reader in compact mode
    feed_height = 520
else:
    feed_height = 920

# ═══════════════════════════════════════════════════════════
# FEED HTML (full iframe — beautiful layout, no restrictions)
# ═══════════════════════════════════════════════════════════
import streamlit.components.v1 as components

articles_json = json.dumps(articles)
errors_json   = json.dumps(errors)
feed_count    = len(FEEDS)

# Article metadata for reader navigation
reader_meta = json.dumps([
    {"url":a["url"],"title":a["title"][:200],"src":a["src"],"color":a["color"]}
    for a in articles
])

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
:root{{
  --bg:#070A12;--sf:#0D1220;--sf2:#111827;--sf3:#0A0F1E;
  --bd:rgba(255,255,255,0.07);--bdh:rgba(0,194,255,0.4);
  --tx:#D0DCF0;--dim:rgba(208,220,240,0.5);--fnt:rgba(208,220,240,0.28);
  --ac:#00C2FF;--gw:rgba(0,194,255,0.13);
}}
body.obsidian{{--bg:#0A0A0A;--sf:#141414;--sf2:#1C1C1C;--sf3:#111;--bdh:rgba(160,120,255,.4);--tx:#E0D8FF;--dim:rgba(224,216,255,.5);--fnt:rgba(224,216,255,.25);--ac:#A078FF;--gw:rgba(160,120,255,.13);}}
body.terminal{{--bg:#010B01;--sf:#051505;--sf2:#081A08;--sf3:#030D03;--bd:rgba(0,255,65,.1);--bdh:rgba(0,255,65,.4);--tx:#B0FFB8;--dim:rgba(176,255,184,.5);--fnt:rgba(176,255,184,.25);--ac:#00FF41;--gw:rgba(0,255,65,.1);}}
body.crimson{{--bg:#0C0608;--sf:#180B0E;--sf2:#200E12;--sf3:#0E0709;--bdh:rgba(255,60,80,.4);--tx:#FFD0D8;--dim:rgba(255,208,216,.5);--fnt:rgba(255,208,216,.25);--ac:#FF3C50;--gw:rgba(255,60,80,.13);}}
body.arctic{{--bg:#EEF2FA;--sf:#FFF;--sf2:#F5F8FF;--sf3:#E8EEF8;--bd:rgba(0,0,0,.08);--bdh:rgba(0,100,255,.4);--tx:#1A2540;--dim:rgba(26,37,64,.55);--fnt:rgba(26,37,64,.32);--ac:#0064FF;--gw:rgba(0,100,255,.1);}}

body{{font-family:'Inter',sans-serif;background:var(--bg);color:var(--tx);width:100vw;height:100vh;display:flex;flex-direction:column;overflow:hidden;}}

/* NAVBAR */
.nav{{flex-shrink:0;background:var(--sf);border-bottom:1px solid var(--bd);height:46px;display:flex;align-items:center;padding:0 18px;box-shadow:0 1px 20px rgba(0,0,0,.4);}}
.logo{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;letter-spacing:2px;color:var(--ac);display:flex;align-items:center;gap:8px;user-select:none;flex-shrink:0;}}
.dot{{width:7px;height:7px;border-radius:50%;background:var(--ac);box-shadow:0 0 8px var(--ac);animation:blink 2s ease-in-out infinite;}}
@keyframes blink{{0%,100%{{opacity:1;transform:scale(1)}}50%{{opacity:.2;transform:scale(.55)}}}}
.stats{{display:flex;align-items:center;margin-left:18px;flex:1;overflow:hidden;}}
.stat{{display:flex;align-items:baseline;gap:4px;padding:0 12px;border-right:1px solid var(--bd);flex-shrink:0;}}
.sn{{font-family:'JetBrains Mono',monospace;font-size:13px;font-weight:700;color:var(--ac);}}
.sl{{font-family:'Inter',sans-serif;font-size:9px;font-weight:500;color:var(--fnt);text-transform:uppercase;letter-spacing:1px;white-space:nowrap;}}
.c-r{{color:#FF4B6E!important}}.c-a{{color:#FF8C00!important}}.c-g{{color:#00D68F!important}}.c-p{{color:#A78BFA!important}}
.nav-time{{margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:10px;color:var(--fnt);flex-shrink:0;}}

/* TICKER */
.ticker{{flex-shrink:0;background:var(--sf3);border-bottom:1px solid var(--bd);height:26px;display:flex;align-items:center;overflow:hidden;}}
.t-lbl{{font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;color:var(--ac);letter-spacing:2px;padding:0 11px;flex-shrink:0;border-right:1px solid var(--bd);white-space:nowrap;}}
.t-track{{flex:1;overflow:hidden;}}
.t-inner{{display:inline-block;white-space:nowrap;animation:ticker 100s linear infinite;}}
.t-inner:hover{{animation-play-state:paused;}}
@keyframes ticker{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
.t-item{{font-family:'Inter',sans-serif;font-size:11px;color:var(--dim);margin-right:32px;display:inline;}}
.t-sep{{color:var(--ac);opacity:.2;margin-right:32px;display:inline;}}

/* TOOLBAR */
.toolbar{{flex-shrink:0;background:var(--sf2);border-bottom:1px solid var(--bd);padding:7px 18px;display:flex;align-items:center;gap:8px;}}
.search-wrap{{flex:1;min-width:0;position:relative;}}
.search-wrap svg{{position:absolute;left:10px;top:50%;transform:translateY(-50%);opacity:.3;pointer-events:none;}}
#searchInput{{width:100%;background:var(--sf);border:1px solid var(--bd);border-radius:7px;color:var(--tx);font-family:'Inter',sans-serif;font-size:12px;padding:7px 10px 7px 32px;height:34px;outline:none;transition:border-color .18s,box-shadow .18s;}}
#searchInput:focus{{border-color:var(--bdh);box-shadow:0 0 0 2px var(--gw);}}
#searchInput::placeholder{{color:var(--fnt);}}
select{{background:var(--sf);border:1px solid var(--bd);border-radius:7px;color:var(--tx);font-family:'Inter',sans-serif;font-size:11px;padding:0 26px 0 10px;height:34px;outline:none;cursor:pointer;-webkit-appearance:none;appearance:none;flex-shrink:0;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23666'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 8px center;transition:border-color .18s;}}
select:focus{{border-color:var(--bdh);}}
#catSel{{width:130px;}}#themeSel{{width:128px;}}
.btn{{background:var(--gw);border:1px solid var(--bdh);border-radius:7px;color:var(--ac);font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:700;height:34px;padding:0 13px;cursor:pointer;transition:all .18s;flex-shrink:0;white-space:nowrap;}}
.btn:hover{{background:var(--ac);color:var(--bg);box-shadow:0 0 14px var(--gw);}}

/* TABS */
.tabs{{flex-shrink:0;background:var(--sf);border-bottom:1px solid var(--bd);padding:0 18px;display:flex;overflow-x:auto;}}
.tabs::-webkit-scrollbar{{height:2px;}}
.tab{{font-family:'Inter',sans-serif;font-size:11px;font-weight:500;padding:9px 14px 7px;color:var(--fnt);border-bottom:2px solid transparent;cursor:pointer;white-space:nowrap;transition:all .18s;}}
.tab:hover{{color:var(--dim);background:var(--gw);}}.tab.on{{color:var(--ac);border-bottom-color:var(--ac);background:var(--gw);}}
.tab-n{{font-family:'JetBrains Mono',monospace;font-size:8px;opacity:.35;margin-left:3px;}}

/* SOURCE BAR */
.src-bar{{flex-shrink:0;background:var(--bg);border-bottom:1px solid var(--bd);padding:5px 18px;display:flex;align-items:center;gap:5px;overflow-x:auto;white-space:nowrap;}}
.src-bar::-webkit-scrollbar{{height:2px;}}.src-bar::-webkit-scrollbar-thumb{{background:var(--bdh);}}
.src-lbl{{font-family:'JetBrains Mono',monospace;font-size:8px;color:var(--fnt);letter-spacing:1.5px;text-transform:uppercase;flex-shrink:0;}}
.pill{{font-family:'Inter',sans-serif;font-size:10px;padding:2px 8px;border-radius:20px;border:1px solid var(--bd);color:var(--dim);cursor:pointer;transition:all .18s;flex-shrink:0;}}
.pill:hover{{border-color:var(--bdh);color:var(--tx);}}.pill.on{{border-color:var(--bdh);background:var(--gw);color:var(--ac);}}

/* MAIN */
.main{{flex:1;overflow-y:auto;overflow-x:hidden;padding:12px 18px 20px;}}
.main::-webkit-scrollbar{{width:4px;}}.main::-webkit-scrollbar-thumb{{background:var(--bdh);border-radius:2px;}}
.feed-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;}}
.feed-lbl{{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--fnt);text-transform:uppercase;letter-spacing:2px;display:flex;align-items:center;gap:10px;}}
.feed-lbl::after{{content:'';flex:1;height:1px;background:var(--bd);min-width:20px;}}

/* PAGINATION */
.pag{{display:flex;align-items:center;gap:4px;flex-shrink:0;}}
.pg-b{{font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:600;width:26px;height:26px;border-radius:6px;border:1px solid var(--bd);background:var(--sf);color:var(--dim);cursor:pointer;transition:all .18s;display:flex;align-items:center;justify-content:center;}}
.pg-b:hover:not([disabled]){{border-color:var(--bdh);color:var(--ac);background:var(--gw);}}.pg-b.on{{border-color:var(--bdh);background:var(--gw);color:var(--ac);}}.pg-b[disabled]{{opacity:.2;cursor:default;}}
.pg-i{{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--fnt);padding:0 2px;}}

/* GRID */
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}}
@media(max-width:1100px){{.grid{{grid-template-columns:repeat(2,1fr);}}}}
@media(max-width:680px){{.grid{{grid-template-columns:1fr;}}}}

/* CARD */
.card{{background:var(--sf);border:1px solid var(--bd);border-left:3px solid var(--card-color,var(--ac));border-radius:9px;padding:14px 15px 12px;transition:transform .2s,border-color .2s,box-shadow .2s;}}
.card:hover{{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,0,0,.45);border-color:var(--bdh);}}
.c-top{{display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:8px;}}
.badge{{font-family:'JetBrains Mono',monospace;font-size:9px;font-weight:600;padding:2px 8px;border-radius:20px;border:1px solid;white-space:nowrap;flex-shrink:0;}}
.c-ago{{font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--fnt);white-space:nowrap;padding-top:2px;}}
.c-title{{font-family:'Inter',sans-serif;font-size:13px;font-weight:600;color:var(--tx);line-height:1.5;margin-bottom:7px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}}
.new-b{{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:7px;font-weight:700;letter-spacing:1px;color:#fff;background:#FF3C50;padding:2px 5px;border-radius:3px;margin-left:5px;vertical-align:middle;animation:nb 1.6s ease-in-out infinite;}}
@keyframes nb{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.c-sum{{font-family:'Inter',sans-serif;font-size:11px;color:var(--dim);line-height:1.6;margin-bottom:10px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}}
.c-foot{{display:flex;justify-content:space-between;align-items:center;gap:6px;}}
.cat-p{{font-family:'JetBrains Mono',monospace;font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;padding:2px 7px;border-radius:4px;}}
.c-btns{{display:flex;gap:5px;align-items:center;}}
.read-btn{{font-family:'Inter',sans-serif;font-size:10px;font-weight:500;color:var(--tx);padding:3px 9px;border:1px solid var(--bd);border-radius:5px;background:var(--sf2);cursor:pointer;transition:all .15s;white-space:nowrap;}}
.read-btn:hover{{border-color:var(--bdh);color:var(--ac);background:var(--gw);}}
.open-btn{{font-family:'Inter',sans-serif;font-size:10px;font-weight:500;color:var(--ac);text-decoration:none;padding:3px 9px;border:1px solid var(--bdh);border-radius:5px;background:var(--gw);transition:all .15s;white-space:nowrap;}}
.open-btn:hover{{background:var(--ac);color:var(--bg);}}

/* ERROR */
.err-panel{{background:rgba(255,75,110,.05);border:1px solid rgba(255,75,110,.18);border-radius:7px;overflow:hidden;margin-bottom:10px;}}
.err-hdr{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#FF4B6E;padding:7px 11px;cursor:pointer;user-select:none;display:flex;align-items:center;gap:8px;}}
.err-body{{padding:0 11px 7px;display:none;}}.err-body.open{{display:block;}}
.err-line{{font-family:'JetBrains Mono',monospace;font-size:9px;color:#FF4B6E;opacity:.7;padding:2px 0;}}
.empty{{grid-column:1/-1;text-align:center;padding:60px 20px;font-family:'JetBrains Mono',monospace;color:var(--fnt);font-size:11px;}}
::-webkit-scrollbar{{width:4px;height:4px;}}::-webkit-scrollbar-track{{background:transparent;}}::-webkit-scrollbar-thumb{{background:var(--bdh);border-radius:2px;}}
</style>
</head>
<body>

<!-- NAVBAR -->
<nav class="nav">
  <div class="logo"><div class="dot"></div>CYBERFEED</div>
  <div class="stats" id="stats"></div>
  <div class="nav-time" id="navTime">{now_str}</div>
</nav>

<!-- TICKER -->
<div class="ticker">
  <div class="t-lbl">LIVE</div>
  <div class="t-track"><div class="t-inner" id="tInner"></div></div>
</div>

<!-- TOOLBAR -->
<div class="toolbar">
  <div class="search-wrap">
    <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
    </svg>
    <input id="searchInput" type="text" placeholder="Search headlines, CVEs, threat actors, APTs…" autocomplete="off">
  </div>
  <select id="catSel">
    <option value="All">All Categories</option>
    <option value="Threats">Threats</option>
    <option value="Vulnerabilities">Vulnerabilities</option>
    <option value="Breaches">Breaches</option>
    <option value="CVE">CVE</option>
    <option value="Analysis">Analysis</option>
  </select>
  <select id="themeSel">
    <option value="">⬤ Midnight</option>
    <option value="obsidian">⬤ Obsidian</option>
    <option value="terminal">⬤ Terminal</option>
    <option value="crimson">⬤ Crimson</option>
    <option value="arctic">⬤ Arctic</option>
  </select>
  <button class="btn" onclick="doRefresh()">↻ REFRESH</button>
</div>

<!-- TABS -->
<div class="tabs" id="tabs"></div>

<!-- SOURCE BAR -->
<div class="src-bar" id="srcBar"><span class="src-lbl">Sources</span></div>

<!-- MAIN -->
<div class="main" id="mainArea">
  <div id="errPanel"></div>
  <div class="feed-hdr">
    <div class="feed-lbl" id="feedLbl">Loading…</div>
    <div class="pag" id="pag"></div>
  </div>
  <div class="grid" id="grid"></div>
</div>

<script>
const ALL   = {articles_json};
const ERRS  = {errors_json};
const FCNT  = {feed_count};
const RMETA = {reader_meta};
const PER   = 15;

const CAT_COLORS={{Threats:'#FF4B6E',Vulnerabilities:'#00C2FF',Breaches:'#FF8C00',CVE:'#E74C3C',Analysis:'#A78BFA'}};
const CAT_ICO={{Threats:'🔴',CVE:'🟠',Breaches:'🟡',Vulnerabilities:'🔵',Analysis:'🟣'}};
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

const S={{search:'',cat:'All',srcs:new Set(),page:0}};

function filtered(){{
  let a=ALL;
  if(S.cat!=='All')a=a.filter(x=>x.cat===S.cat);
  if(S.srcs.size)a=a.filter(x=>S.srcs.has(x.src));
  if(S.search.length>=2){{const q=S.search.toLowerCase();a=a.filter(x=>x.title.toLowerCase().includes(q)||x.summary.toLowerCase().includes(q));}}
  return a;
}}

function renderStats(){{
  const cc={{}};ALL.forEach(a=>cc[a.cat]=(cc[a.cat]||0)+1);
  const fn=ALL.filter(a=>a.fresh).length;
  document.getElementById('stats').innerHTML=`
    <div class="stat"><span class="sn">${{ALL.length}}</span><span class="sl">Articles</span></div>
    <div class="stat"><span class="sn c-g">${{FCNT-ERRS.length}}/${{FCNT}}</span><span class="sl">Feeds</span></div>
    <div class="stat"><span class="sn c-r">${{fn}}</span><span class="sl">New 4h</span></div>
    <div class="stat"><span class="sn c-r">${{cc.Threats||0}}</span><span class="sl">Threats</span></div>
    <div class="stat"><span class="sn">${{cc.Vulnerabilities||0}}</span><span class="sl">Vulns</span></div>
    <div class="stat"><span class="sn c-r">${{cc.CVE||0}}</span><span class="sl">CVE</span></div>
    <div class="stat"><span class="sn c-a">${{cc.Breaches||0}}</span><span class="sl">Breaches</span></div>
    <div class="stat"><span class="sn c-p">${{cc.Analysis||0}}</span><span class="sl">Analysis</span></div>`;
}}

function renderTicker(){{
  const items=ALL.slice(0,24).map(a=>{{
    const t=a.title.length>70?a.title.slice(0,70)+'…':a.title;
    return `<span class="t-item">${{CAT_ICO[a.cat]||'⚪'}} ${{esc(t)}}</span><span class="t-sep">·</span>`;
  }}).join('');
  document.getElementById('tInner').innerHTML=items+items;
}}

function renderErrors(){{
  const el=document.getElementById('errPanel');
  if(!ERRS.length){{el.innerHTML='';return;}}
  el.innerHTML=`<div class="err-panel">
    <div class="err-hdr" onclick="this.nextElementSibling.classList.toggle('open')">⚠ ${{ERRS.length}} feed(s) had errors <span style="margin-left:auto;opacity:.5">▾</span></div>
    <div class="err-body">${{ERRS.map(e=>`<div class="err-line">✗ ${{esc(e)}}</div>`).join('')}}</div>
  </div>`;
}}

function renderTabs(){{
  const CATS=['All','Threats','Vulnerabilities','Breaches','CVE','Analysis'];
  const cc={{}};ALL.forEach(a=>cc[a.cat]=(cc[a.cat]||0)+1);
  document.getElementById('tabs').innerHTML=CATS.map(c=>
    `<div class="tab ${{S.cat===c?'on':''}}" onclick="setCat('${{c}}')">
      ${{c}}<span class="tab-n">(${{c==='All'?ALL.length:cc[c]||0}})</span></div>`).join('');
}}

function renderSrcBar(){{
  const srcs=[...new Set(ALL.map(a=>a.src))].sort();
  document.getElementById('srcBar').innerHTML='<span class="src-lbl">Sources</span>'+
    srcs.map(s=>`<span class="pill ${{S.srcs.has(s)?'on':''}}" onclick="toggleSrc('${{esc(s)}}')">${{esc(s)}}</span>`).join('');
}}

function cardHTML(a,globalIdx){{
  const c=a.color,cc=CAT_COLORS[a.cat]||'#888';
  const nb=a.fresh?'<span class="new-b">NEW</span>':'';
  return `<div class="card" style="--card-color:${{c}}">
  <div class="c-top">
    <div class="badge" style="color:${{c}};border-color:${{c}}44;background:${{c}}14">${{a.icon}} ${{esc(a.src)}}</div>
    <div class="c-ago">${{esc(a.ago)}}</div>
  </div>
  <div class="c-title">${{esc(a.title)}}${{nb}}</div>
  <div class="c-sum">${{esc(a.summary)||'No summary.'}}</div>
  <div class="c-foot">
    <span class="cat-p" style="color:${{cc}};background:${{cc}}18">${{a.cat}}</span>
    <div class="c-btns">
      <button class="read-btn" onclick="openReader(${{globalIdx}})">📖 Read here</button>
      <a class="open-btn" href="${{esc(a.url)}}" target="_blank" rel="noopener">↗ Open</a>
    </div>
  </div>
</div>`;
}}

function renderPag(total){{
  const pages=Math.ceil(total/PER);
  const el=document.getElementById('pag');
  if(pages<=1){{el.innerHTML='';return;}}
  let h=`<button class="pg-b" onclick="goPage(${{S.page-1}})" ${{S.page===0?'disabled':''}}>‹</button>`;
  const range=[];
  for(let i=0;i<pages;i++){{
    if(i===0||i===pages-1||Math.abs(i-S.page)<=1)range.push(i);
    else if(range[range.length-1]!=='…')range.push('…');
  }}
  range.forEach(i=>{{
    if(i==='…')h+=`<span class="pg-i">…</span>`;
    else h+=`<button class="pg-b ${{i===S.page?'on':''}}" onclick="goPage(${{i}})">${{i+1}}</button>`;
  }});
  h+=`<button class="pg-b" onclick="goPage(${{S.page+1}})" ${{S.page===pages-1?'disabled':''}}>›</button>`;
  h+=`<span class="pg-i">${{S.page+1}}/${{pages}}</span>`;
  el.innerHTML=h;
}}

function renderGrid(){{
  const arts=filtered();
  let lbl=`${{arts.length}} articles`;
  if(S.search)lbl+=` · "${{esc(S.search)}}"`;
  if(S.cat!=='All')lbl+=` · ${{S.cat}}`;
  if(S.srcs.size)lbl+=` · ${{S.srcs.size}} source(s)`;
  document.getElementById('feedLbl').textContent=lbl;
  renderPag(arts.length);
  const page=arts.slice(S.page*PER,(S.page+1)*PER);
  window._page=page;
  window._gidx=page.map(a=>ALL.indexOf(a));
  if(!page.length){{document.getElementById('grid').innerHTML='<div class="empty">📡<br><br>No articles match.</div>';return;}}
  document.getElementById('grid').innerHTML=page.map((a,i)=>cardHTML(a,window._gidx[i])).join('');
}}

// ── READER: navigate top window with query params ─────────────────────────────
// window.top works because Streamlit serves everything from same origin.
// If blocked, falls back to window.location (navigates the iframe URL, less ideal).
function openReader(globalIdx){{
  const m=RMETA[globalIdx];
  if(!m)return;
  const p=new URLSearchParams({{
    read:   encodeURIComponent(m.url),
    rtitle: encodeURIComponent(m.title),
    rsrc:   encodeURIComponent(m.src),
    rcolor: encodeURIComponent(m.color),
  }});
  const qs='?'+p.toString();
  try{{
    // Try top window first (works when same-origin)
    if(window.top && window.top.location && window.top !== window){{
      window.top.location.search=qs;
    }} else {{
      window.location.search=qs;
    }}
  }} catch(e){{
    // If top is blocked (cross-origin), fall back to location
    window.location.search=qs;
  }}
}}

function setCat(c){{S.cat=c;S.page=0;renderTabs();renderGrid();}}
function goPage(p){{
  const arts=filtered();const max=Math.ceil(arts.length/PER)-1;
  S.page=Math.max(0,Math.min(p,max));
  renderGrid();document.getElementById('mainArea').scrollTop=0;
}}
function toggleSrc(s){{S.srcs.has(s)?S.srcs.delete(s):S.srcs.add(s);S.page=0;renderSrcBar();renderGrid();}}
function doRefresh(){{
  try{{if(window.top&&window.top!==window)window.top.location.search='';else window.location.search='';}}catch(e){{window.location.search='';}}
}}

document.getElementById('themeSel').addEventListener('change',function(){{document.body.className=this.value;}});
let st_t;
document.getElementById('searchInput').addEventListener('input',function(){{
  clearTimeout(st_t);st_t=setTimeout(()=>{{S.search=this.value;S.page=0;renderGrid();}},200);
}});
setInterval(()=>{{
  const n=new Date();
  document.getElementById('navTime').textContent=
    n.toLocaleDateString('en-GB',{{day:'2-digit',month:'short',year:'numeric'}})+' '+
    n.toLocaleTimeString('en-GB',{{hour:'2-digit',minute:'2-digit'}});
}},15000);

renderStats();renderTicker();renderErrors();renderTabs();renderSrcBar();renderGrid();
</script>
</body>
</html>"""

components.html(HTML, height=feed_height, scrolling=False)
