# 演讲视频合成系统 - 产品需求文档 (PRD)

## 文档版本
- **版本**: v1.0
- **日期**: 2025-10-24
- **产品经理**: Sunflower Team
- **状态**: 设计阶段

---

## 一、产品概述

### 1.1 产品背景
在教育、培训、会议等场景中，用户经常需要记录演讲内容。传统的录屏方式占用存储空间大，而纯音频记录缺乏视觉信息。本产品旨在通过音频+照片的轻量级方式，合成具有视觉效果的演讲回放体验。

### 1.2 产品定位
一个智能的演讲内容记录与回放工具，通过时间轴同步技术，将音频与照片结合，生成类似视频的演讲回放效果。

### 1.3 核心价值
- **存储优化**: 相比完整视频，音频+照片占用空间更小
- **操作简便**: 不需要连续录像，只需不定期拍照
- **回放流畅**: 根据时间轴自动同步音频和画面
- **灵活输出**: 支持实时播放或导出视频

---

## 二、需求分析

### 2.1 用户场景

#### 场景1：大学生课堂记录
张同学在上专业课时，使用手机录制老师讲课的音频，当老师在黑板上写重点内容或展示PPT时，拍摄照片。课后通过系统回放，既能听到讲解又能看到重点内容。

#### 场景2：企业培训记录
李经理参加公司培训，录制音频并拍摄培训师的关键图表和演示内容。培训后分享给缺席的同事，让他们也能获得接近现场的学习体验。

#### 场景3：会议记录
产品团队会议中，录制讨论音频并拍摄白板上的设计草图。会后生成回放视频，便于团队成员回顾讨论内容。

### 2.2 功能需求优先级

| 优先级 | 功能模块 | 说明 |
|--------|----------|------|
| P0 | 音频播放引擎 | 核心播放功能 |
| P0 | 时间轴同步机制 | 根据时间戳同步音频和照片 |
| P0 | 基础播放器UI | 播放、暂停、进度控制 |
| P1 | 照片切换效果 | 平滑过渡动画 |
| P1 | 文件导入管理 | 批量导入音频和照片 |
| P1 | 视频导出功能 | 生成标准视频文件 |
| P2 | 智能照片增强 | 自动调整亮度、对比度 |
| P2 | 字幕生成 | 语音转文字 |
| P3 | 云端存储 | 跨设备同步 |

### 2.3 非功能需求

- **性能要求**: 播放延迟 < 100ms，照片切换流畅 (60fps)
- **兼容性**: 支持主流音频格式 (MP3, WAV, M4A)，图片格式 (JPG, PNG)
- **可用性**: 界面简洁直观，操作步骤不超过3步
- **可扩展性**: 架构支持未来添加AI功能（智能剪辑、关键帧提取等）

---

## 三、技术架构设计

### 3.1 系统架构

```
┌─────────────────────────────────────────────┐
│           用户界面层 (UI Layer)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 播放控制 │  │ 时间轴UI │  │ 文件管理 │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│         业务逻辑层 (Business Layer)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 播放管理 │  │ 时间同步 │  │ 导出管理 │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│          数据服务层 (Data Layer)             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 音频解析 │  │ 图片加载 │  │ 元数据   │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────┐
│         基础设施层 (Infrastructure)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ 文件系统 │  │ 媒体编解码│  │ 渲染引擎 │  │
│  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────┘
```

### 3.2 核心模块设计

#### 3.2.1 时间轴同步引擎 (Timeline Sync Engine)

**功能**: 根据文件创建时间，建立音频和照片的时间轴映射关系

**核心算法**:
```
1. 解析文件名，提取时间戳 (YYYY-MM-DD hh:mm:ss)
2. 以音频起始时间为基准点 (t0)
3. 计算每张照片相对于基准点的时间偏移 (Δt)
4. 构建时间轴数据结构: Timeline = [(t1, photo1), (t2, photo2), ...]
5. 播放时根据当前音频时间，查找对应照片
```

