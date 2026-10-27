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
from datetime import datetime, timezone
from xml.sax.saxutils import escape as xml_escape
from mutagen.mp4 import MP4

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE_DIR = r"G:\My Drive\NotebookLM"
DIST_DIR = os.path.join(BASE_DIR, "podcast_distribution")
ASSETS_DIR = os.path.join(DIST_DIR, "assets")
CHANNEL_TXT_PATH = os.path.join(DIST_DIR, "channel.txt")
CAVES_TXT_PATH = os.path.join(DIST_DIR, "caves.txt")
os.makedirs(ASSETS_DIR, exist_ok=True)

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
                    caves.append({
                        "id": f"cave{idx:02d}",
                        "cave_number": cave_number,
                        "title": cave_title,
                        "dir": series_dir,
                        "cover_src": os.path.join(series_dir, "cover.jpg"),
                        "cover_dst_name": f"cover_cave{idx:02d}.jpg",
                        "season_num": idx,
                        "status": status,
                    })
                    idx += 1
    return caves

SERIES_LIST = load_caves_list()


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

    # 1. Copy channel cover
    src_ch_cover = os.path.join(DIST_DIR, CHANNEL_META["cover_filename"])
    if os.path.exists(src_ch_cover):
        shutil.copy2(src_ch_cover, os.path.join(ASSETS_DIR, CHANNEL_META["cover_filename"]))

    for s_info in SERIES_LIST:
        print(f"Scanning series: {s_info['cave_number']} - {s_info['title']}")

        # Copy series cover
        if os.path.exists(s_info["cover_src"]):
            dst_cover = os.path.join(ASSETS_DIR, s_info["cover_dst_name"])
            shutil.copy2(s_info["cover_src"], dst_cover)
            print(f"  [OK] Copied series cover -> {s_info['cover_dst_name']}")

        s_dir = s_info["dir"]
        m4a_files = sorted(glob.glob(os.path.join(s_dir, "[0-9][0-9]_*.m4a")))

        user = CHANNEL_META.get("github_user", "tzejen")
        repo = CHANNEL_META.get("github_repo", "rabbit-hole")

        for idx, fpath in enumerate(m4a_files, 1):
            fname = os.path.basename(fpath)
            mp4 = MP4(fpath)

            title_tag = mp4.tags.get("©nam", [fname[:-4]])[0]
            clean_title = re.sub(r"^(?:Ep\d+|H\d+E\d+|\d+)[\s\-_:：]*", "", title_tag).strip()
            formatted_title = f"H{s_info['season_num']:02d}E{idx:02d} {clean_title}"

            artist_tag = mp4.tags.get("©ART", [CHANNEL_META["author"]])[0]
            desc_tag = mp4.tags.get("desc", mp4.tags.get("©cmt", [""]))[0]
            notes_tag = mp4.tags.get("©lyr", [desc_tag])[0]

            duration_sec = round(mp4.info.length, 2)
            file_size = os.path.getsize(fpath)
            chapters = get_audio_chapters(fpath)

            pub_date = datetime(2026, 10, 24, 12, idx, 0, tzinfo=timezone.utc)

            # Standard ASCII release filename for GitHub Releases & CDN (streamed directly without local duplicates)
            release_fname = f"{s_info['id']}_ep{idx:02d}.m4a"
            audio_url = f"https://github.com/{user}/{repo}/releases/download/v1.0.0/{release_fname}"

            ep_data = {
                "series_id": s_info["id"],
                "cave_number": s_info["cave_number"],
                "series_title": s_info["title"],
                "season": s_info["season_num"],
                "episode": idx,
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
            }
            all_episodes.append(ep_data)
            print(f"  [OK] Ep{idx:02d} -> {release_fname}: {title_tag} ({ep_data['duration_fmt']}, {len(chapters)} chs)")

    return all_episodes


def generate_rss_feed(episodes, output_path, is_master=True, target_series_id=None):
    """Generate iTunes Podcast RSS 2.0 XML."""
    if not is_master and target_series_id:
        filtered_eps = [e for e in episodes if e["series_id"] == target_series_id]
        if not filtered_eps:
            return
        feed_title = f"{CHANNEL_META['title']}・{filtered_eps[0]['cave_number']}：{filtered_eps[0]['series_title']}"
        feed_desc = f"{CHANNEL_META['title']}系列專題：{filtered_eps[0]['series_title']}"
        feed_cover = filtered_eps[0]["cover_image"]
    else:
        filtered_eps = episodes
        feed_title = f"{CHANNEL_META['title']} (Notes from the Rabbit Hole)"
        feed_desc = CHANNEL_META["description"]
        feed_cover = f"assets/{CHANNEL_META['cover_filename']}"

    # Softcoded Base URL from channel.txt
    user = CHANNEL_META.get("github_user", "username")
    repo = CHANNEL_META.get("github_repo", "rabbit-hole")
    base_url = f"https://{user}.github.io/{repo}"
    audio_base_url = f"https://github.com/{user}/{repo}/releases/download/v1.0.0"

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
        '    <itunes:complete>yes</itunes:complete>',
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

        ch_html = ""
        if ep["chapters"]:
            ch_rows = "".join([f"<li><b>{ch['start_fmt']}</b> {xml_escape(ch['title'])}</li>" for ch in ep["chapters"]])
            ch_html = f"<h4>【本集章節時間軸】</h4><ul>{ch_rows}</ul>"

        notes_html = ep["full_notes"].replace("\n", "<br/>")
        content_encoded = f"<p>{xml_escape(ep['summary'])}</p>{ch_html}<hr/><h4>【考證手冊與大綱】</h4><p>{notes_html}</p>"

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
            f'      <itunes:summary>{xml_escape(ep["summary"])}</itunes:summary>',
            f'      <description>{xml_escape(ep["summary"])}</description>',
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

    print("\n[SUCCESS] All distribution metadata, RSS feeds, and Web Player generated cleanly!")

if __name__ == "__main__":
    main()
