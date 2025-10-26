# 业务服务层

本目录包含数据访问和业务服务的实现。

## 📁 目录结构

```
services/
├── audio/             # 音频服务
│   ├── audio-parser.js
│   ├── audio-loader.js
│   └── audio.test.js
├── image/             # 图片服务
│   ├── image-loader.js
│   ├── image-cache.js
│   └── image.test.js
└── metadata/          # 元数据服务
    ├── metadata-service.js
    ├── storage.js
    └── metadata.test.js
```

## 🎵 audio/ - 音频服务

### 核心职责
处理音频文件的加载、解析和元数据提取。

### audio-parser.js
音频解析器

**功能**：
- 提取音频时长
- 获取采样率和比特率
- 解析编码格式
- 生成波形数据

**API**：
```javascript
class AudioParser {
  /**
   * 解析音频文件
   * @param {File} audioFile - 音频文件
   * @returns {Promise<AudioMetadata>}
   */
  async parse(audioFile) {
    return {
      duration: 3600,        // 时长（秒）
      sampleRate: 44100,     // 采样率
      channels: 2,           // 声道数
      bitrate: 192,          // 比特率（kbps）
      format: 'mp3',         // 格式
      waveform: []           // 波形数据
    };
  }

  /**
   * 生成波形数据
   * @param {AudioBuffer} buffer
   * @param {Number} samples - 采样点数
   * @returns {Array<Number>}
   */
  generateWaveform(buffer, samples = 1000) {}
}
```

### audio-loader.js
音频加载器

**功能**：
- 加载音频文件
- 解码为AudioBuffer
- 错误处理

---

## 🖼️ image/ - 图片服务

### 核心职责
高效加载、缓存和处理图片资源。

### image-loader.js
图片加载器

**功能**：
- 加载图片文件
- 生成Blob URL
- 预加载机制
- 图片压缩

**API**：
```javascript
class ImageLoader {
  /**
   * 加载图片
   * @param {File} file - 图片文件
   * @returns {Promise<ImageData>}
   */
  async load(file) {
    return {
      url: 'blob:...',
      width: 1920,
      height: 1080,
      size: 1024000,
      format: 'jpg'
    };
  }

  /**
   * 预加载图片列表
   * @param {Array<File>} files
   */
  async preload(files) {}

  /**
   * 生成缩略图
   * @param {File} file
   * @param {Number} maxSize
   * @returns {Promise<Blob>}
   */
  async generateThumbnail(file, maxSize = 200) {}
}
```

### image-cache.js
图片缓存管理

**功能**：
- LRU缓存策略
- 内存限制控制
- 自动清理

**实现**：
```javascript
class ImageCache {
  constructor(maxSize = 50) {
    this.maxSize = maxSize;
    this.cache = new Map();
  }

  /**
   * 添加到缓存
   */
  set(key, value) {
    // LRU实现
  }

  /**
   * 从缓存获取
   */
  get(key) {
    // 返回缓存的图片
  }

  /**
   * 清理缓存
   */
  clear() {}

  /**
   * 获取缓存统计
   */
  getStats() {
    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      hitRate: 0.85
    };
  }
}
```

---

## 📋 metadata/ - 元数据服务

### 核心职责
管理项目元数据的存储和读取。

### metadata-service.js
元数据服务

**功能**：
- 保存项目数据
- 加载项目数据
- 导出/导入项目

**数据结构**：
```javascript
{
  version: '1.0',
  title: '演讲标题',
  createdAt: '2025-10-24T14:30:00+08:00',
  updatedAt: '2025-10-24T15:00:00+08:00',
  audio: {
    filename: '2025-10-24 14:30:00.mp3',
    duration: 3600,
    format: 'mp3',
    sampleRate: 44100
  },
  timeline: [
    {
      timestamp: '2025-10-24T14:32:15+08:00',
      offset: 135,
      photo: '2025-10-24 14:32:15.jpg',
      duration: 225
    }
  ],
  settings: {
    transitionEffect: 'fade',
    transitionDuration: 300,
    volume: 0.8,
    playbackSpeed: 1.0
  }
}
```

