# MVP 核心功能实现文档

> **版本**: v1.0  
> **日期**: 2025-10-24  
> **状态**: 已完成  
> **实现语言**: Python 3.8+

---

## 一、实现概述

本文档记录了演讲视频合成系统 MVP（最小可行产品）核心功能的实现细节。MVP 专注于 P0 优先级功能：

✅ **时间轴同步引擎** - 根据文件时间戳构建音频和照片的时间轴映射  
✅ **音频处理服务** - 提取音频元数据（时长、格式、采样率等）  
✅ **图片处理服务** - 提取图片元数据（尺寸、格式等）  
✅ **元数据管理服务** - 管理项目元数据和时间轴信息  
✅ **主控制器** - 整合所有核心功能的编排器

---

## 二、项目结构

```
lecture-video-composer/
├── requirements.txt              # Python 依赖
├── src/
│   ├── core/
│   │   ├── lecture_composer.py  # 主控制器
│   │   └── timeline/
│   │       └── timeline_sync.py # 时间轴同步引擎
│   └── services/
│       ├── audio/
│       │   └── audio_service.py # 音频处理服务
│       ├── image/
│       │   └── image_service.py # 图片处理服务
│       └── metadata/
│           └── metadata_service.py # 元数据管理
└── examples/
    ├── basic/
    │   └── test_mvp.py          # MVP 测试脚本
    └── fixtures/                # 测试文件目录（需手动添加）
```

---

## 三、核心模块实现

### 3.1 时间轴同步引擎 (timeline_sync.py)

**位置**: `src/core/timeline/timeline_sync.py`

#### 核心类

##### TimelineItem
表示时间轴上的单个项（照片）

```python
class TimelineItem:
    timestamp: datetime       # 绝对时间戳
    offset_seconds: float     # 相对音频开始的秒数
    file_path: Path          # 照片文件路径
    duration: float          # 显示持续时间（秒）
```

##### Timeline
时间轴管理器，包含所有时间轴项

```python
class Timeline:
    audio_start_time: datetime  # 音频开始时间
    audio_duration: float       # 音频总时长
    items: List[TimelineItem]   # 时间轴项列表
```

**关键方法**:
- `get_current_item(current_time)` - 根据播放时间查找当前应显示的照片
- `calculate_durations()` - 计算每张照片的显示时长

##### TimelineSync
时间轴同步引擎

**关键方法**:
- `parse_timestamp(filename)` - 从文件名解析时间戳
- `build_timeline(audio_file, photo_files, audio_duration)` - 构建时间轴
- `validate_files(audio_file, photo_files)` - 验证文件名格式

**算法逻辑**:
```python
# 1. 解析音频开始时间
audio_start_time = parse_timestamp("2025-10-24-14:30:00.mp3")

# 2. 计算每张照片的时间偏移
for photo in photos:
    photo_time = parse_timestamp(photo.name)
    offset = (photo_time - audio_start_time).total_seconds()
    
# 3. 计算每张照片的显示时长
duration[i] = offset[i+1] - offset[i]
```

---

### 3.2 音频处理服务 (audio_service.py)

**位置**: `src/services/audio/audio_service.py`

#### 核心类

##### AudioMetadata
音频元数据容器

```python
class AudioMetadata:
    file_path: Path
    duration: float        # 持续时间（秒）
    sample_rate: int       # 采样率（Hz）
    channels: int          # 声道数
    codec: str            # 编解码器
    bitrate: int          # 比特率（可选）
```

##### AudioService
音频处理服务

**关键方法**:
- `get_metadata(audio_file)` - 提取音频元数据
- `validate_audio_file(audio_file)` - 验证音频文件
- `get_duration(audio_file)` - 快捷获取音频时长

**实现策略**:
1. **优先使用 ffprobe** (系统命令，需安装 ffmpeg)
2. **降级使用 mutagen** (Python 库，作为备选)

