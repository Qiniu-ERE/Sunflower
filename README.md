# 🌻 Sunflower - 演讲视频合成系统

> 七牛云第四届内部 Hackathon 参赛项目  
> **让每一场演讲都值得被记录、被回放、被分享**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-MVP%20Complete-success.svg)]()

---

## 📖 项目背景

在 AI 浪潮席卷全球的今天，我们正站在技术演进的关键节点。本项目响应七牛云第四届内部 Hackathon 的号召，用 AI 赋能的思维，重新定义演讲记录与回放体验。

### 💡 核心理念

**问题**：传统录屏方式占用空间大，纯音频记录缺乏视觉信息  
**方案**：音频 + 照片的轻量级方式，合成具有视觉效果的演讲回放  
**创新**：基于时间戳的智能同步，让每一帧画面与声音完美契合

---

## 🎯 Hackathon 选题

**演讲视频合成**

- 用户在听演讲时录制声音，并不定期拍摄演讲内容（如PPT、板书）
- 声音文件和照片以文件创建时间命名：`YYYY-MM-DD-hh:mm:ss.ext`
- 根据时间戳智能合成演讲视频，或实现类似视频的播放效果
- 存储优化：相比完整视频减少 70%+ 存储空间

---

## ✨ 核心特性

### 🚀 已实现 (MVP v1.0)

- ✅ **智能时间轴同步** - 基于文件名时间戳自动构建音频与照片映射
- ✅ **音频处理引擎** - 支持 MP3/WAV/M4A 等格式，自动提取元数据
- ✅ **图片处理服务** - 智能调整、裁剪、优化显示效果
- ✅ **元数据管理** - JSON 格式存储项目配置，支持重新加载
- ✅ **命令行工具** - 一键处理，简单易用
- ✅ **完整文档** - PRD、技术文档、API 文档齐全

### 🎨 技术亮点

- **O(log n) 查询算法** - 二分查找实现高效时间轴定位
- **双重容错机制** - ffprobe + mutagen 双保险音频解析
- **模块化架构** - 清晰分层，易于扩展和维护
- **类型安全** - 完整的 Python Type Hints
- **日志追踪** - 详细的处理过程记录

---

## 📁 项目结构

```
Sunflower/
├── README.md                           # 项目总览（本文件）
├── docs/
│   └── PRD_演讲视频合成系统.md         # 产品需求文档
│
└── lecture-video-composer/             # 核心项目目录
    ├── README.md                        # 项目使用指南
    ├── requirements.txt                 # Python 依赖清单
    │
    ├── src/                             # 源代码目录
    │   ├── core/                        # 核心功能模块
    │   │   ├── lecture_composer.py      # 主控制器（整合所有功能）
    │   │   ├── timeline/
    │   │   │   └── timeline_sync.py     # 时间轴同步引擎
    │   │   ├── player/                  # 播放器模块（规划中）
    │   │   └── exporter/                # 视频导出模块（规划中）
    │   │
    │   ├── services/                    # 服务层
    │   │   ├── audio/
    │   │   │   └── audio_service.py     # 音频处理服务
    │   │   ├── image/
    │   │   │   └── image_service.py     # 图片处理服务
    │   │   └── metadata/
    │   │       └── metadata_service.py  # 元数据管理服务
    │   │
    │   ├── ui/                          # 用户界面（规划中）
    │   └── utils/                       # 工具函数（规划中）
    │
    ├── docs/                            # 项目文档
    │   ├── MVP_实现文档.md              # MVP 实现细节
    │   ├── architecture/                # 架构设计文档
    │   ├── api/                         # API 接口文档
    │   ├── development/                 # 开发指南
    │   └── user-guide/                  # 用户手册
    │
    ├── examples/                        # 示例和教程
    │   ├── basic/
    │   │   ├── test_mvp.py             # MVP 测试脚本
    │   │   └── README.md               # 基础示例说明
    │   ├── fixtures/                    # 测试数据
    │   │   └── sample-photos/          # 示例照片
    │   ├── tutorials/                   # 使用教程
    │   └── advanced/                    # 高级用例
    │
    ├── tests/                           # 测试目录
    │   ├── unit/                        # 单元测试
    │   │   ├── core/                   # 核心模块测试
    │   │   ├── services/               # 服务层测试
    │   │   └── utils/                  # 工具函数测试
    │   ├── integration/                 # 集成测试
    │   ├── e2e/                        # 端到端测试
    │   └── performance/                 # 性能测试
    │
    └── tools/                           # 开发工具
```

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- FFmpeg (音频处理)
- 操作系统：macOS / Linux / Windows

### 安装步骤

```bash
# 1. 克隆项目
git clone https://github.com/Qiniu-ERE/Sunflower.git
cd Sunflower/lecture-video-composer

# 2. 安装系统依赖
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# 3. 安装 Python 依赖
pip install -r requirements.txt
```

### 使用示例

#### 方式 1: 命令行工具

