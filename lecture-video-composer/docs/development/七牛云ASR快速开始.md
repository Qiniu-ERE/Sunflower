# 七牛云ASR快速开始指南

## 5分钟快速配置

本指南帮助您快速配置七牛云ASR服务，开始使用AI字幕功能。

## 步骤1: 获取API密钥（2分钟）

1. 访问 https://portal.qiniu.com/ai-token/overview
2. 登录或注册七牛云账号
3. 开通AI Token API服务
4. 复制您的API密钥

## 步骤2: 配置项目（1分钟）

```bash
# 进入项目目录
cd lecture-video-composer

# 复制配置模板
cp .env.example .env

# 编辑配置文件
nano .env  # 或使用你喜欢的编辑器
```

在 `.env` 文件中填写：
```env
QINIU_AI_API_KEY=你的API密钥
SUBTITLE_SERVICE=qiniu
```

保存并关闭文件。

## 步骤3: 安装依赖（2分钟）

```bash
# 安装Python依赖
pip install -r requirements.txt

# 或者只安装新增的依赖
pip install requests python-dotenv
```

## 步骤4: 验证配置

```bash
# 测试配置
cd src/services/subtitle
python subtitle_factory.py
```

看到 ✅ 表示配置成功！

## 开始使用

### 方式1: Web界面（推荐）

1. 启动Web服务器：
   ```bash
   cd lecture-video-composer
   python run_web.py
   ```

2. 打开浏览器访问: http://localhost:5000

3. 创建项目并导出视频时，勾选"生成AI字幕"

### 方式2: 命令行

```bash
# 为音频文件生成字幕
python -m src.services.subtitle.qiniu_asr_service \
    your_audio.mp3 \
    --output-dir output/subtitles \
    --language zh
```

## 常见问题

**Q: 提示"API密钥未设置"？**
- 检查 `.env` 文件是否在项目根目录
- 确认API密钥没有多余空格
- 重新加载环境变量

**Q: 想切换回Whisper？**
编辑 `.env`:
```env
SUBTITLE_SERVICE=whisper
```

## 完整文档

- 详细配置说明: [七牛云ASR配置指南](./七牛云ASR配置指南.md)
- 功能使用说明: [实时字幕功能说明](./实时字幕功能说明.md)

## 技术支持

- 七牛云API文档: https://developer.qiniu.com/aitokenapi/12981/asr-tts-ocr-api
- 项目Issues: GitHub项目页面

---
就这么简单！现在您可以使用AI字幕功能了 🎉
