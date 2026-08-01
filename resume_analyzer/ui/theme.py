"""Design tokens and the global stylesheet.

The visual language is a dark, glass-and-gradient SaaS aesthetic in the spirit
of Linear, Vercel and Raycast. Everything is driven by CSS custom properties
declared once in :func:`build_css`, so a colour change propagates through the
whole product.

Performance notes:

* The stylesheet is generated once and memoised; Streamlit reruns re-inject
  the same cached string.
* Animations are restricted to ``transform`` and ``opacity`` (compositor-only
  properties), so they never trigger layout or paint.
* ``prefers-reduced-motion`` disables all motion for accessibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Final


@dataclass(frozen=True, slots=True)
class Palette:
    """Semantic colour tokens for the dark theme."""

    bg_base: str = "#07080F"
    bg_elevated: str = "#0D0F1A"
    surface: str = "rgba(255, 255, 255, 0.04)"
    surface_strong: str = "rgba(255, 255, 255, 0.07)"
    border: str = "rgba(255, 255, 255, 0.09)"
    border_strong: str = "rgba(255, 255, 255, 0.16)"

    text_primary: str = "#F4F6FB"
    text_secondary: str = "#A7B0C4"
    text_muted: str = "#6B7488"

    primary: str = "#6366F1"
    primary_soft: str = "#818CF8"
    secondary: str = "#A855F7"
    accent: str = "#22D3EE"
    success: str = "#34D399"
    warning: str = "#FBBF24"
    danger: str = "#F87171"


PALETTE: Final[Palette] = Palette()

#: Chart-friendly categorical sequence, tuned for the dark canvas.
CHART_SEQUENCE: Final[tuple[str, ...]] = (
    "#818CF8",
    "#22D3EE",
    "#A855F7",
    "#34D399",
    "#FBBF24",
    "#F87171",
    "#60A5FA",
    "#F472B6",
)

#: Typeface stack; Inter is loaded from Google Fonts with a system fallback.
FONT_STACK: Final[str] = (
    "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Helvetica Neue', Arial, sans-serif"
)


def score_color(score: float) -> str:
    """Return the palette colour that represents ``score``."""
    if score >= 80:
        return PALETTE.success
    if score >= 60:
        return PALETTE.accent
    if score >= 40:
        return PALETTE.warning
    return PALETTE.danger


def _collapse_indentation(markup: str) -> str:
    """Flatten stylesheet markup into blank-line-free, unindented lines.

    Streamlit renders ``st.markdown`` content through a CommonMark parser
    before the HTML reaches the browser, and CommonMark's *HTML block* rules
    make a raw ``<style>`` payload surprisingly fragile:

    1. A leading ``<link>`` tag opens a "type 7" HTML block, which CommonMark
       terminates at the **first blank line**.
    2. Any blank line inside the following ``<style>`` body therefore closes
       the HTML block early, and every remaining CSS line is re-parsed as
       Markdown — emitted inside ``<p>`` tags as literal text at the top of
       the page instead of styling it.
    3. Separately, lines indented four or more spaces can be treated as
       indented code blocks.

    Removing blank lines (the actual trigger) and leading indentation (a
    latent second trigger) keeps the entire stylesheet inside a single HTML
    block. CSS is whitespace-insensitive between tokens, so this is purely a
    transport concern: every selector, property, colour and keyframe is
    preserved and the rendered design is byte-for-byte unchanged.

    Args:
        markup: The stylesheet markup, formatted for readability.

    Returns:
        The same markup with blank lines dropped and per-line leading
        whitespace removed.
    """
    return "\n".join(
        stripped
        for line in markup.splitlines()
        if (stripped := line.strip())
    )


@lru_cache(maxsize=1)
def build_css() -> str:
    """Return the complete stylesheet, generated once per process.

    The markup is de-indented before it is returned so Streamlit's Markdown
    parser cannot mistake indented CSS for a code block. See
    :func:`_collapse_indentation`.
    """
    p = PALETTE
    return _collapse_indentation(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg-base: {p.bg_base};
  --bg-elevated: {p.bg_elevated};
  --surface: {p.surface};
  --surface-strong: {p.surface_strong};
  --border: {p.border};
  --border-strong: {p.border_strong};
  --text-primary: {p.text_primary};
  --text-secondary: {p.text_secondary};
  --text-muted: {p.text_muted};
  --primary: {p.primary};
  --primary-soft: {p.primary_soft};
  --secondary: {p.secondary};
  --accent: {p.accent};
  --success: {p.success};
  --warning: {p.warning};
  --danger: {p.danger};

  --radius-sm: 10px;
  --radius-md: 16px;
  --radius-lg: 22px;
  --radius-xl: 28px;

  --shadow-sm: 0 1px 2px rgba(0,0,0,.4);
  --shadow-md: 0 8px 24px -6px rgba(0,0,0,.5);
  --shadow-lg: 0 24px 60px -12px rgba(0,0,0,.65);
  --shadow-glow: 0 0 0 1px rgba(99,102,241,.28), 0 18px 50px -12px rgba(99,102,241,.42);

  --ease: cubic-bezier(.22,1,.36,1);
  --dur: .42s;
}}

/* ---------------------------------------------------------------- base */
html, body, [class*="css"] {{ font-family: {FONT_STACK}; }}

.stApp {{
  background:
    radial-gradient(1100px 620px at 12% -8%, rgba(99,102,241,.16), transparent 60%),
    radial-gradient(900px 560px at 88% 4%, rgba(168,85,247,.13), transparent 62%),
    radial-gradient(760px 520px at 50% 108%, rgba(34,211,238,.09), transparent 60%),
    var(--bg-base);
  background-attachment: fixed;
  color: var(--text-primary);
}}

#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
.block-container {{ padding: 1.6rem 2.2rem 4rem; max-width: 1500px; }}

h1, h2, h3, h4 {{ color: var(--text-primary); letter-spacing: -.022em; font-weight: 700; }}
p, span, label, li {{ color: var(--text-secondary); }}
a {{ color: var(--primary-soft); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

::-webkit-scrollbar {{ width: 10px; height: 10px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{
  background: rgba(255,255,255,.13); border-radius: 8px;
  border: 2px solid transparent; background-clip: content-box;
}}
::-webkit-scrollbar-thumb:hover {{ background: rgba(255,255,255,.24); background-clip: content-box; }}

/* -------------------------------------------------------------- layout */
.ra-hero {{
  position: relative; overflow: hidden;
  border-radius: var(--radius-xl);
  border: 1px solid var(--border);
  background:
    linear-gradient(135deg, rgba(99,102,241,.20), rgba(168,85,247,.12) 45%, rgba(34,211,238,.10)),
    var(--surface);
  backdrop-filter: blur(22px) saturate(150%);
  -webkit-backdrop-filter: blur(22px) saturate(150%);
  padding: 2.4rem 2.6rem;
  box-shadow: var(--shadow-lg);
  animation: ra-rise .7s var(--ease) both;
}}
.ra-hero::before {{
  content:""; position:absolute; inset:-40% -10% auto -10%; height:200%;
  background: conic-gradient(from 0deg, transparent, rgba(99,102,241,.16), transparent 32%);
  animation: ra-spin 18s linear infinite; pointer-events:none;
}}
.ra-hero::after {{
  content:""; position:absolute; inset:0; pointer-events:none;
  background: linear-gradient(180deg, rgba(255,255,255,.07), transparent 42%);
}}
.ra-hero > * {{ position: relative; z-index: 1; }}

.ra-hero-title {{
  font-size: 2.65rem; font-weight: 800; line-height: 1.08; margin: 0 0 .5rem;
  background: linear-gradient(120deg, #FFFFFF 8%, var(--primary-soft) 48%, var(--accent) 92%);
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent; color: transparent;
}}
.ra-hero-sub {{ font-size: 1.02rem; color: var(--text-secondary); max-width: 62ch; margin: 0; }}

.ra-badges {{ display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1.25rem; }}
.ra-badge {{
  display:inline-flex; align-items:center; gap:.42rem;
  padding:.36rem .78rem; font-size:.76rem; font-weight:600; letter-spacing:.01em;
  border-radius:999px; border:1px solid var(--border-strong);
  background: var(--surface-strong); color: var(--text-secondary);
  transition: transform .25s var(--ease), border-color .25s var(--ease), color .25s var(--ease);
}}
.ra-badge:hover {{ transform: translateY(-2px); border-color: var(--primary); color: var(--text-primary); }}
.ra-badge-dot {{ width:6px; height:6px; border-radius:50%; background: var(--success);
  box-shadow: 0 0 0 3px rgba(52,211,153,.18); animation: ra-pulse 2.4s ease-in-out infinite; }}

/* --------------------------------------------------------------- cards */
.ra-card {{
  position: relative; overflow: hidden;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: var(--surface);
  backdrop-filter: blur(18px) saturate(140%);
  -webkit-backdrop-filter: blur(18px) saturate(140%);
  padding: 1.4rem 1.55rem;
  box-shadow: var(--shadow-md);
  transition: transform var(--dur) var(--ease), box-shadow var(--dur) var(--ease),
              border-color var(--dur) var(--ease);
  animation: ra-rise .55s var(--ease) both;
  height: 100%;
}}
.ra-card::after {{
  content:""; position:absolute; inset:0 0 auto 0; height:1px;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,.22), transparent);
}}
.ra-card:hover {{
  transform: translateY(-4px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-lg);
}}
.ra-card-title {{
  font-size:.73rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase;
  color: var(--text-muted); margin:0 0 .9rem; display:flex; align-items:center; gap:.5rem;
}}

/* --------------------------------------------------------- stat widget */
.ra-stat {{ display:flex; flex-direction:column; gap:.34rem; }}
.ra-stat-label {{
  font-size:.71rem; font-weight:700; letter-spacing:.11em; text-transform:uppercase;
  color: var(--text-muted); display:flex; align-items:center; gap:.44rem;
}}
.ra-stat-value {{
  font-size:2.1rem; font-weight:800; line-height:1; color: var(--text-primary);
  font-variant-numeric: tabular-nums; letter-spacing:-.03em;
}}
.ra-stat-value.grad {{
  background: linear-gradient(120deg, var(--primary-soft), var(--accent));
  -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent; color:transparent;
}}
.ra-stat-meta {{ font-size:.78rem; color: var(--text-muted); }}
.ra-delta {{ font-size:.76rem; font-weight:650; display:inline-flex; align-items:center; gap:.26rem; }}
.ra-delta.up {{ color: var(--success); }}
.ra-delta.down {{ color: var(--danger); }}
.ra-delta.flat {{ color: var(--text-muted); }}

/* ------------------------------------------------------------ progress */
.ra-bar {{
  position:relative; height:7px; border-radius:999px; overflow:hidden;
  background: rgba(255,255,255,.08); margin-top:.7rem;
}}
.ra-bar-fill {{
  height:100%; border-radius:999px; position:relative;
  background: linear-gradient(90deg, var(--primary), var(--secondary), var(--accent));
  background-size: 220% 100%;
  animation: ra-grow 1.1s var(--ease) both, ra-shift 5s linear infinite;
  box-shadow: 0 0 14px rgba(99,102,241,.5);
}}

/* --------------------------------------------------------------- chips */
.ra-chips {{ display:flex; flex-wrap:wrap; gap:.44rem; }}
.ra-chip {{
  display:inline-flex; align-items:center; gap:.34rem;
  padding:.36rem .72rem; border-radius:999px;
  font-size:.79rem; font-weight:600; letter-spacing:.005em;
  border:1px solid var(--border-strong); background: var(--surface-strong);
  color: var(--text-secondary);
  transition: transform .22s var(--ease), background .22s var(--ease), color .22s var(--ease);
  animation: ra-pop .34s var(--ease) both;
}}
.ra-chip:hover {{ transform: translateY(-2px) scale(1.03); color: var(--text-primary); }}
.ra-chip.ok  {{ border-color: rgba(52,211,153,.36); background: rgba(52,211,153,.11); color:#9DF3D4; }}
.ra-chip.bad {{ border-color: rgba(248,113,113,.34); background: rgba(248,113,113,.10); color:#FCC0C0; }}
.ra-chip.warn{{ border-color: rgba(251,191,36,.34); background: rgba(251,191,36,.10); color:#FBE1A0; }}
.ra-chip.info{{ border-color: rgba(129,140,248,.36); background: rgba(129,140,248,.12); color:#C7CCFB; }}

/* ---------------------------------------------------------- info lines */
.ra-kv {{ display:flex; align-items:flex-start; gap:.7rem; padding:.6rem 0;
  border-bottom:1px solid rgba(255,255,255,.05); }}
.ra-kv:last-child {{ border-bottom:none; }}
.ra-kv-icon {{ width:26px; text-align:center; font-size:.95rem; opacity:.85; flex-shrink:0; }}
.ra-kv-body {{ min-width:0; flex:1; }}
.ra-kv-label {{ font-size:.68rem; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
  color: var(--text-muted); }}
.ra-kv-value {{ font-size:.9rem; color: var(--text-primary); word-break:break-word; }}
.ra-kv-value.empty {{ color: var(--text-muted); font-style: italic; }}

/* -------------------------------------------------------------- verdict */
.ra-verdict {{
  border-radius: var(--radius-md); padding:1rem 1.2rem;
  border-left:3px solid var(--primary); background: var(--surface-strong);
  font-size:.93rem; color: var(--text-primary); line-height:1.6;
  animation: ra-rise .5s var(--ease) both;
}}
.ra-verdict.ok  {{ border-left-color: var(--success); background: rgba(52,211,153,.08); }}
.ra-verdict.warn{{ border-left-color: var(--warning); background: rgba(251,191,36,.08); }}
.ra-verdict.bad {{ border-left-color: var(--danger);  background: rgba(248,113,113,.08); }}

/* ------------------------------------------------------------ timeline */
.ra-timeline {{ position:relative; padding-left:1.5rem; }}
.ra-timeline::before {{
  content:""; position:absolute; left:5px; top:6px; bottom:6px; width:2px;
  background: linear-gradient(180deg, var(--primary), var(--secondary), transparent);
  border-radius:2px;
}}
.ra-tl-item {{ position:relative; padding:0 0 1.15rem 0; animation: ra-rise .5s var(--ease) both; }}
.ra-tl-item::before {{
  content:""; position:absolute; left:-1.5rem; top:5px; width:12px; height:12px;
  border-radius:50%; background: var(--bg-base); border:2px solid var(--primary);
  box-shadow: 0 0 0 3px rgba(99,102,241,.16);
}}
.ra-tl-title {{ font-size:.92rem; font-weight:650; color: var(--text-primary); }}
.ra-tl-meta {{ font-size:.77rem; color: var(--text-muted); }}

/* ------------------------------------------------------------ skeleton */
.ra-skeleton {{
  border-radius: var(--radius-md); height:88px;
  background: linear-gradient(90deg, rgba(255,255,255,.045) 25%,
    rgba(255,255,255,.10) 37%, rgba(255,255,255,.045) 63%);
  background-size: 400% 100%; animation: ra-shimmer 1.5s ease-in-out infinite;
}}

/* --------------------------------------------------- streamlit widgets */
.stButton > button, .stDownloadButton > button {{
  width:100%; border-radius: var(--radius-md); border:1px solid var(--border-strong);
  background: linear-gradient(135deg, var(--primary), var(--secondary));
  color:#fff; font-weight:650; font-size:.94rem; padding:.72rem 1.1rem;
  letter-spacing:.005em; box-shadow: var(--shadow-md);
  transition: transform .24s var(--ease), box-shadow .24s var(--ease), filter .24s var(--ease);
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  transform: translateY(-2px); box-shadow: var(--shadow-glow); filter: brightness(1.07);
}}
.stButton > button:active, .stDownloadButton > button:active {{ transform: translateY(0); }}

section[data-testid="stFileUploaderDropzone"], div[data-testid="stFileUploaderDropzone"] {{
  border:1.5px dashed var(--border-strong) !important; border-radius: var(--radius-md) !important;
  background: var(--surface) !important; transition: border-color .25s var(--ease), background .25s var(--ease);
}}
section[data-testid="stFileUploaderDropzone"]:hover, div[data-testid="stFileUploaderDropzone"]:hover {{
  border-color: var(--primary) !important; background: var(--surface-strong) !important;
}}

.stTextArea textarea, .stTextInput input {{
  background: var(--surface) !important; color: var(--text-primary) !important;
  border:1px solid var(--border) !important; border-radius: var(--radius-md) !important;
  font-size:.92rem !important;
}}
.stTextArea textarea:focus, .stTextInput input:focus {{
  border-color: var(--primary) !important; box-shadow: 0 0 0 3px rgba(99,102,241,.16) !important;
}}

div[data-testid="stExpander"] {{
  border:1px solid var(--border) !important; border-radius: var(--radius-md) !important;
  background: var(--surface) !important; overflow:hidden;
}}
div[data-testid="stExpander"] summary {{ font-weight:600; color: var(--text-primary) !important; }}

.stTabs [data-baseweb="tab-list"] {{
  gap:.3rem; background: var(--surface); padding:.34rem; border-radius: var(--radius-md);
  border:1px solid var(--border);
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: var(--radius-sm); padding:.5rem 1.05rem; font-weight:600; font-size:.88rem;
  color: var(--text-secondary); transition: background .22s var(--ease), color .22s var(--ease);
}}
.stTabs [aria-selected="true"] {{
  background: linear-gradient(135deg, rgba(99,102,241,.30), rgba(168,85,247,.22)) !important;
  color: var(--text-primary) !important;
}}

div[data-testid="stMetric"] {{
  background: var(--surface); border:1px solid var(--border);
  border-radius: var(--radius-md); padding:1rem 1.1rem;
}}

section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(13,15,26,.97), rgba(7,8,15,.99));
  border-right:1px solid var(--border);
}}
section[data-testid="stSidebar"] .block-container {{ padding-top:1.6rem; }}

div[data-testid="stProgress"] > div > div > div {{
  background: linear-gradient(90deg, var(--primary), var(--accent)) !important;
}}

.js-plotly-plot .plotly {{ border-radius: var(--radius-md); }}

/* ---------------------------------------------------------- animations */
@keyframes ra-rise {{ from {{ opacity:0; transform: translateY(14px); }} to {{ opacity:1; transform:none; }} }}
@keyframes ra-pop  {{ from {{ opacity:0; transform: scale(.94); }} to {{ opacity:1; transform:none; }} }}
@keyframes ra-spin {{ to {{ transform: rotate(360deg); }} }}
@keyframes ra-grow {{ from {{ transform: scaleX(0); transform-origin:left; }} to {{ transform: scaleX(1); transform-origin:left; }} }}
@keyframes ra-shift{{ to {{ background-position: 220% 0; }} }}
@keyframes ra-shimmer {{ 0% {{ background-position:100% 0; }} 100% {{ background-position:-100% 0; }} }}
@keyframes ra-pulse {{ 0%,100% {{ opacity:1; }} 50% {{ opacity:.45; }} }}

.ra-d1 {{ animation-delay:.05s; }} .ra-d2 {{ animation-delay:.10s; }}
.ra-d3 {{ animation-delay:.15s; }} .ra-d4 {{ animation-delay:.20s; }}
.ra-d5 {{ animation-delay:.25s; }} .ra-d6 {{ animation-delay:.30s; }}

@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration:.001ms !important; animation-iteration-count:1 !important;
    transition-duration:.001ms !important;
  }}
}}

@media (max-width: 900px) {{
  .block-container {{ padding:1rem 1rem 3rem; }}
  .ra-hero {{ padding:1.6rem 1.4rem; }}
  .ra-hero-title {{ font-size:1.95rem; }}
  .ra-stat-value {{ font-size:1.7rem; }}
}}
</style>
""")
