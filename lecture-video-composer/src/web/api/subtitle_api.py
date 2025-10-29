"""
字幕API
处理字幕的加载和生成
"""
import json
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app

from ..services.session_manager import SessionManager


# 创建蓝图
subtitle_bp = Blueprint('subtitle', __name__)


def get_session_manager() -> SessionManager:
    """获取会话管理器实例"""
    from ..app import session_manager
    return session_manager


@subtitle_bp.route('/load/<project_id>', methods=['GET'])
def load_subtitles(project_id: str):
    """
    加载项目字幕
    
    参数:
        project_id: 项目ID
        session_id: 会话ID（查询参数）
        
    返回:
        JSON响应，包含字幕数据
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
        
        # 查找项目目录中的字幕文件
        metadata_path = Path(project_info.metadata_path)
        project_dir = metadata_path.parent
        
        # 查找.srt字幕文件
        subtitle_files = list(project_dir.glob('**/*.srt'))
        
        if not subtitle_files:
            # 没有找到字幕文件
            return jsonify({
                'success': True,
                'subtitles': [],
                'has_subtitles': False
            })
        
        # 读取第一个字幕文件
        subtitle_file = subtitle_files[0]
        
        try:
            subtitles = parse_srt_file(subtitle_file)
            
            return jsonify({
                'success': True,
                'subtitles': subtitles,
                'has_subtitles': True,
                'subtitle_file': subtitle_file.name
            })
            
        except Exception as e:
            current_app.logger.error(f"Error parsing subtitle file: {e}")
            return jsonify({
                'success': False,
                'error': f'解析字幕文件失败: {str(e)}'
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Error loading subtitles: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'加载字幕失败: {str(e)}'
        }), 500


def parse_srt_file(srt_path: Path):
    """
    解析SRT字幕文件
    
    Args:
        srt_path: SRT文件路径
        
    Returns:
        字幕列表，每个字幕包含 start, end, text
    """
    subtitles = []
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 分割字幕块
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.strip().split('\n')
        
        if len(lines) < 3:
            continue
        
        # 第一行是序号
        # 第二行是时间码
        # 第三行及之后是文本
        
        try:
            time_line = lines[1]
            text_lines = lines[2:]
            
            # 解析时间码 (例如: 00:00:01,000 --> 00:00:05,000)
            start_time_str, end_time_str = time_line.split(' --> ')
            
            start_seconds = parse_srt_time(start_time_str.strip())
            end_seconds = parse_srt_time(end_time_str.strip())
            
            text = '\n'.join(text_lines)
            
            subtitles.append({
                'start': start_seconds,
                'end': end_seconds,
                'text': text
            })
            
        except Exception as e:
            current_app.logger.warning(f"Error parsing subtitle block: {e}")
            continue
    
    return subtitles


def parse_srt_time(time_str: str) -> float:
    """
    将SRT时间格式转换为秒数
    
    Args:
        time_str: SRT时间字符串 (例如: "00:00:01,000")
        
    Returns:
        秒数（浮点数）
    """
    # 格式: HH:MM:SS,mmm
    time_part, ms_part = time_str.split(',')
    hours, minutes, seconds = map(int, time_part.split(':'))
    milliseconds = int(ms_part)
    
    total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
    
    return total_seconds


@subtitle_bp.route('/generate/<project_id>', methods=['POST'])
def generate_subtitles(project_id: str):
    """
    为项目生成字幕（使用Whisper AI）
    
    参数:
        project_id: 项目ID
        
    请求:
        JSON数据，包含：
        - session_id: 会话ID
        - model: Whisper模型 (可选，默认为base)
        - language: 语言代码 (可选，默认为zh)
        
    返回:
        JSON响应，包含生成的字幕数据
    """
    try:
        data = request.get_json() or {}
        
        session_id = data.get('session_id')
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
        
        # 读取项目元数据
        metadata_path = Path(project_info.metadata_path)
        project_dir = metadata_path.parent
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # 获取音频文件路径
        audio_file = project_dir / metadata['audio_file']
        
        if not audio_file.exists():
            return jsonify({
                'success': False,
                'error': '音频文件不存在'
            }), 404
        
        # 获取参数
        model = data.get('model', 'base')
        language = data.get('language', 'zh')
        
        # 生成字幕
        try:
            from src.services.subtitle.subtitle_service import SubtitleService, SubtitleConfig
            
            config = SubtitleConfig(
                model=model,
                language=language
            )
            
            subtitle_service = SubtitleService(config)
            
            # 生成字幕文件
            subtitle_dir = project_dir / 'subtitles'
            subtitle_dir.mkdir(exist_ok=True)
            
            subtitle_file = subtitle_service.generate_subtitles(audio_file, subtitle_dir)
            
            if not subtitle_file:
                return jsonify({
                    'success': False,
                    'error': 'Whisper未安装，无法生成字幕'
                }), 500
            
            # 解析生成的字幕
            subtitles = parse_srt_file(subtitle_file)
            
            return jsonify({
                'success': True,
                'subtitles': subtitles,
                'subtitle_file': subtitle_file.name,
                'count': len(subtitles)
            })
            
        except ImportError:
            return jsonify({
                'success': False,
                'error': 'Whisper未安装，请先安装: pip install openai-whisper'
            }), 500
        except Exception as e:
            current_app.logger.error(f"Error generating subtitles: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': f'生成字幕失败: {str(e)}'
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"Error in generate_subtitles: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'生成字幕失败: {str(e)}'
        }), 500
