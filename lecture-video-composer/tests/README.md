# 测试目录

本目录包含项目的所有测试代码。

## 📁 目录结构

```
tests/
├── unit/              # 单元测试
│   ├── core/         # 核心模块测试
│   ├── services/     # 服务层测试
│   └── utils/        # 工具函数测试
├── integration/       # 集成测试
│   ├── player/       # 播放器集成测试
│   └── exporter/     # 导出功能集成测试
├── e2e/              # 端到端测试
│   ├── scenarios/    # 测试场景
│   └── fixtures/     # 测试数据
├── performance/       # 性能测试
└── helpers/          # 测试辅助工具
```

## 🧪 测试策略

### 测试金字塔

```
        /\
       /  \  E2E Tests (端到端测试)
      /----\
     /      \  Integration Tests (集成测试)
    /--------\
   /          \  Unit Tests (单元测试)
  /------------\
```

- **单元测试 (70%)**：测试独立函数和类
- **集成测试 (20%)**：测试模块间交互
- **端到端测试 (10%)**：测试完整用户流程

## 🔧 技术栈

- **测试框架**: Jest
- **断言库**: Jest (内置)
- **Mock工具**: Jest Mock
- **覆盖率**: Jest Coverage
- **E2E测试**: Puppeteer (可选)

## 📝 单元测试

### 测试文件命名
- 文件名：`*.test.js` 或 `*.spec.js`
- 位置：与源文件同目录或 `tests/unit/` 目录

### 示例：时间轴解析测试

```javascript
// tests/unit/core/timeline-sync.test.js
import { TimelineSync } from '../../../src/core/timeline/timeline-sync.js';

describe('TimelineSync', () => {
  describe('parseTimestamp', () => {
    test('should parse valid timestamp', () => {
      const timeline = new TimelineSync();
      const date = timeline.parseTimestamp('2025-10-24-14:30:00.mp3');
      
      expect(date.getFullYear()).toBe(2025);
      expect(date.getMonth()).toBe(9); // 0-based
      expect(date.getDate()).toBe(24);
      expect(date.getHours()).toBe(14);
      expect(date.getMinutes()).toBe(30);
    });

    test('should throw error for invalid timestamp', () => {
      const timeline = new TimelineSync();
      expect(() => {
        timeline.parseTimestamp('invalid-timestamp.mp3');
      }).toThrow();
    });
  });

  describe('buildTimeline', () => {
    test('should build timeline with correct offsets', () => {
      const audioFile = createMockFile('2025-10-24-14:30:00.mp3');
      const photoFiles = [
        createMockFile('2025-10-24-14:32:00.jpg'),
        createMockFile('2025-10-24-14:35:00.jpg')
      ];

      const timeline = new TimelineSync(audioFile, photoFiles);
      
      expect(timeline.photos).toHaveLength(2);
      expect(timeline.photos[0].offset).toBe(120); // 2分钟
      expect(timeline.photos[1].offset).toBe(300); // 5分钟
    });

    test('should sort photos by timestamp', () => {
      const audioFile = createMockFile('2025-10-24-14:30:00.mp3');
      const photoFiles = [
        createMockFile('2025-10-24-14:35:00.jpg'),
        createMockFile('2025-10-24-14:32:00.jpg') // 顺序颠倒
      ];

      const timeline = new TimelineSync(audioFile, photoFiles);
      
      expect(timeline.photos[0].offset).toBeLessThan(timeline.photos[1].offset);
    });
  });

  describe('getCurrentPhoto', () => {
    test('should return correct photo for given time', () => {
      const timeline = setupTimeline();
      
      const photo1 = timeline.getCurrentPhoto(150); // 2.5分钟
      expect(photo1.offset).toBe(120);
      
      const photo2 = timeline.getCurrentPhoto(350); // 5.8分钟
      expect(photo2.offset).toBe(300);
    });

    test('should return null before first photo', () => {
      const timeline = setupTimeline();
      const photo = timeline.getCurrentPhoto(60); // 1分钟
      expect(photo).toBeNull();
    });
  });
});

// 测试辅助函数
function createMockFile(filename) {
  return new File(['test content'], filename, { type: 'audio/mp3' });
}

function setupTimeline() {
  const audioFile = createMockFile('2025-10-24-14:30:00.mp3');
  const photoFiles = [
    createMockFile('2025-10-24-14:32:00.jpg'),
    createMockFile('2025-10-24-14:35:00.jpg')
  ];
  return new TimelineSync(audioFile, photoFiles);
}
```

