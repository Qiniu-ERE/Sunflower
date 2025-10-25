# 演讲视频合成系统 - 实施计划

**项目**: Lecture Video Composer  
**版本**: v2.2 - GUI界面实现  
**日期**: 2025-10-25  
**当前状态**: 播放器核心已完成(v2.1)，需要添加图形界面  

---

## [概述]

基于已完成的播放器核心模块(v2.1)，本次实施的目标是为系统添加完整的图形用户界面(GUI)，使产品达到可直接面向最终用户的程度。

当前系统已经拥有完整的后端能力，包括：时间轴同步引擎、音频播放控制、照片显示管理、视频导出、字幕生成等核心功能。这些功能通过命令行工具可以完整使用，但缺少用户友好的图形界面。

根据PRD规划，我们将实现Web应用形式的MVP界面，采用本地Web服务器+浏览器前端的架构。这种方案具有跨平台、开发快速、易于迭代的优势，符合"MVP快速验证"的产品策略。

实施范围包括：
1. Web后端服务器（基于Flask）- 提供文件管理、项目管理、播放控制等API
2. Web前端界面（HTML/CSS/JavaScript）- 提供直观的用户界面和交互体验
3. 实时播放功能 - 基于Web Audio API和Canvas渲染
4. 项目管理功能 - 文件导入、项目保存/加载、设置管理
5. 视频导出界面 - 可视化的导出配置和进度显示

---

## [类型]

本次实施需要定义的核心数据结构和接口类型。

### API请求/响应类型

```python
# API响应基础类型
@dataclass
class ApiResponse:
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# 项目信息类型
@dataclass
class ProjectInfo:
    project_id: str
    title: str
    created_at: str
    audio_file: str
    photo_count: int
    duration: float
    metadata_path: Path

# 文件上传信息
@dataclass
class UploadedFile:
    filename: str
    path: Path
    size: int
    mime_type: str
    timestamp: datetime

# 播放状态类型
@dataclass
class PlaybackStatus:
    state: str  # 'stopped', 'playing', 'paused'
    position: float
    duration: float
    current_photo: Optional[str]
    volume: float

# 导出任务状态
@dataclass
class ExportTask:
    task_id: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    progress: float  # 0-100
    output_file: Optional[Path]
    error: Optional[str]
```

### 前端TypeScript接口（可选，使用JavaScript时作为文档）

```typescript
// 项目元数据
interface ProjectMetadata {
  version: string;
  title: string;
  created_at: string;
  audio: {
    filename: string;
    duration: number;
    format: string;
  };
  timeline: TimelineItem[];
  settings: ProjectSettings;
}

// 时间轴项
interface TimelineItem {
  timestamp: string;
  offset: number;
  photo: string;
  duration: number;
}

// 播放器配置
interface PlayerConfig {
  autoPlay: boolean;
  volume: number;
  loop: boolean;
  transitionDuration: number;
  transitionEffect: 'fade' | 'slide' | 'none';
}

// 导出配置
interface ExportConfig {
  resolution: string;
  fps: number;
  videoBitrate: string;
  enableSubtitles: boolean;
}
```

---

## [文件]

本次实施需要创建和修改的文件清单。

### 新建文件

#### Web后端服务器

1. **`lecture-video-composer/src/web/app.py`**
   - Flask应用主文件
   - 路由定义和请求处理
   - 会话管理和错误处理
   - 约600-800行

2. **`lecture-video-composer/src/web/api/__init__.py`**
   - API模块初始化
   - 蓝图注册

3. **`lecture-video-composer/src/web/api/project_api.py`**
   - 项目管理API端点
   - 创建/加载/保存/删除项目
   - 约300行

4. **`lecture-video-composer/src/web/api/file_api.py`**
   - 文件上传/下载API
   - 文件验证和处理
   - 约200行

5. **`lecture-video-composer/src/web/api/playback_api.py`**
   - 播放控制API
   - 状态查询和更新
   - 约250行

6. **`lecture-video-composer/src/web/api/export_api.py`**
   - 视频导出API
   - 任务管理和进度追踪
   - 约300行

7. **`lecture-video-composer/src/web/services/session_manager.py`**
   - 会话状态管理
   - 多用户支持（本地单用户为主）
   - 约200行

8. **`lecture-video-composer/src/web/services/task_manager.py`**
   - 后台任务管理（视频导出等）
   - 任务队列和进度追踪
   - 约250行

