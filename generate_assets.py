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
total_commits = "131"
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

# Discover all public non-fork repos dynamically
repos_data = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100&type=owner") or []
repo_names = [r["name"] for r in repos_data if not r.get("fork")]
if not repo_names:
    repo_names = DEFAULT_REPOS


def clone_repo(name, dest_dir):
    url = f"https://github.com/{USERNAME}/{name}.git"
    target = Path(dest_dir) / name
    subprocess.run(["git", "clone", "--depth", "1", "--quiet", url, str(target)], check=False)


lang_totals = {}
# 1. Live scan all repositories concurrently
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

# 2. Fallback to SLOC cache if live scan yielded nothing
if not lang_totals and SLOC_CACHE_FILE.exists():
    try:
        with open(SLOC_CACHE_FILE, "r", encoding="utf-8") as f:
            lang_totals = json.load(f)
    except Exception:
        pass

# 3. Baseline default if no cache
if not lang_totals:
    lang_totals = {
        "Python": 10636,
        "CSS": 3010,
        "JavaScript": 3003,
        "HTML": 1889,
        "LaTeX": 757,
        "SQL": 687,
        "Shell": 63,
    }

total_lines = sum(lang_totals.values())
sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)
top_5 = sorted_langs[:5]

LANGUAGE_COLORS = {
    "Python": "#3572A5",
    "SQL": "#336791",       # PostgreSQL Blue (matches Core Technologies badge)
    "CSS": "#563D7C",
    "JavaScript": "#F1E05A",
    "HTML": "#E34C26",
    "LaTeX": "#3D6117",
    "Shell": "#89E051",
    "TypeScript": "#3178C6",
    "C": "#555555",
    "C++": "#F34B7D",
    "R": "#198CE7",
    "Mathematica": "#DD1100",
    "Rust": "#DEA584",
    "Go": "#00ADD8",
    "Java": "#B07219",
}

formatted_langs = []
for name, line_count in top_5:
    pct = (line_count / total_lines) * 100.0 if total_lines > 0 else 0
    color = LANGUAGE_COLORS.get(name, "#8B949E")
    formatted_langs.append((name, pct, color))

print(f"  -> Total Source Lines of Code: {total_lines:,} lines")
print("  -> Top 5 Languages (by Source Lines of Code):")
for name, pct, _ in formatted_langs:
    cnt = lang_totals.get(name, 0)
    print(f"     - {name:12}: {pct:5.2f}% ({cnt:,} lines)")


