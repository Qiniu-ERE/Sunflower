# PlaybackAPI 单元测试问题修复总结

## 概述

本文档记录了 `tests/web/test_playback_api.py` 单元测试中遇到的所有问题及其解决方案。

**测试文件**: `lecture-video-composer/tests/web/test_playback_api.py`  
**测试命令**: `cd lecture-video-composer && python3 -m pytest tests/web/test_playback_api.py -v`  
**最终结果**: ✅ 15/15 测试通过

---

## 问题清单

### 问题1: API响应字段不匹配

**错误信息**:
```python
KeyError: 'data'
KeyError: 'files'
KeyError: 'filename'
```

**原因分析**:
测试代码期望的响应字段与实际 API 返回的字段不一致：
- 照片上传 API 返回 `{'uploaded': [{'path': ...}]}` 而非 `{'files': [...]}`
- 音频上传 API 返回 `{'path': ...}` 而非 `{'filename': ...}`

**解决方案**:
```python
# 错误写法
audio_path = audio_result['data']['filename']  # ❌
photo_paths = [f['path'] for f in photo_result['data']['files']]  # ❌

# 正确写法
audio_path = audio_result['data']['path']  # ✅
uploaded_files = photo_result['data']['uploaded']  # ✅
photo_paths = [f['path'] for f in uploaded_files]  # ✅
```

---

### 问题2: PROJECTS_FOLDER配置缺失

**错误信息**:
```python
KeyError: 'PROJECTS_FOLDER'
```

**原因分析**:
`conftest.py` 中的 Flask app fixture 没有配置 `PROJECTS_FOLDER`，导致项目创建时找不到项目目录。

**解决方案**:
在 `tests/web/conftest.py` 中添加配置：

```python
@pytest.fixture
def app():
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app()
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = str(temp_dir)
        app.config['PROJECTS_FOLDER'] = str(temp_dir / 'projects')  # ✅ 添加此行
        
        # 创建必要的目录
        upload_dir = Path(app.config['UPLOAD_FOLDER'])
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        projects_dir = Path(app.config['PROJECTS_FOLDER'])  # ✅ 添加此行
        projects_dir.mkdir(parents=True, exist_ok=True)     # ✅ 添加此行
        
        yield app
```

---

### 问题3: LectureComposer参数名错误

**错误信息**:
```python
TypeError: __init__() got an unexpected keyword argument 'audio_path'
TypeError: __init__() got an unexpected keyword argument 'photo_paths'
```

**原因分析**:
`LectureComposer` 的构造函数参数名为 `audio_file`, `photo_files`, `output_dir`，但测试代码使用了错误的参数名。

**解决方案**:
```python
# 错误写法
composer = LectureComposer(
    audio_path=audio_file,      # ❌
    photo_paths=photo_files,    # ❌
    project_dir=project_dir     # ❌
)

# 正确写法
composer = LectureComposer(
    audio_file=audio_file,      # ✅
    photo_files=photo_files,    # ✅
    output_dir=project_dir      # ✅
)
```

---

### 问题4: 方法调用错误

**错误信息**:
```python
AttributeError: 'LectureComposer' object has no attribute 'generate_metadata'
```

**原因分析**:
`LectureComposer` 类没有 `generate_metadata()` 方法，应该使用 `process()` 方法。

**解决方案**:
```python
# 错误写法
metadata = composer.generate_metadata()  # ❌

# 正确写法
metadata = composer.process()  # ✅

# 手动构建必要的属性
composer.timeline = MagicMock()
composer.timeline.items = []
composer.audio_metadata = MagicMock()
composer.audio_metadata.duration = 60.0
```

---

### 问题5: 音频验证失败

**错误信息**:
```python
ValueError: Invalid audio file or format not supported
```

**原因分析**:
使用假数据（如 `b'fake audio data'`）创建的文件无法通过 `LectureComposer` 的真实音频格式验证。