#### Web前端界面

9. **`lecture-video-composer/src/web/static/index.html`**
   - 主界面HTML结构
   - 约300行

10. **`lecture-video-composer/src/web/static/css/style.css`**
    - 主样式表
    - 响应式设计
    - 约500行

11. **`lecture-video-composer/src/web/static/css/player.css`**
    - 播放器组件样式
    - 时间轴可视化
    - 约300行

12. **`lecture-video-composer/src/web/static/js/app.js`**
    - 应用主逻辑
    - 页面路由和状态管理
    - 约400行

13. **`lecture-video-composer/src/web/static/js/player.js`**
    - 播放器核心类
    - Web Audio API集成
    - Canvas照片渲染
    - 约600行

14. **`lecture-video-composer/src/web/static/js/timeline.js`**
    - 时间轴可视化组件
    - 交互控制
    - 约300行

15. **`lecture-video-composer/src/web/static/js/file-manager.js`**
    - 文件拖拽上传
    - 文件列表管理
    - 约250行

16. **`lecture-video-composer/src/web/static/js/api-client.js`**
    - API调用封装
    - 错误处理
    - 约200行

17. **`lecture-video-composer/src/web/static/js/utils.js`**
    - 工具函数
    - 时间格式化等
    - 约150行

#### 配置和启动脚本

18. **`lecture-video-composer/src/web/config.py`**
    - Web服务器配置
    - 路径配置
    - 约100行

19. **`lecture-video-composer/run_web.py`**
    - Web服务器启动脚本
    - 命令行参数处理
    - 约150行

#### 文档

20. **`lecture-video-composer/docs/Web界面使用指南.md`**
    - 用户使用文档
    - 功能说明和截图
    - 约1000行

21. **`lecture-video-composer/docs/Web_API文档.md`**
    - API接口文档
    - 请求/响应示例
    - 约800行

### 修改文件

1. **`lecture-video-composer/README.md`**
   - 添加Web界面使用说明
   - 更新安装和运行指引

2. **`lecture-video-composer/requirements.txt`**
   - 添加Flask及相关依赖
   - 添加CORS支持库

3. **`lecture-video-composer/src/core/player/sync_coordinator.py`**
   - 添加Web API调用支持
   - 增强状态查询接口

---

## [函数]

关键函数和方法的详细规格。

### Web后端核心函数

#### 项目管理API (`src/web/api/project_api.py`)

```python
def create_project(audio_file: UploadedFile, photo_files: List[UploadedFile], 
                  title: Optional[str] = None) -> ApiResponse:
    """
    创建新项目
    
    功能：
    1. 验证上传的音频和照片文件
    2. 调用LectureComposer处理
    3. 生成项目ID和元数据
    4. 保存到会话中
    
    参数：
    - audio_file: 上传的音频文件
    - photo_files: 上传的照片文件列表
    - title: 项目标题（可选）
    
    返回：
    - ApiResponse包含project_id和metadata
    """

def load_project(project_id: str) -> ApiResponse:
    """
    加载已存在的项目
    
    功能：
    1. 从文件系统读取元数据
    2. 验证文件完整性
    3. 加载到会话中
    """

def get_project_list() -> ApiResponse:
    """
    获取所有项目列表
    
    返回：项目信息列表
    """

def delete_project(project_id: str) -> ApiResponse:
    """
    删除项目
    
    功能：删除项目文件和元数据
    """
```

#### 播放控制API (`src/web/api/playback_api.py`)

```python
def start_playback(project_id: str) -> ApiResponse:
    """
    开始播放
    
    功能：
    1. 获取项目的SyncCoordinator实例
    2. 调用play()方法
    3. 返回初始状态
    """

def pause_playback(project_id: str) -> ApiResponse:
    """暂停播放"""

def stop_playback(project_id: str) -> ApiResponse:
    """停止播放"""

def seek_playback(project_id: str, position: float) -> ApiResponse:
    """跳转到指定位置"""

def set_volume(project_id: str, volume: float) -> ApiResponse:
    """设置音量"""

def get_playback_status(project_id: str) -> ApiResponse:
    """
    获取播放状态
    
    返回：PlaybackStatus对象，包含：
    - state: 播放状态
    - position: 当前位置
    - duration: 总时长
    - current_photo: 当前照片路径
    - volume: 音量
    """
```

#### 视频导出API (`src/web/api/export_api.py`)

