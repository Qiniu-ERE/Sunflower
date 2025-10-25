"""
播放控制API
提供音频播放控制、状态查询等功能
"""
from flask import Blueprint, request, jsonify, current_app
from pathlib import Path
from typing import Optional, Dict, Any
import logging

from ...core.player.sync_coordinator import SyncCoordinator
from ...core.player.playback_controller import PlaybackController
from ...core.player.photo_display import PhotoDisplayManager
from ..services.session_manager import SessionManager


# 创建蓝图
playback_bp = Blueprint('playback', __name__)

# 播放器实例缓存 {session_id: {project_id: coordinator}}
_coordinators: Dict[str, Dict[str, SyncCoordinator]] = {}


def get_or_create_coordinator(session_id: str, project_id: str, 
                              session_manager: SessionManager) -> Optional[SyncCoordinator]:
    """
    获取或创建SyncCoordinator实例
    
    Args:
        session_id: 会话ID
        project_id: 项目ID
        session_manager: 会话管理器
        
    Returns:
        SyncCoordinator实例，失败返回None
    """
    # 检查缓存
    if session_id in _coordinators and project_id in _coordinators[session_id]:
        return _coordinators[session_id][project_id]
    
    # 获取项目信息
    project = session_manager.get_project(session_id, project_id)
    if not project:
        return None
    
    try:
        # 创建播放控制器组件
        playback_controller = PlaybackController()
        
        # 加载音频文件
        audio_file = Path(project.audio_file)
        if not playback_controller.load(audio_file):
            current_app.logger.error(f"Failed to load audio file: {audio_file}")
            return None
        
        photo_display = PhotoDisplayManager()
        
        # 加载元数据获取时间轴
        metadata_path = Path(project.metadata_path)
        if not metadata_path.exists():
            current_app.logger.error(f"Metadata file not found: {metadata_path}")
            return None
        
        import json
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        timeline = metadata.get('timeline', [])
        
        # 创建协调器
        coordinator = SyncCoordinator(
            playback_controller=playback_controller,
            photo_display=photo_display,
            timeline=timeline
        )
        
        # 缓存实例
        if session_id not in _coordinators:
            _coordinators[session_id] = {}
        _coordinators[session_id][project_id] = coordinator
        
        current_app.logger.info(f"Created coordinator for project {project_id}")
        return coordinator
        
    except Exception as e:
        current_app.logger.error(f"Error creating coordinator: {e}", exc_info=True)
        return None


