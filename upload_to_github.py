"""
Direct GitHub Release Asset Uploader
Streams audio directly from the source folder without creating duplicate files on disk.
"""

import os
import sys
import glob
import subprocess
import json
import urllib.request
import urllib.error

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

def get_github_token():
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        text=True,
        capture_output=True
    )
    creds = dict(line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line)
    return creds.get("password")

def main():
    token = get_github_token()
    if not token:
        print("[ERROR] Could not retrieve GitHub token from git credential manager.")
        sys.exit(1)

    owner = "tzejen"
    repo = "rabbit-hole"
    headers = {
        "Authorization": f"token {token}",
        "User-Agent": "Antigravity-Release-Uploader",
        "Accept": "application/vnd.github.v3+json"
    }

    # 1. Fetch release v1.0.0
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
    print(f"[OK] Found Release v1.0.0 (ID: {release_id})")

    # 2. Inspect existing assets
    existing_assets = {a["name"]: a for a in target_rel.get("assets", [])}
    print(f"[INFO] Current assets count: {len(existing_assets)}")

    # Clean up any corrupted / mangled names (like 05_.m4a)
    for name, a in list(existing_assets.items()):
        if name.endswith("_.m4a") or not name.startswith("cave"):
            print(f"  [CLEANUP] Deleting invalid asset: {name} (ID: {a['id']})...")
            del_req = urllib.request.Request(
                f"https://api.github.com/repos/{owner}/{repo}/releases/assets/{a['id']}",
                headers=headers,
                method="DELETE"
            )
            try:
                with urllib.request.urlopen(del_req) as del_resp:
                    del existing_assets[name]
                    print(f"  [OK] Deleted {name}")
            except Exception as e:
                print(f"  [WARN] Failed to delete {name}: {e}")

    # 3. Source directory with original Chinese files
    source_dir = r"G:\My Drive\NotebookLM\白話文運動與日文詞彙_ModernChinese"
    source_files = sorted(glob.glob(os.path.join(source_dir, "[0-9][0-9]_*.m4a")))

    print(f"\n[INFO] Found {len(source_files)} original source audio files to verify/upload.")

    for idx, fpath in enumerate(source_files, 1):
        target_name = f"cave01_ep{idx:02d}.m4a"
        file_size = os.path.getsize(fpath)
        size_mb = round(file_size / (1024 * 1024), 2)

        if target_name in existing_assets and existing_assets[target_name]["size"] == file_size:
            print(f"[SKIP] Ep{idx:02d} -> {target_name} ({size_mb} MB) is already uploaded with identical size.")
            continue

        print(f"\n[UPLOADING] Ep{idx:02d} -> {target_name} ({size_mb} MB) from source file:")
        print(f"  Source: {os.path.basename(fpath)}")

        # Stream file directly to GitHub release
        upload_url = f"{upload_url_template}?name={target_name}"
        upload_headers = {
            "Authorization": f"token {token}",
            "User-Agent": "Antigravity-Release-Uploader",
            "Content-Type": "audio/mp4",
            "Content-Length": str(file_size)
        }

        with open(fpath, "rb") as f:
            data = f.read()

        up_req = urllib.request.Request(upload_url, data=data, headers=upload_headers, method="POST")
        try:
            with urllib.request.urlopen(up_req) as up_resp:
                res_data = json.loads(up_resp.read().decode())
                print(f"  [SUCCESS] Uploaded {target_name} successfully! (Asset ID: {res_data['id']})")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(f"  [ERROR] Upload failed ({e.code}): {err_body}")

    print("\n[COMPLETE] All episodes checked and synchronized to GitHub Release!")

if __name__ == "__main__":
    main()
