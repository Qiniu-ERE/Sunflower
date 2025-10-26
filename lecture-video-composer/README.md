# 演讲视频合成系统

> 智能的演讲内容记录与回放工具，将音频与照片通过时间轴同步，生成流畅的演讲视频

[![Version](https://img.shields.io/badge/version-2.2-blue.svg)](https://github.com/Qiniu-ERE/Sunflower)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-orange.svg)](./LICENSE)

---

## ✨ 核心特性

- 🎯 **轻量化存储** - 相比传统录屏节省 80%+ 存储空间
- 🚀 **操作简便** - 只需录音+拍照，无需连续录像
- ⚡ **实时播放** - 基于时间轴的音画自动同步
- 🎬 **智能字幕** - AI 语音识别自动生成字幕
- 📦 **视频导出** - 支持 720p/1080p MP4 输出

---

## 🎬 效果展示

<!-- 演示视频 -->
### 📹 演示视频

> 待添加：系统操作演示视频

![Demo Video Placeholder](./docs/assets/demo-video-placeholder.png)

<!-- 界面截图 -->
### 🖼️ 界面预览

<table>
  <tr>
    <td><img src="./docs/assets/screenshot-upload.png" alt="文件上传界面" /><br/><center>文件上传</center></td>
    <td><img src="./docs/assets/screenshot-projects.png" alt="项目管理界面" /><br/><center>项目管理</center></td>
  </tr>
  <tr>
    <td><img src="./docs/assets/screenshot-player.png" alt="播放器界面" /><br/><center>实时播放</center></td>
    <td><img src="./docs/assets/screenshot-timeline.png" alt="时间轴界面" /><br/><center>时间轴控制</center></td>
  </tr>
</table>

> 提示：截图将在完成 UI 调优后添加

---

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 现代浏览器（Chrome/Firefox/Safari）

### 安装运行

```bash
# 1. 克隆项目
git clone https://github.com/Qiniu-ERE/Sunflower.git
cd Sunflower/lecture-video-composer

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 Web 服务
python run_web.py

# 4. 访问应用
# 浏览器打开：http://127.0.0.1:5000
```

### 基本使用

1. **上传文件** - 拖拽音频（MP3/WAV）和照片（JPG/PNG）到上传区
2. **创建项目** - 系统自动解析时间戳并生成时间轴
3. **播放预览** - 实时同步播放音频和照片切换
4. **导出视频** - 配置参数并导出 MP4 视频（开发中）

> **文件命名规范**：`YYYY-MM-DD-HH:MM:SS.扩展名`（如：`2025-10-24-15:30:45.jpg`）

---

## 📦 项目结构

```
lecture-video-composer/
├── src/
│   ├── core/                    # 核心引擎
│   │   ├── lecture_composer.py  # 主合成器
│   │   ├── player/              # 播放器模块 ✅
│   │   └── timeline/            # 时间轴引擎 ✅
│   ├── web/                     # Web 应用 ✅
│   │   ├── app.py               # Flask 主应用
│   │   ├── api/                 # REST API
│   │   ├── static/              # 前端资源
│   │   └── services/            # 业务服务
│   └── services/                # 功能服务
│       ├── audio/               # 音频处理 ✅
│       ├── video/               # 视频导出 ✅
│       ├── subtitle/            # 字幕生成 ✅
│       └── image/               # 图片处理 ✅
├── tests/                       # 单元测试 ✅
├── docs/                        # 项目文档
└── examples/                    # 使用示例
```

---

## 📊 开发进度

### v2.2 - Web 界面版本（当前版本）

**已完成功能** ✅

- [x] **后端架构**（Day 1-3）
  - Flask Web 服务器
  - 文件上传/管理 API
  - 项目管理 API
  - 播放控制 API
  - 会话管理系统

- [x] **前端界面**（Day 2-3）
  - 响应式 Web UI（4 个主视图）
  - 文件拖拽上传（支持批量）
  - 实时播放器（Canvas 渲染）
  - 时间轴可视化组件
  - 状态管理和持久化

- [x] **核心功能**
  - 音频播放控制
  - 照片自动切换（3 种过渡动画）
  - 时间轴精确同步
  - 键盘快捷键支持

**开发中功能** 🚧

- [ ] **视频导出**（Day 3）
  - 后台任务管理
  - 导出进度追踪
  - 多分辨率支持

- [ ] **功能完善**（Day 1-3）
  - 用户文档编写
  - API 文档完善
  - 性能优化

**测试覆盖** 📝

- 后端单元测试：26/26 通过 ✅
- 前端集成测试：核心流程验证完成 ✅
- 已修复主要 Bug：5 个 ✅

### 历史版本

- **v2.1** - 播放器核心模块（2025-10）
- **v2.0** - 智能字幕生成（2025-09）
- **v1.0** - 基础 MVP 版本（2025-08）

---

## 📚 文档

### 🎯 快速导航

**核心文档**
- **[文档中心](./docs/README.md)** - 完整文档导航 🆕
- **[产品需求文档（PRD）](../docs/PRD_演讲视频合成系统.md)** - 完整产品设计
- **[实施计划](../docs/implementation_plan.md)** - 开发进度追踪
- [Web API 文档](./docs/api/Web_API文档.md) - REST API 接口定义 ✅
- [技术架构](./docs/architecture/README.md) - 系统架构设计 ✅
- [MVP 实现文档](./docs/architecture/MVP_实现文档.md) - MVP 技术实现 ✅

**功能模块文档**
- [播放器模块](./docs/development/播放器模块文档.md) - 实时播放器 (v2.1) ✅
- [视频导出模块](./docs/development/视频导出模块文档.md) - 视频合成功能 ✅
- [字幕功能](./docs/development/字幕功能文档.md) - AI 字幕生成 (v2.0) ✅

**更新日志**
- [v2.2 更新说明](./docs/changelog/v2.2_项目状态与规划更新.md) - Web 界面版本 🆕
- [v2.1 更新说明](./docs/changelog/v2.1_更新说明.md) - 播放器核心
- [v2.0 更新说明](./docs/changelog/v2.0_更新说明.md) - 智能字幕

**Bug 修复记录**
- [播放器视图交互问题](./docs/bugfix/BUG_FIX_播放器视图交互问题.md) ✅
- [文件上传显示问题](./docs/bugfix/文件上传显示问题修复.md) ✅
- [播放器图片渲染问题](./docs/bugfix/播放器图片渲染和按钮问题修复.md) ✅
- [Session 管理问题](./docs/bugfix/SESSION_ID_修复总结.md) ✅

**测试文档**
- [快速测试指南](./docs/testing/快速测试指南.md) - 功能验证 ✅
- [字幕问题排查](./docs/testing/字幕问题排查指南.md) - 调试指南 ✅

### 📖 文档阅读路径

#### 🎓 新手入门

**推荐阅读顺序：**

1. **[项目 README](./README.md)** - 项目概览和快速开始
2. **[技术架构](./docs/architecture/README.md)** - 理解系统设计
3. **[MVP 实现文档](./docs/architecture/MVP_实现文档.md)** - 核心功能实现
4. **[快速测试指南](./docs/testing/快速测试指南.md)** - 动手验证

#### 👨‍💻 开发者路径

**功能开发：**

1. **[Web API 文档](./docs/api/Web_API文档.md)** - 后端接口
2. **功能模块文档** - 具体模块实现
   - [播放器模块](./docs/development/播放器模块文档.md)
   - [视频导出模块](./docs/development/视频导出模块文档.md)
   - [字幕功能](./docs/development/字幕功能文档.md)
3. **[Bug 修复记录](./docs/bugfix/)** - 常见问题解决方案

#### 👤 最终用户

**使用指南：**（待完善）

1. 快速开始指南
2. 使用教程
3. 常见问题 FAQ

### 📊 文档完成度

| 类别 | 完成度 | 状态 |
|------|--------|------|
| **API 文档** | 100% | ✅ 完成 |
| **架构设计** | 100% | ✅ 完成 |
| **功能模块** | 100% | ✅ 完成 |
| **更新日志** | 100% | ✅ 完成 |
| **Bug 修复** | 100% | ✅ 完成 |
| **测试文档** | 100% | ✅ 完成 |
| **用户文档** | 60% | 🚧 进行中 |
| **部署文档** | 80% | 🚧 进行中 |

**最新补充**：
- ✅ 集成测试指南
- ✅ 快速上手指南
- ✅ 常见问题 FAQ
- ✅ 部署指南

---

## 🛠️ 技术栈

### 后端
- **Python 3.8+** - 主要编程语言
- **Flask** - Web 框架
- **Pillow** - 图像处理
- **MoviePy** - 视频合成
- **Whisper** - 语音识别（字幕生成）

### 前端
- **原生 JavaScript（ES6+）** - 无框架依赖
- **HTML5 Canvas** - 照片渲染
- **Web Audio API** - 音频播放
- **CSS3** - 响应式样式

### 开发工具
- **pytest** - 单元测试
- **Git** - 版本控制

---

## 🤝 贡献

我们欢迎各种形式的贡献！

- 🐛 [报告 Bug](https://github.com/Qiniu-ERE/Sunflower/issues)
- 💡 [提出功能建议](https://github.com/Qiniu-ERE/Sunflower/issues)
- 📝 改进文档
- 🔧 提交代码

---

## 📄 许可证

本项目采用 [MIT 许可证](./LICENSE)

---

## 📧 联系方式

- GitHub: [@Qiniu-ERE](https://github.com/Qiniu-ERE)
- Issues: [提交问题](https://github.com/Qiniu-ERE/Sunflower/issues)
- Email: Qiniu-ERE@gmail.com

---

<p align="center">
  <b>Made with ❤️ by Sunflower Team</b><br>
  <sub>基于 AI 辅助开发，快速迭代，持续改进</sub>
</p>
