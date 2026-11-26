import streamlit as st
import pandas as pd

# ---------------------------------------------------------
# 1. PAGE CONFIG (Mobile-First Compact Layout)
# ---------------------------------------------------------
st.set_page_config(
    page_title="Milkfish Monitor | Behavior Analysis",
    page_icon="🐟",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------
# 2. COLOR THEME PALETTES
# ---------------------------------------------------------
THEMES = {
    "Brackish Emerald": {
        "bg": "#F4F7F5",
        "card": "#FFFFFF",
        "sidebar": "#0F291E",
        "sidebar_text": "#ECFDF5",
        "primary": "#10B981",
        "primary_dark": "#065F46",
        "text": "#111827",
        "muted": "#6B7280",
        "border": "#E2E8F0",
    },
    "Oceanic Aqua": {
        "bg": "#F0F7FA",
        "card": "#FFFFFF",
        "sidebar": "#0B2538",
        "sidebar_text": "#F0F9FF",
        "primary": "#0284C7",
        "primary_dark": "#0369A1",
        "text": "#0F172A",
        "muted": "#64748B",
        "border": "#CBD5E1",
    },
    "Midnight Pond (Dark)": {
        "bg": "#0B1612",
        "card": "#13241E",
        "sidebar": "#070F0C",
        "sidebar_text": "#E2E8F0",
        "primary": "#34D399",
        "primary_dark": "#10B981",
        "text": "#F8FAFC",
        "muted": "#94A3B8",
        "border": "#1E3A2F",
    },
    "Coastal Slate": {
        "bg": "#F8FAFC",
        "card": "#FFFFFF",
        "sidebar": "#1E293B",
        "sidebar_text": "#F8FAFC",
        "primary": "#0D9488",
        "primary_dark": "#115E59",
        "text": "#0F172A",
        "muted": "#64748B",
        "border": "#E2E8F0",
    },
}

# ---------------------------------------------------------
# 3. CUSTOM MILKFISH (BANGUS) SVG LOGO
# ---------------------------------------------------------
def get_milkfish_logo(accent_color: str) -> str:
    return f"""
    <div style="display:flex; align-items:center; gap:10px; padding:4px 0 8px 0;">
        <div style="
            width:40px; height:40px; border-radius:10px;
            background: linear-gradient(135deg, {accent_color}, #047857);
            display:flex; align-items:center; justify-content:center;
            box-shadow: 0 2px 6px rgba(0,0,0,0.25); flex-shrink:0;">
            <svg width="28" height="28" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M14 32L4 21C6 27 6 37 4 43L14 32Z" fill="#FFFFFF"/>
                <path d="M12 32C18 21 34 18 52 27C56 29 59 31 60 32C59 33 56 35 52 37C34 46 18 43 12 32Z" fill="#FFFFFF"/>
                <path d="M30 22L25 14L36 21Z" fill="#D1FAE5"/>
                <path d="M31 42L27 48L36 42Z" fill="#D1FAE5"/>
                <path d="M46 26C44 30 44 34 46 38" stroke="{accent_color}" stroke-width="2.2" stroke-linecap="round"/>
                <circle cx="52" cy="30.5" r="2" fill="#064E3B"/>
            </svg>
        </div>
        <div style="line-height:1.15;">
            <div style="font-weight:700; font-size:15px; color:#FFFFFF;">Milkfish Monitor</div>
            <div style="font-size:11px; color:#A7F3D0;">Behavior Analysis</div>
        </div>
    </div>
    """

# ---------------------------------------------------------
# 4. SIDEBAR CONTROLS (Organized, Compact, Minimal Spacing)
# ---------------------------------------------------------
if "monitoring" not in st.session_state:
    st.session_state.monitoring = True

with st.sidebar:
    selected_theme_name = st.selectbox(
        "Color Theme",
        list(THEMES.keys()),
        index=0,
        label_visibility="collapsed",
    )
    t = THEMES[selected_theme_name]

    st.markdown(get_milkfish_logo(t["primary"]), unsafe_allow_html=True)
    st.markdown("<hr style='margin:6px 0 10px 0; border-color:rgba(255,255,255,0.12);'>", unsafe_allow_html=True)

    st.caption("MONITORING CONTROLS")
    col_start, col_stop = st.columns(2, gap="small")
    with col_start:
        if st.button("▶ Start", use_container_width=True, type="primary"):
            st.session_state.monitoring = True
    with col_stop:
        if st.button("⏹ Stop", use_container_width=True):
            st.session_state.monitoring = False

    st.caption("VIDEO SOURCE")
    uploaded_file = st.file_uploader(
        "Upload Tank Video",
        type=["mp4", "mkv", "avi", "mov", "m4v", "wmv"],
        label_visibility="collapsed",
    )

    st.markdown("<hr style='margin:8px 0; border-color:rgba(255,255,255,0.12);'>", unsafe_allow_html=True)
    st.caption("DASHBOARD SECTIONS")
    st.markdown(
        f"""
        <div class="sidebar-nav">
            <a href="#live-video-feed">🎥 Live Video Feed</a>
            <a href="#key-metrics">📊 Key KPI Metrics</a>
            <a href="#behavior-breakdown">🐟 Behavior Breakdown</a>
            <a href="#individual-tracking">📋 Fish Tracking Table</a>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------
# 5. MOBILE CSS + HIDE STREAMLIT & GITHUB VIEWER ELEMENTS
# ---------------------------------------------------------
st.markdown(
    f"""
    <style>
    /* Hide Streamlit branding, menu, status/viewer & GitHub badge elements */
    #MainMenu,
    footer,
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    #GithubIcon,
    [class*="viewerBadge"],
    [class*="ViewerBadge"] {{
        display: none !important;
        visibility: hidden !important;
    }}

    /* Keep top header transparent so sidebar toggle button remains usable on mobile */
    header[data-testid="stHeader"] {{
        background: transparent !important;
        height: 2.5rem !important;
    }}

    /* Main background & compact mobile padding */
    .stApp {{
        background-color: {t['bg']};
        color: {t['text']};
    }}
    .block-container {{
        padding-top: 0.5rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        max-width: 900px;
    }}

    /* Sidebar compact styling */
    section[data-testid="stSidebar"] {{
        background-color: {t['sidebar']};
        color: {t['sidebar_text']};
    }}
    section[data-testid="stSidebar"] .block-container {{
        padding-top: 0.75rem !important;
    }}
    section[data-testid="stSidebar"] .stCaption {{
        color: #94A3B8 !important;
        font-size: 10px !important;
        font-weight: 700;
        letter-spacing: 0.06em;
        margin-top: 6px !important;
        margin-bottom: 2px !important;
    }}
    section[data-testid="stSidebar"] button {{
        padding: 0.25rem 0.5rem !important;
        min-height: 34px !important;
        font-size: 13px !important;
        border-radius: 8px !important;
    }}

    /* Compact Uploader Box */
    section[data-testid="stFileUploaderDropzone"] {{
        padding: 0.5rem !important;
        min-height: 54px !important;
        background-color: rgba(255,255,255,0.06) !important;
        border: 1px dashed {t['primary']} !important;
        border-radius: 8px !important;
    }}

    /* Organized Sidebar Navigation Links under Upload */
    .sidebar-nav {{
        display: flex;
        flex-direction: column;
        gap: 4px;
        margin-top: 4px;
    }}
    .sidebar-nav a {{
        display: block;
        padding: 7px 10px;
        border-radius: 7px;
        color: {t['sidebar_text']};
        text-decoration: none;
        font-size: 13px;
        font-weight: 500;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.08);
        transition: background 0.15s ease;
    }}
    .sidebar-nav a:hover {{
        background: {t['primary']};
        color: #FFFFFF;
    }}

    /* Top Mobile Header Bar */
    .mobile-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: {t['card']};
        border: 1px solid {t['border']};
        border-radius: 12px;
        padding: 8px 12px;
        margin-bottom: 10px;
    }}
    .status-pill {{
        background: rgba(16, 185, 129, 0.15);
        color: {t['primary_dark']};
        border: 1px solid {t['primary']};
        font-size: 11px;
        font-weight: 600;
        padding: 2px 9px;
        border-radius: 999px;
    }}

    /* Card Containers */
    .dash-card {{
        background: {t['card']};
        border: 1px solid {t['border']};
        border-radius: 12px;
        padding: 12px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    .kpi-label {{
        font-size: 11px;
        color: {t['muted']};
        font-weight: 600;
        margin-bottom: 2px;
    }}
    .kpi-value {{
        font-size: 22px;
        font-weight: 800;
        color: {t['text']};
        line-height: 1.1;
    }}
    .kpi-sub {{
        font-size: 11px;
        color: {t['muted']};
        margin-top: 3px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 6. COMPACT MOBILE HEADER
# ---------------------------------------------------------
status_label = "● System Online" if st.session_state.monitoring else "⏸ Paused"
st.markdown(
    f"""
    <div class="mobile-header">
        <div>
            <div style="font-weight:700; font-size:15px; color:{t['primary_dark']};">Milkfish Monitoring Dashboard</div>
            <div style="font-size:11px; color:{t['muted']};">Automated computer vision & behavioral analysis</div>
        </div>
        <span class="status-pill">{status_label}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 7. PRIORITY 1: VIDEO DISPLAY ABOVE THE FOLD
# ---------------------------------------------------------
st.markdown('<div id="live-video-feed"></div>', unsafe_allow_html=True)

with st.container():
    if uploaded_file is not None:
        st.video(uploaded_file)
    else:
        st.markdown(
            f"""
            <div class="dash-card" style="padding:8px;">
                <div style="
                    position:relative; width:100%; aspect-ratio:16/9; border-radius:8px; overflow:hidden;
                    background: radial-gradient(circle at 65% 60%, #857B28 0%, #2C3E35 55%, #16221E 100%);
                    border: 1px solid {t['border']};">
                    <div style="position:absolute; top:14%; left:42%; border:1.5px solid #4ADE80; padding:1px 4px; font-size:9px; color:#FFF; background:rgba(22,101,52,0.75);">ID 275 • 0.75</div>
                    <div style="position:absolute; top:52%; left:44%; border:1.5px solid #4ADE80; padding:1px 4px; font-size:9px; color:#FFF; background:rgba(22,101,52,0.75);">ID 182 • 0.64</div>
                    <div style="position:absolute; top:58%; left:14%; border:1.5px solid #93C5FD; padding:1px 4px; font-size:9px; color:#FFF; background:rgba(30,58,138,0.65);">ID 290 • 0.55</div>
                    <div style="position:absolute; top:56%; left:70%; border:1.5px solid #93C5FD; padding:1px 4px; font-size:9px; color:#FFF; background:rgba(30,58,138,0.65);">ID 286 • 0.56</div>
                    <div style="position:absolute; bottom:8px; left:8px; background:rgba(0,0,0,0.6); color:#FFF; font-size:10px; padding:2px 7px; border-radius:4px;">
                        LIVE CV STREAM • 12.3 FPS
                    </div>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:11px; color:{t['muted']}; margin-top:6px; padding:0 2px;">
                    <span><b>VID01.mp4</b> • 768×338</span>
                    <span>Source: 30.0 fps • 02:59</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.progress(45, text="Analyzing video... 45% (4:11 elapsed • ~5:07 left)")
    st.markdown(
        f"""
        <div class="dash-card" style="display:flex; justify-content:space-between; align-items:center; padding:10px 12px;">
            <div>
                <div style="font-size:12px; font-weight:700; color:{t['text']};">Recommendation: Continue routine monitoring</div>
                <div style="font-size:11px; color:{t['muted']};">No unusual swimming activity observed.</div>
            </div>
            <span class="status-pill">All Clear</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------
# 8. PRIORITY 2: COMPACT 2-COLUMN MOBILE KPI GRID
# ---------------------------------------------------------
st.markdown('<div id="key-metrics"></div>', unsafe_allow_html=True)

kpis = [
    ("Unique Milkfish Tracked", "213", "14 in view now"),
    ("Peak Fish Count", "37", "Max in single frame"),
    ("Active Fish", "2 (100%)", "12 need more tracking"),
    ("Inactive / Low-Move", "0 (0%)", "Sustained low motion"),
    ("Avg Swimming Speed", "52.9 px/s", "Mean of current frame"),
    ("Schooling Cohesion", "83%", "Current frame"),
    ("Processing FPS", "12.3 fps", "Source: 30.0 fps"),
    ("Unusual Activity", "0 (0%)", "Video observation only"),
]

for i in range(0, len(kpis), 2):
    c1, c2 = st.columns(2, gap="small")
    for col, (label, val, sub) in zip([c1, c2], kpis[i : i + 2]):
        with col:
            st.markdown(
                f"""
                <div class="dash-card">
                    <div class="kpi-label">{label}</div>
                    <div class="kpi-value">{val}</div>
                    <div class="kpi-sub">{sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------
# 9. PRIORITY 3: BEHAVIOR CATEGORIES & DISTRIBUTION
# ---------------------------------------------------------
st.markdown('<div id="behavior-breakdown"></div>', unsafe_allow_html=True)

st.markdown(
    f"""
    <div class="dash-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-weight:700; font-size:14px;">Behavior Categories</span>
            <span style="font-size:11px; color:{t['muted']};">Current Frame</span>
        </div>
        <div style="margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-size:12px;">
                <span><b>Normal Swimming</b> — Steady, relaxed movement</span>
                <span><b>3 (100%)</b></span>
            </div>
            <div style="height:6px; background:{t['border']}; border-radius:4px; margin-top:4px;">
                <div style="width:100%; height:100%; background:{t['primary']}; border-radius:4px;"></div>
            </div>
        </div>
        <div style="margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-size:12px;">
                <span><b>Schooling Behavior</b> — Moving close together</span>
                <span>0 (0%)</span>
            </div>
            <div style="height:6px; background:{t['border']}; border-radius:4px; margin-top:4px;"></div>
        </div>
        <div style="margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; font-size:12px;">
                <span><b>Feeding Activity</b> — Gathering to feed</span>
                <span>0 (0%)</span>
            </div>
            <div style="height:6px; background:{t['border']}; border-radius:4px; margin-top:4px;"></div>
        </div>
        <div>
            <div style="display:flex; justify-content:space-between; font-size:12px;">
                <span><b>Unusual Activity</b> — Sudden or irregular motion</span>
                <span>0 (0%)</span>
            </div>
            <div style="height:6px; background:{t['border']}; border-radius:4px; margin-top:4px;"></div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# 10. PRIORITY 4: INDIVIDUAL FISH TRACKING TABLE
# ---------------------------------------------------------
st.markdown('<div id="individual-tracking"></div>', unsafe_allow_html=True)

fish_df = pd.DataFrame(
    [
        {"Fish ID": "Milkfish 171", "Behavior": "Normal Swimming", "Activity": "Active", "Speed": "68 px/s"},
        {"Fish ID": "Milkfish 182", "Behavior": "Normal Swimming", "Activity": "Active", "Speed": "74 px/s"},
        {"Fish ID": "Milkfish 275", "Behavior": "Normal Swimming", "Activity": "Active", "Speed": "51 px/s"},
        {"Fish ID": "Milkfish 136", "Behavior": "Tracking...", "Activity": "Pending", "Speed": "—"},
    ]
)

st.markdown("<div style='font-weight:700; font-size:14px; margin:6px 0;'>Individual Fish Tracking (11 fish)</div>", unsafe_allow_html=True)
st.dataframe(fish_df, use_container_width=True, hide_index=True)