**支持格式**: MP3, WAV, M4A, AAC, OGG, FLAC

---

### 3.3 图片处理服务 (image_service.py)

**位置**: `src/services/image/image_service.py`

#### 核心类

##### ImageMetadata
图片元数据容器

```python
class ImageMetadata:
    file_path: Path
    width: int
    height: int
    format: str
    file_size: int
    mode: str             # 色彩模式
    aspect_ratio: float   # 宽高比（计算属性）
```

##### ImageService
图片处理服务

**关键方法**:
- `get_metadata(image_file)` - 提取图片元数据
- `validate_image_file(image_file)` - 验证图片文件
- `get_dimensions(image_file)` - 快捷获取图片尺寸
- `resize_image(...)` - 调整图片大小
- `crop_to_aspect_ratio(...)` - 裁剪到指定宽高比

**支持格式**: JPG, JPEG, PNG, GIF, BMP, WEBP

**使用库**: Pillow (PIL)

---

### 3.4 元数据管理服务 (metadata_service.py)

**位置**: `src/services/metadata/metadata_service.py`

#### 核心类

##### ProjectMetadata
项目元数据

```python
class ProjectMetadata:
    version: str = "1.0"
    title: str
    created_at: datetime
    audio_info: dict
    timeline_items: list
    settings: dict
```

**元数据格式** (JSON):
```json
{
  "version": "1.0",
  "title": "演讲项目标题",
  "created_at": "2025-10-24T14:30:00+08:00",
  "audio": {
    "filename": "2025-10-24-14:30:00.mp3",
    "duration": 600,
    "format": "mp3",
    "sample_rate": 44100
  },
  "timeline": [
    {
      "timestamp": "2025-10-24T14:32:15+08:00",
      "offset": 135,
      "photo": "2025-10-24-14:32:15.jpg",
      "duration": 60
    }
  ],
  "settings": {
    "transition_effect": "fade",
    "transition_duration": 300,
    "video_resolution": "1920x1080",
    "fps": 30
  }
}
```

##### MetadataService
元数据管理服务

**关键方法**:
- `create_project_metadata(...)` - 创建项目元数据
- `save_metadata(metadata, output_dir)` - 保存元数据到文件
- `load_metadata(project_dir)` - 从文件加载元数据
- `validate_metadata(metadata)` - 验证元数据完整性

---

### 3.5 主控制器 (lecture_composer.py)

**位置**: `src/core/lecture_composer.py`

#### 核心类

##### LectureComposer
演讲视频合成器主类，整合所有核心功能

**初始化参数**:
```python
composer = LectureComposer(
    audio_file=Path("audio.mp3"),
    photo_files=[Path("photo1.jpg"), ...],
    output_dir=Path("output")
)
```

**工作流程**:
```python
# 完整处理流程
metadata = composer.process(title="项目标题", save=True)

# 或分步执行
composer.validate_inputs()      # 1. 验证输入
composer.extract_metadata()     # 2. 提取元数据
composer.build_timeline()       # 3. 构建时间轴
composer.create_project_metadata() # 4. 创建项目元数据
composer.save_project()         # 5. 保存项目
```

**输出结构**:
```
output/
├── metadata.json              # 项目元数据
├── audio/
│   └── 2025-10-24-14:30:00.mp3
└── photos/
    ├── 2025-10-24-14:32:15.jpg
    ├── 2025-10-24-14:35:40.jpg
    └── ...
```

---

## 四、使用指南

### 4.1 环境准备

#### 系统依赖

