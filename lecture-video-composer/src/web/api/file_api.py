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


def get_file_creation_time_from_exif(filepath: Path) -> Optional[datetime]:
    """
    从图片EXIF数据中获取拍摄时间
    
    Args:
        filepath: 图片文件路径
        
    Returns:
        拍摄时间，如果无法获取则返回None
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS
        
        image = Image.open(filepath)
        exif_data = image._getexif()
        
        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == 'DateTimeOriginal' or tag == 'DateTime':
                    # EXIF日期格式: "2025:10:24 13:38:04"
                    return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
        
        return None
    except Exception as e:
        current_app.logger.debug(f"Failed to get EXIF time: {e}")
        return None


def get_file_creation_time_from_id3(filepath: Path) -> Optional[datetime]:
    """
    从音频文件ID3标签中获取录制时间
    
    Args:
        filepath: 音频文件路径
        
    Returns:
        录制时间，如果无法获取则返回None
    """
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3, TDRC
        
        audio = MP3(filepath)
        
        if not audio.tags:
            return None
        
        # 尝试获取录制时间 (TDRC - Recording Time)
        if 'TDRC' in audio.tags:
            tdrc = audio.tags['TDRC']
            if tdrc.text and len(tdrc.text) > 0:
                timestamp_obj = tdrc.text[0]
                
                # mutagen返回的是ID3TimeStamp对象，有year, month, day, hour, minute, second属性
                try:
                    # 尝试获取完整的日期时间
                    if hasattr(timestamp_obj, 'year') and timestamp_obj.year:
                        year = timestamp_obj.year
                        month = getattr(timestamp_obj, 'month', 1) or 1
                        day = getattr(timestamp_obj, 'day', 1) or 1
                        hour = getattr(timestamp_obj, 'hour', 0) or 0
                        minute = getattr(timestamp_obj, 'minute', 0) or 0
                        second = getattr(timestamp_obj, 'second', 0) or 0
                        
                        return datetime(year, month, day, hour, minute, second)
                except Exception as e:
                    current_app.logger.debug(f"Failed to parse TDRC timestamp object: {e}")
                    
                # 如果对象解析失败，尝试字符串解析
                try:
                    timestamp_str = str(timestamp_obj)
                    # ID3 时间格式可能是: "2017-12-27 19:48:00" 或 "2017-12-27" 或 "2017"
                    if ' ' in timestamp_str:
                        return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    elif '-' in timestamp_str and len(timestamp_str) >= 10:
                        return datetime.strptime(timestamp_str[:10], '%Y-%m-%d')
                    elif len(timestamp_str) == 4:
                        return datetime(int(timestamp_str), 1, 1)
                except Exception as e:
                    current_app.logger.debug(f"Failed to parse TDRC string: {e}")
        
        # 尝试从XMP元数据获取创建时间
        if 'PRIV:XMP' in audio.tags:
            try:
                xmp_data = str(audio.tags['PRIV:XMP'])
                # 查找 xmp:CreateDate
                import re
                match = re.search(r'xmp:CreateDate="(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', xmp_data)
                if match:
                    date_str = match.group(1)
                    # 格式: "2017-12-27T19:48:35+08:00"
                    # 移除时区信息
                    date_str = date_str.split('+')[0].split('-')[0:3]
                    date_str = '-'.join(date_str[:3])
                    if 'T' in date_str:
                        return datetime.fromisoformat(date_str.replace('T', ' '))
            except Exception as e:
                current_app.logger.debug(f"Failed to parse XMP data: {e}")
        
        return None
    except Exception as e:
        current_app.logger.debug(f"Failed to get ID3 time: {e}")
        return None


def get_file_creation_time(file: FileStorage, temp_path: Path) -> datetime:
    """
    获取文件的创建时间
    
    优先级：
    1. 图片文件（JPEG）：尝试从EXIF获取拍摄时间
    2. 音频文件（MP3）：尝试从ID3标签获取录制时间
    3. 所有文件：使用文件系统的birthtime/ctime
    4. 失败时：使用当前时间
    
    Args:
        file: 上传的文件对象
        temp_path: 临时保存的文件路径
        
    Returns:
        文件创建时间
    """
    try:
        ext = temp_path.suffix.lower()
        
        # 对于图片文件，优先尝试从EXIF获取拍摄时间
        if ext in {'.jpg', '.jpeg'}:
            exif_time = get_file_creation_time_from_exif(temp_path)
            if exif_time:
                current_app.logger.info(f"Using EXIF time: {exif_time}")
                return exif_time
        
        # 对于音频文件，尝试从ID3标签获取录制时间
        if ext == '.mp3':
            id3_time = get_file_creation_time_from_id3(temp_path)
            if id3_time:
                current_app.logger.info(f"Using ID3 time: {id3_time}")
                return id3_time
        
        # 获取文件的创建时间（使用stat的st_birthtime或st_ctime）
        stat_info = temp_path.stat()
        
        # macOS和某些系统支持st_birthtime（真正的创建时间）
        if hasattr(stat_info, 'st_birthtime'):
            timestamp = stat_info.st_birthtime
            current_app.logger.info(f"Using st_birthtime: {datetime.fromtimestamp(timestamp)}")
        else:
            # Linux等系统使用st_ctime（元数据修改时间，通常接近创建时间）
            timestamp = stat_info.st_ctime
            current_app.logger.info(f"Using st_ctime: {datetime.fromtimestamp(timestamp)}")
        
        return datetime.fromtimestamp(timestamp)
    except Exception as e:
        current_app.logger.warning(f"Failed to get file creation time: {e}, using current time")
        return datetime.now()


def save_uploaded_file(file: FileStorage, upload_dir: Path, prefix: str = '') -> Path:
    """
    保存上传的文件，自动根据文件创建时间重命名
    
    注意：由于HTTP上传不保留原始文件的birthtime，
    我们使用EXIF数据（照片）或当前时间作为文件名
    
    Args:
        file: 上传的文件
        upload_dir: 上传目录
        prefix: 文件名前缀（未使用）
        
    Returns:
        保存的文件路径
    """
    # 创建上传目录
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 获取原始文件扩展名
    original_filename = file.filename
    ext = Path(original_filename).suffix.lower()
    
    # 先临时保存文件
    temp_filename = f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
    temp_filepath = upload_dir / temp_filename
    file.save(str(temp_filepath))
    
    try:
        # 获取文件创建时间
        # 注意：对于通过HTTP上传的文件，birthtime是保存时间，不是原始时间
        # 只有EXIF数据（照片）能提供原始拍摄时间
        creation_time = get_file_creation_time(file, temp_filepath)
        
        # 使用创建时间生成新文件名：YYYY-MM-DD-HH:MM:SS.ext
        # 注意：使用连字符分隔日期和时间（系统要求格式）
        new_filename = creation_time.strftime('%Y-%m-%d-%H:%M:%S') + ext
        
        # 处理文件名冲突：如果文件已存在，添加毫秒后缀
        final_filepath = upload_dir / new_filename
        if final_filepath.exists():
            # 文件已存在，添加毫秒后缀
            timestamp_with_ms = creation_time.strftime('%Y-%m-%d-%H:%M:%S.%f')[:-3]  # 保留3位毫秒
            new_filename = timestamp_with_ms + ext
            final_filepath = upload_dir / new_filename
            current_app.logger.info(f"File conflict, renamed to: {new_filename}")
        
        # 重命名临时文件为最终文件名
        temp_filepath.rename(final_filepath)
        
        current_app.logger.info(f"File renamed from '{original_filename}' to '{new_filename}'")
        
        return final_filepath
        
    except Exception as e:
        # 如果重命名失败，删除临时文件并抛出异常
        if temp_filepath.exists():
            temp_filepath.unlink()
        current_app.logger.error(f"Error saving file: {e}")
        raise


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
