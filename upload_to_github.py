"""Synchronize public podcast audio files (`caveXX_epYY.m4a`) to Cloudflare R2
and GitHub Release `v1.0.0`.

100% softcoded via `build_podcast` (`channel.txt` + `caves.txt`).
Streams directly from unversioned master `.m4a` files without duplicating disk storage.
"""

from __future__ import annotations

import argparse
import glob
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


def collect_release_items() -> list[tuple[str, str, int]]:
    """Return list of (target_name, local_path, file_size) across all caves in caves.txt."""
    items: list[tuple[str, str, int]] = []
    for s_info in build_podcast.SERIES_LIST:
        s_dir = s_info["dir"]
        m4a_files = sorted(
            [
                f
                for f in glob.glob(os.path.join(s_dir, "[0-9][0-9]_*.m4a"))
                if "Candidate" not in os.path.basename(f)
                and "MicroCut" not in os.path.basename(f)
                and "_v" not in os.path.basename(f)
            ]
        )
        for idx, fpath in enumerate(m4a_files, 1):
            target_name = f"{s_info['id']}_ep{idx:02d}.m4a"
            items.append((target_name, fpath, os.path.getsize(fpath)))
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


def upload_one_r2(wrangler_cmd: list[str], target_name: str, fpath: str, file_size: int) -> str:
    size_mb = file_size / (1024 * 1024)
    cmd = wrangler_cmd + [
        "r2",
        "object",
        "put",
        f"{R2_BUCKET}/{target_name}",
        "--file",
        fpath,
        "--content-type",
        "audio/mp4",
        "--remote",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        raise RuntimeError(f"R2 upload failed for {target_name}: {res.stderr or res.stdout}")
    return f"[R2 OK] {target_name} ({size_mb:.2f} MB)"


def sync_r2(items: list[tuple[str, str, int]], audio_base_url: str, workers: int = 4) -> None:
    print(f"\n=== Syncing {len(items)} audio assets to Cloudflare R2 bucket '{R2_BUCKET}' ===")
    wrangler_cmd = resolve_wrangler_cmd()
    to_upload: list[tuple[str, str, int]] = []

    def _check(item: tuple[str, str, int]) -> tuple[tuple[str, str, int], bool]:
        tname, _, fsize = item
        return item, r2_object_matches(audio_base_url, tname, fsize)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for item, ok in pool.map(_check, items):
            tname, fpath, fsize = item
            size_mb = fsize / (1024 * 1024)
            if ok:
                print(f"[R2 SKIP] {tname} ({size_mb:.2f} MB) already live with identical Content-Length.")
            else:
                to_upload.append(item)

    if not to_upload:
        print("[R2] All audio assets are already up to date.")
        return

    print(f"[R2] Uploading {len(to_upload)} missing/updated files with {workers} workers...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(upload_one_r2, wrangler_cmd, tname, fpath, fsize): tname
            for tname, fpath, fsize in to_upload
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
    print(f"Discovered {len(items)} active release audio assets across {len(build_podcast.SERIES_LIST)} series.")

    audio_base_url = build_podcast.CHANNEL_META.get("audio_base_url")
    if not args.github_only:
        if audio_base_url:
            sync_r2(items, audio_base_url, workers=args.workers)
        else:
            print("[WARN] No audio_base_url configured in channel.txt; skipping R2 sync.")

    if not args.r2_only:
        sync_github_release(items)

    print("\n[COMPLETE] Audio release synchronization finished!")


if __name__ == "__main__":
    main()