# SVG Generators
def build_welcome_banner_desktop_svg(theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#0D1117" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    title_color = "#F0F6FC" if is_dark else "#1F2328"
    text_color = "#8B949E" if is_dark else "#656D76"
    tag_bg = "#388BFD15" if is_dark else "#0969DA15"
    tag_border = "#388BFD40" if is_dark else "#0969DA40"
    tag_text = "#388BFD" if is_dark else "#0969DA"
    dot_color = "#2EA043" if is_dark else "#1A7F37"

    return f"""<svg width="800" height="90" viewBox="0 0 800 90" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 8px; }}
      .greeting {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, sans-serif; font-size: 19px; font-weight: 700; fill: {title_color}; }}
      .subtext {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, sans-serif; font-size: 13px; font-weight: 400; fill: {text_color}; }}
      .tag {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, sans-serif; font-size: 11px; font-weight: 600; fill: {tag_text}; }}
      .tag-bg {{ fill: {tag_bg}; stroke: {tag_border}; stroke-width: 1; rx: 12px; }}

      .mobile-layout {{ display: none; }}
      .desktop-layout {{ display: inline; }}

      @media (max-width: 650px) {{
        .desktop-layout {{ display: none; }}
        .mobile-layout {{ display: inline; }}
      }}
    </style>
  </defs>

  <rect x="1" y="1" width="798" height="88" rx="8" class="card-bg" />

  <!-- Desktop Layout (>= 651px) -->
  <g class="desktop-layout">
    <g transform="translate(24, 34)">
      <text x="0" y="0" class="greeting">Welcome to Ramadhan Imanur's Hub</text>
      <text x="0" y="24" class="subtext">Explore open source contributions, mathematical modeling, and data science research</text>
    </g>

    <g transform="translate(640, 32)">
      <rect x="0" y="0" width="136" height="26" rx="13" class="tag-bg" />
      <circle cx="14" cy="13" r="4" fill="{dot_color}" />
      <text x="26" y="17" class="tag">Active Portfolio</text>
    </g>
  </g>

  <!-- Mobile / Tablet Responsive Layout (<= 650px) -->
  <g class="mobile-layout">
    <text x="400" y="28" class="greeting" text-anchor="middle" font-size="19px">Welcome to Ramadhan Imanur's Hub</text>
    <text x="400" y="48" class="subtext" text-anchor="middle" font-size="12px">Applied Computation · Mathematical Modeling · Data Science</text>

    <g transform="translate(332, 56)">
      <rect x="0" y="0" width="136" height="24" rx="12" class="tag-bg" />
      <circle cx="14" cy="12" r="4" fill="{dot_color}" />
      <text x="26" y="16" class="tag">Active Portfolio</text>
    </g>
  </g>
</svg>"""


def build_stat_card_svg(stat_type, theme="dark"):
    is_dark = theme == "dark"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    num_color = "#F0F6FC" if is_dark else "#1F2328"
    text_color = "#8B949E" if is_dark else "#656D76"
    card_fill = "#161B22" if is_dark else "#F6F8FA"

    width = 188
    height = 104
    cx = 94

    if stat_type == "repos":
        icon_svg = f'<path d="M96 22h-10c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-11c0-1.1-.9-2-2-2h-5l-1.5-1.5c-.4-.4-.9-.5-1.5-.5z" fill="{text_color}" />'
        val = f"{total_repos}+"
        lbl = "TOTAL REPOS"
    elif stat_type == "commits":
        icon_svg = f'<path d="M94 22l2.5 5 5.5.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.5-.8 2.5-5z" fill="{text_color}" />'
        val = f"{total_commits}+"
        lbl = "ANNUAL COMMITS"
    elif stat_type == "followers":
        icon_svg = f'<path d="M90.5 28.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7zm8 0a3 3 0 100-6 3 3 0 000 6zm-8 3c-2.3 0-7 1.2-7 3.5v2.5h14v-2.5c0-2.3-4.7-3.5-7-3.5zm8 0c-.3 0-.7 0-1.1.1 1.3.9 2.1 2.1 2.1 3.4v2.5h6v-2.5c0-2.3-4.7-3.5-7-3.5z" fill="{text_color}" />'
        val = f"{total_followers}+"
        lbl = "FOLLOWERS"
    elif stat_type == "years":
        icon_svg = f'<path d="M94 22a8 8 0 100 16 8 8 0 000-16zm0 14.5a6.5 6.5 0 110-13 6.5 6.5 0 010 13zm.5-10.5H93v4.5l3.8 2.3.8-1.2-3.1-1.8V26z" fill="{text_color}" />'
        val = f"{years_active}"
        lbl = "YEARS ACTIVE"
    else:
        raise ValueError(f"Unknown stat_type: {stat_type}")

    return f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card {{ fill: {card_fill}; stroke: {border_card}; stroke-width: 1; rx: 8px; }}
      .num {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, sans-serif; font-size: 24px; font-weight: 700; fill: {num_color}; text-anchor: middle; }}
      .lbl {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, sans-serif; font-size: 11px; font-weight: 600; fill: {text_color}; text-anchor: middle; letter-spacing: 0.8px; }}
    </style>
  </defs>

  <rect x="1" y="1" width="{width - 2}" height="{height - 2}" rx="8" class="card" />
  {icon_svg}
  <text x="{cx}" y="64" class="num">{val}</text>
  <text x="{cx}" y="84" class="lbl">{lbl}</text>