**macOS**:
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt-get install ffmpeg
```

**Windows**:
下载并安装 FFmpeg: https://ffmpeg.org/download.html

#### Python 依赖

```bash
# 安装依赖
cd lecture-video-composer
pip install -r requirements.txt
```

**依赖列表**:
- `Pillow >= 10.0.0` - 图片处理
- `mutagen >= 1.47.0` - 音频元数据提取（备选）
- `pytest >= 7.4.0` - 单元测试

---

### 4.2 文件准备

#### 文件命名规范

**音频文件**:
```
格式: YYYY-MM-DD-hh:mm:ss.mp3
示例: 2025-10-24-14:30:00.mp3
```

**照片文件**:
```
格式: YYYY-MM-DD-hh:mm:ss.jpg
示例: 2025-10-24-14:32:15.jpg
```

#### 示例文件名生成

对于10分钟的音频和10张照片：

```python
# 音频 (基准时间)
2025-10-24-14:30:00.mp3

# 照片 (均匀分布在10分钟内)
2025-10-24-14:32:15.jpg  # 偏移 135秒 (2.25分钟)
2025-10-24-14:33:15.jpg  # 偏移 195秒 (3.25分钟)
2025-10-24-14:34:15.jpg  # 偏移 255秒 (4.25分钟)
2025-10-24-14:35:15.jpg  # 偏移 315秒 (5.25分钟)
2025-10-24-14:36:15.jpg  # 偏移 375秒 (6.25分钟)
2025-10-24-14:37:15.jpg  # 偏移 435秒 (7.25分钟)
2025-10-24-14:38:15.jpg  # 偏移 495秒 (8.25分钟)
2025-10-24-14:39:15.jpg  # 偏移 555秒 (9.25分钟)
2025-10-24-14:40:15.jpg  # 偏移 615秒 (10.25分钟)
2025-10-24-14:41:15.jpg  # 偏移 675秒 (11.25分钟) - 超出范围会被忽略
```

---

### 4.3 使用方式

#### 方式 1: 命令行工具

```bash
cd lecture-video-composer

# 基本使用
python src/core/lecture_composer.py \
    /path/to/audio.mp3 \
    /path/to/photos/

# 指定输出目录和标题
python src/core/lecture_composer.py \
    /path/to/audio.mp3 \
    /path/to/photos/ \
    --output /path/to/output \
    --title "高等数学第三章"

# 不保存文件（仅测试）
python src/core/lecture_composer.py \
    /path/to/audio.mp3 \
    /path/to/photos/ \
    --no-save
```

#### 方式 2: 测试脚本

```bash
cd lecture-video-composer

# 运行测试脚本
python examples/basic/test_mvp.py
```

测试脚本功能：
1. 显示文件命名规范
2. 测试时间戳解析
3. 运行完整工作流程（需准备测试文件）

#### 方式 3: Python API

```python
from pathlib import Path
from core.lecture_composer import LectureComposer

# 准备文件路径
audio_file = Path("examples/fixtures/2025-10-24-14:30:00.mp3")
photo_files = sorted(Path("examples/fixtures").glob("*.jpg"))

# 创建合成器
composer = LectureComposer(
    audio_file=audio_file,
    photo_files=photo_files,
    output_dir=Path("examples/output/my_project")
)

# 执行处理
metadata = composer.process(title="我的演讲")

# 查看摘要
print(composer.get_summary())

# 查看元数据
print(metadata.to_json())
```

---

## 五、输出说明

### 5.1 项目目录结构

```
output/
├── metadata.json              # 项目元数据文件
├── audio/
│   └── 2025-10-24-14:30:00.mp3  # 音频文件副本
└── photos/
    ├── 2025-10-24-14:32:15.jpg  # 照片文件副本
    ├── 2025-10-24-14:35:40.jpg
    └── ...
