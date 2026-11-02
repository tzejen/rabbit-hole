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

    # Copy channel avatar for upper-right 兔子洞筆記 brand display
    channel_avatar_dst = os.path.join(target_dir, "cover_channel.png")
    channel_avatar_src = os.path.join(DIST_DIR, "cover_channel.png")
    if not os.path.exists(channel_avatar_src):
        channel_avatar_src = os.path.join(DIST_DIR, "cover_channel_1400.jpg")
    if os.path.exists(channel_avatar_src):
        shutil.copy2(channel_avatar_src, channel_avatar_dst)

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

    # Scan References (exclude episode transcripts / 逐字稿)
    ref_docs_list = []
    series_docs_content = {}
    active_doc_fnames = set()
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
            if "逐字稿" in fname or "transcript" in fname.lower():
                continue
            if ext_lower not in ALLOWED_EXTENSIONS:
                continue

            active_doc_fnames.add(fname)
            clean_doc_title = re.sub(r"^\d+[\._\-\s]*", "", base_name).strip()
            clean_doc_title = re.sub(r"^\[.*?\]\s*", "", clean_doc_title).strip()
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

    if os.path.exists(docs_dir):
        for existing_doc in os.listdir(docs_dir):
            if existing_doc not in active_doc_fnames:
                try:
                    os.remove(os.path.join(docs_dir, existing_doc))
                except Exception:
                    pass

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

    total_dur_sec = sum(ep.get("duration_sec", 0.0) for ep in episodes)
    summary = {
        "slug": slug,
        "title": s_title,
        "status": status,
        "dir": os.path.basename(s_dir),
        "description": series_desc,
        "cover_url": f"{slug}/{cover_dst_name}",
        "episode_count": len(episodes),
        "total_duration_sec": total_dur_sec,
        "total_duration_fmt": format_duration(total_dur_sec),
        "web_path": f"{slug}/",
        "full_url": f"https://{user}.github.io/{repo}/p/{slug}/",
        "episodes": [
            {
                "episode": ep["episode"],
                "title": ep["title"],
                "duration_fmt": ep["duration_fmt"],
                "filename": ep["filename"]
            }
            for ep in episodes
        ],
        "ref_docs_count": len(ref_docs_list),
        "ref_docs": [
            {
                "title": doc["title"],
                "filename": doc["filename"],
                "ext": doc["ext"],
                "url": f"{slug}/{doc['url']}"
            }
            for doc in ref_docs_list
        ]
    }
    return summary

