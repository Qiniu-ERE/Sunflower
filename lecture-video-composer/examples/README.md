# 示例项目

本目录包含演讲视频合成系统的使用示例。

## 📁 目录结构

```
examples/
├── basic/                 # 基础示例
│   ├── index.html
│   ├── app.js
│   └── README.md
├── advanced/              # 高级示例
│   ├── custom-effects/   # 自定义转场效果
│   ├── batch-export/     # 批量导出
│   └── README.md
├── fixtures/              # 示例数据
│   ├── sample-audio.mp3
│   └── sample-photos/
└── tutorials/             # 教程
    ├── getting-started.md
    └── advanced-usage.md
```

## 🚀 快速开始

### 示例1：基础播放器

最简单的演讲回放器实现。

```html
<!-- examples/basic/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>演讲回放器 - 基础示例</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .player {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 8px;
        }
        
        .photo-display {
            width: 100%;
            max-height: 600px;
            object-fit: contain;
            background: #000;
            border-radius: 4px;
        }
        
        .controls {
            margin-top: 20px;
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        button {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            background: #007bff;
            color: white;
            cursor: pointer;
        }
        
        button:hover {
            background: #0056b3;
        }
        
        .timeline {
            flex: 1;
            height: 8px;
            background: #ddd;
            border-radius: 4px;
            cursor: pointer;
            position: relative;
        }
        
        .timeline-progress {
            height: 100%;
            background: #007bff;
            border-radius: 4px;
            transition: width 0.1s;
        }
    </style>
</head>
<body>
    <h1>演讲回放器</h1>
    
    <div class="upload-area">
        <h2>1. 上传文件</h2>
        <label>
            音频文件:
            <input type="file" id="audioInput" accept="audio/*">
        </label>
        <br><br>
        <label>
            照片文件:
            <input type="file" id="photoInput" accept="image/*" multiple>
        </label>
    </div>
    
    <div class="player" id="player" style="display: none;">
        <h2>2. 播放演讲</h2>
        <img id="photoDisplay" class="photo-display" src="" alt="演讲内容">
        
        <div class="controls">
            <button id="playBtn">播放</button>
            <button id="pauseBtn">暂停</button>
            <div class="timeline" id="timeline">
                <div class="timeline-progress" id="progress"></div>
            </div>
            <span id="timeDisplay">00:00 / 00:00</span>
        </div>
        
        <audio id="audioPlayer" style="display: none;"></audio>
    </div>

    <script type="module" src="./app.js"></script>
</body>
</html>
```

```javascript
// examples/basic/app.js
import { TimelineSync } from '../../src/core/timeline/timeline-sync.js';
import { PlayManager } from '../../src/core/player/play-manager.js';

let timeline, player;

// 文件上传处理
document.getElementById('audioInput').addEventListener('change', async (e) => {
  const audioFile = e.target.files[0];
  if (!audioFile) return;
  
  // 检查是否也选择了照片
  const photoInput = document.getElementById('photoInput');
  if (photoInput.files.length === 0) {
    alert('请先选择照片文件');
    return;
  }
  
  await initPlayer(audioFile, Array.from(photoInput.files));
});

document.getElementById('photoInput').addEventListener('change', async (e) => {
  const photoFiles = Array.from(e.target.files);
  if (photoFiles.length === 0) return;
  
  // 检查是否也选择了音频
  const audioInput = document.getElementById('audioInput');
  if (audioInput.files.length === 0) {
    alert('请先选择音频文件');
    return;
  }
  
  await initPlayer(audioInput.files[0], photoFiles);
});

async function initPlayer(audioFile, photoFiles) {
  console.log('初始化播放器...');
  console.log('音频:', audioFile.name);
  console.log('照片数量:', photoFiles.length);
  
  // 创建时间轴
  timeline = new TimelineSync(audioFile, photoFiles);
  console.log('时间轴构建完成:', timeline);
  
  // 设置音频源
  const audioElement = document.getElementById('audioPlayer');
  audioElement.src = URL.createObjectURL(audioFile);
  
  // 创建播放器
  const imageElement = document.getElementById('photoDisplay');
  player = new PlayManager(audioElement, imageElement, timeline);
  
  // 监听照片切换
  player.on('photochange', (photo) => {
    console.log('切换到照片:', photo);
  });
  
  // 监听时间更新
  player.on('timeupdate', (state) => {
    updateUI(state);
  });
  
  // 显示播放器
  document.getElementById('player').style.display = 'block';
  
  // 显示第一张照片
  if (timeline.photos.length > 0) {
    imageElement.src = timeline.photos[0].url;
  }
}

function updateUI(state) {
  const progress = document.getElementById('progress');
  const timeDisplay = document.getElementById('timeDisplay');
  
  // 更新进度条
  const percent = (state.currentTime / state.duration) * 100;
  progress.style.width = percent + '%';
  
  // 更新时间显示
  timeDisplay.textContent = 
    formatTime(state.currentTime) + ' / ' + formatTime(state.duration);
}

function formatTime(seconds) {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// 播放控制
document.getElementById('playBtn').addEventListener('click', () => {
  if (player) {
    player.play();
  }
});

document.getElementById('pauseBtn').addEventListener('click', () => {
  if (player) {
    player.pause();
  }
});

// 时间轴点击跳转
document.getElementById('timeline').addEventListener('click', (e) => {
  if (!player) return;
  
  const timeline = e.currentTarget;
  const rect = timeline.getBoundingClientRect();
  const percent = (e.clientX - rect.left) / rect.width;
  const audioElement = document.getElementById('audioPlayer');
  const time = percent * audioElement.duration;
  
  player.seek(time);
});
```

## 📚 其他示例

### 示例2：自定义转场效果

