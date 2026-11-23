"""
Build script for 《兔子洞筆記》 (Notes from the Rabbit Hole) Podcast Distribution.
100% Softcoded: Reads channel configuration from channel.txt and series from caves.txt.
Generates:
1. feed.xml (Master Podcast RSS for Apple Podcasts / Pocket Casts)
2. Standalone Series RSS feeds
3. episodes.json (Data store for the web player)
4. Synchronizes assets and builds index.html
"""

import os
import sys
import json
import shutil
import subprocess
import glob
import re
from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape as xml_escape
from mutagen.mp4 import MP4

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE_DIR = r"G:\My Drive\NotebookLM"
DIST_DIR = os.path.join(BASE_DIR, "podcast_distribution")
ASSETS_DIR = os.path.join(DIST_DIR, "assets")
SUBS_DIR = os.path.join(ASSETS_DIR, "subs")
CHANNEL_TXT_PATH = os.path.join(DIST_DIR, "channel.txt")
CAVES_TXT_PATH = os.path.join(DIST_DIR, "caves.txt")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(SUBS_DIR, exist_ok=True)

# 1. Parse channel.txt
def load_channel_meta():
    meta = {
        "title": "兔子洞筆記",
        "subtitle": "其他洞窟挖掘中",
        "author": "",
        "email": "",
        "category": "History",
        "subcategory": "Asian History",
        "language": "zh-tw",
        "github_user": "tzejen",
        "github_repo": "rabbit-hole",
        "description": "",
        "cover_filename": "cover_channel_1400.jpg"
    }
    if not os.path.exists(CHANNEL_TXT_PATH):
        return meta

    desc_lines = []
    reading_desc = False

    with open(CHANNEL_TXT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\r\n")
            striped = raw.strip()
            if not striped or striped.startswith("#"):
                continue

            if striped.startswith("Description:"):
                reading_desc = True
                continue

            if reading_desc:
                desc_lines.append(raw)
            else:
                if ":" in striped:
                    k, v = striped.split(":", 1)
                    k_lower = k.strip().lower()
                    v_clean = v.strip()
                    if k_lower == "title":
                        meta["title"] = v_clean
                    elif k_lower == "subtitle":
                        meta["subtitle"] = v_clean
                    elif k_lower == "author":
                        meta["author"] = v_clean
                    elif k_lower == "email":
                        meta["email"] = v_clean
                    elif k_lower == "language":
                        meta["language"] = v_clean
                    elif k_lower == "category":
                        meta["category"] = v_clean
                    elif k_lower == "subcategory":
                        meta["subcategory"] = v_clean
                    elif k_lower == "github_user":
                        meta["github_user"] = v_clean
                    elif k_lower == "github_repo":
                        meta["github_repo"] = v_clean
                    elif k_lower == "audio_base_url":
                        meta["audio_base_url"] = v_clean.rstrip("/")

    meta["description"] = "\n".join(desc_lines).strip() if desc_lines else ""
    return meta

CHANNEL_META = load_channel_meta()

# 2. Parse caves.txt to discover series
def load_caves_list():
    caves = []
    if not os.path.exists(CAVES_TXT_PATH):
        return caves

    idx = 1
    with open(CAVES_TXT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            parts = [p.strip() for p in line_str.split("|")]
            if len(parts) >= 2:
                cave_number = parts[0]
                cave_title = parts[1]
                custom_folder = parts[2] if len(parts) >= 4 else None
                status = parts[3] if len(parts) >= 4 else (parts[2] if len(parts) == 3 else "已上線")
                publish_mode = parts[4].strip().lower() if len(parts) >= 5 else ""

                # Auto-detect folder when not specified in caves.txt
                if custom_folder and os.path.isdir(os.path.join(BASE_DIR, custom_folder)):
                    series_dir = os.path.join(BASE_DIR, custom_folder)
                elif "第一窟" in cave_number or "漢字" in cave_title or "詞彙" in cave_title:
                    series_dir = os.path.join(BASE_DIR, "白話文運動與日文詞彙_ModernChinese")
                else:
                    series_dir = None
                    for d in os.listdir(BASE_DIR):
                        full = os.path.join(BASE_DIR, d)
                        if os.path.isdir(full) and d.startswith(cave_title[:2]):
                            series_dir = full
                            break

                if series_dir and os.path.isdir(series_dir):
                    series_desc = ""
                    desc_file = os.path.join(series_dir, "desc.txt")
                    if os.path.exists(desc_file):
                        try:
                            dlines = open(desc_file, "r", encoding="utf-8").read().splitlines()
                            for didx, dl in enumerate(dlines):
                                if "【系列簡介】" in dl:
                                    collected = []
                                    for follow in dlines[didx+1:]:
                                        if follow.startswith("【各集目錄】") or follow.startswith("【隨身") or follow.startswith("■") or follow.startswith("第 "):
                                            break
                                        if follow.strip():
                                            collected.append(follow.strip())
                                    series_desc = "\n".join(collected).strip()
                                    break
                        except Exception:
                            pass

                    caves.append({
                        "id": f"cave{idx:02d}",
                        "cave_number": cave_number,
                        "title": cave_title,
                        "description": series_desc,
                        "dir": series_dir,
                        "cover_src": os.path.join(series_dir, "cover.jpg"),
                        "cover_dst_name": f"cover_cave{idx:02d}.jpg",
                        "season_num": idx,
                        "status": status,
                        "publish_mode": publish_mode,
                    })
                    idx += 1
    return caves

SERIES_LIST = load_caves_list()


def discover_series_media(s_info):
    """Discover per-episode audio, optional video, and subtitle assets for a series."""
    s_dir = s_info["dir"]
    series_id = s_info["id"]
    publish_mode = s_info.get("publish_mode", "").strip().lower()

    # 1. Scan <s_dir>/Video/*.mp4
    video_by_ep = {}
    video_dir = os.path.join(s_dir, "Video")
    if os.path.isdir(video_dir):
        skip_tokens = ("candidate", "microcut", "測試", "test", "_tmp")
        for fpath in sorted(glob.glob(os.path.join(video_dir, "*.mp4"))):
            fname = os.path.basename(fpath)
            fname_low = fname.lower()
            if any(tok in fname_low for tok in skip_tokens):
                continue
            m = re.match(r"^ep(\d+)(?:_v(\d+)\.(\d+))?", fname, re.IGNORECASE)
            if not m:
                continue
            ep_num = int(m.group(1))
            ver = (int(m.group(2)), int(m.group(3))) if m.group(2) is not None else (0, 0)
            mtime = os.path.getmtime(fpath)
            cand = (ver, mtime, fpath)
            prev = video_by_ep.get(ep_num)
            if prev is None or (ver, mtime) > (prev[0], prev[1]):
                video_by_ep[ep_num] = cand

    # 2. Scan <s_dir>/ for unversioned .m4a first (preserves cave01-cave03 behavior)
    unversioned_m4as = sorted([
        f for f in glob.glob(os.path.join(s_dir, "[0-9][0-9]_*.m4a"))
        if "Candidate" not in os.path.basename(f)
        and "MicroCut" not in os.path.basename(f)
        and "_v" not in os.path.basename(f)
    ])

    audio_by_ep = {}
    if unversioned_m4as:
        for idx, fpath in enumerate(unversioned_m4as, 1):
            audio_by_ep[idx] = fpath
    else:
        grouped_m4as = {}
        for fpath in sorted(glob.glob(os.path.join(s_dir, "[0-9][0-9]_v*.m4a"))):
            fname = os.path.basename(fpath)
            if "Candidate" in fname or "MicroCut" in fname:
                continue
            m = re.match(r"^(\d{2})_v(\d+)\.(\d+)_.*\.m4a$", fname)
            if not m:
                continue
            ep_num = int(m.group(1))
            ver = (int(m.group(2)), int(m.group(3)))
            mtime = os.path.getmtime(fpath)
            grouped_m4as.setdefault(ep_num, []).append((ver, mtime, fpath))

        for ep_num, cands in grouped_m4as.items():
            target_vid_ver = video_by_ep[ep_num][0] if ep_num in video_by_ep else None
            chosen = None
            if target_vid_ver is not None:
                matching = [c for c in cands if c[0] == target_vid_ver]
                if matching:
                    chosen = max(matching, key=lambda c: (c[0], c[1]))
            if chosen is None:
                chosen = max(cands, key=lambda c: (c[0], c[1]))
            audio_by_ep[ep_num] = chosen[2]

    # 3. Combine audio + video + subtitle and apply publish_mode filter
    items = []
    for ep_num in sorted(audio_by_ep.keys()):
        audio_path = audio_by_ep[ep_num]
        vid_entry = video_by_ep.get(ep_num)
        video_path = vid_entry[2] if vid_entry else None

        if publish_mode == "video_only" and not video_path:
            continue
        if publish_mode.startswith("max_ep="):
            try:
                max_ep = int(publish_mode.split("=", 1)[1].strip())
                if ep_num > max_ep:
                    continue
            except ValueError:
                pass

        srt_path = None
        if video_path:
            cand_srt = os.path.splitext(video_path)[0] + ".srt"
            if os.path.isfile(cand_srt):
                srt_path = cand_srt

        items.append({
            "ep_num": ep_num,
            "audio_path": audio_path,
            "audio_release_name": f"{series_id}_ep{ep_num:02d}.m4a",
            "video_path": video_path,
            "video_release_name": f"{series_id}_ep{ep_num:02d}.mp4" if video_path else None,
            "srt_path": srt_path,
            "vtt_filename": f"{series_id}_ep{ep_num:02d}.vtt" if srt_path else None,
        })

    return items


def convert_srt_to_vtt(srt_path, vtt_path):
    """Convert a UTF-8 SRT subtitle file to WebVTT (.vtt)."""
    try:
        with open(srt_path, "r", encoding="utf-8-sig") as f:
            raw = f.read()
    except Exception as e:
        print(f"[WARN] Failed reading SRT {srt_path}: {e}")
        return False

    normalized = raw.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return False

    ts_re = re.compile(r"^(\d{2}:\d{2}:\d{2}),(\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}),(\d{3}.*)$")
    cue_blocks = []
    for block in re.split(r"\n{2,}", normalized):
        lines = block.split("\n")
        if not lines:
            continue
        if lines[0].strip().isdigit():
            lines = lines[1:]
        if not lines:
            continue
        converted_lines = []
        for idx, line in enumerate(lines):
            if idx == 0:
                m = ts_re.match(line.strip())
                if m:
                    line = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
            converted_lines.append(line)
        cue_blocks.append("\n".join(converted_lines))

    vtt_text = "WEBVTT\n\n" + "\n\n".join(cue_blocks) + "\n"
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_text)
    return True


def get_audio_chapters(file_path):
    """Extract chapters with ffprobe."""
    try:
        cmd = [
            "ffprobe", "-i", file_path,
            "-print_format", "json",
            "-show_chapters",
            "-loglevel", "error"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0:
            data = json.loads(res.stdout)
            ch_list = []
            for ch in data.get("chapters", []):
                start = float(ch["start_time"])
                end = float(ch["end_time"])
                title = ch.get("tags", {}).get("title", f"Chapter {len(ch_list)+1}")
                ch_list.append({
                    "title": title,
                    "start": round(start, 2),
                    "end": round(end, 2),
                    "start_fmt": f"{int(start//60):02d}:{int(start%60):02d}",
                    "end_fmt": f"{int(end//60):02d}:{int(end%60):02d}"
                })
            return ch_list
    except Exception as e:
        print(f"[WARN] Failed extracting chapters for {file_path}: {e}")
    return []


def format_duration(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def scan_and_collect_episodes():
    all_episodes = []
    active_vtt_files = set()

    # 1. Copy channel cover
    src_ch_cover = os.path.join(DIST_DIR, CHANNEL_META["cover_filename"])
    if os.path.exists(src_ch_cover):
        shutil.copy2(src_ch_cover, os.path.join(ASSETS_DIR, CHANNEL_META["cover_filename"]))

    user = CHANNEL_META.get("github_user", "tzejen")
    repo = CHANNEL_META.get("github_repo", "rabbit-hole")
    audio_base_url = CHANNEL_META.get("audio_base_url") or f"https://github.com/{user}/{repo}/releases/download/v1.0.0"

    for s_info in SERIES_LIST:
        print(f"Scanning series: {s_info['cave_number']} - {s_info['title']}")

        # Copy series cover
        if os.path.exists(s_info["cover_src"]):
            dst_cover = os.path.join(ASSETS_DIR, s_info["cover_dst_name"])
            shutil.copy2(s_info["cover_src"], dst_cover)
            print(f"  [OK] Copied series cover -> {s_info['cover_dst_name']}")

        media_items = discover_series_media(s_info)

        for item in media_items:
            ep_num = item["ep_num"]
            fpath = item["audio_path"]
            fname = os.path.basename(fpath)
            mp4 = MP4(fpath)

            title_tag = mp4.tags.get("©nam", [fname[:-4]])[0]
            clean_title = re.sub(r"^(?:Ep\d+|H\d+E\d+|\d+)[\s\-_:：]*", "", title_tag).strip()
            formatted_title = f"H{s_info['season_num']:02d}E{ep_num:02d} {clean_title}"

            artist_tag = mp4.tags.get("©ART", [CHANNEL_META["author"]])[0]
            desc_tag = mp4.tags.get("desc", mp4.tags.get("©cmt", [""]))[0]
            notes_tag = mp4.tags.get("©lyr", [desc_tag])[0]

            duration_sec = round(mp4.info.length, 2)
            file_size = os.path.getsize(fpath)
            chapters = get_audio_chapters(fpath)

            if s_info["id"] == "cave01":
                pub_date = datetime(2026, 10, 24, 12, ep_num, 0, tzinfo=timezone.utc)
            elif s_info["id"] == "cave02":
                pub_date = datetime(2026, 10, 29, 12, ep_num, 0, tzinfo=timezone.utc)
            elif s_info["id"] == "cave03":
                pub_date = datetime(2026, 10, 28, 12, ep_num, 0, tzinfo=timezone.utc)
            else:
                pub_date = datetime(2026, 11, 22, 12, 0, 0, tzinfo=timezone.utc) + timedelta(
                    days=s_info["season_num"] - 4, minutes=ep_num
                )

            # Standard ASCII release filename for CDN / R2 (streamed directly without local duplicates)
            release_fname = item["audio_release_name"]
            audio_url = f"{audio_base_url}/{release_fname}"

            has_video = bool(item["video_path"])
            video_release_fname = item["video_release_name"] or ""
            video_url = f"{audio_base_url}/{video_release_fname}" if has_video else ""
            video_file_size = os.path.getsize(item["video_path"]) if has_video else 0

            vtt_generated = False
            if has_video and item["srt_path"] and item["vtt_filename"]:
                vtt_dst = os.path.join(SUBS_DIR, item["vtt_filename"])
                vtt_generated = convert_srt_to_vtt(item["srt_path"], vtt_dst)
                if vtt_generated:
                    active_vtt_files.add(item["vtt_filename"])

            web_episode_url = f"https://{user}.github.io/{repo}/#{s_info['id']}/ep{ep_num:02d}"

            ep_data = {
                "series_id": s_info["id"],
                "cave_number": s_info["cave_number"],
                "series_title": s_info["title"],
                "season": s_info["season_num"],
                "episode": ep_num,
                "title": formatted_title,
                "filename": fname,
                "release_filename": release_fname,
                "audio_url": audio_url,
                "local_path": fpath,
                "file_size": file_size,
                "duration_sec": duration_sec,
                "duration_fmt": format_duration(duration_sec),
                "artist": artist_tag,
                "summary": desc_tag,
                "full_notes": notes_tag,
                "chapters": chapters,
                "cover_image": f"assets/{s_info['cover_dst_name']}",
                "pub_date_rfc822": pub_date.strftime("%a, %d %b %Y %H:%M:%S +0000"),
                "pub_date_iso": pub_date.isoformat(),
                "has_video": has_video,
                "video_url": video_url,
                "video_release_filename": video_release_fname,
                "video_file_size": video_file_size,
                "subtitle_url": f"assets/subs/{item['vtt_filename']}" if vtt_generated else "",
                "web_episode_url": web_episode_url,
            }
            all_episodes.append(ep_data)
            vid_note = f" + VIDEO ({video_file_size / (1024*1024):.1f} MB)" if has_video else ""
            sub_note = " + VTT" if vtt_generated else ""
            print(f"  [OK] Ep{ep_num:02d} -> {release_fname}: {title_tag} ({ep_data['duration_fmt']}, {len(chapters)} chs{vid_note}{sub_note})")

    if os.path.isdir(SUBS_DIR):
        for existing_sub in os.listdir(SUBS_DIR):
            if existing_sub not in active_vtt_files:
                try:
                    os.remove(os.path.join(SUBS_DIR, existing_sub))
                except Exception:
                    pass

    return all_episodes


def generate_rss_feed(episodes, output_path, is_master=True, target_series_id=None):
    """Generate iTunes Podcast RSS 2.0 XML."""
    if not is_master and target_series_id:
        filtered_eps = [e for e in episodes if e["series_id"] == target_series_id]
        if not filtered_eps:
            return
        series_meta = next((s for s in SERIES_LIST if s["id"] == target_series_id), {})
        is_series_complete = (series_meta.get("status", "") == "已上線")
        feed_title = f"{CHANNEL_META['title']}・{filtered_eps[0]['cave_number']}：{filtered_eps[0]['series_title']}"
        feed_desc = f"{CHANNEL_META['title']}系列專題：{filtered_eps[0]['series_title']}"
        feed_cover = filtered_eps[0]["cover_image"]
    else:
        filtered_eps = episodes
        is_series_complete = False
        feed_title = CHANNEL_META["title"]
        feed_desc = CHANNEL_META["description"]
        feed_cover = f"assets/{CHANNEL_META['cover_filename']}"

    # Softcoded Base URL from channel.txt
    user = CHANNEL_META.get("github_user", "username")
    repo = CHANNEL_META.get("github_repo", "rabbit-hole")
    base_url = f"https://{user}.github.io/{repo}"
    audio_base_url = CHANNEL_META.get("audio_base_url") or f"https://github.com/{user}/{repo}/releases/download/v1.0.0"

    author = CHANNEL_META.get("author", "").strip()
    subtitle = CHANNEL_META.get("subtitle", "").strip()
    email = CHANNEL_META.get("email", "").strip()
    feed_desc_clean = xml_escape(feed_desc) if feed_desc else ""

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0"',
        '     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"',
        '     xmlns:content="http://purl.org/rss/1.0/modules/content/"',
        '     xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        f'    <title>{xml_escape(feed_title)}</title>',
    ]

    if subtitle:
        xml_lines.append(f'    <itunes:subtitle>{xml_escape(subtitle)}</itunes:subtitle>')

    xml_lines.extend([
        f'    <language>{CHANNEL_META["language"]}</language>',
        f'    <itunes:summary>{feed_desc_clean}</itunes:summary>',
        f'    <description>{feed_desc_clean}</description>',
        '    <itunes:type>episodic</itunes:type>',
    ])
    if is_series_complete:
        xml_lines.append('    <itunes:complete>yes</itunes:complete>')
    xml_lines.extend([
        '    <itunes:explicit>false</itunes:explicit>',
        f'    <itunes:image href="{base_url}/{feed_cover}"/>',
    ])

    if author:
        xml_lines.extend([
            f'    <copyright>© {datetime.now().year} {xml_escape(author)}</copyright>',
            f'    <itunes:author>{xml_escape(author)}</itunes:author>',
            '    <itunes:owner>',
            f'      <itunes:name>{xml_escape(author)}</itunes:name>',
            f'      <itunes:email>{email}</itunes:email>',
            '    </itunes:owner>',
        ])

    xml_lines.append(f'    <itunes:category text="{CHANNEL_META["category"]}">')
    if CHANNEL_META.get("subcategory"):
        xml_lines.append(f'      <itunes:category text="{CHANNEL_META["subcategory"]}"/>')
    xml_lines.append('    </itunes:category>')

    for ep in filtered_eps:
        audio_url = ep.get("audio_url", f"{audio_base_url}/{ep.get('release_filename', ep['filename'])}")

        summary_text = ep["summary"]
        content_prefix = ""
        if ep.get("has_video") and ep.get("web_episode_url"):
            video_link = ep["web_episode_url"]
            summary_text = (
                f"🎬 觀看本集圖文影片：{video_link}\n\n{ep['summary']}"
                if ep["summary"]
                else f"🎬 觀看本集圖文影片：{video_link}"
            )
            content_prefix = (
                f'<p>🎬 <b>觀看本集圖文影片</b>：'
                f'<a href="{xml_escape(video_link)}">{xml_escape(video_link)}</a></p>'
            )

        ch_html = ""
        if ep["chapters"]:
            ch_rows = "".join([f"<li><b>{ch['start_fmt']}</b> {xml_escape(ch['title'])}</li>" for ch in ep["chapters"]])
            ch_html = f"<h4>【本集章節時間軸】</h4><ul>{ch_rows}</ul>"

        content_encoded = f"{content_prefix}<p>{xml_escape(ep['summary'])}</p>{ch_html}"

        xml_lines.extend([
            '    <item>',
            f'      <title>{xml_escape(ep["title"])}</title>',
            f'      <itunes:title>{xml_escape(ep["title"])}</itunes:title>',
            f'      <itunes:season>{ep["season"]}</itunes:season>',
            f'      <itunes:episode>{ep["episode"]}</itunes:episode>',
            '      <itunes:episodeType>full</itunes:episodeType>',
            f'      <pubDate>{ep["pub_date_rfc822"]}</pubDate>',
            f'      <guid isPermaLink="false">{ep["series_id"]}_ep{ep["episode"]:02d}</guid>',
            f'      <enclosure url="{audio_url}" length="{ep["file_size"]}" type="audio/mp4"/>',
            f'      <itunes:duration>{ep["duration_sec"]}</itunes:duration>',
            f'      <itunes:summary>{xml_escape(summary_text)}</itunes:summary>',
            f'      <description>{xml_escape(summary_text)}</description>',
            f'      <content:encoded><![CDATA[{content_encoded}]]></content:encoded>',
            f'      <itunes:image href="{base_url}/{ep["cover_image"]}"/>',
            '    </item>'
        ])

    xml_lines.extend([
        '  </channel>',
        '</rss>'
    ])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))
    print(f"[OK] Generated RSS Feed -> {os.path.basename(output_path)} ({len(filtered_eps)} episodes)")


