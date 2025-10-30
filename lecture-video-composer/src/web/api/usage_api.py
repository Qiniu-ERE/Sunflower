"""
用量计费API
提供用户使用量统计和查询功能
"""
from flask import Blueprint, jsonify, request, session
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import logging

usage_bp = Blueprint('usage', __name__)
logger = logging.getLogger(__name__)


def get_session_manager():
    """获取会话管理器实例"""
    from ..app import session_manager
    return session_manager


def init_usage_data() -> Dict[str, Any]:
    """初始化使用数据结构"""
    return {
        'projects_created': 0,
        'videos_exported': 0,
        'total_export_duration': 0.0,  # 秒
        'total_storage_used': 0,  # 字节
        'files_uploaded': {
            'audio': 0,
            'photos': 0
        },
        'history': [],  # 使用历史记录
        'limits': {
            'max_projects': 10,
            'max_export_duration': 3600,  # 1小时
            'max_storage_mb': 500,  # 500MB
            'max_videos_per_day': 5
        }
    }


@usage_bp.route('/stats', methods=['GET'])
def get_usage_stats():
    """
    获取当前用户的使用统计
    
    Returns:
        JSON响应，包含用户的使用统计数据
    """
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No active session'
            }), 401
        
        sm = get_session_manager()
        
        # 获取或初始化使用数据
        usage_data = sm.get_session_data(session_id, 'usage_stats')
        if not usage_data:
            usage_data = init_usage_data()
            sm.set_session_data(session_id, 'usage_stats', usage_data)
        
        # 计算百分比
        stats = {
            'projects': {
                'used': usage_data['projects_created'],
                'limit': usage_data['limits']['max_projects'],
                'percentage': min(100, int(usage_data['projects_created'] / usage_data['limits']['max_projects'] * 100))
            },
            'exports': {
                'used': usage_data['videos_exported'],
                'limit': usage_data['limits']['max_videos_per_day'],
                'percentage': min(100, int(usage_data['videos_exported'] / usage_data['limits']['max_videos_per_day'] * 100))
            },
            'duration': {
                'used': int(usage_data['total_export_duration']),
                'limit': usage_data['limits']['max_export_duration'],
                'percentage': min(100, int(usage_data['total_export_duration'] / usage_data['limits']['max_export_duration'] * 100)),
                'formatted': format_duration(usage_data['total_export_duration'])
            },
            'storage': {
                'used': usage_data['total_storage_used'],
                'limit': usage_data['limits']['max_storage_mb'] * 1024 * 1024,
                'percentage': min(100, int(usage_data['total_storage_used'] / (usage_data['limits']['max_storage_mb'] * 1024 * 1024) * 100)),
                'formatted': format_size(usage_data['total_storage_used'])
            },
            'files': usage_data['files_uploaded'],
            'history': usage_data['history'][-10:]  # 最近10条记录
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@usage_bp.route('/record/upload', methods=['POST'])
def record_upload():
    """
    记录文件上传
    
    Request Body:
        file_type: 文件类型 ('audio' 或 'photo')
        file_size: 文件大小（字节）
    """
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No active session'
            }), 401
        
        data = request.get_json()
        file_type = data.get('file_type')
        file_size = data.get('file_size', 0)
        
        if file_type not in ['audio', 'photos']:
            return jsonify({
                'success': False,
                'error': 'Invalid file type'
            }), 400
        
        sm = get_session_manager()
        usage_data = sm.get_session_data(session_id, 'usage_stats')
        if not usage_data:
            usage_data = init_usage_data()
        
        # 更新统计
        usage_data['files_uploaded'][file_type] += 1
        usage_data['total_storage_used'] += file_size
        
        # 添加历史记录
        usage_data['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'upload',
            'type': file_type,
            'size': file_size,
            'description': f'上传{get_file_type_name(file_type)}'
        })
        
        sm.set_session_data(session_id, 'usage_stats', usage_data)
        
        return jsonify({
            'success': True,
            'message': 'Upload recorded'
        })
    
    except Exception as e:
        logger.error(f"Error recording upload: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@usage_bp.route('/record/project', methods=['POST'])
def record_project_creation():
    """
    记录项目创建
    
    Request Body:
        project_name: 项目名称
    """
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No active session'
            }), 401
        
        data = request.get_json()
        project_name = data.get('project_name', '未命名项目')
        
        sm = get_session_manager()
        usage_data = sm.get_session_data(session_id, 'usage_stats')
        if not usage_data:
            usage_data = init_usage_data()
        
        # 检查是否超过限制
        if usage_data['projects_created'] >= usage_data['limits']['max_projects']:
            return jsonify({
                'success': False,
                'error': f"已达到项目创建上限（{usage_data['limits']['max_projects']}个）"
            }), 403
        
        # 更新统计
        usage_data['projects_created'] += 1
        
        # 添加历史记录
        usage_data['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'create_project',
            'description': f'创建项目：{project_name}'
        })
        
        sm.set_session_data(session_id, 'usage_stats', usage_data)
        
        return jsonify({
            'success': True,
            'message': 'Project creation recorded'
        })
    
    except Exception as e:
        logger.error(f"Error recording project creation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@usage_bp.route('/record/export', methods=['POST'])
def record_export():
    """
    记录视频导出
    
    Request Body:
        duration: 视频时长（秒）
        file_size: 文件大小（字节）
        resolution: 分辨率（如 "720p"）
    """
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No active session'
            }), 401
        
        data = request.get_json()
        duration = data.get('duration', 0)
        file_size = data.get('file_size', 0)
        resolution = data.get('resolution', '720p')
        
        sm = get_session_manager()
        usage_data = sm.get_session_data(session_id, 'usage_stats')
        if not usage_data:
            usage_data = init_usage_data()
        
        # 检查是否超过限制
        if usage_data['videos_exported'] >= usage_data['limits']['max_videos_per_day']:
            return jsonify({
                'success': False,
                'error': f"今日已达到导出上限（{usage_data['limits']['max_videos_per_day']}个）"
            }), 403
        
        if usage_data['total_export_duration'] + duration > usage_data['limits']['max_export_duration']:
            return jsonify({
                'success': False,
                'error': f"导出时长已达到上限（{usage_data['limits']['max_export_duration']}秒）"
            }), 403
        
        # 更新统计
        usage_data['videos_exported'] += 1
        usage_data['total_export_duration'] += duration
        usage_data['total_storage_used'] += file_size
        
        # 添加历史记录
        usage_data['history'].append({
            'timestamp': datetime.now().isoformat(),
            'action': 'export',
            'duration': duration,
            'size': file_size,
            'resolution': resolution,
            'description': f'导出{resolution}视频（{format_duration(duration)}）'
        })
        
        sm.set_session_data(session_id, 'usage_stats', usage_data)
        
        return jsonify({
            'success': True,
            'message': 'Export recorded'
        })
    
    except Exception as e:
        logger.error(f"Error recording export: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@usage_bp.route('/limits', methods=['GET'])
def get_limits():
    """获取使用限制"""
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No active session'
            }), 401
        
        sm = get_session_manager()
        usage_data = sm.get_session_data(session_id, 'usage_stats')
        if not usage_data:
            usage_data = init_usage_data()
        
        return jsonify({
            'success': True,
            'limits': usage_data['limits']
        })
    
    except Exception as e:
        logger.error(f"Error getting limits: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@usage_bp.route('/reset', methods=['POST'])
def reset_usage():
    """重置使用统计（仅用于测试）"""
    try:
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No active session'
            }), 401
        
        sm = get_session_manager()
        usage_data = init_usage_data()
        sm.set_session_data(session_id, 'usage_stats', usage_data)
        
        return jsonify({
            'success': True,
            'message': 'Usage stats reset'
        })
    
    except Exception as e:
        logger.error(f"Error resetting usage: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# 辅助函数
def format_duration(seconds: float) -> str:
    """格式化时长"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}小时{minutes}分钟"
    elif minutes > 0:
        return f"{minutes}分钟{secs}秒"
    else:
        return f"{secs}秒"


def format_size(bytes_size: int) -> str:
    """格式化文件大小"""
    size_float = float(bytes_size)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_float < 1024.0:
            return f"{size_float:.1f} {unit}"
        size_float /= 1024.0
    return f"{size_float:.1f} TB"


def get_file_type_name(file_type: str) -> str:
    """获取文件类型的中文名称"""
    names = {
        'audio': '音频文件',
        'photos': '照片文件'
    }
    return names.get(file_type, file_type)


def record_usage_internal(session_id: str, action: str, project_id: str = None, metadata: Dict = None):
    """
    内部使用的用量记录函数，供其他模块调用
    
    Args:
        session_id: 会话ID
        action: 操作类型 ('upload', 'create_project', 'export')
        project_id: 项目ID（可选）
        metadata: 额外的元数据（可选）
    """
    try:
        sm = get_session_manager()
        usage_data = sm.get_session_data(session_id, 'usage_stats')
        if not usage_data:
            usage_data = init_usage_data()
        
        # 根据操作类型更新统计
        if action == 'upload':
            file_type = metadata.get('file_type', 'audio')
            file_size = metadata.get('file_size', 0)
            usage_data['files_uploaded'][file_type] += 1
            usage_data['total_storage_used'] += file_size
            
            usage_data['history'].append({
                'timestamp': datetime.now().isoformat(),
                'action': 'upload',
                'type': file_type,
                'size': file_size,
                'description': f'上传{get_file_type_name(file_type)}'
            })
        
        elif action == 'create_project':
            project_name = metadata.get('project_name', '未命名项目') if metadata else '未命名项目'
            usage_data['projects_created'] += 1
            
            usage_data['history'].append({
                'timestamp': datetime.now().isoformat(),
                'action': 'create_project',
                'project_id': project_id,
                'description': f'创建项目：{project_name}'
            })
        
        elif action == 'export':
            duration = metadata.get('duration', 0) if metadata else 0
            file_size = metadata.get('file_size', 0) if metadata else 0
            resolution = metadata.get('resolution', '720p') if metadata else '720p'
            ai_subtitle = metadata.get('ai_subtitle', False) if metadata else False
            
            usage_data['videos_exported'] += 1
            usage_data['total_export_duration'] += duration
            if file_size > 0:
                usage_data['total_storage_used'] += file_size
            
            desc = f'导出{resolution}视频（{format_duration(duration)}）'
            if ai_subtitle:
                desc += ' - 含AI字幕'
            
            usage_data['history'].append({
                'timestamp': datetime.now().isoformat(),
                'action': 'export',
                'project_id': project_id,
                'duration': duration,
                'size': file_size,
                'resolution': resolution,
                'ai_subtitle': ai_subtitle,
                'description': desc
            })
        
        # 保存更新后的数据
        sm.set_session_data(session_id, 'usage_stats', usage_data)
        logger.info(f"Usage recorded: {action} for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error in record_usage_internal: {e}")
        raise