</svg>"""


def build_core_tech_svg(theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#0D1117" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    header_color = "#8B949E" if is_dark else "#656D76"
    badge_bg = "#161B22" if is_dark else "#F6F8FA"
    badge_border = "#30363D" if is_dark else "#D0D7DE"
    badge_text = "#C9D1D9" if is_dark else "#1F2328"

    linux_dot = "#FCC624" if is_dark else "#D99B00"
    js_dot = "#F1E05A" if is_dark else "#B89C00"
    stoch_dot = "#2EA043" if is_dark else "#1A7F37"

    return f"""<svg width="350" height="215" viewBox="0 0 350 215" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 4.5px; }}
      .header {{ font: 600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: {header_color}; text-transform: uppercase; letter-spacing: 0.8px; }}
      .badge-bg {{ fill: {badge_bg}; stroke: {badge_border}; stroke-width: 1; rx: 12px; }}
      .badge-text {{ font: 500 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: {badge_text}; }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="349" height="214" rx="4.5" class="card-bg" />

  <text x="20" y="32" class="header">CORE TECHNOLOGIES</text>

  <!-- Row 1 -->
  <g transform="translate(20, 52)">
    <rect x="0" y="0" width="82" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#3572A5" />
    <text x="24" y="17" class="badge-text">Python</text>
  </g>

  <g transform="translate(110, 52)">
    <rect x="0" y="0" width="102" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#336791" />
    <text x="24" y="17" class="badge-text">PostgreSQL</text>
  </g>

  <g transform="translate(220, 52)">
    <rect x="0" y="0" width="108" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#DD1100" />
    <text x="24" y="17" class="badge-text">Mathematica</text>
  </g>

  <!-- Row 2 -->
  <g transform="translate(20, 88)">
    <rect x="0" y="0" width="102" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#F7931E" />
    <text x="24" y="17" class="badge-text">Scikit-Learn</text>
  </g>

  <g transform="translate(130, 88)">
    <rect x="0" y="0" width="85" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#EE4C2C" />
    <text x="24" y="17" class="badge-text">PyTorch</text>
  </g>

  <g transform="translate(223, 88)">
    <rect x="0" y="0" width="105" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#4B8BBE" />
    <text x="24" y="17" class="badge-text">NumPy/Pandas</text>
  </g>

  <!-- Row 3 -->
  <g transform="translate(20, 124)">
    <rect x="0" y="0" width="70" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#E34C26" />
    <text x="24" y="17" class="badge-text">SQL</text>
  </g>

  <g transform="translate(98, 124)">
    <rect x="0" y="0" width="76" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#008080" />
    <text x="24" y="17" class="badge-text">LaTeX</text>
  </g>

  <g transform="translate(182, 124)">
    <rect x="0" y="0" width="88" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#F05032" />
    <text x="24" y="17" class="badge-text">Git &amp; Hub</text>
  </g>

  <!-- Row 4 -->
  <g transform="translate(20, 160)">
    <rect x="0" y="0" width="78" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="{linux_dot}" />
    <text x="24" y="17" class="badge-text">Linux</text>
  </g>

  <g transform="translate(106, 160)">
    <rect x="0" y="0" width="98" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="{js_dot}" />
    <text x="24" y="17" class="badge-text">JavaScript</text>
  </g>

  <g transform="translate(212, 160)">
    <rect x="0" y="0" width="116" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="{stoch_dot}" />
    <text x="24" y="17" class="badge-text">SARIMA/Markov</text>
  </g>
</svg>"""


def build_languages_donut_svg(langs, theme="dark"):
    is_dark = theme == "dark"
    bg_card = "#0D1117" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    header_color = "#8B949E" if is_dark else "#656D76"
    text_color = "#C9D1D9" if is_dark else "#1F2328"
    pct_color = "#8B949E" if is_dark else "#656D76"
    track_color = "#21262D" if is_dark else "#E1E4E8"

    cx = 260
    cy = 120
    r = 46
    circ = 2 * math.pi * r
    stroke_w = 16

    donut_circles = []
    accum_pct = 0.0
    for name, pct, color in langs:
        dash_len = (pct / 100.0) * circ
        dash_gap = circ - dash_len
        offset = -(accum_pct / 100.0) * circ
        donut_circles.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}"'
            f' stroke-width="{stroke_w}" stroke-dasharray="{dash_len:.2f} {dash_gap:.2f}"'
            f' stroke-dashoffset="{offset:.2f}" transform="rotate(-90 {cx} {cy})" />'
        )
        accum_pct += pct

    legend_items = []
    start_y = 66
    spacing = 28
    for i, (name, pct, color) in enumerate(langs):
        y = start_y + i * spacing
        escaped_name = html.escape(name)
        legend_items.append(f"""  <g>
    <circle cx="24" cy="{y - 4}" r="4.5" fill="{color}" />
    <text x="36" y="{y}" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, sans-serif" font-size="12" font-weight="500" fill="{text_color}">{escaped_name}</text>
    <text x="180" y="{y}" text-anchor="end" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, sans-serif" font-size="11" font-weight="500" fill="{pct_color}">{pct:.1f}%</text>
  </g>""")

    return f"""<svg width="350" height="215" viewBox="0 0 350 215" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 4.5px; }}
      .header {{ font: 600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: {header_color}; text-transform: uppercase; letter-spacing: 0.8px; }}
    </style>
  </defs>

  <rect x="0.5" y="0.5" width="349" height="214" rx="4.5" class="card-bg" />
  <text x="20" y="32" class="header">MOST USED LANGUAGES</text>

  <!-- Legend -->
{"".join(legend_items)}

  <!-- Donut Chart -->
  <g>
    <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{track_color}" stroke-width="{stroke_w}" />
    {"".join(donut_circles)}
  </g>
