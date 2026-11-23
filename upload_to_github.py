"""Synchronize public podcast audio (`caveXX_epYY.m4a`) and video (`caveXX_epYY.mp4`)
files to Cloudflare R2, and audio assets to GitHub Release `v1.0.0`.

100% softcoded via `build_podcast` (`channel.txt` + `caves.txt`).
Streams directly from master files without duplicating disk storage.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

DIST_DIR = Path(__file__).resolve().parent
if str(DIST_DIR) not in sys.path:
    sys.path.insert(0, str(DIST_DIR))

import build_podcast  # noqa: E402

R2_BUCKET = "rabbit-hole"
WRANGLER_CANDIDATES = [
    Path(r"C:\Users\tzejen\AppData\Local\npm-cache\_npx\32026684e21afda6\node_modules\.bin\wrangler.cmd"),
    Path(r"C:\cowork\life\node_modules\.bin\wrangler.cmd"),
]


def resolve_wrangler_cmd() -> list[str]:
    for cand in WRANGLER_CANDIDATES:
        if cand.exists():
            return [str(cand)]
    w = shutil.which("wrangler")
    if w:
        return [w]
    npx = shutil.which("npx")
    if npx:
        return [npx, "--yes", "wrangler"]
    raise RuntimeError("Could not locate wrangler or npx in environment.")


def collect_release_items() -> list[tuple[str, str, int, str]]:
    """Return list of (target_name, local_path, file_size, content_type) across all caves."""
    items: list[tuple[str, str, int, str]] = []
    for s_info in build_podcast.SERIES_LIST:
        for media in build_podcast.discover_series_media(s_info):
            audio_path = media["audio_path"]
            items.append((
                media["audio_release_name"],
                audio_path,
                os.path.getsize(audio_path),
                "audio/mp4",
            ))
            video_path = media.get("video_path")
            video_name = media.get("video_release_name")
            if video_path and video_name:
                items.append((
                    video_name,
                    video_path,
                    os.path.getsize(video_path),
                    "video/mp4",
                ))
    return items


def r2_object_matches(audio_base_url: str, target_name: str, expected_size: int) -> bool:
    url = f"{audio_base_url.rstrip('/')}/{target_name}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            cl = int(resp.headers.get("Content-Length", -1))
            return resp.status == 200 and cl == expected_size
    except Exception:
        return False


def upload_one_r2(
    wrangler_cmd: list[str],
    target_name: str,
    fpath: str,
    file_size: int,
    content_type: str,
) -> str:
    size_mb = file_size / (1024 * 1024)
    cmd = wrangler_cmd + [
        "r2",
        "object",
        "put",
        f"{R2_BUCKET}/{target_name}",
        "--file",
        fpath,
        "--content-type",
        content_type,
        "--remote",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"R2 upload failed for {target_name}: {res.stderr or res.stdout}")
    return f"[R2 OK] {target_name} ({size_mb:.2f} MB, {content_type})"


def sync_r2(items: list[tuple[str, str, int, str]], audio_base_url: str, workers: int = 4) -> None:
    n_audio = sum(1 for x in items if x[3] == "audio/mp4")
    n_video = sum(1 for x in items if x[3] == "video/mp4")
    print(f"\n=== Syncing {len(items)} media assets ({n_audio} audio, {n_video} video) to Cloudflare R2 bucket '{R2_BUCKET}' ===")
    wrangler_cmd = resolve_wrangler_cmd()
    to_upload: list[tuple[str, str, int, str]] = []

    def _check(item: tuple[str, str, int, str]) -> tuple[tuple[str, str, int, str], bool]:
        tname, _, fsize, _ = item
        return item, r2_object_matches(audio_base_url, tname, fsize)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for item, ok in pool.map(_check, items):
            tname, fpath, fsize, ctype = item
            size_mb = fsize / (1024 * 1024)
            if ok:
                print(f"[R2 SKIP] {tname} ({size_mb:.2f} MB, {ctype}) already live with identical Content-Length.")
            else:
                to_upload.append(item)

    if not to_upload:
        print("[R2] All audio and video assets are already up to date.")
        return

    print(f"[R2] Uploading {len(to_upload)} missing/updated files with {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(upload_one_r2, wrangler_cmd, tname, fpath, fsize, ctype): tname
            for tname, fpath, fsize, ctype in to_upload
        }
        for fut in as_completed(futs):
            print(" ", fut.result())


def get_github_token() -> str | None:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        text=True,
        capture_output=True,
    )
    creds = dict(line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line)
    return creds.get("password")


def fetch_all_release_assets(owner: str, repo: str, release_id: int, headers: dict[str, str]) -> dict[str, dict]:
    assets: dict[str, dict] = {}
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/{release_id}/assets?per_page=100&page={page}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            batch = json.loads(resp.read().decode())
        if not batch:
            break
        for a in batch:
            assets[a["name"]] = a
        if len(batch) < 100:
            break
        page += 1
    return assets


def sync_github_release(items: list[tuple[str, str, int]]) -> None:
    token = get_github_token()
    if not token:
        print("[ERROR] Could not retrieve GitHub token from git credential manager.")
        sys.exit(1)

    owner = build_podcast.CHANNEL_META.get("github_user", "tzejen")
    repo = build_podcast.CHANNEL_META.get("github_repo", "rabbit-hole")
    headers = {
        "Authorization": f"token {token}",
        "User-Agent": "Antigravity-Release-Uploader",
        "Accept": "application/vnd.github.v3+json",
    }

    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        releases = json.loads(resp.read().decode())

    target_rel = next((r for r in releases if r.get("tag_name") == "v1.0.0"), None)
    if not target_rel:
        print("[ERROR] Release v1.0.0 not found on GitHub!")
        sys.exit(1)

    release_id = target_rel["id"]
    upload_url_template = target_rel["upload_url"].split("{")[0]
    existing_assets = fetch_all_release_assets(owner, repo, release_id, headers)
    print(f"\n=== Syncing {len(items)} audio assets to GitHub Release v1.0.0 (ID: {release_id}, existing: {len(existing_assets)}) ===")

    for name, a in list(existing_assets.items()):
        if name.endswith("_.m4a") or not name.startswith("cave"):
            print(f"  [GH CLEANUP] Deleting invalid asset: {name} (ID: {a['id']})...")
            del_req = urllib.request.Request(
                f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{a['id']}",
                headers=headers,
                method="DELETE",
            )
            with urllib.request.urlopen(del_req):
                del existing_assets[name]
                print(f"  [GH OK] Deleted {name}")

    for target_name, fpath, file_size in items:
        size_mb = file_size / (1024 * 1024)
        if target_name in existing_assets:
            if existing_assets[target_name]["size"] == file_size:
                print(f"[GH SKIP] {target_name} ({size_mb:.2f} MB) already uploaded with identical size.")
                continue
            old_id = existing_assets[target_name]["id"]
            print(f"[GH UPDATE] Deleting stale {target_name} (ID: {old_id})...")
            del_req = urllib.request.Request(
                f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{old_id}",
                headers=headers,
                method="DELETE",
            )
            with urllib.request.urlopen(del_req):
                pass

        print(f"[GH UPLOAD] {target_name} ({size_mb:.2f} MB) <- {os.path.basename(fpath)}")
        upload_url = f"{upload_url_template}?name={target_name}"
        upload_headers = {
            "Authorization": f"token {token}",
            "User-Agent": "Antigravity-Release-Uploader",
            "Content-Type": "audio/mp4",
            "Content-Length": str(file_size),
        }
        with open(fpath, "rb") as f:
            data = f.read()
        up_req = urllib.request.Request(upload_url, data=data, headers=upload_headers, method="POST")
        with urllib.request.urlopen(up_req) as up_resp:
            res_data = json.loads(up_resp.read().decode())
            print(f"  [GH OK] {target_name} (Asset ID: {res_data['id']})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r2-only", action="store_true")
    parser.add_argument("--github-only", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    items = collect_release_items()
    audio_items = [(tname, fpath, fsize) for tname, fpath, fsize, ctype in items if ctype == "audio/mp4"]
    video_items = [(tname, fpath, fsize) for tname, fpath, fsize, ctype in items if ctype == "video/mp4"]
    print(f"Discovered {len(audio_items)} audio + {len(video_items)} video release assets across {len(build_podcast.SERIES_LIST)} series.")

    audio_base_url = build_podcast.CHANNEL_META.get("audio_base_url")
    if not args.github_only:
        if audio_base_url:
            sync_r2(items, audio_base_url, workers=args.workers)
        else:
            print("[WARN] No audio_base_url configured in channel.txt; skipping R2 sync.")

    if not args.r2_only:
        sync_github_release(audio_items)

    print("\n[COMPLETE] Media release synchronization finished!")


if __name__ == "__main__":
    main()
