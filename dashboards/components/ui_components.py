"""ORPMI Dashboard — Dark Navy Industrial Theme"""
import streamlit as st
import plotly.graph_objects as go

THEME = {
    "bg_primary":     "#0a1628",
    "bg_secondary":   "#0f2040",
    "bg_card":        "#0f2040",
    "bg_elevated":    "#162848",
    "border":         "#1e3a5f",
    "border_light":   "#243d5c",
    "text_primary":   "#e8edf5",
    "text_secondary": "#8aa3be",
    "text_muted":     "#4d6a85",
    "green":   "#00d4aa",
    "amber":   "#f59e0b",
    "red":     "#ef4444",
    "blue":    "#3b82f6",
    "purple":  "#a78bfa",
    "cyan":    "#06b6d4",
    "orange":  "#f97316",
    "asset_colors": {
        "P-101": "#00d4aa", "P-202": "#3b82f6",
        "C-201": "#f97316", "TK-105": "#a78bfa",
        "HX-401": "#f59e0b", "V-301": "#06b6d4",
    },
    "plotly_bg":    "#0f2040",
    "plotly_paper": "#0a1628",
    "grid_color":   "#1e3a5f",
    "axis_color":   "#4d6a85",
}

RISK_COLORS = {
    "Critical": "#ef4444",
    "High":     "#f97316",
    "Medium":   "#f59e0b",
    "Low":      "#00d4aa",
}

CRITICALITY_COLORS = RISK_COLORS.copy()

SEVERITY_COLORS = {
    "Critical":   "#ef4444",
    "Major":      "#f97316",
    "Minor":      "#f59e0b",
    "Negligible": "#00d4aa",
}

GLOBAL_CSS = """
<style>
.stApp{background-color:#0a1628}
[data-testid="stSidebar"]{background-color:#060e1e!important;border-right:1px solid #1e3a5f}
[data-testid="stSidebar"] *{color:#8aa3be!important}
[data-testid="stSidebar"] .stRadio label{color:#c8d8ea!important;font-size:13px!important}
[data-testid="stSidebar"] .stRadio label:hover{color:#00d4aa!important}
[data-testid="stMetric"]{background:linear-gradient(135deg,#0f2040,#162848);border:1px solid #1e3a5f;border-left:3px solid #00d4aa;border-radius:8px;padding:14px 18px}
[data-testid="stMetric"] label{color:#8aa3be!important;font-size:11px!important;text-transform:uppercase;letter-spacing:.08em}
[data-testid="stMetricValue"]{color:#e8edf5!important;font-size:24px!important;font-weight:700!important}
.stTabs [data-baseweb="tab"]{background-color:#0f2040;border:1px solid #1e3a5f;color:#8aa3be;border-radius:6px 6px 0 0}
.stTabs [aria-selected="true"]{background-color:#162848!important;color:#00d4aa!important;border-bottom:2px solid #00d4aa!important}
[data-testid="stForm"]{background-color:#0f2040;border:1px solid #1e3a5f;border-radius:10px;padding:20px}
.stButton>button{background:linear-gradient(135deg,#00d4aa,#0891b2);color:#0a1628;border:none;font-weight:700;border-radius:6px}
.stButton>button:hover{background:linear-gradient(135deg,#00b894,#0773a0);color:#fff}
hr{border-color:#1e3a5f}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:#0a1628}
::-webkit-scrollbar-thumb{background:#1e3a5f;border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#00d4aa}
</style>
"""

def inject_css():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

def page_header(title: str, subtitle: str = "", icon: str = ""):
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0f2040,#162848);border:1px solid #1e3a5f;
                border-left:4px solid #00d4aa;border-radius:10px;padding:18px 24px;margin-bottom:24px;">
        <div style="display:flex;align-items:center;gap:12px;">
            <span style="font-size:28px;">{icon}</span>
            <div>
                <h1 style="color:#e8edf5;font-size:22px;font-weight:800;margin:0;">{title}</h1>
                {"<p style='color:#8aa3be;font-size:13px;margin:4px 0 0;'>"+subtitle+"</p>" if subtitle else ""}
            </div>
        </div>
    </div>""", unsafe_allow_html=True)

def section_header(text: str):
    st.markdown(f"""
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:#00d4aa;
                border-bottom:1px solid #1e3a5f;padding-bottom:8px;margin-bottom:16px;
                margin-top:8px;font-weight:700;">{text}</div>""", unsafe_allow_html=True)

def alert_banner(message: str, level: str = "critical"):
    colors = {
        "critical": ("#ef4444", "#1a0808"),
        "warning":  ("#f59e0b", "#1a1200"),
        "info":     ("#3b82f6", "#080f1a"),
        "success":  ("#00d4aa", "#081a18"),
    }
    color, bg = colors.get(level, colors["info"])
    icons = {"critical": "🔴", "warning": "🟡", "info": "🔵", "success": "🟢"}
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {color};border-left:4px solid {color};
                border-radius:8px;padding:12px 18px;margin:8px 0;color:{color};
                font-size:13px;font-weight:600;">{icons.get(level,"")} {message}</div>
    """, unsafe_allow_html=True)

def apply_layout(fig: go.Figure, title: str = "", height: int = 340) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(color="#8aa3be", size=12), x=0),
        paper_bgcolor="#0a1628",
        plot_bgcolor="#0f2040",
        font=dict(color="#e8edf5", size=12),
        height=height,
        margin=dict(l=50, r=20, t=40 if title else 20, b=50),
        xaxis=dict(gridcolor="#1e3a5f", linecolor="#1e3a5f",
                   tickfont=dict(size=11, color="#4d6a85"), zeroline=False),
        yaxis=dict(gridcolor="#1e3a5f", linecolor="#1e3a5f",
                   tickfont=dict(size=11, color="#4d6a85"), zeroline=False),
        hoverlabel=dict(bgcolor="#162848", bordercolor="#1e3a5f",
                        font=dict(size=12, color="#e8edf5")),
        legend=dict(bgcolor="rgba(15,32,64,0.9)", bordercolor="#1e3a5f",
                    borderwidth=1, font=dict(size=11, color="#e8edf5")),
    )
    return fig
