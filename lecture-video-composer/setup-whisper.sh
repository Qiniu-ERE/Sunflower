#!/bin/bash
# Whisper 环境设置脚本
# 用于在 Python 3.13 环境中安装 Whisper（因为 Python 3.14 不兼容）

echo "🔧 设置 Whisper 环境（Python 3.13）..."

# 检查 Python 3.13
if ! command -v python3.13 &> /dev/null; then
    echo "❌ Python 3.13 未找到"
    echo "请安装: brew install python@3.13"
    exit 1
fi

echo "✅ 找到 Python 3.13: $(python3.13 --version)"

# 创建虚拟环境（如果不存在）
if [ ! -d ".venv-whisper" ]; then
    echo "📦 创建虚拟环境..."
    python3.13 -m venv .venv-whisper
else
    echo "✅ 虚拟环境已存在"
fi

# 激活环境
echo "🔄 激活虚拟环境..."
source .venv-whisper/bin/activate

# 升级 pip
echo "📦 升级 pip..."
pip install -q --upgrade pip

# 安装项目依赖
echo "📥 安装项目依赖..."
pip install -q -r requirements.txt

# 安装 Whisper
echo "🎤 安装 OpenAI Whisper..."
pip install -q openai-whisper

# 验证安装
echo ""
echo "✅ Whisper 环境设置完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Python 版本: $(python --version)"
echo "Whisper 版本: $(python -c 'import whisper; print(whisper.__version__)' 2>/dev/null || echo '未知')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📝 使用方法:"
echo "  1. 激活环境: source .venv-whisper/bin/activate"
echo "  2. 运行测试: python examples/basic/test_v2_features.py"
echo "  3. 退出环境: deactivate"
echo ""
