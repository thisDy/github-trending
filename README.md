# 🔥 GitHub 热榜 - 趋势追踪

实时追踪 GitHub 热门开源项目，按 **日增 / 周增 / 月增** Star 数排行。

🌐 **在线访问：** https://thisDy.github.io/github-trending/

## ✨ 功能

- 📈 **日增排行** — 24 小时内 Star 增长最多的项目
- 📊 **周增排行** — 7 天内增长最多
- 🔥 **月增排行** — 30 天内增长最多
- 🆕 **新项目** — 刚创建就爆火的项目
- 🏷️ **语言筛选** — Python / JS / TS / Rust / Go 等
- 📲 **PWA 支持** — 手机添加到主屏幕，像 APP 一样使用
- 📴 **离线缓存** — 断网也能看

## 🏗️ 架构

```
GitHub Actions (每天自动运行)
    │
    ├─ GitHub GraphQL API 批量抓取 240k+ 仓库
    ├─ 与历史数据对比，计算 star/fork 增量
    ├─ 生成排行榜 JSON
    └─ 自动提交到仓库
            │
            ▼
    GitHub Pages (免费托管)
            │
            ▼
    PWA 前端 (手机/桌面)
```

## 📁 项目结构

```
github-trending/
├── .github/workflows/
│   └── collect.yml          # GitHub Actions 定时任务
├── scripts/
│   └── collect.py           # 数据采集脚本
├── data/
│   ├── summary.json         # 前端用的轻量摘要
│   ├── rankings.json        # 完整排行榜数据
│   └── history/             # 历史快照 (30天自动清理)
│       └── YYYY-MM-DD.json
├── index.html               # PWA 前端
├── sw.js                    # Service Worker
├── manifest.json            # PWA 配置
├── icon-192.png
└── icon-512.png
```

## 🔧 本地运行

### 采集数据（需要 GitHub Token）

```bash
export GITHUB_TOKEN=ghp_your_token_here
python3 scripts/collect.py
```

### 本地预览前端

```bash
python3 -m http.server 8080
# 打开 http://localhost:8080
```

## 📊 数据来源

- **GitHub GraphQL API** — 批量获取仓库的 Star/Fork/Issue 等数据
- **增量计算** — 与 1天前、7天前、30天前的历史快照对比
- **每日更新** — GitHub Actions 每天北京时间 10:00 自动运行

## 📝 License

MIT
