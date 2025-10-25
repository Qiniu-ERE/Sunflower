# Web API 文档

## 概述

本文档描述了 Lecture Video Composer Web 应用的 RESTful API 接口。

**基础URL**: `http://localhost:5000/api`  
**响应格式**: JSON  
**认证方式**: Session (Flask Session)

---

## 通用响应格式

所有API端点返回统一的JSON响应格式：

### 成功响应

```json
{
  "success": true,
  "message": "操作成功的描述信息",
  "data": {
    // 具体数据
  }
}
```

### 错误响应

```json
{
  "success": false,
  "message": "错误描述信息",
  "error": "详细错误信息（可选）"
}
```

---

## 1. 文件管理 API

### 1.1 上传音频文件

**端点**: `POST /api/file/upload/audio`  
**描述**: 上传单个音频文件

**请求**:
- Content-Type: `multipart/form-data`
- Body:
  - `file`: 音频文件（支持 .mp3, .wav, .m4a, .aac, .ogg）
  - 最大文件大小: 500MB

**响应示例**:
```json
{
  "success": true,
  "message": "音频文件上传成功",
  "data": {
    "path": "uploads/audio_20251025_143022.mp3",
    "filename": "lecture_audio.mp3",
    "size": 15728640
  }
}
```

**错误码**:
- 400: 未提供文件或文件类型不支持
- 413: 文件大小超过限制
- 500: 服务器内部错误

---

### 1.2 批量上传照片

**端点**: `POST /api/file/upload/photos`  
**描述**: 批量上传多张照片

**请求**:
- Content-Type: `multipart/form-data`
- Body:
  - `files`: 照片文件数组（支持 .jpg, .jpeg, .png）
  - 每个文件最大: 20MB
  - 最多上传: 100张

**响应示例**:
```json
{
  "success": true,
  "message": "上传了 5 个照片文件",
  "data": {
    "uploaded": [
      {
        "path": "uploads/photo_20251025_143025_001.jpg",
        "filename": "photo1.jpg",
        "size": 2457600
      },
      {
        "path": "uploads/photo_20251025_143025_002.jpg",
        "filename": "photo2.jpg",
        "size": 3145728
      }
    ]
  }
}
```

---

### 1.3 列出上传的文件

**端点**: `GET /api/file/list`  
**描述**: 获取当前会话所有已上传文件列表

**响应示例**:
```json
{
  "success": true,
  "message": "获取文件列表成功",
  "data": {
    "files": [
      {
        "path": "uploads/audio_20251025_143022.mp3",
        "filename": "lecture_audio.mp3",
        "type": "audio",
        "size": 15728640
      },
      {
        "path": "uploads/photo_20251025_143025_001.jpg",
        "filename": "photo1.jpg",
        "type": "photo",
        "size": 2457600
      }
    ]
  }
}
```

---

### 1.4 下载文件

**端点**: `GET /api/file/download/<path:file_path>`  
**描述**: 下载指定文件

**参数**:
- `file_path`: 文件相对路径（从上传响应中获取）

**响应**: 文件二进制内容

---

### 1.5 删除文件

**端点**: `POST /api/file/delete`  
**描述**: 删除指定文件

**请求**:
```json
{
  "path": "uploads/audio_20251025_143022.mp3"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "文件删除成功"
}
```

---

## 2. 项目管理 API

### 2.1 创建项目

**端点**: `POST /api/project/create`  
**描述**: 从上传的文件创建新项目，自动生成时间轴

**请求**:
```json
{
  "audio_file": "uploads/audio_20251025_143022.mp3",
  "photo_files": [
    "uploads/photo_20251025_143025_001.jpg",
    "uploads/photo_20251025_143025_002.jpg"
  ],
  "title": "我的演讲项目"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "项目创建成功",
  "data": {
    "project_id": "proj_20251025_143030",
    "title": "我的演讲项目",
    "metadata": {
      "version": "2.0",
      "title": "我的演讲项目",
      "created_at": "2025-10-25T14:30:30",
      "audio": {
        "filename": "lecture_audio.mp3",
        "duration": 180.5,
        "format": "mp3"
      },
      "timeline": [
        {
          "timestamp": "2025-10-25T14:15:15",
          "offset": 0.0,
          "photo": "photo1.jpg",
          "duration": 90.0
        },
        {
          "timestamp": "2025-10-25T14:16:45",
          "offset": 90.0,
          "photo": "photo2.jpg",
          "duration": 90.5
        }
      ]
    }
  }
}
```

---

### 2.2 加载项目

**端点**: `GET /api/project/load/<project_id>`  
**描述**: 加载已存在的项目

**响应示例**:
```json
{
  "success": true,
  "message": "项目加载成功",
  "data": {
    "project_id": "proj_20251025_143030",
    "title": "我的演讲项目",
    "metadata": {
      // 项目元数据（同创建项目响应）
    }
  }
}
```

---

### 2.3 获取项目列表

**端点**: `GET /api/project/list`  
**描述**: 获取所有可用项目列表

