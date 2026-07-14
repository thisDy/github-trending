#!/usr/bin/env python3
"""Deploy 高考志愿填报思维导图 to GitHub Pages"""
import urllib.request, json, base64, os, sys

token = os.environ.get('GITHUB_TOKEN', '')
if not token:
    print('ERROR: export GITHUB_TOKEN first'); sys.exit(1)

user = json.loads(urllib.request.urlopen(
    urllib.request.Request('https://api.github.com/user',
        headers={'Authorization': f'Bearer {token}', 'User-Agent': 'x'}), timeout=10
).read())['login']
print(f'User: {user}')

repo = 'gaokao-mindmap-3'
src = os.path.expanduser('~/.openclaw/workspace/高考志愿填报-逻辑与风险-思维导图.html')
if not os.path.exists(src):
    print(f'ERROR: Source file not found: {src}'); sys.exit(1)

# 1. Create repo (ignore if exists)
try:
    req = urllib.request.Request(
        'https://api.github.com/user/repos',
        data=json.dumps({'name': repo, 'auto_init': True, 'public': True}).encode(),
        headers={'Authorization': f'Bearer {token}', 'User-Agent': 'x',
                 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='POST')
    urllib.request.urlopen(req, timeout=20)
    print('Repo created')
except urllib.error.HTTPError:
    print('Repo exists (continuing)')
import time; time.sleep(1)

# 2. Deploy index.html
content = open(src, 'rb').read()
b64 = base64.b64encode(content).decode()
print(f'File: {len(content)} bytes')

sha = None
try:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{user}/{repo}/contents/index.html',
        headers={'Authorization': f'Bearer {token}', 'User-Agent': 'x',
                 'Accept': 'application/vnd.github.v3+json'})
    sha = json.loads(urllib.request.urlopen(req, timeout=15).read())['sha']
    print('Found existing file')
except urllib.error.HTTPError:
    print('New file')

payload = {'message': 'Deploy mind map', 'content': b64}
if sha: payload['sha'] = sha

req = urllib.request.Request(
    f'https://api.github.com/repos/{user}/{repo}/contents/index.html',
    data=json.dumps(payload).encode(),
    headers={'Authorization': f'Bearer {token}', 'User-Agent': 'x',
             'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
    method='PUT')
resp = urllib.request.urlopen(req, timeout=30)
print(f'Deployed: {resp.status}')

# 3. Enable Pages
try:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{user}/{repo}/pages',
        data=json.dumps({'source': {'branch': 'main', 'path': '/'}}).encode(),
        headers={'Authorization': f'Bearer {token}', 'User-Agent': 'x',
                 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='POST')
    urllib.request.urlopen(req, timeout=20)
    print('Pages enabled')
except:
    print('Pages: already enabled or pending')

print(f'\nURL: https://{user}.github.io/{repo}/')
