# Whisper 安装指南

## 问题说明

OpenAI Whisper 依赖 `numba` 库，而 numba 目前仅支持 Python 3.10-3.13，不支持 Python 3.14。

错误信息：
```
RuntimeError: Cannot install on Python version 3.14.0; only versions >=3.10,<3.14 are supported.
```

## 解决方案

### 方案1：使用 Python 3.13 虚拟环境（推荐）

1. 创建 Python 3.13 虚拟环境：
```bash
cd /Users/daniel/git/hack/Sunflower
python3.13 -m venv .venv-py313
```

2. 激活虚拟环境：
```bash
source .venv-py313/bin/activate
```

3. 安装项目依赖：
```bash
cd lecture-video-composer
pip install -r requirements.txt
```

4. 安装 Whisper：
```bash
pip install openai-whisper
```

5. 验证安装：
```bash
python -c "import whisper; print(whisper.__version__)"
```

### 方案2：使用现有的 Python 3.13 环境

您的系统上已经有 Python 3.13.9，可以直接使用：

```bash
# 在项目根目录
cd /Users/daniel/git/hack/Sunflower/lecture-video-composer

# 创建新的虚拟环境
python3.13 -m venv .venv-whisper

# 激活
source .venv-whisper/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install openai-whisper
```

### 方案3：等待 numba 更新

等待 numba 项目发布支持 Python 3.14 的版本（可能需要数月）。

## 推荐的项目 Python 版本

为了获得最佳兼容性，建议项目使用：
- **Python 3.13.x**（当前稳定版）
- Python 3.12.x（长期支持）
- Python 3.11.x（广泛支持）

## 快速切换命令

创建一个便捷的切换脚本：

```bash
# 创建 setup-whisper.sh
cat > lecture-video-composer/setup-whisper.sh << 'EOF'
#!/bin/bash
# Whisper 环境设置脚本

echo "🔧 设置 Whisper 环境（Python 3.13）..."

# 检查 Python 3.13
if ! command -v python3.13 &> /dev/null; then
    echo "❌ Python 3.13 未找到"
    echo "请安装: brew install python@3.13"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d ".venv-whisper" ]; then
    echo "📦 创建虚拟环境..."
    python3.13 -m venv .venv-whisper
fi

# 激活环境
echo "✅ 激活虚拟环境..."
source .venv-whisper/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q openai-whisper

echo "✅ Whisper 环境已就绪！"
echo "Python 版本: $(python --version)"
echo ""
echo "使用方法:"
echo "  source .venv-whisper/bin/activate"
echo "  python examples/basic/test_v2_features.py"
EOF

chmod +x lecture-video-composer/setup-whisper.sh
```

使用方法：
```bash
cd lecture-video-composer
./setup-whisper.sh
```

## 验证安装

安装完成后，运行以下命令验证：

```bash
# 检查 Python 版本
python --version  # 应该显示 3.13.x

# 检查 Whisper
python -c "import whisper; print('✅ Whisper 已安装')"

# 检查 numba
python -c "import numba; print('✅ Numba 已安装')"

# 运行字幕测试
cd lecture-video-composer
python examples/basic/test_v2_features.py
```

## 常见问题

### Q: 为什么不能在 Python 3.14 中使用？
A: numba 是一个底层性能库，需要针对每个 Python 版本进行优化和测试。通常新 Python 版本发布后需要几个月时间才能获得支持。

### Q: 可以不使用 Whisper 吗？
A: 可以。Whisper 是可选功能，用于自动生成字幕。项目的核心功能（视频合成、播放器）不依赖 Whisper。

### Q: 有其他字幕生成方案吗？
A: 可以使用：
- 在线字幕服务（如讯飞、阿里云）
- 手动创建 SRT 文件
- 使用其他语音识别库（如 SpeechRecognition）

## 相关链接

- [numba 项目](https://github.com/numba/numba)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [Python 版本兼容性](https://devguide.python.org/versions/)

---

**更新日期**: 2025-10-25  
**适用版本**: lecture-video-composer v2.2