def generate_private_html(output_dir, series_info, episodes, ref_docs, docs_content):
    for ep in episodes:
        ep["summary"] = (ep.get("summary") or "").replace("Created with Gemini Antigravity and Google Notebook", "").strip()
        ep["full_notes"] = (ep.get("full_notes") or "").replace("Created with Gemini Antigravity and Google Notebook", "").strip()

    total_sec = sum(ep.get("duration_sec", 0.0) for ep in episodes)
    dur_hours = round(total_sec / 3600 * 10) / 10
    dur_text = f"{dur_hours} 小時" if dur_hours >= 1 else f"{round(total_sec / 60)} 分鐘"

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
  <title>{series_info['title']} — 兔子洞筆記</title>
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
      -webkit-font-smoothing: antialiased;
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
      padding: 0 20px;
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
      justify-content: flex-end;
      align-items: center;
      padding: 12px 0;
    }}
    .brand-group {{
      display: flex;
      align-items: center;
      gap: 14px;
      cursor: default;
      user-select: none;
      min-width: 0;
    }}
    .brand-avatar {{
      width: 44px;
      height: 44px;
      border-radius: 10px;
      object-fit: cover;
      border: 1px solid var(--border-color);
      flex-shrink: 0;
    }}
    .brand-title {{
      font-size: 19px;
      font-weight: 700;
      color: #ffffff;
      letter-spacing: 0.5px;
      white-space: nowrap;
    }}
    .brand-subtitle {{
      font-size: 12px;
      color: var(--gold-light);
      font-weight: 400;
      margin-top: 1px;
      white-space: nowrap;
    }}

    .series-toggle-btn {{
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      color: var(--text-muted);
      border-radius: 6px;
      padding: 5px 10px;
      font-size: 12px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      flex-shrink: 0;
      transition: all 0.2s;
      white-space: nowrap;
    }}
    .series-toggle-btn:hover {{
      border-color: var(--gold-primary);
      color: var(--gold-light);
      background: rgba(212, 175, 55, 0.1);
    }}

    /* Series Hero Banner (Header Box) */
    .hero-banner {{
      background: linear-gradient(145deg, #131d35 0%, #172442 100%);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      padding: 28px;
      margin: 20px 0 24px;
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
    .hero-tag-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
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
      white-space: nowrap;
    }}
    .hero-title {{
      font-size: 24px;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 10px;
      line-height: 1.3;
      word-break: break-word;
    }}
    .hero-desc {{
      display: none;
      font-size: 14px;
      color: var(--text-muted);
      line-height: 1.6;
      margin-bottom: 14px;
      padding: 10px 14px;
      background: rgba(11, 17, 32, 0.4);
      border-radius: 8px;
      border-left: 3px solid var(--gold-primary);
      text-align: left;
      white-space: pre-line;
    }}
    .hero-desc.show {{
      display: block;
    }}
    .hero-stats {{
      display: flex;
      align-items: center;
      gap: 18px;
      font-size: 13px;
      color: var(--text-dim);
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}
    .stat-item {{
      white-space: nowrap;
      display: inline-flex;
      align-items: baseline;
      gap: 4px;
    }}
    .stat-item b {{
      color: var(--gold-light);
      font-weight: 600;
      white-space: nowrap;
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
      white-space: nowrap;
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
      white-space: nowrap;
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
      white-space: nowrap;
    }}
    .ep-text-block {{
      flex: 1;
      min-width: 0;
    }}
    .ep-title {{
      font-size: 16px;
      font-weight: 600;
      color: var(--text-main);
      line-height: 1.4;
      word-break: break-word;
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
      white-space: nowrap;
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
      white-space: pre-line;
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
      white-space: nowrap;
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
      max-width: 1000px;
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
      white-space: nowrap;
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
      width: 100px;
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
      white-space: nowrap;
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
      max-width: 720px;
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
      .container {{
        padding: 0 14px;
      }}
      .header-content {{
        padding: 10px 0;
        gap: 8px;
      }}
      .brand-group {{
        gap: 10px;
      }}
      .brand-avatar {{
        width: 38px;
        height: 38px;
        border-radius: 8px;
      }}
      .brand-title {{
        font-size: 17px;
      }}
      .brand-subtitle {{
        font-size: 11px;
      }}
      .hero-banner {{
        flex-direction: column;
        text-align: center;
        padding: 18px 16px;
        gap: 14px;
      }}
      .hero-cover {{
        width: 96px;
        height: 96px;
        border-radius: 12px;
      }}
      .hero-tag-row {{
        justify-content: center;
      }}
      .hero-title {{
        font-size: 19px;
      }}
      .hero-desc {{
        font-size: 13px;
        text-align: left;
      }}
      .hero-stats {{
        justify-content: center;
        gap: 12px;
        font-size: 12.5px;
      }}
      .series-resources {{
        justify-content: center;
      }}
      .resources-pills-wrap {{
        justify-content: center;
      }}
      .episode-card {{
        padding: 12px 14px;
      }}
      .ep-header {{
        gap: 10px;
      }}
      .ep-main-info {{
        gap: 12px;
      }}
      .ep-title {{
        font-size: 14.5px;
      }}
      .ep-toggle-btn {{
        padding: 5px 8px;
        font-size: 11.5px;
      }}
      .bottom-player {{
        padding: 10px 14px calc(10px + env(safe-area-inset-bottom));
      }}
      .player-inner {{
        display: grid;
        grid-template-columns: 1fr auto auto;
        gap: 8px 10px;
        align-items: center;
      }}
      .player-center {{
        display: contents;
      }}
      .track-info {{
        grid-column: 1;
        grid-row: 1;
        width: auto;
        gap: 8px;
      }}
      .track-thumb {{
        width: 36px;
        height: 36px;
        border-radius: 6px;
      }}
      .track-title {{
        font-size: 13px;
      }}
      .track-artist {{
        font-size: 11px;
      }}
      .controls-row {{
        grid-column: 2;
        grid-row: 1;
        gap: 8px;
      }}
      .ctrl-btn-play {{
        width: 36px;
        height: 36px;
      }}
      .player-right {{
        grid-column: 3;
        grid-row: 1;
        width: auto;
        display: flex;
      }}
      .speed-btn {{
        padding: 3px 6px;
        font-size: 11px;
      }}
      .progress-row {{
        grid-column: 1 / -1;
        grid-row: 2;
        gap: 8px;
      }}
    }}
  </style>
</head>
<body>

  <header class="site-header">
    <div class="container">
      <div class="header-content">
        <div class="brand-group">
          <img src="cover_channel.png" onerror="this.src='cover.jpg'" alt="兔子洞筆記封面" class="brand-avatar">
          <div>
            <div class="brand-title">兔子洞筆記</div>
            <div class="brand-subtitle">Notes from the Rabbit Hole</div>
          </div>
        </div>
      </div>
    </div>
  </header>

  <div class="container">
    <!-- Series View: Hero Banner (Header Box) -->
    <section class="hero-banner" id="seriesHeroBanner">
      <img id="heroCoverImg" src="cover.jpg" alt="系列封面" class="hero-cover">
      <div class="hero-info">
        <div class="hero-tag-row">
          <div class="hero-cave-tag" id="heroCaveTag">{series_info['status']}</div>
          <button class="series-toggle-btn" id="heroDescToggleBtn" onclick="toggleHeroDesc()">簡介 ▾</button>
        </div>
        <h1 class="hero-title" id="heroTitle">{series_info['title']}</h1>
        <p class="hero-desc" id="heroDesc">{series_info['description']}</p>
        <div class="hero-stats" id="heroStats">
          <div class="stat-item">集數：<b id="heroStatCount">{len(episodes)} 集</b></div>
          <div class="stat-item">總長：<b id="heroStatDur">{dur_text}</b></div>
          <div class="stat-item">狀態：<b id="heroStatStatus">{series_info['status']}</b></div>
        </div>

        <div class="series-resources" id="seriesResourcesBox" style="display: none;">
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
        <img id="playerThumb" src="cover.jpg" class="track-thumb" alt="封面">
        <div class="track-text">
          <div class="track-title" id="playerTitle">點擊任一單集開始收聽</div>
          <div class="track-artist" id="playerArtist">{series_info['title']}</div>
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

  <!-- Resource Document Modal -->
  <div class="modal-backdrop" id="resourceModal" onclick="closeModal('resourceModal')">
    <div class="modal-window" onclick="event.stopPropagation()">
      <button class="modal-close" onclick="closeModal('resourceModal')">&times;</button>
      <div class="modal-title" id="resourceModalTitle">📑 參考資料</div>
      <pre class="pre-box" id="resourceModalContent"></pre>
    </div>
  </div>

  <script>
    const DATA = {data_json_str};
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
      renderSeriesResources();
      renderEpisodesList();
    }}

    function toggleHeroDesc() {{
      const descEl = document.getElementById('heroDesc');
      const btn = document.getElementById('heroDescToggleBtn');
      if (!descEl || !btn) return;

      if (descEl.classList.contains('show')) {{
        descEl.classList.remove('show');
        btn.innerHTML = '簡介 ▾';
      }} else {{
        descEl.classList.add('show');
        btn.innerHTML = '收合 ▴';
      }}
    }}

    function renderSeriesResources() {{
      const box = document.getElementById('seriesResourcesBox');
      const wrap = document.getElementById('resourcesPillsWrap');
      const docs = DATA.ref_docs_list || [];

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

    function renderEpisodesList() {{
      const list = document.getElementById('episodesList');
      list.innerHTML = DATA.episodes.map(ep => {{
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
                  <div class="ep-title">${{ep.title}}</div>
                </div>
              </div>
              <button class="ep-toggle-btn" onclick="toggleDetails('${{ep.release_filename}}', event)">
                展開 ▾
              </button>
            </div>

            <div class="ep-details" id="details-${{ep.release_filename}}">
              <div class="ep-summary-text">${{ep.summary || ep.full_notes || ''}}</div>
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
      const ep = DATA.episodes.find(e => e.release_filename === relFname);
      if (!ep) return;

      if (currentPlayingEp && currentPlayingEp.release_filename === relFname && audio.src) {{
        togglePlay();
      }} else {{
        loadAndPlayEpisode(ep);
      }}
    }}

    function loadAndPlayEpisode(ep) {{
      currentPlayingEp = ep;
      audio.src = ep.audio_url;
      audio.playbackRate = speeds[currentSpeedIdx];
      playerTitle.textContent = ep.title;
      playerArtist.textContent = ep.series_title;
      playerThumb.src = ep.cover_image || 'cover.jpg';

      updateAllCardPlayStates(true);
      audio.play().then(() => {{
        isPlaying = true;
        updatePlayIcons(true);
      }}).catch(e => console.log('Audio playback error: ', e));
    }}

    function jumpToChapter(relFname, timestamp) {{
      const ep = DATA.episodes.find(e => e.release_filename === relFname);
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
        if (DATA.episodes.length > 0) {{
          loadAndPlayEpisode(DATA.episodes[0]);
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
        const fname = c.id.replace('card-', '');
        const btn = document.getElementById(`play-btn-${{fname}}`);
        if (btn) btn.innerHTML = SVG_PLAY;
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
      const idx = DATA.episodes.findIndex(e => e.release_filename === currentPlayingEp.release_filename);
      if (idx !== -1 && idx < DATA.episodes.length - 1) {{
        loadAndPlayEpisode(DATA.episodes[idx + 1]);
      }}
    }}

    function playPrev() {{
      if (!currentPlayingEp) return;
      const idx = DATA.episodes.findIndex(e => e.release_filename === currentPlayingEp.release_filename);
      if (idx > 0) {{
        loadAndPlayEpisode(DATA.episodes[idx - 1]);
      }}
    }}

    function skipTime(delta) {{
      if (!audio.duration) return;
      audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + delta));
    }}

    function seek(e) {{
      if (!audio.duration) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const pos = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      audio.currentTime = pos * audio.duration;
    }}

    function cycleSpeed() {{
      currentSpeedIdx = (currentSpeedIdx + 1) % speeds.length;
      const spd = speeds[currentSpeedIdx];
      audio.playbackRate = spd;
      speedBtn.textContent = `${{spd.toFixed(spd % 1 === 0 ? 1 : 2)}}x`;
    }}

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

    function openDocModal(docId, docTitle) {{
      const modal = document.getElementById('resourceModal');
      const title = document.getElementById('resourceModalTitle');
      const box = document.getElementById('resourceModalContent');

      title.textContent = `📑 ${{docTitle}}`;
      box.textContent = DATA.series_docs_content[docId] || '尚無文檔內容。';
      modal.classList.add('active');
    }}

    function closeModal(id) {{
      document.getElementById(id).classList.remove('active');
    }}

    init();
  </script>
</body>
</html>
"""
    out_html = os.path.join(output_dir, "index.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   [OK] Generated private companion player -> {out_html} ({len(html_content):,} bytes)")

def scan_workspace_other_series(configured_dirs):
    public_dirs = set()
    caves_path = os.path.join(DIST_DIR, "caves.txt")
    if os.path.exists(caves_path):
        with open(caves_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3 and parts[2]:
                    d = parts[2]
                    p = os.path.join(BASE_DIR, d) if not os.path.isabs(d) else d
                    if os.path.exists(p):
                        public_dirs.add(os.path.abspath(p))

    known_dirs = set(configured_dirs).union(public_dirs)
    known_dirs.add(os.path.abspath(DIST_DIR))
    scripts_dir = os.path.join(BASE_DIR, "scripts")
    if os.path.exists(scripts_dir):
        known_dirs.add(os.path.abspath(scripts_dir))
    archive_dir = os.path.join(BASE_DIR, "Archive")
    if os.path.exists(archive_dir):
        known_dirs.add(os.path.abspath(archive_dir))

    other_series = []
    try:
        for entry in os.scandir(BASE_DIR):
            if not entry.is_dir():
                continue
            abs_p = os.path.abspath(entry.path)
            if abs_p in known_dirs:
                continue
            if entry.name.startswith(".") or entry.name.startswith("_"):
                continue

            # Check for m4a files
            m4as = sorted([
                f for f in glob.glob(os.path.join(entry.path, "[0-9][0-9]_*.m4a"))
                if "Candidate" not in os.path.basename(f)
                and "MicroCut" not in os.path.basename(f)
                and "_v" not in os.path.basename(f)
            ])
            if not m4as:
                m4as = sorted([
                    f for f in glob.glob(os.path.join(entry.path, "*.m4a"))
                    if "Candidate" not in os.path.basename(f)
                    and "MicroCut" not in os.path.basename(f)
                    and "_v" not in os.path.basename(f)
                ])

            if m4as:
                sample_titles = []
                for f in m4as[:3]:
                    base = os.path.splitext(os.path.basename(f))[0]
                    clean = re.sub(r"^(?:Ep\d+|\d+)[\s\-_:：]*", "", base).strip()
                    sample_titles.append(clean or base)

                other_series.append({
                    "dir_name": entry.name,
                    "count": len(m4as),
                    "sample_episodes": sample_titles
                })
    except Exception as e:
        print(f"[WARN] Error scanning other workspace series: {e}")

    other_series.sort(key=lambda x: x["dir_name"])
    return other_series

def generate_private_index(series_summaries, other_workspace_series):
    user = CHANNEL_META.get("github_user", "tzejen")
    repo = CHANNEL_META.get("github_repo", "rabbit-hole")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    total_series = len(series_summaries)
    total_episodes = sum(s["episode_count"] for s in series_summaries)
    total_dur_sec = sum(s["total_duration_sec"] for s in series_summaries)
    total_dur_fmt = format_duration(total_dur_sec)

    index_data = {
        "updated_at": now_str,
        "github_user": user,
        "github_repo": repo,
        "total_series": total_series,
        "total_episodes": total_episodes,
        "total_duration_sec": total_dur_sec,
        "total_duration_fmt": total_dur_fmt,
        "series": series_summaries,
        "workspace_other_series": other_workspace_series
    }

    # Save JSON manifest
    json_path = os.path.join(P_ROOT_DIR, "private_series.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)
    print(f"   [OK] Saved private series JSON -> {json_path}")

    # Build dynamic web page
    data_json_literal = json.dumps(index_data, ensure_ascii=False)

    html_template = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="robots" content="noindex, nofollow, noarchive">
  <title>私密專題清單 · 兔子洞筆記</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🐇</text></svg>">
  <style>
    :root {
      --bg: #0d1117;
      --card-bg: #161b22;
      --card-hover: #1c2128;
      --border: #30363d;
      --border-accent: #388bfd44;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --text-light: #f0f6fc;
      --accent: #58a6ff;
      --accent-hover: #79c0ff;
      --green: #3fb950;
      --green-bg: #23863622;
      --green-border: #23863655;
      --gold: #d29922;
      --gold-bg: #bb800922;
      --purple: #bc8cff;
      --purple-bg: #8957e522;
      --shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", "PingFang TC", Roboto, sans-serif;
      line-height: 1.5;
      padding: 24px 16px 80px;
    }
    .container {
      max-width: 960px;
      margin: 0 auto;
    }
    /* Header */
    header {
      margin-bottom: 28px;
    }
    .header-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-icon {
      font-size: 32px;
      line-height: 1;
    }
    .brand-title {
      font-size: 24px;
      font-weight: 700;
      color: var(--text-light);
      letter-spacing: -0.5px;
    }
    .private-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--gold-bg);
      color: var(--gold);
      border: 1px solid rgba(210, 153, 34, 0.3);
      font-weight: 600;
    }
    .header-desc {
      color: var(--text-muted);
      font-size: 14px;
      line-height: 1.6;
    }
    /* Stats Bar */
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 28px;
    }
    .stat-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
    }
    .stat-label {
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .stat-val {
      font-size: 20px;
      font-weight: 700;
      color: var(--text-light);
    }
    /* Toolbar */
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
      background: var(--card-bg);
      border: 1px solid var(--border);
      padding: 12px 16px;
      border-radius: 8px;
    }
    .search-box {
      flex: 1;
      min-width: 240px;
      position: relative;
    }
    .search-input {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 12px 8px 34px;
      font-size: 14px;
      color: var(--text-light);
      outline: none;
      transition: border-color 0.15s ease;
    }
    .search-input:focus {
      border-color: var(--accent);
    }
    .search-icon {
      position: absolute;
      left: 10px;
      top: 50%;
      transform: translateY(-50%);
      font-size: 14px;
      color: var(--text-muted);
      pointer-events: none;
    }
    .filter-group {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .filter-btn {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .filter-btn:hover {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-light);
    }
    .filter-btn.active {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 600;
    }
    /* Series Cards */
    .series-list {
      display: flex;
      flex-direction: column;
      gap: 16px;
      margin-bottom: 36px;
    }
    .series-card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
      transition: transform 0.15s ease, border-color 0.15s ease;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .series-card:hover {
      border-color: var(--border-accent);
    }
    .card-main {
      display: flex;
      gap: 20px;
      align-items: flex-start;
    }
    .card-cover {
      width: 100px;
      height: 100px;
      border-radius: 8px;
      object-fit: cover;
      flex-shrink: 0;
      background: #21262d;
      border: 1px solid var(--border);
    }
    .card-body {
      flex: 1;
      min-width: 0;
    }
    .card-tags {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .tag {
      font-size: 11px;
      padding: 2px 8px;
      border-radius: 4px;
      font-weight: 600;
      line-height: 1.4;
    }
    .tag-status {
      background: var(--purple-bg);
      color: var(--purple);
      border: 1px solid rgba(188, 140, 255, 0.3);
    }
    .tag-slug {
      background: var(--green-bg);
      color: var(--green);
      border: 1px solid var(--green-border);
      font-family: monospace;
    }
    .tag-dir {
      background: rgba(255, 255, 255, 0.05);
      color: var(--text-muted);
      border: 1px solid var(--border);
    }
    .card-title {
      font-size: 18px;
      font-weight: 700;
      color: var(--text-light);
      margin-bottom: 6px;
      line-height: 1.35;
    }
    .card-title a {
      color: inherit;
      text-decoration: none;
    }
    .card-title a:hover {
      color: var(--accent);
      text-decoration: underline;
    }
    .card-desc {
      font-size: 13px;
      color: var(--text-muted);
      line-height: 1.5;
      margin-bottom: 12px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .card-meta-line {
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
      font-size: 13px;
      color: var(--text-muted);
    }
    .card-meta-item {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    /* Actions */
    .card-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      border-top: 1px solid rgba(255, 255, 255, 0.06);
      padding-top: 14px;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 14px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.15s ease;
      border: 1px solid transparent;
    }
    .btn-primary {
      background: var(--accent);
      color: #0d1117;
    }
    .btn-primary:hover {
      background: var(--accent-hover);
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.06);
      color: var(--text-light);
      border-color: var(--border);
    }
    .btn-secondary:hover {
      background: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
    }
    .btn-toggle {
      margin-left: auto;
      font-size: 12px;
      color: var(--text-muted);
      background: transparent;
      border: none;
      cursor: pointer;
      padding: 4px 8px;
    }
    .btn-toggle:hover {
      color: var(--text-light);
    }
    /* Tracklist Drawer */
    .tracklist-drawer {
      display: none;
      border-top: 1px dashed var(--border);
      padding-top: 14px;
      margin-top: 2px;
    }
    .tracklist-drawer.open {
      display: block;
    }
    .tracklist-grid {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .track-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 6px 10px;
      border-radius: 4px;
      font-size: 13px;
      background: rgba(0, 0, 0, 0.2);
    }
    .track-row:hover {
      background: rgba(255, 255, 255, 0.04);
    }
    .track-name {
      color: var(--text-light);
      text-decoration: none;
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-right: 12px;
    }
    .track-name:hover {
      color: var(--accent);
    }
    .track-dur {
      color: var(--text-muted);
      font-family: monospace;
      font-size: 12px;
    }
    /* Workspace Other Series */
    .section-box {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
    }
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      cursor: pointer;
      user-select: none;
    }
    .section-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text-light);
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .section-count {
      font-size: 12px;
      padding: 2px 8px;
      background: rgba(255, 255, 255, 0.08);
      border-radius: 999px;
      color: var(--text-muted);
    }
    .section-body {
      margin-top: 16px;
      display: none;
    }
    .section-body.open {
      display: block;
    }
    .other-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }
    .other-card {
      background: rgba(0, 0, 0, 0.25);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
    }
    .other-name {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-light);
      margin-bottom: 4px;
    }
    .other-meta {
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 6px;
    }
    .other-sample {
      font-size: 11px;
      color: #8b949e;
      line-height: 1.4;
      background: rgba(255, 255, 255, 0.03);
      padding: 4px 8px;
      border-radius: 4px;
    }
    .tip-box {
      margin-top: 16px;
      padding: 12px;
      border-radius: 6px;
      background: rgba(88, 166, 255, 0.08);
      border: 1px solid rgba(88, 166, 255, 0.2);
      font-size: 13px;
      color: #9ac2ef;
      line-height: 1.6;
    }
    .tip-box code {
      background: rgba(0, 0, 0, 0.3);
      padding: 2px 6px;
      border-radius: 4px;
      color: #79c0ff;
      font-family: monospace;
    }
    /* Toast */
    #toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #238636;
      color: #fff;
      padding: 10px 18px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      box-shadow: var(--shadow);
      display: none;
      z-index: 1000;
      animation: fadeIn 0.2s ease-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    /* Empty State */
    .empty-state {
      text-align: center;
      padding: 48px 16px;
      color: var(--text-muted);
      font-size: 14px;
    }
    @media (max-width: 600px) {
      .card-main {
        flex-direction: column;
      }
      .card-cover {
        width: 100%;
        height: 140px;
      }
      .btn-toggle {
        margin-left: 0;
        width: 100%;
        text-align: left;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="header-top">
        <div class="brand">
          <span class="brand-icon">🐇</span>
          <div>
            <h1 class="brand-title">私密專題總覽</h1>
          </div>
        </div>
        <span class="private-badge">🔒 未公開空間 · Disallow: /p/</span>
      </div>
      <p class="header-desc">
        本頁自動彙整 <code>private_caves.txt</code> 中配置的所有秘密路徑專題，提供快速直連與集數備忘。
        頁面絕不會出現於公開首頁或 RSS 饋送。
      </p>
    </header>

    <!-- Stats -->
    <div class="stats-grid" id="statsGrid">
      <div class="stat-card">
        <span class="stat-label">私密專題數</span>
        <span class="stat-val" id="statSeries">0</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">總音檔集數</span>
        <span class="stat-val" id="statEpisodes">0</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">總播放時長</span>
        <span class="stat-val" id="statDuration">00:00</span>
      </div>
      <div class="stat-card">
        <span class="stat-label">最後動態同步</span>
        <span class="stat-val" style="font-size: 15px;" id="statUpdated">--</span>
      </div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" class="search-input" placeholder="搜尋專題、集名、資料夾或 Slug... (按 / 聚焦)">
      </div>
      <div class="filter-group" id="filterGroup">
        <button class="filter-btn active" data-filter="all">全部</button>
      </div>
    </div>

    <!-- Series Cards Container -->
    <div class="series-list" id="seriesList">
      <!-- Dynamic rendered series cards -->
    </div>

    <!-- Other Workspace Series Section -->
    <div class="section-box" id="workspaceOtherSection">
      <div class="section-header" onclick="toggleWorkspaceSection()">
        <span class="section-title">
          <span>📁 工作區其他待發布專題</span>
          <span class="section-count" id="otherSeriesCount">0</span>
        </span>
        <span id="otherSectionArrow" style="color: var(--text-muted);">▾ 展開</span>
      </div>
      <div class="section-body" id="workspaceSectionBody">
        <div class="other-grid" id="otherGrid"></div>
        <div class="tip-box">
          💡 <strong>如何發布為私密專題？</strong><br>
          只需在 <code>podcast_distribution/private_caves.txt</code> 新增一行：<br>
          <code>secret-slug | 專題標題 | 資料夾名稱 | 狀態標籤</code><br>
          再執行 <code>更新發布網站.bat</code> 或 <code>python build_private.py</code>，即可自動生成專屬播放器並收錄於此頁面！
        </div>
      </div>
    </div>
  </div>

  <div id="toast">已複製私密連結！</div>

  <script>
    const INITIAL_DATA = """ + data_json_literal + """;
    let appData = INITIAL_DATA;
    let activeFilter = 'all';

    function init() {
      renderStats();
      renderFilters();
      renderSeries();
      renderOtherSeries();

      // Setup search
      const searchInput = document.getElementById('searchInput');
      searchInput.addEventListener('input', () => {
        renderSeries();
      });

      // Keyboard shortcut '/'
      window.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== searchInput) {
          e.preventDefault();
          searchInput.focus();
        } else if (e.key === 'Escape' && document.activeElement === searchInput) {
          searchInput.value = '';
          searchInput.blur();
          renderSeries();
        }
      });

      // Background fresh fetch when hosted over HTTP/HTTPS
      if (location.protocol.startsWith('http')) {
        fetch('./private_series.json?t=' + Date.now())
          .then(res => res.json())
          .then(data => {
            if (data && data.updated_at && data.updated_at !== appData.updated_at) {
              appData = data;
              renderStats();
              renderFilters();
              renderSeries();
              renderOtherSeries();
            }
          })
          .catch(() => {});
      }
    }

    function renderStats() {
      document.getElementById('statSeries').textContent = `${appData.total_series || 0} 個`;
      document.getElementById('statEpisodes').textContent = `${appData.total_episodes || 0} 集`;
      document.getElementById('statDuration').textContent = appData.total_duration_fmt || '00:00';
      document.getElementById('statUpdated').textContent = appData.updated_at || '--';
    }

    function renderFilters() {
      const group = document.getElementById('filterGroup');
      const statuses = new Set();
      (appData.series || []).forEach(s => {
        if (s.status) statuses.add(s.status);
      });

      let html = `<button class="filter-btn ${activeFilter === 'all' ? 'active' : ''}" onclick="setFilter('all')">全部</button>`;
      statuses.forEach(st => {
        html += `<button class="filter-btn ${activeFilter === st ? 'active' : ''}" onclick="setFilter('${st}')">${st}</button>`;
      });
      group.innerHTML = html;
    }

    function setFilter(filter) {
      activeFilter = filter;
      renderFilters();
      renderSeries();
    }

    function renderSeries() {
      const listEl = document.getElementById('seriesList');
      const query = (document.getElementById('searchInput').value || '').trim().toLowerCase();

      const filtered = (appData.series || []).filter(s => {
        if (activeFilter !== 'all' && s.status !== activeFilter) return false;
        if (!query) return true;

        const matchTitle = (s.title || '').toLowerCase().includes(query);
        const matchSlug = (s.slug || '').toLowerCase().includes(query);
        const matchDir = (s.dir || '').toLowerCase().includes(query);
        const matchDesc = (s.description || '').toLowerCase().includes(query);
        const matchEps = (s.episodes || []).some(ep => (ep.title || '').toLowerCase().includes(query));
        return matchTitle || matchSlug || matchDir || matchDesc || matchEps;
      });

      if (filtered.length === 0) {
        listEl.innerHTML = `<div class="empty-state">沒有符合條件的私密專題。</div>`;
        return;
      }

      const user = appData.github_user || 'tzejen';
      const repo = appData.github_repo || 'rabbit-hole';

      listEl.innerHTML = filtered.map(s => {
        const coverSrc = s.cover_url || '../cover_channel.png';
        const fullUrl = `https://${user}.github.io/${repo}/p/${s.slug}/`;
        const localUrl = `${s.slug}/`;

        const epRows = (s.episodes || []).map(ep => `
          <div class="track-row">
            <a class="track-name" href="${localUrl}" title="${escapeHtml(ep.title)}">
              ${escapeHtml(ep.title)}
            </a>
            <span class="track-dur">${ep.duration_fmt || ''}</span>
          </div>
        `).join('');

        return `
          <article class="series-card" data-slug="${s.slug}">
            <div class="card-main">
              <img class="card-cover" src="${coverSrc}" alt="${escapeHtml(s.title)}" onerror="this.src='../cover_channel.png'">
              <div class="card-body">
                <div class="card-tags">
                  <span class="tag tag-status">${escapeHtml(s.status || '未公開')}</span>
                  <span class="tag tag-slug">🔑 ${s.slug}</span>
                  <span class="tag tag-dir">📁 ${escapeHtml(s.dir || '')}</span>
                </div>
                <h2 class="card-title">
                  <a href="${localUrl}">${escapeHtml(s.title)}</a>
                </h2>
                ${s.description ? `<p class="card-desc">${escapeHtml(s.description)}</p>` : ''}
                <div class="card-meta-line">
                  <span class="card-meta-item">🎧 <strong>${s.episode_count || 0}</strong> 集</span>
                  <span class="card-meta-item">⏱️ <strong>${s.total_duration_fmt || '00:00'}</strong></span>
                  ${s.ref_docs_count ? `<span class="card-meta-item">📚 <strong>${s.ref_docs_count}</strong> 份文獻</span>` : ''}
                </div>
              </div>
            </div>

            <div class="card-actions">
              <a class="btn btn-primary" href="${localUrl}">
                🚀 進入播放頁
              </a>
              <button class="btn btn-secondary" onclick="copySecretLink('${fullUrl}')">
                📋 複製私密連結
              </button>
              <button class="btn-toggle" onclick="toggleTracks('${s.slug}')">
                <span id="toggleText_${s.slug}">📑 查看集數 (${s.episode_count}) ▾</span>
              </button>
            </div>

            <div class="tracklist-drawer" id="tracks_${s.slug}">
              <div class="tracklist-grid">
                ${epRows}
              </div>
            </div>
          </article>
        `;
      }).join('');
    }

    function toggleTracks(slug) {
      const drawer = document.getElementById(`tracks_${slug}`);
      const btnText = document.getElementById(`toggleText_${slug}`);
      if (!drawer) return;

      const isOpen = drawer.classList.contains('open');
      if (isOpen) {
        drawer.classList.remove('open');
        if (btnText) btnText.innerHTML = btnText.innerHTML.replace('▴', '▾');
      } else {
        drawer.classList.add('open');
        if (btnText) btnText.innerHTML = btnText.innerHTML.replace('▾', '▴');
      }
    }

    function toggleWorkspaceSection() {
      const body = document.getElementById('workspaceSectionBody');
      const arrow = document.getElementById('otherSectionArrow');
      const isOpen = body.classList.contains('open');
      if (isOpen) {
        body.classList.remove('open');
        arrow.textContent = '▾ 展開';
      } else {
        body.classList.add('open');
        arrow.textContent = '▴ 收合';
      }
    }

    function renderOtherSeries() {
      const others = appData.workspace_other_series || [];
      document.getElementById('otherSeriesCount').textContent = `${others.length} 個目錄`;

      const grid = document.getElementById('otherGrid');
      if (others.length === 0) {
        grid.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">無其他未配置的音檔目錄。</div>';
        return;
      }

      grid.innerHTML = others.map(o => `
        <div class="other-card">
          <div class="other-name">📁 ${escapeHtml(o.dir_name)}</div>
          <div class="other-meta">包含 ${o.count} 個音檔</div>
          ${o.sample_episodes && o.sample_episodes.length ? `
            <div class="other-sample">範例：${escapeHtml(o.sample_episodes.join('、'))}</div>
          ` : ''}
        </div>
      `).join('');
    }

    function copySecretLink(url) {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => showToast('✓ 已複製私密網址至剪貼簿！'));
      } else {
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);
        showToast('✓ 已複製私密網址至剪貼簿！');
      }
    }

    function showToast(msg) {
      const toast = document.getElementById('toast');
      toast.textContent = msg;
      toast.style.display = 'block';
      setTimeout(() => {
        toast.style.display = 'none';
      }, 2500);
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    init();
  </script>
</body>
</html>
"""

    index_html_path = os.path.join(P_ROOT_DIR, "index.html")
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(html_template)
    print(f"   [OK] Generated private directory index -> {index_html_path} ({len(html_template):,} bytes)")

def main():
    print("=== Scanning Private / Unlisted Caves ===")
    entries = parse_private_caves()
    if not entries:
        print("[INFO] No private series configured in private_caves.txt.")
        return

    summaries = []
    configured_dirs = set()
    for entry in entries:
        if entry.get("dir"):
            configured_dirs.add(os.path.abspath(entry["dir"]))
        summary = build_private_series(entry)
        if summary:
            summaries.append(summary)

    other_series = scan_workspace_other_series(configured_dirs)
    generate_private_index(summaries, other_series)

    print("\n[SUCCESS] Private series processing complete!")

if __name__ == "__main__":
    main()
