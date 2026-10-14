import datetime
from html.parser import HTMLParser
from pathlib import Path
import urllib.request

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

print("Fetching contributions data from GitHub...")
url = "https://github.com/users/ramadhan-imanur/contributions"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html_data = urllib.request.urlopen(req).read().decode("utf-8")


class CalParser(HTMLParser):

  def __init__(self):
    super().__init__()
    self.days = []
    self.total_contrib = "98 in the last year"
    self.in_h2 = False
    self.h2_text = ""

  def handle_starttag(self, tag, attrs):
    attrs_dict = dict(attrs)
    if (
        tag == "h2"
        and "js-contribution-activity-description" in attrs_dict.get("id", "")
    ):
      self.in_h2 = True
    if tag == "td" and "data-date" in attrs_dict:
      self.days.append({
          "date": attrs_dict.get("data-date"),
          "level": int(attrs_dict.get("data-level", 0)),
      })

  def handle_endtag(self, tag):
    if tag == "h2" and self.in_h2:
      self.in_h2 = False
      cleaned = " ".join(self.h2_text.split())
      if "contributions" in cleaned:
        # e.g. "98 contributions in the last year" -> "98 in the last year"
        parts = cleaned.replace("contributions", "").split()
        self.total_contrib = f"{parts[0]} in the last year"

  def handle_data(self, data):
    if self.in_h2:
      self.h2_text += data


parser = CalParser()
parser.feed(html_data)
print(f"Parsed {len(parser.days)} days. Total: {parser.total_contrib}")

# Group into weeks (columns of 7)
weeks = []
current_week = []
for day in parser.days:
  current_week.append(day)
  if len(current_week) == 7:
    weeks.append(current_week)
    current_week = []
if current_week:
  weeks.append(current_week)

# Take the last 52 weeks
weeks = weeks[-52:]

# Month labels
month_labels = []
last_month = None
for col_idx, week in enumerate(weeks):
  if week:
    dt = datetime.datetime.strptime(week[0]["date"], "%Y-%m-%d")
    if dt.month != last_month:
      month_labels.append((dt.strftime("%b"), col_idx))
      last_month = dt.month

# Generate contributions.svg
color_map = {
    0: "#161B22",  # Dark empty cell
    1: "#0E4429",  # Level 1
    2: "#006D32",  # Level 2
    3: "#26A641",  # Level 3
    4: "#39D353",  # Level 4
}

svg_width = 800
svg_height = 200
cell_size = 10
cell_gap = 3
start_x = 42
start_y = 65

cells_svg = []
for col_idx, week in enumerate(weeks):
  x = start_x + col_idx * (cell_size + cell_gap)
  for row_idx, day in enumerate(week):
    y = start_y + row_idx * (cell_size + cell_gap)
    color = color_map.get(day["level"], "#161B22")
    cells_svg.append(
        f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}"'
        f' rx="2" fill="{color}" />'
    )

months_svg = []
for m_label, col_idx in month_labels:
  x = start_x + col_idx * (cell_size + cell_gap)
  months_svg.append(
      f'<text x="{x}" y="{start_y - 8}" fill="#8B949E" font-size="10"'
      ' font-family="-apple-system,BlinkMacSystemFont,\'Segoe'
      ' UI\',Helvetica,Arial,sans-serif">'
      f"{m_label}</text>"
  )

days_labels_svg = []
days_map = {1: "Mon", 3: "Wed", 5: "Fri"}
for r_idx, label in days_map.items():
  y = start_y + r_idx * (cell_size + cell_gap) + 8
  days_labels_svg.append(
      f'<text x="{start_x - 10}" y="{y}" text-anchor="end" fill="#8B949E"'
      ' font-size="10"'
      ' font-family="-apple-system,BlinkMacSystemFont,\'Segoe'
      ' UI\',Helvetica,Arial,sans-serif">'
      f"{label}</text>"
  )

