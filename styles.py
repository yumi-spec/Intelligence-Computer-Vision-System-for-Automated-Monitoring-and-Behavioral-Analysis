"""Minimalist dark-navy theme: one type scale, one 4 px spacing scale, one palette.

All custom classes are prefixed `mf-`. Streamlit widget overrides are scoped to data-testid selectors.
"""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root{--bg:#FFFFFF;--side:#F0FAF3;--card:#FFFFFF;--bd:#D2E4D8;--acc:#14532D;
--tx:#14261B;--mut:#4F6156;--ok:#16803C;--warn:#B45309;--bad:#B91C1C;
--stage:#EAF4ED;--track:#DCFCE7;--overlay:rgba(240,250,243,.85);--line:#E3EFE7}

/* ---------- app shell ---------- */
html,body,.stApp,[data-testid="stApp"]{background:var(--bg)!important;color:var(--tx);
font-family:Inter,"Segoe UI",system-ui,-apple-system,Roboto,Arial,sans-serif}
header[data-testid="stHeader"]{background:transparent!important;height:0!important;min-height:0!important;
pointer-events:none;overflow:visible}
[data-testid="stToolbarActions"],[data-testid="stMainMenu"],[data-testid="stAppDeployButton"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],footer{display:none!important}
/* narrow windows: keep the button that reopens the collapsed sidebar */
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"]{
display:flex!important;visibility:visible!important;pointer-events:auto!important;position:fixed!important;
top:.6rem!important;left:.6rem!important;z-index:1000001!important;background:var(--acc)!important;
border-radius:8px!important;padding:.15rem .35rem}
[data-testid="stExpandSidebarButton"] *,[data-testid="stSidebarCollapsedControl"] *,
[data-testid="collapsedControl"] *{color:#fff!important}
@media (max-width:999px){.mf-head{padding-left:48px}}

.block-container,[data-testid="stMainBlockContainer"]{padding:24px 24px 32px!important;max-width:100%!important}
[data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{gap:16px;overflow:visible}
[data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]{gap:16px}
[data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]{flex-shrink:0!important;overflow:visible;margin-bottom:0!important}
/* Streamlit pulls the next block up by 1rem after every markdown block; cancel that */
[data-testid="stMarkdownContainer"],.stMarkdown{margin-bottom:0!important;display:flow-root}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"]{background:var(--side)!important;border-right:1px solid var(--bd)}
@media (min-width:1000px){
[data-testid="stSidebar"],[data-testid="stSidebar"][aria-expanded="false"]{transform:none!important;
margin-left:0!important;left:0!important;visibility:visible!important;min-width:232px!important;width:232px!important}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{visibility:visible!important}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"],[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"],[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"]{display:none!important}}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{min-height:0!important;height:0!important;padding:0!important}
[data-testid="stSidebar"] [data-testid="stLogo"]{display:none}
[data-testid="stSidebarCollapseButton"] button,[data-testid="stSidebarCollapseButton"] button *{color:var(--tx)!important}
[data-testid="stSidebarUserContent"]{padding:16px 12px}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:8px}
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"]{gap:8px}
[data-testid="stSidebar"] .stElementContainer:has(button){width:100%!important}

[data-testid="stSidebar"] .stButton>button{width:100%!important;min-height:44px;border-radius:8px;
font-size:15px;font-weight:500;background:transparent;color:var(--mut);border:1px solid transparent;
justify-content:flex-start;padding:0 12px;gap:12px;white-space:nowrap}
[data-testid="stSidebar"] .stButton>button p{font-size:inherit;margin:0;white-space:nowrap}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(22,128,60,.10);color:var(--tx);border-color:transparent}
[data-testid="stSidebar"] .stButton>button[kind="primary"],
[data-testid="stSidebar"] .stButton>button[data-testid="stBaseButton-primary"]{
background:rgba(22,128,60,.18);color:var(--tx);border-color:rgba(22,128,60,.35)}
[data-testid="stSidebar"] .st-key-btn_start button,[data-testid="stSidebar"] .st-key-btn_stop button{
justify-content:center;min-height:40px;font-size:14px;background:var(--card);color:var(--tx);border:1px solid var(--bd)}
[data-testid="stSidebar"] .st-key-btn_start button:hover,[data-testid="stSidebar"] .st-key-btn_stop button:hover{
border-color:var(--acc);color:var(--tx)}

[data-testid="stSidebar"] [data-testid="stFileUploader"]{width:100%}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"]{background:var(--card);border:1px dashed var(--bd);
border-radius:8px;padding:12px;flex-direction:column;align-items:stretch;gap:8px}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"]{min-width:0}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] *{color:var(--tx)!important}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small,
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] span{font-size:12px;color:var(--mut)!important;
white-space:normal;overflow-wrap:anywhere}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button{width:100%!important;min-height:36px;
font-size:13px;justify-content:center;background:var(--acc);border:1px solid var(--acc);border-radius:8px}
[data-testid="stSidebar"] [data-testid="stFileUploaderFile"]{min-width:0;overflow-wrap:anywhere;font-size:12px}

