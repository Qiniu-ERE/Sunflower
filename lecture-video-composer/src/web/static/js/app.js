/**
 * 主应用程序
 */

import { LecturePlayer } from './player.js';
import { APIClient, showNotification, showLoading, hideLoading, confirm, formatTime } from './utils.js';

class App {
    constructor() {
        this.api = new APIClient('/api');
        this.player = null;
        this.currentSessionId = null;
        this.currentProject = null;
        
        // 初始化
        this.init();
    }

    /**
     * 初始化应用
     */
    async init() {
        try {
            // 初始化播放器
            this.initPlayer();
            
            // 绑定事件
            this.bindEvents();
            
            // 加载项目列表
            await this.loadProjects();
            
            // 显示上传视图
            this.showView('upload');
            
        } catch (error) {
            console.error('应用初始化失败:', error);
            showNotification('应用初始化失败', 'error');
        }
    }

    /**
     * 初始化播放器
     */
    initPlayer() {
        this.player = new LecturePlayer('photo-canvas', {
            transitionDuration: 0.5,
            transitionType: 'fade',
            autoPlay: false,
            volume: 0.8
        });
        
        // 监听播放器事件
        this.player.on('loaded', (data) => {
            console.log('项目已加载:', data);
            this.updatePlayerUI();
        });
        
        this.player.on('play', () => {
            document.getElementById('play-btn').innerHTML = '<i class="fas fa-pause"></i>';
            document.querySelector('.play-status').classList.add('playing');
        });
        
        this.player.on('pause', () => {
            document.getElementById('play-btn').innerHTML = '<i class="fas fa-play"></i>';
            document.querySelector('.play-status').classList.remove('playing');
        });
        
        this.player.on('stop', () => {
            document.getElementById('play-btn').innerHTML = '<i class="fas fa-play"></i>';
            document.querySelector('.play-status').classList.remove('playing');
            this.updateTimeDisplay(0, this.player.state.duration);
        });
        
        this.player.on('timeupdate', (data) => {
            this.updateTimeDisplay(data.currentTime, data.duration);
            this.updateTimeline(data.currentTime, data.duration);
        });
        
        this.player.on('photochange', (data) => {
            console.log('照片切换:', data.index);
        });
        
        this.player.on('error', (data) => {
            console.error('播放器错误:', data);
            showNotification(data.message, 'error');
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
    }

    /**
     * 初始化文件上传
     */
    initFileUpload() {
        const audioDropzone = document.getElementById('audio-dropzone');
        const photoDropzone = document.getElementById('photo-dropzone');
        const audioInput = document.getElementById('audio-input');
        const photoInput = document.getElementById('photo-input');
        
        // 音频上传
        this.setupDropzone(audioDropzone, audioInput, 'audio', false);
        
        // 照片上传
        this.setupDropzone(photoDropzone, photoInput, 'image', true);
        
        // 创建项目按钮
        document.getElementById('create-project-btn').addEventListener('click', () => {
            this.createProject();
        });
    }

    /**
     * 设置拖拽区域
     */
    setupDropzone(dropzone, input, fileType, multiple) {
        // 点击上传
        dropzone.addEventListener('click', () => {
            input.click();
        });
        
        // 文件选择
        input.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            this.handleFiles(files, fileType);
        });
        
        // 拖拽上传
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });
        
        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });
        
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            
            const files = Array.from(e.dataTransfer.files);
            this.handleFiles(files, fileType);
        });
    }

    /**
     * 处理上传文件
     */
    async handleFiles(files, fileType) {
        const loader = showLoading('上传文件中...');
        
        try {
            for (const file of files) {
                await this.uploadFile(file, fileType);
            }
            
            showNotification('文件上传成功', 'success');
            this.updateFileList();
            
        } catch (error) {
            console.error('文件上传失败:', error);
            showNotification('文件上传失败: ' + error.message, 'error');
        } finally {
            hideLoading();
        }
    }

    /**
     * 上传单个文件
     */
    async uploadFile(file, fileType) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('type', fileType);
        
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || '上传失败');
        }
        
        return await response.json();
    }

    /**
     * 更新文件列表
     */
    async updateFileList() {
        try {
            const data = await this.api.get('/files/list');
            
            // 更新音频列表
            const audioList = document.getElementById('audio-list');
            audioList.innerHTML = data.audio_files.map(file => `
                <div class="file-item">
                    <i class="fas fa-music"></i>
                    <span>${file.name}</span>
                    <button class="btn-icon" onclick="app.deleteFile('${file.path}', 'audio')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `).join('');
            
            // 更新照片列表
            const photoList = document.getElementById('photo-list');
            photoList.innerHTML = data.photo_files.map(file => `
                <div class="file-item">
                    <i class="fas fa-image"></i>
                    <span>${file.name}</span>
                    <button class="btn-icon" onclick="app.deleteFile('${file.path}', 'photo')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            `).join('');
            
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
                await this.api.delete(`/files/${encodeURIComponent(path)}`);
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
            const data = await this.api.post('/projects/create', {
                name: projectName
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
            const data = await this.api.get('/projects/list');
            
            const projectsGrid = document.getElementById('projects-grid');
            projectsGrid.innerHTML = data.projects.map(project => `
                <div class="project-card" data-project-id="${project.id}">
                    <div class="project-thumbnail">
                        <i class="fas fa-folder"></i>
                    </div>
                    <div class="project-info">
                        <h3>${project.name}</h3>
                        <p>${project.audio_file ? '已关联音频' : '未关联音频'}</p>
                        <p>${project.photo_count} 张照片</p>
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
            const project = await this.api.get(`/projects/${projectId}`);
            this.currentProject = project;
            
            // 创建会话
            const session = await this.api.post('/playback/session/create', {
                project_id: projectId
            });
            this.currentSessionId = session.session_id;
            
            // 加载到播放器
            const audioUrl = `/api/files/${encodeURIComponent(project.audio_file)}`;
            const photoUrls = project.photos.map(p => `/api/files/${encodeURIComponent(p.path)}`);
            const photoTimestamps = project.photos.map(p => p.timestamp);
            
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
                await this.api.delete(`/projects/${projectId}`);
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
        document.getElementById('play-btn').addEventListener('click', () => {
            if (this.player.state.isPlaying) {
                this.player.pause();
            } else {
                this.player.play();
            }
        });
        
        // 停止
        document.getElementById('stop-btn').addEventListener('click', () => {
            this.player.stop();
        });
        
        // 时间轴点击
        const timeline = document.querySelector('.timeline');
        timeline.addEventListener('click', (e) => {
            const rect = timeline.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            const time = percent * this.player.state.duration;
            this.player.seek(time);
        });
        
        // 音量控制
        const volumeSlider = document.getElementById('volume-slider');
        volumeSlider.addEventListener('input', (e) => {
            const volume = e.target.value / 100;
            this.player.setVolume(volume);
        });
        
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
     * 更新时间显示
     */
    updateTimeDisplay(currentTime, duration) {
        document.getElementById('current-time').textContent = formatTime(currentTime);
        document.getElementById('total-time').textContent = formatTime(duration);
    }

    /**
     * 更新时间轴
     */
    updateTimeline(currentTime, duration) {
        const percent = (currentTime / duration) * 100;
        document.querySelector('.timeline-progress').style.width = `${percent}%`;
    }

    /**
     * 更新播放器 UI
     */
    updatePlayerUI() {
        const state = this.player.getState();
        this.updateTimeDisplay(state.currentTime, state.duration);
        document.getElementById('volume-slider').value = state.volume * 100;
    }

    /**
     * 初始化项目管理
     */
    initProjectManagement() {
        // 刷新项目列表按钮
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
     * 编辑项目
     */
    editProject(projectId) {
        showNotification('编辑功能开发中', 'info');
    }
}

// 创建全局应用实例
window.app = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});

export default App;
