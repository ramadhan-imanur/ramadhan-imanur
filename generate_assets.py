import datetime
from html.parser import HTMLParser
from pathlib import Path
import shutil
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
        parts = cleaned.replace("contributions", "").split()
        self.total_contrib = f"{parts[0]} in the last year"

  def handle_data(self, data):
    if self.in_h2:
      self.h2_text += data


parser = CalParser()
parser.feed(html_data)
print(f"Parsed {len(parser.days)} days. Total: {parser.total_contrib}")

# Parse grid rows directly from <tr> tags (rows 1..7 for Sun..Sat)
import re

table_rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html_data, re.DOTALL)
grid_rows = []
for r in table_rows[1:]:
  days = re.findall(
      r'<td[^>]*data-date=\"([^\"]+)\"[^>]*data-level=\"([^\"]+)\"', r
  )
  if days:
    grid_rows.append(days)

# We have 7 rows (row 0 = Sun, 1 = Mon, ..., 6 = Sat). Keep the last 52 weeks.
max_cols = max(len(r) for r in grid_rows) if grid_rows else 0
if max_cols > 52:
  grid_rows = [r[-52:] for r in grid_rows]


def build_contributions_svg(theme="dark"):
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
      cells_svg.append(
          f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}"'
          f' rx="2" fill="{color}" />'
      )

  # Day labels on the left
  days_labels_svg = []
  days_map = {1: "Mon", 3: "Wed", 5: "Fri"}
  for r_idx, label in days_map.items():
    y = start_y + r_idx * (cell_size + cell_gap) + 8
    days_labels_svg.append(
        f'<text x="{start_x - 10}" y="{y}" text-anchor="end"'
        f' fill="{text_color}" font-size="10"'
        ' font-family="-apple-system,BlinkMacSystemFont,\'Segoe'
        ' UI\',Helvetica,Arial,sans-serif">'
        f"{label}</text>"
    )

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
  <text x="{svg_width - 24}" y="38" text-anchor="end" class="subtitle">{parser.total_contrib}</text>

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


def build_welcome_banner_svg(theme="dark"):
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
      .greeting {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 19px; font-weight: 700; fill: {title_color}; }}
      .subtext {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 13px; font-weight: 400; fill: {text_color}; }}
      .tag {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 600; fill: {tag_text}; }}
      .tag-bg {{ fill: {tag_bg}; stroke: {tag_border}; stroke-width: 1; rx: 12px; }}
    </style>
  </defs>

  <rect x="1" y="1" width="798" height="88" rx="8" class="card-bg" />

  <g transform="translate(24, 34)">
    <text x="0" y="0" class="greeting">Welcome to Ramadhan Imanur's Hub</text>
    <text x="0" y="24" class="subtext">Explore open source contributions, mathematical modeling, and data science research</text>
  </g>

  <g transform="translate(640, 32)">
    <rect x="0" y="0" width="136" height="26" rx="13" class="tag-bg" />
    <circle cx="14" cy="13" r="4" fill="{dot_color}" />
    <text x="26" y="17" class="tag">Active Portfolio</text>
  </g>
</svg>"""


def build_quick_stats_svg(theme="dark"):
  is_dark = theme == "dark"
  bg_card = "#0D1117" if is_dark else "#FFFFFF"
  border_card = "#30363D" if is_dark else "#D0D7DE"
  num_color = "#F0F6FC" if is_dark else "#1F2328"
  label_color = "#8B949E" if is_dark else "#656D76"
  icon_color = "#8B949E" if is_dark else "#656D76"

  return f"""<svg width="800" height="110" viewBox="0 0 800 110" fill="none" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .stat-card {{ fill: {bg_card}; stroke: {border_card}; stroke-width: 1; rx: 8px; }}
      .stat-num {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 24px; font-weight: 700; fill: {num_color}; text-anchor: middle; }}
      .stat-label {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 11px; font-weight: 600; fill: {label_color}; text-anchor: middle; letter-spacing: 0.8px; }}
    </style>
  </defs>

  <!-- Card 1: Total Repos -->
  <g transform="translate(0, 0)">
    <rect x="1" y="1" width="188" height="108" rx="8" class="stat-card" />
    <path d="M94 24h-10c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2v-11c0-1.1-.9-2-2-2h-5l-1.5-1.5c-.4-.4-.9-.5-1.5-.5z" fill="{icon_color}" />
    <text x="95" y="68" class="stat-num">11+</text>
    <text x="95" y="88" class="stat-label">TOTAL REPOS</text>
  </g>

  <!-- Card 2: Contributions -->
  <g transform="translate(204, 0)">
    <rect x="1" y="1" width="188" height="108" rx="8" class="stat-card" />
    <path d="M95 24l2.5 5 5.5.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.5-.8 2.5-5z" fill="{icon_color}" />
    <text x="95" y="68" class="stat-num">98+</text>
    <text x="95" y="88" class="stat-label">ANNUAL COMMITS</text>
  </g>

  <!-- Card 3: Followers -->
  <g transform="translate(408, 0)">
    <rect x="1" y="1" width="188" height="108" rx="8" class="stat-card" />
    <path d="M91 30a3.5 3.5 0 100-7 3.5 3.5 0 000 7zm8 0a3 3 0 100-6 3 3 0 000 6zm-8 3c-2.3 0-7 1.2-7 3.5V39h14v-2.5c0-2.3-4.7-3.5-7-3.5zm8 0c-.3 0-.7 0-1.1.1 1.3.9 2.1 2.1 2.1 3.4V39h6v-2.5c0-2.3-4.7-3.5-7-3.5z" fill="{icon_color}" />
    <text x="95" y="68" class="stat-num">2+</text>
    <text x="95" y="88" class="stat-label">FOLLOWERS</text>
  </g>

  <!-- Card 4: Years Active -->
  <g transform="translate(612, 0)">
    <rect x="1" y="1" width="187" height="108" rx="8" class="stat-card" />
    <path d="M94 24a8 8 0 100 16 8 8 0 000-16zm0 14.5a6.5 6.5 0 110-13 6.5 6.5 0 010 13zm.5-10.5H93v4.5l3.8 2.3.8-1.2-3.1-1.8V28z" fill="{icon_color}" />
    <text x="94" y="68" class="stat-num">5</text>
    <text x="94" y="88" class="stat-label">YEARS ACTIVE</text>
  </g>
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