**解决方案**:
Mock `LectureComposer` 类以避免真实的音频验证：

```python
@pytest.fixture
def project_with_files(client):
    """创建包含文件的项目"""
    # Mock LectureComposer 以避免真实文件验证
    with patch('src.web.api.project_api.LectureComposer') as mock_composer_class:
        mock_composer = MagicMock()
        mock_composer_class.return_value = mock_composer
        
        # 设置返回值
        mock_metadata = {
            'audio_duration': 60.0,
            'total_photos': 2,
            'timeline': []
        }
        mock_composer.process.return_value = mock_metadata
        mock_composer.timeline = MagicMock()
        mock_composer.timeline.items = []
        mock_composer.audio_metadata = MagicMock()
        mock_composer.audio_metadata.duration = 60.0
        
        # ... 其余代码
```

---

### 问题6: Mock路径错误

**错误信息**:
```python
ModuleNotFoundError: No module named 'lecture-video-composer'
```

**原因分析**:
使用了错误的 Mock 路径，如 `@patch('lecture-video-composer.src.web.api...')`。

**解决方案**:
使用相对于项目根目录的正确路径：

```python
# 错误写法
@patch('lecture-video-composer.src.web.api.playback_api.SyncCoordinator')  # ❌

# 正确写法
@patch('src.web.api.playback_api.SyncCoordinator')  # ✅
@patch('src.web.api.playback_api.PlaybackController')  # ✅
@patch('src.web.api.playback_api.PhotoDisplayManager')  # ✅
```

---

### 问题7: PlaybackController初始化错误

**错误信息**:
```python
TypeError: __init__() got an unexpected keyword argument 'audio_file'
```

**原因分析**:
`PlaybackController` 的构造函数不接受 `audio_file` 参数。正确的使用方式是先创建实例，然后调用 `load()` 方法。

**实际签名**:
```python
class PlaybackController:
    def __init__(self, config: Optional[PlaybackConfig] = None):
        pass
    
    def load(self, audio_file: Path) -> bool:
        pass
```

**解决方案**:
```python
# 错误写法
controller = PlaybackController(audio_file=audio_file)  # ❌

# 正确写法
controller = PlaybackController()  # ✅ 先创建实例
controller.load(audio_file)        # ✅ 再加载音频文件
```

**Mock 策略**:
```python
@patch('src.web.api.playback_api.PlaybackController')
def test_play_success(mock_playback, ...):
    # 创建 Mock 实例
    mock_controller = MagicMock()
    mock_playback.return_value = mock_controller
    
    # Mock load 方法返回 True
    mock_controller.load.return_value = True
    
    # ... 其余测试代码
```

---

### 问题8: PIL依赖缺失

**错误信息**:
```python
RuntimeError: PIL is required for photo display
```

**原因分析**:
`PhotoDisplayManager` 初始化时会检查 PIL 库的可用性，测试环境中可能缺少此依赖。

**解决方案**:
Mock `PhotoDisplayManager` 类以避免依赖检查：

```python
@patch('src.web.api.playback_api.PhotoDisplayManager')
@patch('src.web.api.playback_api.PlaybackController')
@patch('src.web.api.playback_api.SyncCoordinator')
def test_play_success(mock_sync, mock_playback, mock_photo, ...):
    # Mock PhotoDisplayManager
    mock_photo.return_value = MagicMock()  # ✅
    
    # ... 其余代码
```

---

### 问题9: Mock对象不可序列化

**错误信息**:
```python
TypeError: Object of type MagicMock is not JSON serializable
```

**原因分析**:
API 返回的 JSON 响应中包含了未序列化的 Mock 对象，如 `get_status()` 返回的某些字段。

**解决方案**:
确保所有 Mock 方法返回可序列化的字典：

```python
# 错误写法
mock_coordinator.get_status.return_value = MagicMock()  # ❌

# 正确写法
mock_coordinator.get_status.return_value = {  # ✅
    'state': 'playing',
    'position': 0.0,
    'duration': 60.0,
    'current_photo': None  # 使用 None 而不是 MagicMock
}
```

