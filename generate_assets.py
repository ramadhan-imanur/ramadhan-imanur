import datetime
import html
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

USERNAME = "ramadhan-imanur"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# GitHub API Headers & Auth
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
API_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/vnd.github.v3+json",
}
if GITHUB_TOKEN:
    API_HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"


def fetch_json(url, timeout=10):
    req = urllib.request.Request(url, headers=API_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Warning: Failed to fetch {url}: {e}")
        return None


# 1. Fetch User Stats (Repos, Followers, Account Creation)
print(f"Fetching GitHub profile stats for {USERNAME}...")
user_data = fetch_json(f"https://api.github.com/users/{USERNAME}") or {}
total_repos = user_data.get("public_repos", 13)
total_followers = user_data.get("followers", 3)
created_at = user_data.get("created_at", "2021-11-18T01:59:00Z")

try:
    created_dt = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    years_active = max(1, round((datetime.datetime.now(datetime.timezone.utc) - created_dt).days / 365.25))
except Exception:
    years_active = 5

print(f"  -> Total Repos: {total_repos}+ | Followers: {total_followers}+ | Years Active: {years_active}")

# 2. Fetch Contributions Data for Annual Commits
print("Fetching contributions data from GitHub...")
total_commits = "248"
contrib_url = f"https://github.com/users/{USERNAME}/contributions"
html_data = ""
try:
    req = urllib.request.Request(contrib_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html_data = resp.read().decode("utf-8")

    match = re.search(r"([0-9,]+)\s+contributions?\s+in\s+the\s+last\s+year", html_data, re.IGNORECASE)
    if match:
        total_commits = match.group(1).replace(",", "")
    else:
        class CalParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.total = ""
                self.in_h2 = False
                self.h2_text = ""

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                if tag == "h2" and "js-contribution-activity-description" in attrs_dict.get("id", ""):
                    self.in_h2 = True

            def handle_endtag(self, tag):
                if tag == "h2" and self.in_h2:
                    self.in_h2 = False
                    cleaned = " ".join(self.h2_text.split())
                    if "contributions" in cleaned:
                        parts = cleaned.replace("contributions", "").split()
                        self.total = parts[0]

            def handle_data(self, data):
                if self.in_h2:
                    self.h2_text += data

        p = CalParser()
        p.feed(html_data)
        if p.total:
            total_commits = p.total
except Exception as e:
    print(f"Warning: Failed to scrape contributions: {e}. Using fallback {total_commits}.")

print(f"  -> Annual Commits: {total_commits}+")

# 3. Calculate Source Lines of Code (SLOC)
print("Calculating Source Lines of Code (SLOC)...")
SLOC_CACHE_FILE = ASSETS_DIR / ".sloc_cache.json"

IGNORE_DIRS = {"build", "dist", "public", "out", "vendor", "node_modules", ".git", ".github"}

EXT_MAP = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".ts": "TypeScript",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
    ".tex": "LaTeX",
    ".sh": "Shell",
    ".bash": "Shell",
    ".nb": "Mathematica",
    ".wl": "Mathematica",
}


def count_lines(filepath):
    cnt = 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip():
                    cnt += 1
    except Exception:
        pass
    return cnt


def count_ipynb(filepath):
    cnt = 0
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            nb = json.load(f)
            for cell in nb.get("cells", []):
                if cell.get("cell_type") == "code":
                    source = cell.get("source", [])
                    if isinstance(source, str):
                        lines = [l for l in source.split("\n") if l.strip()]
                    else:
                        lines = [l.strip() for l in source if l.strip()]
                    cnt += len(lines)
    except Exception:
        pass
    return cnt


def scan_directory(dir_path):
    counts = {}
    for path in Path(dir_path).rglob("*"):
        if not path.is_file():
            continue
        if any(ignored in path.parts for ignored in IGNORE_DIRS):
            continue
        if path.name.endswith(".min.js") or path.name.endswith(".min.css"):
            continue
        ext = path.suffix.lower()
        if ext == ".ipynb":
            c = count_ipynb(path)
            if c > 0:
                counts["Python"] = counts.get("Python", 0) + c
        elif ext in EXT_MAP:
            lang = EXT_MAP[ext]
            c = count_lines(path)
            if c > 0:
                counts[lang] = counts.get(lang, 0) + c
    return counts


DEFAULT_REPOS = [
    "absorbing-markov-chain-covid19-indonesia",
    "analisis-makroekonomi-m2-ihsg",
    "california-housing-ale-xai",
    "HospitalDB-ManagementSystem",
    "markov-chain-ihsg",
    "naive-bayes-probabilistic-classification",
    "ramadhan-imanur",
    "rice-quality-sni",
    "sarima-sampah-randukuning",
    "seattle-911-poisson-process",
    "time-series-wisman-soetta",
    "Titanic_Survival_Prediction",
    "tree-search-demo",
]

repos_data = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner") or []
repo_names = [r["name"] for r in repos_data if not r.get("fork")]
if not repo_names:
    repo_names = DEFAULT_REPOS


def clone_repo(name, dest_dir):
    url = f"https://github.com/{USERNAME}/{name}.git"
    target = Path(dest_dir) / name
    subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, str(target)], check=False)


