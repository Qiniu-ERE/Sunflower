# 七牛云ASR配置指南

## 概述

本系统支持使用七牛云AI Token API进行语音识别（ASR），自动生成字幕。本文档介绍如何配置和使用七牛云ASR服务。

## 前提条件

1. 拥有七牛云账号
2. 已开通七牛云AI Token API服务
3. 已获取API密钥

## 获取七牛云API密钥

### 步骤1: 注册七牛云账号

访问 [七牛云官网](https://www.qiniu.com/) 注册账号

### 步骤2: 开通AI Token API服务

1. 登录七牛云控制台
2. 访问 [AI Token API页面](https://portal.qiniu.com/ai-token/overview)
3. 根据提示开通服务

### 步骤3: 获取API密钥

1. 在AI Token API控制台找到"密钥管理"
2. 创建新的API密钥或使用现有密钥
3. 复制API密钥（请妥善保管，不要泄露）

## 配置步骤

### 方法1: 使用环境变量文件（推荐）

1. **复制配置模板**
   ```bash
   cd lecture-video-composer
   cp .env.example .env
   ```

2. **编辑 .env 文件**
   ```bash
   # 使用你喜欢的编辑器打开
   nano .env
   # 或
   vim .env
   # 或
   code .env
   ```

3. **填写配置**
   ```env
   # 七牛云AI Token API配置
   QINIU_AI_API_KEY=your_actual_api_key_here
   
   # 字幕服务配置（使用七牛云）
   SUBTITLE_SERVICE=qiniu
   
   # 日志级别
   LOG_LEVEL=INFO
   ```

4. **保存文件**

### 方法2: 使用系统环境变量

如果不想使用 `.env` 文件，可以直接设置系统环境变量：

**Linux/macOS:**
```bash
export QINIU_AI_API_KEY="your_actual_api_key_here"
export SUBTITLE_SERVICE="qiniu"
```

**Windows (PowerShell):**
```powershell
$env:QINIU_AI_API_KEY="your_actual_api_key_here"
$env:SUBTITLE_SERVICE="qiniu"
```

**Windows (命令提示符):**
```cmd
set QINIU_AI_API_KEY=your_actual_api_key_here
set SUBTITLE_SERVICE=qiniu
```

## 安装依赖

确保已安装必要的Python包：

```bash
pip install -r requirements.txt
```

主要依赖：
- `requests`: HTTP请求库
- `python-dotenv`: 环境变量管理

## 验证配置

### 方法1: 使用测试脚本

```bash
cd lecture-video-composer/src/services/subtitle
python subtitle_factory.py
```

成功的输出示例：
```
测试七牛云ASR服务...
✅ 七牛云ASR服务可用
   服务实例: <qiniu_asr_service.QiniuASRService object at 0x...>
```

### 方法2: 测试实际转录

```bash
python qiniu_asr_service.py /path/to/your/audio.mp3 --api-key "your_api_key"
```

## 使用示例

### 1. 在视频导出时生成字幕

1. 登录系统Web界面
2. 进入"视频导出"页面
3. 选择要导出的项目
4. 勾选"生成AI字幕"选项
5. 点击"开始导出"

系统将自动：
- 提取项目音频
- 调用七牛云ASR API进行语音识别
- 生成SRT格式字幕文件
- 将字幕保存到项目目录

### 2. 使用Python API

```python
from pathlib import Path
from src.services.subtitle.subtitle_factory import get_subtitle_service

# 获取字幕服务实例
service = get_subtitle_service()

# 生成字幕
audio_file = Path("path/to/audio.mp3")
output_dir = Path("output/subtitles")

subtitle_file = service.generate_subtitles(
    audio_file=audio_file,
    output_dir=output_dir,
    language="zh"  # 中文
)

if subtitle_file:
    print(f"字幕已生成: {subtitle_file}")
else:
    print("字幕生成失败")
```

### 3. 命令行使用

```bash
# 使用七牛云ASR生成字幕
python -m src.services.subtitle.qiniu_asr_service \
    audio.mp3 \
    --output-dir output/subtitles \
    --api-key "your_api_key" \
    --language zh
```

## API参数说明

### language参数

- `zh`: 中文（简体）
- `en`: 英文
- 其他语言请参考七牛云API文档

### enable_timestamp参数

- `true`: 返回带时间戳的字幕片段（默认）
- `false`: 只返回完整文本

### enable_punctuation参数

- `true`: 启用标点符号（默认）
- `false`: 不添加标点符号

## 响应格式

七牛云ASR API返回JSON格式：

```json
{
    "code": 0,
    "message": "success",
    "result": {
        "text": "完整的转录文本",
        "segments": [
            {
                "text": "第一段文本",
                "start": 0.0,
                "end": 2.5
            },
            {
                "text": "第二段文本",
                "start": 2.5,
                "end": 5.0
            }
        ]
    }
}
```

## 生成的字幕格式

系统生成标准SRT格式字幕：

```srt
1
00:00:00,000 --> 00:00:02,500
第一段文本

2
00:00:02,500 --> 00:00:05,000
第二段文本
```

## 常见问题

### Q1: API密钥无效

**问题**: 提示"七牛云API密钥未设置"或"API密钥无效"

**解决方案**:
1. 检查 `.env` 文件中的API密钥是否正确
2. 确认API密钥没有多余的空格或引号
3. 验证API密钥在七牛云控制台是否有效
4. 检查是否已正确安装 `python-dotenv`

### Q2: 请求超时

**问题**: ASR API请求超时

**解决方案**:
1. 检查网络连接
2. 音频文件较大时，适当增加超时时间
3. 尝试压缩音频文件大小

### Q3: 字幕时间戳不准确

**问题**: 生成的字幕时间与实际不符

**解决方案**:
1. 确保音频文件质量良好
2. 检查音频编码格式是否支持
3. 尝试使用不同的音频格式（推荐MP3或WAV）

### Q4: 识别效果不佳

**问题**: 转录文本错误较多

**解决方案**:
1. 提高音频质量（降低背景噪音）
2. 确保发音清晰
3. 检查是否选择了正确的语言参数
4. 音频音量适中（不要太小或太大）

### Q5: 切换到Whisper服务

**问题**: 想使用本地Whisper而不是七牛云ASR

**解决方案**:
编辑 `.env` 文件：
```env
# 改为使用whisper
SUBTITLE_SERVICE=whisper
WHISPER_MODEL=base
```

## 费用说明

1. 七牛云ASR API按使用量计费
2. 具体价格请参考 [七牛云官方定价](https://www.qiniu.com/prices/ai-token)
3. 建议定期检查账户余额和使用量

## 安全建议

1. **不要**将API密钥提交到Git仓库
2. **不要**在代码中硬编码API密钥
3. `.env` 文件已在 `.gitignore` 中排除
4. 定期更换API密钥
5. 为不同环境使用不同的API密钥

## 技术支持

### 七牛云官方文档
- API文档: https://developer.qiniu.com/aitokenapi/12981/asr-tts-ocr-api
- 控制台: https://portal.qiniu.com/ai-token/overview

### 项目相关
- 问题反馈: 在项目GitHub提交Issue
- 技术交流: 查看项目README联系方式

## 附录: 完整配置示例

### .env 文件示例

```env
# 七牛云AI Token API配置
# 获取方式：https://portal.qiniu.com/ai-token/overview
QINIU_AI_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# 字幕服务配置
# 可选值: qiniu (七牛云ASR) 或 whisper (本地Whisper)
SUBTITLE_SERVICE=qiniu

# Whisper配置（仅在使用whisper时需要）
WHISPER_MODEL=base  # 可选: tiny, base, small, medium, large

# 日志级别
LOG_LEVEL=INFO
```

### Python代码示例

```python
import os
from pathlib import Path
from dotenv import load_dotenv
from src.services.subtitle.qiniu_asr_service import QiniuASRService

# 加载环境变量
load_dotenv()

# 获取API密钥
api_key = os.getenv('QINIU_AI_API_KEY')

# 创建服务实例
service = QiniuASRService(api_key=api_key)

# 生成字幕
audio_file = Path("examples/fixtures/2025-10-24-15:15:15.mp3")
output_dir = Path("output/subtitles")

result = service.generate_subtitles(
    audio_file=audio_file,
    output_dir=output_dir,
    language="zh"
)

if result:
    print(f"✅ 成功: {result}")
else:
    print("❌ 失败")
```

---

*文档版本: 1.0*  
*最后更新: 2025年10月29日*
