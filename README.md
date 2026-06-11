# Serenity-A · 网站

**A股供应链卡点逆向投资分析引擎** — 将 Serenity(@aleabitoreddit) 的"从下游钱流出发、沿供应链逆向往上找卡点"方法论适配到 A 股市场的静态展示网站。

## 页面

| 页面 | 说明 |
|------|------|
| [首页](index.html) | 框架总览、KPI仪表盘、核心立场 |
| [方法论](framework.html) | 14条卡点判据、12条红旗、估值框架 |
| [美股映射](mapping.html) | NVDA→A股映射表、四大分析维度 |
| [分析流水线](pipeline.html) | 12步全流程详解 |
| [A股维度](a-dims.html) | 北向/解禁/龙虎榜等A股特有因子 |
| [报告标准](reports.html) | 输出规范、证据规则、独立复核 |

## 技术栈

纯静态网站：HTML + CSS + JS，零外部依赖。

## 部署到 GitHub Pages

```bash
# 1. 在 GitHub 上创建一个仓库（例如 serenity-a-site）

# 2. 初始化并推送
git init
git add .
git commit -m "Initial commit: Serenity-A website"
git branch -M main
git remote add origin https://github.com/<你的用户名>/serenity-a-site.git
git push -u origin main

# 3. 在 GitHub 仓库设置中启用 GitHub Pages：
#    Settings → Pages → Source: Deploy from branch: main, / (root)
#    网站将发布到 https://<你的用户名>.github.io/serenity-a-site/
```

## 许可

Apache License 2.0
