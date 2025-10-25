/**
 * 主应用程序 - 增强版
 * 集成了 Timeline、FileManager 和 StateManager
 */

import { LecturePlayer } from './player.js';
import { Timeline } from './timeline.js';
import { FileManager } from './file-manager.js';
import { StateManager } from './state-manager.js';
import { APIClient, showNotification, showLoading, hideLoading, confirm, formatTime } from './utils.js';

class App {
    constructor() {
        this.api = new APIClient('/api');
        this.player = null;
        this.timeline = null;
        this.fileManager = null;
        this.state = null;
        
        // 初始化
        this.init();
    }

    /**
     * 初始化应用
     */
    async init() {
        try {
            // 初始化状态管理器
            this.initStateManager();
            
            // 初始化文件管理器
            this.initFileManager();
            
            // 初始化播放器
            this.initPlayer();
            
            // 初始化时间轴
            this.initTimeline();
            
            // 绑定事件
            this.bindEvents();
            
            // 加载项目列表
            await this.loadProjects();
            
            // 显示上传视图
            this.showView(this.state.get('ui.currentView') || 'upload');
            
            // 恢复用户偏好设置
            this.restorePreferences();
            
        } catch (error) {
            console.error('应用初始化失败:', error);
            showNotification('应用初始化失败', 'error');
        }
    }

    /**
     * 初始化状态管理器
     */
    initStateManager() {
        this.state = new StateManager({}, {
            persist: true,
            persistKey: 'lecture_video_composer_state'
        });
        
        // 监听状态变化
        this.state.subscribe('ui.currentView', (view) => {
            console.log('视图切换:', view);
        });
        
        this.state.subscribe('preferences', (prefs) => {
            console.log('偏好设置更新:', prefs);
            this.applyPreferences(prefs);
        });
    }

    /**
     * 初始化文件管理器
     */
    initFileManager() {
        this.fileManager = new FileManager({
            maxFileSize: 100 * 1024 * 1024, // 100MB
            concurrentUploads: 3
        });
        
        // 监听上传事件
        this.fileManager.on('uploadStart', ({ file, fileType }) => {
            console.log('开始上传:', file.name, fileType);
            this.state.update('uploads', { inProgress: true });
        });
        
        this.fileManager.on('uploadProgress', ({ file, progress }) => {
            console.log(`上传进度 ${file.name}: ${progress.toFixed(1)}%`);
        });
        
        this.fileManager.on('uploadComplete', ({ file }) => {
            console.log('上传完成:', file.name);
            showNotification(`${file.name} 上传成功`, 'success');
            this.updateFileList();
        });
        
        this.fileManager.on('uploadError', ({ file, error }) => {
            console.error('上传失败:', file?.name, error);
            showNotification(`上传失败: ${error}`, 'error');
        });
        
        this.fileManager.on('queueComplete', () => {
            console.log('所有文件上传完成');
            this.state.update('uploads', { inProgress: false });
            hideLoading();
        });
    }

    /**
     * 初始化播放器
     */
    initPlayer() {
        const prefs = this.state.get('preferences');
        
        this.player = new LecturePlayer('photo-canvas', {
            transitionDuration: prefs.transitionDuration,
            transitionType: prefs.transitionType,
            autoPlay: false,
            volume: prefs.volume
        });
        
        // 监听播放器事件
        this.player.on('loaded', (data) => {
            console.log('项目已加载:', data);
            this.updatePlayerUI();
            
            // 加载时间轴数据
            if (this.timeline && data.photos) {
                const photos = data.photos.map((url, index) => ({
                    url,
                    timestamp: data.timestamps[index]
                }));
                this.timeline.loadData(photos, data.duration);
            }
        });
        
        this.player.on('play', () => {
            const playBtn = document.getElementById('play-btn');
            if (playBtn) playBtn.innerHTML = '<i class="fas fa-pause"></i>';
            
            const playStatus = document.querySelector('.play-status');
            if (playStatus) playStatus.classList.add('playing');
            
            this.state.update('session', { isPlaying: true });
        });
        
        this.player.on('pause', () => {
            const playBtn = document.getElementById('play-btn');
            if (playBtn) playBtn.innerHTML = '<i class="fas fa-play"></i>';
            
            const playStatus = document.querySelector('.play-status');
            if (playStatus) playStatus.classList.remove('playing');
            
            this.state.update('session', { isPlaying: false });
        });
        
        this.player.on('stop', () => {
            const playBtn = document.getElementById('play-btn');
            if (playBtn) playBtn.innerHTML = '<i class="fas fa-play"></i>';
            
            const playStatus = document.querySelector('.play-status');
            if (playStatus) playStatus.classList.remove('playing');
            
            this.updateTimeDisplay(0, this.player.state.duration);
            this.state.update('session', { isPlaying: false, currentTime: 0 });
        });
        
        this.player.on('timeupdate', (data) => {
            this.updateTimeDisplay(data.currentTime, data.duration);
            
            // 更新时间轴
            if (this.timeline) {
                this.timeline.updateProgress(data.currentTime);
                this.timeline.highlightCurrentMarker();
            }
            
            this.state.update('session', { 
                currentTime: data.currentTime,
                duration: data.duration
            });
        });
        
        this.player.on('photochange', (data) => {
            console.log('照片切换:', data.index);
        });
        
        this.player.on('volumechange', (data) => {
            this.state.set('preferences.volume', data.volume);
        });
        
        this.player.on('ratechange', (data) => {
            this.state.set('preferences.playbackRate', data.rate);
        });
        
        this.player.on('error', (data) => {
            console.error('播放器错误:', data);
            showNotification(data.message, 'error');
        });
    }

