"""
Flask Web应用主文件
提供演讲视频合成系统的Web界面和API
"""
import os
from pathlib import Path
from flask import Flask, jsonify, request, session, send_file
from flask_cors import CORS
from werkzeug.exceptions import HTTPException
import logging

from .config import get_config, Config
from .services.session_manager import SessionManager

# 全局变量
session_manager: SessionManager = None


def create_app(config_name: str = None) -> Flask:
    """
    创建Flask应用实例
    
    Args:
        config_name: 配置名称 ('development', 'production', 'testing')
        
    Returns:
        Flask应用实例
    """
    app = Flask(__name__)
    
    # 加载配置
    config_class = get_config(config_name)
    app.config.from_object(config_class)
    config_class.init_app(app)
    
    # 初始化扩展
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # 初始化会话管理器
    global session_manager
    session_manager = SessionManager(
        session_dir=app.config['SESSION_FILE_DIR'],
        max_age=app.config['PERMANENT_SESSION_LIFETIME']
    )
    
    # 注册蓝图
    register_blueprints(app)
    
    # 注册错误处理器
    register_error_handlers(app)
    
    # 注册钩子函数
    register_hooks(app)
    
    # 配置日志
    setup_logging(app)
    
    return app


def register_blueprints(app: Flask):
    """注册蓝图"""
    # 注册API蓝图
    from .api import file_bp, project_bp, playback_bp
    app.register_blueprint(file_bp, url_prefix='/api/file')
    app.register_blueprint(project_bp, url_prefix='/api/project')
    app.register_blueprint(playback_bp, url_prefix='/api/playback')
    
    # TODO: 注册其他蓝图
    # from .api import export_bp
    # app.register_blueprint(export_bp, url_prefix='/api/export')
    
    # 暂时添加基础路由
    @app.route('/')
    def index():
        """主页"""
        return app.send_static_file('index.html')
    
    @app.route('/health')
    def health():
        """健康检查"""
        return jsonify({
            'status': 'healthy',
            'version': 'v2.2',
            'sessions': session_manager.get_session_count()
        })
    
    @app.route('/api/session/create', methods=['POST'])
    def create_session():
        """创建新会话"""
        session_id = session_manager.create_session()
        session['session_id'] = session_id
        return jsonify({
            'success': True,
            'session_id': session_id
        })
    
    @app.route('/api/session/info', methods=['GET'])
    def get_session_info():
        """获取会话信息"""
        session_id = session.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'error': 'No active session'
            }), 401
        
        sess = session_manager.get_session(session_id)
        if not sess:
            return jsonify({
                'success': False,
                'error': 'Session expired or invalid'
            }), 401
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'project_count': len(sess.projects),
            'current_project_id': sess.current_project_id
        })


def register_error_handlers(app: Flask):
    """注册错误处理器"""
    
    @app.errorhandler(400)
    def bad_request(e):
        """400 Bad Request"""
        return jsonify({
            'success': False,
            'error': 'Bad Request',
            'message': str(e)
        }), 400
    
    @app.errorhandler(401)
    def unauthorized(e):
        """401 Unauthorized"""
        return jsonify({
            'success': False,
            'error': 'Unauthorized',
            'message': str(e)
        }), 401
    
    @app.errorhandler(404)
    def not_found(e):
        """404 Not Found"""
        return jsonify({
            'success': False,
            'error': 'Not Found',
            'message': str(e)
        }), 404
    
    @app.errorhandler(500)
    def internal_error(e):
        """500 Internal Server Error"""
        app.logger.error(f"Internal error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }), 500
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """处理所有未捕获的异常"""
        # 传递HTTP异常
        if isinstance(e, HTTPException):
            return e
        
        # 记录错误
        app.logger.error(f"Unhandled exception: {e}", exc_info=True)
        
        # 返回500错误
        return jsonify({
            'success': False,
            'error': 'Internal Server Error',
            'message': str(e) if app.debug else 'An unexpected error occurred'
        }), 500


def register_hooks(app: Flask):
    """注册请求钩子"""
    
    @app.before_request
    def before_request():
        """请求前处理"""
        # 确保会话ID存在
        if 'session_id' not in session and request.endpoint not in ['create_session', 'health', 'static']:
            # 自动创建会话
            session_id = session_manager.create_session()
            session['session_id'] = session_id
            app.logger.info(f"Auto-created session: {session_id}")
    
    @app.after_request
    def after_request(response):
        """请求后处理"""
        # 添加安全头
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response
    
    @app.teardown_appcontext
    def teardown(exception=None):
        """应用上下文清理"""
        if exception:
            app.logger.error(f"Teardown exception: {exception}")


def setup_logging(app: Flask):
    """配置日志"""
    if not app.debug and not app.testing:
        # 生产环境日志配置已在config中设置
        app.logger.info('Lecture Video Composer Web started in production mode')
    else:
        # 开发环境使用控制台日志
        logging.basicConfig(
            level=logging.DEBUG if app.debug else logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        app.logger.info('Lecture Video Composer Web started in development mode')


def cleanup_sessions():
    """清理过期会话（可由定时任务调用）"""
    if session_manager:
        count = session_manager.cleanup_expired_sessions()
        if count > 0:
            print(f"Cleaned up {count} expired sessions")


# 创建默认应用实例（用于开发）
app = create_app()


if __name__ == '__main__':
    # 开发服务器
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    
    print(f"Starting Lecture Video Composer Web Server")
    print(f"Server running at http://{host}:{port}")
    print(f"Press Ctrl+C to quit")
    
    app.run(
        host=host,
        port=port,
        debug=True,
        threaded=True
    )
