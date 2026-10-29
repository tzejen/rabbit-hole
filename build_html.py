"""
Builds the standalone, fully interactive index.html companion web player
for 《兔子洞筆記》 with embedded episode data for zero-config local file:// playback.
Supports:
1. Landing page with All Episodes (Newest to Oldest) and Series selector / tabs.
2. Clicking a series card or tab filters to that series view with cover, description, and series resources.
3. Clicking an episode row or series badge switches views or starts playing seamlessly.
4. Softcoded reference documents and credits per series.
5. URL hash navigation (#all, #cave01, #cave02).
"""

import os
import sys
import json
import shutil
import re
import glob

sys.stdout.reconfigure(encoding="utf-8")

DIST_DIR = r"G:\My Drive\NotebookLM\podcast_distribution"
JSON_PATH = os.path.join(DIST_DIR, "episodes.json")
HTML_PATH = os.path.join(DIST_DIR, "index.html")
DOCS_DIR = os.path.join(DIST_DIR, "docs")
CAVES_TXT_PATH = os.path.join(DIST_DIR, "caves.txt")
os.makedirs(DOCS_DIR, exist_ok=True)

# Load base episodes.json
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# 1. Softcoded Series Credits (from active series)
series_credits = ""
for s_item in data.get("series", []):
    s_dir = s_item.get("dir", "")
    c_path = os.path.join(s_dir, "credits.txt")
    if os.path.exists(c_path):
        with open(c_path, "r", encoding="utf-8") as f:
            series_credits += f.read().strip() + "\n\n"
data["series_credits"] = series_credits.strip()

# 2. Softcoded Reference Documents (auto-scanned from all registered Series/References/)
ref_docs_list = []
series_docs_content = {}

ALLOWED_EXTENSIONS = {".md", ".pdf", ".docx", ".txt", ".html", ".epub"}
SYSTEM_IGNORE_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}
active_doc_filenames = set()

for s_item in data.get("series", []):
    s_dir = s_item.get("dir", "")
    s_prefix = s_item.get("id", "series")
    s_name = s_item.get("cave_number", "")
    ref_src_dir = os.path.join(s_dir, "References")

    if os.path.exists(ref_src_dir):
        raw_files = sorted(glob.glob(os.path.join(ref_src_dir, "*")))
        for fpath in raw_files:
            if not os.path.isfile(fpath):
                continue
            fname = os.path.basename(fpath)
            dst_fname = f"{s_prefix}_{fname}"
            active_doc_filenames.add(dst_fname)
            base_name, ext = os.path.splitext(fname)
            ext_lower = ext.lower()

            if fname.lower() in SYSTEM_IGNORE_FILES or fname.startswith(".") or fname.startswith("_") or fname.startswith("~$"):
                continue
            if ext_lower not in ALLOWED_EXTENSIONS:
                continue

            clean_title = re.sub(r"^\d+[\._\-\s]*", "", base_name).strip()
            display_title = f"[{s_name}] {clean_title}"
            doc_id = re.sub(r"[^\w\-]", "_", f"{s_prefix}_{base_name}").lower()

            dst_path = os.path.join(DOCS_DIR, dst_fname)
            shutil.copy2(fpath, dst_path)

            doc_info = {
                "id": doc_id,
                "title": display_title,
                "filename": dst_fname,
                "series_id": s_item.get("id"),
                "ext": ext_lower,
                "is_pdf": (ext_lower == ".pdf"),
                "is_download": (ext_lower in [".docx", ".epub"]),
                "url": f"docs/{dst_fname}"
            }

            if ext_lower in [".md", ".txt", ".json"]:
                try:
                    with open(fpath, "r", encoding="utf-8") as fp:
                        series_docs_content[doc_id] = fp.read()
                except Exception:
                    series_docs_content[doc_id] = ""

            ref_docs_list.append(doc_info)

if os.path.exists(DOCS_DIR):
    for existing_doc in os.listdir(DOCS_DIR):
        if existing_doc not in active_doc_filenames:
            try:
                os.remove(os.path.join(DOCS_DIR, existing_doc))
            except Exception:
                pass

data["ref_docs_list"] = ref_docs_list
data["series_docs_content"] = series_docs_content

# Clean summaries
for ep in data["episodes"]:
    ep["summary"] = ep["summary"].replace("Created with Gemini Antigravity and Google Notebook", "").strip()
    ep["full_notes"] = ep["full_notes"].replace("Created with Gemini Antigravity and Google Notebook", "").strip()

data_json_str = json.dumps(data, ensure_ascii=False)