</svg>"""


# Optional Contributions Activity SVG (Preserved if explicitly needed)
def build_contributions_svg(theme="dark"):
    if not html_data:
        return ""
    is_dark = theme == "dark"
    bg_card = "#0D1117" if is_dark else "#FFFFFF"
    border_card = "#30363D" if is_dark else "#D0D7DE"
    title_color = "#F0F6FC" if is_dark else "#1F2328"
    text_color = "#8B949E" if is_dark else "#656D76"

    color_map = {
        0: "#161B22" if is_dark else "#EBEDF0",
        1: "#0E4429" if is_dark else "#9BE9A8",
        2: "#006D32" if is_dark else "#40C463",
        3: "#26A641" if is_dark else "#30A14E",
        4: "#39D353" if is_dark else "#216E39",
    }

    table_rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_data, re.DOTALL)
    grid_rows = []
    for r in table_rows[1:]:
        days = re.findall(r'<td[^>]*data-date=\"([^\"]+)\"[^>]*data-level=\"([^\"]+)\"', r)
        if days:
            grid_rows.append(days)

    if grid_rows and max(len(r) for r in grid_rows) > 52:
        grid_rows = [r[-52:] for r in grid_rows]

    svg_width = 800
    svg_height = 180
    cell_size = 10
    cell_gap = 3
    start_x = 42
    start_y = 56

    cells_svg = []
    for row_idx, row_days in enumerate(grid_rows):
        y = start_y + row_idx * (cell_size + cell_gap)
        for col_idx, day_info in enumerate(row_days):
            x = start_x + col_idx * (cell_size + cell_gap)
            level = int(day_info[1])
            color = color_map.get(level, color_map[0])
            cells_svg.append(f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="2" fill="{color}" />')

    days_labels_svg = []
    days_map = {1: "Mon", 3: "Wed", 5: "Fri"}
    for r_idx, label in days_map.items():
        y = start_y + r_idx * (cell_size + cell_gap) + 8
        days_labels_svg.append(f'<text x="{start_x - 10}" y="{y}" text-anchor="end" fill="{text_color}" font-size="10" font-family="-apple-system,BlinkMacSystemFont,\'Segoe UI\',Helvetica,Arial,sans-serif">{label}</text>')

    return f"""<svg width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 8px; }}
      .title {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 600; fill: {title_color}; }}
      .subtitle {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 500; fill: {text_color}; }}
      .footnote {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; fill: {text_color}; }}
    </style>
  </defs>

  <rect x="1" y="1" width="{svg_width - 2}" height="{svg_height - 2}" rx="8" class="card-bg" />

  <g transform="translate(20, 26)">
    <path d="M3 13V17C3 18.1046 3.89543 19 5 19H19C20.1046 19 21 18.1046 21 17V13M3 13V7C3 5.89543 3.89543 5 5 5H19C20.1046 5 21 5.89543 21 7V13M3 13H21M8 10V14M16 10V14" stroke="{text_color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    <text x="28" y="14" class="title">Contributions</text>
  </g>
  <text x="{svg_width - 24}" y="38" text-anchor="end" class="subtitle">{total_commits} in the last year</text>

  <!-- Day Labels -->
  {"".join(days_labels_svg)}

  <!-- Heatmap Grid -->
  {"".join(cells_svg)}

  <!-- Footer -->
  <text x="42" y="{svg_height - 18}" class="footnote">Last 52 weeks of activity</text>

  <!-- Legend -->
  <g transform="translate({svg_width - 160}, {svg_height - 26})">
    <text x="-8" y="8" text-anchor="end" class="footnote">Less</text>
    <rect x="0" y="0" width="10" height="10" rx="2" fill="{color_map[0]}" />
    <rect x="14" y="0" width="10" height="10" rx="2" fill="{color_map[1]}" />
    <rect x="28" y="0" width="10" height="10" rx="2" fill="{color_map[2]}" />
    <rect x="42" y="0" width="10" height="10" rx="2" fill="{color_map[3]}" />
    <rect x="56" y="0" width="10" height="10" rx="2" fill="{color_map[4]}" />
    <text x="74" y="8" class="footnote">More</text>
  </g>
