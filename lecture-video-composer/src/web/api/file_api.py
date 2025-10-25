"""
文件上传/下载API
处理音频和照片文件的上传、验证和管理
"""
import os
import mimetypes
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from flask import Blueprint, request, jsonify, current_app, send_file, session
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

from ..services.session_manager import SessionManager


# 创建蓝图
file_bp = Blueprint('file', __name__)


# 允许的文件扩展名
ALLOWED_AUDIO_EXTENSIONS = {'.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'}
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

# 文件大小限制（字节）
MAX_AUDIO_SIZE = 500 * 1024 * 1024  # 500MB
MAX_IMAGE_SIZE = 50 * 1024 * 1024   # 50MB


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """
    检查文件扩展名是否允许
    
    Args:
        filename: 文件名
        allowed_extensions: 允许的扩展名集合
        
    Returns:
        是否允许
    """
    if not filename:
        return False
    
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


def validate_file_size(file: FileStorage, max_size: int) -> Tuple[bool, Optional[str]]:
    """
    验证文件大小
    
    Args:
        file: 上传的文件
        max_size: 最大大小（字节）
        
    Returns:
        (是否有效, 错误消息)
    """
    # 获取文件大小
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    if size > max_size:
        size_mb = size / (1024 * 1024)
        max_mb = max_size / (1024 * 1024)
        return False, f"文件过大 ({size_mb:.1f}MB)，最大允许 {max_mb:.1f}MB"
    
    return True, None


def save_uploaded_file(file: FileStorage, upload_dir: Path, prefix: str = '') -> Path:
    """
    保存上传的文件
    
    Args:
        file: 上传的文件
        upload_dir: 上传目录
        prefix: 文件名前缀（未使用，保留原始文件名）
        
    Returns:
        保存的文件路径
    """
    # 创建上传目录
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 使用原始文件名（保留时间戳格式）
    # 文件名格式应为: YYYY-MM-DD-HH:MM:SS.ext
    # 注意：不使用 secure_filename，因为它会移除冒号，而时间戳格式需要冒号
    original_filename = file.filename
    
    # 基本安全检查：防止路径遍历攻击
    # 移除路径分隔符和特殊字符，但保留冒号、连字符、点和下划线
    safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.:')
    filename = ''.join(c for c in original_filename if c in safe_chars)
    
    # 确保文件名不为空
    if not filename or filename.startswith('.'):
        # 如果清理后的文件名无效，使用时间戳生成新文件名
        ext = Path(original_filename).suffix if '.' in original_filename else ''
        timestamp = datetime.now().strftime('%Y-%m-%d-%H:%M:%S')
        filename = f"{prefix}{timestamp}{ext}" if prefix else f"{timestamp}{ext}"
    
    # 处理文件名冲突：如果文件已存在，添加后缀
    filepath = upload_dir / filename
    if filepath.exists():
        # 文件已存在，添加时间戳后缀
        stem = Path(filename).stem
        ext = Path(filename).suffix
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{stem}_{timestamp}{ext}"
        filepath = upload_dir / filename
        current_app.logger.warning(f"File {original_filename} already exists, renamed to {filename}")
    
    # 保存文件
    file.save(str(filepath))
    
    return filepath


@file_bp.route('/upload/audio', methods=['POST'])
def upload_audio():
    """
    上传音频文件
    
    请求：
        - 表单数据，包含 'file' 字段和 'session_id' 字段
        
    返回：
        JSON响应，包含文件信息
    """
    try:
        # 验证 session_id
        session_id = request.form.get('session_id') or request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id parameter'
            }), 400
        
        # 检查文件是否存在
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file part'
            }), 400
        
        file = request.files['file']
        
        # 检查文件名
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '文件名为空'
            }), 400
        
        # 验证文件类型
        if not allowed_file(file.filename, ALLOWED_AUDIO_EXTENSIONS):
            return jsonify({
                'success': False,
                'error': f'Invalid file type. Supported formats: {", ".join(ALLOWED_AUDIO_EXTENSIONS)}'
            }), 400
        
        # 验证文件大小
        valid, error = validate_file_size(file, MAX_AUDIO_SIZE)
        if not valid:
            return jsonify({
                'success': False,
                'error': error
            }), 400
        
        # 保存文件
        upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / session_id / 'audio'
        filepath = save_uploaded_file(file, upload_dir, prefix='audio')
        
        # 获取文件信息
        file_info = {
            'filename': file.filename,
            'saved_name': filepath.name,
            'path': str(filepath),
            'size': filepath.stat().st_size,
            'mime_type': mimetypes.guess_type(str(filepath))[0],
            'timestamp': datetime.now().isoformat()
        }
        
        current_app.logger.info(f"Audio file uploaded: {filepath.name}")
        
        return jsonify({
            'success': True,
            'message': '音频文件上传成功',
            'data': file_info
        })
        
    except Exception as e:
        current_app.logger.error(f"Error uploading audio: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'上传失败: {str(e)}'
        }), 500