**数据结构**:
```python
class TimelineItem:
    timestamp: datetime      # 绝对时间戳
    offset_seconds: float    # 相对音频开始的秒数
    resource_path: str       # 照片路径
    duration: float          # 显示持续时间

class Timeline:
    audio_start_time: datetime
    audio_duration: float
    items: List[TimelineItem]
```

#### 3.2.2 播放控制器 (Playback Controller)

**功能**: 协调音频播放和照片切换

**工作流程**:
```
1. 初始化音频播放器
2. 加载时间轴数据
3. 启动播放循环:
   - 获取当前音频播放位置 (current_time)
   - 查询时间轴，确定当前应显示的照片
   - 检测是否需要切换照片
   - 触发照片切换动画
   - 更新UI显示
```

**性能优化**:
- 照片预加载机制 (预加载下一张照片)
- 二分查找优化时间轴查询
- 异步加载避免UI阻塞

#### 3.2.3 视频导出模块 (Video Exporter)

**功能**: 将音频+照片序列合成为标准视频文件

**实现方案**:
- 使用 FFmpeg 进行视频编码
- 照片转换为视频帧，设置持续时间
- 音频作为视频的音轨
- 支持自定义分辨率和码率

---

## 四、详细设计

### 4.1 文件命名规范

**输入文件要求**:
- 音频文件: `YYYY-MM-DD hh:mm:ss.mp3` (例: `2025-10-24 14:30:00.mp3`)
- 照片文件: `YYYY-MM-DD hh:mm:ss.jpg` (例: `2025-10-24 14:32:15.jpg`)

**时间解析逻辑**:
```python
def parse_filename_timestamp(filename: str) -> datetime:
    # 提取文件名中的时间部分（去除扩展名）
    name_without_ext = filename.rsplit('.', 1)[0]
    # 解析为 datetime 对象
    return datetime.strptime(name_without_ext, "%Y-%m-%d %H:%M:%S")
```

### 4.2 播放器功能规格

#### 基础控制
- **播放/暂停**: 空格键或点击播放按钮
- **进度控制**: 拖动时间轴跳转
- **音量调节**: 音量滑块，范围 0-100%
- **倍速播放**: 支持 0.5x, 0.75x, 1x, 1.25x, 1.5x, 2x

#### 时间轴显示
```
[==================|====|=======|===========]
0:00              2:15 3:42    6:18      10:00
                   📷   📷       📷
```
- 蓝色进度条表示当前播放位置
- 标记点表示照片拍摄时间点
- 鼠标悬停显示时间戳和照片缩略图

#### 照片切换效果
- **默认**: 淡入淡出 (Fade), 持续时间 300ms
- **可选**: 滑动、缩放、无动画

### 4.3 照片显示策略

**场景1: 照片密集**
- 如果两张照片间隔 < 5秒，直接切换
- 示例: 用户连续拍摄板书

**场景2: 照片稀疏**
- 如果两张照片间隔 > 30秒，保持上一张照片直到下一张
- 示例: 老师长时间讲解一页PPT

**场景3: 开始前/结束后**
- 音频开始前：显示第一张照片或占位图
- 音频结束后：保持最后一张照片

### 4.4 数据存储方案

**项目文件结构**:
```
lecture_project/
├── metadata.json          # 项目元数据
├── audio/
│   └── 2025-10-24 14:30:00.mp3
└── photos/
    ├── 2025-10-24 14:32:15.jpg
    ├── 2025-10-24 14:35:40.jpg
    └── 2025-10-24 14:38:22.jpg
```

**metadata.json 格式**:
```json
{
  "version": "1.0",
  "title": "高等数学第三章",
  "created_at": "2025-10-24T14:30:00+08:00",
  "audio": {
    "filename": "2025-10-24 14:30:00.mp3",
    "duration": 3600,
    "format": "mp3",
    "sample_rate": 44100
  },
  "timeline": [
    {
      "timestamp": "2025-10-24T14:32:15+08:00",
      "offset": 135,
      "photo": "2025-10-24 14:32:15.jpg",
      "duration": 225
    },
    {
      "timestamp": "2025-10-24T14:35:40+08:00",
      "offset": 340,
      "photo": "2025-10-24 14:35:40.jpg",
      "duration": 162
    }
  ],
  "settings": {
    "transition_effect": "fade",
    "transition_duration": 300
  }
}
```