**完整示例**:
```python
@patch('src.web.api.playback_api.SyncCoordinator')
def test_play_success(mock_sync, ...):
    mock_coordinator = MagicMock()
    mock_sync.return_value = mock_coordinator
    
    # 返回完整的可序列化字典
    mock_coordinator.get_status.return_value = {
        'state': 'playing',
        'position': 0.0,
        'duration': 60.0,
        'current_photo': None
    }
```

---

### 问题10: API字段不一致

**错误信息**:
```python
KeyError: 'status'
```

**原因分析**:
测试代码期望 `'status'` 字段，但 API 实际返回 `'state'` 字段。

**解决方案**:
统一使用 `'state'` 字段：

```python
# 错误写法
assert response.json['data']['status'] == 'paused'  # ❌

# 正确写法
assert response.json['data']['state'] == 'paused'  # ✅
```

**API 响应格式**:
```python
{
    'success': True,
    'data': {
        'state': 'playing',      # ✅ 使用 'state' 而非 'status'
        'position': 0.0,
        'duration': 60.0,
        'current_photo': None
    }
}
```

---

## 最佳实践总结

### 1. Mock 策略

```python
# 完整的 Mock 模式
@patch('src.web.api.playback_api.PhotoDisplayManager')
@patch('src.web.api.playback_api.PlaybackController')
@patch('src.web.api.playback_api.SyncCoordinator')
def test_play_success(mock_sync, mock_playback, mock_photo, project_with_files, client):
    # 1. Mock PlaybackController
    mock_controller = MagicMock()
    mock_playback.return_value = mock_controller
    mock_controller.load.return_value = True
    
    # 2. Mock PhotoDisplayManager
    mock_photo.return_value = MagicMock()
    
    # 3. Mock SyncCoordinator
    mock_coordinator = MagicMock()
    mock_sync.return_value = mock_coordinator
    mock_coordinator.get_status.return_value = {
        'state': 'playing',
        'position': 0.0,
        'duration': 60.0,
        'current_photo': None
    }
    
    # 4. 执行测试
    response = client.post(f'/api/playback/play/{project_id}')
    assert response.status_code == 200
```

### 2. Fixture 配置

```python
@pytest.fixture
def app():
    """配置完整的测试应用"""
    with tempfile.TemporaryDirectory() as temp_dir:
        app = create_app()
        app.config['TESTING'] = True
        app.config['UPLOAD_FOLDER'] = str(temp_dir)
        app.config['PROJECTS_FOLDER'] = str(temp_dir / 'projects')
        
        # 创建所有必需目录
        Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
        Path(app.config['PROJECTS_FOLDER']).mkdir(parents=True, exist_ok=True)
        
        yield app
```

### 3. API 响应格式验证

```python
def test_api_response(client):
    response = client.get('/api/endpoint')
    
    # 验证响应结构
    assert response.status_code == 200
    assert 'success' in response.json
    assert 'data' in response.json
    
    # 验证字段名称
    data = response.json['data']
    assert 'state' in data  # 不是 'status'
    assert 'path' in data   # 不是 'filename'
```

### 4. Mock 对象可序列化

```python
# 始终返回可序列化的值
mock_method.return_value = {
    'field': 'value',
    'number': 123,
    'boolean': True,
    'null_field': None,  # ✅ 使用 None
    'list': [1, 2, 3]
}

# 避免返回 Mock 对象
mock_method.return_value = MagicMock()  # ❌
```

---

## 测试结果

**命令**: `cd lecture-video-composer && python3 -m pytest tests/web/test_playback_api.py -v`

**结果**: ✅ **15 passed** in 0.45s

```
tests/web/test_playback_api.py::test_play_no_session PASSED
tests/web/test_playback_api.py::test_play_project_