.mf-brand{display:flex;align-items:center;gap:12px;padding:0 4px 12px;border-bottom:1px solid var(--bd);margin-bottom:8px}
.mf-logo{width:32px;height:32px;flex:0 0 32px;border-radius:8px;background:var(--acc);color:#fff;
font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center}
.mf-bname{font-size:15px;font-weight:600;line-height:1.2}
.mf-bsub{font-size:12px;color:var(--mut)}
.mf-slabel{font-size:12.5px;color:var(--mut);padding:8px 4px 0}

/* ---------- main widgets (Analytics / Reports / Settings) ---------- */
[data-testid="stMain"] .stButton>button,[data-testid="stMain"] .stDownloadButton>button{min-height:40px;
border-radius:8px;font-size:14px;background:var(--card);color:var(--tx);border:1px solid var(--bd)}
[data-testid="stMain"] .stButton>button:hover,[data-testid="stMain"] .stDownloadButton>button:hover{
border-color:var(--acc);color:var(--tx)}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 20px}
[data-testid="stMetricLabel"]{font-size:14px;color:var(--mut)}
[data-testid="stMetricValue"]{font-size:28px;font-weight:700}
button[data-baseweb="tab"]{font-size:15px;font-weight:500}
[data-testid="stDataFrame"]{border:1px solid var(--bd);border-radius:10px;overflow:hidden}
[data-testid="stMain"] [data-testid="stFileUploaderDropzone"]{background:var(--card);border:1px dashed var(--bd);border-radius:10px}

/* ---------- dashboard blocks ---------- */
.mf{color:var(--tx);font-size:14px;line-height:1.45}
.mf,.mf *{box-sizing:border-box}

.mf-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px 24px;flex-wrap:wrap}
.mf-title{font-size:27px;font-weight:700;line-height:1.2}
.mf-sub{font-size:14px;color:var(--mut);margin-top:4px}
.mf-headr{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.mf-time{font-size:13px;color:var(--mut);white-space:nowrap}

.mf-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-top:8px}
.mf-kpi{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 20px;
min-height:104px;display:flex;flex-direction:column;gap:6px;min-width:0}
.mf-klabel{font-size:14px;color:var(--mut)}
.mf-kval{font-size:30px;font-weight:700;line-height:1.1}
.mf-kval .u{font-size:14px;font-weight:400;color:var(--mut)}
.mf-ksub{font-size:12.5px;color:var(--mut)}
.mf-info{cursor:help;color:var(--acc)}
@media (max-width:1100px){.mf-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:380px){.mf-kpis{grid-template-columns:1fr}}

.mf-main{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,3fr);gap:16px;align-items:start}
@media (max-width:1100px){.mf-main{grid-template-columns:1fr}}
.mf-side{display:flex;flex-direction:column;gap:16px;min-width:0}

.mf-card{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 20px;min-width:0}
.mf-cardhead{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}
.mf-ch{font-size:16px;font-weight:600}

.mf-stage{position:relative;aspect-ratio:16/9;width:100%;background:var(--stage);border-radius:8px;
overflow:hidden;display:flex;align-items:center;justify-content:center}
.mf-stage img{width:100%;height:100%;object-fit:contain;display:block}
.mf-ended{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
justify-content:center;gap:4px;background:var(--overlay);text-align:center;font-size:16px;font-weight:600}
.mf-ended span{font-size:13px;font-weight:400;color:var(--mut)}
.mf-meta{display:flex;flex-wrap:wrap;gap:4px 16px;margin-top:12px;font-size:12.5px;color:var(--mut)}
.mf-meta .fn{display:inline-block;max-width:min(100%,320px);overflow:hidden;text-overflow:ellipsis;
white-space:nowrap;vertical-align:bottom}
.mf-msg{padding:24px;text-align:center;display:flex;flex-direction:column;gap:6px;max-width:100%;
overflow-wrap:anywhere;font-size:14px}
.mf-msg b{font-size:16px;font-weight:600}
.mf-msg span{font-size:13px;color:var(--mut)}
.mf-msg.bad b{color:var(--bad)}.mf-msg.warn b{color:var(--warn)}