---

## 五、技术实现方案

### 5.1 技术栈选型

#### 方案A: Web应用 (推荐用于MVP)
- **前端**: HTML5 + JavaScript (或 React/Vue)
- **音频**: Web Audio API
- **图片**: Canvas API 或 DOM
- **优点**: 跨平台、开发快速、易于分发
- **缺点**: 性能受浏览器限制

#### 方案B: 桌面应用
- **框架**: Electron (Web技术) 或 Qt (C++)
- **音频**: 原生音频库
- **视频导出**: FFmpeg
- **优点**: 性能更好、功能更完整
- **缺点**: 开发周期长、需要分平台打包

#### 方案C: 移动应用
- **iOS**: Swift + AVFoundation
- **Android**: Kotlin + MediaPlayer
- **优点**: 集成拍照和录音功能
- **缺点**: 需要两套代码

**建议**: 先实现方案A的Web版本作为MVP，验证产品可行性后再考虑桌面或移动版本。

### 5.2 核心代码示例 (Web版)

#### 时间轴解析
```javascript
class LectureTimeline {
  constructor(audioFile, photoFiles) {
    this.audioStartTime = this.parseTimestamp(audioFile.name);
    this.photos = this.buildTimeline(photoFiles);
  }

  parseTimestamp(filename) {
    // "2025-10-24 14:30:00.mp3" -> Date对象
    const timeStr = filename.replace(/\.[^.]+$/, '');
    return new Date(timeStr.replace(' ', 'T'));
  }

  buildTimeline(photoFiles) {
    const timeline = photoFiles.map(file => {
      const photoTime = this.parseTimestamp(file.name);
      const offsetSeconds = (photoTime - this.audioStartTime) / 1000;
      return {
        offset: offsetSeconds,
        file: file,
        url: URL.createObjectURL(file)
      };
    });

    // 按时间排序
    timeline.sort((a, b) => a.offset - b.offset);

    // 计算每张照片的显示时长
    for (let i = 0; i < timeline.length - 1; i++) {
      timeline[i].duration = timeline[i + 1].offset - timeline[i].offset;
    }
    
    // 最后一张照片显示到音频结束
    if (timeline.length > 0) {
      timeline[timeline.length - 1].duration = Infinity;
    }

    return timeline;
  }

  getCurrentPhoto(currentTime) {
    // 二分查找当前时间对应的照片
    for (let i = this.photos.length - 1; i >= 0; i--) {
      if (currentTime >= this.photos[i].offset) {
        return this.photos[i];
      }
    }
    return null;
  }
}
```

#### 播放控制器
```javascript
class LecturePlayer {
  constructor(audioElement, imageElement, timeline) {
    this.audio = audioElement;
    this.image = imageElement;
    this.timeline = timeline;
    this.currentPhoto = null;

    this.setupEventListeners();
  }

  setupEventListeners() {
    this.audio.addEventListener('timeupdate', () => {
      this.updateImage();
    });
  }

  updateImage() {
    const currentTime = this.audio.currentTime;
    const photo = this.timeline.getCurrentPhoto(currentTime);

    if (photo && photo !== this.currentPhoto) {
      this.transitionToPhoto(photo);
      this.currentPhoto = photo;
    }
  }

  transitionToPhoto(photo) {
    // 淡入淡出效果
    this.image.style.opacity = '0';
    
    setTimeout(() => {
      this.image.src = photo.url;
      this.image.style.opacity = '1';
    }, 300);
  }

  play() {
    this.audio.play();
  }

  pause() {
    this.audio.pause();
  }

  seek(time) {
    this.audio.currentTime = time;
    this.updateImage();
  }
}
```

