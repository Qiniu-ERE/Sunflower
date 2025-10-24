# Whisper SSL证书问题解决方案

## 问题描述

在中国大陆使用Whisper时，可能会遇到SSL证书验证错误：

```
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: 
Hostname mismatch, certificate is not valid for 'openaipublic.azureedge.net'
```

这是因为Whisper需要从OpenAI的服务器下载模型文件，但网络环境导致SSL证书验证失败。

---

## 解决方案

### 方案1: 使用--no-subtitles暂时跳过字幕功能 ⭐推荐

如果您暂时不需要字幕功能，可以禁用它：

```bash
python src/core/lecture_composer.py \
    examples/fixtures/2025-10-24-15:15:15.mp3 \
    examples/fixtures/sample-photos/ \
    --export-video \
    --no-subtitles
```

这样可以正常生成720p视频，只是不包含字幕。

### 方案2: 手动下载Whisper模型 ⭐推荐

1. **创建模型缓存目录**：
```bash
mkdir -p ~/.cache/whisper
```

2. **手动下载模型文件**（选择一个）：

使用浏览器或下载工具下载以下文件到 `~/.cache/whisper/` 目录：

#### tiny模型（最小，最快）
```
https://openaipublic.azureedge.net/main/whisper/models/65147644a518d12f04e32d6f3b26facc3f8dd46e5390956a9424a650c0ce22b9/tiny.pt
```
文件名保存为：`tiny.pt`

#### base模型（推荐，默认）
```
https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt
```
文件名保存为：`base.pt`

#### small模型（更准确）
```
https://openaipublic.azureedge.net/main/whisper/models/9ecf779972d90ba49c06d968637d720dd632c55bbf19d441fb42bf17a411e794/small.pt
```
文件名保存为：`small.pt`

3. **下载方式**：

**方法A: 使用curl**（如果可以翻墙）
```bash
cd ~/.cache/whisper
curl -O https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt
```

**方法B: 使用浏览器**
1. 开启VPN/代理
2. 在浏览器中打开上面的URL
3. 下载文件到 `~/.cache/whisper/` 目录
4. 确保文件名为 `base.pt`

**方法C: 使用第三方镜像**（推荐）
```bash
# 使用Hugging Face镜像
cd ~/.cache/whisper
wget https://huggingface.co/openai/whisper-base/resolve/main/pytorch_model.bin -O base.pt
```

4. **验证文件**：
```bash
ls -lh ~/.cache/whisper/
# 应该看到 base.pt 文件，大小约 142MB
```

5. **测试**：
```bash
python -c "import whisper; model = whisper.load_model('base'); print('Success!')"
```

### 方案3: 使用VPN或代理

1. **开启VPN或代理**

2. **设置代理环境变量**（如果使用代理）：
```bash
export http_proxy=http://127.0.0.1:7890
export https_proxy=http://127.0.0.1:7890
```

3. **运行程序**：
```bash
python src/core/lecture_composer.py \
    examples/fixtures/2025-10-24-15:15:15.mp3 \
    examples/fixtures/sample-photos/ \
    --export-video
```

### 方案4: 使用替代的语音识别服务（未来版本）

我们计划在未来版本中支持：
- 阿里云语音识别
- 腾讯云语音识别
- 百度语音识别
- 本地部署的Whisper

---

## 快速操作指南

### 选项A: 不使用字幕（最简单）

```bash
cd lecture-video-composer

# 导出720p视频（无字幕）
python src/core/lecture_composer.py \
    examples/fixtures/2025-10-24-15:15:15.mp3 \
    examples/fixtures/sample-photos/ \
    --export-video \
    --no-subtitles
```

输出：`output/video.mp4` （720p，无字幕）

### 选项B: 手动下载模型后使用字幕

```bash
# 1. 创建目录
mkdir -p ~/.cache/whisper

# 2. 下载模型（使用VPN或代理）
cd ~/.cache/whisper
# 使用curl或浏览器下载 base.pt

# 3. 验证文件存在
ls -lh ~/.cache/whisper/base.pt

# 4. 运行程序
cd ~/path/to/lecture-video-composer
python src/core/lecture_composer.py \
    examples/fixtures/2025-10-24-15:15:15.mp3 \
    examples/fixtures/sample-photos/ \
    --export-video
```

---

## 模型大小对比

| 模型 | 文件大小 | 准确度 | 速度 | 推荐场景 |
|------|---------|--------|------|---------|
| tiny | ~75MB | ⭐⭐ | ⭐⭐⭐⭐⭐ | 快速测试 |
| base | ~142MB | ⭐⭐⭐ | ⭐⭐⭐⭐ | 日常使用（推荐） |
| small | ~466MB | ⭐⭐⭐⭐ | ⭐⭐⭐ | 高质量要求 |
| medium | ~1.5GB | ⭐⭐⭐⭐⭐ | ⭐⭐ | 专业场景 |
| large | ~2.9GB | ⭐⭐⭐⭐⭐ | ⭐ | 最高质量 |

---

## 常见问题

### Q1: 下载的文件放在哪里？

**A**: 放在 `~/.cache/whisper/` 目录下，文件名必须是 `{模型名}.pt`

示例：
```
~/.cache/whisper/tiny.pt
~/.cache/whisper/base.pt
~/.cache/whisper/small.pt
```

### Q2: 如何确认模型下载成功？

**A**: 运行测试命令：
```bash
python -c "import whisper; whisper.load_model('base'); print('OK')"
```

如果输出 "OK" 则成功。

### Q3: 能否使用其他模型？

**A**: 可以，在命令行指定：
```bash
# 使用tiny模型（最快）
python src/core/lecture_composer.py audio.mp3 photos/ --export-video

# 使用small模型（更准确）
python src/core/lecture_composer.py audio.mp3 photos/ --export-video
```

### Q4: 模型会自动更新吗？

**A**: 不会。模型下载后会缓存，除非手动删除 `~/.cache/whisper/` 目录。

### Q5: 不使用字幕会影响视频质量吗？

**A**: 不会。字幕只是附加功能，不使用字幕不影响：
- 视频分辨率（720p）
- 视频质量
- 音频质量
- 照片切换

---

## 推荐配置

### 开发测试环境
```bash
# 不使用字幕，快速导出
--no-subtitles
```

### 生产环境
```bash
# 提前手动下载base模型
# 然后正常使用字幕功能
```

### 高质量需求
```bash
# 手动下载small或medium模型
# 在命令中指定模型
```

---

## 获取帮助

如果以上方案都无法解决问题，请：

1. 查看完整错误日志
2. 确认网络环境
3. 提交Issue: https://github.com/your-org/lecture-video-composer/issues
4. 附上错误信息和环境信息

---

**总结：最简单的方法是使用 `--no-subtitles` 跳过字幕功能！**