.mf-badge{display:inline-flex;align-items:center;gap:4px;font-size:12.5px;font-weight:600;padding:3px 10px;
border-radius:999px;border:1px solid var(--bd);white-space:nowrap;line-height:1.4}
.mf-badge.ok{color:var(--ok);background:rgba(22,128,60,.12);border-color:rgba(22,128,60,.4)}
.mf-badge.warn{color:var(--warn);background:rgba(180,83,9,.12);border-color:rgba(180,83,9,.4)}
.mf-badge.bad{color:var(--bad);background:rgba(185,28,28,.12);border-color:rgba(185,28,28,.4)}
.mf-badge.mut{color:var(--mut);background:rgba(79,97,86,.10)}

.mf-kv{display:flex;justify-content:space-between;align-items:baseline;gap:16px;padding:8px 0;
border-bottom:1px solid var(--line);font-size:14px}
.mf-kv:last-of-type{border-bottom:0}
.mf-kv span{color:var(--mut);flex:0 1 auto}
.mf-kv b{font-weight:500;text-align:right;overflow-wrap:anywhere;min-width:0}
.mf-note{font-size:13px;color:var(--mut);margin-top:8px}
.mf-act{font-size:15px;font-weight:600}

.mf-sec{margin-top:8px}
.mf-h2{font-size:20px;font-weight:600;margin-bottom:12px}
.mf-grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
@media (max-width:900px){.mf-grid2{grid-template-columns:1fr}}
.mf-bottom{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.7fr);gap:16px;align-items:start}
@media (max-width:1000px){.mf-bottom{grid-template-columns:1fr}}

.mf-bars{display:flex;flex-direction:column;gap:16px}
.mf-brow{display:flex;justify-content:space-between;gap:12px;font-size:14px;margin-bottom:6px}
.mf-brow span:last-child{color:var(--mut);white-space:nowrap}
.mf-bar{height:8px;border-radius:999px;background:var(--track);overflow:hidden}
.mf-bar i{display:block;height:100%;border-radius:999px}
.mf-bar i.ok{background:var(--ok)}.mf-bar i.warn{background:var(--warn)}.mf-bar i.bad{background:var(--bad)}