**API**：
```javascript
class MetadataService {
  /**
   * 保存项目
   * @param {String} projectId
   * @param {Object} metadata
   */
  async save(projectId, metadata) {}

  /**
   * 加载项目
   * @param {String} projectId
   * @returns {Promise<Object>}
   */
  async load(projectId) {}

  /**
   * 列出所有项目
   * @returns {Promise<Array>}
   */
  async list() {}

  /**
   * 删除项目
   * @param {String} projectId
   */
  async delete(projectId) {}

  /**
   * 导出项目
   * @param {String} projectId
   * @returns {Promise<Blob>} JSON文件
   */
  async export(projectId) {}

  /**
   * 导入项目
   * @param {File} file
   * @returns {Promise<String>} 项目ID
   */
  async import(file) {}
}
```

### storage.js
存储适配器

**功能**：
- IndexedDB存储
- LocalStorage备份
- 云端同步（后期）

**实现**：
```javascript
class Storage {
  constructor(storageType = 'indexeddb') {
    this.type = storageType;
    this.db = null;
  }

  /**
   * 初始化存储
   */
  async init() {
    if (this.type === 'indexeddb') {
      this.db = await this.openIndexedDB();
    }
  }

  /**
   * 存储数据
   */
  async set(key, value) {}

  /**
   * 读取数据
   */
  async get(key) {}

  /**
   * 删除数据
   */
  async delete(key) {}

  /**
   * 列出所有键
   */
  async keys() {}
}
```

---

## 🔧 使用示例

### 完整工作流程

```javascript
import { AudioParser } from './audio/audio-parser.js';
import { ImageLoader, ImageCache } from './image/image-loader.js';
import { MetadataService } from './metadata/metadata-service.js';

// 1. 解析音频
const audioParser = new AudioParser();
const audioMeta = await audioParser.parse(audioFile);
console.log('音频时长:', audioMeta.duration);

// 2. 加载图片
const imageLoader = new ImageLoader();
const imageCache = new ImageCache(50);

for (const photoFile of photoFiles) {
  const imageData = await imageLoader.load(photoFile);
  imageCache.set(photoFile.name, imageData);
}

// 3. 保存元数据
const metadataService = new MetadataService();
await metadataService.save('project-001', {
  version: '1.0',
  title: '我的演讲',
  audio: audioMeta,
  timeline: timelineData,
  settings: userSettings
});

// 4. 后续加载
const savedProject = await metadataService.load('project-001');
console.log('加载项目:', savedProject.title);
```

---

## 📊 性能优化

### 音频处理优化
- 使用Web Worker异步解析
- 增量生成波形数据
- 缓存解析结果

### 图片加载优化
- 懒加载策略
- 预加载下一张
- 压缩和缩略图
- LRU缓存管理

### 存储优化
- 批量操作减少I/O
- 索引优化查询速度
- 定期清理过期数据

---

## 🧪 测试

### 单元测试示例

```javascript
// audio.test.js
describe('AudioParser', () => {
  test('should parse audio metadata', async () => {
    const parser = new AudioParser();
    const file = new File(['...'], 'test.mp3');
    const meta = await parser.parse(file);
    
    expect(meta.duration).toBeGreaterThan(0);
    expect(meta.format).toBe('mp3');
  });
});

// image.test.js
describe('ImageCache', () => {
  test('should implement LRU eviction', () => {
    const cache = new ImageCache(2);
    cache.set('a', 'data-a');
    cache.set('b', 'data-b');
    cache.set('c', 'data-c'); // 应该驱逐 'a'
    
    expect(cache.get('a')).toBeNull();
    expect(cache.get('b')).toBe('data-b');
  });
});
```

---

## 🔍 错误处理

### 常见错误

```javascript
class ServiceError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}

// 错误代码
const ERROR_CODES = {
  AUDIO_PARSE_FAILED: 'E001',
  IMAGE_LOAD_FAILED: 'E002',
  STORAGE_QUOTA_EXCEEDED: 'E003',
  INVALID_FORMAT: 'E004'
};

// 使用示例
try {
  await audioParser.parse(file);
} catch (error) {
  if (error.code === 'E001') {
    console.error('音频解析失败:', error.message);
  }
}
```

---

## 📚 相关文档

- [核心模块文档](../core/README.md)
- [Web API文档](../../docs/api/Web_API文档.md)
- [技术架构](../../docs/architecture/README.md)

---

**维护者**: Sunflower Team  
**最后更新**: 2025-10-24
