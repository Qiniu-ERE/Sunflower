"""
Web模块测试fixture
"""
import pytest
import tempfile
from pathlib import Path
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.web.app import create_app


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def app(temp_dir):
    """创建Flask应用实例用于测试"""
    # 创建测试配置应用
    app = create_app('testing')
    
    # 覆盖配置为测试目录
    app.config['SESSION_FILE_DIR'] = str(temp_dir)
    app.config['UPLOAD_FOLDER'] = str(temp_dir / 'uploads')
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    # 确保上传目录存在
    upload_dir = Path(app.config['UPLOAD_FOLDER'])
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 重新初始化session_manager使用测试目录
    from src.web.app import session_manager
    import src.web.app as web_app
    web_app.session_manager = web_app.SessionManager(
        session_dir=app.config['SESSION_FILE_DIR'],
        max_age=app.config['PERMANENT_SESSION_LIFETIME']
    )
    
    yield app


@pytest.fixture
def client(app):
    """创建测试客户端"""
    return app.test_client()


@pytest.fixture
def session_id(client):
    """创建测试会话"""
    import json
    response = client.post('/api/session/create')
    data = json.loads(response.data)
    return data['session_id']
