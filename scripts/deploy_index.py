#!/usr/bin/env python3
"""Deploy index.html to GitHub using GITHUB_TOKEN env var."""
import subprocess, json, base64, os, sys
from pathlib import Path

TOKEN = os.environ.get("GITHUB_TOKEN", "")
if not TOKEN:
    print("❌ Run: export GITHUB_TOKEN=ghp_xxx...xxx first")
    sys.exit(1)

BASE = "https://api.github.com/repos/thisDy/github-trending"
fname = "index.html"
fpath = Path("/Users/firefly/.openclaw/workspace/github-trending") / fname

print(f"Deploying {fname} ({fpath.stat().st_size//1024}KB)...")

with open(fpath, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

r = subprocess.run(["curl", "-s", "-H", f"Authorization: token {TOKEN}", f"{BASE}/contents/{fname}"], capture_output=True, text=True, timeout=15)
sha = None
try: sha = json.loads(r.stdout).get("sha")
except: pass

p = {"message": "Redesign v4: layered bg, gradient accent, refined typography", "content": b64}
if sha: p["sha"] = sha

with open("/tmp/p.json", "w") as f:
    json.dump(p, f)

r2 = subprocess.run(["curl", "-s", "-X", "PUT", "-H", f"Authorization: token {TOKEN}", "-H", "Content-Type: application/json", "-d", "@/tmp/p.json", f"{BASE}/contents/{fname}"], capture_output=True, text=True, timeout=30)
try:
    resp = json.loads(r2.stdout)
    if "content" in resp:
        print(f"✅ OK! https://thisDy.github.io/github-trending/")
    else:
        print(f"❌ {resp.get('message', 'unknown error')}")
except:
    print(f"❌ {r2.stdout[:200]}")

os.remove("/tmp/p.json")
