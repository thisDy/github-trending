#!/usr/bin/env python3
"""
Deploy files to GitHub via API (bypasses git network issues).
"""
import urllib.request
import json
import base64
import os
import sys
from pathlib import Path

REPO = "thisDy/github-trending"
BASE_URL = f"https://api.github.com/repos/{REPO}"

def get_headers():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    # Force ASCII encoding for token
    token = token.encode("ascii", errors="ignore").decode("ascii")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "openclaw-deploy"
    }

def api_get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=get_headers())
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def api_put(path, data):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={**get_headers(), "Content-Type": "application/json; charset=utf-8"},
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())

def upload_file(local_path, repo_path, message):
    with open(local_path, "rb") as f:
        content = f.read()
    b64 = base64.b64encode(content).decode("ascii")

    sha = None
    try:
        existing = api_get(f"/contents/{repo_path}")
        sha = existing.get("sha")
    except:
        pass

    payload = {"message": message, "content": b64}
    if sha:
        payload["sha"] = sha

    return api_put(f"/contents/{repo_path}", payload)

def main():
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("❌ 请设置 GITHUB_TOKEN")
        sys.exit(1)

    print(f"🚀 Deploying to {REPO}...")
    print("=" * 50)

    base = Path("/Users/firefly/.openclaw/workspace/github-trending")

    files = [
        ("index.html", "index.html"),
        ("manifest.json", "manifest.json"),
        ("sw.js", "sw.js"),
        ("icon-192.png", "icon-192.png"),
        ("icon-512.png", "icon-512.png"),
        ("README.md", "README.md"),
        ("data/summary.json", "data/summary.json"),
        ("data/rankings.json", "data/rankings.json"),
        ("scripts/collect.py", "scripts/collect.py"),
        ("scripts/deploy.py", "scripts/deploy.py"),
    ]

    # Also upload history files
    history_dir = base / "data" / "history"
    if history_dir.exists():
        for f in sorted(history_dir.glob("*.json")):
            rel = f.relative_to(base)
            files.append((str(f), str(rel)))

    success = 0
    for local_name, repo_name in files:
        local_path = base / local_name
        if not local_path.exists():
            print(f"  ⚠️ 跳过: {local_name}")
            continue

        size = local_path.stat().st_size
        try:
            upload_file(local_path, repo_name, f"Update {repo_name}")
            print(f"  ✅ {repo_name} ({size/1024:.1f} KB)")
            success += 1
        except Exception as e:
            print(f"  ❌ {repo_name}: {e}")

    print(f"\n{'=' * 50}")
    print(f"✅ 部署完成! {success}/{len(files)} 个文件")
    print(f"🌐 https://thisDy.github.io/github-trending/")

if __name__ == "__main__":
    main()
