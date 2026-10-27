"""
Builds the standalone, fully interactive index.html companion web player
for 《兔子洞筆記》 with embedded episode data for zero-config local file:// playback.
Supports:
1. Sticky/fixed header bar that stays anchored at the top when scrolling.
2. Completely code-free caves control via caves.txt.
3. Softcoded reference documents from <Series>/References/ and credits from <Series>/credits.txt.
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

# ==============================================================================
# READ OTHER CAVES FROM PLAIN TEXT FILE (100% Code-Free: caves.txt)
# ==============================================================================
visible_caves = []
if os.path.exists(CAVES_TXT_PATH):
    with open(CAVES_TXT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            # Skip comments and empty lines
            if not line_str or line_str.startswith("#"):
                continue
            parts = [p.strip() for p in line_str.split("|")]
            if len(parts) >= 4:
                name = parts[0]
                desc = parts[1]
                status = parts[3]
            elif len(parts) >= 2:
                name = parts[0]
                desc = parts[1]
                status = parts[2] if len(parts) > 2 else "已上線"
            else:
                continue

            is_active = ("播放中" in status or "當前" in status)
            visible_caves.append({
                "name": name,
                "desc": desc,
                "status": status,
                "is_active": is_active
            })

# Load base episodes.json
with open(JSON_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

SERIES_DIR = r"G:\My Drive\NotebookLM\白話文運動與日文詞彙_ModernChinese"

# 1. Softcoded Series Credits (from <Series>/credits.txt)
credits_file = os.path.join(SERIES_DIR, "credits.txt")
series_credits = ""
if os.path.exists(credits_file):
    with open(credits_file, "r", encoding="utf-8") as f:
        series_credits = f.read().strip()
data["series_credits"] = series_credits

# 2. Softcoded Reference Documents (auto-scanned from <Series>/References/)
ref_src_dir = os.path.join(SERIES_DIR, "References")
ref_docs_list = []
series_docs_content = {}

# Allowed document extensions
ALLOWED_EXTENSIONS = {".md", ".pdf", ".docx", ".txt", ".html", ".epub"}
# System junk & temporary lock files to strictly ignore
SYSTEM_IGNORE_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}

if os.path.exists(ref_src_dir):
    raw_files = sorted(glob.glob(os.path.join(ref_src_dir, "*")))
    active_doc_filenames = set()
    for fpath in raw_files:
        if not os.path.isfile(fpath):
            continue
        fname = os.path.basename(fpath)
        active_doc_filenames.add(fname)
        base_name, ext = os.path.splitext(fname)
        ext_lower = ext.lower()

        # 1. Ignore desktop.ini, Thumbs.db, .DS_Store
        if fname.lower() in SYSTEM_IGNORE_FILES:
            continue
        # 2. Ignore Word temporary lock files (~$*) and hidden/draft files (. or _)
        if fname.startswith(".") or fname.startswith("_") or fname.startswith("~$"):
            continue
        # 3. Whitelist document extensions only
        if ext_lower not in ALLOWED_EXTENSIONS:
            continue

        display_title = re.sub(r"^\d+[\._\-\s]*", "", base_name).strip()
        doc_id = re.sub(r"[^\w\-]", "_", base_name).lower()

        dst_path = os.path.join(DOCS_DIR, fname)
        shutil.copy2(fpath, dst_path)

        doc_info = {
            "id": doc_id,
            "title": display_title,
            "filename": fname,
            "ext": ext_lower,
            "is_pdf": (ext_lower == ".pdf"),
            "is_download": (ext_lower in [".docx", ".epub"]),
            "url": f"docs/{fname}"
        }

        if ext_lower in [".md", ".txt", ".json"]:
            try:
                with open(fpath, "r", encoding="utf-8") as fp:
                    series_docs_content[doc_id] = fp.read()
            except Exception:
                series_docs_content[doc_id] = ""

        ref_docs_list.append(doc_info)

    # Synchronize and clean orphan docs in DOCS_DIR
    if os.path.exists(DOCS_DIR):
        for existing_doc in os.listdir(DOCS_DIR):
            if existing_doc not in active_doc_filenames:
                try:
                    os.remove(os.path.join(DOCS_DIR, existing_doc))
                except Exception:
                    pass

data["ref_docs_list"] = ref_docs_list
data["series_docs_content"] = series_docs_content

# Convert local audio file paths to relative paths for browser playback
for ep in data["episodes"]:
    rel_audio = os.path.relpath(ep["local_path"], DIST_DIR).replace("\\", "/")
    ep["audio_src"] = ep.get("audio_url", f"https://github.com/tzejen/rabbit-hole/releases/download/v1.0.0/{ep.get('release_filename', ep['filename'])}")
    ep["summary"] = ep["summary"].replace("Created with Gemini Antigravity and Google Notebook", "").strip()
    ep["full_notes"] = ep["full_notes"].replace("Created with Gemini Antigravity and Google Notebook", "").strip()

data["other_caves"] = visible_caves
data_json_str = json.dumps(data, ensure_ascii=False)

html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>兔子洞筆記 (Notes from the Rabbit Hole) — 隨選隨聽客廳</title>
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
      max-width: 1000px;
      margin: 0 auto;
      padding: 0 24px;
    }}

    /* Top Sticky/Fixed Header Bar */
    header.site-header {{
      position: sticky;
      top: 0;
      z-index: 900;
      background: rgba(11, 17, 32, 0.94);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      padding: 14px 0;
      border-bottom: 1px solid var(--border-color);
      margin-bottom: 24px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.45);
    }}
    .header-content {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
    }}
    .brand-group {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .brand-avatar {{
      width: 52px;
      height: 52px;
      border-radius: 12px;
      border: 2px solid var(--gold-primary);
      object-fit: cover;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }}
    .brand-title {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 1px;
      color: var(--gold-primary);
    }}
    .brand-subtitle {{
      font-size: 12px;
      color: var(--text-muted);
      letter-spacing: 0.5px;
    }}

    .header-actions {{
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 16px;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.2s ease;
      text-decoration: none;
    }}
    .btn-gold {{
      background: linear-gradient(135deg, #d4af37, #b89327);
      color: #0b1120;
    }}
    .btn-gold:hover {{
      background: linear-gradient(135deg, #f3d478, #d4af37);
      transform: translateY(-1px);
      box-shadow: 0 4px 14px rgba(212, 175, 55, 0.35);
      text-decoration: none;
    }}
    .btn-outline {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: var(--text-main);
    }}
    .btn-outline:hover {{
      background: rgba(212, 175, 55, 0.1);
      border-color: var(--gold-primary);
      text-decoration: none;
    }}

    /* Hero Banner - Compact */
    .hero-banner {{
      background: linear-gradient(145deg, #131d35 0%, #172442 100%);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      padding: 26px 28px;
      margin-bottom: 28px;
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
    .hero-title {{
      font-size: 26px;
      font-weight: 700;
      color: var(--text-main);
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
      margin-bottom: 8px;
      flex-wrap: wrap;
    }}
    .stat-item b {{
      color: var(--gold-light);
      font-weight: 600;
    }}

    /* Softcoded Credits Inside Hero Box */
    .hero-credits {{
      font-size: 10px;
      color: #94a3b8;
      letter-spacing: 0.3px;
      margin-bottom: 12px;
      display: flex;
      align-items: center;
      justify-content: flex-end;
      text-align: right;
      opacity: 0.75;
    }}

    /* Series Level Documentation & Resources - Left-aligned wrap */
    .series-resources {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
      padding-top: 14px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      justify-content: flex-start;
      text-align: left;
    }}
    .resources-label {{
      font-size: 13px;
      color: var(--gold-light);
      font-weight: 600;
      display: flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
    }}
    .resources-pills-wrap {{
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-start;
      text-align: left;
    }}
    .resource-pill {{
      background: rgba(212, 175, 55, 0.1);
      border: 1px solid rgba(212, 175, 55, 0.3);
      color: var(--text-main);
      font-size: 12px;
      font-weight: 600;
      padding: 5px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
    }}
    .resource-pill:hover {{
      background: var(--gold-primary);
      color: #0b1120;
      border-color: var(--gold-primary);
      transform: translateY(-1px);
    }}

    /* Episode Cards - Compact 1-Row Layout */
    .episodes-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .episode-card {{
      background: var(--bg-card);
      border: 1px solid rgba(255,255,255,0.06);
      border-radius: 12px;
      padding: 14px 20px;
      transition: all 0.2s ease;
      cursor: pointer;
    }}
    .episode-card:hover {{
      background: var(--bg-card-hover);
      border-color: var(--border-color);
      transform: translateY(-1px);
    }}
    .episode-card.is-playing {{
      border-color: var(--gold-primary);
      background: rgba(212, 175, 55, 0.08);
    }}
    .ep-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .ep-main-info {{
      display: flex;
      align-items: center;
      gap: 16px;
      flex: 1;
      min-width: 0;
    }}
    .ep-play-col {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
      width: 44px;
    }}
    .ep-play-btn {{
      width: 38px;
      height: 38px;
      border-radius: 50%;
      background: rgba(212, 175, 55, 0.15);
      border: 1px solid var(--gold-primary);
      color: var(--gold-primary);
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font-size: 14px;
      transition: all 0.2s;
    }}
    .episode-card:hover .ep-play-btn,
    .ep-play-btn:hover {{
      background: var(--gold-primary);
      color: #0b1120;
      transform: scale(1.06);
    }}
    .ep-duration-tag {{
      font-family: monospace;
      font-size: 11px;
      color: var(--text-dim);
      letter-spacing: 0.3px;
    }}
    .episode-card:hover .ep-duration-tag {{
      color: var(--gold-light);
    }}

    .ep-title {{
      font-size: 15px;
      font-weight: 600;
      color: var(--text-main);
      line-height: 1.4;
      flex: 1;
      min-width: 0;
    }}
    .ep-toggle-btn {{
      background: transparent;
      border: none;
      color: var(--text-dim);
      font-size: 13px;
      cursor: pointer;
      padding: 6px 10px;
      border-radius: 6px;
      transition: all 0.2s;
      flex-shrink: 0;
    }}
    .ep-toggle-btn:hover {{
      color: var(--gold-primary);
      background: rgba(255,255,255,0.04);
    }}

    /* Episode Expanded Drawer */
    .ep-details {{
      display: none;
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid rgba(255,255,255,0.06);
    }}
    .ep-details.show {{
      display: block;
    }}
    .ep-summary-text {{
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.7;
      margin-bottom: 18px;
      background: rgba(0,0,0,0.25);
      padding: 14px 18px;
      border-radius: 8px;
      border-left: 3px solid var(--gold-primary);
    }}
    .chapters-title {{
      font-size: 13px;
      font-weight: 700;
      color: var(--gold-primary);
      text-transform: uppercase;
      letter-spacing: 1px;
      margin-bottom: 12px;
    }}
    .chapters-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 8px;
    }}
    .chapter-pill {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.06);
      padding: 8px 12px;
      border-radius: 8px;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .chapter-pill:hover {{
      background: rgba(212, 175, 55, 0.12);
      border-color: var(--gold-primary);
      color: var(--gold-light);
    }}
    .chapter-time {{
      font-family: monospace;
      font-size: 11px;
      color: var(--gold-primary);
      background: rgba(212, 175, 55, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
      font-weight: 600;
    }}
    .chapter-name {{
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    /* Fixed Bottom Player */
    .bottom-player {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: rgba(15, 23, 42, 0.95);
      backdrop-filter: blur(16px);
      border-top: 1px solid var(--border-color);
      padding: 16px 24px;
      z-index: 1000;
      box-shadow: 0 -8px 24px rgba(0,0,0,0.5);
    }}
    .player-inner {{
      max-width: 1000px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 280px 1fr 180px;
      align-items: center;
      gap: 20px;
    }}
    .track-info {{
      display: flex;
      align-items: center;
      gap: 14px;
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
      color: var(--text-main);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    .track-artist {{
      font-size: 12px;
      color: var(--text-dim);
    }}

    .player-center {{
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
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
      font-size: 16px;
      padding: 6px;
      border-radius: 50%;
      transition: all 0.15s;
    }}
    .ctrl-btn:hover {{
      color: var(--gold-primary);
      transform: scale(1.1);
    }}
    .ctrl-btn-play {{
      width: 40px;
      height: 40px;
      background: var(--gold-primary);
      color: #0b1120;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
    }}
    .ctrl-btn-play:hover {{
      background: var(--gold-light);
      transform: scale(1.06);
    }}

    .timeline-row {{
      width: 100%;
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 11px;
      font-family: monospace;
      color: var(--text-dim);
    }}
    .progress-bar-container {{
      flex: 1;
      height: 6px;
      background: rgba(255,255,255,0.1);
      border-radius: 3px;
      cursor: pointer;
      position: relative;
    }}
    .progress-bar-fill {{
      height: 100%;
      background: var(--gold-primary);
      border-radius: 3px;
      width: 0%;
      position: relative;
    }}

    .player-right {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 14px;
    }}
    .speed-btn {{
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      color: var(--gold-light);
      font-size: 12px;
      font-weight: 700;
      padding: 4px 8px;
      border-radius: 6px;
      cursor: pointer;
    }}
    .speed-btn:hover {{
      border-color: var(--gold-primary);
    }}

    /* Modals */
    .modal-backdrop {{
      display: none;
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0,0,0,0.8);
      backdrop-filter: blur(8px);
      z-index: 2000;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .modal-backdrop.active {{
      display: flex;
    }}
    .modal-window {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      max-width: 650px;
      width: 100%;
      max-height: 85vh;
      overflow-y: auto;
      padding: 32px;
      box-shadow: 0 16px 48px rgba(0,0,0,0.7);
      position: relative;
    }}
    .modal-close {{
      position: absolute;
      top: 20px;
      right: 20px;
      background: transparent;
      border: none;
      color: var(--text-dim);
      font-size: 22px;
      cursor: pointer;
    }}
    .modal-close:hover {{
      color: var(--text-main);
    }}
    .modal-title {{
      font-size: 22px;
      font-weight: 700;
      color: var(--gold-primary);
      margin-bottom: 12px;
    }}
    .modal-desc {{
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.6;
      margin-bottom: 24px;
    }}
    .feed-box {{
      background: rgba(0,0,0,0.3);
      border: 1px dashed var(--border-color);
      padding: 12px 16px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
    }}
    .feed-input {{
      flex: 1;
      background: transparent;
      border: none;
      color: var(--gold-light);
      font-family: monospace;
      font-size: 13px;
      outline: none;
    }}
    .steps-list {{
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.8;
      padding-left: 20px;
    }}

    /* Other Caves List in Modal */
    .caves-list-group {{
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .cave-item {{
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 10px;
      padding: 14px 18px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}
    .cave-item.active-cave {{
      border-color: var(--gold-primary);
      background: rgba(212, 175, 55, 0.08);
    }}
    .cave-item-name {{
      font-size: 15px;
      font-weight: 600;
      color: var(--text-main);
    }}
    .cave-item-desc {{
      font-size: 12px;
      color: var(--text-dim);
      margin-top: 2px;
    }}
    .cave-status-tag {{
      font-size: 12px;
      font-weight: 600;
      padding: 3px 10px;
      border-radius: 20px;
      background: rgba(255,255,255,0.05);
      color: var(--text-dim);
      white-space: nowrap;
      flex-shrink: 0;
    }}
    .cave-status-tag.active {{
      background: rgba(212, 175, 55, 0.2);
      color: var(--gold-light);
      border: 1px solid var(--gold-primary);
    }}

    /* Doc Content in Modal */
    .doc-content-box {{
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.8;
      white-space: pre-wrap;
      font-family: var(--font-stack);
      background: rgba(0,0,0,0.25);
      padding: 18px;
      border-radius: 10px;
      max-height: 50vh;
      overflow-y: auto;
    }}

    /* Toast */
    .toast {{
      position: fixed;
      top: 24px;
      left: 50%;
      transform: translateX(-50%) translateY(-100px);
      background: var(--gold-primary);
      color: #0b1120;
      font-weight: 700;
      padding: 10px 24px;
      border-radius: 9999px;
      font-size: 14px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
      transition: transform 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28);
      z-index: 3000;
      pointer-events: none;
    }}
    .toast.show {{
      transform: translateX(-50%) translateY(0);
    }}

    @media (max-width: 768px) {{
      .hero-banner {{
        flex-direction: column;
        align-items: flex-start;
        padding: 20px;
      }}
      .hero-cover {{
        width: 130px;
        height: 130px;
      }}
      .player-inner {{
        grid-template-columns: 1fr 100px;
      }}
      .player-center {{
        grid-column: 1 / -1;
        order: 2;
      }}
      .track-info {{
        order: 1;
      }}
      .player-right {{
        order: 1;
      }}
    }}
  </style>
</head>
<body>

  <!-- Toast Notification -->
  <div id="toast" class="toast">已複製到剪貼簿！</div>

  <!-- Sticky / Fixed Header Bar (Pinned across full width) -->
  <header class="site-header">
    <div class="container">
      <div class="header-content">
        <div class="brand-group">
          <img src="cover_channel.png" alt="兔子洞筆記封面" class="brand-avatar">
          <div>
            <div class="brand-title">兔子洞筆記</div>
            <div class="brand-subtitle">Notes from the Rabbit Hole</div>
          </div>
        </div>
        <div class="header-actions">
          <button class="btn btn-outline" onclick="openOtherCavesModal()">
            <span>🐇 其他洞窟</span>
          </button>
          <button class="btn btn-gold" onclick="openSubscribeModal('all')">
            <span>📡 訂閱 Podcast</span>
          </button>
        </div>
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Hero Banner (第一窟) - Compact Layout -->
    <section class="hero-banner">
      <img src="assets/cover_cave01_hanzi.jpg" alt="第一窟封面" class="hero-cover">
      <div class="hero-info">
        <h1 class="hero-title">漢字大遷徙：近代中日詞彙革命</h1>
        <p class="hero-desc">
          當西方近代哲學與科學衝擊東亞，我們每天使用的「經濟、社會、哲學、主觀、客觀」從何而來？
          從江戶蘭學的刑場解剖、嚴復與梁啟超的譯詞對決，到五四言文一致運動與台灣東亞回流——解構現代漢語底層的驚人零件。
        </p>
        <div class="hero-stats">
          <div class="stat-item">集數：<b>10 集</b></div>
          <div class="stat-item">總長：<b>3 小時 15 分</b></div>
          <div class="stat-item">語言：<b>中文</b></div>
        </div>

        <!-- Softcoded Series Credits (in the title box, shown only if present) -->
        <div class="hero-credits" id="heroCreditsContainer"></div>

        <!-- Softcoded Series Resources (Left-aligned wrap) -->
        <div class="series-resources" id="seriesResourcesBox">
          <span class="resources-label">📚 系列資料庫：</span>
          <div class="resources-pills-wrap" id="resourcesPillsWrap"></div>
        </div>
      </div>
    </section>

    <!-- Episodes List -->
    <div class="episodes-list" id="episodesList"></div>
  </div>

  <!-- Bottom Persistent Audio Player -->
  <div class="bottom-player" id="bottomPlayer">
    <div class="player-inner">
      <div class="track-info">
        <img id="playerThumb" src="assets/cover_cave01_hanzi.jpg" class="track-thumb" alt="封面">
        <div class="track-text">
          <div class="track-title" id="playerTitle">點擊任一單集開始收聽</div>
          <div class="track-artist" id="playerArtist">兔子洞筆記・第一窟</div>
        </div>
      </div>

      <div class="player-center">
        <div class="controls-row">
          <button class="ctrl-btn" onclick="skipTime(-15)" title="倒退 15 秒">↺ 15s</button>
          <button class="ctrl-btn" onclick="playPrev()" title="上一集">⏮</button>
          <button class="ctrl-btn ctrl-btn-play" id="playBtn" onclick="togglePlay()" title="播放/暫停">▶</button>
          <button class="ctrl-btn" onclick="playNext()" title="下一集">⏭</button>
          <button class="ctrl-btn" onclick="skipTime(15)" title="快進 15 秒">15s ↻</button>
        </div>
        <div class="timeline-row">
          <span id="currentTime">00:00</span>
          <div class="progress-bar-container" id="progressBar" onclick="seek(event)">
            <div class="progress-bar-fill" id="progressFill"></div>
          </div>
          <span id="totalDuration">00:00</span>
        </div>
      </div>

      <div class="player-right">
        <button class="speed-btn" id="speedBtn" onclick="cycleSpeed()">1.0x</button>
      </div>
    </div>
  </div>

  <!-- Hidden Audio Element -->
  <audio id="audioElement" preload="metadata"></audio>

  <!-- Combined Subscribe Modal -->
  <div class="modal-backdrop" id="subscribeModal" onclick="closeModal('subscribeModal')">
    <div class="modal-window" onclick="event.stopPropagation()">
      <button class="modal-close" onclick="closeModal('subscribeModal')">&times;</button>
      <div class="modal-title">訂閱《兔子洞筆記》</div>
      <p class="modal-desc">
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

  <!-- Other Caves Modal (Dynamically Populated from caves.txt) -->
  <div class="modal-backdrop" id="otherCavesModal" onclick="closeModal('otherCavesModal')">
    <div class="modal-window" onclick="event.stopPropagation()">
      <button class="modal-close" onclick="closeModal('otherCavesModal')">&times;</button>
      <div class="modal-title">🐇 兔子洞系列目錄</div>

      <div class="caves-list-group" id="cavesListContainer"></div>
      <p style="font-size: 12px; color: var(--text-dim); margin-top: 20px; text-align: center;">
        ✦ 訂閱全頻道 RSS，即可在任一新窟完成時於 Podcast App 自動獲取最新集數！
      </p>
    </div>
  </div>

  <!-- Resource Document Modal -->
  <div class="modal-backdrop" id="resourceModal" onclick="closeModal('resourceModal')">
    <div class="modal-window" style="max-width: 800px;" onclick="event.stopPropagation()">
      <button class="modal-close" onclick="closeModal('resourceModal')">&times;</button>
      <div class="modal-title" id="resourceModalTitle">系列資料文件</div>
      <div class="doc-content-box" id="resourceModalContent"></div>
    </div>
  </div>

  <!-- Application Script -->
  <script>
    const PODCAST_DATA = {data_json_str};
    let currentEpIndex = 0;
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

    // Render Hero Credits (Softcoded)
    function renderHeroCredits() {{
      const container = document.getElementById('heroCreditsContainer');
      const credits = PODCAST_DATA.series_credits;
      if (credits) {{
        container.innerHTML = `<span>✧</span> <span>${{credits}}</span>`;
        container.style.display = 'flex';
      }} else {{
        container.style.display = 'none';
      }}
    }}

    // Render Softcoded Series Reference Documents (Left-aligned wrap)
    function renderSeriesResources() {{
      const box = document.getElementById('seriesResourcesBox');
      const wrap = document.getElementById('resourcesPillsWrap');
      const docs = PODCAST_DATA.ref_docs_list || [];

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

    // Render Episodes List - Compact 1-Row Layout
    function renderEpisodes() {{
      const list = document.getElementById('episodesList');
      list.innerHTML = PODCAST_DATA.episodes.map((ep, idx) => `
        <div class="episode-card" id="card-${{idx}}">
          <div class="ep-header">
            <div class="ep-main-info" onclick="handleRowClick(${{idx}})">
              <div class="ep-play-col">
                <div class="ep-play-btn" id="card-play-btn-${{idx}}">▶</div>
                <div class="ep-duration-tag">${{ep.duration_fmt}}</div>
              </div>
              <div class="ep-title">${{ep.title}}</div>
            </div>
            <button class="ep-toggle-btn" onclick="toggleDetails(${{idx}}, event)">
              展開 ▾
            </button>
          </div>

          <div class="ep-details" id="details-${{idx}}">
            <div class="ep-summary-text">${{ep.summary}}</div>
            <div class="chapters-title">📑 本集章節時間軸（點擊直接跳轉收聽）</div>
            <div class="chapters-grid">
              ${{ep.chapters.map(ch => `
                <div class="chapter-pill" onclick="jumpToChapter(${{idx}}, ${{ch.start}})">
                  <span class="chapter-time">${{ch.start_fmt}}</span>
                  <span class="chapter-name" title="${{ch.title}}">${{ch.title}}</span>
                </div>
              `).join('')}}
            </div>
          </div>
        </div>
      `).join('');
    }}

    // Render Other Caves Modal Content from caves.txt
    function renderOtherCaves() {{
      const container = document.getElementById('cavesListContainer');
      const caves = PODCAST_DATA.other_caves || [];
      if (caves.length === 0) {{
        container.innerHTML = '<div style="text-align: center; color: var(--text-dim); padding: 20px;">目前尚無其他展示洞窟。</div>';
        return;
      }}
      container.innerHTML = caves.map(cave => `
        <div class="cave-item ${{cave.is_active ? 'active-cave' : ''}}">
          <div>
            <div class="cave-item-name">${{cave.name}}</div>
            <div class="cave-item-desc">${{cave.desc}}</div>
          </div>
          <span class="cave-status-tag ${{cave.is_active ? 'active' : ''}}">${{cave.status}}</span>
        </div>
      `).join('');
    }}

    function toggleDetails(idx, evt) {{
      if (evt) evt.stopPropagation();
      const el = document.getElementById(`details-${{idx}}`);
      const btn = evt.currentTarget;
      if (el.classList.contains('show')) {{
        el.classList.remove('show');
        btn.textContent = '展開 ▾';
      }} else {{
        el.classList.add('show');
        btn.textContent = '收合 ▴';
      }}
    }}

    function handleRowClick(idx) {{
      if (currentEpIndex === idx && audio.src && !audio.src.endsWith('.html') && !audio.src.endsWith('/')) {{
        togglePlay();
      }} else {{
        loadAndPlayEpisode(idx);
      }}
    }}

    function loadAndPlayEpisode(idx) {{
      currentEpIndex = idx;
      const ep = PODCAST_DATA.episodes[idx];
      audio.src = ep.audio_src;
      playerTitle.textContent = ep.title;
      playerArtist.textContent = `${{ep.cave_number}}・${{ep.series_title}}`;
      playerThumb.src = ep.cover_image;
      
      updateCardStyles(idx, true);
      audio.play().then(() => {{
        isPlaying = true;
        updatePlayIcons(true);
      }}).catch(e => console.log('Audio playback error: ', e));
    }}

    function jumpToChapter(idx, timestamp) {{
      if (currentEpIndex !== idx || !audio.src || audio.src.endsWith('.html')) {{
        loadAndPlayEpisode(idx);
      }}
      audio.currentTime = timestamp;
      audio.play().then(() => {{
        isPlaying = true;
        updatePlayIcons(true);
      }});
    }}

    function togglePlay() {{
      if (!audio.src || audio.src.endsWith('.html') || audio.src.endsWith('/')) {{
        loadAndPlayEpisode(0);
        return;
      }}
      if (audio.paused) {{
        audio.play().then(() => {{
          isPlaying = true;
          updatePlayIcons(true);
        }});
      }} else {{
        audio.pause();
        isPlaying = false;
        updatePlayIcons(false);
      }}
    }}

    function updatePlayIcons(playing) {{
      playBtn.textContent = playing ? '⏸' : '▶';
      const cardBtn = document.getElementById(`card-play-btn-${{currentEpIndex}}`);
      if (cardBtn) cardBtn.textContent = playing ? '⏸' : '▶';
    }}

    function updateCardStyles(activeIdx, playing) {{
      document.querySelectorAll('.episode-card').forEach((c, i) => {{
        c.classList.toggle('is-playing', i === activeIdx);
        const cardPlayBtn = document.getElementById(`card-play-btn-${{i}}`);
        if (cardPlayBtn) cardPlayBtn.textContent = (i === activeIdx && playing) ? '⏸' : '▶';
      }});
    }}

    function playNext() {{
      if (currentEpIndex < PODCAST_DATA.episodes.length - 1) {{
        loadAndPlayEpisode(currentEpIndex + 1);
      }}
    }}

    function playPrev() {{
      if (currentEpIndex > 0) {{
        loadAndPlayEpisode(currentEpIndex - 1);
      }}
    }}

    function skipTime(delta) {{
      audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + delta));
    }}

    function cycleSpeed() {{
      currentSpeedIdx = (currentSpeedIdx + 1) % speeds.length;
      const s = speeds[currentSpeedIdx];
      audio.playbackRate = s;
      speedBtn.textContent = s.toFixed(1) + 'x';
    }}

    function seek(e) {{
      const rect = e.currentTarget.getBoundingClientRect();
      const pos = (e.clientX - rect.left) / rect.width;
      audio.currentTime = pos * audio.duration;
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
    }});

    audio.addEventListener('pause', () => {{
      isPlaying = false;
      updatePlayIcons(false);
    }});

    audio.addEventListener('ended', () => {{
      playNext();
    }});

    function formatSec(sec) {{
      if (isNaN(sec)) return '00:00';
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${{String(m).padStart(2, '0')}}:${{String(s).padStart(2, '0')}}`;
    }}

    // Subscription & Modals
    function openSubscribeModal(type) {{
      const modal = document.getElementById('subscribeModal');
      const input = document.getElementById('modalFeedInput');
      const feedName = (type === 'all') ? 'feed.xml' : 'feed_cave01_hanzi.xml';
      const fullUrl = window.location.href.substring(0, window.location.href.lastIndexOf('/') + 1) + feedName;
      input.value = fullUrl;
      modal.classList.add('active');
    }}

    function openOtherCavesModal() {{
      renderOtherCaves();
      document.getElementById('otherCavesModal').classList.add('active');
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

    // Init
    renderHeroCredits();
    renderSeriesResources();
    renderEpisodes();
  </script>
</body>
</html>
"""

with open(HTML_PATH, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"[OK] Successfully built updated {HTML_PATH} ({len(html_content):,} bytes)")
