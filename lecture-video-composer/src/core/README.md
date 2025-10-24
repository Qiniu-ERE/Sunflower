# 核心业务逻辑模块

本目录包含系统的核心业务逻辑实现。

## 📁 模块结构

```
core/
├── timeline/          # 时间轴同步引擎
│   ├── timeline-sync.js
│   ├── timeline-builder.js
│   └── timeline.test.js
├── player/            # 播放管理器
│   ├── play-manager.js
│   ├── audio-controller.js
│   └── player.test.js
└── exporter/          # 导出管理器
    ├── export-manager.js
    ├── video-encoder.js
    └── exporter.test.js
```

## 🎯 timeline/ - 时间轴同步引擎

### 核心职责
根据文件创建时间，建立音频和照片的时间轴映射关系。

### 主要文件

#### timeline-sync.js
时间轴同步引擎主类

**核心功能**：
- 解析文件名时间戳（YYYY-MM-DD hh:mm:ss）
- 计算照片相对音频的时间偏移
- 构建时间轴数据结构
- 实时查询当前应显示的照片

**示例代码**：
```javascript
class TimelineSync {
  constructor(audioFile, photoFiles) {
    this.audioStartTime = this.parseTimestamp(audioFile.name);
    this.photos = this.buildTimeline(photoFiles);
  }

  parseTimestamp(filename) {
    const timeStr = filename.replace(/\.[^.]+$/, '');
    return new Date(timeStr.replace(' ', 'T'));
  }

  buildTimeline(photoFiles) {
    // 构建时间轴逻辑
  }

  getCurrentPhoto(currentTime) {
    // 查询当前照片
  }
}
```

#### timeline-builder.js
时间轴构建器

**核心功能**：
- 排序照片文件
- 计算每张照片的显示时长
- 处理边界情况（开始前/结束后）

### 数据结构

```javascript
// 时间轴项
{
  timestamp: Date,       // 绝对时间戳
  offset: Number,        // 相对音频开始的秒数
  file: File,           // 照片文件对象
  url: String,          // Blob URL
  duration: Number      // 显示持续时间（秒）
}

// 完整时间轴
{
  audioStartTime: Date,
  audioDuration: Number,
  photos: Array<TimelineItem>
}
```

### 算法说明

**时间偏移计算**：
```
offset = (photo_timestamp - audio_start_time) / 1000
```

**显示时长计算**：
```
duration = next_photo_offset - current_photo_offset
```

最后一张照片的duration设为Infinity，表示持续到音频结束。

---

## 🎮 player/ - 播放管理器

### 核心职责
协调音频播放和照片切换，提供播放控制接口。

### 主要文件

#### play-manager.js
播放管理器主类

**核心功能**：
- 音频播放控制（播放、暂停、跳转）
- 监听播放进度
- 触发照片切换
- 音量和倍速控制

**API接口**：
```javascript
class PlayManager {
  /**
   * 开始播放
   */
  play() {}

  /**
   * 暂停播放
   */
  pause() {}

  /**
   * 跳转到指定时间
   * @param {Number} time - 时间（秒）
   */
  seek(time) {}

  /**
   * 设置音量
   * @param {Number} volume - 音量 (0-1)
   */
  setVolume(volume) {}

  /**
   * 设置播放速度
   * @param {Number} speed - 速度倍率
   */
  setSpeed(speed) {}

  /**
   * 获取当前播放状态
   * @returns {Object} 状态信息
   */
  getState() {}
}
```

#### audio-controller.js
音频控制器

**核心功能**：
- 封装Web Audio API
- 音频加载和解码
- 精确的时间控制

### 事件系统

```javascript
// 支持的事件
'play'          // 开始播放
'pause'         // 暂停
'timeupdate'    // 时间更新
'photochange'   // 照片切换
'ended'         // 播放结束
'error'         // 错误发生
```

---

## 📤 exporter/ - 导出管理器

### 核心职责
将音频和照片序列合成为标准视频文件。

### 主要文件

#### export-manager.js
导出管理器主类

**核心功能**：
- 管理导出流程
- 进度反馈
- 错误处理

**API接口**：
```javascript
class ExportManager {
  /**
   * 导出视频
   * @param {Object} options - 导出选项
   * @returns {Promise<Blob>} 视频文件
   */
  async export(options) {
    // options: {
    //   width: 1920,
    //   height: 1080,
    //   fps: 30,
    //   quality: 'high',
    //   onProgress: (percent) => {}
    // }
  }
}
```

#### video-encoder.js
视频编码器

**核心功能**：
- 使用FFmpeg.wasm编码
- 帧序列生成
- 音视频合并

**工作流程**：
```
1. 根据时间轴生成帧序列
2. 将照片转换为视频帧
3. 使用FFmpeg合成视频
4. 添加音频轨道
5. 输出视频文件
```

### 导出配置

```javascript
// 默认配置
const DEFAULT_EXPORT_CONFIG = {
  width: 1920,
  height: 1080,
  fps: 30,
  videoBitrate: '5000k',
  audioBitrate: '192k',
  format: 'mp4',
  codec: 'libx264',
  pixelFormat: 'yuv420p'
};
```

---

## 🧪 测试

### 单元测试

每个模块都有对应的测试文件：

```javascript
// timeline.test.js
describe('TimelineSync', () => {
  test('should parse timestamp correctly', () => {
    // 测试时间戳解析
  });

  test('should build timeline with correct offsets', () => {
    // 测试时间轴构建
  });

  test('should find current photo', () => {
    // 测试照片查询
  });
});
```

运行测试：
```bash
npm test src/core
```

---

## 🔧 使用示例

### 完整使用流程

```javascript
import { TimelineSync } from './timeline/timeline-sync.js';
import { PlayManager } from './player/play-manager.js';
import { ExportManager } from './exporter/export-manager.js';

// 1. 创建时间轴
const audioFile = new File(/*...*/);
const photoFiles = [/*...*/];
const timeline = new TimelineSync(audioFile, photoFiles);

// 2. 初始化播放器
const player = new PlayManager(audioElement, imageElement, timeline);

// 3. 播放控制
player.on('photochange', (photo) => {
  console.log('切换到照片:', photo);
});

player.play();
player.setVolume(0.8);
player.setSpeed(1.5);

// 4. 导出视频
const exporter = new ExportManager(timeline);
const videoBlob = await exporter.export({
  width: 1920,
  height: 1080,
  onProgress: (percent) => {
    console.log(`导出进度: ${percent}%`);
  }
});
```

---

## 📊 性能优化

### 时间轴查询优化
- 使用二分查找算法
- 时间复杂度：O(log n)

### 照片预加载
- 预加载下一张照片
- 减少切换延迟

### 内存管理
- 及时释放不用的资源
- 限制缓存大小

---

## 🔍 调试技巧

### 启用详细日志
```javascript
// 在配置中设置
const config = {
  debug: true,
  logLevel: 'verbose'
};
```

### 性能监控
```javascript
player.on('timeupdate', (state) => {
  console.log('播放位置:', state.currentTime);
  console.log('缓冲状态:', state.buffered);
});
```

---

**维护者**: Sunflower Team  
**最后更新**: 2025-10-24