```python
def start_export(project_id: str, config: ExportConfig) -> ApiResponse:
    """
    开始视频导出
    
    功能：
    1. 创建后台导出任务
    2. 调用VideoExporter
    3. 返回task_id
    """

def get_export_progress(task_id: str) -> ApiResponse:
    """
    获取导出进度
    
    返回：ExportTask状态
    """

def cancel_export(task_id: str) -> ApiResponse:
    """取消导出任务"""

def download_video(task_id: str) -> Response:
    """下载导出的视频文件"""
```

### Web前端核心函数

#### 播放器类 (`static/js/player.js`)

```javascript
class LecturePlayer {
    /**
     * 初始化播放器
     * @param {HTMLAudioElement} audioElement - 音频元素
     * @param {HTMLCanvasElement} canvasElement - 画布元素
     */
    constructor(audioElement, canvasElement) { }
    
    /**
     * 加载项目
     * @param {ProjectMetadata} metadata - 项目元数据
     */
    async loadProject(metadata) {
        // 1. 加载音频文件
        // 2. 解析时间轴
        // 3. 预加载第一张照片
    }
    
    /**
     * 主同步循环
     */
    syncLoop() {
        // 1. 获取音频当前时间
        // 2. 查询时间轴获取当前照片
        // 3. 检测是否需要切换照片
        // 4. 执行切换动画
        // 5. 更新UI
        // 6. 使用requestAnimationFrame循环
    }
    
    /**
     * 照片过渡动画
     * @param {PhotoItem} photo - 目标照片
     */
    async transitionToPhoto(photo) {
        // 1. 淡出当前照片
        // 2. 加载新照片
        // 3. 在Canvas上渲染
        // 4. 淡入新照片
    }
    
    /**
     * 在Canvas上绘制照片
     * @param {Image} image - 图片对象
     */
    drawPhoto(image) {
        // 1. 计算缩放和居中
        // 2. 清空画布
        // 3. 绘制图片
    }
}
```

#### 时间轴组件 (`static/js/timeline.js`)

```javascript
class Timeline {
    /**
     * 渲染时间轴
     * @param {TimelineItem[]} items - 时间轴项
     */
    render(items) {
        // 1. 创建时间轴HTML
        // 2. 添加照片标记点
        // 3. 绑定点击事件
    }
    
    /**
     * 更新进度
     * @param {number} position - 当前位置
     * @param {number} duration - 总时长
     */
    updateProgress(position, duration) {
        // 更新进度条宽度
    }
    
    /**
     * 处理时间轴点击
     * @param {MouseEvent} event - 点击事件
     */
    handleClick(event) {
        // 1. 计算点击位置对应的时间
        // 2. 触发seek事件
    }
}
```

#### 文件管理器 (`static/js/file-manager.js`)

```javascript
class FileManager {
    /**
     * 初始化文件拖拽上传
     */
    initDragAndDrop() {
        // 1. 监听dragover事件
        // 2. 监听drop事件
        // 3. 验证文件类型
    }
    
    /**
     * 上传文件到服务器
     * @param {File[]} files - 文件列表
     */
    async uploadFiles(files) {
        // 1. 创建FormData
        // 2. 显示上传进度
        // 3. 调用API上传
        // 4. 处理响应
    }
}
```

---

## [类]

需要创建和修改的主要类。

### 新建类

#### 后端类

1. **`SessionManager` (src/web/services/session_manager.py)**
   - 目的：管理用户会话和项目状态
   - 关键方法：
     - `create_session() -> str`: 创建新会话
     - `get_session(session_id: str) -> Session`: 获取会话
     - `store_project(session_id: str, project: ProjectInfo)`: 存储项目
     - `get_project(session_id: str, project_id: str) -> ProjectInfo`: 获取项目
     - `cleanup_expired_sessions()`: 清理过期会话

2. **`TaskManager` (src/web/services/task_manager.py)**
   - 目的：管理后台任务（视频导出等）
   - 关键方法：
     - `create_task(task_type: str, params: Dict) -> str`: 创建任务
     - `get_task_status(task_id: str) -> ExportTask`: 获取任务状态
     - `cancel_task(task_id: str) -> bool`: 取消任务
     - `_run_export_task(task_id: str, project_id: str, config: ExportConfig)`: 执行导出任务

3. **`ProjectController` (src/web/api/project_api.py)**
   - 目的：项目API路由控制器
   - 关键方法：见[函数]章节

