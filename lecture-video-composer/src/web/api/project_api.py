"""
项目管理API
处理项目的创建、加载、保存和删除
"""
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from flask import Blueprint, request, jsonify, current_app, session

from ..services.session_manager import SessionManager, ProjectInfo
from ...core.lecture_composer import LectureComposer


# 创建蓝图
project_bp = Blueprint('project', __name__)


def get_session_manager() -> SessionManager:
    """获取会话管理器实例"""
    from ..app import session_manager
    return session_manager


@project_bp.route('/create', methods=['POST'])
def create_project():
    """
    创建新项目
    
    请求：
        JSON数据，包含：
        - session_id: 会话ID
        - audio_file: 音频文件路径（可以是完整路径或相对路径）
        - photo_files: 照片文件路径列表
        - title: 项目标题（可选）
        
    返回：
        JSON响应，包含项目信息
    """
    try:
        data = request.get_json()
        
        # 验证请求数据
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        # 检查session_id
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        if 'audio_file' not in data:
            return jsonify({
                'success': False,
                'error': '缺少音频文件路径'
            }), 400
        
        if 'photo_files' not in data or not data['photo_files']:
            return jsonify({
                'success': False,
                'error': '缺少照片文件'
            }), 400
        
        # 获取上传目录
        upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / session_id
        
        # 获取文件路径（可能是完整路径或相对路径）
        audio_file = Path(data['audio_file'])
        photo_files = [Path(p) for p in data['photo_files']]
        
        # 如果是相对路径，加上上传目录前缀
        if not audio_file.is_absolute():
            audio_file = upload_dir / audio_file
            photo_files = [upload_dir / p for p in photo_files]
        
        # 验证文件存在
        if not audio_file.exists():
            return jsonify({
                'success': False,
                'error': f'音频文件不存在: {data["audio_path"]}'
            }), 404
        
        for photo_path in photo_files:
            if not photo_path.exists():
                return jsonify({
                    'success': False,
                    'error': f'照片文件不存在: {photo_path.name}'
                }), 404
        
        # 生成项目ID
        project_id = str(uuid.uuid4())
        project_title = data.get('title', f'Project {datetime.now().strftime("%Y%m%d_%H%M%S")}')
        
        # 创建项目目录
        project_dir = Path(current_app.config['PROJECTS_FOLDER']) / session_id / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建项目内的audio和photos子目录
        project_audio_dir = project_dir / 'audio'
        project_photos_dir = project_dir / 'photos'
        project_audio_dir.mkdir(exist_ok=True)
        project_photos_dir.mkdir(exist_ok=True)
        
        current_app.logger.info(f"Creating project: {project_id}")
        current_app.logger.info(f"Audio: {audio_file}")
        current_app.logger.info(f"Photos: {len(photo_files)} files")
        
        # 复制文件到项目目录（独立存储，避免被删除影响）
        import shutil
        
        # 复制音频文件
        project_audio_file = project_audio_dir / audio_file.name
        shutil.copy2(audio_file, project_audio_file)
        current_app.logger.info(f"Copied audio to: {project_audio_file}")
        
        # 复制照片文件
        project_photo_files = []
        for photo_file in photo_files:
            project_photo_file = project_photos_dir / photo_file.name
            shutil.copy2(photo_file, project_photo_file)
            project_photo_files.append(project_photo_file)
        current_app.logger.info(f"Copied {len(project_photo_files)} photos to project directory")
        
        # 使用项目目录中的文件进行处理
        audio_file = project_audio_file
        photo_files = project_photo_files
        
        # 使用LectureComposer处理
        try:
            composer = LectureComposer(
                audio_file=audio_file,
                photo_files=photo_files,
                output_dir=project_dir
            )
            
            # 处理项目但不保存（我们会手动保存元数据）
            project_metadata = composer.process(title=project_title, save=False)
            
            # 保存元数据到项目目录
            metadata_path = project_dir / 'metadata.json'
            
            # 转换时间轴为简单格式
            timeline_items = []
            if composer.timeline:
                for item in composer.timeline.items:
                    timeline_items.append({
                        'timestamp': item.timestamp.isoformat(),
                        'offset': item.offset_seconds,
                        'photo': item.file_path.name,
                        'duration': item.duration
                    })
            
            # 增强元数据 - 使用项目内的相对路径
            enhanced_metadata = {
                'project_id': project_id,
                'title': project_title,
                'created_at': datetime.now().isoformat(),
                'audio_file': f'audio/{audio_file.name}',
                'photo_count': len(photo_files),
                'photo_files': [f'photos/{p.name}' for p in photo_files],
                'duration': composer.audio_metadata.duration if composer.audio_metadata else 0,
                'timeline': timeline_items,
                'version': 'v2.2'
            }
            
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False)
            
            current_app.logger.info(f"Metadata saved to: {metadata_path}")
            
        except Exception as e:
            current_app.logger.error(f"Error in LectureComposer: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'项目处理失败: {str(e)}'
            }), 500
        
        # 创建项目信息
        project_info = ProjectInfo(
            project_id=project_id,
            title=project_title,
            created_at=enhanced_metadata['created_at'],
            audio_file=enhanced_metadata['audio_file'],
            photo_count=len(photo_files),
            duration=enhanced_metadata['duration'],
            metadata_path=str(metadata_path)
        )
        
        # 存储到会话
        session_manager = get_session_manager()
        session_manager.store_project(session_id, project_info)
        
        current_app.logger.info(f"Project created successfully: {project_id}")
        
        return jsonify({
            'success': True,
            'project_id': project_id,
            'title': project_title,
            'metadata': enhanced_metadata
        })
        
    except Exception as e:
        current_app.logger.error(f"Error creating project: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'创建项目失败: {str(e)}'
        }), 500