**响应示例**:
```json
{
  "success": true,
  "message": "获取项目列表成功",
  "data": {
    "projects": [
      {
        "project_id": "proj_20251025_143030",
        "title": "我的演讲项目",
        "created_at": "2025-10-25T14:30:30",
        "duration": 180.5,
        "photo_count": 2
      }
    ]
  }
}
```

---

### 2.4 获取当前项目

**端点**: `GET /api/project/current`  
**描述**: 获取会话中当前活动的项目

**响应示例**:
```json
{
  "success": true,
  "message": "获取当前项目成功",
  "data": {
    "project_id": "proj_20251025_143030",
    "title": "我的演讲项目"
  }
}
```

---

### 2.5 设置当前项目

**端点**: `POST /api/project/set-current/<project_id>`  
**描述**: 将指定项目设置为当前活动项目

**响应示例**:
```json
{
  "success": true,
  "message": "当前项目已设置",
  "data": {
    "project_id": "proj_20251025_143030"
  }
}
```

---

### 2.6 删除项目

**端点**: `DELETE /api/project/delete/<project_id>`  
**描述**: 删除指定项目及其所有文件

**响应示例**:
```json
{
  "success": true,
  "message": "项目删除成功"
}
```

---

### 2.7 获取项目元数据

**端点**: `GET /api/project/metadata/<project_id>`  
**描述**: 获取项目的详细元数据

**响应示例**:
```json
{
  "success": true,
  "message": "获取元数据成功",
  "data": {
    "metadata": {
      "version": "2.0",
      "title": "我的演讲项目",
      "created_at": "2025-10-25T14:30:30",
      "audio": {
        "filename": "lecture_audio.mp3",
        "duration": 180.5,
        "format": "mp3"
      },
      "timeline": [
        // 时间轴项数组
      ]
    }
  }
}
```

---

### 2.8 更新项目信息

**端点**: `PUT /api/project/update/<project_id>`  
**描述**: 更新项目的基本信息

**请求**:
```json
{
  "title": "更新后的项目标题"
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "项目信息更新成功",
  "data": {
    "project_id": "proj_20251025_143030",
    "title": "更新后的项目标题"
  }
}
```

---

## 3. 播放控制 API ✅

### 3.1 开始播放

**端点**: `POST /api/playback/play/<project_id>`  
**描述**: 开始或恢复播放指定项目

**响应示例**:
```json
{
  "success": true,
  "message": "播放已开始",
  "data": {
    "state": "playing",
    "position": 0.0,
    "duration": 180.5,
    "current_photo": "photo1.jpg",
    "volume": 1.0
  }
}
```

**状态说明**:
- `state`: 播放状态
  - `playing` - 正在播放
  - `paused` - 已暂停
  - `stopped` - 已停止
- `position`: 当前播放位置（秒）
- `duration`: 总时长（秒）
- `current_photo`: 当前显示的照片文件名
- `volume`: 音量（0.0-1.0）

---

### 3.2 暂停播放

**端点**: `POST /api/playback/pause/<project_id>`  
**描述**: 暂停当前播放

**响应示例**:
```json
{
  "success": true,
  "message": "播放已暂停",
  "data": {
    "state": "paused",
    "position": 45.2,
    "duration": 180.5,
    "current_photo": "photo1.jpg",
    "volume": 1.0
  }
}
```

---

### 3.3 停止播放

**端点**: `POST /api/playback/stop/<project_id>`  
**描述**: 停止播放并重置到开始位置

**响应示例**:
```json
{
  "success": true,
  "message": "播放已停止",
  "data": {
    "state": "stopped",
    "position": 0.0,
    "duration": 180.5,
    "current_photo": null,
    "volume": 1.0
  }
}
```

---

### 3.4 跳转位置

**端点**: `POST /api/playback/seek/<project_id>`  
**描述**: 跳转到指定播放位置

**请求**:
```json
{
  "position": 60.0
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "跳转成功",
  "data": {
    "state": "playing",
    "position": 60.0,
    "duration": 180.5,
    "current_photo": "photo1.jpg",
    "volume": 1.0
  }
}
```

---

### 3.5 设置音量

**端点**: `POST /api/playback/volume/<project_id>`  
**描述**: 设置播放音量

**请求**:
```json
{
  "volume": 0.5
}
```

**参数说明**:
- `volume`: 音量值，范围 0.0-1.0
  - 0.0 = 静音
  - 0.5 = 50%音量
  - 1.0 = 100%音量

**响应示例**:
```json
{
  "success": true,
  "message": "音量设置成功",
  "data": {
    "state": "playing",
    "position": 45.2,
    "duration": 180.5,
    "current_photo": "photo1.jpg",
    "volume": 0.5
  }
}
```

---

### 3.6 获取播放状态

**端点**: `GET /api/playback/status/<project_id>`  
**描述**: 获取当前播放状态（用于前端轮询更新）

**响应示例**:
```json
{
  "success": true,
  "message": "获取状态成功",
  "data": {
    "state": "playing",
    "position": 45.2,
    "duration": 180.5,
    "current_photo": "photo1.jpg",
    "volume": 1.0
  }
}
```

