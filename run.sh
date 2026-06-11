#!/bin/bash
# Serenity-A 数据面板启动脚本
cd "$(dirname "$0")"

# 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 检查 API Key
if [ -z "$DEEPSEEK_API_KEY" ]; then
    echo "⚠️  未设置 DEEPSEEK_API_KEY"
    echo "   复制 .env.example 为 .env 并填入你的 Key"
    echo "   或运行: export DEEPSEEK_API_KEY=你的Key"
    echo "   没有 Key 仍可使用行情数据面板，但 AI 分析报告不可用"
    echo ""
fi

echo "🚀 Serenity-A 数据面板启动中..."
echo "   访问地址: http://localhost:${PORT:-8765}"
echo "   按 Ctrl+C 停止"
echo ""

python3 app.py
