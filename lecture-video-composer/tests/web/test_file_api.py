"""
文件上传API测试
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


def test_upload_audio_success(client, session_id, temp_dir):
    """测试音频文件上传成功"""
    # 创建测试音频文件
    audio_content = b'fake audio content'
    data = {
        'file': (BytesIO(audio_content), 'test_audio.mp3'),
        'session_id': session_id
    }
    
    response = client.post(
        '/api/file/upload/audio',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert 'data' in result
    assert result['data']['filename'] == 'test_audio.mp3'


def test_upload_audio_no_file(client, session_id):
    """测试音频上传缺少文件"""
    response = client.post(
        '/api/file/upload/audio',
        data={'session_id': session_id},
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False
    assert 'No file part' in result['error']


def test_upload_audio_invalid_type(client, session_id):
    """测试音频上传无效文件类型"""
    data = {
        'file': (BytesIO(b'fake content'), 'test.txt'),
        'session_id': session_id
    }
    
    response = client.post(
        '/api/file/upload/audio',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False
    assert 'Invalid file type' in result['error']


def test_upload_audio_no_session(client):
    """测试音频上传缺少会话ID"""
    data = {
        'file': (BytesIO(b'fake audio'), 'test.mp3')
    }
    
    response = client.post(
        '/api/file/upload/audio',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False
    assert 'session_id' in result['error'].lower()


def test_upload_photos_success(client, session_id, temp_dir):
    """测试照片批量上传成功"""
    photo1 = (BytesIO(b'fake image 1'), 'photo1.jpg')
    photo2 = (BytesIO(b'fake image 2'), 'photo2.png')
    
    data = {
        'files': [photo1, photo2],
        'session_id': session_id
    }
    
    response = client.post(
        '/api/file/upload/photos',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert 'data' in result
    assert len(result['data']['uploaded']) == 2
    assert result['data']['count'] == 2


def test_upload_photos_no_files(client, session_id):
    """测试照片上传缺少文件"""
    response = client.post(
        '/api/file/upload/photos',
        data={'session_id': session_id},
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False


def test_upload_photos_invalid_type(client, session_id):
    """测试照片上传无效文件类型"""
    data = {
        'files': [(BytesIO(b'fake'), 'test.txt')],
        'session_id': session_id
    }
    
    response = client.post(
        '/api/file/upload/photos',
        data=data,
        content_type='multipart/form-data'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False
    assert 'Invalid file type' in result.get('error', '') or 'Invalid file type' in str(result.get('errors', []))


def test_list_files(client, session_id, temp_dir):
    """测试文件列表"""
    # 先上传一个文件
    data = {
        'file': (BytesIO(b'fake audio'), 'test.mp3'),
        'session_id': session_id
    }
    client.post(
        '/api/file/upload/audio',
        data=data,
        content_type='multipart/form-data'
    )
    
    # 获取文件列表
    response = client.get(f'/api/file/list?session_id={session_id}')
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True
    assert 'data' in result
    assert len(result['data']['audio']) > 0


def test_list_files_no_session(client):
    """测试文件列表缺少会话ID"""
    response = client.get('/api/file/list')
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False
    assert 'session_id' in result['error'].lower()


def test_delete_file(client, session_id, temp_dir):
    """测试删除文件"""
    # 先上传一个文件
    data = {
        'file': (BytesIO(b'fake audio'), 'test_delete.mp3'),
        'session_id': session_id
    }
    upload_response = client.post(
        '/api/file/upload/audio',
        data=data,
        content_type='multipart/form-data'
    )
    upload_data = json.loads(upload_response.data)
    filepath = upload_data['data']['path']
    
    # 删除文件
    delete_data = {
        'session_id': session_id,
        'filepath': filepath
    }
    response = client.post(
        '/api/file/delete',
        data=json.dumps(delete_data),
        content_type='application/json'
    )
    
    assert response.status_code == 200
    result = json.loads(response.data)
    assert result['success'] is True


def test_delete_file_not_found(client, session_id):
    """测试删除不存在的文件"""
    delete_data = {
        'session_id': session_id,
        'filepath': 'nonexistent.mp3'
    }
    response = client.post(
        '/api/file/delete',
        data=json.dumps(delete_data),
        content_type='application/json'
    )
    
    assert response.status_code == 404
    result = json.loads(response.data)
    assert result['success'] is False


def test_delete_file_path_traversal(client, session_id):
    """测试删除文件的路径遍历攻击防护"""
    delete_data = {
        'session_id': session_id,
        'filepath': '../../../etc/passwd'
    }
    response = client.post(
        '/api/file/delete',
        data=json.dumps(delete_data),
        content_type='application/json'
    )
    
    assert response.status_code == 400
    result = json.loads(response.data)
    assert result['success'] is False
    assert 'Invalid file path' in result['error']