contributions_svg = f"""<svg width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg {{ fill: #0D1117; stroke: #30363D; stroke-width: 1; rx: 8px; }}
      .title {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 600; fill: #F0F6FC; }}
      .subtitle {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 500; fill: #8B949E; }}
      .footnote {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; fill: #8B949E; }}
    </style>
  </defs>

  <!-- Container Card -->
  <rect x="1" y="1" width="{svg_width - 2}" height="{svg_height - 2}" rx="8" class="card-bg" />

  <!-- Header -->
  <g transform="translate(20, 26)">
    <!-- Icon -->
    <path d="M3 13V17C3 18.1046 3.89543 19 5 19H19C20.1046 19 21 18.1046 21 17V13M3 13V7C3 5.89543 3.89543 5 5 5H19C20.1046 5 21 5.89543 21 7V13M3 13H21M8 10V14M16 10V14" stroke="#8B949E" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    <text x="28" y="14" class="title">Contributions</text>
  </g>
  <text x="{svg_width - 24}" y="38" text-anchor="end" class="subtitle">{parser.total_contrib}</text>

  <!-- Month Labels -->
  {"".join(months_svg)}

  <!-- Day Labels -->
  {"".join(days_labels_svg)}

  <!-- Heatmap Grid -->
  {"".join(cells_svg)}

  <!-- Footer -->
  <text x="42" y="{svg_height - 18}" class="footnote">Last 52 weeks of activity</text>

  <!-- Legend -->
  <g transform="translate({svg_width - 160}, {svg_height - 26})">
    <text x="-8" y="8" text-anchor="end" class="footnote">Less</text>
    <rect x="0" y="0" width="10" height="10" rx="2" fill="#161B22" />
    <rect x="14" y="0" width="10" height="10" rx="2" fill="#0E4429" />
    <rect x="28" y="0" width="10" height="10" rx="2" fill="#006D32" />
    <rect x="42" y="0" width="10" height="10" rx="2" fill="#26A641" />
    <rect x="56" y="0" width="10" height="10" rx="2" fill="#39D353" />
    <text x="74" y="8" class="footnote">More</text>
  </g>
</svg>"""

with open(ASSETS_DIR / "contributions.svg", "w", encoding="utf-8") as f:
  f.write(contributions_svg)
print("Saved assets/contributions.svg")

# Generate quick-stats.svg (4 Cards in a row)
quick_stats_svg = """<svg width="800" height="110" viewBox="0 0 800 110" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .stat-card { fill: #0D1117; stroke: #30363D; stroke-width: 1; rx: 8px; }
      .stat-num { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 24px; font-weight: 700; fill: #F0F6FC; text-anchor: middle; }
      .stat-label { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 600; fill: #8B949E; text-anchor: middle; letter-spacing: 0.8px; }
    </style>
  </defs>

  <!-- Card 1: Total Repos -->
  <g transform="translate(0, 0)">
    <rect x="1" y="1" width="188" height="108" rx="8" class="stat-card" />
    <!-- Folder Icon -->
    <path d="M94 24h-10c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-11c0-1.1-.9-2-2-2h-5l-1.5-1.5c-.4-.4-.9-.5-1.5-.5z" fill="#8B949E" />
    <text x="95" y="68" class="stat-num">11+</text>
    <text x="95" y="88" class="stat-label">TOTAL REPOS</text>
  </g>

  <!-- Card 2: Contributions -->
  <g transform="translate(204, 0)">
    <rect x="1" y="1" width="188" height="108" rx="8" class="stat-card" />
    <!-- Star Icon -->
    <path d="M95 24l2.5 5 5.5.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.5-.8 2.5-5z" fill="#8B949E" />
    <text x="95" y="68" class="stat-num">98+</text>
    <text x="95" y="88" class="stat-label">ANNUAL COMMITS</text>
  </g>

  <!-- Card 3: Followers -->
  <g transform="translate(408, 0)">
    <rect x="1" y="1" width="188" height="108" rx="8" class="stat-card" />
    <!-- Users Icon -->
    <path d="M91 30a3.5 3.5 0 100-7 3.5 3.5 0 000 7zm8 0a3 3 0 100-6 3 3 0 000 6zm-8 3c-2.3 0-7 1.2-7 3.5V39h14v-2.5c0-2.3-4.7-3.5-7-3.5zm8 0c-.3 0-.7 0-1.1.1 1.3.9 2.1 2.1 2.1 3.4V39h6v-2.5c0-2.3-4.7-3.5-7-3.5z" fill="#8B949E" />
    <text x="95" y="68" class="stat-num">2+</text>
    <text x="95" y="88" class="stat-label">FOLLOWERS</text>
  </g>

  <!-- Card 4: Years Active -->
  <g transform="translate(612, 0)">
    <rect x="1" y="1" width="187" height="108" rx="8" class="stat-card" />
    <!-- Clock Icon -->
    <path d="M94 24a8 8 0 100 16 8 8 0 000-16zm0 14.5a6.5 6.5 0 110-13 6.5 6.5 0 010 13zm.5-10.5H93v4.5l3.8 2.3.8-1.2-3.1-1.8V28z" fill="#8B949E" />
    <text x="94" y="68" class="stat-num">5</text>
    <text x="94" y="88" class="stat-label">YEARS ACTIVE</text>
  </g>
</svg>"""

