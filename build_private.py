"""
Builds unlisted standalone companion web players for private or work-in-progress podcast series.
Each private series is output into:
  podcast_distribution/p/<secret_slug>/index.html
with its own self-contained audio data and documents.
Crucially:
- It has NO inbound links from the main index.html or feed.xml.
- It has NO outbound links leading visitors back to the rabbit-hole index.
- It shares the exact same responsive dark-luxe UI, audio player, speed/chapter controls, and reference docs viewer.
"""

import os
import sys
import json
import shutil
import glob
import re
import subprocess
from datetime import datetime, timezone
from mutagen.mp4 import MP4

sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = r"G:\My Drive\NotebookLM"
DIST_DIR = os.path.join(BASE_DIR, "podcast_distribution")
PRIVATE_CAVES_PATH = os.path.join(DIST_DIR, "private_caves.txt")
CHANNEL_TXT_PATH = os.path.join(DIST_DIR, "channel.txt")
P_ROOT_DIR = os.path.join(DIST_DIR, "p")
os.makedirs(P_ROOT_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".md", ".pdf", ".docx", ".txt", ".html", ".epub"}
SYSTEM_IGNORE_FILES = {"desktop.ini", "thumbs.db", ".ds_store"}

def load_channel_meta():
    meta = {
        "title": "兔子洞筆記 (私人專題)",
        "subtitle": "專屬試聽與籌備空間",
        "author": "tzejen",
        "email": "",
        "category": "History",
        "language": "zh-tw",
        "github_user": "tzejen",
        "github_repo": "rabbit-hole",
        "cover_filename": "cover_channel_1400.jpg"
    }
    if os.path.exists(CHANNEL_TXT_PATH):
        with open(CHANNEL_TXT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if ":" in s and not s.startswith("#"):
                    k, v = s.split(":", 1)
                    k_l = k.strip().lower()
                    if k_l == "github_user": meta["github_user"] = v.strip()
                    elif k_l == "github_repo": meta["github_repo"] = v.strip()
                    elif k_l == "author": meta["author"] = v.strip()
    return meta

CHANNEL_META = load_channel_meta()

def get_audio_duration_and_chapters(file_path):
    duration_sec = 0.0
    # Try ffprobe for duration
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0 and res.stdout.strip():
            duration_sec = float(res.stdout.strip())
    except Exception:
        pass

    chapters = []
    try:
        cmd = ["ffprobe", "-i", file_path, "-print_format", "json", "-show_chapters", "-loglevel", "error"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0:
            data = json.loads(res.stdout)
            for ch in data.get("chapters", []):
                start = float(ch["start_time"])
                end = float(ch["end_time"])
                title = ch.get("tags", {}).get("title", f"Chapter {len(chapters)+1}")
                chapters.append({
                    "title": title,
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "start_fmt": f"{int(start//60):02d}:{int(start%60):02d}",
                    "end_fmt": f"{int(end//60):02d}:{int(end%60):02d}"
                })
    except Exception:
        pass

    return duration_sec, chapters

def format_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def parse_private_caves():
    if not os.path.exists(PRIVATE_CAVES_PATH):
        print(f"[WARN] {PRIVATE_CAVES_PATH} not found.")
        return []

    entries = []
    with open(PRIVATE_CAVES_PATH, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            parts = [p.strip() for p in raw.split("|")]
            if len(parts) >= 2:
                slug = parts[0]
                title = parts[1]
                subdir = parts[2] if len(parts) > 2 else ""
                status = parts[3] if len(parts) > 3 else "未公開"

                series_dir = None
                if subdir:
                    cand = os.path.join(BASE_DIR, subdir)
                    if os.path.isdir(cand):
                        series_dir = cand
                if not series_dir:
                    for d in os.listdir(BASE_DIR):
                        full = os.path.join(BASE_DIR, d)
                        if os.path.isdir(full) and d.startswith(title[:2]):
                            series_dir = full
                            break

                if series_dir and os.path.isdir(series_dir):
                    entries.append({
                        "slug": slug,
                        "title": title,
                        "dir": series_dir,
                        "status": status
                    })
    return entries

def build_private_series(entry):
    slug = entry["slug"]
    s_title = entry["title"]
    s_dir = entry["dir"]
    status = entry["status"]

    target_dir = os.path.join(P_ROOT_DIR, slug)
    os.makedirs(target_dir, exist_ok=True)
    docs_dir = os.path.join(target_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)

    print(f"\n🔨 Building Private Series Page: [{slug}] {s_title}")
    print(f"   Source directory: {s_dir}")
    print(f"   Target web directory: {target_dir}")

    # Copy cover image
    cover_dst_name = "cover.jpg"
    cover_src = os.path.join(s_dir, "cover.jpg")
    if not os.path.exists(cover_src):
        cover_src = os.path.join(s_dir, "cover.png")
    if not os.path.exists(cover_src):
        cover_src = os.path.join(DIST_DIR, "cover_channel.png")
    shutil.copy2(cover_src, os.path.join(target_dir, cover_dst_name))

    # Read series description
    series_desc = ""
    desc_file = os.path.join(s_dir, "desc.txt")
    if os.path.exists(desc_file):
        try:
            dlines = open(desc_file, "r", encoding="utf-8").read().splitlines()
            for didx, dl in enumerate(dlines):
                if "【系列簡介】" in dl:
                    collected = []
                    for follow in dlines[didx+1:]:
                        if follow.startswith("【各集目錄】") or follow.startswith("■") or follow.startswith("第 "):
                            break
                        if follow.strip():
                            collected.append(follow.strip())
                    series_desc = "\n".join(collected).strip()
                    break
        except Exception:
            pass
    if not series_desc:
        series_desc = f"{s_title} 專題未公開播放頁面。"

    # Scan episodes
    m4a_files = sorted([
        f for f in glob.glob(os.path.join(s_dir, "[0-9][0-9]_*.m4a"))
        if "Candidate" not in os.path.basename(f)
        and "MicroCut" not in os.path.basename(f)
        and "_v" not in os.path.basename(f)
    ])

    episodes = []
    user = CHANNEL_META.get("github_user", "tzejen")
    repo = CHANNEL_META.get("github_repo", "rabbit-hole")

    for idx, fpath in enumerate(m4a_files, 1):
        fname = os.path.basename(fpath)
        base_no_ext = os.path.splitext(fname)[0]
        mp4 = MP4(fpath)

        title_tag = mp4.tags.get("©nam", [base_no_ext])[0] if mp4.tags else base_no_ext
        clean_title = re.sub(r"^(?:Ep\d+|H\d+E\d+|\d+)[\s\-_:：]*", "", title_tag).strip()
        formatted_title = f"Ep{idx:02d} {clean_title}"

        artist_tag = mp4.tags.get("©ART", [CHANNEL_META["author"]])[0] if mp4.tags else CHANNEL_META["author"]
        desc_tag = mp4.tags.get("desc", mp4.tags.get("©cmt", [""]))[0] if mp4.tags else ""
        notes_tag = mp4.tags.get("©lyr", [desc_tag])[0] if mp4.tags else desc_tag

        dur_sec, chapters = get_audio_duration_and_chapters(fpath)
        if dur_sec <= 0:
            dur_sec = round(mp4.info.length, 2)
        file_size = os.path.getsize(fpath)

        # In private mode, audio can be linked to local relative file if placed in folder, or github release asset
        # To make it work immediately even before github release, let's copy or symlink the audio or provide standard audio URL
        # We can also store audio locally in p/<slug>/audio/ or reference GitHub Release if uploaded!
        # For seamless zero-config local and web playback, we place audio in `audio/` within the private directory:
        audio_subfolder = os.path.join(target_dir, "audio")
        os.makedirs(audio_subfolder, exist_ok=True)
        dst_audio_path = os.path.join(audio_subfolder, fname)
        # Copy audio if not exists or size differs
        if not os.path.exists(dst_audio_path) or os.path.getsize(dst_audio_path) != file_size:
            print(f"   Copying audio: {fname} -> p/{slug}/audio/{fname}")
            shutil.copy2(fpath, dst_audio_path)

        audio_url = f"audio/{fname}"

        ep_data = {
            "series_id": slug,
            "cave_number": "專屬",
            "series_title": s_title,
            "season": 1,
            "episode": idx,
            "title": formatted_title,
            "filename": fname,
            "release_filename": fname,
            "audio_url": audio_url,
            "local_path": fpath,
            "file_size": file_size,
            "duration_sec": dur_sec,
            "duration_fmt": format_duration(dur_sec),
            "artist": artist_tag,
            "summary": desc_tag,
            "full_notes": notes_tag,
            "chapters": chapters,
            "cover_image": cover_dst_name,
            "pub_date_rfc822": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000"),
            "pub_date_iso": datetime.now(timezone.utc).isoformat(),
        }
        episodes.append(ep_data)
        print(f"   [OK] Ep{idx:02d}: {formatted_title} ({ep_data['duration_fmt']})")

    # Scan References
    ref_docs_list = []
    series_docs_content = {}
    ref_src_dir = os.path.join(s_dir, "References")
    if os.path.exists(ref_src_dir):
        raw_files = sorted(glob.glob(os.path.join(ref_src_dir, "*")))
        for fpath in raw_files:
            if not os.path.isfile(fpath): continue
            fname = os.path.basename(fpath)
            base_name, ext = os.path.splitext(fname)
            ext_lower = ext.lower()
            if fname.lower() in SYSTEM_IGNORE_FILES or fname.startswith(".") or fname.startswith("_") or fname.startswith("~$"):
                continue
            if ext_lower not in ALLOWED_EXTENSIONS:
                continue

            clean_doc_title = re.sub(r"^\d+[\._\-\s]*", "", base_name).strip()
            doc_id = re.sub(r"[^\w\-]", "_", f"{slug}_{base_name}").lower()
            dst_path = os.path.join(docs_dir, fname)
            shutil.copy2(fpath, dst_path)

            doc_info = {
                "id": doc_id,
                "title": clean_doc_title,
                "filename": fname,
                "series_id": slug,
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

    # Series metadata bundle
    series_entry = {
        "id": slug,
        "cave_number": "未公開專題",
        "title": s_title,
        "description": series_desc,
        "dir": s_dir,
        "cover_src": cover_src,
        "cover_dst_name": cover_dst_name,
        "season_num": 1,
        "status": status
    }

    # Generate standalone index.html
    generate_private_html(target_dir, series_entry, episodes, ref_docs_list, series_docs_content)

def generate_private_html(output_dir, series_info, episodes, ref_docs, docs_content):
    data_bundle = {
        "series_info": series_info,
        "episodes": episodes,
        "ref_docs_list": ref_docs,
        "series_docs_content": docs_content
    }
    data_json_str = json.dumps(data_bundle, ensure_ascii=False)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{series_info['title']} — 專屬聆聽客廳</title>
  <meta name="robots" content="noindex, nofollow">
  <link rel="icon" type="image/jpeg" href="cover.jpg">
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

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background-color: var(--bg-midnight);
      color: var(--text-main);
      font-family: var(--font-stack);
      line-height: 1.6;
      padding-bottom: 150px;
      -webkit-font-smoothing: antialiased;
    }}

    header {{
      background: linear-gradient(180deg, rgba(19, 29, 53, 0.95) 0%, rgba(11, 17, 32, 0.8) 100%);
      border-bottom: 1px solid var(--border-color);
      padding: 24px 20px;
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 100;
    }}

    .header-inner {{
      max-width: 960px;
      margin: 0 auto;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 14px;
      text-decoration: none;
      color: inherit;
    }}

    .brand-icon {{
      width: 44px;
      height: 44px;
      border-radius: 10px;
      object-fit: cover;
      border: 1px solid var(--gold-primary);
    }}

    .brand h1 {{
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--gold-light);
      letter-spacing: 0.05em;
    }}

    .badge-private {{
      background: rgba(212, 175, 55, 0.15);
      color: var(--gold-light);
      border: 1px solid var(--border-color);
      font-size: 0.75rem;
      padding: 3px 8px;
      border-radius: 6px;
      letter-spacing: 0.05em;
    }}

    main {{
      max-width: 960px;
      margin: 32px auto;
      padding: 0 20px;
    }}

    .hero-banner {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 28px;
      margin-bottom: 32px;
      display: flex;
      gap: 24px;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
    }}

    .hero-cover {{
      width: 140px;
      height: 140px;
      border-radius: 12px;
      object-fit: cover;
      border: 1px solid var(--gold-primary);
      flex-shrink: 0;
    }}

    .hero-content h2 {{
      font-size: 1.5rem;
      color: var(--gold-light);
      margin-bottom: 8px;
    }}

    .hero-meta {{
      font-size: 0.85rem;
      color: var(--gold-dim);
      margin-bottom: 12px;
      display: flex;
      gap: 16px;
    }}

    .hero-desc {{
      font-size: 0.95rem;
      color: var(--text-muted);
      line-height: 1.7;
    }}

    .section-title {{
      font-size: 1.15rem;
      font-weight: 600;
      color: var(--gold-light);
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .episode-list {{
      display: flex;
      flex-direction: column;
      gap: 12px;
      margin-bottom: 36px;
    }}

    .episode-card {{
      background: var(--bg-card);
      border: 1px solid rgba(255, 255, 255, 0.07);
      border-radius: 12px;
      padding: 18px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      transition: all 0.2s ease;
      cursor: pointer;
    }}

    .episode-card:hover {{
      background: var(--bg-card-hover);
      border-color: var(--border-focus);
      transform: translateY(-2px);
    }}

    .episode-card.active {{
      border-color: var(--gold-primary);
      background: rgba(212, 175, 55, 0.08);
    }}

    .ep-left {{
      display: flex;
      align-items: center;
      gap: 16px;
      flex-grow: 1;
    }}

    .play-btn {{
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: rgba(212, 175, 55, 0.15);
      border: 1px solid var(--gold-primary);
      color: var(--gold-light);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.1rem;
      cursor: pointer;
      flex-shrink: 0;
      transition: all 0.2s;
    }}

    .play-btn:hover {{
      background: var(--gold-primary);
      color: #000;
      transform: scale(1.05);
    }}

    .ep-info h3 {{
      font-size: 1.05rem;
      color: var(--text-main);
      margin-bottom: 4px;
    }}

    .ep-info p {{
      font-size: 0.85rem;
      color: var(--text-muted);
    }}

    .ep-duration {{
      font-size: 0.85rem;
      color: var(--gold-dim);
      font-variant-numeric: tabular-nums;
      flex-shrink: 0;
    }}

    /* References Section */
    .docs-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 12px;
      margin-bottom: 40px;
    }}

    .doc-pill {{
      background: var(--bg-card);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 10px;
      padding: 12px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--text-main);
      text-decoration: none;
      font-size: 0.9rem;
      transition: all 0.2s;
      cursor: pointer;
    }}

    .doc-pill:hover {{
      border-color: var(--gold-primary);
      background: var(--bg-card-hover);
    }}

    /* Bottom Player Bar */
    .player-bar {{
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      background: rgba(15, 23, 42, 0.96);
      border-top: 1px solid var(--border-color);
      backdrop-filter: blur(16px);
      padding: 14px 20px;
      z-index: 200;
      box-shadow: 0 -10px 30px rgba(0,0,0,0.5);
    }}

    .player-inner {{
      max-width: 960px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }}

    .player-top {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}

    .now-playing {{
      display: flex;
      align-items: center;
      gap: 12px;
      overflow: hidden;
      flex-grow: 1;
    }}

    .now-title {{
      font-size: 0.95rem;
      font-weight: 600;
      color: var(--gold-light);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .player-controls {{
      display: flex;
      align-items: center;
      gap: 14px;
      flex-shrink: 0;
    }}

    .ctrl-btn {{
      background: none;
      border: none;
      color: var(--text-main);
      font-size: 1.1rem;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: color 0.2s;
    }}

    .ctrl-btn:hover {{
      color: var(--gold-primary);
    }}

    .ctrl-btn-play {{
      width: 42px;
      height: 42px;
      border-radius: 50%;
      background: var(--gold-primary);
      color: #000;
      font-size: 1.2rem;
    }}

    .ctrl-btn-play:hover {{
      background: var(--gold-light);
      color: #000;
    }}

    .rate-btn {{
      font-size: 0.8rem;
      font-weight: bold;
      color: var(--gold-dim);
      padding: 4px 8px;
      border: 1px solid rgba(212, 175, 55, 0.3);
      border-radius: 6px;
      cursor: pointer;
    }}

    .rate-btn:hover {{
      color: var(--gold-light);
      border-color: var(--gold-primary);
    }}

    /* Progress bar */
    .progress-wrap {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .time-lbl {{
      font-size: 0.75rem;
      color: var(--text-dim);
      font-variant-numeric: tabular-nums;
      width: 42px;
    }}

    .time-right {{ text-align: right; }}

    .progress-bar {{
      flex-grow: 1;
      height: 6px;
      background: rgba(255,255,255,0.1);
      border-radius: 3px;
      position: relative;
      cursor: pointer;
    }}

    .progress-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--gold-dim), var(--gold-primary));
      border-radius: 3px;
      width: 0%;
      pointer-events: none;
    }}

    /* Modal for Docs */
    .modal-backdrop {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.75);
      z-index: 500;
      backdrop-filter: blur(4px);
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}

    .modal-backdrop.active {{
      display: flex;
    }}

    .modal-card {{
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      max-width: 760px;
      width: 100%;
      max-height: 80vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
    }}

    .modal-header {{
      padding: 18px 24px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}

    .modal-header h3 {{
      color: var(--gold-light);
      font-size: 1.15rem;
    }}

    .modal-body {{
      padding: 24px;
      overflow-y: auto;
      font-size: 0.95rem;
      color: var(--text-main);
      white-space: pre-wrap;
      line-height: 1.8;
    }}

    .close-btn {{
      background: none;
      border: none;
      color: var(--text-muted);
      font-size: 1.5rem;
      cursor: pointer;
    }}

    .close-btn:hover {{
      color: #fff;
    }}

    @media (max-width: 640px) {{
      .hero-banner {{ flex-direction: column; align-items: center; text-align: center; padding: 18px 16px; gap: 14px; }}
      .hero-cover {{ width: 96px; height: 96px; }}
      .hero-meta {{ justify-content: center; }}
      .hero-desc {{ text-align: left; font-size: 0.9rem; }}
      .badge-private {{ white-space: nowrap; flex-shrink: 0; }}
    }}
  </style>
</head>
<body>

  <header>
    <div class="header-inner">
      <div class="brand">
        <img src="cover.jpg" alt="Cover" class="brand-icon">
        <div>
          <h1>{series_info['title']}</h1>
        </div>
      </div>
      <span class="badge-private">🔒 專屬不公開預覽</span>
    </div>
  </header>

  <main>
    <section class="hero-banner">
      <img src="cover.jpg" alt="Series Cover" class="hero-cover">
      <div class="hero-content">
        <h2>{series_info['title']}</h2>
        <div class="hero-meta">
          <span>{len(episodes)} 集全</span>
          <span>•</span>
          <span>{series_info['status']}</span>
        </div>
        <p class="hero-desc">{series_info['description']}</p>
      </div>
    </section>

    <div class="section-title">
      <span>🎙️ 各集選播</span>
    </div>

    <div class="episode-list" id="episodesContainer">
      <!-- Injected by JS -->
    </div>

    <div class="section-title" id="docsTitle" style="display: none;">
      <span>📑 隨選文獻與行前指南</span>
    </div>
    <div class="docs-grid" id="docsContainer">
      <!-- Injected by JS -->
    </div>
  </main>

  <!-- Player Bar -->
  <div class="player-bar">
    <div class="player-inner">
      <div class="player-top">
        <div class="now-playing">
          <span id="nowPlayingTitle" class="now-title">點選上方任一集開始播放</span>
        </div>
        <div class="player-controls">
          <button class="ctrl-btn" onclick="seekBy(-15)" title="倒退 15 秒">↺ 15s</button>
          <button class="ctrl-btn ctrl-btn-play" id="playBtn" onclick="togglePlay()">▶</button>
          <button class="ctrl-btn" onclick="seekBy(30)" title="快進 30 秒">30s ↻</button>
          <button class="rate-btn" id="rateBtn" onclick="togglePlaybackRate()">1.0x</button>
        </div>
      </div>
      <div class="progress-wrap">
        <span class="time-lbl" id="currTime">00:00</span>
        <div class="progress-bar" id="progressBar" onclick="seekClick(event)">
          <div class="progress-fill" id="progressFill"></div>
        </div>
        <span class="time-lbl time-right" id="totalTime">00:00</span>
      </div>
    </div>
  </div>

  <audio id="audioElement" preload="metadata"></audio>

  <!-- Modal -->
  <div class="modal-backdrop" id="docModal">
    <div class="modal-card">
      <div class="modal-header">
        <h3 id="modalTitle">文獻閱讀</h3>
        <button class="close-btn" onclick="closeDocModal()">&times;</button>
      </div>
      <div class="modal-body" id="modalBody"></div>
    </div>
  </div>

  <script>
    const DATA = {data_json_str};
    const audio = document.getElementById('audioElement');
    let currentIndex = -1;
    const rates = [1.0, 1.2, 1.5, 1.8, 2.0];
    let rateIdx = 0;

    function init() {{
      renderEpisodes();
      renderDocs();
      setupAudioListeners();
    }}

    function renderEpisodes() {{
      const container = document.getElementById('episodesContainer');
      container.innerHTML = '';
      DATA.episodes.forEach((ep, idx) => {{
        const card = document.createElement('div');
        card.className = 'episode-card';
        card.id = `ep-card-${{idx}}`;
        card.onclick = (e) => {{
          if (e.target.tagName !== 'BUTTON') playEpisode(idx);
        }};

        card.innerHTML = `
          <div class="ep-left">
            <button class="play-btn" onclick="event.stopPropagation(); playEpisode(${{idx}})" id="card-btn-${{idx}}">▶</button>
            <div class="ep-info">
              <h3>${{ep.title}}</h3>
              <p>${{ep.summary || ep.full_notes || '點擊即可即時收聽完整節目'}}</p>
            </div>
          </div>
          <span class="ep-duration">${{ep.duration_fmt}}</span>
        `;
        container.appendChild(card);
      }});
    }}

    function renderDocs() {{
      if (!DATA.ref_docs_list || DATA.ref_docs_list.length === 0) return;
      document.getElementById('docsTitle').style.display = 'flex';
      const container = document.getElementById('docsContainer');
      container.innerHTML = '';
      DATA.ref_docs_list.forEach(doc => {{
        const pill = document.createElement('div');
        pill.className = 'doc-pill';
        pill.onclick = () => openDoc(doc.id, doc.title, doc.url, doc.is_pdf);
        pill.innerHTML = `
          <span>📄 ${{doc.title}}</span>
          <span style="font-size:0.8rem; color:var(--gold-dim);">${{doc.ext.toUpperCase()}}</span>
        `;
        container.appendChild(pill);
      }});
    }}

    function playEpisode(index) {{
      if (currentIndex === index && !audio.paused) {{
        audio.pause();
        updatePlayState(false);
        return;
      }}

      currentIndex = index;
      const ep = DATA.episodes[index];
      audio.src = ep.audio_url;
      audio.playbackRate = rates[rateIdx];
      audio.play();

      document.getElementById('nowPlayingTitle').textContent = ep.title;
      document.querySelectorAll('.episode-card').forEach(c => c.classList.remove('active'));
      const activeCard = document.getElementById(`ep-card-${{index}}`);
      if (activeCard) activeCard.classList.add('active');

      updatePlayState(true);
    }}

    function togglePlay() {{
      if (currentIndex === -1) {{
        playEpisode(0);
        return;
      }}
      if (audio.paused) {{
        audio.play();
        updatePlayState(true);
      }} else {{
        audio.pause();
        updatePlayState(false);
      }}
    }}

    function updatePlayState(isPlaying) {{
      const mainBtn = document.getElementById('playBtn');
      mainBtn.textContent = isPlaying ? '⏸' : '▶';
      DATA.episodes.forEach((_, idx) => {{
        const btn = document.getElementById(`card-btn-${{idx}}`);
        if (btn) {{
          btn.textContent = (idx === currentIndex && isPlaying) ? '⏸' : '▶';
        }}
      }});
    }}

    function seekBy(seconds) {{
      if (!audio.duration) return;
      audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
    }}

    function togglePlaybackRate() {{
      rateIdx = (rateIdx + 1) % rates.length;
      const r = rates[rateIdx];
      audio.playbackRate = r;
      document.getElementById('rateBtn').textContent = r.toFixed(1) + 'x';
    }}

    function seekClick(e) {{
      if (!audio.duration) return;
      const bar = document.getElementById('progressBar');
      const rect = bar.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const ratio = Math.max(0, Math.min(1, clickX / rect.width));
      audio.currentTime = ratio * audio.duration;
    }}

    function setupAudioListeners() {{
      audio.ontimeupdate = () => {{
        if (!audio.duration) return;
        const ratio = (audio.currentTime / audio.duration) * 100;
        document.getElementById('progressFill').style.width = ratio + '%';
        document.getElementById('currTime').textContent = fmtTime(audio.currentTime);
      }};

      audio.onloadedmetadata = () => {{
        document.getElementById('totalTime').textContent = fmtTime(audio.duration);
      }};

      audio.onended = () => {{
        if (currentIndex < DATA.episodes.length - 1) {{
          playEpisode(currentIndex + 1);
        }} else {{
          updatePlayState(false);
        }}
      }};
    }}

    function fmtTime(sec) {{
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return `${{m.toString().padStart(2, '0')}}:${{s.toString().padStart(2, '0')}}`;
    }}

    function openDoc(docId, title, url, isPdf) {{
      if (isPdf) {{
        window.open(url, '_blank');
        return;
      }}
      const content = DATA.series_docs_content[docId] || '尚無內容';
      document.getElementById('modalTitle').textContent = `📑 ${{title}}`;
      document.getElementById('modalBody').textContent = content;
      document.getElementById('docModal').classList.add('active');
    }}

    function closeDocModal() {{
      document.getElementById('docModal').classList.remove('active');
    }}

    window.onclick = (e) => {{
      const modal = document.getElementById('docModal');
      if (e.target === modal) closeDocModal();
    }};

    init();
  </script>
</body>
</html>
"""
    out_html = os.path.join(output_dir, "index.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   [OK] Generated private companion player -> {out_html} ({len(html_content):,} bytes)")

def main():
    print("=== Scanning Private / Unlisted Caves ===")
    entries = parse_private_caves()
    if not entries:
        print("[INFO] No private series configured in private_caves.txt.")
        return

    for entry in entries:
        build_private_series(entry)

    print("\n[SUCCESS] Private series processing complete!")

if __name__ == "__main__":
    main()