**建议轮询间隔**: 100-500ms

---

## 4. 视频导出 API

### 4.1 开始导出

**端点**: `POST /api/export/start/<project_id>`  
**描述**: 开始导出视频（后台任务）

**请求**:
```json
{
  "resolution": "1920x1080",
  "fps": 30,
  "video_bitrate": "4M",
  "enable_subtitles": false
}
```

**响应示例**:
```json
{
  "success": true,
  "message": "导出任务已创建",
  "data": {
    "task_id": "export_20251025_143500",
    "status": "pending"
  }
}
```

---

### 4.2 获取导出进度

**端点**: `GET /api/export/progress/<task_id>`  
**描述**: 获取导出任务进度

**响应示例**:
```json
{
  "success": true,
  "message": "获取进度成功",
  "data": {
    "task_id": "export_20251025_143500",
    "status": "processing",
    "progress": 45.5,
    "current_step": "处理音频",
    "estimated_time": 120
  }
}
```

**状态说明**:
- `pending` - 等待开始
- `processing` - 处理中
- `completed` - 已完成
- `failed` - 失败

---

### 4.3 取消导出

**端点**: `POST /api/export/cancel/<task_id>`  
**描述**: 取消正在进行的导出任务

**响应示例**:
```json
{
  "success": true,
  "message": "导出任务已取消"
}
```

---

### 4.4 下载导出视频

**端点**: `GET /api/export/download/<task_id>`  
**描述**: 下载已完成的导出视频

**响应**: 视频文件二进制内容

---

## 错误处理

### 错误码说明

| HTTP状态码 | 含义 | 示例场景 |
|-----------|------|---------|
| 400 | 请求错误 | 缺少必需参数、参数格式错误 |
| 401 | 未认证 | 会话无效或过期 |
| 404 | 资源不存在 | 项目ID不存在 |
| 413 | 请求体过大 | 上传文件超过大小限制 |
| 500 | 服务器错误 | 内部处理异常 |

### 错误响应示例

```json
{
  "success": false,
  "message": "项目不存在",
  "error": "Project 'proj_invalid' not found in session"
}
```

---

## 会话管理

### 会话生命周期

- 会话在首次API调用时自动创建
- 会话ID存储在Cookie中：`session_id`
- 默认过期时间：24小时
- 过期后会话及其数据将被清理

### 会话状态

会话存储以下信息：
- 上传的文件列表
- 创建的项目列表
- 当前活动项目
- 播放器实例和状态

---

## 使用示例

### 完整工作流示例（使用curl）

```bash
# 1. 上传音频
curl -X POST http://localhost:5000/api/file/upload/audio \
  -F "file=@lecture.mp3"

# 2. 上传照片
curl -X POST http://localhost:5000/api/file/upload/photos \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.jpg"

# 3. 创建项目
curl -X POST http://localhost:5000/api/project/create \
  -H "Content-Type: application/json" \
  -d '{
    "audio_file": "uploads/audio_xxx.mp3",
    "photo_files": ["uploads/photo_xxx_001.jpg", "uploads/photo_xxx_002.jpg"],
    "title": "我的项目"
  }'

# 4. 开始播放
curl -X POST http://localhost:5000/api/playback/play/proj_xxx

# 5. 获取播放状态
curl http://localhost:5000/api/playback/status/proj_xxx

# 6. 暂停播放
curl -X POST http://localhost:5000/api/playback/pause/proj_xxx

# 7. 导出视频
curl -X POST http://localhost:5000/api/export/start/proj_xxx \
  -H "Content-Type: application/json" \
  -d '{
    "resolution": "1920x1080",
    "fps": 30
  }'
```

---

## 开发状态

### 已完成的API ✅

- ✅ 文件管理 API（完整）
- ✅ 项目管理 API（完整）
- ✅ 播放控制 API（完整，15个测试全部通过）

### 待开发的API

- ⏳ 视频导出 API（规划中）
- ⏳ 字幕管理 API（规划中）
- ⏳ 配置管理 API（规划中）

---

## 技术说明

### 架构设计

- **后端框架**: Flask 3.0.0
- **会话管理**: Flask-Session
- **文件处理**: Werkzeug
- **音频处理**: pygame, ffprobe
- **图片处理**: Pillow
- **视频导出**: FFmpeg

### 性能优化

- 文件上传使用流式处理，支持大文件
- 播放器状态查询建议使用轮询（100-500ms间隔）
- 导出任务在后台线程执行，不阻塞API响应

### 安全考虑

- 文件路径安全验证，防止路径遍历攻击
- 文件类型和大小限制
- 会话隔离，多用户数据互不干扰
- 定期清理过期会话和临时文件

---

## 参考文档

- [实施计划](./implementation_plan.md)
- [播放器模块文档](./播放器模块文档.md)
- [PlaybackAPI测试问题修复总结](./test_playback_api_fixes.md)

---

**文档版本**: v2.2  
**最后更新**: 2025-10-25  
**API状态**: 播放控制API已完成并通过测试