# Write Dark SVGs
with open(ASSETS_DIR / "welcome-banner-dark.svg", "w", encoding="utf-8") as f:
  f.write(build_welcome_banner_svg("dark"))
with open(ASSETS_DIR / "quick-stats-dark.svg", "w", encoding="utf-8") as f:
  f.write(build_quick_stats_svg("dark"))
with open(ASSETS_DIR / "contributions-dark.svg", "w", encoding="utf-8") as f:
  f.write(build_contributions_svg("dark"))
with open(ASSETS_DIR / "core-tech-dark.svg", "w", encoding="utf-8") as f:
  f.write(build_core_tech_svg("dark"))

# Write Light SVGs
with open(ASSETS_DIR / "welcome-banner-light.svg", "w", encoding="utf-8") as f:
  f.write(build_welcome_banner_svg("light"))
with open(ASSETS_DIR / "quick-stats-light.svg", "w", encoding="utf-8") as f:
  f.write(build_quick_stats_svg("light"))
with open(ASSETS_DIR / "contributions-light.svg", "w", encoding="utf-8") as f:
  f.write(build_contributions_svg("light"))
with open(ASSETS_DIR / "core-tech-light.svg", "w", encoding="utf-8") as f:
  f.write(build_core_tech_svg("light"))

# Fallbacks
shutil.copyfile(
    ASSETS_DIR / "welcome-banner-dark.svg", ASSETS_DIR / "welcome-banner.svg"
)
shutil.copyfile(
    ASSETS_DIR / "quick-stats-dark.svg", ASSETS_DIR / "quick-stats.svg"
)
shutil.copyfile(
    ASSETS_DIR / "contributions-dark.svg", ASSETS_DIR / "contributions.svg"
)
shutil.copyfile(ASSETS_DIR / "core-tech-dark.svg", ASSETS_DIR / "core-tech.svg")

# Fetch Donut Charts (Dark & Light)
print("Fetching Dark Donut chart...")
dark_donut_url = "https://github-readme-stats.vercel.app/api/top-langs/?username=ramadhan-imanur&layout=donut&theme=dark&bg_color=0D1117&border_color=30363D&title_color=E6EDF3&text_color=8B949E"
req_dark = urllib.request.Request(
    dark_donut_url, headers={"User-Agent": "Mozilla/5.0"}
)
try:
  donut_dark = urllib.request.urlopen(req_dark, timeout=10).read()
  with open(ASSETS_DIR / "languages-donut-dark.svg", "wb") as f:
    f.write(donut_dark)
  with open(ASSETS_DIR / "languages-donut.svg", "wb") as f:
    f.write(donut_dark)
  print("Saved assets/languages-donut-dark.svg")
except Exception as e:
  print("Error fetching dark donut:", e)

print("Fetching Light Donut chart...")
light_donut_url = "https://github-readme-stats.vercel.app/api/top-langs/?username=ramadhan-imanur&layout=donut&theme=default&bg_color=FFFFFF&border_color=D0D7DE&title_color=1F2328&text_color=656D76"
req_light = urllib.request.Request(
    light_donut_url, headers={"User-Agent": "Mozilla/5.0"}
)
try:
  donut_light = urllib.request.urlopen(req_light, timeout=10).read()
  with open(ASSETS_DIR / "languages-donut-light.svg", "wb") as f:
    f.write(donut_light)
  print("Saved assets/languages-donut-light.svg")
except Exception as e:
  print("Error fetching light donut:", e)

print("All theme assets generated successfully!")