html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>兔子洞筆記 — 隨選隨聽客廳</title>
  <meta name="description" content="兔子洞筆記 (Notes from the Rabbit Hole)">
  <link rel="icon" type="image/png" href="cover_channel.png">
  <style>
    :root {{
      --bg-midnight: #0b1120;
      --bg-card: #131d35;
      --bg-card-hover: #192745;
      --bg-player: #0f172a;
      --gold-primary: #d4af37;
      --gold-light: #f3d478;
      --gold-dim: #997e29;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --border-color: rgba(212, 175, 55, 0.2);
      --border-focus: rgba(212, 175, 55, 0.5);
      --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Noto Sans TC", "Microsoft JhengHei", sans-serif;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: var(--font-stack);
      background-color: var(--bg-midnight);
      color: var(--text-main);
      line-height: 1.6;
      padding-bottom: 140px;
      min-height: 100vh;
    }}

    a {{
      color: var(--gold-light);
      text-decoration: none;
      transition: color 0.2s;
    }}
    a:hover {{
      color: var(--gold-primary);
      text-decoration: underline;
    }}

    .container {{
      max-width: 1060px;
      margin: 0 auto;
      padding: 0 24px;
    }}

    /* Top Sticky/Fixed Header Bar */
    .site-header {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(11, 17, 32, 0.94);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--border-color);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }}
    .header-content {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 0;
    }}
    .brand-group {{
      display: flex;
      align-items: center;
      gap: 14px;
      cursor: pointer;
    }}
    .brand-avatar {{
      width: 44px;
      height: 44px;
      border-radius: 10px;
      object-fit: cover;
      border: 1px solid var(--border-color);
    }}
    .brand-title {{
      font-size: 19px;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: 0.5px;
    }}
    .brand-subtitle {{
      font-size: 12px;
      color: var(--gold-light);
      font-weight: 400;
      margin-top: 1px;
    }}
    .header-actions {{
      display: flex;
      gap: 10px;
    }}
    .btn {{
      padding: 7px 16px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s;
      border: 1px solid transparent;
      outline: none;
    }}
    .btn-gold {{
      background: linear-gradient(135deg, var(--gold-primary) 0%, var(--gold-dim) 100%);
      color: #0b1120;
      font-weight: 600;
    }}
    .btn-gold:hover {{
      background: linear-gradient(135deg, var(--gold-light) 0%, var(--gold-primary) 100%);
      box-shadow: 0 0 12px rgba(212, 175, 55, 0.4);
      text-decoration: none;
    }}
    .btn-outline {{
      background: transparent;
      border-color: var(--border-color);
      color: var(--text-main);
    }}
    .btn-outline:hover {{
      border-color: var(--gold-primary);
      color: var(--gold-light);
      background: rgba(212, 175, 55, 0.05);
      text-decoration: none;
    }}

    /* Series Navigation Tabs */
    .nav-tabs-bar {{
      display: flex;
      gap: 10px;
      margin: 24px 0 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      overflow-x: auto;
      scrollbar-width: thin;
    }}
    .tab-pill {{
      padding: 8px 18px;
      border-radius: 20px;
      font-size: 14px;
      font-weight: 500;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      transition: all 0.2s;
    }}
    .tab-pill:hover {{
      background: var(--bg-card-hover);
      color: var(--gold-light);
      border-color: var(--gold-light);
    }}
    .tab-pill.active {{
      background: linear-gradient(135deg, rgba(212, 175, 55, 0.2) 0%, rgba(212, 175, 55, 0.05) 100%);
      color: var(--gold-light);
      border-color: var(--gold-primary);
      font-weight: 600;
      box-shadow: 0 0 10px rgba(212, 175, 55, 0.2);
    }}
    .tab-badge {{
      font-size: 11px;
      padding: 2px 7px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.1);
      color: var(--text-main);
    }}
    .tab-pill.active .tab-badge {{
      background: var(--gold-primary);
      color: #0b1120;
      font-weight: 700;
    }}

    /* Series Cards Overview Grid (Landing View) */
    .series-overview-section {{
      margin-bottom: 32px;
    }}
    .section-heading {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 16px;
    }}
    .section-title {{
      font-size: 20px;
      font-weight: 700;
      color: #ffffff;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .section-subtitle {{
      font-size: 13px;
      color: var(--text-dim);
    }}
    .series-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 18px;
    }}
    .series-promo-card {{
      background: linear-gradient(145deg, #131d35 0%, #172442 100%);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 20px;
      display: flex;
      gap: 18px;
      cursor: pointer;
      transition: all 0.25s ease;
      position: relative;
      overflow: hidden;
    }}
    .series-promo-card:hover {{
      transform: translateY(-3px);
      border-color: var(--gold-primary);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
    }}
    .series-promo-cover {{
      width: 100px;
      height: 100px;
      border-radius: 12px;
      object-fit: cover;
      flex-shrink: 0;
      border: 1px solid var(--border-color);
      box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    }}
    .series-promo-body {{
      flex: 1;
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .series-promo-cave {{
      font-size: 11px;
      font-weight: 700;
      color: var(--gold-primary);
      letter-spacing: 0.5px;
      text-transform: uppercase;
      margin-bottom: 4px;
    }}
    .series-promo-title {{
      font-size: 16px;
      font-weight: 700;
      color: #ffffff;
      line-height: 1.35;
      margin-bottom: 6px;
    }}
    .series-promo-desc {{
      font-size: 12px;
      color: var(--text-muted);
      line-height: 1.5;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      margin-bottom: 8px;
    }}
    .series-promo-footer {{
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 12px;
      color: var(--text-dim);
    }}
    .series-promo-footer b {{
      color: var(--gold-light);
    }}

    /* Series Hero Banner (Dedicated Series View) */
    .hero-banner {{
      background: linear-gradient(145deg, #131d35 0%, #172442 100%);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      padding: 26px 28px;
      margin-bottom: 24px;
      display: flex;
      gap: 28px;
      align-items: center;
      box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }}
    .hero-cover {{
      width: 170px;
      height: 170px;
      border-radius: 16px;
      object-fit: cover;
      box-shadow: 0 8px 24px rgba(0,0,0,0.6);
      border: 1px solid var(--border-color);
      flex-shrink: 0;
    }}
    .hero-info {{
      flex: 1;
      min-width: 0;
    }}
    .hero-cave-tag {{
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      color: var(--gold-primary);
      background: rgba(212, 175, 55, 0.12);
      border: 1px solid rgba(212, 175, 55, 0.3);
      padding: 3px 10px;
      border-radius: 12px;
      margin-bottom: 8px;
    }}
    .hero-title {{
      font-size: 24px;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 10px;
      line-height: 1.3;
    }}
    .hero-desc {{
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.6;
      margin-bottom: 14px;
    }}
    .hero-stats {{
      display: flex;
      align-items: center;
      gap: 20px;
      font-size: 13px;
      color: var(--text-dim);
      margin-bottom: 12px;
      flex-wrap: wrap;
    }}
    .stat-item b {{
      color: var(--gold-light);
      font-weight: 600;
    }}

    .hero-credits {{
      font-size: 12px;
      color: var(--gold-light);
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}

    .series-resources {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .resources-label {{
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 600;
    }}
    .resources-pills-wrap {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .resource-pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--border-color);
      color: var(--text-main);
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .resource-pill:hover {{
      background: rgba(212, 175, 55, 0.15);
      border-color: var(--gold-primary);
      color: var(--gold-light);
      text-decoration: none;
    }}

    /* Episodes List */
    .episodes-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .episode-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 14px;
      padding: 16px 20px;
      transition: all 0.2s ease;
    }}
    .episode-card:hover {{
      background: var(--bg-card-hover);
      border-color: var(--border-focus);
    }}
    .episode-card.is-playing {{
      border-color: var(--gold-primary);
      background: rgba(212, 175, 55, 0.06);
    }}
    .ep-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
    }}
    .ep-main-info {{
      display: flex;
      align-items: center;
      gap: 16px;
      flex: 1;
      cursor: pointer;
      min-width: 0;
    }}
    .ep-play-col {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }}
    .ep-play-btn {{
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: rgba(212, 175, 55, 0.12);
      border: 1px solid var(--border-color);
      color: var(--gold-primary);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s;
    }}
    .episode-card:hover .ep-play-btn {{
      background: var(--gold-primary);
      color: #0b1120;
      transform: scale(1.05);
    }}
    .episode-card.is-playing .ep-play-btn {{
      background: var(--gold-primary);
      color: #0b1120;
    }}
    .ep-duration-tag {{
      font-size: 11px;
      color: var(--text-dim);
      font-family: monospace;
    }}
    .ep-text-block {{
      flex: 1;
      min-width: 0;
    }}
    .ep-series-badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 600;
      color: var(--gold-primary);
      margin-bottom: 2px;
      cursor: pointer;
    }}
    .ep-series-badge:hover {{
      text-decoration: underline;
    }}
    .ep-title {{
      font-size: 16px;
      font-weight: 600;
      color: var(--text-main);
      line-height: 1.4;
    }}
    .episode-card.is-playing .ep-title {{
      color: var(--gold-light);
    }}
    .ep-toggle-btn {{
      background: transparent;
      border: 1px solid rgba(255,255,255,0.1);
      color: var(--text-muted);
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 12px;
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.2s;
    }}
    .ep-toggle-btn:hover {{
      border-color: var(--gold-primary);
      color: var(--gold-light);
    }}
    .ep-details {{
      display: none;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid rgba(255,255,255,0.06);
    }}
    .ep-details.show {{
      display: block;
    }}
    .ep-summary-text {{
      font-size: 13.5px;
      color: var(--text-muted);
      line-height: 1.6;
      margin-bottom: 12px;
    }}
    .chapters-title {{
      font-size: 12px;
      color: var(--gold-light);
      margin-bottom: 8px;
      font-weight: 600;
    }}
    .chapters-grid {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .chapter-pill {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 6px;
      padding: 4px 10px;
      font-size: 12px;
      display: flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
      transition: all 0.2s;
    }}
    .chapter-pill:hover {{
      background: rgba(212, 175, 55, 0.15);
      border-color: var(--gold-primary);
      color: var(--gold-light);
    }}
    .chapter-time {{
      font-family: monospace;
      color: var(--gold-dim);
      font-size: 11px;
    }}

    /* Bottom Persistent Audio Player */
    .bottom-player {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: rgba(15, 23, 42, 0.96);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-top: 1px solid var(--border-color);
      padding: 12px 24px;
      box-shadow: 0 -4px 30px rgba(0, 0, 0, 0.6);
      z-index: 200;
    }}
    .player-inner {{
      max-width: 1060px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      gap: 20px;
    }}
    .track-info {{
      display: flex;
      align-items: center;
      gap: 12px;
      width: 260px;
      min-width: 0;
    }}
    .track-thumb {{
      width: 48px;
      height: 48px;
      border-radius: 8px;
      object-fit: cover;
      border: 1px solid var(--border-color);
      flex-shrink: 0;
    }}
    .track-text {{
      min-width: 0;
    }}
    .track-title {{
      font-size: 14px;
      font-weight: 600;
      color: #ffffff;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .track-artist {{
      font-size: 12px;
      color: var(--gold-light);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .player-center {{
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 6px;
    }}
    .controls-row {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .ctrl-btn {{
      background: transparent;
      border: none;
      color: var(--text-muted);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: color 0.2s;
    }}
    .ctrl-btn:hover {{
      color: var(--gold-light);
    }}
    .ctrl-btn-play {{
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: var(--gold-primary);
      color: #0b1120;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      border: none;
      transition: transform 0.2s, background 0.2s;
    }}
    .ctrl-btn-play:hover {{
      transform: scale(1.08);
      background: var(--gold-light);
    }}
    .progress-row {{
      width: 100%;
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .time-label {{
      font-size: 11px;
      font-family: monospace;
      color: var(--text-dim);
      width: 42px;
      text-align: center;
    }}
    .progress-bar {{
      flex: 1;
      height: 6px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 3px;
      cursor: pointer;
      position: relative;
      overflow: hidden;
    }}
    .progress-fill {{
      height: 100%;
      background: var(--gold-primary);
      border-radius: 3px;
      width: 0%;
      transition: width 0.1s linear;
    }}
    .player-right {{
      display: flex;
      align-items: center;
      gap: 12px;
      width: 120px;
      justify-content: flex-end;
    }}
    .speed-btn {{
      background: rgba(255,255,255,0.06);
      border: 1px solid var(--border-color);
      color: var(--gold-light);
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 12px;
      font-family: monospace;
      cursor: pointer;
    }}

    /* Modals */
    .modal-backdrop {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(8px);
      z-index: 300;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .modal-backdrop.active {{
      display: flex;
    }}
    .modal-window {{
      background: #131d35;
      border: 1px solid var(--border-color);
      border-radius: 18px;
      width: 100%;
      max-width: 580px;
      max-height: 85vh;
      overflow-y: auto;
      padding: 28px;
      box-shadow: 0 20px 50px rgba(0,0,0,0.8);
      position: relative;
    }}
    .modal-close {{
      position: absolute;
      top: 18px;
      right: 20px;
      background: transparent;
      border: none;
      color: var(--text-dim);
      font-size: 24px;
      cursor: pointer;
    }}
    .modal-close:hover {{
      color: #ffffff;
    }}
    .modal-title {{
      font-size: 20px;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 12px;
    }}
    .modal-desc {{
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.6;
      margin-bottom: 18px;
    }}
    .feed-box {{
      display: flex;
      gap: 8px;
      margin-bottom: 20px;
    }}
    .feed-input {{
      flex: 1;
      background: #0b1120;
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 10px 14px;
      color: var(--gold-light);
      font-family: monospace;
      font-size: 13px;
    }}
    .steps-list {{
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.8;
      padding-left: 20px;
    }}
    .steps-list b {{
      color: #ffffff;
    }}

    .toast {{
      position: fixed;
      top: 20px;
      left: 50%;
      transform: translateX(-50%);
      background: var(--gold-primary);
      color: #0b1120;
      padding: 10px 24px;
      border-radius: 20px;
      font-weight: 600;
      font-size: 14px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
      z-index: 400;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.3s;
    }}
    .toast.show {{
      opacity: 1;
    }}

    .pre-box {{
      background: #0b1120;
      border: 1px solid var(--border-color);
      border-radius: 10px;
      padding: 16px;
      font-size: 13px;
      color: var(--text-main);
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.7;
      max-height: 60vh;
      overflow-y: auto;
      font-family: var(--font-stack);
    }}

    @media (max-width: 768px) {{
      .hero-banner {{
        flex-direction: column;
        text-align: center;
        padding: 20px;
      }}
      .hero-cover {{
        width: 140px;
        height: 140px;
      }}
      .hero-stats {{
        justify-content: center;
      }}
      .series-resources {{
        justify-content: center;
      }}
      .track-info {{
        width: 160px;
      }}
      .track-thumb {{
        display: none;
      }}
      .player-right {{
        display: none;
      }}
    }}
  </style>
</head>
<body>

  <div id="toast" class="toast">已複製到剪貼簿！</div>

  <header class="site-header">
    <div class="container">
      <div class="header-content">
        <div class="brand-group" onclick="selectSeries('all')">
          <img src="cover_channel.png" alt="兔子洞筆記封面" class="brand-avatar">
          <div>
            <div class="brand-title">兔子洞筆記</div>
            <div class="brand-subtitle">Notes from the Rabbit Hole</div>
          </div>
        </div>
        <div class="header-actions">
          <button class="btn btn-outline" onclick="openSubscribeModal('all')">
            <span>📡 總頻道 RSS</span>
          </button>
          <button class="btn btn-gold" id="headerSeriesFeedBtn" onclick="openCurrentSeriesFeed()">
            <span>🎙️ 訂閱本專案</span>
          </button>
        </div>
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Series Navigation Tabs -->
    <nav class="nav-tabs-bar" id="seriesTabsBar"></nav>

    <!-- Top Series Overview Section (Only on 'All Episodes' view) -->
    <section class="series-overview-section" id="seriesOverviewSection">
      <div class="section-heading">
        <div class="section-title">
          <span>🏛️</span> <span>探索洞窟系列</span>
        </div>
        <div class="section-subtitle">點擊卡片進入專題導覽與文獻</div>
      </div>
      <div class="series-grid" id="seriesCardsGrid"></div>
    </section>

    <!-- Hero Banner (Only shown in dedicated series view) -->
    <section class="hero-banner" id="seriesHeroBanner" style="display: none;">
      <img id="heroCoverImg" src="assets/cover_cave01.jpg" alt="系列封面" class="hero-cover">
      <div class="hero-info">
        <div class="hero-cave-tag" id="heroCaveTag">第一窟</div>
        <h1 class="hero-title" id="heroTitle">系列標題</h1>
        <p class="hero-desc" id="heroDesc">系列簡介說明</p>
        <div class="hero-stats" id="heroStats">
          <div class="stat-item">集數：<b id="heroStatCount">0 集</b></div>
          <div class="stat-item">總長：<b id="heroStatDur">0 分鐘</b></div>
          <div class="stat-item">狀態：<b id="heroStatStatus">已上線</b></div>
        </div>

        <div class="hero-credits" id="heroCreditsContainer"></div>

        <div class="series-resources" id="seriesResourcesBox">
          <span class="resources-label">📚 系列資料庫：</span>
          <div class="resources-pills-wrap" id="resourcesPillsWrap"></div>
        </div>
      </div>
    </section>

    <!-- Episodes Section Header -->
    <div class="section-heading" style="margin-top: 10px;">
      <div class="section-title">
        <span id="episodesListIcon">🎙️</span> <span id="episodesListHeading">所有單集</span>
      </div>
      <div class="section-subtitle" id="episodesListSubheading">最新至最舊排序</div>
    </div>

    <!-- Episodes List -->
    <div class="episodes-list" id="episodesList"></div>
  </div>

  <!-- Bottom Audio Player -->
  <div class="bottom-player" id="bottomPlayer">
    <div class="player-inner">
      <div class="track-info">
        <img id="playerThumb" src="assets/cover_channel_1400.jpg" class="track-thumb" alt="封面">
        <div class="track-text">
          <div class="track-title" id="playerTitle">點擊任一單集開始收聽</div>
          <div class="track-artist" id="playerArtist">兔子洞筆記</div>
        </div>
      </div>

      <div class="player-center">
        <div class="controls-row">
          <button class="ctrl-btn" onclick="playPrev()" title="上一集">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
          </button>
          <button class="ctrl-btn" onclick="skipTime(-15)" title="倒退 15 秒">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M12.5 8c-2.65 0-5.05.99-6.9 2.6L2 7v9h9l-3.62-3.62c1.39-1.2 3.16-1.98 5.12-1.98 3.53 0 6.51 2.37 7.42 5.62l2.38-.79C20.81 11.23 17.03 8 12.5 8z"/></svg>
          </button>
          <button class="ctrl-btn-play" id="playBtn" onclick="togglePlay()" title="播放/暫停">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6,4 20,12 6,20"/></svg>
          </button>
          <button class="ctrl-btn" onclick="skipTime(30)" title="快進 30 秒">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M11.5 8c2.65 0 5.05.99 6.9 2.6L22 7v9h-9l3.62-3.62c-1.39-1.2-3.16-1.98-5.12-1.98-3.53 0-6.51 2.37-7.42 5.62l-2.38-.79C3.19 11.23 6.97 8 11.5 8z"/></svg>
          </button>
          <button class="ctrl-btn" onclick="playNext()" title="下一集">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
          </button>
        </div>

        <div class="progress-row">
          <span class="time-label" id="currentTime">00:00</span>
          <div class="progress-bar" id="progressBar" onclick="seek(event)">
            <div class="progress-fill" id="progressFill"></div>
          </div>
          <span class="time-label" id="totalDuration">00:00</span>
        </div>
      </div>

      <div class="player-right">
        <button class="speed-btn" id="speedBtn" onclick="cycleSpeed()">1.0x</button>
      </div>
    </div>
  </div>

  <audio id="audioElement" preload="metadata"></audio>

  <!-- Combined Subscribe Modal -->
  <div class="modal-backdrop" id="subscribeModal" onclick="closeModal('subscribeModal')">
    <div class="modal-window" onclick="event.stopPropagation()">
      <button class="modal-close" onclick="closeModal('subscribeModal')">&times;</button>
      <div class="modal-title" id="subscribeModalTitle">訂閱《兔子洞筆記》</div>
      <p class="modal-desc" id="subscribeModalDesc">
        複製下方的私人 Podcast RSS 訂閱連結，在任何你常用的播客 App 內貼上即可完成訂閱。
      </p>
      <div class="feed-box">
        <input type="text" id="modalFeedInput" class="feed-input" readonly value="">
        <button class="btn btn-gold" style="padding: 6px 14px; font-size: 13px;" onclick="copyModalFeed()">複製連結</button>
      </div>
      <h4 style="font-size: 14px; color: var(--gold-light); margin-bottom: 8px;">如何在 App 中貼上網址？</h4>
      <ol class="steps-list">
        <li><b>Apple Podcasts</b>：打開 App $\rightarrow$ 點擊下方「資料庫」 $\rightarrow$ 點右上角「...」 $\rightarrow$ 選擇「透過 URL 追蹤節目」並貼上。</li>
        <li><b>Pocket Casts / Overcast</b>：直接在頂部搜尋欄貼上這段網址並按搜尋。</li>
        <li>未來更新的所有新集數，都會自動在你的手機背景同步下載！</li>
      </ol>
    </div>
  </div>

  <!-- Resource Document Modal -->
  <div class="modal-backdrop" id="resourceModal" onclick="closeModal('resourceModal')">
    <div class="modal-window" style="max-width: 720px;" onclick="event.stopPropagation()">
      <button class="modal-close" onclick="closeModal('resourceModal')">&times;</button>
      <div class="modal-title" id="resourceModalTitle">📑 參考資料</div>
      <pre class="pre-box" id="resourceModalContent"></pre>
    </div>
  </div>

  <script>
    const PODCAST_DATA = {data_json_str};

    let activeFilter = 'all'; // 'all' or series_id ('cave01', 'cave02')
    let currentPlayingEp = null;
    let isPlaying = false;

    const audio = document.getElementById('audioElement');
    const playBtn = document.getElementById('playBtn');
    const playerTitle = document.getElementById('playerTitle');
    const playerArtist = document.getElementById('playerArtist');
    const playerThumb = document.getElementById('playerThumb');
    const currentTimeEl = document.getElementById('currentTime');
    const totalDurationEl = document.getElementById('totalDuration');
    const progressFill = document.getElementById('progressFill');
    const speedBtn = document.getElementById('speedBtn');

    const speeds = [1.0, 1.25, 1.5, 2.0];
    let currentSpeedIdx = 0;

    const SVG_PLAY = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="display:block;margin-left:2px;"><polygon points="6,4 20,12 6,20"/></svg>';
    const SVG_PAUSE = '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="display:block;"><rect x="5" y="4" width="4" height="16" rx="1"/><rect x="15" y="4" width="4" height="16" rx="1"/></svg>';
    const SVG_PLAY_LG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="display:block;margin-left:2px;"><polygon points="6,4 20,12 6,20"/></svg>';
    const SVG_PAUSE_LG = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style="display:block;"><rect x="5" y="4" width="4" height="16" rx="1"/><rect x="15" y="4" width="4" height="16" rx="1"/></svg>';

    function init() {{
      // Read initial filter from URL hash (#cave01, #cave02, or default 'all')
      const hash = window.location.hash.replace('#', '').trim();
      if (hash && (hash === 'all' || PODCAST_DATA.series.some(s => s.id === hash))) {{
        activeFilter = hash;
      }} else {{
        activeFilter = 'all';
      }}

      renderTabs();
      renderSeriesCards();
      renderView();
    }}

    window.addEventListener('hashchange', () => {{
      const hash = window.location.hash.replace('#', '').trim();
      if (hash && (hash === 'all' || PODCAST_DATA.series.some(s => s.id === hash))) {{
        if (activeFilter !== hash) {{
          activeFilter = hash;
          renderTabs();
          renderView();
        }}
      }}
    }});

    function selectSeries(seriesId) {{
      activeFilter = seriesId;
      window.location.hash = seriesId;
      renderTabs();
      renderView();
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    function renderTabs() {{
      const bar = document.getElementById('seriesTabsBar');
      const allCount = PODCAST_DATA.episodes.length;

      let html = `
        <div class="tab-pill ${{activeFilter === 'all' ? 'active' : ''}}" onclick="selectSeries('all')">
          <span>全部單集</span>
          <span class="tab-badge">${{allCount}}</span>
        </div>
      `;

      PODCAST_DATA.series.forEach(s => {{
        const sCount = PODCAST_DATA.episodes.filter(e => e.series_id === s.id).length;
        html += `
          <div class="tab-pill ${{activeFilter === s.id ? 'active' : ''}}" onclick="selectSeries('${{s.id}}')">
            <span>${{s.cave_number}}・${{s.title}}</span>
            <span class="tab-badge">${{sCount}}</span>
          </div>
        `;
      }});

      bar.innerHTML = html;
    }}

    function renderSeriesCards() {{
      const grid = document.getElementById('seriesCardsGrid');
      grid.innerHTML = PODCAST_DATA.series.map(s => {{
        const sEps = PODCAST_DATA.episodes.filter(e => e.series_id === s.id);
        const totalSec = sEps.reduce((acc, cur) => acc + (cur.duration_sec || 0), 0);
        const durHours = Math.round(totalSec / 3600 * 10) / 10;
        const durText = durHours >= 1 ? `${{durHours}} 小時` : `${{Math.round(totalSec/60)}} 分鐘`;

        return `
          <div class="series-promo-card" onclick="selectSeries('${{s.id}}')">
            <img src="assets/${{s.cover_dst_name}}" alt="${{s.title}}" class="series-promo-cover">
            <div class="series-promo-body">
              <div>
                <div class="series-promo-cave">${{s.cave_number}}</div>
                <div class="series-promo-title">${{s.title}}</div>
                <div class="series-promo-desc">${{s.description || '探索深度人文歷史與專題。'}}</div>
              </div>
              <div class="series-promo-footer">
                <span>集數：<b>${{sEps.length}} 集</b></span>
                <span>時長：<b>${{durText}}</b></span>
                <span>狀態：<b>${{s.status}}</b></span>
              </div>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function renderView() {{
      const overviewSec = document.getElementById('seriesOverviewSection');
      const heroBanner = document.getElementById('seriesHeroBanner');
      const headingIcon = document.getElementById('episodesListIcon');
      const headingText = document.getElementById('episodesListHeading');
      const subheading = document.getElementById('episodesListSubheading');
      const seriesFeedBtn = document.getElementById('headerSeriesFeedBtn');

      if (activeFilter === 'all') {{
        // Landing Mode: Show Series Overview + All Episodes (Newest to Oldest)
        overviewSec.style.display = 'block';
        heroBanner.style.display = 'none';
        headingIcon.textContent = '🎙️';
        headingText.textContent = '所有單集';
        subheading.textContent = '按發布時間排序（最新至最舊）';
        seriesFeedBtn.style.display = 'none';

        // Sort: newest first (cave02 before cave01)
        const sortedEps = [...PODCAST_DATA.episodes].sort((a, b) => {{
          return new Date(b.pub_date_iso || 0) - new Date(a.pub_date_iso || 0);
        }});
        renderEpisodesList(sortedEps);
      }} else {{
        // Series Mode: Hide overview, Show detailed Series Hero Banner
        overviewSec.style.display = 'none';
        heroBanner.style.display = 'flex';
        seriesFeedBtn.style.display = 'inline-flex';

        const curSeries = PODCAST_DATA.series.find(s => s.id === activeFilter);
        if (curSeries) {{
          document.getElementById('heroCoverImg').src = `assets/${{curSeries.cover_dst_name}}`;
          document.getElementById('heroCaveTag').textContent = curSeries.cave_number;
          document.getElementById('heroTitle').textContent = curSeries.title;
          document.getElementById('heroDesc').textContent = curSeries.description || '';

          const sEps = PODCAST_DATA.episodes.filter(e => e.series_id === curSeries.id);
          const totalSec = sEps.reduce((acc, cur) => acc + (cur.duration_sec || 0), 0);
          const durHours = Math.round(totalSec / 3600 * 10) / 10;
          const durText = durHours >= 1 ? `${{durHours}} 小時` : `${{Math.round(totalSec/60)}} 分鐘`;

          document.getElementById('heroStatCount').textContent = `${{sEps.length}} 集`;
          document.getElementById('heroStatDur').textContent = durText;
          document.getElementById('heroStatStatus').textContent = curSeries.status;

          headingIcon.textContent = '📖';
          headingText.textContent = `${{curSeries.cave_number}}・各集單集目錄`;
          subheading.textContent = `共 ${{sEps.length}} 集完整版`;

          // Render series resources
          renderSeriesResources(curSeries.id);

          // In dedicated series view, order sequentially 1..N
          const seriesEps = [...sEps].sort((a, b) => a.episode - b.episode);
          renderEpisodesList(seriesEps);
        }}
      }}
    }}

    function renderSeriesResources(seriesId) {{
      const box = document.getElementById('seriesResourcesBox');
      const wrap = document.getElementById('resourcesPillsWrap');
      const docs = (PODCAST_DATA.ref_docs_list || []).filter(d => d.series_id === seriesId);

      if (docs.length === 0) {{
        box.style.display = 'none';
        return;
      }}
      box.style.display = 'flex';
      wrap.innerHTML = docs.map(doc => {{
        if (doc.is_pdf) {{
          return `<a href="${{doc.url}}" target="_blank" class="resource-pill" title="查看 PDF 文件">📄 ${{doc.title}}</a>`;
        }} else if (doc.is_download) {{
          return `<a href="${{doc.url}}" download class="resource-pill" title="下載文件">📝 ${{doc.title}}</a>`;
        }} else {{
          return `<button class="resource-pill" onclick="openDocModal('${{doc.id}}', '${{doc.title}}')">📑 ${{doc.title}}</button>`;
        }}
      }}).join('');
    }}

    function renderEpisodesList(episodes) {{
      const list = document.getElementById('episodesList');
      list.innerHTML = episodes.map(ep => {{
        const isCurrentPlaying = (currentPlayingEp && currentPlayingEp.release_filename === ep.release_filename);
        return `
          <div class="episode-card ${{isCurrentPlaying ? 'is-playing' : ''}}" id="card-${{ep.release_filename}}">
            <div class="ep-header">
              <div class="ep-main-info" onclick="handleEpisodeClick('${{ep.release_filename}}')">
                <div class="ep-play-col">
                  <div class="ep-play-btn" id="play-btn-${{ep.release_filename}}">
                    ${{(isCurrentPlaying && isPlaying) ? SVG_PAUSE : SVG_PLAY}}
                  </div>
                  <div class="ep-duration-tag">${{ep.duration_fmt}}</div>
                </div>
                <div class="ep-text-block">
                  <div class="ep-series-badge" onclick="event.stopPropagation(); selectSeries('${{ep.series_id}}')">
                    ${{ep.cave_number}}・${{ep.series_title}}
                  </div>
                  <div class="ep-title">${{ep.title}}</div>
                </div>
              </div>
              <button class="ep-toggle-btn" onclick="toggleDetails('${{ep.release_filename}}', event)">
                展開 ▾
              </button>
            </div>

            <div class="ep-details" id="details-${{ep.release_filename}}">
              <div class="ep-summary-text">${{ep.summary}}</div>
              ${{ep.chapters && ep.chapters.length > 0 ? `
                <div class="chapters-title">📑 本集章節時間軸（點擊直接跳轉收聽）</div>
                <div class="chapters-grid">
                  ${{ep.chapters.map(ch => `
                    <div class="chapter-pill" onclick="jumpToChapter('${{ep.release_filename}}', ${{ch.start}})">
                      <span class="chapter-time">${{ch.start_fmt}}</span>
                      <span class="chapter-name" title="${{ch.title}}">${{ch.title}}</span>
                    </div>
                  `).join('')}}
                </div>
              ` : ''}}
            </div>
          </div>
        `;
      }}).join('');
    }}

    function toggleDetails(relFname, evt) {{
      if (evt) evt.stopPropagation();
      const el = document.getElementById(`details-${{relFname}}`);
      const btn = evt.currentTarget;
      if (el.classList.contains('show')) {{
        el.classList.remove('show');
        btn.textContent = '展開 ▾';
      }} else {{
        el.classList.add('show');
        btn.textContent = '收合 ▴';
      }}
    }}

    function handleEpisodeClick(relFname) {{
      const ep = PODCAST_DATA.episodes.find(e => e.release_filename === relFname);
      if (!ep) return;

      if (currentPlayingEp && currentPlayingEp.release_filename === relFname && audio.src) {{
        togglePlay();
      }} else {{
        loadAndPlayEpisode(ep);
      }}
    }}

    function loadAndPlayEpisode(ep) {{
      currentPlayingEp = ep;
      audio.src = ep.audio_src || ep.audio_url;
      playerTitle.textContent = ep.title;
      playerArtist.textContent = `${{ep.cave_number}}・${{ep.series_title}}`;
      playerThumb.src = ep.cover_image;

      updateAllCardPlayStates(true);
      audio.play().then(() => {{
        isPlaying = true;
        updatePlayIcons(true);
      }}).catch(e => console.log('Audio playback error: ', e));
    }}

    function jumpToChapter(relFname, timestamp) {{
      const ep = PODCAST_DATA.episodes.find(e => e.release_filename === relFname);
      if (!ep) return;

      if (!currentPlayingEp || currentPlayingEp.release_filename !== relFname) {{
        loadAndPlayEpisode(ep);
      }}
      audio.currentTime = timestamp;
      audio.play().then(() => {{
        isPlaying = true;
        updatePlayIcons(true);
      }});
    }}

    function togglePlay() {{
      if (!audio.src || audio.src.endsWith('.html') || audio.src.endsWith('/')) {{
        if (PODCAST_DATA.episodes.length > 0) {{
          loadAndPlayEpisode(PODCAST_DATA.episodes[0]);
        }}
        return;
      }}
      if (audio.paused) {{
        audio.play().then(() => {{
          isPlaying = true;
          updatePlayIcons(true);
          updateAllCardPlayStates(true);
        }});
      }} else {{
        audio.pause();
        isPlaying = false;
        updatePlayIcons(false);
        updateAllCardPlayStates(false);
      }}
    }}

    function updatePlayIcons(playing) {{
      playBtn.innerHTML = playing ? SVG_PAUSE_LG : SVG_PLAY_LG;
    }}

    function updateAllCardPlayStates(playing) {{
      document.querySelectorAll('.episode-card').forEach(c => {{
        c.classList.remove('is-playing');
      }});
      if (currentPlayingEp) {{
        const activeCard = document.getElementById(`card-${{currentPlayingEp.release_filename}}`);
        if (activeCard) {{
          activeCard.classList.add('is-playing');
          const btn = document.getElementById(`play-btn-${{currentPlayingEp.release_filename}}`);
          if (btn) btn.innerHTML = playing ? SVG_PAUSE : SVG_PLAY;
        }}
      }}
    }}

    function playNext() {{
      if (!currentPlayingEp) return;
      const idx = PODCAST_DATA.episodes.findIndex(e => e.release_filename === currentPlayingEp.release_filename);
      if (idx !== -1 && idx < PODCAST_DATA.episodes.length - 1) {{
        loadAndPlayEpisode(PODCAST_DATA.episodes[idx + 1]);
      }}
    }}

    function playPrev() {{
      if (!currentPlayingEp) return;
      const idx = PODCAST_DATA.episodes.findIndex(e => e.release_filename === currentPlayingEp.release_filename);
      if (idx > 0) {{
        loadAndPlayEpisode(PODCAST_DATA.episodes[idx - 1]);
      }}
    }}

    function skipTime(delta) {{
      audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + delta));
    }}

    function seek(e) {{
      const rect = e.currentTarget.getBoundingClientRect();
      const pos = (e.clientX - rect.left) / rect.width;
      audio.currentTime = pos * audio.duration;
    }}

    function cycleSpeed() {{
      currentSpeedIdx = (currentSpeedIdx + 1) % speeds.length;
      const spd = speeds[currentSpeedIdx];
      audio.playbackRate = spd;
      speedBtn.textContent = `${{spd.toFixed(1)}}x`;
    }}

    // Audio Event Listeners
    audio.addEventListener('timeupdate', () => {{
      if (!isNaN(audio.duration)) {{
        const percent = (audio.currentTime / audio.duration) * 100;
        progressFill.style.width = percent + '%';
        currentTimeEl.textContent = formatSec(audio.currentTime);
        totalDurationEl.textContent = formatSec(audio.duration);
      }}
    }});

    audio.addEventListener('play', () => {{
      isPlaying = true;
      updatePlayIcons(true);
      updateAllCardPlayStates(true);
    }});

    audio.addEventListener('pause', () => {{
      isPlaying = false;
      updatePlayIcons(false);
      updateAllCardPlayStates(false);
    }});

    audio.addEventListener('ended', () => {{
      playNext();
    }});

    function formatSec(sec) {{
      if (isNaN(sec)) return '00:00';
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${{m.toString().padStart(2, '0')}}:${{s.toString().padStart(2, '0')}}`;
    }}

    function openSubscribeModal(type) {{
      const modal = document.getElementById('subscribeModal');
      const input = document.getElementById('modalFeedInput');
      const title = document.getElementById('subscribeModalTitle');
      const desc = document.getElementById('subscribeModalDesc');

      let feedName = 'feed.xml';
      if (type === 'all') {{
        title.textContent = '訂閱《兔子洞筆記》全頻道';
        desc.textContent = '包含所有洞窟系列更新的 Master RSS 訂閱源。';
        feedName = 'feed.xml';
      }} else {{
        const curSeries = PODCAST_DATA.series.find(s => s.id === type);
        title.textContent = `訂閱專題：${{curSeries ? curSeries.title : ''}}`;
        desc.textContent = `僅訂閱${{curSeries ? curSeries.cave_number : ''}}獨立專題 RSS。`;
        feedName = `feed_${{type}}.xml`;
      }}

      const fullUrl = window.location.href.substring(0, window.location.href.lastIndexOf('/') + 1) + feedName;
      input.value = fullUrl;
      modal.classList.add('active');
    }}

    function openCurrentSeriesFeed() {{
      if (activeFilter && activeFilter !== 'all') {{
        openSubscribeModal(activeFilter);
      }} else {{
        openSubscribeModal('all');
      }}
    }}

    function openDocModal(docId, docTitle) {{
      const modal = document.getElementById('resourceModal');
      const title = document.getElementById('resourceModalTitle');
      const box = document.getElementById('resourceModalContent');

      title.textContent = `📑 ${{docTitle}}`;
      box.textContent = PODCAST_DATA.series_docs_content[docId] || '尚無文檔內容。';
      modal.classList.add('active');
    }}

    function closeModal(id) {{
      document.getElementById(id).classList.remove('active');
    }}

    function copyModalFeed() {{
      const input = document.getElementById('modalFeedInput');
      input.select();
      navigator.clipboard.writeText(input.value).then(() => showToast('已複製！請至 Apple Podcasts 貼上'));
    }}

    function showToast(msg) {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      setTimeout(() => t.classList.remove('show'), 2500);
    }}

    // Init App
    init();
  </script>
</body>
</html>
"""

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[OK] Successfully built updated {HTML_PATH} ({len(html_content):,} bytes)")