def main():
    print("=== Building 《兔子洞筆記》 Podcast Distribution (100% Softcoded) ===")
    episodes = scan_and_collect_episodes()

    # Save episodes.json for web player
    json_path = os.path.join(DIST_DIR, "episodes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "channel": CHANNEL_META,
            "series": SERIES_LIST,
            "episodes": episodes
        }, f, ensure_ascii=False, indent=2)
    print(f"[OK] Saved episodes.json ({len(episodes)} episodes, {os.path.getsize(json_path):,} bytes)")

    # 1. Master feed (all caves)
    master_feed = os.path.join(DIST_DIR, "feed.xml")
    generate_rss_feed(episodes, master_feed, is_master=True)

    # 2. Standalone series feed for each active series
    for s in SERIES_LIST:
        s_feed = os.path.join(DIST_DIR, f"feed_{s['id']}.xml")
        generate_rss_feed(episodes, s_feed, is_master=False, target_series_id=s["id"])

    # 3. Build Web Player (index.html)
    import build_html
    build_html.build_public_html()

    # 4. Build Unlisted Private Pages
    try:
        import build_private
        build_private.main()
    except Exception as e:
        print(f"[WARN] build_private failed: {e}")

    print("\n[SUCCESS] All distribution metadata, RSS feeds, and Web Player generated cleanly!")

if __name__ == "__main__":
    main()