#### 视频导出 (需要后端支持)
```python
# 使用 FFmpeg 导出视频
import subprocess
import os

def export_video(audio_path, timeline, output_path, width=1280, height=720):
    """
    将音频和照片序列合成视频
    """
    # 1. 创建临时目录
    temp_dir = "temp_frames"
    os.makedirs(temp_dir, exist_ok=True)
    
    # 2. 根据时间轴生成视频帧序列
    frame_rate = 30
    frame_files = []
    
    for i, item in enumerate(timeline):
        photo_path = item['photo']
        duration = item['duration']
        frame_count = int(duration * frame_rate)
        
        # 为每张照片生成对应数量的帧
        for j in range(frame_count):
            frame_filename = f"{temp_dir}/frame_{len(frame_files):06d}.jpg"
            # 复制或链接照片
            os.system(f"cp {photo_path} {frame_filename}")
            frame_files.append(frame_filename)
    
    # 3. 使用 FFmpeg 合成视频
    ffmpeg_cmd = [
        "ffmpeg",
        "-framerate", str(frame_rate),
        "-i", f"{temp_dir}/frame_%06d.jpg",
        "-i", audio_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_path
    ]
    
    subprocess.run(ffmpeg_cmd, check=True)
    
    # 4. 清理临时文件
    os.system(f"rm -rf {temp_dir}")
```

### 5.3 前端界面设计

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>演讲回放器</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            color: #fff;
        }
        
        .player-container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .video-area {
            position: relative;
            background: #000;
            border-radius: 8px;
            overflow: hidden;
            aspect-ratio: 16/9;
        }
        
        .photo-display {
            width: 100%;
            height: 100%;
            object-fit: contain;
            transition: opacity 0.3s ease;
        }
        
        .controls {
            margin-top: 20px;
            padding: 20px;
            background: #2a2a2a;
            border-radius: 8px;
        }
        
        .timeline {
            width: 100%;
            height: 40px;
            background: #444;
            border-radius: 4px;
            position: relative;
            cursor: pointer;
        }
        
        .timeline-progress {
            height: 100%;
            background: #1e90ff;
            border-radius: 4px;
            transition: width 0.1s linear;
        }
        
        .photo-markers {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
        }
        
        .photo-marker {
            position: absolute;
            width: 3px;
            height: 100%;
            background: #ff6b6b;
            cursor: pointer;
        }
        
        .playback-controls {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-top: 15px;
        }
        
        .btn {
            padding: 10px 20px;
            background: #1e90ff;
            border: none;
            border-radius: 4px;
            color: white;
            cursor: pointer;
            font-size: 14px;
        }
        
        .btn:hover {
            background: #4169e1;
        }
        
        .time-display {
            font-size: 14px;
            color: #aaa;
        }
    </style>
</head>
<body>
    <div class="player-container">
        <h1>演讲回放器</h1>
        
        <div class="video-area">
            <img id="photoDisplay" class="photo-display" src="" alt="演讲内容">
        </div>
        
        <div class="controls">
            <div class="timeline" id="timeline">
                <div class="timeline-progress" id="progress"></div>
                <div class="photo-markers" id="markers"></div>
            </div>
            
            <div class="playback-controls">
                <button class="btn" id="playBtn">播放</button>
                <button class="btn" id="pauseBtn">暂停</button>
                <span class="time-display">
                    <span id="currentTime">00:00</span> / 
                    <span id="duration">00:00</span>
                </span>
                <button class="btn" id="exportBtn">导出视频</button>
            </div>
        </div>
        
        <audio id="audioPlayer" style="display: none;"></audio>
    </div>
    
    <script src="lecture-player.js"></script>