```bash
# 基础使用
python src/core/lecture_composer.py \
    /path/to/audio/2025-10-24-14:30:00.mp3 \
    /path/to/photos/

# 指定输出目录和项目标题
python src/core/lecture_composer.py \
    ./fixtures/2025-10-24-14:30:00.mp3 \
    ./fixtures/photos/ \
    --output ./output/my_lecture \
    --title "高等数学第三章"
```

#### 方式 2: Python API

```python
from pathlib import Path
from core.lecture_composer import LectureComposer

# 创建合成器
composer = LectureComposer(
    audio_file=Path("2025-10-24-14:30:00.mp3"),
    photo_files=[
        Path("2025-10-24-14:32:15.jpg"),
        Path("2025-10-24-14:35:40.jpg"),
    ],
    output_dir=Path("output/my_project")
)

# 执行处理
metadata = composer.process(title="我的演讲")

# 查看摘要
print(composer.get_summary())
```

#### 方式 3: 测试脚本

```bash
# 运行交互式测试
python examples/basic/test_mvp.py
```

---

## 📝 文件命名规范

### 重要提示

所有输入文件必须严格遵循以下命名格式：

**格式**: `YYYY-MM-DD-hh:mm:ss.ext`

- 年月日用 `-` 分隔
- 时分秒用 `:` 分隔  
- 日期和时间之间用 `-` 分隔

**示例**:
```
音频: 2025-10-24-14:30:00.mp3
照片: 2025-10-24-14:32:15.jpg
     2025-10-24-14:35:40.jpg
     2025-10-24-14:38:22.jpg
```

---

## 📊 工作原理

### 核心算法流程

```
┌─────────────────┐
│  输入文件验证   │
│  - 音频文件     │
│  - 照片文件     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  时间戳解析     │
│  YYYY-MM-DD-    │
│  hh:mm:ss       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  构建时间轴     │
│  offset = t照片  │
│         - t音频  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  计算显示时长   │
│  duration[i] =  │
│  offset[i+1] -  │
│  offset[i]      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  生成元数据     │
│  JSON 格式      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  保存项目       │
│  - 音频副本     │
│  - 照片副本     │
│  - metadata.json│
└─────────────────┘
```

### 时间轴同步示例

```
音频: 2025-10-24-14:30:00.mp3 (600秒 = 10分钟)
├─ 照片1: 2025-10-24-14:32:15.jpg (偏移 135秒)
│  └─ 显示时长: 60秒
├─ 照片2: 2025-10-24-14:33:15.jpg (偏移 195秒)
│  └─ 显示时长: 60秒
├─ 照片3: 2025-10-24-14:34:15.jpg (偏移 255秒)
│  └─ 显示时长: 60秒
...
└─ 照片N: 2025-10-24-14:38:15.jpg
   └─ 显示时长: 至音频结束
```

---

## 🎯 开发路线图

### ✅ 阶段 1: MVP (已完成)
- [x] 时间轴同步引擎
- [x] 音频/图片处理服务
- [x] 元数据管理
- [x] 命令行工具
- [x] 基础文档

### 🚧 阶段 2: 基础完善版 (进行中)
- [x] 视频导出功能 (FFmpeg)
- [x] 项目加载功能
- [x] 照片编辑 (裁剪/旋转)
- [x] 单元测试覆盖
- [x] 性能优化

### 📋 阶段 3: 智能增强版
- [x] 语音转文字 (字幕生成)
- [ ] 关键帧智能识别
- [x] 照片智能增强
- [ ] 智能剪辑 (去除沉默)

### 🌟 阶段 4: 协作与分享版
- [x] Web 播放器
- [ ] 云端存储
- [ ] 分享功能
- [ ] 团队协作

---

## 📚 文档导航

### 核心文档
- [产品需求文档 (PRD)](docs/PRD_演讲视频合成系统.md) - 完整的产品设计
- [MVP 实现文档](lecture-video-composer/docs/MVP_实现文档.md) - 技术实现细节
- [项目使用指南](lecture-video-composer/README.md) - 详细使用说明

### 开发文档
- [架构设计](lecture-video-composer/docs/architecture/README.md) - 系统架构
- [API 文档](lecture-video-composer/docs/api/) - 接口说明
- [开发指南](lecture-video-composer/docs/development/) - 开发规范

### 示例教程
- [基础示例](lecture-video-composer/examples/basic/README.md) - 快速上手
- [高级用例](lecture-video-composer/examples/advanced/) - 进阶功能
- [测试脚本](lecture-video-composer/examples/basic/test_mvp.py) - 功能验证

---

## 🛠️ 技术栈

### 核心技术
- **Python 3.8+** - 主要开发语言
- **Pillow (PIL)** - 图片处理
- **FFmpeg** - 音频/视频处理
- **Mutagen** - 音频元数据提取

### 开发工具
- **Git** - 版本控制
- **pytest** - 单元测试
- **Pylint** - 代码质量检查

### 未来计划
- **React/Vue** - Web UI
- **TensorFlow.js** - AI 功能
- **Web Audio API** - 浏览器播放

---

## 🤝 贡献指南

欢迎七牛的伙伴们参与贡献！

### 贡献方式
1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

### 代码规范
- 遵循 PEP 8 Python 代码规范
- 添加完整的类型提示