@project_bp.route('/load/<project_id>', methods=['GET'])
def load_project(project_id: str):
    """
    加载项目
    
    参数：
        project_id: 项目ID
        session_id: 会话ID（查询参数）
        
    返回：
        JSON响应，包含完整的项目元数据
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        session_manager = get_session_manager()
        
        # 从会话获取项目
        project_info = session_manager.get_project(session_id, project_id)
        
        if not project_info:
            return jsonify({
                'success': False,
                'error': '项目不存在'
            }), 404
        
        # 读取元数据文件
        metadata_path = Path(project_info.metadata_path)
        
        if not metadata_path.exists():
            return jsonify({
                'success': False,
                'error': '项目元数据文件不存在'
            }), 404
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 设置为当前项目
        session_manager.set_current_project(session_id, project_id)
        
        # 构建完整的项目数据，包含播放器需要的所有信息
        # 使用项目目录而非上传目录
        project_dir = metadata_path.parent
        
        # 构建音频URL路径 - 从项目目录
        audio_path = f'/projects/{session_id}/{project_id}/{metadata["audio_file"]}'
        
        # 构建照片URL路径 - 从项目目录
        timeline_with_urls = []
        for item in metadata.get('timeline', []):
            timeline_item = item.copy()
            # 将相对路径转换为完整的URL
            photo_filename = item['photo']
            timeline_item['photo'] = f'/projects/{session_id}/{project_id}/photos/{photo_filename}'
            timeline_with_urls.append(timeline_item)
        
        # 返回完整的元数据
        return jsonify({
            'success': True,
            'project_id': metadata['project_id'],
            'title': metadata['title'],
            'audio_path': audio_path,
            'duration': metadata.get('duration', 0),
            'photo_count': metadata.get('photo_count', 0),
            'timeline': timeline_with_urls,
            'created_at': metadata.get('created_at')
        })
        
    except Exception as e:
        current_app.logger.error(f"Error loading project: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'加载项目失败: {str(e)}'
        }), 500


@project_bp.route('/list', methods=['GET'])
def list_projects():
    """
    列出所有项目
    
    返回：
        JSON响应，包含项目列表
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        session_manager = get_session_manager()
        
        # 获取会话
        sess = session_manager.get_session(session_id)
        
        if not sess:
            return jsonify({
                'success': True,
                'projects': [],
                'current_project_id': None
            })
        
        # 构建项目列表
        projects = []
        for project_id, project_info in sess.projects.items():
            projects.append({
                'project_id': project_info.project_id,
                'title': project_info.title,
                'created_at': project_info.created_at,
                'photo_count': project_info.photo_count,
                'duration': project_info.duration
            })
        
        # 按创建时间排序
        projects.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({
            'success': True,
            'projects': projects,
            'current_project_id': sess.current_project_id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error listing projects: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'获取项目列表失败: {str(e)}'
        }), 500