```javascript
// examples/advanced/custom-effects/fade-slide.js

/**
 * 自定义淡入淡出+滑动效果
 */
export class FadeSlideEffect {
  constructor(duration = 500) {
    this.duration = duration;
  }
  
  apply(fromImage, toImage, direction = 'left') {
    return new Promise((resolve) => {
      // 设置初始状态
      toImage.style.opacity = '0';
      toImage.style.transform = `translateX(${direction === 'left' ? '100%' : '-100%'})`;
      toImage.style.transition = `all ${this.duration}ms ease-in-out`;
      
      // 触发动画
      requestAnimationFrame(() => {
        fromImage.style.opacity = '0';
        toImage.style.opacity = '1';
        toImage.style.transform = 'translateX(0)';
        
        setTimeout(resolve, this.duration);
      });
    });
  }
}

// 使用示例
import { FadeSlideEffect } from './fade-slide.js';

const effect = new FadeSlideEffect(300);
player.setTransitionEffect(effect);
```

### 示例3：批量导出

```javascript
// examples/advanced/batch-export/batch-exporter.js

import { ExportManager } from '../../../src/core/exporter/export-manager.js';

/**
 * 批量导出多个演讲项目
 */
export class BatchExporter {
  constructor() {
    this.exportManager = new ExportManager();
    this.queue = [];
  }
  
  /**
   * 添加导出任务
   */
  addTask(timeline, options) {
    this.queue.push({ timeline, options });
  }
  
  /**
   * 开始批量导出
   */
  async exportAll(onProgress) {
    const results = [];
    
    for (let i = 0; i < this.queue.length; i++) {
      const { timeline, options } = this.queue[i];
      
      onProgress({
        current: i + 1,
        total: this.queue.length,
        taskName: options.filename || `video-${i + 1}`
      });
      
      try {
        const videoBlob = await this.exportManager.export({
          ...options,
          timeline,
          onProgress: (percent) => {
            console.log(`任务 ${i + 1}: ${percent}%`);
          }
        });
        
        results.push({
          success: true,
          blob: videoBlob,
          filename: options.filename
        });
      } catch (error) {
        results.push({
          success: false,
          error: error.message
        });
      }
    }
    
    return results;
  }
}

// 使用示例
const batchExporter = new BatchExporter();

// 添加多个任务
projects.forEach(project => {
  batchExporter.addTask(project.timeline, {
    filename: `${project.title}.mp4`,
    width: 1920,
    height: 1080
  });
});

// 开始导出
const results = await batchExporter.exportAll((progress) => {
  console.log(`进度: ${progress.current}/${progress.total} - ${progress.taskName}`);
});

// 下载结果
results.forEach((result, index) => {
  if (result.success) {
    downloadBlob(result.blob, result.filename);
  }
});
```

### 示例4：响应式播放器

```javascript
// examples/advanced/responsive/responsive-player.js

/**
 * 响应式播放器，自动适配不同屏幕尺寸
 */
export class ResponsivePlayer {
  constructor(container, timeline) {
    this.container = container;
    this.timeline = timeline;
    this.setupResponsive();
  }
  
  setupResponsive() {
    // 监听窗口大小变化
    window.addEventListener('resize', () => {
      this.adjustLayout();
    });
    
    // 初始布局
    this.adjustLayout();
  }
  
  adjustLayout() {
    const width = this.container.clientWidth;
    
    if (width < 768) {
      // 移动端布局
      this.applyMobileLayout();
    } else if (width < 1024) {
      // 平板布局
      this.applyTabletLayout();
    } else {
      // 桌面布局
      this.applyDesktopLayout();
    }
  }
  
  applyMobileLayout() {
    // 垂直布局，简化控制
    this.container.classList.add('mobile-layout');
  }
  
  applyTabletLayout() {
    this.container.classList.add('tablet-layout');
  }
  
  applyDesktopLayout() {
    this.container.classList.add('desktop-layout');
  }
}
```

## 🎓 教程

### 入门教程

查看 [getting-started.md](./tutorials/getting-started.md) 了解：
- 如何创建第一个播放器
- 文件命名规范
- 基础API使用

### 高级用法

查看 [advanced-usage.md](./tutorials/advanced-usage.md) 了解：
- 自定义转场效果
- 性能优化技巧
- 插件开发指南

## 📦 示例数据

`fixtures/` 目录包含测试用的示例数据：

```
fixtures/
├── sample-audio.mp3          # 5分钟示例音频
├── sample-photos/
│   ├── 2025-10-24-14:30:00.jpg
│   ├── 2025-10-24-14:32:00.jpg
│   └── 2025-10-24-14:35:00.jpg
└── README.md
```

使用示例数据：

```javascript
// 从fixtures目录加载
const audioPath = './fixtures/sample-audio.mp3';
const photoPaths = [
  './fixtures/sample-photos/2025-10-24-14:30:00.jpg',
  './fixtures/sample-photos/2025-10-24-14:32:00.jpg',
  './fixtures/sample-photos/2025-10-24-14:35:00.jpg'
];
```

## 🔧 运行示例

### 本地运行

```bash
# 进入示例目录
cd examples/basic

# 启动本地服务器
npx http-server -p 8080

# 在浏览器打开
# http://localhost:8080
```

### 使用Live Server (VS Code)

1. 安装 Live Server 扩展
2. 右键点击 `index.html`
3. 选择 "Open with Live Server"

## 📝 贡献示例

欢迎贡献新的示例！请确保：

1. 代码清晰易懂
2. 添加充分的注释
3. 包含README说明
4. 提供示例数据或说明
5. 测试示例可正常运行

## 🔗 相关链接

- [API文档](../docs/api/README.md)
- [开发指南](../docs/development/README.md)
- [技术架构](../docs/architecture/README.md)

---
