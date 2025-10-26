"""
视频导出API
提供视频合成和导出功能
"""
import os
import uuid
from pathlib import Path
from flask import Blueprint, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename

from ...services.video.video_exporter import VideoExporter, VideoExportConfig
from .. import app as app_module

export_bp = Blueprint('export', __name__)


def get_session_manager():
    """获取全局session_manager实例"""
    return app_module.session_manager


@export_bp.route('/start', methods=['POST'])
def start_export():
    """
    开始视频导出
    
    Request Body:
        project_id: 项目ID
        session_id: 会话ID
        output_format: 输出格式（mp4, avi等）
        resolution: 分辨率（1920x1080, 1280x720等）
        fps: 帧率
        
    Returns:
        export_id: 导出任务ID
        status: 任务状态
    """
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        session_id = data.get('session_id')
        output_format = data.get('output_format', 'mp4')
        resolution = data.get('resolution', '1280x720')
        fps = data.get('fps', 30)
        
        if not project_id:
            return jsonify({
                'success': False,
                'error': 'Missing project_id'
            }), 400
        
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id'
            }), 400
        
        # 获取会话
        session_manager = get_session_manager()
        sess = session_manager.get_session(session_id)
        if not sess:
            return jsonify({
                'success': False,
                'error': 'Invalid session'
            }), 401
        
        # 获取项目信息
        project_info = session_manager.get_project(session_id, project_id)
        if not project_info:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
        # 读取项目元数据
        import json
        metadata_path = Path(project_info.metadata_path)
        if not metadata_path.exists():
            return jsonify({
                'success': False,
                'error': 'Project metadata not found'
            }), 404
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 解析分辨率
        try:
            width, height = map(int, resolution.split('x'))
        except:
            width, height = 1920, 1080
        
        # 生成导出ID和输出文件名
        export_id = str(uuid.uuid4())
        output_filename = f"{project_info.title}_{export_id}.{output_format}"
        output_dir = Path(current_app.config['EXPORT_FOLDER'])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / output_filename
        
        # 准备音频和照片路径
        upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / session_id
        audio_path = upload_dir / metadata['audio_file']
        
        # 准备时间轴数据用于视频导出
        timeline_items = metadata.get('timeline', [])
        photos_dir = upload_dir / 'photos'
        
        # 创建视频导出配置
        video_config = VideoExportConfig(
            resolution=f"{width}x{height}",
            fps=fps,
            video_codec='libx264',
            preset='medium',
            enable_subtitles=False  # 暂时禁用字幕以加快导出速度
        )
        
        # 创建VideoExporter实例
        exporter = VideoExporter(video_config)
        
        # 初始化导出任务状态（必须在启动线程前完成）
        if not hasattr(sess, 'export_tasks'):
            sess.export_tasks = {}
        
        sess.export_tasks[export_id] = {
            'status': 'pending',
            'progress': 0,
            'output_path': str(output_path),
            'error': None
        }
        
        # 开始导出（在后台线程中）
        import threading
        import logging
        import traceback
        
        # 获取Flask应用实例以便在线程中使用
        app = current_app._get_current_object()
        
        def export_video():
            # 在线程中使用Flask应用上下文
            with app.app_context():
                try:
                    # 更新为处理中状态
                    sess.export_tasks[export_id]['status'] = 'processing'
                    sess.export_tasks[export_id]['progress'] = 5  # 初始进度5%
                    
                    app.logger.info(f"Starting video export for project {project_id}")
                    
                    # 计算总步骤数：
                    # - 创建片段：占70%
                    # - 合并片段：占10%
                    # - 添加音频：占10%
                    # - 完成：占10%
                    total_segments = len(timeline_items)
                    
                    # 保存原始的_create_photo_segments方法
                    original_create_segments = exporter._create_photo_segments
                    
                    # 包装方法以跟踪进度
                    def create_segments_with_progress(*args, **kwargs):
                        # 创建一个进度跟踪的包装器
                        original_create_single = exporter._create_single_segment
                        completed_count = [0]  # 使用列表以便在闭包中修改
                        
                        def tracked_create_single(item_data):
                            result = original_create_single(item_data)
                            completed_count[0] += 1
                            # 片段创建占70%的进度，从5%到75%
                            progress = 5 + int((completed_count[0] / total_segments) * 70)
                            sess.export_tasks[export_id]['progress'] = progress
                            app.logger.info(f"Export progress: {progress}% ({completed_count[0]}/{total_segments} segments)")
                            return result
                        
                        # 临时替换方法
                        exporter._create_single_segment = tracked_create_single
                        try:
                            return original_create_segments(*args, **kwargs)
                        finally:
                            # 恢复原始方法
                            exporter._create_single_segment = original_create_single
                    
                    # 替换方法
                    exporter._create_photo_segments = create_segments_with_progress
                    
                    try:
                        # 执行导出
                        result_path = exporter.export_video(
                            audio_file=audio_path,
                            timeline_items=timeline_items,
                            photos_dir=photos_dir,
                            output_file=output_path,
                            audio_duration=metadata.get('duration', 0)
                        )
                        
                        # 更新最终状态
                        sess.export_tasks[export_id]['status'] = 'completed'
                        sess.export_tasks[export_id]['progress'] = 100
                        sess.export_tasks[export_id]['output_path'] = str(result_path)
                        
                        app.logger.info(f"Video export completed: {result_path}")
                        
                    finally:
                        # 恢复原始方法
                        exporter._create_photo_segments = original_create_segments
                    
                except Exception as e:
                    error_msg = f"Export failed: {str(e)}"
                    app.logger.error(error_msg)
                    app.logger.error(traceback.format_exc())
                    sess.export_tasks[export_id]['status'] = 'failed'
                    sess.export_tasks[export_id]['error'] = str(e)
        
        # 启动后台线程
        thread = threading.Thread(target=export_video)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'export_id': export_id,
            'status': 'pending'
        })
        
    except Exception as e:
        current_app.logger.error(f"Start export error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@export_bp.route('/status/<export_id>', methods=['GET'])
def get_export_status(export_id):
    """
    获取导出任务状态
    
    Args:
        export_id: 导出任务ID
        
    Returns:
        status: pending, processing, completed, failed
        progress: 进度百分比
        error: 错误信息（如果失败）
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id'
            }), 400
        
        # 获取会话
        session_manager = get_session_manager()
        sess = session_manager.get_session(session_id)
        if not sess:
            return jsonify({
                'success': False,
                'error': 'Invalid session'
            }), 401
        
        # 获取导出任务
        if not hasattr(sess, 'export_tasks') or export_id not in sess.export_tasks:
            return jsonify({
                'success': False,
                'error': 'Export task not found'
            }), 404
        
        task = sess.export_tasks[export_id]
        
        return jsonify({
            'success': True,
            'status': task['status'],
            'progress': task['progress'],
            'error': task.get('error')
        })
        
    except Exception as e:
        current_app.logger.error(f"Get export status error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@export_bp.route('/download/<export_id>', methods=['GET'])
def download_export(export_id):
    """
    下载导出的视频
    
    Args:
        export_id: 导出任务ID
        
    Returns:
        视频文件
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id'
            }), 400
        
        # 获取会话
        session_manager = get_session_manager()
        sess = session_manager.get_session(session_id)
        if not sess:
            return jsonify({
                'success': False,
                'error': 'Invalid session'
            }), 401
        
        # 获取导出任务
        if not hasattr(sess, 'export_tasks') or export_id not in sess.export_tasks:
            return jsonify({
                'success': False,
                'error': 'Export task not found'
            }), 404
        
        task = sess.export_tasks[export_id]
        
        # 检查状态
        if task['status'] != 'completed':
            return jsonify({
                'success': False,
                'error': f"Export not completed (status: {task['status']})"
            }), 400
        
        # 获取文件路径
        output_path = Path(task['output_path'])
        if not output_path.exists():
            return jsonify({
                'success': False,
                'error': 'Export file not found'
            }), 404
        
        # 发送文件
        return send_file(
            output_path,
            as_attachment=True,
            download_name=output_path.name,
            mimetype='video/mp4'
        )
        
    except Exception as e:
        current_app.logger.error(f"Download export error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@export_bp.route('/list', methods=['GET'])
def list_exports():
    """
    列出所有导出任务
    
    Returns:
        exports: 导出任务列表
    """
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id'
            }), 400
        
        # 获取会话
        session_manager = get_session_manager()
        sess = session_manager.get_session(session_id)
        if not sess:
            return jsonify({
                'success': False,
                'error': 'Invalid session'
            }), 401
        
        # 获取所有导出任务
        exports = []
        if hasattr(sess, 'export_tasks'):
            for export_id, task in sess.export_tasks.items():
                exports.append({
                    'export_id': export_id,
                    'status': task['status'],
                    'progress': task['progress'],
                    'error': task.get('error')
                })
        
        return jsonify({
            'success': True,
            'exports': exports
        })
        
    except Exception as e:
        current_app.logger.error(f"List exports error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
