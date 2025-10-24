# 演讲视频合成系统

> 一个智能的演讲内容记录与回放工具，通过时间轴同步技术，将音频与照片结合，生成类似视频的演讲回放效果

## 📖 项目简介

本项目旨在解决教育、培训、会议等场景中演讲内容记录的痛点。用户只需录制音频并不定期拍摄照片，系统会自动根据时间戳同步音频和照片，生成流畅的演讲回放体验。

### 核心优势

- 🎯 **轻量化存储**：相比传统录屏，存储空间节省80%以上
- 🚀 **操作简便**：不需要连续录像，只需不定期拍照
- ⚡ **回放流畅**：根据时间轴自动同步音频和画面
- 📦 **灵活输出**：支持实时播放或导出视频文件

## 🏗️ 项目结构

```
lecture-video-composer/
├── docs/                    # 项目文档
├── src/                     # 源代码
│   ├── core/               # 核心模块
│   ├── ui/                 # 用户界面
│   ├── utils/              # 工具函数
│   └── services/           # 业务服务
├── tests/                   # 测试代码
├── examples/               # 示例项目
└── tools/                  # 开发工具
```

## 🚀 快速开始

### 前置要求

- Node.js >= 16.0.0
- 现代浏览器（Chrome/Firefox/Safari最新版本）

### 安装

```bash
# 克隆项目
git clone https://github.com/your-org/lecture-video-composer.git

# 进入项目目录
cd lecture-video-composer

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

### 使用方法

1. **准备素材**：确保音频和照片文件名格式为 `YYYY-MM-DD-hh:mm:ss`
2. **导入文件**：拖拽音频文件和照片到应用界面
3. **开始播放**：系统自动解析时间轴并同步播放
4. **导出视频**（可选）：点击导出按钮生成MP4视频文件

## 📚 文档

- [产品需求文档 (PRD)](./docs/PRD_演讲视频合成系统.md)
- [技术架构文档](./docs/architecture/README.md)
- [API文档](./docs/api/README.md)
- [用户指南](./docs/user-guide/README.md)
- [开发指南](./docs/development/README.md)

## 🎯 开发路线图

> **基于AI辅助编码**，开发周期大幅压缩，预计 10-14 天完成全部功能

### 阶段1: MVP (1-2天)
- [x] 文件导入功能
- [x] 时间轴自动解析
- [x] 基础播放控制
- [x] 照片自动切换
- [ ] 简单UI界面优化

### 阶段2: 基础完善版 (2-3天)
- [ ] 视频导出功能
- [ ] 项目保存/加载
- [ ] 时间轴可视化
- [ ] 照片编辑功能

### 阶段3: 智能增强版 (2-3天)
- [ ] 语音转文字（字幕）
- [ ] 关键帧智能识别
- [ ] 照片智能增强
- [ ] 智能剪辑

### 阶段4: 协作与分享版 (2-3天)
- [ ] 云端存储和同步
- [ ] 分享功能
- [ ] 团队协作

### 阶段5: 平台化 (3天)
- [ ] 实时录制
- [ ] AI助手
- [ ] 开放API

## 🤝 贡献指南

我们欢迎所有形式的贡献，包括但不限于：

- 🐛 报告Bug
- 💡 提出新功能建议
- 📝 改进文档
- 🔧 提交代码

请查看 [贡献指南](./docs/CONTRIBUTING.md) 了解详情。

## 📄 许可证

本项目采用 MIT 许可证，详情请见 [LICENSE](./LICENSE) 文件。

## 📧 联系我们

- Issue Tracker: [GitHub Issues](https://github.com/your-org/lecture-video-composer/issues)
- Email: support@example.com

---

**Made with ❤️ by Sunflower Team**