    /**
     * 初始化时间轴
     */
    initTimeline() {
        const timelineContainer = document.querySelector('.timeline-container');
        if (!timelineContainer) {
            console.warn('时间轴容器未找到');
            return;
        }
        
        this.timeline = new Timeline(timelineContainer, {
            height: 60,
            markerColor: '#4CAF50',
            progressColor: '#2196F3',
            hoverColor: '#FFC107'
        });
        
        // 监听时间轴事件
        this.timeline.on('seek', ({ time }) => {
            if (this.player) {
                this.player.seek(time);
            }
        });
        
        this.timeline.on('markerClick', ({ index, photo }) => {
            console.log('点击标记点:', index, photo);
            if (this.player) {
                this.player.seek(photo.timestamp);
            }
        });
        
        this.timeline.on('markerHover', ({ index, photo }) => {
            // 可以显示照片预览
            console.log('悬停标记点:', index);
        });
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 侧边栏导航
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const view = e.currentTarget.dataset.view;
                this.showView(view);
            });
        });
        
        // 文件上传
        this.initFileUpload();
        
        // 播放控制
        this.initPlaybackControls();
        
        // 项目管理
        this.initProjectManagement();
        
        // 键盘快捷键
        this.initKeyboardShortcuts();
    }

    /**
     * 初始化文件上传
     */
    initFileUpload() {
        const audioDropzone = document.getElementById('audio-dropzone');
        const photoDropzone = document.getElementById('photo-dropzone');
        const audioInput = document.getElementById('audio-input');
        const photoInput = document.getElementById('photo-input');
        
        if (audioDropzone && audioInput) {
            this.fileManager.initDropzone(audioDropzone, audioInput, 'audio');
        }
        
        if (photoDropzone && photoInput) {
            this.fileManager.initDropzone(photoDropzone, photoInput, 'image');
        }
        
        // 创建项目按钮
        const createBtn = document.getElementById('create-project-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => {
                this.createProject();
            });
        }
    }

    /**
     * 更新文件列表
     */
    async updateFileList() {
        try {
            const data = await this.api.get('/file/list');
            
            // 更新状态
            this.state.update('uploads', {
                audioFiles: data.audio_files || [],
                photoFiles: data.photo_files || []
            });
            
            // 更新音频列表
            const audioList = document.getElementById('audio-list');
            if (audioList && data.audio_files) {
                audioList.innerHTML = data.audio_files.map(file => `
                    <div class="file-item">
                        <i class="fas fa-music"></i>
                        <span>${file.name}</span>
                        <button class="btn-icon" onclick="app.deleteFile('${file.path}', 'audio')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                `).join('');
            }
            
            // 更新照片列表
            const photoList = document.getElementById('photo-list');
            if (photoList && data.photo_files) {
                photoList.innerHTML = data.photo_files.map(file => `
                    <div class="file-item">
                        <i class="fas fa-image"></i>
                        <span>${file.name}</span>
                        <button class="btn-icon" onclick="app.deleteFile('${file.path}', 'photo')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                `).join('');
            }
            
        } catch (error) {
            console.error('获取文件列表失败:', error);
        }
    }

    /**
     * 删除文件
     */
    async deleteFile(path, type) {
        confirm('确认删除该文件？', async () => {
            try {
                await this.api.post('/file/delete', { path });
                showNotification('文件已删除', 'success');
                this.updateFileList();
            } catch (error) {
                showNotification('删除失败: ' + error.message, 'error');
            }
        });
    }

    /**
     * 创建项目
     */
    async createProject() {
        const projectName = prompt('请输入项目名称:');
        if (!projectName) return;
        
        const loader = showLoading('创建项目中...');
        
        try {
            const data = await this.api.post('/project/create', {
                title: projectName
            });
            
            showNotification('项目创建成功', 'success');
            await this.loadProjects();
            
        } catch (error) {
            showNotification('创建项目失败: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    }

    /**
     * 加载项目列表
     */
    async loadProjects() {
        try {
            const data = await this.api.get('/project/list');
            
            // 更新状态
            this.state.set('projects', data.projects || []);
            
            const projectsGrid = document.getElementById('projects-grid');
            if (!projectsGrid) return;
            
            projectsGrid.innerHTML = (data.projects || []).map(project => `
                <div class="project-card" data-project-id="${project.id}">
                    <div class="project-thumbnail">
                        <i class="fas fa-folder"></i>
                    </div>
                    <div class="project-info">
                        <h3>${project.title}</h3>
                        <p>${project.audio_duration ? formatTime(project.audio_duration) : '无音频'}</p>
                        <p>${project.photo_count || 0} 张照片</p>
                        <small>${new Date(project.created_at).toLocaleString()}</small>
                    </div>
                    <div class="project-actions">
                        <button class="btn btn-primary" onclick="app.openProject('${project.id}')">
                            <i class="fas fa-play"></i> 打开
                        </button>
                        <button class="btn btn-secondary" onclick="app.editProject('${project.id}')">
                            <i class="fas fa-edit"></i> 编辑
                        </button>
                        <button class="btn btn-danger" onclick="app.deleteProject('${project.id}')">
                            <i class="fas fa-trash"></i> 删除
                        </button>
                    </div>
                </div>
            `).join('');
            
        } catch (error) {
            console.error('加载项目列表失败:', error);
        }
    }

    /**
     * 打开项目
     */
    async openProject(projectId) {
        const loader = showLoading('加载项目中...');
        
        try {
            // 获取项目详情
            const project = await this.api.get(`/project/load/${projectId}`);
            
            // 更新状态
            this.state.update('session', {
                projectId: project.id,
                projectName: project.title
            });
            
            // 准备数据
            const audioUrl = project.audio_path;
            const photoUrls = project.timeline.map(item => item.photo);
            const photoTimestamps = project.timeline.map(item => item.offset);
            
            // 加载到播放器
            await this.player.loadProject(audioUrl, photoUrls, photoTimestamps);
            
            // 切换到播放器视图
            this.showView('player');
            
            showNotification('项目加载成功', 'success');
            
        } catch (error) {
            console.error('打开项目失败:', error);
            showNotification('打开项目失败: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    }

    /**
     * 删除项目
     */
    async deleteProject(projectId) {
        confirm('确认删除该项目？', async () => {
            try {
                await this.api.delete(`/project/delete/${projectId}`);
                showNotification('项目已删除', 'success');
                await this.loadProjects();
            } catch (error) {
                showNotification('删除失败: ' + error.message, 'error');
            }
        });
    }

    /**
     * 初始化播放控制
     */
    initPlaybackControls() {
        // 播放/暂停
        const playBtn = document.getElementById('play-btn');
        if (playBtn) {
            playBtn.addEventListener('click', () => {
                if (this.player.state.isPlaying) {
                    this.player.pause();
                } else {
                    this.player.play();
                }
            });
        }
        
        // 停止
        const stopBtn = document.getElementById('stop-btn');
        if (stopBtn) {
            stopBtn.addEventListener('click', () => {
                this.player.stop();
            });
        }
        
        // 音量控制
        const volumeSlider = document.getElementById('volume-slider');
        if (volumeSlider) {
            volumeSlider.addEventListener('input', (e) => {
                const volume = e.target.value / 100;
                this.player.setVolume(volume);
            });
        }
        
        // 播放速率
        const speedButtons = document.querySelectorAll('.speed-btn');
        speedButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const rate = parseFloat(e.target.dataset.rate);
                this.player.setPlaybackRate(rate);
                
                speedButtons.forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
            });
        });
    }

    /**
     * 初始化键盘快捷键
     */
    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // 空格键：播放/暂停
            if (e.code === 'Space' && !e.target.matches('input, textarea')) {
                e.preventDefault();
                if (this.player) {
                    if (this.player.state.isPlaying) {
                        this.player.pause();
                    } else {
                        this.player.play();
                    }
                }
            }
            
            // 左箭头：后退5秒
            if (e.code === 'ArrowLeft' && !e.target.matches('input, textarea')) {
                e.preventDefault();
                if (this.player) {
                    const newTime = Math.max(0, this.player.state.currentTime - 5);
                    this.player.seek(newTime);
                }
            }
            
            // 右箭头：前进5秒
            if (e.code === 'ArrowRight' && !e.target.matches('input, textarea')) {
                e.preventDefault();
                if (this.player) {
                    const newTime = Math.min(this.player.state.duration, this.player.state.currentTime + 5);
                    this.player.seek(newTime);
                }
            }
            
            // 上箭头：增加音量
            if (e.code === 'ArrowUp' && !e.target.matches('input, textarea')) {
                e.preventDefault();
                if (this.player) {
                    const newVolume = Math.min(1, this.player.state.volume + 0.1);
                    this.player.setVolume(newVolume);
                }
            }
            
            // 下箭头：减少音量
            if (e.code === 'ArrowDown' && !e.target.matches('input, textarea')) {
                e.preventDefault();
                if (this.player) {
                    const newVolume = Math.max(0, this.player.state.volume - 0.1);
                    this.player.setVolume(newVolume);
                }
            }
        });
    }

    /**
     * 更新时间显示
     */
    updateTimeDisplay(currentTime, duration) {
        const currentTimeEl = document.getElementById('current-time');
        const totalTimeEl = document.getElementById('total-time');
        
        if (currentTimeEl) currentTimeEl.textContent = formatTime(currentTime);
        if (totalTimeEl) totalTimeEl.textContent = formatTime(duration);
    }

    /**
     * 更新播放器 UI
     */
    updatePlayerUI() {
        const state = this.player.getState();
        this.updateTimeDisplay(state.currentTime, state.duration);
        
        const volumeSlider = document.getElementById('volume-slider');
        if (volumeSlider) {
            volumeSlider.value = state.volume * 100;
        }
    }

    /**
     * 初始化项目管理
     */
    initProjectManagement() {
        const refreshBtn = document.getElementById('refresh-projects-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this.loadProjects();
            });
        }
    }

    /**
     * 切换视图
     */
    showView(viewName) {
        // 更新状态
        this.state.set('ui.currentView', viewName);
        
        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.view === viewName) {
                item.classList.add('active');
            }
        });
        
        // 切换视图
        document.querySelectorAll('.view').forEach(view => {
            view.classList.remove('active');
        });
        
        const targetView = document.getElementById(`${viewName}-view`);
        if (targetView) {
            targetView.classList.add('active');
        }
    }

    /**
     * 恢复用户偏好设置
     */
    restorePreferences() {
        const prefs = this.state.get('preferences');
        
        // 恢复音量
        if (this.player && prefs.volume !== undefined) {
            this.player.setVolume(prefs.volume);
        }
        
        // 恢复播放速率
        if (this.player && prefs.playbackRate !== undefined) {
            this.player.setPlaybackRate(prefs.playbackRate);
        }
        
        // 应用其他偏好设置
        this.applyPreferences(prefs);
    }

    /**
     * 应用偏好设置
     */
    applyPreferences(prefs) {
        // 主题
        if (prefs.theme) {
            document.body.setAttribute('data-theme', prefs.theme);
        }
        
        // 过渡效果
        if (this.player && prefs.transitionType) {
            this.player.setOptions({
                transitionType: prefs.transitionType,
                transitionDuration: prefs.transitionDuration
            });
        }
    }

    /**
     * 编辑项目
     */
    editProject(projectId) {
        showNotification('编辑功能开发中', 'info');
    }

    /**
     * 获取应用状态快照
     */
    getSnapshot() {
        return {
            state: this.state.getSnapshot(),
            player: this.player?.getState(),
            timeline: this.timeline?.getState()
        };
    }
}

// 创建全局应用实例
window.app = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});

export default App;
