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
    dst_cover_path = os.path.join(target_dir, cover_dst_name)
    if not os.path.exists(dst_cover_path) or os.path.getsize(dst_cover_path) != os.path.getsize(cover_src):
        try:
            shutil.copy2(cover_src, dst_cover_path)
        except Exception as e:
            print(f"   [WARN] Could not copy cover: {e}")

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
        notes_tag = ""  # Clean show notes: do not embed full outlines in private episodes

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
            "full_notes": "",
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
            if "逐字稿" in fname or "transcript" in fname.lower() or "大綱" in fname or "outline" in fname.lower() or "prompt" in fname.lower():
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
        "cave_number": status,
        "title": s_title,
        "description": series_desc,
        "dir": s_dir,
        "cover_src": cover_src,
        "cover_dst_name": cover_dst_name,
        "cover_url": cover_dst_name,
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
    from build_html import render_player_html

    data_bundle = {
        "series": [series_info],
        "episodes": episodes,
        "ref_docs_list": ref_docs,
        "series_docs_content": docs_content
    }
    html_content = render_player_html(data_bundle, is_private=True)
    out_html = os.path.join(output_dir, "index.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"   [OK] Generated private companion player (shared build_html template) -> {out_html} ({len(html_content):,} bytes)")

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

    ignore_file = os.path.join(DIST_DIR, "wip_ignore.txt")
    ignored_wips = set()
    if os.path.exists(ignore_file):
        with open(ignore_file, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    ignored_wips.add(s)

    other_series = []
    try:
        for entry in os.scandir(BASE_DIR):
            if not entry.is_dir():
                continue
            abs_p = os.path.abspath(entry.path)
            if abs_p in known_dirs:
                continue
            if entry.name in ignored_wips:
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

                latest_mtime = max(os.path.getmtime(f) for f in m4as)
                latest_date_str = datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d")

                other_series.append({
                    "dir_name": entry.name,
                    "count": len(m4as),
                    "date": latest_date_str,
                    "mtime": latest_mtime,
                    "sample_episodes": sample_titles
                })
    except Exception as e:
        print(f"[WARN] Error scanning other workspace series: {e}")

    # Sort by date in descending order (newest first)
    other_series.sort(key=lambda x: x["mtime"], reverse=True)
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
      position: relative;
      transition: border-color 0.15s ease;
    }
    .other-card:hover {
      border-color: rgba(255, 255, 255, 0.18);
    }
    .wip-header-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 6px;
    }
    .other-name {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-light);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      flex: 1;
    }
    .wip-header-right {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }
    .wip-date {
      font-size: 11px;
      color: #8b949e;
      background: rgba(255, 255, 255, 0.04);
      padding: 2px 6px;
      border-radius: 4px;
      font-family: monospace;
    }
    .btn-del-wip {
      background: transparent;
      border: 1px solid rgba(248, 81, 73, 0.35);
      color: #f85149;
      padding: 2px 7px;
      border-radius: 4px;
      font-size: 11px;
      cursor: pointer;
      line-height: 1.3;
      transition: all 0.15s ease;
    }
    .btn-del-wip:hover {
      background: rgba(248, 81, 73, 0.18);
      border-color: #f85149;
    }
    .btn-restore {
      background: transparent;
      border: 1px dashed var(--border);
      color: var(--text-muted);
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 11px;
      cursor: pointer;
      margin-left: 8px;
      transition: all 0.15s ease;
    }
    .btn-restore:hover {
      color: var(--text-light);
      border-color: var(--accent);
      background: rgba(255, 255, 255, 0.05);
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
      let dismissed = [];
      try {
        dismissed = JSON.parse(localStorage.getItem('rabbit_hole_dismissed_wip') || '[]');
      } catch (e) { dismissed = []; }

      const visibleOthers = others.filter(o => !dismissed.includes(o.dir_name));
      const countEl = document.getElementById('otherSeriesCount');
      if (dismissed.length > 0) {
        countEl.innerHTML = `${visibleOthers.length} 個目錄 <button class="btn-restore" onclick="restoreDismissedWip(event)" title="點擊復原已隱藏的 ${dismissed.length} 個專題">↩️ 復原 ${dismissed.length} 個</button>`;
      } else {
        countEl.textContent = `${visibleOthers.length} 個目錄`;
      }

      const grid = document.getElementById('otherGrid');
      if (visibleOthers.length === 0) {
        if (dismissed.length > 0) {
          grid.innerHTML = `<div style="color: var(--text-muted); font-size: 13px; padding: 12px 0;">已移除所有待發布專題。<button class="btn-restore" onclick="restoreDismissedWip(event)">↩️ 復原全部 (${dismissed.length} 個)</button></div>`;
        } else {
          grid.innerHTML = '<div style="color: var(--text-muted); font-size: 13px;">無其他未配置的音檔目錄。</div>';
        }
        return;
      }

      grid.innerHTML = visibleOthers.map(o => `
        <div class="other-card" id="wip_${escapeAttr(o.dir_name)}">
          <div class="wip-header-row">
            <div class="other-name" title="${escapeHtml(o.dir_name)}">📁 ${escapeHtml(o.dir_name)}</div>
            <div class="wip-header-right">
              <span class="wip-date">📅 ${escapeHtml(o.date || '')}</span>
              <button class="btn-del-wip" onclick="dismissWipCard('${escapeAttr(o.dir_name)}')" title="從此清單移除（不會刪除本機檔案）">✕ 移除</button>
            </div>
          </div>
          <div class="other-meta">包含 <strong>${o.count}</strong> 個音檔 · 更新時間：${escapeHtml(o.date || '')}</div>
          ${o.sample_episodes && o.sample_episodes.length ? `
            <div class="other-sample">範例：${escapeHtml(o.sample_episodes.join('、'))}</div>
          ` : ''}
        </div>
      `).join('');
    }

    function dismissWipCard(dirName) {
      if (!confirm(`確定要從此清單移除「${dirName}」嗎？\\n\\n（注意：這只會從網頁清單中移除，絕不會刪除電腦中的任何檔案）`)) {
        return;
      }
      let dismissed = [];
      try {
        dismissed = JSON.parse(localStorage.getItem('rabbit_hole_dismissed_wip') || '[]');
      } catch (e) { dismissed = []; }
      if (!dismissed.includes(dirName)) {
        dismissed.push(dirName);
        localStorage.setItem('rabbit_hole_dismissed_wip', JSON.stringify(dismissed));
      }
      renderOtherSeries();
      showToast(`✓ 已從清單移除「${dirName}」（本機檔案保留）`);
    }

    function restoreDismissedWip(event) {
      if (event) event.stopPropagation();
      localStorage.removeItem('rabbit_hole_dismissed_wip');
      renderOtherSeries();
      showToast('✓ 已復原所有已隱藏的待發布專題！');
    }

    function escapeAttr(str) {
      if (!str) return '';
      return String(str)
        .replace(/\\\\/g, '\\\\\\\\')
        .replace(/'/g, "\\\\'")
        .replace(/"/g, '&quot;');
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