#### 前端类

4. **`LecturePlayer` (static/js/player.js)**
   - 目的：Web音频播放器和照片显示
   - 关键方法：见[函数]章节
   - 关键属性：
     - `audio: HTMLAudioElement`: 音频元素
     - `canvas: HTMLCanvasElement`: Canvas元素
     - `timeline: Timeline`: 时间轴数据
     - `currentPhoto: PhotoItem`: 当前照片
     - `isPlaying: boolean`: 播放状态

5. **`Timeline` (static/js/timeline.js)**
   - 目的：时间轴可视化和交互
   - 关键方法：见[函数]章节
   - 关键属性：
     - `container: HTMLElement`: 容器元素
     - `items: TimelineItem[]`: 时间轴项
     - `duration: number`: 总时长

6. **`ApiClient` (static/js/api-client.js)**
   - 目的：封装API调用
   - 关键方法：
     - `createProject(formData: FormData) -> Promise<Response>`
     - `loadProject(projectId: string) -> Promise<Response>`
     - `startPlayback(projectId: string) -> Promise<Response>`
     - `getPlaybackStatus(projectId: string) -> Promise<Response>`
     - `startExport(projectId: string, config: ExportConfig) -> Promise<Response>`

### 修改类

1. **`SyncCoordinator` (src/core/player/sync_coordinator.py)**
   - 修改原因：增强Web API支持
   - 新增方法：
     - `get_detailed_status() -> Dict`: 获取详细状态（包含更多信息）
     - `set_callback_mode(mode: str)`: 设置回调模式（本地/远程）

---

## [依赖关系]

新增和更新的Python包依赖。

### 新增依赖

```txt
# Web框架
Flask==3.0.0
Flask-CORS==4.0.0

# 会话管理
Flask-Session==0.5.0

# 任务队列（可选，用于异步导出）
celery==5.3.4
redis==5.0.1

# WebSocket支持（可选，用于实时进度推送）
Flask-SocketIO==5.3.5
python-socketio==5.10.0
```

### 前端依赖（通过CDN引入，不需要npm）

```html
<!-- 无需额外依赖，使用原生JavaScript -->
```

---

## [测试]

测试策略和测试用例设计。

### 后端API测试

#### 单元测试 (`tests/web/test_api.py`)

```python
class TestProjectAPI:
    def test_create_project_success(self):
        """测试成功创建项目"""
        # 准备测试数据
        # 调用API
        # 验证响应
    
    def test_create_project_invalid_audio(self):
        """测试无效音频文件"""
    
    def test_load_project_not_found(self):
        """测试加载不存在的项目"""

class TestPlaybackAPI:
    def test_playback_lifecycle(self):
        """测试完整播放生命周期"""
        # 创建项目
        # 开始播放
        # 暂停
        # 跳转
        # 停止
```

#### 集成测试 (`tests/web/test_integration.py`)

```python
class TestEndToEnd:
    def test_complete_workflow(self):
        """测试完整工作流"""
        # 1. 上传文件
        # 2. 创建项目
        # 3. 播放
        # 4. 导出视频
        # 5. 下载视频
```

### 前端测试

#### 手动测试清单

1. **文件上传测试**
   - [ ] 拖拽单个音频文件
   - [ ] 拖拽多个照片文件
   - [ ] 拖拽无效文件（应显示错误）
   - [ ] 上传进度显示正确

2. **播放器测试**
   - [ ] 音频播放正常
   - [ ] 照片切换同步准确
   - [ ] 进度条拖动正常
   - [ ] 音量控制正常
   - [ ] 暂停/恢复正常

3. **时间轴测试**
   - [ ] 时间轴显示正确
   - [ ] 照片标记点位置准确
   - [ ] 点击标记点跳转正确
   - [ ] 进度条更新流畅

4. **导出测试**
   - [ ] 导出配置保存正确
   - [ ] 导出进度显示正确
   - [ ] 导出完成提示
   - [ ] 视频可正常播放

### 性能测试

1. **加载性能**
   - 目标：项目加载时间 < 2秒
   - 测试：50张照片项目

2. **播放性能**
   - 目标：播放流畅度 60fps
   - 目标：照片切换延迟 < 100ms

3. **导出性能**
   - 目标：10分钟音频+50张照片 < 5分钟导出

---

## [实施顺序]

按优先级和依赖关系排列的实施步骤。

