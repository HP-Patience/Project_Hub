#!/usr/bin/env python3
"""从 data/projects.json 生成 index.html 与 README.md。

用法：python build.py
无第三方依赖，Python 3.8+ 即可。
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_FILE = ROOT / "data" / "projects.json"
TEMPLATE = ROOT / "templates" / "index.html"
OUT_HTML = ROOT / "index.html"
OUT_README = ROOT / "README.md"

STATUS_LABEL = {
    "active": "活跃",
    "maintained": "维护中",
    "paused": "暂缓",
    "fork": "上游衍生",
    "archived": "已归档",
    "local": "仅本地",
}
REPO_URL = "https://github.com/{owner}/{name}"
SITE_URL = "https://hp-patience.github.io/Project_Hub/"


def fail(msg: str) -> None:
    print(f"[build] 错误：{msg}", file=sys.stderr)
    raise SystemExit(1)


def load() -> dict:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    cats = data.get("categories") or []
    projects = data.get("projects") or []
    if not cats or not projects:
        fail("categories 或 projects 为空")

    cat_ids = [c["id"] for c in cats]
    if len(cat_ids) != len(set(cat_ids)):
        fail("categories.id 有重复")

    seen = set()
    for p in projects:
        for key in ("name", "owner", "category", "tagline", "stack", "tags", "updated"):
            if key not in p:
                fail(f"项目 {p.get('name', '?')} 缺少字段 {key}")
        if p["category"] not in cat_ids:
            fail(f"项目 {p['name']} 的分类 {p['category']} 未定义")
        if p["name"].lower() in seen:
            fail(f"项目重名：{p['name']}")
        seen.add(p["name"].lower())
        try:
            datetime.strptime(p["updated"], "%Y-%m-%d")
        except ValueError:
            fail(f"项目 {p['name']} 的 updated 不是 YYYY-MM-DD")
        if p["owner"] not in (data.get("meta", {}).get("accounts") or []):
            fail(f"项目 {p['name']} 的 owner {p['owner']} 不在 meta.accounts 白名单内")
        override = p.get("statusOverride")
        if override and override not in STATUS_LABEL:
            fail(f"项目 {p['name']} 的 statusOverride 非法：{override}")
    return data


def status_of(p: dict, today: date) -> str:
    if p.get("statusOverride"):
        return p["statusOverride"]
    days = (today - datetime.strptime(p["updated"], "%Y-%m-%d").date()).days
    if days <= 14:
        return "active"
    if days <= 90:
        return "maintained"
    return "paused"


def build_html(data: dict, today: date, now: str) -> None:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = (
        tpl.replace("__DATA__", payload)
        .replace("__TODAY__", today.isoformat())
        .replace("__YEAR__", str(today.year))
        .replace("__GENERATED__", now)
    )
    OUT_HTML.write_text(html, encoding="utf-8")


def build_readme(data: dict, today: date, now: str) -> None:
    cats = data["categories"]
    projects = data["projects"]
    owner = data["meta"]["owner"]

    rows = []
    for c in cats:
        items = [p for p in projects if p["category"] == c["id"]]
        items.sort(key=lambda p: p["updated"], reverse=True)
        items.sort(key=lambda p: not p.get("featured"))
        if not items:
            continue
        rows.append(f"\n### {c['name']} · {c['en']}\n\n{c['desc']}\n")
        rows.append("| 项目 | 说明 | 技术栈 | 状态 | 最近更新 |")
        rows.append("| --- | --- | --- | --- | --- |")
        for p in items:
            name = p["name"]
            if p.get("statusOverride") != "local":
                name = f"[{name}]({REPO_URL.format(owner=p['owner'], name=p['name'])})"
            stack = " · ".join(p["stack"]) if p["stack"] else "—"
            rows.append(
                f"| {name} | **{p['tagline']}** {p['desc']} | {stack} | "
                f"{STATUS_LABEL[status_of(p, today)]} | {p['updated']} |"
            )

    overview = ["| 分类 | 数量 | 说明 |", "| --- | --- | --- |"]
    for c in cats:
        n = sum(1 for p in projects if p["category"] == c["id"])
        overview.append(f"| {c['name']} | {n} | {c['desc']} |")

    active = sum(1 for p in projects if status_of(p, today) == "active")
    latest = max(p["updated"] for p in projects)

    body = f"""<div align="center">

# 项目中枢 · Project Hub

把 HP-Patience 账号与本地工作区里的项目，按用途归成一条可读的索引。

<img src="assets/preview.png" alt="项目中枢页面预览：深色界面，顶部为统计与分类筛选，下方为精选项目卡片" width="100%">

[**在线浏览 →**]({SITE_URL}) · [个人主页](https://github.com/{owner})

<sub>{len(projects)} 个项目 · {len(cats)} 个分类 · {active} 个近 14 天活跃 · 最近更新 {latest}</sub>

</div>

---

## 分类概览

{chr(10).join(overview)}

状态说明：**活跃** 14 天内推送 · **维护中** 90 天内 · **暂缓** 超过 90 天 · **上游衍生** 基于他人项目二次开发 · **已归档** 停止维护 · **仅本地** 未发布到远程。
{chr(10).join(rows)}

---

## 仓库结构

```
Project_Hub/
├─ data/projects.json     # 唯一数据源：分类与项目条目
├─ templates/index.html   # 页面模板（含样式与交互）
├─ build.py               # 生成 index.html 与 README.md
├─ index.html             # 生成产物，GitHub Pages 入口
└─ README.md              # 生成产物，本文件
```

## 维护方式

1. 在 `data/projects.json` 增加或修改条目（`category` 必须是 `categories` 里已有的 id）。
2. 运行 `python build.py` 重新生成页面与 README。
3. 提交并推送，Pages 自动更新。

字段约定：`name` `owner` `category` `tagline`（一句话）`desc`（两三句）`stack` `tags` `updated`；可选 `homepage` `featured` `statusOverride`（`fork` / `archived` / `local`）。状态默认由 `updated` 推算。

<sub>生成时间 {now} · 数据来源 GitHub REST API 与本地工作区</sub>
"""
    OUT_README.write_text(body, encoding="utf-8")


def main() -> None:
    data = load()
    today = date.today()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    build_html(data, today, now)
    build_readme(data, today, now)
    print(f"[build] 已生成 index.html 与 README.md（{len(data['projects'])} 个项目 / {len(data['categories'])} 个分类）")


if __name__ == "__main__":
    main()
