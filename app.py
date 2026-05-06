"""
CyberFeed v14 — Clean feed, no reader feature.
Full HTML iframe UI for best appearance.
"""

import streamlit as st
import feedparser
import requests
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
    dict(name="NIST NVD",             url="https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-recent.json.gz", cat="CVE",             color="#C0392B", icon="📋"),
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
    txt=re.sub(r'<[^>]+',' ',txt or ''); txt=re.sub(r'\s+',' ',txt).strip()
    return txt[:260]+"…" if len(txt)>260 else txt

def fetch_one(feed):
    try:
        r=requests.get(feed["url"],timeout=8,headers={"User-Agent":"CyberFeed/14.0"})
        r.raise_for_status()
        parsed=feedparser.parse(r.text)
        out=[]
        for e in parsed.entries[:20]:
            dt=parse_date(e)
            out.append(dict(
                title=(e.get("title") or "Untitled").strip(),
                url=e.get("link","#"),
                summary=clean(e.get("summary") or e.get("description") or ""),
                src=feed["name"],cat=feed["cat"],color=feed["color"],icon=feed["icon"],
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
            items,err=f.result(); arts.extend(items)
            if err: errs.append(err)
        for f in pending:
            errs.append(f"{futs[f]}: timeout"); f.cancel()
    arts.sort(key=lambda x:x["ts"],reverse=True)
    return arts,errs

with st.spinner("Fetching security feeds…"):
    articles, errors = fetch_all()

import streamlit.components.v1 as components

now_str       = datetime.now().strftime("%d %b %Y %H:%M")
articles_json = json.dumps(articles)
errors_json   = json.dumps(errors)
feed_count    = len(FEEDS)

HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
:root{{
  --bg:#F7F5F0;--sf:#FFFFFF;--sf2:#EFEDE8;--sf3:#E8E5DE;
  --bd:rgba(0,0,0,0.1);--bds:rgba(0,0,0,0.06);
  --tx:#111111;--dim:#444444;--muted:#888888;
  --ac:#C41230;--ac2:#8B0D1F;
  --serif:'Playfair Display',Georgia,serif;
  --sans:'Inter',sans-serif;
  --mono:'JetBrains Mono',monospace;
}}
body.night{{
  --bg:#0E0E0E;--sf:#181818;--sf2:#1F1F1F;--sf3:#151515;
  --bd:rgba(255,255,255,0.08);--bds:rgba(255,255,255,0.04);
  --tx:#F0EEE8;--dim:#AAAAAA;--muted:#666666;
  --ac:#E8294A;--ac2:#FF4D6A;
}}
body.slate{{
  --bg:#1A1F2E;--sf:#232B3E;--sf2:#1E2538;--sf3:#161B29;
  --bd:rgba(255,255,255,0.08);--bds:rgba(255,255,255,0.04);
  --tx:#D8E0F0;--dim:#8896B8;--muted:#4A5580;
  --ac:#4F8EF7;--ac2:#7AAEFF;
}}
body.forest{{
  --bg:#F2F5EE;--sf:#FFFFFF;--sf2:#E8EDE2;--sf3:#DDE4D5;
  --bd:rgba(0,0,0,0.1);--bds:rgba(0,0,0,0.05);
  --tx:#1C2B1A;--dim:#3D5C38;--muted:#7A9A72;
  --ac:#2D6A2A;--ac2:#1F4D1D;
}}
body{{font-family:var(--sans);background:var(--bg);color:var(--tx);width:100vw;height:100vh;display:flex;flex-direction:column;overflow:hidden;}}

/* ── MASTHEAD ── */
.masthead{{
  flex-shrink:0;background:var(--sf);
  border-bottom:3px solid var(--tx);
  padding:0 24px;
}}
.mast-top{{
  display:flex;align-items:center;justify-content:space-between;
  padding:8px 0 6px;border-bottom:1px solid var(--bd);
  gap:12px;
}}
.mast-meta{{font-family:var(--mono);font-size:9px;color:var(--muted);letter-spacing:.08em;}}
.mast-cats{{display:flex;gap:2px;}}
.mcat{{font-family:var(--sans);font-size:10px;font-weight:500;padding:3px 10px;border-radius:2px;cursor:pointer;color:var(--dim);transition:all .15s;border:none;background:none;}}
.mcat:hover{{color:var(--tx);}}.mcat.on{{color:var(--sf);background:var(--tx);}}
.mast-bottom{{
  display:flex;align-items:center;justify-content:center;
  padding:10px 0 8px;gap:16px;
}}
.logo{{font-family:var(--serif);font-size:32px;font-weight:900;color:var(--tx);letter-spacing:-.5px;line-height:1;user-select:none;text-align:center;flex:1;}}
.logo span{{color:var(--ac);}}
.mast-side{{display:flex;align-items:center;gap:8px;width:220px;}}
.mast-side-r{{justify-content:flex-end;}}
.live-dot{{width:7px;height:7px;border-radius:50%;background:var(--ac);animation:blink 2s ease-in-out infinite;flex-shrink:0;}}
@keyframes blink{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
.live-txt{{font-family:var(--mono);font-size:9px;color:var(--ac);letter-spacing:.15em;}}
.stat-pill{{font-family:var(--mono);font-size:9px;color:var(--muted);display:flex;align-items:baseline;gap:3px;}}
.stat-n{{font-size:11px;font-weight:500;color:var(--tx);}}

/* ── TICKER ── */
.ticker{{
  flex-shrink:0;background:var(--tx);
  height:24px;display:flex;align-items:center;overflow:hidden;
}}
.t-lbl{{font-family:var(--mono);font-size:8px;font-weight:500;color:var(--sf);letter-spacing:.2em;padding:0 12px;flex-shrink:0;border-right:1px solid rgba(255,255,255,0.2);white-space:nowrap;}}
.t-track{{flex:1;overflow:hidden;}}
.t-inner{{display:inline-block;white-space:nowrap;animation:ticker 120s linear infinite;}}
.t-inner:hover{{animation-play-state:paused;}}
@keyframes ticker{{0%{{transform:translateX(0)}}100%{{transform:translateX(-50%)}}}}
.t-item{{font-family:var(--sans);font-size:10px;color:rgba(255,255,255,.75);margin-right:28px;display:inline;}}
.t-sep{{color:var(--ac);margin-right:28px;display:inline;opacity:.6;}}
.night .t-lbl{{color:var(--sf);}}.night .t-item{{color:rgba(240,238,232,.75);}}

/* ── TOOLBAR ── */
.toolbar{{
  flex-shrink:0;background:var(--sf2);
  border-bottom:1px solid var(--bd);
  padding:6px 24px;display:flex;align-items:center;gap:8px;
}}
.sw{{flex:1;min-width:0;position:relative;}}
.sw svg{{position:absolute;left:9px;top:50%;transform:translateY(-50%);opacity:.35;pointer-events:none;}}
#si{{
  width:100%;background:var(--sf);border:1px solid var(--bd);border-radius:4px;
  color:var(--tx);font-family:var(--sans);font-size:12px;
  padding:6px 10px 6px 30px;height:32px;outline:none;
  transition:border-color .15s;
}}
#si:focus{{border-color:var(--ac);}}
#si::placeholder{{color:var(--muted);}}
select{{
  background:var(--sf);border:1px solid var(--bd);border-radius:4px;
  color:var(--tx);font-family:var(--sans);font-size:11px;
  padding:0 24px 0 9px;height:32px;outline:none;cursor:pointer;
  -webkit-appearance:none;appearance:none;flex-shrink:0;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='8' height='5'%3E%3Cpath d='M0 0l4 5 4-5z' fill='%23999'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 7px center;
  transition:border-color .15s;
}}
select:focus{{border-color:var(--ac);}}
#cs{{width:130px;}}#th{{width:130px;}}
.rbtn{{
  background:var(--ac);border:none;border-radius:4px;
  color:#fff;font-family:var(--mono);
  font-size:10px;font-weight:500;height:32px;padding:0 12px;
  cursor:pointer;transition:all .15s;flex-shrink:0;
}}
.rbtn:hover{{background:var(--ac2);}}

/* ── SRC BAR ── */
.src-bar{{
  flex-shrink:0;background:var(--sf);border-bottom:1px solid var(--bd);
  padding:5px 24px;display:flex;align-items:center;gap:5px;overflow-x:auto;white-space:nowrap;
}}
.src-bar::-webkit-scrollbar{{height:2px;}}.src-bar::-webkit-scrollbar-thumb{{background:var(--bd);}}
.src-lbl{{font-family:var(--mono);font-size:8px;color:var(--muted);letter-spacing:.15em;text-transform:uppercase;flex-shrink:0;margin-right:4px;}}
.pill{{font-family:var(--sans);font-size:10px;padding:2px 9px;border-radius:2px;border:1px solid var(--bd);color:var(--dim);cursor:pointer;transition:all .15s;flex-shrink:0;}}
.pill:hover{{border-color:var(--ac);color:var(--ac);}}.pill.on{{border-color:var(--ac);background:var(--ac);color:#fff;}}

/* ── MAIN ── */
.main{{flex:1;overflow-y:auto;overflow-x:hidden;padding:20px 24px 28px;}}
.main::-webkit-scrollbar{{width:4px;}}.main::-webkit-scrollbar-thumb{{background:var(--bd);border-radius:2px;}}

/* ── SECTION HEADER ── */
.sec-hdr{{
  display:flex;align-items:baseline;gap:12px;
  margin-bottom:14px;padding-bottom:8px;
  border-bottom:2px solid var(--tx);
}}
.sec-title{{font-family:var(--serif);font-size:13px;font-weight:700;color:var(--tx);text-transform:uppercase;letter-spacing:.12em;}}
.sec-count{{font-family:var(--mono);font-size:10px;color:var(--muted);}}
.sec-line{{flex:1;height:1px;background:var(--bd);}}

/* ── MAGAZINE GRID ── */
.mag-grid{{display:grid;gap:0;}}

/* Hero layout: big left + 3 right */
.hero-layout{{
  display:grid;
  grid-template-columns:1fr 320px;
  grid-template-rows:auto;
  border:1px solid var(--bd);
  margin-bottom:16px;
  background:var(--sf);
}}
.hero-main{{
  border-right:1px solid var(--bd);
  padding:20px 22px;
  display:flex;flex-direction:column;gap:10px;
}}
.hero-cat{{font-family:var(--mono);font-size:9px;font-weight:500;color:var(--ac);letter-spacing:.15em;text-transform:uppercase;}}
.hero-title{{font-family:var(--serif);font-size:26px;font-weight:700;line-height:1.25;color:var(--tx);}}
.hero-title a{{color:inherit;text-decoration:none;}}
.hero-title a:hover{{color:var(--ac);}}
.hero-sum{{font-family:var(--sans);font-size:13px;color:var(--dim);line-height:1.65;}}
.hero-foot{{display:flex;align-items:center;gap:10px;padding-top:6px;border-top:1px solid var(--bds);margin-top:auto;}}
.hero-src{{font-family:var(--mono);font-size:10px;color:var(--muted);}}
.hero-ago{{font-family:var(--mono);font-size:10px;color:var(--muted);}}
.new-badge{{font-family:var(--mono);font-size:8px;font-weight:500;letter-spacing:.1em;color:#fff;background:var(--ac);padding:2px 6px;border-radius:2px;animation:blink 2s ease-in-out infinite;}}
.hero-sidebar{{display:flex;flex-direction:column;}}
.side-item{{
  padding:14px 16px;border-bottom:1px solid var(--bd);
  display:flex;flex-direction:column;gap:6px;flex:1;
}}
.side-item:last-child{{border-bottom:none;}}
.side-cat{{font-family:var(--mono);font-size:8px;color:var(--ac);letter-spacing:.12em;text-transform:uppercase;}}
.side-title{{font-family:var(--serif);font-size:14px;font-weight:700;line-height:1.35;color:var(--tx);}}
.side-title a{{color:inherit;text-decoration:none;}}
.side-title a:hover{{color:var(--ac);}}
.side-src{{font-family:var(--mono);font-size:9px;color:var(--muted);}}

/* 3-col grid for rest */
.card-grid{{
  display:grid;
  grid-template-columns:repeat(3,1fr);
  border:1px solid var(--bd);
  margin-bottom:16px;
  background:var(--sf);
}}
@media(max-width:900px){{.card-grid{{grid-template-columns:repeat(2,1fr);}}.hero-layout{{grid-template-columns:1fr;}}}}
@media(max-width:600px){{.card-grid{{grid-template-columns:1fr;}}.hero-sidebar{{display:none;}}}}

.art-card{{
  padding:16px 18px;border-right:1px solid var(--bd);border-bottom:1px solid var(--bd);
  display:flex;flex-direction:column;gap:8px;
  transition:background .12s;cursor:pointer;
}}
.art-card:hover{{background:var(--sf2);}}
.art-card:nth-child(3n){{border-right:none;}}
.card-cat{{font-family:var(--mono);font-size:8px;color:var(--ac);letter-spacing:.12em;text-transform:uppercase;}}
.card-title{{font-family:var(--serif);font-size:14px;font-weight:700;line-height:1.4;color:var(--tx);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;}}
.card-title a{{color:inherit;text-decoration:none;}}
.card-title a:hover{{color:var(--ac);}}
.card-sum{{font-family:var(--sans);font-size:11px;color:var(--dim);line-height:1.55;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}}
.card-foot{{display:flex;justify-content:space-between;align-items:center;padding-top:4px;border-top:1px solid var(--bds);margin-top:auto;}}
.card-src{{font-family:var(--mono);font-size:9px;color:var(--muted);}}
.card-ago{{font-family:var(--mono);font-size:9px;color:var(--muted);}}

/* ── DIVIDER ── */
.cat-divider{{
  display:flex;align-items:center;gap:10px;
  margin:20px 0 14px;
}}
.cat-div-label{{font-family:var(--serif);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.14em;color:var(--tx);white-space:nowrap;}}
.cat-div-line{{flex:1;height:1px;background:var(--bd);}}
.cat-div-n{{font-family:var(--mono);font-size:9px;color:var(--muted);white-space:nowrap;}}

/* ── PAGINATION ── */
.pag-footer{{display:flex;align-items:center;justify-content:center;gap:4px;padding:20px 0 4px;}}
.pg-b{{
  font-family:var(--mono);font-size:10px;font-weight:500;
  width:28px;height:28px;border-radius:3px;
  border:1px solid var(--bd);background:var(--sf);
  color:var(--dim);cursor:pointer;transition:all .15s;
  display:flex;align-items:center;justify-content:center;
}}
.pg-b:hover:not([disabled]){{border-color:var(--ac);color:var(--ac);}}
.pg-b.on{{border-color:var(--ac);background:var(--ac);color:#fff;}}
.pg-b[disabled]{{opacity:.2;cursor:default;}}
.pg-i{{font-family:var(--mono);font-size:9px;color:var(--muted);padding:0 3px;}}

/* ── ERROR PANEL ── */
.err-panel{{background:rgba(196,18,48,.05);border:1px solid rgba(196,18,48,.2);border-radius:3px;overflow:hidden;margin-bottom:12px;}}
.err-hdr{{font-family:var(--mono);font-size:10px;color:var(--ac);padding:7px 11px;cursor:pointer;user-select:none;display:flex;align-items:center;gap:8px;}}
.err-body{{padding:0 11px 7px;display:none;}}.err-body.open{{display:block;}}
.err-line{{font-family:var(--mono);font-size:9px;color:var(--ac);opacity:.7;padding:2px 0;}}
.empty{{text-align:center;padding:60px 20px;font-family:var(--serif);color:var(--muted);font-size:16px;font-style:italic;}}

::-webkit-scrollbar{{width:4px;height:4px;}}
::-webkit-scrollbar-track{{background:transparent;}}
::-webkit-scrollbar-thumb{{background:var(--bd);border-radius:2px;}}
</style>
</head>
<body>

<!-- MASTHEAD -->
<header class="masthead">
  <div class="mast-top">
    <div class="mast-meta" id="mastDate">{now_str}</div>
    <div class="mast-cats">
      <button class="mcat on" onclick="setCat('All',this)">All</button>
      <button class="mcat" onclick="setCat('Threats',this)">Threats</button>
      <button class="mcat" onclick="setCat('Vulnerabilities',this)">Vulnerabilities</button>
      <button class="mcat" onclick="setCat('Breaches',this)">Breaches</button>
      <button class="mcat" onclick="setCat('CVE',this)">CVE</button>
      <button class="mcat" onclick="setCat('Analysis',this)">Analysis</button>
    </div>
    <div class="mast-meta" id="feedMeta"></div>
  </div>
  <div class="mast-bottom">
    <div class="mast-side">
      <div class="live-dot"></div>
      <div class="live-txt">LIVE FEED</div>
    </div>
    <div class="logo">CYBER<span>FEED</span></div>
    <div class="mast-side mast-side-r" id="mastStats"></div>
  </div>
</header>

<!-- TICKER -->
<div class="ticker">
  <div class="t-lbl">BREAKING</div>
  <div class="t-track"><div class="t-inner" id="tInner"></div></div>
</div>

<!-- TOOLBAR -->
<div class="toolbar">
  <div class="sw">
    <svg width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
      <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
    </svg>
    <input id="si" type="text" placeholder="Search headlines, CVEs, threat actors…" autocomplete="off">
  </div>
  <select id="th">
    <option value="">⬤ Classic</option>
    <option value="night">⬤ Night</option>
    <option value="slate">⬤ Slate</option>
    <option value="forest">⬤ Forest</option>
  </select>
  <button class="rbtn" onclick="location.reload()">↻ Refresh</button>
</div>

<!-- SOURCE BAR -->
<div class="src-bar" id="srcBar"><span class="src-lbl">Sources</span></div>

<!-- MAIN -->
<div class="main" id="mainArea">
  <div id="errPanel"></div>
  <div id="grid"></div>
  <div class="pag-footer" id="pag"></div>
</div>

<script>
const ALL  = {articles_json};
const ERRS = {errors_json};
const FCNT = {feed_count};
const PER  = 18;

const CAT_ICO={{Threats:'▲',CVE:'●',Breaches:'■',Vulnerabilities:'◆',Analysis:'◀'}};
const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

const S={{search:'',cat:'All',srcs:new Set(),page:0}};
let _catBtn=document.querySelector('.mcat.on');

function filtered(){{
  let a=ALL;
  if(S.cat!=='All')a=a.filter(x=>x.cat===S.cat);
  if(S.srcs.size)a=a.filter(x=>S.srcs.has(x.src));
  if(S.search.length>=2){{
    const q=S.search.toLowerCase();
    a=a.filter(x=>x.title.toLowerCase().includes(q)||x.summary.toLowerCase().includes(q));
  }}
  return a;
}}

function renderMasthead(){{
  const cc={{}};ALL.forEach(a=>cc[a.cat]=(cc[a.cat]||0)+1);
  const fn=ALL.filter(a=>a.fresh).length;
  document.getElementById('mastStats').innerHTML=
    `<span class="stat-pill"><span class="stat-n">${{ALL.length}}</span> articles</span>
     <span class="stat-pill" style="color:var(--ac)"><span class="stat-n" style="color:var(--ac)">${{fn}}</span> new</span>`;
  document.getElementById('feedMeta').textContent=`${{FCNT-ERRS.length}}/${{FCNT}} feeds active`;
}}

function renderTicker(){{
  const items=ALL.slice(0,30).map(a=>{{
    const t=a.title.length>80?a.title.slice(0,80)+'…':a.title;
    return `<span class="t-item">${{CAT_ICO[a.cat]||'·'}} ${{esc(t)}}</span><span class="t-sep"> — </span>`;
  }}).join('');
  document.getElementById('tInner').innerHTML=items+items;
}}

function renderErrors(){{
  const el=document.getElementById('errPanel');
  if(!ERRS.length){{el.innerHTML='';return;}}
  el.innerHTML=`<div class="err-panel">
    <div class="err-hdr" onclick="this.nextElementSibling.classList.toggle('open')">
      ⚠ ${{ERRS.length}} feed(s) had errors <span style="margin-left:auto;opacity:.5">▾</span>
    </div>
    <div class="err-body">${{ERRS.map(e=>`<div class="err-line">✗ ${{esc(e)}}</div>`).join('')}}</div>
  </div>`;
}}

function renderSrcBar(){{
  const srcs=[...new Set(ALL.map(a=>a.src))].sort();
  document.getElementById('srcBar').innerHTML='<span class="src-lbl">Sources</span>'+
    srcs.map(s=>`<span class="pill ${{S.srcs.has(s)?'on':''}}" onclick="toggleSrc('${{esc(s)}}')">${{esc(s)}}</span>`).join('');
}}

function heroHTML(a){{
  const nb=a.fresh?'<span class="new-badge">NEW</span>':'';
  return `<div class="hero-main">
    <div class="hero-cat">${{CAT_ICO[a.cat]||'·'}} ${{a.cat}}</div>
    <div class="hero-title"><a href="${{esc(a.url)}}" target="_blank" rel="noopener">${{esc(a.title)}}</a> ${{nb}}</div>
    <div class="hero-sum">${{esc(a.summary)||''}}</div>
    <div class="hero-foot">
      <span class="hero-src">${{esc(a.src)}}</span>
      <span style="color:var(--bd)">·</span>
      <span class="hero-ago">${{esc(a.ago)}}</span>
    </div>
  </div>`;
}}

function sideItemHTML(a){{
  return `<div class="side-item">
    <div class="side-cat">${{a.cat}}</div>
    <div class="side-title"><a href="${{esc(a.url)}}" target="_blank" rel="noopener">${{esc(a.title)}}</a></div>
    <div class="side-src">${{esc(a.src)}} · ${{esc(a.ago)}}</div>
  </div>`;
}}

function cardHTML(a){{
  const nb=a.fresh?'<span class="new-badge" style="font-size:7px;margin-left:4px">NEW</span>':'';
  return `<div class="art-card">
    <div class="card-cat">${{CAT_ICO[a.cat]||'·'}} ${{a.cat}}</div>
    <div class="card-title"><a href="${{esc(a.url)}}" target="_blank" rel="noopener">${{esc(a.title)}}</a>${{nb}}</div>
    <div class="card-sum">${{esc(a.summary)||''}}</div>
    <div class="card-foot">
      <span class="card-src">${{esc(a.src)}}</span>
      <span class="card-ago">${{esc(a.ago)}}</span>
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
  renderPag(arts.length);
  const page=arts.slice(S.page*PER,(S.page+1)*PER);
  const el=document.getElementById('grid');
  if(!page.length){{
    el.innerHTML='<div class="empty">No articles match your filters.</div>';
    return;
  }}

  let html='';

  // First page: hero layout (first 4 articles)
  if(S.page===0&&page.length>=4){{
    const [hero,...rest]=page;
    const sidebar=rest.slice(0,3);
    const remaining=rest.slice(3);

    html+=`<div class="sec-hdr">
      <span class="sec-title">${{S.cat==='All'?'Latest Intelligence':S.cat}}</span>
      <span class="sec-line"></span>
      <span class="sec-count">${{arts.length}} articles</span>
    </div>`;

    html+=`<div class="hero-layout">
      ${{heroHTML(hero)}}
      <div class="hero-sidebar">${{sidebar.map(sideItemHTML).join('')}}</div>
    </div>`;

    if(remaining.length){{
      html+=`<div class="cat-divider">
        <span class="cat-div-line"></span>
        <span class="cat-div-label">More Reports</span>
        <span class="cat-div-line"></span>
      </div>`;
      html+=`<div class="card-grid">${{remaining.map(cardHTML).join('')}}</div>`;
    }}
  }} else {{
    html+=`<div class="sec-hdr">
      <span class="sec-title">${{S.cat==='All'?'Intelligence Feed':S.cat}}</span>
      <span class="sec-line"></span>
      <span class="sec-count">Page ${{S.page+1}} · ${{arts.length}} articles</span>
    </div>`;
    html+=`<div class="card-grid">${{page.map(cardHTML).join('')}}</div>`;
  }}

  el.innerHTML=html;
}}

function setCat(c,btn){{
  S.cat=c;S.page=0;
  if(_catBtn)_catBtn.classList.remove('on');
  if(btn){{btn.classList.add('on');_catBtn=btn;}}
  renderGrid();
}}

function goPage(p){{
  const arts=filtered();
  S.page=Math.max(0,Math.min(p,Math.ceil(arts.length/PER)-1));
  renderGrid();
  document.getElementById('mainArea').scrollTop=0;
}}

function toggleSrc(s){{
  S.srcs.has(s)?S.srcs.delete(s):S.srcs.add(s);
  S.page=0;renderSrcBar();renderGrid();
}}

document.getElementById('th').addEventListener('change',function(){{
  document.body.className=this.value;
}});

let q_t;
document.getElementById('si').addEventListener('input',function(){{
  clearTimeout(q_t);
  q_t=setTimeout(()=>{{S.search=this.value;S.page=0;renderGrid();}},200);
}});

setInterval(()=>{{
  const n=new Date();
  document.getElementById('mastDate').textContent=
    n.toLocaleDateString('en-GB',{{day:'2-digit',month:'short',year:'numeric'}})+' · '+
    n.toLocaleTimeString('en-GB',{{hour:'2-digit',minute:'2-digit'}});
}},15000);

renderMasthead();renderTicker();renderErrors();renderSrcBar();renderGrid();
</script>
</body>
</html>"""

components.html(HTML, height=900, scrolling=False)
