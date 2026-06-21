#!/usr/bin/env python3
"""
GitHub Trending 数据采集脚本

使用 GitHub GraphQL API 批量抓取高星仓库的 star/fork 数据，
与历史数据对比计算日增/周增/月增，生成排行 JSON。

用法:
  python3 scripts/collect.py

环境变量:
  GITHUB_TOKEN - GitHub Personal Access Token (需要 public_repo 权限)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# ─── 配置 ────────────────────────────────────────────────────
GRAPHQL_URL = "https://api.github.com/graphql"
DATA_DIR = Path(__file__).parent.parent / "data"
HISTORY_DIR = DATA_DIR / "history"
TODAY = datetime.utcnow().strftime("%Y-%m-%d")

# 抓取配置
STAR_RANGES = [
    (500000, 100000),
    (100000, 50000),
    (50000, 20000),
    (20000, 10000),
    (10000, 5000),
    (5000, 2000),
    (2000, 1000),
    (1000, 500),
    (500, 200),
]
PAGE_SIZE = 100  # GraphQL 每页最多 100 条


# ─── GraphQL 查询 ─────────────────────────────────────────────
QUERY = """
query($query: String!, $cursor: String) {
  search(query: $query, type: REPOSITORY, first: 100, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        nameWithOwner
        name
        owner { login }
        description
        url
        homepageUrl
        stargazerCount
        forkCount
        watchers { totalCount }
        issues(states: OPEN) { totalCount }
        pullRequests(states: OPEN) { totalCount }
        primaryLanguage { name color }
        languages(first: 5, orderBy: {field: SIZE, direction: DESC}) {
          nodes { name color }
        }
        repositoryTopics(first: 10) {
          nodes { topic { name } }
        }
        createdAt
        pushedAt
        updatedAt
        licenseInfo { spdxId }
        isArchived
        isFork
      }
    }
  }
}
"""


def get_token():
    """获取 GitHub Token"""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("❌ 请设置环境变量 GITHUB_TOKEN")
        print("   export GITHUB_TOKEN=ghp_xxx")
        sys.exit(1)
    return token


def graphql_request(token, query, variables, retries=3):
    """发送 GraphQL 请求，带重试"""
    data = json.dumps({"query": query, "variables": variables}).encode('utf-8')
    token = token.encode('ascii', errors='ignore').decode('ascii')
    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "github-trending-collector"
    }

    for attempt in range(retries):
        try:
            req = urllib.request.Request(GRAPHQL_URL, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
                if "errors" in result:
                    print(f"  ⚠️ GraphQL errors: {result['errors']}")
                return result
        except urllib.error.HTTPError as e:
            if e.code == 403:
                # Rate limited
                reset_time = int(e.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset_time - int(time.time()), 10)
                print(f"  ⏳ Rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise


def fetch_repos_in_range(token, star_min, star_max):
    """抓取指定 star 范围内的仓库"""
    repos = []
    query_str = f"stars:{star_min}..{star_max} fork:true"
    cursor = None
    page = 0

    while page < 10:  # 每个范围最多 10 页 = 1000 个仓库
        variables = {"query": query_str, "cursor": cursor}
        result = graphql_request(token, QUERY, variables)

        search = result.get("data", {}).get("search", {})
        nodes = search.get("nodes", [])

        for repo in nodes:
            if repo.get("isArchived") or repo.get("isFork"):
                continue
            repos.append({
                "name": repo["nameWithOwner"],
                "owner": repo["owner"]["login"],
                "repo": repo["name"],
                "desc": repo.get("description") or "",
                "url": repo["url"],
                "homepage": repo.get("homepageUrl") or "",
                "stars": repo["stargazerCount"],
                "forks": repo["forkCount"],
                "watchers": repo.get("watchers", {}).get("totalCount", 0),
                "open_issues": repo.get("issues", {}).get("totalCount", 0),
                "open_prs": repo.get("pullRequests", {}).get("totalCount", 0),
                "lang": repo.get("primaryLanguage", {}).get("name") if repo.get("primaryLanguage") else None,
                "lang_color": repo.get("primaryLanguage", {}).get("color") if repo.get("primaryLanguage") else None,
                "languages": [l["name"] for l in repo.get("languages", {}).get("nodes", [])],
                "topics": [t["topic"]["name"] for t in repo.get("repositoryTopics", {}).get("nodes", [])],
                "created_at": repo.get("createdAt"),
                "pushed_at": repo.get("pushedAt"),
                "updated_at": repo.get("updatedAt"),
                "license": repo.get("licenseInfo", {}).get("spdxId") if repo.get("licenseInfo") else None,
            })

        page_info = search.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        page += 1

    return repos


def collect_all(token):
    """批量采集所有仓库"""
    all_repos = {}
    total_ranges = len(STAR_RANGES)

    for idx, (star_max, star_min) in enumerate(STAR_RANGES, 1):
        print(f"  📡 [{idx}/{total_ranges}] 抓取 stars:{star_min}..{star_max} ...")
        repos = fetch_repos_in_range(token, star_min, star_max)
        print(f"     找到 {len(repos)} 个仓库")

        for r in repos:
            name = r["name"]
            if name not in all_repos or r["stars"] > all_repos[name]["stars"]:
                all_repos[name] = r

        # 避免 rate limit
        if idx < total_ranges:
            time.sleep(1)

    return list(all_repos.values())


def load_history(date_str):
    """加载指定日期的历史数据"""
    path = HISTORY_DIR / f"{date_str}.json"
    if path.exists():
        with open(path) as f:
            data = json.load(f)
            # 转成 dict: name -> repo
            return {r["name"]: r for r in data}
    return {}


def save_history(repos):
    """保存今日数据到历史目录"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"{TODAY}.json"
    with open(path, "w") as f:
        json.dump(repos, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  💾 历史数据已保存: {path}")


def calculate_deltas(repos, history_today):
    """计算 star/fork 增量"""
    # 加载 1天前、7天前、30天前的数据
    dates = {}
    for label, days in [("d1", 1), ("d7", 7), ("d30", 30)]:
        d = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        dates[label] = load_history(d)

    enriched = []
    for repo in repos:
        name = repo["name"]
        entry = dict(repo)

        for label in ["d1", "d7", "d30"]:
            hist = dates[label].get(name)
            if hist:
                entry[f"star_{label}"] = repo["stars"] - hist["stars"]
                entry[f"fork_{label}"] = repo["forks"] - hist["forks"]
            else:
                entry[f"star_{label}"] = None
                entry[f"fork_{label}"] = None

        enriched.append(entry)

    return enriched


def generate_rankings(repos):
    """生成各类排行榜"""
    def safe_sort(key, limit=100):
        valid = [r for r in repos if r.get(key) is not None and r[key] > 0]
        return sorted(valid, key=lambda x: x[key], reverse=True)[:limit]

    rankings = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "date": TODAY,
        "total_repos": len(repos),
        "trending_daily": safe_sort("star_d1"),
        "trending_weekly": safe_sort("star_d7"),
        "trending_monthly": safe_sort("star_d30"),
        "forks_daily": safe_sort("fork_d1"),
        "new_repos": sorted(
            [r for r in repos if r.get("created_at") and r["created_at"][:10] >= (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")],
            key=lambda x: x["stars"],
            reverse=True
        )[:50],
        "by_language": {},
    }

    # 按语言分类 Top 10
    lang_repos = {}
    for r in repos:
        lang = r.get("lang") or "Other"
        if lang not in lang_repos:
            lang_repos[lang] = []
        lang_repos[lang].append(r)

    for lang, lang_list in sorted(lang_repos.items(), key=lambda x: -len(x[1])):
        if len(lang_list) >= 10:
            daily = sorted(
                [r for r in lang_list if r.get("star_d1") is not None and r["star_d1"] > 0],
                key=lambda x: x["star_d1"],
                reverse=True
            )[:10]
            if daily:
                rankings["by_language"][lang] = daily

    return rankings


def generate_summary(rankings):
    """生成简要摘要（给前端用的轻量数据）"""
    def slim(repo_list, limit=30):
        return [{
            "n": r["name"],
            "d": r["desc"][:100],
            "s": r["stars"],
            "f": r["forks"],
            "l": r.get("lang"),
            "lc": r.get("lang_color"),
            "t": r.get("topics", [])[:5],
            "u": r["url"],
            "hp": r.get("homepage", ""),
            "s1": r.get("star_d1"),
            "s7": r.get("star_d7"),
            "s30": r.get("star_d30"),
            "f1": r.get("fork_d1"),
            "pa": r.get("pushed_at", ""),
            "ca": r.get("created_at", ""),
        } for r in repo_list[:limit]]

    return {
        "date": rankings["date"],
        "generated_at": rankings["generated_at"],
        "total": rankings["total_repos"],
        "daily": slim(rankings["trending_daily"]),
        "weekly": slim(rankings["trending_weekly"]),
        "monthly": slim(rankings["trending_monthly"]),
        "new": slim(rankings["new_repos"], 20),
        "langs": list(rankings["by_language"].keys())[:20],
    }


def cleanup_old_history(keep_days=35):
    """清理超过 keep_days 天的历史数据"""
    cutoff = datetime.utcnow() - timedelta(days=keep_days)
    count = 0
    for f in HISTORY_DIR.glob("*.json"):
        try:
            file_date = datetime.strptime(f.stem, "%Y-%m-%d")
            if file_date < cutoff:
                f.unlink()
                count += 1
        except ValueError:
            pass
    if count:
        print(f"  🧹 清理了 {count} 个过期历史文件")


def main():
    print(f"🚀 GitHub Trending 数据采集 - {TODAY}")
    print(f"=" * 50)

    token = get_token()

    # 1. 采集数据
    print(f"\n📡 开始采集数据...")
    start = time.time()
    repos = collect_all(token)
    elapsed = time.time() - start
    print(f"  ✅ 共采集 {len(repos)} 个仓库，耗时 {elapsed:.0f}s")

    # 2. 保存历史
    save_history(repos)

    # 3. 计算增量
    print(f"\n📊 计算增量数据...")
    history_today = {r["name"]: r for r in repos}
    repos = calculate_deltas(repos, history_today)

    # 统计有效增量
    with_daily = sum(1 for r in repos if r.get("star_d1") is not None)
    with_weekly = sum(1 for r in repos if r.get("star_d7") is not None)
    with_monthly = sum(1 for r in repos if r.get("star_d30") is not None)
    print(f"  日增数据: {with_daily}/{len(repos)}")
    print(f"  周增数据: {with_weekly}/{len(repos)}")
    print(f"  月增数据: {with_monthly}/{len(repos)}")

    # 4. 生成排行榜
    print(f"\n🏆 生成排行榜...")
    rankings = generate_rankings(repos)

    # 5. 保存完整数据
    full_path = DATA_DIR / "rankings.json"
    with open(full_path, "w") as f:
        json.dump(rankings, f, ensure_ascii=False, indent=2)
    print(f"  💾 完整数据: {full_path} ({full_path.stat().st_size / 1024:.0f} KB)")

    # 6. 生成前端用的轻量摘要
    summary = generate_summary(rankings)
    summary_path = DATA_DIR / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  💾 轻量摘要: {summary_path} ({summary_path.stat().st_size / 1024:.0f} KB)")

    # 7. 清理旧数据
    cleanup_old_history()

    # 8. 打印 Top 10
    print(f"\n🔥 今日 Star 增长 Top 10:")
    print(f"{'─' * 60}")
    for i, r in enumerate(rankings["trending_daily"][:10], 1):
        delta = r.get("star_d1", 0)
        print(f"  {i:2d}. {r['name']:<40} +{delta:>5}⭐  ({r['stars']:>7}⭐)")

    print(f"\n📊 本周 Star 增长 Top 10:")
    print(f"{'─' * 60}")
    for i, r in enumerate(rankings["trending_weekly"][:10], 1):
        delta = r.get("star_d7", 0)
        print(f"  {i:2d}. {r['name']:<40} +{delta:>6}⭐  ({r['stars']:>7}⭐)")

    print(f"\n✅ 采集完成！")


if __name__ == "__main__":
    main()