with open(ASSETS_DIR / "quick-stats.svg", "w", encoding="utf-8") as f:
  f.write(quick_stats_svg)
print("Saved assets/quick-stats.svg")

# Generate welcome-banner.svg
welcome_banner_svg = """<svg width="800" height="90" viewBox="0 0 800 90" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg { fill: #0D1117; stroke: #30363D; stroke-width: 1; rx: 8px; }
      .greeting { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 19px; font-weight: 700; fill: #F0F6FC; }
      .subtext { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 400; fill: #8B949E; }
      .tag { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 600; fill: #388BFD; }
      .tag-bg { fill: #388BFD15; stroke: #388BFD40; stroke-width: 1; rx: 12px; }
    </style>
  </defs>

  <rect x="1" y="1" width="798" height="88" rx="8" class="card-bg" />

  <g transform="translate(24, 34)">
    <text x="0" y="0" class="greeting">Welcome to Ramadhan Imanur's Hub</text>
    <text x="0" y="24" class="subtext">Explore open source contributions, mathematical modeling, and data science research</text>
  </g>

  <!-- Tag / Badge Right -->
  <g transform="translate(640, 32)">
    <rect x="0" y="0" width="136" height="26" rx="13" class="tag-bg" />
    <circle cx="14" cy="13" r="4" fill="#2EA043" />
    <text x="26" y="17" class="tag">Active Portfolio</text>
  </g>
</svg>"""

with open(ASSETS_DIR / "welcome-banner.svg", "w", encoding="utf-8") as f:
  f.write(welcome_banner_svg)
print("Saved assets/welcome-banner.svg")

# Generate core-tech.svg matching languages-donut.svg size (350x215)
core_tech_svg = """<svg width="350" height="215" viewBox="0 0 350 215" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .card-bg { fill: #0D1117; stroke: #30363D; stroke-width: 1; rx: 4.5px; }
      .header { font: 600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: #8B949E; text-transform: uppercase; letter-spacing: 0.8px; }
      .badge-bg { fill: #161B22; stroke: #30363D; stroke-width: 1; rx: 12px; }
      .badge-text { font: 500 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', Ubuntu, Sans-Serif; fill: #C9D1D9; }
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
    <circle cx="12" cy="13" r="4" fill="#FCC624" />
    <text x="24" y="17" class="badge-text">Linux</text>
  </g>

  <g transform="translate(106, 160)">
    <rect x="0" y="0" width="98" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#F1E05A" />
    <text x="24" y="17" class="badge-text">JavaScript</text>
  </g>

  <g transform="translate(212, 160)">
    <rect x="0" y="0" width="116" height="26" rx="13" class="badge-bg" />
    <circle cx="12" cy="13" r="4" fill="#2EA043" />
    <text x="24" y="17" class="badge-text">SARIMA/Markov</text>
  </g>
</svg>"""

with open(ASSETS_DIR / "core-tech.svg", "w", encoding="utf-8") as f:
  f.write(core_tech_svg)
print("Saved assets/core-tech.svg")

# Fetch and save languages donut
print("Fetching donut chart...")
donut_url = "https://github-readme-stats.vercel.app/api/top-langs/?username=ramadhan-imanur&layout=donut&theme=dark&bg_color=0D1117&border_color=30363D&title_color=E6EDF3&text_color=8B949E"
req_donut = urllib.request.Request(donut_url, headers={"User-Agent": "Mozilla/5.0"})
try:
  donut_data = urllib.request.urlopen(req_donut, timeout=10).read()
  with open(ASSETS_DIR / "languages-donut.svg", "wb") as f:
    f.write(donut_data)
  print("Saved assets/languages-donut.svg")
except Exception as e:
  print("Error fetching donut chart:", e)

print("All assets generated successfully!")