@file_bp.route('/upload/photos', methods=['POST'])
def upload_photos():
    """
    上传照片文件（支持多文件）
    
    请求：
        - 表单数据，包含多个 'files' 字段和 'session_id' 字段
        
    返回：
        JSON响应，包含所有文件信息
    """
    try:
        # 验证 session_id
        session_id = request.form.get('session_id') or request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id parameter'
            }), 400
        
        # 检查文件是否存在
        if 'files' not in request.files:
            return jsonify({
                'success': False,
                'error': '没有上传文件'
            }), 400
        
        files = request.files.getlist('files')
        
        if not files or len(files) == 0:
            return jsonify({
                'success': False,
                'error': '没有选择文件'
            }), 400
        
        # 获取上传目录
        upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / session_id / 'photos'
        
        uploaded_files = []
        errors = []
        
        # 处理每个文件
        for i, file in enumerate(files):
            try:
                # 检查文件名
                if file.filename == '':
                    errors.append(f'文件 {i+1}: 文件名为空')
                    continue
                
                # 验证文件类型
                if not allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
                    errors.append(f'{file.filename}: Invalid file type')
                    continue
                
                # 验证文件大小
                valid, error = validate_file_size(file, MAX_IMAGE_SIZE)
                if not valid:
                    errors.append(f'{file.filename}: {error}')
                    continue
                
                # 保存文件
                filepath = save_uploaded_file(file, upload_dir, prefix='photo')
                
                # 记录文件信息
                file_info = {
                    'filename': file.filename,
                    'saved_name': filepath.name,
                    'path': str(filepath),
                    'size': filepath.stat().st_size,
                    'mime_type': mimetypes.guess_type(str(filepath))[0],
                    'timestamp': datetime.now().isoformat()
                }
                
                uploaded_files.append(file_info)
                
            except Exception as e:
                errors.append(f'{file.filename}: {str(e)}')
        
        # 记录日志
        current_app.logger.info(f"Uploaded {len(uploaded_files)} photos, {len(errors)} errors")
        
        # 返回结果
        if len(uploaded_files) == 0:
            return jsonify({
                'success': False,
                'error': '所有文件上传失败',
                'errors': errors
            }), 400
        
        return jsonify({
            'success': True,
            'message': f'成功上传 {len(uploaded_files)} 个文件',
            'data': {
                'uploaded': uploaded_files,
                'count': len(uploaded_files),
                'errors': errors if errors else None
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error uploading photos: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'上传失败: {str(e)}'
        }), 500


@file_bp.route('/download/<path:filename>', methods=['GET'])
def download_file(filename: str):
    """
    下载文件
    
    参数：
        filename: 文件路径（相对于会话目录）
        
    返回：
        文件内容
    """
    try:
        session_id = session.get('session_id')
        upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / session_id
        filepath = upload_dir / filename
        
        # 安全检查：确保文件在会话目录内
        try:
            filepath.resolve().relative_to(upload_dir.resolve())
        except ValueError:
            return jsonify({
                'success': False,
                'error': '非法的文件路径'
            }), 403
        
        # 检查文件是否存在
        if not filepath.exists():
            return jsonify({
                'success': False,
                'error': '文件不存在'
            }), 404
        
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filepath.name
        )
        
    except Exception as e:
        current_app.logger.error(f"Error downloading file: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'下载失败: {str(e)}'
        }), 500


@file_bp.route('/list', methods=['GET'])
def list_files():
    """
    列出会话中的所有文件
    
    参数：
        session_id: 会话ID（查询参数）
    
    返回：
        JSON响应，包含文件列表
    """
    try:
        # 验证 session_id
        session_id = request.args.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id parameter'
            }), 400
        
        upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / session_id
        
        if not upload_dir.exists():
            return jsonify({
                'success': True,
                'data': {
                    'audio': [],
                    'photos': []
                }
            })
        
        # 列出音频文件
        audio_dir = upload_dir / 'audio'
        audio_files = []
        if audio_dir.exists():
            for f in audio_dir.iterdir():
                if f.is_file():
                    audio_files.append({
                        'filename': f.name,
                        'path': str(f.relative_to(upload_dir)),
                        'size': f.stat().st_size,
                        'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    })
        
        # 列出照片文件
        photo_dir = upload_dir / 'photos'
        photo_files = []
        if photo_dir.exists():
            for f in photo_dir.iterdir():
                if f.is_file():
                    photo_files.append({
                        'filename': f.name,
                        'path': str(f.relative_to(upload_dir)),
                        'size': f.stat().st_size,
                        'modified': datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    })
        
        return jsonify({
            'success': True,
            'data': {
                'audio': audio_files,
                'photos': photo_files
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error listing files: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'列表获取失败: {str(e)}'
        }), 500


@file_bp.route('/delete', methods=['POST'])
def delete_file():
    """
    删除文件
    
    请求：
        JSON数据，包含 'session_id' 和 'filepath' 字段
        
    返回：
        JSON响应
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '缺少请求数据'
            }), 400
        
        # 验证 session_id
        session_id = data.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'Missing session_id parameter'
            }), 400
        
        # 验证 filepath
        filepath_str = data.get('filepath')
        if not filepath_str:
            return jsonify({
                'success': False,
                'error': '缺少文件路径'
            }), 400
        
        upload_dir = Path(current_app.config['UPLOAD_FOLDER']) / session_id
        filepath = upload_dir / filepath_str
        
        # 安全检查：路径遍历攻击防护
        try:
            filepath.resolve().relative_to(upload_dir.resolve())
        except ValueError:
            # 路径不在上传目录内
            return jsonify({
                'success': False,
                'error': 'Invalid file path'
            }), 400
        
        # 删除文件
        if filepath.exists():
            filepath.unlink()
            current_app.logger.info(f"Deleted file: {filepath.name}")
            
            return jsonify({
                'success': True,
                'message': '文件删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '文件不存在'
            }), 404
        
    except Exception as e:
        current_app.logger.error(f"Error deleting file: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'删除失败: {str(e)}'
        }), 500