.mf-tw{overflow:auto;max-height:320px;border-radius:8px}
.mf-tbl{width:100%;min-width:560px;border-collapse:collapse;font-size:13.5px;table-layout:fixed}
.mf-tbl th{position:sticky;top:0;background:var(--card);text-align:left;font-size:13px;font-weight:600;
color:var(--mut);padding:10px 12px;border-bottom:1px solid var(--bd)}
.mf-tbl td{padding:10px 12px;border-bottom:1px solid var(--line);font-weight:400;
overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mf-tbl .num{text-align:right;font-variant-numeric:tabular-nums}
.mf-tbl th.num{text-align:right}
.mf-tbl .ctr{text-align:center}

.mf-alert{background:var(--card);border:1px solid var(--bd);border-left-width:4px;border-radius:12px;
padding:12px 16px;margin-top:8px}
.mf-alert.bad{border-left-color:var(--bad)}.mf-alert.warn{border-left-color:var(--warn)}

/* ---------- layout helper ---------- */
.mf-leftcol{display:flex;flex-direction:column;gap:16px;min-width:0}

/* ---------- settings menu rows ---------- */
[class*="st-key-sec_"]{background:var(--card);border:1px solid var(--bd);border-radius:12px;padding:16px 20px}

/* ---------- native widgets follow the chosen theme ---------- */
[data-testid="stMain"] h1,[data-testid="stMain"] h2,[data-testid="stMain"] h3,
[data-testid="stMain"] [data-testid="stWidgetLabel"] p,[data-testid="stMain"] label p,
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p{color:var(--tx)}
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] *{color:var(--mut)!important}
[data-testid="stMain"] [data-testid="stMetricLabel"] *{color:var(--mut)}
[data-baseweb="select"]>div,[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="textarea"]{
background:var(--card)!important;border-color:var(--bd)!important}
[data-baseweb="select"] div,[data-baseweb="input"] input,[data-baseweb="base-input"] input{color:var(--tx)!important}
[data-baseweb="popover"] ul,[data-baseweb="menu"]{background:var(--card)!important}
[data-baseweb="popover"] li,[data-baseweb="menu"] li{color:var(--tx)!important}
[data-baseweb="popover"] li:hover{background:rgba(22,128,60,.15)!important}
button[data-baseweb="tab"]{color:var(--mut)}
button[data-baseweb="tab"][aria-selected="true"]{color:var(--tx)}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button,
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button *{color:#fff!important}
/* ---------- Milkfish Monitor look: white, dark/light green, rounded cards ---------- */
.mf-card,.mf-kpi,.mf-alert,[data-testid="stMetric"],[class*="st-key-sec_"]{border-radius:16px;box-shadow:0 2px 8px rgba(20,83,45,.10)}
.mf-title,.mf-h2,.mf-ch{color:var(--acc)}
.mf-alert.warn{background:#FFFBEB;border-color:#F2C46B;border-left-color:var(--warn)}
.mf-alert.bad{background:#FEF2F2;border-color:#F5B5B5;border-left-color:var(--bad)}
[data-testid="stMain"] .stButton>button[kind="primary"],[data-testid="stMain"] .stDownloadButton>button[kind="primary"]{
background:var(--acc);color:#fff;border-color:var(--acc)}
[data-testid="stSidebar"] .stButton>button[kind="primary"],
[data-testid="stSidebar"] .stButton>button[data-testid="stBaseButton-primary"]{color:var(--acc);font-weight:700}

/* ---------- bottom navigation (phones and narrow windows) ---------- */
.st-key-bottomnav{display:none;position:fixed;left:0;right:0;bottom:0;z-index:999;background:var(--card);
border-top:1px solid var(--bd);padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px))}
.st-key-bottomnav [data-testid="stHorizontalBlock"]{gap:4px!important;flex-wrap:nowrap!important}
.st-key-bottomnav [data-testid="stColumn"]{min-width:0!important;flex:1 1 0!important}
.st-key-bottomnav .stButton>button{flex-direction:column;gap:2px;min-height:52px;width:100%;padding:4px 0;
background:transparent!important;color:var(--mut)!important;border:0!important;border-radius:12px}
.st-key-bottomnav .stButton>button>div,.st-key-bottomnav .stButton>button [data-testid="stMarkdownContainer"]{
display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;width:100%}
.st-key-bottomnav .stButton>button p{font-size:11px;font-weight:500;margin:0;text-align:center}
.st-key-bottomnav .stButton>button[kind="primary"],.st-key-bottomnav .stButton>button[data-testid="stBaseButton-primary"]{
background:rgba(22,128,60,.12)!important;color:var(--acc)!important}
.st-key-bottomnav .stButton>button[kind="primary"] p{font-weight:700}
@media (max-width:999px){
[data-testid="stSidebar"] [class*="st-key-nav_"]{display:none!important}
.st-key-bottomnav{display:block}
.block-container,[data-testid="stMainBlockContainer"]{padding:16px 16px 96px!important}
.mf-title{font-size:22px}
.mf-kval{font-size:26px}}

/* ---------- behavior categories ---------- */
.mf-cats{display:flex;flex-direction:column;gap:14px}
.mf-cat{display:flex;align-items:center;gap:12px}
.mf-ico{width:40px;height:40px;border-radius:12px;background:#DCFCE7;color:var(--acc);display:flex;
align-items:center;justify-content:center;flex:none}
.mf-ico.w{background:#FEF3C7;color:var(--warn)}
.mf-ico svg{fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.mf-ct{font-size:14px;font-weight:600}
.mf-cd{font-size:12.5px;color:var(--mut)}
.mf-cn{margin-left:auto;text-align:right;font-size:22px;font-weight:700;color:var(--acc);line-height:1.1}
.mf-cn small{display:block;font-size:12px;font-weight:500;color:var(--mut)}

/* hide the "Live Milkfish Monitoring / LIVE" heading above the video (left column only) */
.mf-main>div:first-child .mf-cardhead{display:none}
"""


DARK = """
:root{--bg:#0B1F14;--side:#0A1A11;--card:#12291C;--bd:#25472F;--acc:#4ADE80;
--tx:#E6F4EA;--mut:#9DB8A5;--ok:#4ADE80;--warn:#FBBF24;--bad:#F87171;
--stage:#07140D;--track:#1C3A27;--overlay:rgba(7,20,13,.8);--line:#1F3A29}
.mf-ico{background:rgba(74,222,128,.15)}.mf-ico.w{background:rgba(251,191,36,.15)}
.mf-card,.mf-kpi,[data-testid="stMetric"]{box-shadow:0 2px 8px rgba(0,0,0,.35)}
.mf-alert.warn{background:rgba(251,191,36,.10);border-color:rgba(251,191,36,.4);border-left-color:var(--warn)}
.mf-alert.bad{background:rgba(248,113,113,.10);border-color:rgba(248,113,113,.4);border-left-color:var(--bad)}
[data-testid="stMain"] .stButton>button[kind="primary"],[data-testid="stMain"] .stDownloadButton>button[kind="primary"]{color:#06210F}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button,
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button *,
[data-testid="stExpandSidebarButton"] *,[data-testid="stSidebarCollapsedControl"] *,[data-testid="collapsedControl"] *{color:#06210F!important}
"""


def build_css(theme: str = "light") -> str:
    """Light green theme by default; the dark green palette is added on top when theme == "dark"."""
    return CSS + (DARK if theme == "dark" else "")