@project_bp.route('/current', methods=['GET'])
def get_current_project():
    """
    获取当前项目
    
    返回：
        JSON响应，包含当前项目信息
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        session_manager = get_session_manager()
        
        project_info = session_manager.get_current_project(session_id)
        
        if not project_info:
            return jsonify({
                'success': False,
                'error': '没有当前项目'
            }), 404
        
        return jsonify({
            'success': True,
            'project_id': project_info.project_id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting current project: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'获取当前项目失败: {str(e)}'
        }), 500


@project_bp.route('/set-current/<project_id>', methods=['POST'])
def set_current_project(project_id: str):
    """
    设置当前项目
    
    参数：
        project_id: 项目ID
        session_id: 会话ID（查询参数）
        
    返回：
        JSON响应
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        session_manager = get_session_manager()
        
        success = session_manager.set_current_project(session_id, project_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': '项目不存在'
            }), 404
        
        return jsonify({
            'success': True,
            'project_id': project_id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error setting current project: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'设置当前项目失败: {str(e)}'
        }), 500


@project_bp.route('/delete/<project_id>', methods=['DELETE'])
def delete_project(project_id: str):
    """
    删除项目
    
    参数：
        project_id: 项目ID
        session_id: 会话ID（查询参数）
        
    返回：
        JSON响应
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        session_manager = get_session_manager()
        
        # 获取项目信息
        project_info = session_manager.get_project(session_id, project_id)
        
        if not project_info:
            return jsonify({
                'success': False,
                'error': '项目不存在'
            }), 404
        
        # 删除项目文件
        metadata_path = Path(project_info.metadata_path)
        project_dir = metadata_path.parent
        
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir)
            current_app.logger.info(f"Deleted project directory: {project_dir}")
        
        # 从会话移除项目
        session_manager.remove_project(session_id, project_id)
        
        return jsonify({
            'success': True
        })
        
    except Exception as e:
        current_app.logger.error(f"Error deleting project: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'删除项目失败: {str(e)}'
        }), 500


@project_bp.route('/metadata/<project_id>', methods=['GET'])
def get_project_metadata(project_id: str):
    """
    获取项目元数据
    
    参数：
        project_id: 项目ID
        session_id: 会话ID（查询参数）
        
    返回：
        JSON响应，包含完整元数据
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        session_manager = get_session_manager()
        
        project_info = session_manager.get_project(session_id, project_id)
        
        if not project_info:
            return jsonify({
                'success': False,
                'error': '项目不存在'
            }), 404
        
        metadata_path = Path(project_info.metadata_path)
        
        if not metadata_path.exists():
            return jsonify({
                'success': False,
                'error': '元数据文件不存在'
            }), 404
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        return jsonify({
            'success': True,
            'metadata': metadata
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting metadata: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'获取元数据失败: {str(e)}'
        }), 500


@project_bp.route('/update/<project_id>', methods=['PUT'])
def update_project(project_id: str):
    """
    更新项目信息
    
    参数：
        project_id: 项目ID
        
    请求：
        JSON数据，包含session_id和要更新的字段（title等）
        
    返回：
        JSON响应
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少更新数据'
            }), 400
        
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': '缺少session_id'
            }), 400
        
        session_manager = get_session_manager()
        
        project_info = session_manager.get_project(session_id, project_id)
        
        if not project_info:
            return jsonify({
                'success': False,
                'error': '项目不存在'
            }), 404
        
        # 读取现有元数据
        metadata_path = Path(project_info.metadata_path)
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 更新字段
        if 'title' in data:
            metadata['title'] = data['title']
            project_info.title = data['title']
        
        # 保存更新后的元数据
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        # 更新会话中的项目信息
        session_manager.store_project(session_id, project_info)
        
        return jsonify({
            'success': True,
            'title': metadata['title']
        })
        
    except Exception as e:
        current_app.logger.error(f"Error updating project: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'更新项目失败: {str(e)}'
        }), 500