lang_totals = {}
try:
    print(f"  -> Scanning {len(repo_names)} repositories for real code changes...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        with ThreadPoolExecutor(max_workers=5) as ex:
            ex.map(lambda r: clone_repo(r, tmp_dir), repo_names)

        lang_totals = scan_directory(tmp_dir)
        if lang_totals:
            with open(SLOC_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(lang_totals, f, indent=2)
except Exception as e:
    print(f"Note: Error during live repo scan: {e}")

if not lang_totals and SLOC_CACHE_FILE.exists():
    try:
        with open(SLOC_CACHE_FILE, "r", encoding="utf-8") as f:
            lang_totals = json.load(f)
    except Exception:
        pass

if not lang_totals:
    lang_totals = {
        "Python": 10636,
        "Mathematica": 5318,
        "SQL": 3190,
        "Shell": 2127,
    }

total_lines = sum(lang_totals.values())
sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)
top_5 = sorted_langs[:5]

LANGUAGE_COLORS = {
    "Python": "#39D353",       # GitHub neon green
    "Mathematica": "#238636",  # Dark green
    "SQL": "#58A6FF",          # Syntax blue
    "Shell": "#BC8CFF",        # Syntax purple
    "JavaScript": "#F1E05A",
    "TypeScript": "#3178C6",
    "CSS": "#563D7C",
    "HTML": "#E34C26",
    "LaTeX": "#3D6117",
}

formatted_langs = []
for name, line_count in top_5:
    pct = (line_count / total_lines) * 100.0 if total_lines > 0 else 0
    color = LANGUAGE_COLORS.get(name, "#39D353")
    formatted_langs.append((name, pct, color))

print(f"  -> Total Source Lines of Code: {total_lines:,} lines")
print("  -> Top Languages (by Source Lines of Code):")
for name, pct, _ in formatted_langs:
    cnt = lang_totals.get(name, 0)
    print(f"     - {name:12}: {pct:5.2f}% ({cnt:,} lines)")


user_stats = {
    "total_repos": total_repos,
    "total_commits": total_commits,
    "total_followers": total_followers,
    "years_active": years_active,
}


# ==========================================
# 1. Cosmic Math Welcome Banner (Stitch Design Update)
# ==========================================
def build_welcome_banner_svg(theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#0D1117" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    title_color = "#F0F6FC" if is_dark else "#1F2328"
    accent_green = "#39D353" if is_dark else "#1A7F37"
    accent_blue = "#58A6FF" if is_dark else "#0969DA"
    accent_purple = "#BC8CFF" if is_dark else "#8250DF"
    subtext_color = "#8B949E" if is_dark else "#656D76"
    badge_bg = "#21262D" if is_dark else "#F6F8FA"
    badge_border = "#30363D" if is_dark else "#D0D7DE"
    badge_text = "#C9D1D9" if is_dark else "#24292F"

    return f"""<svg width="800" height="215" viewBox="0 0 800 215" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 12px; }}
      @keyframes subtle-dot-pulse {{
        0%, 100% {{ transform: scale(1); opacity: 0.85; }}
        50% {{ transform: scale(1.3); opacity: 1; }}
      }}
      @keyframes subtle-twinkle {{
        0%, 100% {{ opacity: 0.25; transform: scale(0.85); }}
        50% {{ transform: scale(0.95); opacity: 1.2; }}
      }}
      @keyframes soft-pulse-star {{
        0%, 100% {{ opacity: 0.3; transform: rotate(0deg) scale(0.9); }}
        50% {{ opacity: 1; transform: rotate(45deg) scale(1.15); }}
      }}
      .status-dot-pulse {{ animation: subtle-dot-pulse 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite; transform-origin: center; }}
      .star-twinkle-slow {{ animation: subtle-twinkle 4s ease-in-out infinite; transform-origin: center; }}
      .star-twinkle-mid {{ animation: subtle-twinkle 2.8s ease-in-out infinite; transform-origin: center; }}
      .star-twinkle-fast {{ animation: subtle-twinkle 2s ease-in-out infinite; transform-origin: center; }}
      .star-sparkle {{ animation: soft-pulse-star 5s ease-in-out infinite; }}

      .headline {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Newsreader', Georgia, serif; font-size: 26px; font-weight: 600; letter-spacing: -0.02em; fill: {title_color}; }}
      .headline-italic {{ font-family: 'Newsreader', Georgia, serif; font-style: italic; fill: {accent_green}; font-weight: 500; }}
      .mono-sub {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 13px; fill: {subtext_color}; }}
      .mono-pill {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 11px; font-weight: 500; fill: {badge_text}; }}
      .math-symbol {{ font-family: 'JetBrains Mono', 'Newsreader', serif; font-style: italic; user-select: none; pointer-events: none; }}

      .mobile-layout {{ display: none; }}
      .desktop-layout {{ display: inline; }}

      @media (max-width: 650px) {{
        .desktop-layout {{ display: none; }}
        .mobile-layout {{ display: inline; }}
      }}
      @media (prefers-reduced-motion: reduce) {{
        .status-dot-pulse, .star-twinkle-slow, .star-twinkle-mid, .star-twinkle-fast, .star-sparkle {{
          animation: none !important;
        }}
      }}
    </style>

    <radialGradient id="star-green-glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{accent_green}" stop-opacity="0.8" />
      <stop offset="100%" stop-color="{accent_green}" stop-opacity="0" />
    </radialGradient>
    <radialGradient id="star-cyan-glow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="{accent_blue}" stop-opacity="0.8" />
      <stop offset="100%" stop-color="{accent_blue}" stop-opacity="0" />
    </radialGradient>

    <!-- 3 Nebula Ambient Glows -->
    <radialGradient id="ambient-green-corner" cx="75%" cy="20%" r="60%">
      <stop offset="0%" stop-color="{accent_green}" stop-opacity="{'0.13' if is_dark else '0.06'}" />
      <stop offset="100%" stop-color="{accent_green}" stop-opacity="0" />
    </radialGradient>
    <radialGradient id="ambient-cyan-center" cx="45%" cy="80%" r="55%">
      <stop offset="0%" stop-color="{accent_blue}" stop-opacity="{'0.10' if is_dark else '0.05'}" />
      <stop offset="100%" stop-color="{accent_blue}" stop-opacity="0" />
    </radialGradient>
    <radialGradient id="ambient-purple-edge" cx="95%" cy="90%" r="50%">
      <stop offset="0%" stop-color="{accent_purple}" stop-opacity="{'0.09' if is_dark else '0.04'}" />
      <stop offset="100%" stop-color="{accent_purple}" stop-opacity="0" />
    </radialGradient>
  </defs>

  <!-- Outer Card Background & Nebulas -->
  <rect x="1" y="1" width="798" height="213" rx="12" class="card-bg" />
  <rect x="1" y="1" width="798" height="213" rx="12" fill="url(#ambient-green-corner)" />
  <rect x="1" y="1" width="798" height="213" rx="12" fill="url(#ambient-cyan-center)" />
  <rect x="1" y="1" width="798" height="213" rx="12" fill="url(#ambient-purple-edge)" />

  <!-- Twinkling Starfield -->
  <circle cx="34" cy="48" r="1.2" fill="{title_color}" class="star-twinkle-slow" />
  <circle cx="112" cy="28" r="1.4" fill="{accent_green}" class="star-twinkle-mid" />
  <circle cx="185" cy="82" r="1.0" fill="{title_color}" class="star-twinkle-fast" />
  <circle cx="420" cy="35" r="1.3" fill="{accent_blue}" class="star-twinkle-slow" />
  <circle cx="492" cy="110" r="1.0" fill="{title_color}" class="star-twinkle-mid" />
  <circle cx="738" cy="46" r="1.3" fill="{title_color}" class="star-twinkle-fast" />
  <circle cx="762" cy="160" r="1.2" fill="{accent_green}" class="star-twinkle-mid" />
  <circle cx="38" cy="175" r="1.1" fill="{accent_blue}" class="star-twinkle-slow" />
  <circle cx="410" cy="180" r="1.2" fill="{title_color}" class="star-twinkle-fast" />

  <!-- 4-Point Diamond Sparkles -->
  <g transform="translate(710, 52)" class="star-sparkle" style="transform-origin: 710px 52px;">
    <path d="M0 -4.5 Q0 0 4.5 0 Q0 0 0 4.5 Q0 0 -4.5 0 Q0 0 0 -4.5 Z" fill="{accent_green}" />
    <circle cx="0" cy="0" r="5" fill="url(#star-green-glow)" />
  </g>
  <g transform="translate(640, 145)" class="star-sparkle" style="transform-origin: 640px 145px; animation-delay: 1.5s;">
    <path d="M0 -4 Q0 0 4 0 Q0 0 0 4 Q0 0 -4 0 Q0 0 0 -4 Z" fill="{accent_blue}" />
    <circle cx="0" cy="0" r="4.5" fill="url(#star-cyan-glow)" />
  </g>
  <g transform="translate(36, 125)" class="star-sparkle" style="transform-origin: 36px 125px; animation-delay: 2.2s;">
    <path d="M0 -3.5 Q0 0 3.5 0 Q0 0 0 3.5 Q0 0 -3.5 0 Q0 0 0 -3.5 Z" fill="{title_color}" opacity="0.8" />
  </g>

  <!-- Mathematical Geometry & Parametric Curves -->
  <g opacity="{'0.22' if is_dark else '0.15'}" stroke="{accent_green}" stroke-width="0.9" fill="none">
    <path d="M 420 180 Q 540 130 630 180 T 790 180" stroke-dasharray="3 3" />
    <path d="M 460 70 C 550 20, 640 120, 740 60" stroke="{accent_blue}" stroke-dasharray="2 4" />
  </g>

  <!-- Coordinate Axis Crosshairs -->
  <g opacity="{'0.22' if is_dark else '0.15'}" stroke="{subtext_color}" stroke-width="0.8">
    <line x1="740" y1="95" x2="770" y2="95" />
    <line x1="755" y1="80" x2="755" y2="110" />
    <circle cx="755" cy="95" r="2.5" fill="none" stroke="{accent_green}" />
  </g>

  <!-- Advanced Mathematical & LaTeX Formulas from Stitch Desktop -->
  <g class="math-symbol" font-size="15" fill="{accent_green}" opacity="{'0.25' if is_dark else '0.18'}">
    <text x="680" y="115">∫ ℝⁿ</text>
  </g>
  <g class="math-symbol" font-size="13" fill="{accent_blue}" opacity="{'0.22' if is_dark else '0.16'}">
    <text x="650" y="145">∮_C E·dr = 0</text>
  </g>
  <g class="math-symbol" font-size="14" fill="{accent_green}" opacity="{'0.25' if is_dark else '0.18'}">
    <text x="735" y="42">∇ f(x)</text>
  </g>
  <g class="math-symbol" font-size="12" fill="{subtext_color}" opacity="{'0.25' if is_dark else '0.18'}">
    <text x="440" y="45">∂f/∂x</text>
  </g>
  <g class="math-symbol" font-size="12" fill="{accent_purple}" opacity="{'0.22' if is_dark else '0.16'}">
    <text x="590" y="52">det(A - λᵢI) = 0</text>
  </g>
  <g class="math-symbol" font-size="12" fill="{accent_blue}" opacity="{'0.22' if is_dark else '0.16'}">
    <text x="500" y="180">𝔼[X] = μ · Var(X) = σ²</text>
  </g>
  <g class="math-symbol" font-size="11" fill="{accent_green}" opacity="{'0.22' if is_dark else '0.16'}">
    <text x="450" y="200">ℋ ≅ L²(ℝⁿ) · ⟨ψ|Ĥ|ψ⟩</text>
  </g>
  <g class="math-symbol" font-size="11" fill="{subtext_color}" opacity="{'0.22' if is_dark else '0.16'}">
    <text x="750" y="185">λᵢ ≥ 0</text>
  </g>

  <!-- Desktop Layout -->
  <g class="desktop-layout">
    <!-- Top Pill Badge -->
    <g transform="translate(28, 24)">
      <rect x="0" y="0" width="112" height="26" rx="13" fill="{badge_bg}" stroke="{badge_border}" stroke-width="1" />
      <circle cx="13" cy="13" r="3.5" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 13px 13px;" />
      <text x="24" y="17" class="mono-pill">imanur.dev</text>
      <text x="124" y="17" class="mono-sub" font-size="11">Overview</text>
    </g>

    <!-- Top Right Active Portfolio Indicator -->
    <g transform="translate(634, 24)">
      <rect x="0" y="0" width="138" height="26" rx="13" fill="{badge_bg}" stroke="{badge_border}" stroke-width="1" />
      <path d="M12 9l3 3-3 3M17 15h3" stroke="{subtext_color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      <text x="28" y="17" class="mono-pill" font-size="10">ACTIVE PORTFOLIO</text>
    </g>

    <!-- Headline -->
    <g transform="translate(28, 92)">
      <text x="0" y="0" class="headline">Where applied mathematics meets <tspan class="headline-italic">predictive computation.</tspan></text>
      <text x="0" y="32" class="mono-sub">@ramadhan-imanur <tspan fill="{border_card}">/</tspan> <tspan fill="{badge_text}">Imanur.dev</tspan></text>
      <text x="0" y="62" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" font-size="12" fill="{subtext_color}">Applied Computation · Mathematical Modeling · Data Science Research</text>
    </g>
  </g>

  <!-- Mobile Layout -->
  <g class="mobile-layout">
    <g transform="translate(20, 20)">
      <rect x="0" y="0" width="108" height="24" rx="12" fill="{badge_bg}" stroke="{badge_border}" stroke-width="1" />
      <circle cx="12" cy="12" r="3" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 12px 12px;" />
      <text x="22" y="16" class="mono-pill" font-size="10">imanur.dev</text>
    </g>
    <g transform="translate(20, 75)">
      <text x="0" y="0" class="headline" font-size="20">Where applied mathematics meets</text>
      <text x="0" y="26" class="headline-italic" font-size="20">predictive computation.</text>
      <text x="0" y="56" class="mono-sub" font-size="11">@ramadhan-imanur / Imanur.dev</text>
      <text x="0" y="80" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" font-size="11" fill="{subtext_color}">Applied Computation · Modeling · Data Science</text>
    </g>
  </g>
</svg>"""


# ==========================================
# 2. Standalone Donut Card (Stitch Design Update)
# ==========================================
def build_donut_card_svg(theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#161B22" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    title_color = "#F0F6FC" if is_dark else "#1F2328"
    accent_green = "#39D353" if is_dark else "#1A7F37"
    accent_green_dark = "#238636" if is_dark else "#2EA043"
    accent_blue = "#58A6FF" if is_dark else "#0969DA"
    accent_purple = "#BC8CFF" if is_dark else "#8250DF"
    subtext_color = "#8B949E" if is_dark else "#656D76"
    ring_bg = "#21262D" if is_dark else "#E1E4E8"

    circ = 2 * math.pi * 58  # ~364.424

    display_langs = [
        ("Python", 50.0, accent_green, "CORE"),
        ("Mathematica", 25.0, accent_green_dark, "SYMBOLIC"),
        ("SQL", 15.0, accent_blue, "QUERY"),
        ("Shell / Bash", 10.0, accent_purple, "SCRIPT"),
    ]

    accum = 0.0
    donut_segments = []
    for name, pct, col, cat in display_langs:
        dash_len = max(1.0, (pct / 100.0) * circ - 2.5)
        dash_gap = circ - dash_len
        offset = -(accum / 100.0) * circ
        donut_segments.append(
            f'<circle cx="400" cy="190" r="58" fill="none" stroke="{col}" '
            f'stroke-width="13" stroke-dasharray="{dash_len:.2f} {dash_gap:.2f}" '
            f'stroke-dashoffset="{offset:.2f}" />'
        )
        accum += pct

    l1, l2, l3, l4 = display_langs[0], display_langs[1], display_langs[2], display_langs[3]

    return f"""<svg width="800" height="350" viewBox="0 0 800 350" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 12px; }}
      @keyframes subtle-dot-pulse {{
        0%, 100% {{ transform: scale(1); opacity: 0.85; }}
        50% {{ transform: scale(1.3); opacity: 1; }}
      }}
      @keyframes github-neon-glow {{
        0%, 100% {{ filter: drop-shadow(0 0 4px {accent_green}88); opacity: 0.92; transform: scale(1); }}
        50% {{ filter: drop-shadow(0 0 10px {accent_green}ff); opacity: 1; transform: scale(1.04); }}
      }}
      .status-dot-pulse {{ animation: subtle-dot-pulse 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite; transform-origin: center; }}
      .github-logo-pulse {{ animation: github-neon-glow 3s ease-in-out infinite; transform-origin: 400px 190px; }}

      .sec-title {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 11px; font-weight: 700; letter-spacing: 0.12em; fill: {accent_green}; }}
      .sec-meta {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 10px; font-weight: 500; fill: {subtext_color}; }}
      .callout-val {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 9px; font-weight: 600; letter-spacing: 0.05em; }}
      .callout-name {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 12px; font-weight: 600; fill: {title_color}; }}
      .watermark {{ font-family: 'JetBrains Mono', monospace; font-size: 9px; fill: {subtext_color}; opacity: 0.25; letter-spacing: 0.08em; user-select: none; pointer-events: none; }}

      @media (prefers-reduced-motion: reduce) {{
        .status-dot-pulse, .github-logo-pulse {{ animation: none !important; }}
      }}
    </style>

    <radialGradient id="donut-phosphor-glow" cx="80%" cy="15%" r="50%">
      <stop offset="0%" stop-color="{accent_green}" stop-opacity="{'0.12' if is_dark else '0.06'}" />
      <stop offset="100%" stop-color="{accent_green}" stop-opacity="0" />
    </radialGradient>
  </defs>

  <rect x="1" y="1" width="798" height="348" rx="12" class="card-bg" />
  <circle cx="720" cy="50" r="140" fill="url(#donut-phosphor-glow)" />

  <!-- Top Header Bar -->
  <g transform="translate(24, 26)">
    <circle cx="6" cy="6" r="3.5" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 6px 6px;" />
    <text x="18" y="9" class="sec-title">PROGRAMMING LANGUAGES // DISTRIBUTION</text>
    <text x="360" y="9" class="sec-meta">ASCII · GEN_03</text>
    <text x="748" y="9" class="sec-meta" text-anchor="end" opacity="0.4">[∀x ∈ ℝⁿ]</text>
  </g>
  <line x1="24" y1="46" x2="776" y2="46" stroke="{border_card}" stroke-width="0.8" />

  <!-- Donut Visualizer -->
  <g>
    <circle cx="400" cy="190" r="82" fill="none" stroke="{ring_bg}" stroke-width="1" />
    <circle cx="400" cy="190" r="74" fill="none" stroke="{border_card}" stroke-dasharray="2 4" stroke-width="0.8" />
    <circle cx="400" cy="190" r="44" fill="none" stroke="{border_card}" stroke-dasharray="2 6" stroke-width="0.8" />

    <g transform="rotate(-90 400 190)">
      {"".join(donut_segments)}
    </g>

    <!-- Center Pulsing GitHub Logo -->
    <g class="github-logo-pulse" transform="translate(388, 178)">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="{accent_green}">
        <path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" />
      </svg>
    </g>

    <!-- Callout 1 (Top Right) -->
    <polyline points="445,149 472,106 580,106" fill="none" stroke="{l1[2]}" stroke-width="1" opacity="0.85" />
    <circle cx="445" cy="149" r="2.5" fill="{l1[2]}" />
    <text x="580" y="90" text-anchor="end" class="callout-val" fill="{l1[2]}">{l1[1]:.0f}% // {l1[3]}</text>
    <text x="580" y="103" text-anchor="end" class="callout-name">{l1[0]}</text>

    <!-- Callout 2 (Bottom Right) -->
    <polyline points="438,231 468,274 580,274" fill="none" stroke="{l2[2]}" stroke-width="1" opacity="0.85" />
    <circle cx="438" cy="231" r="2.5" fill="{l2[2]}" />
    <text x="580" y="288" text-anchor="end" class="callout-name">{l2[0]}</text>
    <text x="580" y="300" text-anchor="end" class="callout-val" fill="{l2[2]}">{l2[1]:.0f}% // {l2[3]}</text>

    <!-- Callout 3 (Bottom Left) -->
    <polyline points="360,231 332,274 220,274" fill="none" stroke="{l3[2]}" stroke-width="1" opacity="0.85" />
    <circle cx="360" cy="231" r="2.5" fill="{l3[2]}" />
    <text x="220" y="288" text-anchor="start" class="callout-name">{l3[0]}</text>
    <text x="220" y="300" text-anchor="start" class="callout-val" fill="{l3[2]}">{l3[1]:.0f}% // {l3[3]}</text>

    <!-- Callout 4 (Top Left) -->
    <polyline points="355,149 328,106 220,106" fill="none" stroke="{l4[2]}" stroke-width="1" opacity="0.85" />
    <circle cx="355" cy="149" r="2.5" fill="{l4[2]}" />
    <text x="220" y="90" text-anchor="start" class="callout-val" fill="{l4[2]}">{l4[1]:.0f}% // {l4[3]}</text>
    <text x="220" y="103" text-anchor="start" class="callout-name">{l4[0]}</text>
  </g>

  <!-- Watermarks -->
  <text x="24" y="335" text-anchor="start" class="watermark">⟨ψ|Ĥ|ψ⟩ · dim(V)=4</text>
  <text x="774" y="335" text-anchor="end" class="watermark">[∀x ∈ ℝⁿ]</text>
</svg>"""


# ==========================================
# 3. Dedicated Telemetry Stats Card (Stitch Design Update)
# ==========================================
def build_stats_card_svg(user_stats, theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#161B22" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    title_color = "#F0F6FC" if is_dark else "#1F2328"
    accent_green = "#39D353" if is_dark else "#1A7F37"
    subtext_color = "#8B949E" if is_dark else "#656D76"
    card_sub_bg = "#21262D" if is_dark else "#F6F8FA"

    total_repos = user_stats.get("total_repos", 13)
    total_commits = user_stats.get("total_commits", "248")
    total_followers = user_stats.get("total_followers", 3)
    years_active = user_stats.get("years_active", 5)

    return f"""<svg width="800" height="195" viewBox="0 0 800 195" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 12px; }}
      .sub-card {{ fill: {card_sub_bg}; stroke: {border_card}; stroke-width: 1; rx: 8px; }}

      @keyframes subtle-dot-pulse {{
        0%, 100% {{ transform: scale(1); opacity: 0.85; }}
        50% {{ transform: scale(1.3); opacity: 1; }}
      }}
      .status-dot-pulse {{ animation: subtle-dot-pulse 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite; transform-origin: center; }}

      .telemetry-name {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 15px; font-weight: 700; fill: {title_color}; letter-spacing: -0.01em; }}
      .telemetry-sub {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 10px; font-weight: 600; fill: {accent_green}; letter-spacing: 0.12em; }}

      .metric-num {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 22px; font-weight: 700; fill: {title_color}; letter-spacing: -0.02em; }}
      .metric-lbl {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 9px; font-weight: 600; fill: {subtext_color}; letter-spacing: 0.08em; text-transform: uppercase; }}
      .metric-desc {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; font-size: 10px; fill: {subtext_color}; }}
      .watermark {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; fill: {subtext_color}; opacity: 0.4; letter-spacing: 0.08em; }}

      @media (prefers-reduced-motion: reduce) {{
        .status-dot-pulse {{ animation: none !important; }}
      }}
    </style>
  </defs>

  <rect x="1" y="1" width="798" height="193" rx="12" class="card-bg" />

  <!-- Header -->
  <g transform="translate(24, 22)">
    <text x="0" y="14" class="telemetry-name">Ramadhan Imanur</text>
    <text x="0" y="30" class="telemetry-sub">GITHUB TELEMETRY // STATS OVERVIEW</text>
    <text x="752" y="18" text-anchor="end" class="watermark">[∀x ∈ ℝⁿ]</text>
  </g>
  <line x1="24" y1="62" x2="776" y2="62" stroke="{border_card}" stroke-width="0.8" />

  <!-- 4 Metrics Horizontal Grid across 800px -->
  <!-- Card 1: Repos -->
  <g transform="translate(24, 76)">
    <rect x="0" y="0" width="174" height="102" class="sub-card" />
    <text x="14" y="24" class="metric-lbl">TOTAL REPOS</text>
    <circle cx="158" cy="20" r="3" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 158px 20px;" />
    <text x="14" y="62" class="metric-num">{total_repos}+</text>
    <text x="14" y="86" class="metric-desc">Curated Repositories</text>
  </g>

  <!-- Card 2: Commits -->
  <g transform="translate(216, 76)">
    <rect x="0" y="0" width="174" height="102" class="sub-card" />
    <text x="14" y="24" class="metric-lbl">ANNUAL COMMITS</text>
    <circle cx="158" cy="20" r="3" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 158px 20px;" />
    <text x="14" y="62" class="metric-num">{total_commits}+</text>
    <text x="14" y="86" class="metric-desc">Contributions Past Year</text>
  </g>

  <!-- Card 3: Followers -->
  <g transform="translate(408, 76)">
    <rect x="0" y="0" width="174" height="102" class="sub-card" />
    <text x="14" y="24" class="metric-lbl">FOLLOWERS</text>
    <circle cx="158" cy="20" r="3" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 158px 20px;" />
    <text x="14" y="62" class="metric-num">{total_followers}+</text>
    <text x="14" y="86" class="metric-desc">Developer Network</text>
  </g>

  <!-- Card 4: Years Active -->
  <g transform="translate(600, 76)">
    <rect x="0" y="0" width="174" height="102" class="sub-card" />
    <text x="14" y="24" class="metric-lbl">YEARS ACTIVE</text>
    <circle cx="158" cy="20" r="3" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 158px 20px;" />
    <text x="14" y="62" class="metric-num">{years_active}+</text>
    <text x="14" y="86" class="metric-desc">Since 2021 Joined</text>
  </g>
</svg>"""


# ==========================================
# 4. Statement of Craft Card
# ==========================================
def build_statement_craft_svg(theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#161B22" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    accent_green = "#39D353" if is_dark else "#1A7F37"
    body_color = "#C9D1D9" if is_dark else "#24292F"
    subtext_color = "#8B949E" if is_dark else "#656D76"

    return f"""<svg width="800" height="116" viewBox="0 0 800 116" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 12px; }}
      .craft-hdr {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 11px; font-weight: 700; letter-spacing: 0.12em; fill: {accent_green}; }}
      .craft-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Geist', sans-serif; font-size: 13.5px; line-height: 22px; fill: {body_color}; }}
      .watermark {{ font-family: 'JetBrains Mono', monospace; font-size: 10px; fill: {subtext_color}; opacity: 0.4; letter-spacing: 0.08em; }}
    </style>
  </defs>

  <rect x="1" y="1" width="798" height="114" rx="12" class="card-bg" />

  <!-- Header -->
  <g transform="translate(24, 22)">
    <path d="M4 19.5v-15A2.5 2.5 0 016.5 2H19a1 1 0 011 1v18a1 1 0 01-1 1H6.5a2.5 2.5 0 01-2.5-2.5zM6.5 20H18V4H6.5A1.5 1.5 0 005 5.5v13A1.5 1.5 0 006.5 20z" fill="{accent_green}" />
    <path d="M8 7h8v1.5H8zm0 3.5h8v1.5H8zm0 3.5h5v1.5H8z" fill="{accent_green}" />
    <text x="24" y="13" class="craft-hdr">STATEMENT OF CRAFT</text>
    <text x="752" y="13" text-anchor="end" class="watermark">[∀x ∈ ℝⁿ]</text>
  </g>

  <!-- Body -->
  <text x="24" y="66" class="craft-text">
    <tspan x="24" dy="0">Undergraduate Mathematics student focused on applied computation, mathematical modeling, and data science.</tspan>
    <tspan x="24" dy="24">Grounded in pure and applied mathematics, Python, Wolfram Mathematica, and relational database systems.</tspan>
  </text>
</svg>"""


# ==========================================
# 5. Channels Connect Section
# ==========================================
def build_connect_header_svg(theme="dark"):
    is_dark = theme == "dark"
    accent_green = "#39D353" if is_dark else "#1A7F37"
    subtext_color = "#8B949E" if is_dark else "#656D76"

    return f"""<svg width="800" height="32" viewBox="0 0 800 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      @keyframes subtle-dot-pulse {{
        0%, 100% {{ transform: scale(1); opacity: 0.85; }}
        50% {{ transform: scale(1.3); opacity: 1; }}
      }}
      .status-dot-pulse {{ animation: subtle-dot-pulse 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite; transform-origin: center; }}
      .lbl {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 11px; font-weight: 700; letter-spacing: 0.12em; fill: {accent_green}; }}
      .sub {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 10px; font-weight: 500; fill: {subtext_color}; }}
      @media (prefers-reduced-motion: reduce) {{
        .status-dot-pulse {{ animation: none !important; }}
      }}
    </style>
  </defs>

  <g transform="translate(6, 16)">
    <circle cx="6" cy="0" r="3.5" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: 6px 0px;" />
    <text x="18" y="4" class="lbl">CHANNELS // CONNECT</text>
    <text x="788" y="4" text-anchor="end" class="sub">EXTERNAL · ENDPOINT</text>
  </g>
</svg>"""


def build_connect_card_svg(platform, theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#161B22" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    title_color = "#F0F6FC" if is_dark else "#1F2328"
    accent_green = "#39D353" if is_dark else "#1A7F37"
    icon_box_bg = "#21262D" if is_dark else "#F6F8FA"
    subtext_color = "#8B949E" if is_dark else "#656D76"

    width = 392
    height = 76

    if platform == "github":
        title = "GitHub"
        sub = "@ramadhan-imanur"
        icon_svg = f"""<path fill-rule="evenodd" clip-rule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" fill="{title_color}" />"""
    elif platform == "email":
        title = "Gmail"
        sub = "ramadhan.imanur.rochim@gmail.com"
        icon_svg = f"""<path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" fill="{title_color}" />"""
    else:
        raise ValueError(f"Unknown platform: {platform}")

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 12px; }}
      .icon-box {{ fill: {icon_box_bg}; stroke: {border_card}; stroke-width: 1; rx: 8px; }}
      .title {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 13.5px; font-weight: 700; fill: {title_color}; }}
      .sub {{ font-family: 'JetBrains Mono', 'SF Mono', Consolas, monospace; font-size: 10.5px; font-weight: 500; fill: {subtext_color}; }}
      .arrow {{ stroke: {subtext_color}; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }}
      .card-bg:hover {{ stroke: {accent_green}; }}
    </style>
  </defs>

  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="12" class="card-bg" />

  <!-- Icon Box -->
  <g transform="translate(16, 16)">
    <rect x="0" y="0" width="44" height="44" class="icon-box" />
    <g transform="translate(10, 10)">
      <svg width="24" height="24" viewBox="0 0 24 24">
        {icon_svg}
      </svg>
    </g>
  </g>

  <!-- Titles -->
  <g transform="translate(74, 33)">
    <text x="0" y="0" class="title">{title}</text>
    <path d="M52 -11l6 -6M58 -17h-6M58 -17v6" class="arrow" />
    <text x="0" y="19" class="sub">{sub}</text>
  </g>
</svg>"""


# ==========================================
# 6. Legacy & Fallback Generators
# ==========================================
def build_stat_card_svg(stat_type, theme="dark"):
    is_dark = theme == "dark"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    num_color = "#F0F6FC" if is_dark else "#1F2328"
    text_color = "#8B949E" if is_dark else "#656D76"
    card_fill = "#161B22" if is_dark else "#F6F8FA"
    accent_green = "#39D353" if is_dark else "#1A7F37"

    width = 188
    height = 104
    cx = 94

    if stat_type == "repos":
        val = f"{total_repos}+"
        lbl = "TOTAL REPOS"
    elif stat_type == "commits":
        val = f"{total_commits}+"
        lbl = "ANNUAL COMMITS"
    elif stat_type == "followers":
        val = f"{total_followers}+"
        lbl = "FOLLOWERS"
    elif stat_type == "years":
        val = f"{years_active}+"
        lbl = "YEARS ACTIVE"
    else:
        raise ValueError(f"Unknown stat_type: {stat_type}")

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card {{ fill: {card_fill}; stroke: {border_card}; stroke-width: 1; rx: 8px; }}
      .num {{ font-family: 'JetBrains Mono', monospace; font-size: 22px; font-weight: 700; fill: {num_color}; text-anchor: middle; }}
      .lbl {{ font-family: 'JetBrains Mono', monospace; font-size: 9.5px; font-weight: 600; fill: {text_color}; text-anchor: middle; letter-spacing: 0.8px; text-transform: uppercase; }}
      @keyframes subtle-dot-pulse {{
        0%, 100% {{ transform: scale(1); opacity: 0.85; }}
        50% {{ transform: scale(1.3); opacity: 1; }}
      }}
      .status-dot-pulse {{ animation: subtle-dot-pulse 2.2s cubic-bezier(0.4, 0, 0.6, 1) infinite; transform-origin: center; }}
    </style>
  </defs>

  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="8" class="card" />
  <circle cx="{width - 20}" cy="20" r="3" fill="{accent_green}" class="status-dot-pulse" style="transform-origin: {width - 20}px 20px;" />
  <text x="{cx}" y="56" class="num">{val}</text>
  <text x="{cx}" y="80" class="lbl">{lbl}</text>
</svg>"""


# ==========================================
# Write All Assets (Dark, Light, Fallbacks)
# ==========================================
def write_svg_asset(filename, content):
    filepath = ASSETS_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        ET.fromstring(content)
    except Exception as e:
        print(f"ERROR: Invalid XML generated for {filename}: {e}")
        raise


print("Writing Dark Theme assets (Updated Stitch Design)...")
write_svg_asset("welcome-banner-dark.svg", build_welcome_banner_svg("dark"))
write_svg_asset("donut-card-dark.svg", build_donut_card_svg("dark"))
write_svg_asset("stats-card-dark.svg", build_stats_card_svg(user_stats, "dark"))
write_svg_asset("statement-craft-dark.svg", build_statement_craft_svg("dark"))
write_svg_asset("connect-header-dark.svg", build_connect_header_svg("dark"))
write_svg_asset("connect-github-dark.svg", build_connect_card_svg("github", "dark"))
write_svg_asset("connect-email-dark.svg", build_connect_card_svg("email", "dark"))

# Legacy telemetry-card alias to stats-card
write_svg_asset("telemetry-card-dark.svg", build_stats_card_svg(user_stats, "dark"))

for stat in ["repos", "commits", "followers", "years"]:
    write_svg_asset(f"stat-{stat}-dark.svg", build_stat_card_svg(stat, "dark"))

print("Writing Light Theme assets (Updated Stitch Design)...")
write_svg_asset("welcome-banner-light.svg", build_welcome_banner_svg("light"))
write_svg_asset("donut-card-light.svg", build_donut_card_svg("light"))
write_svg_asset("stats-card-light.svg", build_stats_card_svg(user_stats, "light"))
write_svg_asset("statement-craft-light.svg", build_statement_craft_svg("light"))
write_svg_asset("connect-header-light.svg", build_connect_header_svg("light"))
write_svg_asset("connect-github-light.svg", build_connect_card_svg("github", "light"))
write_svg_asset("connect-email-light.svg", build_connect_card_svg("email", "light"))

write_svg_asset("telemetry-card-light.svg", build_stats_card_svg(user_stats, "light"))

for stat in ["repos", "commits", "followers", "years"]:
    write_svg_asset(f"stat-{stat}-light.svg", build_stat_card_svg(stat, "light"))

print("Updating default fallback assets...")
shutil.copyfile(ASSETS_DIR / "welcome-banner-dark.svg", ASSETS_DIR / "welcome-banner.svg")
shutil.copyfile(ASSETS_DIR / "donut-card-dark.svg", ASSETS_DIR / "donut-card.svg")
shutil.copyfile(ASSETS_DIR / "stats-card-dark.svg", ASSETS_DIR / "stats-card.svg")
shutil.copyfile(ASSETS_DIR / "telemetry-card-dark.svg", ASSETS_DIR / "telemetry-card.svg")
shutil.copyfile(ASSETS_DIR / "statement-craft-dark.svg", ASSETS_DIR / "statement-craft.svg")
shutil.copyfile(ASSETS_DIR / "connect-header-dark.svg", ASSETS_DIR / "connect-header.svg")
shutil.copyfile(ASSETS_DIR / "connect-github-dark.svg", ASSETS_DIR / "connect-github.svg")
shutil.copyfile(ASSETS_DIR / "connect-email-dark.svg", ASSETS_DIR / "connect-email.svg")

for stat in ["repos", "commits", "followers", "years"]:
    shutil.copyfile(ASSETS_DIR / f"stat-{stat}-dark.svg", ASSETS_DIR / f"stat-{stat}.svg")

print("All active dashboard assets updated successfully!")