</svg>"""


# Write Active Assets (Dark Theme)
print("Writing Dark Theme assets...")
with open(ASSETS_DIR / "welcome-banner-dark.svg", "w", encoding="utf-8") as f:
    f.write(build_welcome_banner_desktop_svg("dark"))
for stat in ["repos", "commits", "followers", "years"]:
    with open(ASSETS_DIR / f"stat-{stat}-dark.svg", "w", encoding="utf-8") as f:
        f.write(build_stat_card_svg(stat, "dark"))
with open(ASSETS_DIR / "core-tech-dark.svg", "w", encoding="utf-8") as f:
    f.write(build_core_tech_svg("dark"))
with open(ASSETS_DIR / "languages-donut-dark.svg", "w", encoding="utf-8") as f:
    f.write(build_languages_donut_svg(formatted_langs, "dark"))

# Write Active Assets (Light Theme)
print("Writing Light Theme assets...")
with open(ASSETS_DIR / "welcome-banner-light.svg", "w", encoding="utf-8") as f:
    f.write(build_welcome_banner_desktop_svg("light"))
for stat in ["repos", "commits", "followers", "years"]:
    with open(ASSETS_DIR / f"stat-{stat}-light.svg", "w", encoding="utf-8") as f:
        f.write(build_stat_card_svg(stat, "light"))
with open(ASSETS_DIR / "core-tech-light.svg", "w", encoding="utf-8") as f:
    f.write(build_core_tech_svg("light"))
with open(ASSETS_DIR / "languages-donut-light.svg", "w", encoding="utf-8") as f:
    f.write(build_languages_donut_svg(formatted_langs, "light"))

# Fallbacks (Defaults)
print("Updating fallback assets...")
shutil.copyfile(ASSETS_DIR / "welcome-banner-dark.svg", ASSETS_DIR / "welcome-banner.svg")
for stat in ["repos", "commits", "followers", "years"]:
    shutil.copyfile(ASSETS_DIR / f"stat-{stat}-dark.svg", ASSETS_DIR / f"stat-{stat}.svg")
shutil.copyfile(ASSETS_DIR / "core-tech-dark.svg", ASSETS_DIR / "core-tech.svg")
shutil.copyfile(ASSETS_DIR / "languages-donut-dark.svg", ASSETS_DIR / "languages-donut.svg")

# Optional: Contributions SVG if specifically requested via argument
if "--include-contributions" in sys.argv:
    print("Writing optional Contributions Heatmap assets...")
    with open(ASSETS_DIR / "contributions-dark.svg", "w", encoding="utf-8") as f:
        f.write(build_contributions_svg("dark"))
    with open(ASSETS_DIR / "contributions-light.svg", "w", encoding="utf-8") as f:
        f.write(build_contributions_svg("light"))
    shutil.copyfile(ASSETS_DIR / "contributions-dark.svg", ASSETS_DIR / "contributions.svg")

print("All active dashboard assets updated successfully!")