## 🔗 集成测试

### 测试模块间交互

```javascript
// tests/integration/player/playback.test.js
import { TimelineSync } from '../../../src/core/timeline/timeline-sync.js';
import { PlayManager } from '../../../src/core/player/play-manager.js';
import { ImageLoader } from '../../../src/services/image/image-loader.js';

describe('Playback Integration', () => {
  let timeline, player, imageLoader;

  beforeEach(async () => {
    // 准备测试数据
    const audioFile = await loadTestAudio();
    const photoFiles = await loadTestPhotos();
    
    // 初始化组件
    timeline = new TimelineSync(audioFile, photoFiles);
    imageLoader = new ImageLoader();
    player = new PlayManager(timeline, imageLoader);
  });

  test('should sync photo changes with audio playback', async () => {
    const photoChanges = [];
    
    player.on('photochange', (photo) => {
      photoChanges.push({
        time: player.getCurrentTime(),
        photo: photo
      });
    });

    await player.play();
    await waitForPlayback(5000); // 播放5秒
    player.pause();

    expect(photoChanges.length).toBeGreaterThan(0);
    // 验证照片切换时机正确
    photoChanges.forEach((change, index) => {
      if (index > 0) {
        expect(change.time).toBeGreaterThan(photoChanges[index - 1].time);
      }
    });
  });

  test('should preload next photo', async () => {
    const preloadSpy = jest.spyOn(imageLoader, 'preload');
    
    await player.play();
    await waitForPlayback(1000);
    
    expect(preloadSpy).toHaveBeenCalled();
  });
});
```

## 🌐 端到端测试

### 测试完整用户流程

```javascript
// tests/e2e/scenarios/basic-playback.e2e.js
import puppeteer from 'puppeteer';

describe('Basic Playback E2E', () => {
  let browser, page;

  beforeAll(async () => {
    browser = await puppeteer.launch({
      headless: true
    });
    page = await browser.newPage();
    await page.goto('http://localhost:3000');
  });

  afterAll(async () => {
    await browser.close();
  });

  test('user can import files and play lecture', async () => {
    // 1. 上传音频文件
    const audioInput = await page.$('input[type="file"][accept="audio/*"]');
    await audioInput.uploadFile('./tests/fixtures/test-audio.mp3');
    
    // 2. 上传照片
    const photoInput = await page.$('input[type="file"][accept="image/*"]');
    await photoInput.uploadFile(
      './tests/fixtures/photo1.jpg',
      './tests/fixtures/photo2.jpg'
    );

    // 3. 等待处理完成
    await page.waitForSelector('.timeline-ready', { timeout: 5000 });

    // 4. 点击播放
    await page.click('#playBtn');
    
    // 5. 验证播放状态
    const isPlaying = await page.$eval('#playBtn', el => {
      return el.textContent.includes('暂停');
    });
    expect(isPlaying).toBe(true);

    // 6. 验证照片显示
    const photoSrc = await page.$eval('#photoDisplay', el => el.src);
    expect(photoSrc).toBeTruthy();
    expect(photoSrc).toContain('blob:');

    // 7. 等待照片切换
    await page.waitForFunction(
      () => document.querySelectorAll('.photo-marker').length > 0,
      { timeout: 3000 }
    );

    // 8. 测试进度拖动
    const timeline = await page.$('.timeline');
    const box = await timeline.boundingBox();
    await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);

    // 9. 截图验证
    await page.screenshot({ path: './tests/screenshots/playback.png' });
  });

  test('user can export video', async () => {
    // 导入文件
    await importTestFiles(page);

    // 点击导出按钮
    await page.click('#exportBtn');

    // 等待导出完成
    await page.waitForSelector('.export-success', { timeout: 30000 });

    // 验证下载
    const downloadPath = await getDownloadPath(page);
    expect(downloadPath).toMatch(/\.mp4$/);
  });
});
```