### 阶段1：基础架构搭建（Day 1-3）

**目标**：建立Web服务器和基础API框架

#### Day 1：后端框架
- [ ] 创建Flask应用结构
- [ ] 配置文件系统路径
- [ ] 实现SessionManager
- [ ] 实现基础错误处理
- [ ] 编写单元测试

**文件**：
- `src/web/app.py`
- `src/web/config.py`
- `src/web/services/session_manager.py`
- `tests/web/test_session.py`

**验收**：
- Web服务器可启动
- 会话管理功能正常

#### Day 2：项目管理API
- [ ] 实现文件上传API
- [ ] 实现项目创建API
- [ ] 实现项目加载API
- [ ] 集成LectureComposer
- [ ] 编写API测试

**文件**：
- `src/web/api/file_api.py`
- `src/web/api/project_api.py`
- `tests/web/test_project_api.py`

**验收**：
- 可通过API上传文件
- 可创建和加载项目

#### Day 3：播放控制API
- [ ] 实现播放控制端点
- [ ] 集成SyncCoordinator
- [ ] 实现状态查询API
- [ ] 添加WebSocket支持（可选）
- [ ] 编写API测试

**文件**：
- `src/web/api/playback_api.py`
- `tests/web/test_playback_api.py`

**验收**：
- 播放控制API功能完整
- 状态查询准确

---

### 阶段2：前端界面开发（Day 4-7）

**目标**：实现用户界面和交互

#### Day 4：HTML/CSS框架
- [ ] 设计页面布局
- [ ] 实现响应式CSS
- [ ] 创建播放器UI组件
- [ ] 实现时间轴UI
- [ ] 添加动画效果

**文件**：
- `src/web/static/index.html`
- `src/web/static/css/style.css`
- `src/web/static/css/player.css`

**验收**：
- 界面美观现代
- 响应式设计正常

#### Day 5：播放器JavaScript
- [ ] 实现LecturePlayer类
- [ ] Web Audio API集成
- [ ] Canvas照片渲染
- [ ] 过渡动画实现
- [ ] 同步算法实现

**文件**：
- `src/web/static/js/player.js`
- `src/web/static/js/utils.js`

**验收**：
- 音频播放正常
- 照片切换流畅

#### Day 6：交互功能
- [ ] 实现Timeline类
- [ ] 文件拖拽上传
- [ ] API客户端封装
- [ ] 应用状态管理
- [ ] 错误处理和提示

**文件**：
- `src/web/static/js/timeline.js`
- `src/web/static/js/file-manager.js`
- `src/web/static/js/api-client.js`
- `src/web/static/js/app.js`

**验收**：
- 所有交互功能正常
- 用户体验流畅

#### Day 7：集成测试和调试
- [ ] 前后端完整集成
- [ ] 修复集成问题
- [ ] 性能优化
- [ ] 浏览器兼容性测试

**验收**：
- 端到端功能正常
- 无重大bug

---

### 阶段3：高级功能（Day 8-10）

**目标**：添加视频导出和高级特性

#### Day 8：视频导出功能
- [ ] 实现TaskManager
- [ ] 实现导出API
- [ ] 后台任务处理
- [ ] 进度追踪
- [ ] 导出UI

**文件**：
- `src/web/services/task_manager.py`
- `src/web/api/export_api.py`

**验收**：
- 视频导出功能完整
- 进度显示准确

#### Day 9：功能完善
- [ ] 项目列表管理
- [ ] 配置保存/加载
- [ ] 键盘快捷键
- [ ] 帮助文档
- [ ] 错误恢复机制

**验收**：
- 所有PRD P0/P1功能完成
- 用户体验优化

#### Day 10：测试和文档
- [ ] 完整功能测试
- [ ] 性能测试和优化
- [ ] 编写用户文档
- [ ] 编写API文档
- [ ] 准备演示

**文件**：
- `docs/Web界面使用指南.md`
- `docs/Web_API文档.md`

**验收**：
- 所有测试通过
- 文档完整

---

### 阶段4：发布准备（Day 11-12）

#### Day 11-12：打磨和发布
- [ ] 代码审查和重构
- [ ] 安全性检查
- [ ] 安装脚本优化
- [ ] README更新
- [ ] 版本标记

**验收**：
- 代码质量达标
- 可正式发布

---

**实施计划文档完成**

*参考 docs/implementation_plan.md 获取完整的实施指南*
