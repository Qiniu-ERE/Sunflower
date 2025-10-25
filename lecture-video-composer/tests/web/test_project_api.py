"""
项目管理API测试
"""
import pytest
import json
import os
from pathlib import Path
from io import BytesIO


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture
def session_id(client):
    """创建测试会话"""
    response = client.post('/api/session/create')
    data = json.loads(response.data)
    return data['session_id']


@pytest.fixture
def uploaded_files(client, session_id, temp_dir):
    """上传测试文件并返回文件路径"""
    # 上传音频
    audio_data = {
        'file': (BytesIO(b'fake audio content'), 'test.mp3'),
        'session_id': session_id
    }
    audio_response = client.post(
        '/api/file/upload/audio',
        data=audio_data,
        content_type='multipart/form-data'
    )
    audio_result = json.loads(audio_response.data)
    # API返回结构: { success: True, data: { path: '...', ... } }
    audio_file = audio_result['data']['path']
    
    # 上传照片
    photo1 = (BytesIO(b'fake image 1'), 'photo1.jpg')
    photo2 = (BytesIO(b'fake image 2'), 'photo2.jpg')
    photos_data = {
        'files': [photo1, photo2],
        'session_id': session_id
    }
    photos_response = client.post(
        '/api/file/upload/photos',
        data=photos_data,
        content_type='multipart/form-data'
    )
    photos_result = json.loads(photos_response.data)
    # API返回结构: { success: True, data: { uploaded: [{path: '...'}, ...] } }
    photo_files = [item['path'] for item in photos_result['data']['uploaded']]
    
    return {
        'audio_file': audio_file,
        'photo_files': photo_files
    }


def test_create_project_success(client, session_id, uploaded_files):
    """测试创建项目成功"""
    project_data = {
        'session_id': session_id,
        'title': 'Test Project',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    
    response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert 'project_id' in result
    assert result['title'] == 'Test Project'
    assert 'metadata' in result


def test_create_project_missing_fields(client, session_id):
    """测试创建项目缺少必需字段"""
    project_data = {
        'session_id': session_id,
        'title': 'Test Project'
        # 缺少 audio_file 和 photo_files
    }
    
    response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False


def test_create_project_no_session(client, uploaded_files):
    """测试创建项目缺少会话ID"""
    project_data = {
        'title': 'Test Project',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    
    response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False


def test_load_project(client, session_id, uploaded_files):
    """测试加载项目"""
    # 先创建项目
    project_data = {
        'session_id': session_id,
        'title': 'Test Project',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    create_response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    create_result = json.loads(create_response.data)
    project_id = create_result['project_id']
    
    # 加载项目
    response = client.get(
        f'/api/project/load/{project_id}?session_id={session_id}'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert result['project_id'] == project_id
    assert result['title'] == 'Test Project'


def test_load_project_not_found(client, session_id):
    """测试加载不存在的项目"""
    response = client.get(
        f'/api/project/load/nonexistent?session_id={session_id}'
    )
    
    assert response.status_code == 404
    result = json.loads(response.data)
    assert result['success'] is False


def test_list_projects(client, session_id, uploaded_files):
    """测试列出所有项目"""
    # 创建两个项目
    for i in range(2):
        project_data = {
            'session_id': session_id,
            'title': f'Test Project {i+1}',
            'audio_file': uploaded_files['audio_file'],
            'photo_files': uploaded_files['photo_files']
        }
        client.post(
            '/api/project/create',
            data=json.dumps(project_data),
            content_type='application/json'
        )
    
    # 列出项目
    response = client.get(f'/api/project/list?session_id={session_id}')
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert 'projects' in result
    assert len(result['projects']) == 2


def test_get_current_project(client, session_id, uploaded_files):
    """测试获取当前项目"""
    # 创建项目
    project_data = {
        'session_id': session_id,
        'title': 'Current Project',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    create_response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    create_result = json.loads(create_response.data)
    project_id = create_result['project_id']
    
    # 设置为当前项目
    client.post(
        f'/api/project/set-current/{project_id}?session_id={session_id}'
    )
    
    # 获取当前项目
    response = client.get(f'/api/project/current?session_id={session_id}')
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert result['project_id'] == project_id


def test_get_current_project_none(client, session_id):
    """测试获取当前项目（无当前项目）"""
    response = client.get(f'/api/project/current?session_id={session_id}')
    
    assert response.status_code == 404
    result = json.loads(response.data)
    assert result['success'] is False


def test_set_current_project(client, session_id, uploaded_files):
    """测试设置当前项目"""
    # 创建项目
    project_data = {
        'session_id': session_id,
        'title': 'Test Project',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    create_response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    create_result = json.loads(create_response.data)
    project_id = create_result['project_id']
    
    # 设置为当前项目
    response = client.post(
        f'/api/project/set-current/{project_id}?session_id={session_id}'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert result['project_id'] == project_id


def test_delete_project(client, session_id, uploaded_files):
    """测试删除项目"""
    # 创建项目
    project_data = {
        'session_id': session_id,
        'title': 'Test Project',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    create_response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    create_result = json.loads(create_response.data)
    project_id = create_result['project_id']
    
    # 删除项目
    response = client.delete(
        f'/api/project/delete/{project_id}?session_id={session_id}'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True


def test_delete_project_not_found(client, session_id):
    """测试删除不存在的项目"""
    response = client.delete(
        f'/api/project/delete/nonexistent?session_id={session_id}'
    )
    
    assert response.status_code == 404
    result = json.loads(response.data)
    assert result['success'] is False


def test_get_project_metadata(client, session_id, uploaded_files):
    """测试获取项目元数据"""
    # 创建项目
    project_data = {
        'session_id': session_id,
        'title': 'Test Project',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    create_response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    create_result = json.loads(create_response.data)
    project_id = create_result['project_id']
    
    # 获取元数据
    response = client.get(
        f'/api/project/metadata/{project_id}?session_id={session_id}'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert 'metadata' in result
    assert result['metadata']['project_id'] == project_id
    assert 'duration' in result['metadata']
    assert 'photo_count' in result['metadata']


def test_update_project(client, session_id, uploaded_files):
    """测试更新项目信息"""
    # 创建项目
    project_data = {
        'session_id': session_id,
        'title': 'Original Title',
        'audio_file': uploaded_files['audio_file'],
        'photo_files': uploaded_files['photo_files']
    }
    create_response = client.post(
        '/api/project/create',
        data=json.dumps(project_data),
        content_type='application/json'
    )
    create_result = json.loads(create_response.data)
    project_id = create_result['project_id']
    
    # 更新项目
    update_data = {
        'session_id': session_id,
        'title': 'Updated Title'
    }
    response = client.put(
        f'/api/project/update/{project_id}',
        data=json.dumps(update_data),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert result['title'] == 'Updated Title'


def test_update_project_not_found(client, session_id):
    """测试更新不存在的项目"""
    update_data = {
        'session_id': session_id,
        'title': 'Updated Title'
    }
    response = client.put(
        f'/api/project/update/nonexistent',
        data=json.dumps(update_data),
        content_type='application/json'
    )
    
    assert response.status_code == 404
    result = json.loads(response.data)
    assert result['success'] is False
