"""
会话管理服务
负责管理用户会话、项目状态和临时数据
"""
import uuid
import time
from pathlib import Path
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import threading


@dataclass
class ProjectInfo:
    """项目信息"""
    project_id: str
    title: str
    created_at: str
    audio_file: str
    photo_count: int
    duration: float
    metadata_path: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class Session:
    """会话对象"""
    session_id: str
    created_at: float
    last_accessed: float
    projects: Dict[str, ProjectInfo] = field(default_factory=dict)
    current_project_id: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    
    def update_access_time(self):
        """更新最后访问时间"""
        self.last_accessed = time.time()
    
    def is_expired(self, max_age: int = 86400) -> bool:
        """检查会话是否过期"""
        return time.time() - self.last_accessed > max_age


class SessionManager:
    """会话管理器"""
    
    def __init__(self, session_dir: Optional[Path] = None, max_age: int = 86400):
        """
        初始化会话管理器
        
        Args:
            session_dir: 会话存储目录
            max_age: 会话最大年龄（秒），默认24小时
        """
        self.session_dir = session_dir
        self.max_age = max_age
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.RLock()  # 使用可重入锁避免死锁
        
        # 如果指定了存储目录，加载已有会话
        if self.session_dir:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            self._load_sessions()
    
    def create_session(self) -> str:
        """
        创建新会话
        
        Returns:
            会话ID
        """
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        session = Session(
            session_id=session_id,
            created_at=current_time,
            last_accessed=current_time
        )
        
        with self._lock:
            self._sessions[session_id] = session
            self._save_session(session)
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        获取会话对象
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话对象，不存在或已过期返回None
        """
        with self._lock:
            session = self._sessions.get(session_id)
            
            if session is None:
                # 尝试从文件加载
                session = self._load_session(session_id)
                if session:
                    self._sessions[session_id] = session
            
            if session and not session.is_expired(self.max_age):
                session.update_access_time()
                self._save_session(session)
                return session
            
            # 会话不存在或已过期
            if session:
                self._remove_session(session_id)
            
            return None
    
    def store_project(self, session_id: str, project: ProjectInfo) -> bool:
        """
        存储项目到会话
        
        Args:
            session_id: 会话ID
            project: 项目信息
            
        Returns:
            是否成功
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        with self._lock:
            session.projects[project.project_id] = project
            session.current_project_id = project.project_id
            self._save_session(session)
        
        return True
    
    def get_project(self, session_id: str, project_id: str) -> Optional[ProjectInfo]:
        """
        从会话获取项目
        
        Args:
            session_id: 会话ID
            project_id: 项目ID
            
        Returns:
            项目信息
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        return session.projects.get(project_id)
    
    def get_current_project(self, session_id: str) -> Optional[ProjectInfo]:
        """
        获取当前项目
        
        Args:
            session_id: 会话ID
            
        Returns:
            当前项目信息
        """
        session = self.get_session(session_id)
        if not session or not session.current_project_id:
            return None
        
        return session.projects.get(session.current_project_id)
    
    def set_current_project(self, session_id: str, project_id: str) -> bool:
        """
        设置当前项目
        
        Args:
            session_id: 会话ID
            project_id: 项目ID
            
        Returns:
            是否成功
        """
        session = self.get_session(session_id)
        if not session or project_id not in session.projects:
            return False
        
        with self._lock:
            session.current_project_id = project_id
            self._save_session(session)
        
        return True
    
    def remove_project(self, session_id: str, project_id: str) -> bool:
        """
        从会话移除项目
        
        Args:
            session_id: 会话ID
            project_id: 项目ID
            
        Returns:
            是否成功
        """
        session = self.get_session(session_id)
        if not session or project_id not in session.projects:
            return False
        
        with self._lock:
            del session.projects[project_id]
            if session.current_project_id == project_id:
                session.current_project_id = None
            self._save_session(session)
        
        return True
    
    def set_session_data(self, session_id: str, key: str, value: Any) -> bool:
        """
        设置会话数据
        
        Args:
            session_id: 会话ID
            key: 数据键
            value: 数据值
            
        Returns:
            是否成功
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        with self._lock:
            session.data[key] = value
            self._save_session(session)
        
        return True
    
    def get_session_data(self, session_id: str, key: str, default: Any = None) -> Any:
        """
        获取会话数据
        
        Args:
            session_id: 会话ID
            key: 数据键
            default: 默认值
            
        Returns:
            数据值
        """
        session = self.get_session(session_id)
        if not session:
            return default
        
        return session.data.get(key, default)
    
    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话
        
        Returns:
            清理的会话数量
        """
        expired_sessions = []
        
        with self._lock:
            for session_id, session in list(self._sessions.items()):
                if session.is_expired(self.max_age):
                    expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self._remove_session(session_id)
        
        return len(expired_sessions)
    
    def _save_session(self, session: Session):
        """保存会话到文件"""
        if not self.session_dir:
            return
        
        session_file = self.session_dir / f"{session.session_id}.json"
        
        # 转换为可序列化格式
        session_data = {
            'session_id': session.session_id,
            'created_at': session.created_at,
            'last_accessed': session.last_accessed,
            'current_project_id': session.current_project_id,
            'projects': {
                pid: proj.to_dict() for pid, proj in session.projects.items()
            },
            'data': session.data
        }
        
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving session {session.session_id}: {e}")
    
    def _load_session(self, session_id: str) -> Optional[Session]:
        """从文件加载会话"""
        if not self.session_dir:
            return None
        
        session_file = self.session_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # 重建ProjectInfo对象
            projects = {
                pid: ProjectInfo(**proj_data)
                for pid, proj_data in session_data.get('projects', {}).items()
            }
            
            session = Session(
                session_id=session_data['session_id'],
                created_at=session_data['created_at'],
                last_accessed=session_data['last_accessed'],
                current_project_id=session_data.get('current_project_id'),
                projects=projects,
                data=session_data.get('data', {})
            )
            
            return session
        except Exception as e:
            print(f"Error loading session {session_id}: {e}")
            return None
    
    def _load_sessions(self):
        """加载所有已保存的会话"""
        if not self.session_dir or not self.session_dir.exists():
            return
        
        for session_file in self.session_dir.glob("*.json"):
            session_id = session_file.stem
            session = self._load_session(session_id)
            if session and not session.is_expired(self.max_age):
                self._sessions[session_id] = session
    
    def _remove_session(self, session_id: str):
        """移除会话"""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
        
        if self.session_dir:
            session_file = self.session_dir / f"{session_id}.json"
            if session_file.exists():
                try:
                    session_file.unlink()
                except Exception as e:
                    print(f"Error removing session file {session_id}: {e}")
    
    def get_session_count(self) -> int:
        """获取活跃会话数量"""
        with self._lock:
            return len(self._sessions)
    
    def get_all_session_ids(self) -> List[str]:
        """获取所有会话ID"""
        with self._lock:
            return list(self._sessions.keys())