@playback_bp.route('/play', methods=['POST'])
def play():
    """
    开始播放
    
    请求JSON：
        {
            "session_id": "会话ID",
            "project_id": "项目ID"
        }
    
    返回：
        {
            "success": true/false,
            "message": "消息",
            "data": {
                "state": "playing",
                "position": 0.0,
                "duration": 123.45
            }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        session_id = data.get('session_id')
        project_id = data.get('project_id')
        
        if not session_id or not project_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id or project_id'
            }), 400
        
        # 从app获取session_manager
        from ..app import session_manager
        
        # 获取或创建协调器
        coordinator = get_or_create_coordinator(session_id, project_id, session_manager)
        if not coordinator:
            return jsonify({
                'success': False,
                'error': '无法加载项目或创建播放器'
            }), 404
        
        # 开始播放
        coordinator.play()
        
        # 获取状态
        status = coordinator.get_status()
        
        return jsonify({
            'success': True,
            'message': '开始播放',
            'data': {
                'state': status['state'],
                'position': status['position'],
                'duration': status['duration'],
                'current_photo': status.get('current_photo')
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error starting playback: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'播放失败: {str(e)}'
        }), 500


@playback_bp.route('/pause', methods=['POST'])
def pause():
    """
    暂停播放
    
    请求JSON：
        {
            "session_id": "会话ID",
            "project_id": "项目ID"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        session_id = data.get('session_id')
        project_id = data.get('project_id')
        
        if not session_id or not project_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id or project_id'
            }), 400
        
        # 从缓存获取协调器
        if session_id not in _coordinators or project_id not in _coordinators[session_id]:
            return jsonify({
                'success': False,
                'error': '播放器未初始化'
            }), 404
        
        coordinator = _coordinators[session_id][project_id]
        coordinator.pause()
        
        status = coordinator.get_status()
        
        return jsonify({
            'success': True,
            'message': '已暂停',
            'data': {
                'state': status['state'],
                'position': status['position']
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error pausing playback: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'暂停失败: {str(e)}'
        }), 500


@playback_bp.route('/stop', methods=['POST'])
def stop():
    """
    停止播放
    
    请求JSON：
        {
            "session_id": "会话ID",
            "project_id": "项目ID"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        session_id = data.get('session_id')
        project_id = data.get('project_id')
        
        if not session_id or not project_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id or project_id'
            }), 400
        
        # 从缓存获取协调器
        if session_id not in _coordinators or project_id not in _coordinators[session_id]:
            return jsonify({
                'success': False,
                'error': '播放器未初始化'
            }), 404
        
        coordinator = _coordinators[session_id][project_id]
        coordinator.stop()
        
        status = coordinator.get_status()
        
        return jsonify({
            'success': True,
            'message': '已停止',
            'data': {
                'state': status['state'],
                'position': status['position']
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error stopping playback: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'停止失败: {str(e)}'
        }), 500


@playback_bp.route('/seek', methods=['POST'])
def seek():
    """
    跳转到指定位置
    
    请求JSON：
        {
            "session_id": "会话ID",
            "project_id": "项目ID",
            "position": 12.34  # 秒
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        session_id = data.get('session_id')
        project_id = data.get('project_id')
        position = data.get('position')
        
        if not session_id or not project_id or position is None:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        try:
            position = float(position)
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'Invalid position value'
            }), 400
        
        # 从缓存获取协调器
        if session_id not in _coordinators or project_id not in _coordinators[session_id]:
            return jsonify({
                'success': False,
                'error': '播放器未初始化'
            }), 404
        
        coordinator = _coordinators[session_id][project_id]
        coordinator.seek(position)
        
        status = coordinator.get_status()
        
        return jsonify({
            'success': True,
            'message': f'已跳转到 {position:.2f}秒',
            'data': {
                'state': status['state'],
                'position': status['position'],
                'current_photo': status.get('current_photo')
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error seeking: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'跳转失败: {str(e)}'
        }), 500


@playback_bp.route('/volume', methods=['POST'])
def set_volume():
    """
    设置音量
    
    请求JSON：
        {
            "session_id": "会话ID",
            "project_id": "项目ID",
            "volume": 0.8  # 0.0-1.0
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        session_id = data.get('session_id')
        project_id = data.get('project_id')
        volume = data.get('volume')
        
        if not session_id or not project_id or volume is None:
            return jsonify({
                'success': False,
                'error': 'Missing required parameters'
            }), 400
        
        try:
            volume = float(volume)
            if not 0.0 <= volume <= 1.0:
                raise ValueError("Volume must be between 0.0 and 1.0")
        except (TypeError, ValueError) as e:
            return jsonify({
                'success': False,
                'error': f'Invalid volume value: {str(e)}'
            }), 400
        
        # 从缓存获取协调器
        if session_id not in _coordinators or project_id not in _coordinators[session_id]:
            return jsonify({
                'success': False,
                'error': '播放器未初始化'
            }), 404
        
        coordinator = _coordinators[session_id][project_id]
        coordinator.set_volume(volume)
        
        return jsonify({
            'success': True,
            'message': f'音量已设置为 {int(volume * 100)}%',
            'data': {
                'volume': volume
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error setting volume: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'设置音量失败: {str(e)}'
        }), 500


@playback_bp.route('/status', methods=['GET'])
def get_status():
    """
    获取播放状态
    
    查询参数：
        session_id: 会话ID
        project_id: 项目ID
    
    返回：
        {
            "success": true/false,
            "data": {
                "state": "playing/paused/stopped",
                "position": 12.34,
                "duration": 123.45,
                "current_photo": "photo_path.jpg",
                "volume": 0.8,
                "timeline_index": 5
            }
        }
    """
    try:
        session_id = request.args.get('session_id')
        project_id = request.args.get('project_id')
        
        if not session_id or not project_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id or project_id'
            }), 400
        
        # 从缓存获取协调器
        if session_id not in _coordinators or project_id not in _coordinators[session_id]:
            return jsonify({
                'success': False,
                'error': '播放器未初始化'
            }), 404
        
        coordinator = _coordinators[session_id][project_id]
        status = coordinator.get_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting status: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'获取状态失败: {str(e)}'
        }), 500


@playback_bp.route('/cleanup', methods=['POST'])
def cleanup():
    """
    清理播放器资源
    
    请求JSON：
        {
            "session_id": "会话ID",
            "project_id": "项目ID" (可选，不提供则清理该会话所有项目)
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        session_id = data.get('session_id')
        project_id = data.get('project_id')
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id'
            }), 400
        
        cleaned = 0
        
        if session_id in _coordinators:
            if project_id:
                # 清理特定项目
                if project_id in _coordinators[session_id]:
                    del _coordinators[session_id][project_id]
                    cleaned = 1
                    current_app.logger.info(f"Cleaned up coordinator for project {project_id}")
            else:
                # 清理该会话的所有项目
                cleaned = len(_coordinators[session_id])
                del _coordinators[session_id]
                current_app.logger.info(f"Cleaned up {cleaned} coordinators for session {session_id}")
        
        return jsonify({
            'success': True,
            'message': f'已清理 {cleaned} 个播放器实例',
            'data': {
                'cleaned_count': cleaned
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error cleaning up: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'清理失败: {str(e)}'
        }), 500