## ⚡ 性能测试

### 测试性能指标

```javascript
// tests/performance/timeline-performance.test.js
describe('Timeline Performance', () => {
  test('should build timeline for 100 photos in < 1s', async () => {
    const audioFile = createMockFile('2025-10-24-14:30:00.mp3');
    const photoFiles = Array.from({ length: 100 }, (_, i) => {
      const time = new Date('2025-10-24-14:30:00');
      time.setSeconds(time.getSeconds() + i * 10);
      return createMockFile(formatTimestamp(time) + '.jpg');
    });

    const start = performance.now();
    const timeline = new TimelineSync(audioFile, photoFiles);
    const duration = performance.now() - start;

    expect(duration).toBeLessThan(1000); // 应在1秒内完成
    expect(timeline.photos).toHaveLength(100);
  });

  test('should query photo in < 1ms (binary search)', () => {
    const timeline = setupLargeTimeline(1000); // 1000张照片

    const iterations = 1000;
    const start = performance.now();
    
    for (let i = 0; i < iterations; i++) {
      const randomTime = Math.random() * 10000;
      timeline.getCurrentPhoto(randomTime);
    }
    
    const avgTime = (performance.now() - start) / iterations;
    expect(avgTime).toBeLessThan(1); // 平均查询时间 < 1ms
  });
});
```

## 🛠️ 测试工具

### Mock 辅助函数

```javascript
// tests/helpers/mocks.js

/**
 * 创建Mock文件
 */
export function createMockFile(filename, content = 'test', type = 'audio/mp3') {
  return new File([content], filename, { type });
}

/**
 * 创建Mock音频元素
 */
export function createMockAudio() {
  return {
    play: jest.fn().mockResolvedValue(undefined),
    pause: jest.fn(),
    currentTime: 0,
    duration: 300,
    volume: 1,
    playbackRate: 1,
    addEventListener: jest.fn(),
    removeEventListener: jest.fn()
  };
}

/**
 * 创建Mock图片元素
 */
export function createMockImage() {
  return {
    src: '',
    width: 1920,
    height: 1080,
    onload: null,
    onerror: null
  };
}

/**
 * 等待指定时间
 */
export function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}
```

## 📊 运行测试

### 命令

```bash
# 运行所有测试
npm test

# 运行单元测试
npm run test:unit

# 运行集成测试
npm run test:integration

# 运行E2E测试
npm run test:e2e

# 监视模式
npm test -- --watch

# 生成覆盖率报告
npm run test:coverage

# 运行特定文件
npm test timeline-sync.test.js

# 调试模式
node --inspect-brk node_modules/.bin/jest --runInBand
```

### 配置文件

```javascript
// jest.config.js
module.exports = {
  testEnvironment: 'jsdom',
  coverageDirectory: 'coverage',
  collectCoverageFrom: [
    'src/**/*.js',
    '!src/**/*.test.js',
    '!src/**/*.spec.js'
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  },
  testMatch: [
    '**/tests/**/*.test.js',
    '**/tests/**/*.spec.js'
  ],
  setupFilesAfterEnv: ['<rootDir>/tests/setup.js'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1'
  }
};
```

## 📈 覆盖率目标

| 类型 | 目标 | 当前 |
|------|------|------|
| 语句覆盖率 | 80% | - |
| 分支覆盖率 | 80% | - |
| 函数覆盖率 | 80% | - |
| 行覆盖率 | 80% | - |

## ✅ 测试检查清单

开发新功能时，确保：

- [ ] 编写单元测试
- [ ] 测试边界情况
- [ ] 测试错误处理
- [ ] 添加集成测试（如需要）
- [ ] 更新相关文档
- [ ] 确保测试通过
- [ ] 检查覆盖率

## 🐛 调试测试

### VS Code 调试配置

```json
// .vscode/launch.json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "node",
      "request": "launch",
      "name": "Jest Debug",
      "program": "${workspaceFolder}/node_modules/.bin/jest",
      "args": ["--runInBand", "--no-cache"],
      "console": "integratedTerminal",
      "internalConsoleOptions": "neverOpen"
    }
  ]
}
```

---

**维护者**: Sunflower Team  
**最后更新**: 2025-10-24