```

### 5.2 元数据文件详解

**metadata.json** 包含：
- 项目基本信息（标题、创建时间）
- 音频信息（文件名、时长、格式）
- 时间轴信息（每张照片的时间点和显示时长）
- 项目设置（过渡效果、分辨率等）

此文件可用于：
1. 重新加载项目
2. 导出视频时的配置
3. 播放器的时间同步

---

## 六、技术特性

### 6.1 性能优化

✅ **二分查找算法** - 时间轴查询 O(log n) 复杂度  
✅ **懒加载策略** - 仅在需要时读取文件元数据  
✅ **异常处理** - 完善的错误处理和回退机制  
✅ **日志记录** - 详细的处理过程日志

### 6.2 容错机制

✅ **文件验证** - 验证音频和图片文件的有效性  
✅ **格式检查** - 验证文件名时间戳格式  
✅ **边界处理** - 处理照片在音频时间范围外的情况  
✅ **降级方案** - ffprobe 失败时使用 Python 库

### 6.3 扩展性

✅ **模块化设计** - 各模块独立，易于扩展  
✅ **接口清晰** - 提供明确的 API 接口  
✅ **配置化** - 关键参数可配置  
✅ **插件友好** - 易于添加新的处理服务

---

## 七、开发计划

### 已完成 ✅

- [x] 时间轴同步引擎
- [x] 音频处理服务
- [x] 图片处理服务
- [x] 元数据管理服务
- [x] 主控制器实现
- [x] 命令行工具
- [x] 测试脚本
- [x] 基础文档

### 下一步计划 📋

#### 阶段 2: 基础完善版 (2-3天)
- [ ] 视频导出功能（使用 FFmpeg）
- [ ] 项目加载功能
- [ ] 照片编辑功能（裁剪、旋转）
- [ ] 单元测试覆盖
- [ ] 性能基准测试

#### 阶段 3: 智能增强版 (2-3天)
- [ ] 语音转文字（字幕生成）
- [ ] 关键帧智能识别
- [ ] 照片智能增强
- [ ] 智能剪辑（去除沉默）

---

## 八、常见问题

### Q1: ffprobe 警告信息

**问题**: `WARNING: ffprobe failed, trying fallback method`

**说明**: 
- 这是一个**警告**，不是错误！系统会自动降级使用 Python mutagen 库
- MVP 已实现**双重容错机制**：优先使用 ffprobe，失败则使用 mutagen
- 功能完全正常，只是使用了备选方案

**关于 pip install ffprobe**:
- `pip install ffprobe` 安装的只是一个 Python 包装器，不是真正的 ffprobe 工具
- 真正的 `ffprobe` 是 FFmpeg 项目的可执行文件，需要单独安装

**完全解决方案（可选）**:
```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt-get install ffmpeg

# 验证安装
ffprobe -version
```

**注意**: macOS 15 (Sequoia) 预发布版本可能遇到 brew 问题，但不影响 MVP 功能

### Q2: PIL/Pillow 导入错误

**问题**: `ModuleNotFoundError: No module named 'PIL'`

**解决**:
```bash
pip install Pillow
```

### Q3: 文件名格式错误

**问题**: `ValueError: Invalid filename format`

**解决**: 确保文件名严格遵循格式 `YYYY-MM-DD-hh:mm:ss.ext`
- 年月日用 `-` 分隔
- 时分秒用 `:` 分隔
- 日期和时间之间有空格
- 示例: `2025-10-24-14:30:00.mp3`

### Q4: 照片未出现在时间轴

**问题**: 照片文件存在但未被添加到时间轴

**原因**: 照片时间戳超出音频时间范围

**解决**: 确保照片的时间戳在音频开始和结束时间之间

---

## 九、贡献指南

### 代码风格

- 遵循 PEP 8 Python 代码规范
- 使用类型提示 (Type Hints)
- 添加详细的文档字符串 (Docstrings)
- 保持函数简洁，单一职责

### 提交规范

```
feat: 添加新功能
fix: 修复bug
docs: 更新文档
refactor: 重构代码
test: 添加测试
perf: 性能优化
```

---

## 十、联系方式

- **项目**: Sunflower - Lecture Video Composer
- **维护团队**: Sunflower Team
- **文档更新**: 2025-10-24
- **版本**: MVP v1.0

---

**文档结束**
