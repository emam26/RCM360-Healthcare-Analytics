"""Reference-aligned Streamlit presentation styles."""

import streamlit as st


INDIGO_STYLES = """
<style>
:root {
  --rcm-nav: #231F38;
  --rcm-ink: #26243A;
  --rcm-muted: #646579;
  --rcm-line: #E5E3ED;
  --rcm-canvas: #F6F5FA;
  --rcm-indigo: #5145B8;
  --rcm-indigo-soft: #EFEDFC;
  --rcm-lavender: #8784B5;
  --rcm-red: #B74660;
  --rcm-amber: #DBA14A;
  --rcm-success: #167451;
  --rcm-radius: 14px;
  --rcm-shadow: 0 2px 6px #211A3D0D;
}
html, body, [class*="css"] { font-family: Inter, "Segoe UI", system-ui, sans-serif; }
.stApp { background: var(--rcm-canvas); color: var(--rcm-ink); }
[data-testid="stHeader"] { height: 0; background: transparent; }
[data-testid="stToolbar"], [data-testid="stStatusWidget"], [data-testid="stDecoration"] { display: none; }
section[data-testid="stSidebar"] {
  background: var(--rcm-nav);
  min-width: 244px !important;
  max-width: 244px !important;
  width: 244px !important;
  border-right: 0;
}
section[data-testid="stSidebar"] > div:first-child { background: var(--rcm-nav); }
[data-testid="stSidebarContent"] { padding: 25px 16px 20px; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: #B9B4D0; }
.st-key-rcm-brand { padding: 0 4px 25px; }
.st-key-rcm-brand [data-testid="stMarkdownContainer"] { color: #fff; }
.st-key-rcm-brand svg { width: 22px; height: 22px; }
.rcm-brand-mark {
  display: inline-grid; width: 42px; height: 42px; margin-right: 11px; vertical-align: middle;
  place-items: center; border-radius: 12px; background: #7061DF; color: #fff;
}
.rcm-brand-mark + div { display: inline-block; vertical-align: middle; }
.rcm-brand-mark + div strong { display: block; color: #fff; font-size: 17px; letter-spacing: -.35px; }
.rcm-brand-mark + div small { color: #B9B4D0; font-size: 10px; letter-spacing: .7px; text-transform: uppercase; }
.st-key-rcm-nav-title { padding: 0 10px; margin: 0 0 6px; }
.st-key-rcm-nav-title p {
  color: #AAA4C2 !important; font-size: 10px; font-weight: 700;
  letter-spacing: 1.1px; text-transform: uppercase;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] > label { display: none; }
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] { gap: 3px; }
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label {
  min-height: 44px; width: 100%; padding: 10px 12px; margin: 0;
  border-radius: 8px; color: #D4CFE5; font-size: 12px; font-weight: 600;
  transition: background .15s ease, color .15s ease;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:hover { background: #332D4D; color: #fff; }
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
  color: #fff; background: #3E355D; box-shadow: inset 3px 0 #B5A7FF;
}
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label > div:first-child { display: none; }
.st-key-rcm-sidebar-footer { margin-top: 30px; }
.st-key-rcm-sidebar-footer [data-testid="stMarkdownContainer"] { color: #C7C0D8; }
.st-key-rcm-sidebar-footer p { font-size: 11px; line-height: 1.55; }
.st-key-rcm-sidebar-footer strong { color: #F4F0FF; }
.rcm-side-note { padding: 13px 11px; border: 1px solid #4A425F; border-radius: 10px; background: #302941; color: #C7C0D8; font-size: 11px; line-height: 1.55; }
.rcm-side-note strong { color: #F4F0FF; }
[data-testid="stMainBlockContainer"] {
  max-width: 1700px; padding: 0 30px 32px;
}
.st-key-rcm-topbar {
  min-height: 65px; width: calc(100% + 60px); margin: 0 -30px 24px;
  padding: 0 30px; background: #fff; border-bottom: 1px solid var(--rcm-line);
  display: flex; align-items: center;
}
.st-key-rcm-topbar [data-testid="stHorizontalBlock"] { align-items: center; }
.st-key-rcm-topbar p { margin: 0; font-size: 12px; color: var(--rcm-muted); }
.st-key-rcm-topbar strong { color: var(--rcm-ink); font-weight: 600; }
.rcm-topbar-right { display: flex; justify-content: flex-end; align-items: center; gap: 12px; white-space: nowrap; }
.rcm-environment { padding: 6px 8px; border: 1px solid #DED8FA; border-radius: 6px; background: #F1EDFF; color: #4F419D; font-size: 10px; font-weight: 700; }
.rcm-avatar { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 50%; background: #EEEBFC; color: #5446A1; font-size: 10px; font-weight: 800; }
.st-key-rcm-heading { margin-bottom: 20px; }
.st-key-rcm-heading [data-testid="stHorizontalBlock"] { align-items: end; }
.st-key-rcm-heading h1 { font-size: 30px; letter-spacing: -1px; line-height: 1.2; margin: 0; }
.st-key-rcm-heading p { color: var(--rcm-muted); font-size: 12px; line-height: 1.5; margin-top: 6px; }
.rcm-eyebrow { color: var(--rcm-indigo); font-size: 10px; font-weight: 800; letter-spacing: 1.4px; text-transform: uppercase; margin-bottom: 5px; }
.stApp h3 { color: var(--rcm-ink); font-size: 14px; font-weight: 700; letter-spacing: -.2px; }
.stApp [data-testid="stCaptionContainer"] p { color: var(--rcm-muted); font-size: 11px; line-height: 1.5; }
.st-key-rcm-heading [data-testid="stCaptionContainer"] p { font-size: 12px; }
.st-key-rcm-heading [data-testid="stDownloadButton"] button,
.st-key-rcm-heading [data-testid="stButton"] button {
  min-height: 40px; border: 1px solid var(--rcm-indigo); border-radius: 7px;
  background: var(--rcm-indigo); color: #fff; font-size: 12px; font-weight: 600;
}
.st-key-rcm-heading [data-testid="stDownloadButton"] button:hover,
.st-key-rcm-heading [data-testid="stButton"] button:hover { background: #4034A1; color: #fff; }
.st-key-rcm-filters, .st-key-rcm-empty-filters {
  padding: 13px 15px; margin-bottom: 13px; border: 1px solid var(--rcm-line);
  border-radius: var(--rcm-radius); background: #fff; box-shadow: var(--rcm-shadow);
}
.st-key-rcm-filters [data-testid="stHorizontalBlock"], .st-key-rcm-empty-filters [data-testid="stHorizontalBlock"] { align-items: end; }
.st-key-rcm-filters [data-testid="stWidgetLabel"] p, .st-key-rcm-empty-filters [data-testid="stWidgetLabel"] p {
  color: var(--rcm-muted); font-size: 10px; font-weight: 700; margin-bottom: 3px;
}
.st-key-rcm-filters [data-baseweb="select"] > div,
.st-key-rcm-empty-filters [data-baseweb="select"] > div,
.st-key-rcm-filters [data-testid="stDateInput"] input,
.st-key-rcm-filters [data-testid="stButton"] button {
  min-height: 40px; border-radius: 7px; border-color: var(--rcm-line); font-size: 12px;
}
.st-key-rcm-filters [data-testid="stButton"] button { font-weight: 600; color: var(--rcm-muted); }
.st-key-rcm-count-row { min-height: 28px; margin-bottom: 8px; }
.st-key-rcm-count-row [data-testid="stMarkdownContainer"] p { color: var(--rcm-muted); font-size: 11px; }
.st-key-rcm-count-row strong { color: var(--rcm-ink); }
.st-key-rcm-kpis { margin-bottom: 15px; }
.st-key-rcm-kpis [data-testid="stHorizontalBlock"] { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.st-key-rcm-kpis [data-testid="column"] { width: auto !important; min-width: 0; }
.st-key-rcm-kpis [data-testid="stMarkdownContainer"] { padding: 0; }
.rcm-kpi-card {
  min-height: 119px; padding: 15px 15px 13px; border: 1px solid var(--rcm-line);
  border-radius: var(--rcm-radius); background: #fff; box-shadow: var(--rcm-shadow); overflow: hidden;
}
.rcm-kpi-top { display: flex; align-items: center; justify-content: space-between; gap: 5px; }
.rcm-kpi-label { color: var(--rcm-muted); font-size: 11px; font-weight: 600; line-height: 1.3; }
.rcm-kpi-icon { display: grid; width: 28px; height: 28px; flex: none; place-items: center; border-radius: 7px; background: #F0EEF8; color: #6258A4; }
.rcm-kpi-icon svg { width: 16px; height: 16px; }
.rcm-kpi-icon.indigo { background: var(--rcm-indigo-soft); color: var(--rcm-indigo); }
.rcm-kpi-icon.red { background: #FFF0F2; color: var(--rcm-red); }
.rcm-kpi-value { margin-top: 7px; color: var(--rcm-ink); font-size: 25px; font-weight: 700; letter-spacing: -.8px; line-height: 1.15; font-variant-numeric: tabular-nums; white-space: nowrap; }
.rcm-kpi-foot { display: -webkit-box; overflow: hidden; margin-top: 8px; color: var(--rcm-muted); font-size: 10px; line-height: 1.35; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.st-key-overview_status_paid button::before, .st-key-denial_status_paid button::before { content: "●"; margin-right: 7px; color: var(--rcm-indigo); }
.st-key-overview_status_denied button::before, .st-key-denial_status_denied button::before { content: "●"; margin-right: 7px; color: var(--rcm-red); }
.st-key-overview_status_pending button::before, .st-key-denial_status_pending button::before { content: "●"; margin-right: 7px; color: var(--rcm-amber); }
[data-testid="stVerticalBlockBorderWrapper"] > div {
  border-color: var(--rcm-line); border-radius: var(--rcm-radius); background: #fff; box-shadow: var(--rcm-shadow);
}
h2, h3 { color: var(--rcm-ink); font-size: 14px; letter-spacing: -.2px; }
[data-testid="stPlotlyChart"] { min-width: 0; }
[data-testid="stDataFrame"] { border: 1px solid var(--rcm-line); border-radius: 8px; }
[data-testid="stDataFrame"] canvas { font-size: 11px; }
[data-testid="stExpander"] { border-color: var(--rcm-line); border-radius: 8px; }
.st-key-rcm-table-controls [data-baseweb="select"],
.st-key-rcm-table-controls [data-testid="stTextInput"] input { font-size: 11px; }
.st-key-rcm-footer { padding: 8px 0 4px; }
.st-key-rcm-footer p { color: #747488; font-size: 10px; }
.st-key-rcm-empty-state { padding: 18px 16px; margin: 4px 0 14px; border: 1px solid #DED8F5; border-radius: 9px; background: #F2EFFF; }
.st-key-rcm-empty-state p { color: #4F419D; font-size: 12px; line-height: 1.55; }

@media (min-width: 901px) and (max-width: 1190px) {
  section[data-testid="stSidebar"] { min-width: 205px !important; max-width: 205px !important; width: 205px !important; }
  [data-testid="stMainBlockContainer"] { padding-left: 20px; padding-right: 20px; }
  .st-key-rcm-topbar { width: calc(100% + 40px); margin-left: -20px; margin-right: -20px; padding-left: 20px; padding-right: 20px; }
  .rcm-kpi-value { font-size: 21px; }
  .st-key-rcm-kpis [data-testid="stHorizontalBlock"] { gap: 8px; }
}
@media (max-width: 900px) {
  [data-testid="stAppViewContainer"] { display: flex; flex-direction: column; }
  section[data-testid="stSidebar"] {
    position: relative !important; inset: auto !important; z-index: 2;
    width: 100% !important; min-width: 100% !important; max-width: 100% !important;
    height: auto !important; transform: none !important; visibility: visible !important;
  }
  [data-testid="stSidebarContent"] { height: auto !important; min-height: 0; padding: 10px 14px; }
  .st-key-rcm-brand { padding: 0 4px 10px; }
  .st-key-rcm-nav-title, .st-key-rcm-sidebar-footer { display: none; }
  section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] { display: flex; flex-wrap: nowrap; overflow-x: auto; gap: 5px; }
  section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label { width: auto; min-width: max-content; min-height: 44px; padding: 10px 12px; }
  section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) { box-shadow: inset 0 -3px #B5A7FF; }
  [data-testid="stMainBlockContainer"] { padding-top: 0; }
  .st-key-rcm-topbar { min-height: 52px; margin-bottom: 19px; }
  .st-key-rcm-filters [data-testid="stHorizontalBlock"] { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .st-key-rcm-filters [data-testid="column"] { width: auto !important; }
  .st-key-rcm-kpis [data-testid="stHorizontalBlock"] { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .st-key-rcm-heading h1 { font-size: 25px; }
  .st-key-rcm-table-controls [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
}
@media (max-width: 520px) {
  [data-testid="stMainBlockContainer"] { padding-left: 12px; padding-right: 12px; padding-bottom: 24px; }
  .st-key-rcm-topbar { width: calc(100% + 24px); margin-left: -12px; margin-right: -12px; padding-left: 12px; padding-right: 12px; }
  .st-key-rcm-heading [data-testid="stHorizontalBlock"] { display: flex; flex-direction: column; align-items: stretch; gap: 10px; }
  .st-key-rcm-heading [data-testid="column"] { width: 100% !important; }
  .st-key-rcm-heading h1 { font-size: 24px; }
  .st-key-rcm-heading [data-testid="stDownloadButton"] button,
  .st-key-rcm-heading [data-testid="stButton"] button { width: 100%; }
  .st-key-rcm-topbar [data-testid="stHorizontalBlock"] { display: grid; grid-template-columns: minmax(0, 1fr) auto; }
  .st-key-rcm-topbar [data-testid="column"] { width: auto !important; }
  .st-key-rcm-table-controls [data-testid="stHorizontalBlock"] { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .st-key-rcm-table-controls [data-testid="column"] { width: auto !important; }
  .st-key-rcm-table-controls [data-testid="column"]:first-child { grid-column: 1 / -1; }
  .rcm-avatar { display: none; }
  .rcm-environment { padding: 5px 6px; font-size: 9px; }
  .st-key-rcm-filters, .st-key-rcm-empty-filters { padding: 10px; }
  .st-key-rcm-filters [data-testid="stHorizontalBlock"] { gap: 8px; }
  .st-key-rcm-kpis [data-testid="stHorizontalBlock"] { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .rcm-kpi-card { min-height: 110px; padding: 13px 11px; }
  .rcm-kpi-value { font-size: 23px; }
  .st-key-rcm-topbar p { font-size: 10px; }
}
</style>
"""


def apply_theme() -> None:
    """Apply the indigo dashboard system without replacing Streamlit widgets."""
    st.markdown(INDIGO_STYLES, unsafe_allow_html=True)
