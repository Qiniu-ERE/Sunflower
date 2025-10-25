"""
会话管理器单元测试
"""
import pytest
import tempfile
from pathlib import Path
import time

from src.web.services.session_manager import SessionManager, ProjectInfo, Session


class TestSessionManager:
    """测试SessionManager类"""
    
    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def session_manager(self, temp_dir):
        """创建SessionManager实例"""
        return SessionManager(session_dir=temp_dir, max_age=3600)
    
    def test_create_session(self, session_manager):
        """测试创建会话"""
        session_id = session_manager.create_session()
        
        assert session_id is not None
        assert len(session_id) == 36  # UUID格式
        
        session = session_manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id
    
    def test_get_nonexistent_session(self, session_manager):
        """测试获取不存在的会话"""
        session = session_manager.get_session("nonexistent-id")
        assert session is None
    
    def test_store_and_get_project(self, session_manager):
        """测试存储和获取项目"""
        # 创建会话
        session_id = session_manager.create_session()
        
        # 创建项目信息
        project = ProjectInfo(
            project_id="test-project-1",
            title="测试项目",
            created_at="2025-10-25",
            audio_file="test.mp3",
            photo_count=10,
            duration=120.5,
            metadata_path="/path/to/metadata.json"
        )
        
        # 存储项目
        success = session_manager.store_project(session_id, project)
        assert success is True
        
        # 获取项目
        retrieved_project = session_manager.get_project(session_id, "test-project-1")
        assert retrieved_project is not None
        assert retrieved_project.project_id == "test-project-1"
        assert retrieved_project.title == "测试项目"
        assert retrieved_project.photo_count == 10
    
    def test_get_current_project(self, session_manager):
        """测试获取当前项目"""
        # 创建会话
        session_id = session_manager.create_session()
        
        # 存储项目
        project = ProjectInfo(
            project_id="test-project-1",
            title="测试项目",
            created_at="2025-10-25",
            audio_file="test.mp3",
            photo_count=10,
            duration=120.5,
            metadata_path="/path/to/metadata.json"
        )
        session_manager.store_project(session_id, project)
        
        # 获取当前项目（应该自动设置为最新存储的项目）
        current = session_manager.get_current_project(session_id)
        assert current is not None
        assert current.project_id == "test-project-1"
    
    def test_set_current_project(self, session_manager):
        """测试设置当前项目"""
        session_id = session_manager.create_session()
        
        # 存储两个项目
        project1 = ProjectInfo(
            project_id="project-1",
            title="项目1",
            created_at="2025-10-25",
            audio_file="test1.mp3",
            photo_count=5,
            duration=60.0,
            metadata_path="/path/to/metadata1.json"
        )
        project2 = ProjectInfo(
            project_id="project-2",
            title="项目2",
            created_at="2025-10-25",
            audio_file="test2.mp3",
            photo_count=8,
            duration=90.0,
            metadata_path="/path/to/metadata2.json"
        )
        
        session_manager.store_project(session_id, project1)
        session_manager.store_project(session_id, project2)
        
        # 设置当前项目为project-1
        success = session_manager.set_current_project(session_id, "project-1")
        assert success is True
        
        current = session_manager.get_current_project(session_id)
        assert current.project_id == "project-1"
    
    def test_remove_project(self, session_manager):
        """测试移除项目"""
        session_id = session_manager.create_session()
        
        project = ProjectInfo(
            project_id="test-project-1",
            title="测试项目",
            created_at="2025-10-25",
            audio_file="test.mp3",
            photo_count=10,
            duration=120.5,
            metadata_path="/path/to/metadata.json"
        )
        
        session_manager.store_project(session_id, project)
        
        # 移除项目
        success = session_manager.remove_project(session_id, "test-project-1")
        assert success is True
        
        # 验证项目已被移除
        retrieved = session_manager.get_project(session_id, "test-project-1")
        assert retrieved is None
    
    def test_session_data(self, session_manager):
        """测试会话数据存储"""
        session_id = session_manager.create_session()
        
        # 设置数据
        session_manager.set_session_data(session_id, "key1", "value1")
        session_manager.set_session_data(session_id, "key2", 123)
        session_manager.set_session_data(session_id, "key3", {"nested": "data"})
        
        # 获取数据
        assert session_manager.get_session_data(session_id, "key1") == "value1"
        assert session_manager.get_session_data(session_id, "key2") == 123
        assert session_manager.get_session_data(session_id, "key3") == {"nested": "data"}
        assert session_manager.get_session_data(session_id, "nonexistent", "default") == "default"
    
    def test_session_persistence(self, temp_dir):
        """测试会话持久化"""
        # 创建第一个管理器并存储数据
        manager1 = SessionManager(session_dir=temp_dir, max_age=3600)
        session_id = manager1.create_session()
        
        project = ProjectInfo(
            project_id="test-project-1",
            title="测试项目",
            created_at="2025-10-25",
            audio_file="test.mp3",
            photo_count=10,
            duration=120.5,
            metadata_path="/path/to/metadata.json"
        )
        manager1.store_project(session_id, project)
        
        # 创建第二个管理器（模拟重启）
        manager2 = SessionManager(session_dir=temp_dir, max_age=3600)
        
        # 验证会话和项目已恢复
        session = manager2.get_session(session_id)
        assert session is not None
        
        retrieved_project = manager2.get_project(session_id, "test-project-1")
        assert retrieved_project is not None
        assert retrieved_project.title == "测试项目"
    
    def test_expired_session(self, temp_dir):
        """测试过期会话"""
        # 创建会话并设置很短的过期时间
        manager = SessionManager(session_dir=temp_dir, max_age=1)  # 1秒过期
        session_id = manager.create_session()
        
        # 验证会话存在
        session = manager.get_session(session_id)
        assert session is not None
        
        # 等待过期
        time.sleep(1.5)
        
        # 验证会话已过期
        session = manager.get_session(session_id)
        assert session is None
    
    def test_cleanup_expired_sessions(self, temp_dir):
        """测试清理过期会话"""
        # 创建多个会话
        manager = SessionManager(session_dir=temp_dir, max_age=1)
        session_ids = [manager.create_session() for _ in range(3)]
        
        # 验证所有会话存在
        assert manager.get_session_count() == 3
        
        # 等待过期
        time.sleep(1.5)
        
        # 清理过期会话
        count = manager.cleanup_expired_sessions()
        assert count == 3
        assert manager.get_session_count() == 0
    
    def test_session_count(self, session_manager):
        """测试会话计数"""
        assert session_manager.get_session_count() == 0
        
        session_manager.create_session()
        assert session_manager.get_session_count() == 1
        
        session_manager.create_session()
        session_manager.create_session()
        assert session_manager.get_session_count() == 3