</body>
</html>
```

---

## 六、多阶段演进规划

> **基于AI辅助编码**：利用现代AI编码工具（如GitHub Copilot、Cursor、Claude等），开发效率可提升3-5倍，因此将传统周期压缩为天级别的敏捷迭代。

### 阶段1: MVP (最小可行产品) - 1-2天
**目标**: 验证核心概念，实现基础播放功能

**功能范围**:
- ✅ 文件导入 (拖拽音频和照片文件)
- ✅ 时间轴自动解析
- ✅ 基础播放控制 (播放、暂停、进度条)
- ✅ 照片自动切换 (淡入淡出效果)
- ✅ 简单的UI界面

**技术实现**: Web应用 (纯前端)
**AI辅助**: 使用AI生成核心算法、UI组件模板

**验证指标**:
- 用户能否成功导入文件并播放
- 照片切换是否流畅准确
- 用户反馈满意度 > 7/10

**开发分工**:
- Day 1: 时间轴引擎 + 基础播放器
- Day 2: UI界面 + 集成测试

### 阶段2: 基础完善版 - 2-3天
**目标**: 提升用户体验，增加导出功能

**新增功能**:
- ✅ 视频导出 (生成MP4文件)
- ✅ 项目保存/加载
- ✅ 时间轴可视化 (显示照片标记点)
- ✅ 照片编辑 (裁剪、旋转)
- ✅ 音量控制、倍速播放
- ✅ 键盘快捷键

**技术优化**:
- 照片预加载机制
- 性能监控和优化
- 错误处理和提示

**AI辅助**: 使用AI优化性能瓶颈、生成测试用例

**开发分工**:
- Day 1: 视频导出功能 + 项目存储
- Day 2: 时间轴UI + 照片编辑
- Day 3: 性能优化 + 测试完善

### 阶段3: 智能增强版 - 2-3天
**目标**: 引入AI能力，提升智能化水平

**新增功能**:
- ✅ 语音转文字 (自动生成字幕)
- ✅ 关键帧智能识别 (自动标记重要内容)
- ✅ 照片智能增强 (去模糊、提亮)
- ✅ 智能剪辑 (自动去除沉默段)
- ✅ 多音轨支持 (背景音乐)

**AI技术**:
- 语音识别: Web Speech API 或云端API
- 图像处理: TensorFlow.js 或云端服务
- 关键帧检测: 音量变化 + 时间间隔分析

**AI辅助**: 直接使用AI API集成、AI生成图像处理算法

**开发分工**:
- Day 1: 语音转文字集成
- Day 2: 关键帧识别 + 智能剪辑
- Day 3: 照片增强 + 测试优化

### 阶段4: 协作与分享版 - 2-3天
**目标**: 支持团队协作和内容分享

**新增功能**:
- ✅ 云端存储和同步
- ✅ 多设备支持 (Web + 移动端响应式)
- ✅ 分享功能 (生成分享链接)
- ✅ 评论和标注
- ✅ 团队空间

**架构升级**:
- 后端服务搭建 (使用Serverless加速)
- 用户认证系统 (OAuth集成)
- 云存储集成 (AWS S3 或 七牛云)

**AI辅助**: AI生成后端API、数据库模型设计

**开发分工**:
- Day 1: 后端API + 数据库设计
- Day 2: 云存储集成 + 用户认证
- Day 3: 分享功能 + 团队协作

### 阶段5: 平台化 - 3天
**目标**: 打造完整的演讲记录生态系统

**新增功能**:
- ✅ 实时录制功能 (集成录音和拍照)
- ✅ 直播模式 (边录边播)
- ✅ AI助手 (自动问答、内容总结)
- ✅ 知识图谱 (关联相关演讲)
- ✅ 开放API (第三方集成)

**商业化**:
- 免费版 (基础功能 + 广告)
- 专业版 (高级功能 + 云存储)
- 企业版 (团队协作 + 定制化)

**AI辅助**: AI生成API文档、SDK、营销文案

**开发分工**:
- Day 1: 实时录制 + 直播功能
- Day 2: AI助手集成 + 知识图谱
- Day 3: 开放API + 文档 + 上线准备

---

### 总开发周期：10-14天

**AI辅助开发的关键优势**:
1. **代码生成**: AI可快速生成样板代码、工具函数
2. **调试加速**: AI辅助排查bug，提供解决方案
3. **文档自动化**: AI生成API文档、注释
4. **测试用例**: AI生成单元测试和集成测试
5. **性能优化**: AI建议优化方案

---

## 七、技术难点与解决方案

### 7.1 时间同步精度

**问题**: 文件系统时间戳精度可能不够，导致同步不准确

**解决方案**:
1. 允许用户手动微调照片时间点 (±10秒)
2. 提供时间轴编辑器，可拖动照片标记点
3. 自动检测音量变化，辅助判断照片切换时机

### 7.2 照片加载性能

**问题**: 大量高清照片导致加载缓慢

**解决方案**:
1. 图片压缩: 自动生成缩略图
2. 懒加载: 只加载当前和下一张照片
3. 渐进式渲染: 先显示低清版，再切换高清版
4. Web Worker: 异步处理图片加载

### 7.3 视频导出质量

**问题**: 照片静态显示可能显得生硬

**解决方案**:
1. Ken Burns效果: 缓慢缩放和平移照片
2. 智能构图: 自动裁剪照片至16:9
3. 过渡动画: 提供多种切换特效
4. 动态调整: 根据照片内容调整显示时长

### 7.4 音频延迟

**问题**: Web Audio API 可能存在播放延迟

**解决方案**:
1. 预加载音频缓冲区
2. 使用 AudioContext 的精确时间控制
3. 音视频同步算法: 定期校准时间偏差

---

## 八、测试计划

### 8.1 单元测试
- 时间戳解析函数
- 时间轴构建逻辑
- 照片查找算法

### 8.2 集成测试
- 音频播放与照片切换同步
- 进度条拖动功能
- 视频导出完整流程

### 8.3 性能测试
- 100张照片场景下的加载速度
- 1小时音频的播放流畅度
- 内存占用监控

### 8.4 用户测试
- 5-10名目标用户试用
- 收集可用性反馈
- A/B测试不同UI设计

---

## 九、风险评估

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|----------|
| 文件命名不规范 | 高 | 中 | 提供文件名批量修正工具 |
| 照片拍摄时间不准 | 中 | 高 | 提供手动校准功能 |
| 音频格式不兼容 | 中 | 低 | 支持主流格式，提供转换工具 |
| 浏览器兼容性问题 | 中 | 中 | 降级方案，提示用户使用Chrome |
| 性能不达标 | 高 | 低 | 持续优化，必要时切换技术方案 |

---

## 十、成功指标 (KPI)

### 产品指标
- **用户留存率**: DAU/MAU > 40%
- **功能使用率**: 导出功能使用率 > 30%
- **用户满意度**: NPS > 50

### 技术指标
- **播放流畅度**: 卡顿率 < 1%
- **加载速度**: 首屏加载 < 3秒
- **导出成功率**: > 95%

### 业务指标
- **用户增长**: 月增长率 > 20%
- **付费转化**: 免费转付费 > 5%
- **分享传播**: 病毒系数 K > 0.3

---

## 十一、开发排期

| 阶段 | 时间 | 负责人 | 交付物 |
|------|------|--------|--------|
| 需求评审 | Week 1 | PM | PRD文档 |
| 技术方案设计 | Week 1-2 | Tech Lead | 技术设计文档 |
| MVP开发 | Week 2-5 | 前端开发 | 可演示原型 |
| 内部测试 | Week 5-6 | QA | 测试报告 |
| Beta发布 | Week 6 | 运营 | 100名种子用户 |
| 迭代优化 | Week 7-8 | 全团队 | V1.0正式版 |

---

## 十二、附录

### A. 竞品分析

| 产品 | 优势 | 劣势 | 差异化 |
|------|------|------|--------|
| 传统录屏软件 | 画面完整 | 文件大、占资源 | 我们更轻量 |
| 纯音频记录 | 简单便捷 | 缺乏视觉 | 我们有画面 |
| 自动录课系统 | 专业功能多 | 价格贵、复杂 | 我们更易用 |

### B. 技术参考

- [Web Audio API Documentation](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [Canvas API Guide](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)

### C. 设计规范

- 主色调: #1e90ff (道奇蓝)
- 字体: 系统默认 Sans-serif
- 圆角: 4px (小组件) / 8px (大容器)
- 动画时长: 300ms (过渡) / 150ms (交互)

---

## 文档审批

| 角色 | 姓名 | 审批日期 | 状态 |
|------|------|----------|------|
| 产品经理 | - | - | 待审批 |
| 技术负责人 | - | - | 待审批 |
| 设计负责人 | - | - | 待审批 |
| 项目经理 | - | - | 待审批 |

---

**文档结束**
