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
            
            // 创建或获取会话
            await this.ensureSession();
            
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
            
            // 加载初始文件列表
            await this.updateFileList();
            
            // 恢复用户偏好设置
            this.restorePreferences();
            
            // 初始化完成后，订阅preferences变化
            this.state.subscribe('preferences', (prefs) => {
                console.log('偏好设置更新:', prefs);
                this.applyPreferences(prefs);
            });
            
        } catch (error) {
            console.error('应用初始化失败:', error);
            showNotification('应用初始化失败', 'error');
        }
    }

    /**
     * 确保会话存在
     */
    async ensureSession() {
        try {
            // 尝试获取现有会话信息
            const sessionInfo = await this.api.get('/session/info');
            if (sessionInfo && sessionInfo.session_id) {
                this.state.set('session.sessionId', sessionInfo.session_id);
                console.log('使用现有会话:', sessionInfo.session_id);
                return;
            }
        } catch (error) {
            console.log('未找到现有会话，创建新会话');
        }
        
        // 创建新会话
        try {
            const data = await this.api.post('/session/create', {});
            if (data && data.session_id) {
                this.state.set('session.sessionId', data.session_id);
                console.log('创建新会话:', data.session_id);
            }
        } catch (error) {
            console.error('创建会话失败:', error);
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
        
        // 注意：不在这里订阅preferences，避免初始化时的错误
        // preferences的变更会在restorePreferences中处理
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
        try {
            const prefs = this.state.get('preferences') || {};
            
            this.player = new LecturePlayer('photo-canvas', {
                transitionDuration: prefs.transitionDuration || 300,
                transitionType: prefs.transitionType || 'fade',
                autoPlay: false,
                volume: prefs.volume !== undefined ? prefs.volume : 1.0
            });
        } catch (error) {
            console.error('播放器初始化失败:', error);
            // 创建一个空的播放器占位对象，避免后续代码出错
            this.player = {
                on: () => {},
                setVolume: () => {},
                setPlaybackRate: () => {},
                setOptions: () => {},
                getState: () => ({ currentTime: 0, duration: 0, volume: 1 }),
                loadProject: async () => {
                    throw new Error('播放器未正确初始化');
                },
                play: () => {},
                pause: () => {},
                stop: () => {},
                seek: () => {},
                state: { isPlaying: false, currentTime: 0, duration: 0, volume: 1 }
            };
            return;
        }
        
        // 监听播放器事件
        this.player.on('loaded', (data) => {
            console.log('项目已加载:', data);
            this.updatePlayerUI();
            
            // 隐藏占位符，显示播放器
            const photoPlaceholder = document.getElementById('photo-placeholder');
            if (photoPlaceholder) {
                photoPlaceholder.classList.remove('show');
            }
            
            // 隐藏空状态提示
            const playerEmpty = document.getElementById('player-empty');
            if (playerEmpty) {
                playerEmpty.style.display = 'none';
            }
            
            // 显示播放器容器
            const playerContainer = document.querySelector('.player-container');
            if (playerContainer) {
                playerContainer.style.display = 'block';
            }
            
            // 启用播放控制按钮
            const playBtn = document.getElementById('play-btn');
            const stopBtn = document.getElementById('stop-btn');
            
            console.log('准备启用播放按钮...');
            console.log('播放按钮before:', playBtn, 'disabled=', playBtn?.disabled);
            console.log('停止按钮before:', stopBtn, 'disabled=', stopBtn?.disabled);
            
            if (playBtn) {
                playBtn.disabled = false;
                playBtn.removeAttribute('disabled');
                console.log('播放按钮after:', 'disabled=', playBtn.disabled);
            }
            if (stopBtn) {
                stopBtn.disabled = false;
                stopBtn.removeAttribute('disabled');
                console.log('停止按钮after:', 'disabled=', stopBtn.disabled);
            }
            
            // 更新项目信息显示
            const projectName = this.state.get('session.projectName');
            const currentProjectName = document.getElementById('current-project-name');
            if (currentProjectName && projectName) {
                currentProjectName.textContent = projectName;
            }
            
            // 更新快速信息面板
            const quickInfo = document.getElementById('project-quick-info');
            if (quickInfo) {
                quickInfo.style.display = 'block';
                
                const quickDuration = document.getElementById('quick-duration');
                const quickPhotos = document.getElementById('quick-photos');
                const quickStatus = document.getElementById('quick-status');
                
                if (quickDuration) quickDuration.textContent = formatTime(data.duration);
                if (quickPhotos) quickPhotos.textContent = `${data.photoCount} 张`;
                if (quickStatus) quickStatus.textContent = '就绪';
            }
            
            // 加载时间轴数据
            if (this.timeline && data.photos && data.timestamps) {
                console.log('App: 准备加载时间轴数据', {
                    photoCount: data.photos.length,
                    timestampCount: data.timestamps.length,
                    duration: data.duration
                });
                
                const photos = data.photos.map((photo, index) => ({
                    url: photo.url,
                    timestamp: data.timestamps[index]
                }));
                
                console.log('App: 调用timeline.loadData', {
                    photos: photos.length,
                    duration: data.duration
                });
                
                this.timeline.loadData(photos, data.duration);
            } else {
                console.warn('App: 无法加载时间轴数据', {
                    hasTimeline: !!this.timeline,
                    hasPhotos: !!data.photos,
                    hasTimestamps: !!data.timestamps
                });
            }
        });
        
        this.player.on('play', () => {
            const playBtn = document.getElementById('play-btn');
            if (playBtn) {
                const icon = playBtn.querySelector('.control-icon');
                if (icon) icon.textContent = '⏸️';
            }
            
            const playStatus = document.querySelector('.play-status');
            if (playStatus) playStatus.classList.add('playing');
            
            this.state.update('session', { isPlaying: true });
        });
        
        this.player.on('pause', () => {
            const playBtn = document.getElementById('play-btn');
            if (playBtn) {
                const icon = playBtn.querySelector('.control-icon');
                if (icon) icon.textContent = '▶️';
            }
            
            const playStatus = document.querySelector('.play-status');
            if (playStatus) playStatus.classList.remove('playing');
            
            this.state.update('session', { isPlaying: false });
        });
        
        this.player.on('stop', () => {
            const playBtn = document.getElementById('play-btn');
            if (playBtn) {
                const icon = playBtn.querySelector('.control-icon');
                if (icon) icon.textContent = '▶️';
            }
            
            const playStatus = document.querySelector('.play-status');
            if (playStatus) playStatus.classList.remove('playing');
            
            this.updateTimeDisplay(0, this.player.state.duration);
            this.state.update('session', { isPlaying: false, currentTime: 0 });
        });
        
        this.player.on('timeupdate', (data) => {
            console.log('App: timeupdate事件', { 
                currentTime: data.currentTime.toFixed(2), 
                duration: data.duration.toFixed(2),
                hasTimeline: !!this.timeline 
            });
            
            this.updateTimeDisplay(data.currentTime, data.duration);
            
            // 更新时间轴
            if (this.timeline) {
                console.log('App: 调用timeline.updateProgress', data.currentTime);
                this.timeline.updateProgress(data.currentTime);
                this.timeline.highlightCurrentMarker();
            } else {
                console.warn('App: timeline未初始化，无法更新进度');
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
            console.warn('时间轴容器未找到，将在播放器视图中初始化');
            return;
        }
        
        try {
            this.timeline = new Timeline(timelineContainer, {
                height: 6,
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
        } catch (error) {
            console.error('时间轴初始化失败:', error);
            this.timeline = null;
        }
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 帮助按钮
        const helpBtn = document.getElementById('help-btn');
        if (helpBtn) {
            helpBtn.addEventListener('click', () => {
                window.open('/help.html', '_blank');
            });
        }
        
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
        
        // 视频导出
        this.initExport();
        
        // 键盘快捷键
        this.initKeyboardShortcuts();
    }

    /**
     * 初始化文件上传
     */
    initFileUpload() {
        const audioDropzone = document.getElementById('audio-drop-zone');
        const photoDropzone = document.getElementById('photos-drop-zone');
        const audioInput = document.getElementById('audio-input');
        const photoInput = document.getElementById('photos-input');
        
        if (audioDropzone && audioInput) {
            try {
                this.fileManager.initDropzone(audioDropzone, audioInput, 'audio');
            } catch (error) {
                console.error('初始化音频上传区失败:', error);
            }
        } else {
            console.warn('音频上传区元素未找到');
        }
        
        if (photoDropzone && photoInput) {
            try {
                this.fileManager.initDropzone(photoDropzone, photoInput, 'image');
            } catch (error) {
                console.error('初始化照片上传区失败:', error);
            }
        } else {
            console.warn('照片上传区元素未找到');
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
            const sessionId = this.state.get('session.sessionId');
            const params = sessionId ? `?session_id=${sessionId}` : '';
            const response = await this.api.get(`/file/list${params}`);
            
            console.log('文件列表数据:', response);
            
            // API返回格式: { data: { audio: [...], photos: [...] }, success: true }
            const audioFiles = response.data?.audio || [];
            const photoFiles = response.data?.photos || [];
            
            // 更新状态
            this.state.update('uploads', {
                audioFiles: audioFiles,
                photoFiles: photoFiles
            });
            
            // 更新音频列表
            const audioList = document.getElementById('audio-file-list');
            const audioControls = document.getElementById('audio-controls');
            if (audioList) {
                const validAudioFiles = audioFiles.filter(file => file.filename !== '.DS_Store');
                if (validAudioFiles.length > 0) {
                    audioList.innerHTML = validAudioFiles
                        .map(file => `
                            <div class="file-item">
                                <label class="checkbox-label">
                                    <input type="checkbox" class="file-checkbox audio-checkbox" data-path="${file.path}">
                                </label>
                                <span class="file-icon">🎵</span>
                                <span class="file-name">${file.filename}</span>
                                <button class="btn-icon" onclick="app.deleteFile('${file.path}', 'audio')">
                                    <span>🗑️</span>
                                </button>
                            </div>
                        `).join('');
                    if (audioControls) audioControls.style.display = 'flex';
                } else {
                    audioList.innerHTML = '';
                    if (audioControls) audioControls.style.display = 'none';
                }
            }
            
            // 更新照片列表
            const photoList = document.getElementById('photos-file-list');
            const photosControls = document.getElementById('photos-controls');
            if (photoList) {
                const validPhotoFiles = photoFiles.filter(file => file.filename !== '.DS_Store');
                if (validPhotoFiles.length > 0) {
                    photoList.innerHTML = validPhotoFiles
                        .map(file => `
                            <div class="file-item">
                                <label class="checkbox-label">
                                    <input type="checkbox" class="file-checkbox photo-checkbox" data-path="${file.path}">
                                </label>
                                <span class="file-icon">📸</span>
                                <span class="file-name">${file.filename}</span>
                                <button class="btn-icon" onclick="app.deleteFile('${file.path}', 'photo')">
                                    <span>🗑️</span>
                                </button>
                            </div>
                        `).join('');
                    if (photosControls) photosControls.style.display = 'flex';
                } else {
                    photoList.innerHTML = '';
                    if (photosControls) photosControls.style.display = 'none';
                }
            }
            
            // 重新绑定复选框事件
            this.bindFileCheckboxEvents();
            
            // 更新创建项目按钮状态
            this.updateCreateButtonState(audioFiles, photoFiles);
            
        } catch (error) {
            console.error('获取文件列表失败:', error);
        }
    }
    
    /**
     * 更新创建项目按钮状态
     */
    updateCreateButtonState(audioFiles, photoFiles) {
        const createBtn = document.getElementById('create-project-btn');
        if (createBtn) {
            const hasAudio = audioFiles && audioFiles.length > 0;
            const hasPhotos = photoFiles && photoFiles.length > 0;
            
            if (hasAudio && hasPhotos) {
                createBtn.disabled = false;
                createBtn.classList.remove('disabled');
            } else {
                createBtn.disabled = true;
                createBtn.classList.add('disabled');
            }
        }
    }

    /**
     * 绑定文件复选框事件
     */
    bindFileCheckboxEvents() {
        // 音频全选复选框
        const audioSelectAll = document.getElementById('audio-select-all');
        if (audioSelectAll) {
            audioSelectAll.addEventListener('change', (e) => {
                const checkboxes = document.querySelectorAll('.audio-checkbox');
                checkboxes.forEach(cb => cb.checked = e.target.checked);
                this.updateDeleteButtonState('audio');
            });
        }
        
        // 照片全选复选框
        const photosSelectAll = document.getElementById('photos-select-all');
        if (photosSelectAll) {
            photosSelectAll.addEventListener('change', (e) => {
                const checkboxes = document.querySelectorAll('.photo-checkbox');
                checkboxes.forEach(cb => cb.checked = e.target.checked);
                this.updateDeleteButtonState('photos');
            });
        }
        
        // 音频复选框变化事件
        document.querySelectorAll('.audio-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateDeleteButtonState('audio');
                this.updateSelectAllState('audio');
            });
        });
        
        // 照片复选框变化事件
        document.querySelectorAll('.photo-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateDeleteButtonState('photos');
                this.updateSelectAllState('photos');
            });
        });
        
        // 音频删除选中按钮
        const audioDeleteBtn = document.getElementById('audio-delete-selected');
        if (audioDeleteBtn) {
            audioDeleteBtn.replaceWith(audioDeleteBtn.cloneNode(true));
            const newAudioDeleteBtn = document.getElementById('audio-delete-selected');
            newAudioDeleteBtn.addEventListener('click', () => {
                this.deleteSelectedFiles('audio');
            });
        }
        
        // 照片删除选中按钮
        const photosDeleteBtn = document.getElementById('photos-delete-selected');
        if (photosDeleteBtn) {
            photosDeleteBtn.replaceWith(photosDeleteBtn.cloneNode(true));
            const newPhotosDeleteBtn = document.getElementById('photos-delete-selected');
            newPhotosDeleteBtn.addEventListener('click', () => {
                this.deleteSelectedFiles('photos');
            });
        }
    }
    
    /**
     * 更新删除按钮状态
     */
    updateDeleteButtonState(type) {
        const deleteBtn = document.getElementById(`${type === 'audio' ? 'audio' : 'photos'}-delete-selected`);
        if (!deleteBtn) return;
        
        const checkboxes = document.querySelectorAll(`.${type === 'audio' ? 'audio' : 'photo'}-checkbox`);
        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        
        deleteBtn.disabled = checkedCount === 0;
    }
    
    /**
     * 更新全选复选框状态
     */
    updateSelectAllState(type) {
        const selectAll = document.getElementById(`${type === 'audio' ? 'audio' : 'photos'}-select-all`);
        if (!selectAll) return;
        
        const checkboxes = document.querySelectorAll(`.${type === 'audio' ? 'audio' : 'photo'}-checkbox`);
        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        const totalCount = checkboxes.length;
        
        selectAll.checked = totalCount > 0 && checkedCount === totalCount;
        selectAll.indeterminate = checkedCount > 0 && checkedCount < totalCount;
    }
    
    /**
     * 删除选中的文件
     */
    async deleteSelectedFiles(type) {
        const checkboxes = document.querySelectorAll(`.${type === 'audio' ? 'audio' : 'photo'}-checkbox:checked`);
        const paths = Array.from(checkboxes).map(cb => cb.dataset.path);
        
        if (paths.length === 0) {
            showNotification('请先选择要删除的文件', 'warning');
            return;
        }
        
        confirm(`确认删除选中的 ${paths.length} 个文件？`, async () => {
            const loader = showLoading('删除文件中...');
            
            try {
                const sessionId = this.state.get('session.sessionId');
                let successCount = 0;
                let failCount = 0;
                
                // 批量删除文件
                for (const path of paths) {
                    try {
                        await this.api.post('/file/delete', { 
                            filepath: path,
                            session_id: sessionId
                        });
                        successCount++;
                    } catch (error) {
                        console.error('删除文件失败:', path, error);
                        failCount++;
                    }
                }
                
                // 显示结果
                if (failCount === 0) {
                    showNotification(`成功删除 ${successCount} 个文件`, 'success');
                } else {
                    showNotification(`删除完成: 成功 ${successCount} 个，失败 ${failCount} 个`, 'warning');
                }
                
                // 刷新文件列表
                await this.updateFileList();
                
            } catch (error) {
                showNotification('删除失败: ' + error.message, 'error');
            } finally {
                hideLoading();
            }
        });
    }

    /**
     * 删除文件
     */
    async deleteFile(path, type) {
        confirm('确认删除该文件？', async () => {
            try {
                const sessionId = this.state.get('session.sessionId');
                await this.api.post('/file/delete', { 
                    filepath: path,  // 修改为 filepath 以匹配后端参数名
                    session_id: sessionId
                });
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
        // 从输入框获取项目名称
        const projectTitleInput = document.getElementById('project-title');
        const projectName = projectTitleInput?.value.trim() || `项目_${new Date().toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        }).replace(/\//g, '-').replace(/:/g, '-').replace(/ /g, '_')}`;
        
        // 获取已上传的文件
        const uploads = this.state.get('uploads');
        const audioFiles = uploads?.audioFiles || [];
        const photoFiles = uploads?.photoFiles || [];
        
        // 验证是否有必需的文件
        if (audioFiles.length === 0) {
            showNotification('请先上传音频文件', 'error');
            return;
        }
        
        if (photoFiles.length === 0) {
            showNotification('请先上传照片文件', 'error');
            return;
        }
        
        const loader = showLoading('创建项目中...');
        
        try {
            const sessionId = this.state.get('session.sessionId');
            
            // 准备文件路径（排除.DS_Store等系统文件）
            const audioFile = audioFiles.find(f => f.filename !== '.DS_Store')?.path;
            const photoFilePaths = photoFiles
                .filter(f => f.filename !== '.DS_Store')
                .map(f => f.path);
            
            if (!audioFile) {
                showNotification('未找到有效的音频文件', 'error');
                hideLoading();
                return;
            }
            
            if (photoFilePaths.length === 0) {
                showNotification('未找到有效的照片文件', 'error');
                hideLoading();
                return;
            }
            
            const data = await this.api.post('/project/create', {
                title: projectName,
                audio_file: audioFile,
                photo_files: photoFilePaths,
                session_id: sessionId
            });
            
            showNotification('项目创建成功', 'success');
            
            // 清空输入框
            if (projectTitleInput) {
                projectTitleInput.value = '';
            }
            
            await this.loadProjects();
            
            // 切换到项目视图
            this.showView('projects');
            
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
            // 获取session_id（从cookie或其他地方）
            const sessionId = this.state.get('session.sessionId');
            const params = sessionId ? `?session_id=${sessionId}` : '';
            
            const data = await this.api.get(`/project/list${params}`);
            
            // 更新状态
            this.state.set('projects', data.projects || []);
            
            const projectsList = document.getElementById('projects-list');
            const projectsEmpty = document.getElementById('projects-empty');
            
            if (!projectsList) return;
            
            // 如果有项目，显示列表
            if (data.projects && data.projects.length > 0) {
                console.log('显示项目列表:', data.projects);
                projectsList.innerHTML = (data.projects || []).map(project => `
                    <div class="project-card" data-project-id="${project.project_id}">
                        <div class="project-thumbnail">
                            <i class="fas fa-folder"></i>
                        </div>
                        <div class="project-info">
                            <h3>${project.title}</h3>
                            <p>${project.duration ? formatTime(project.duration) : '无音频'}</p>
                            <p>${project.photo_count || 0} 张照片</p>
                            <small>${new Date(project.created_at).toLocaleString()}</small>
                        </div>
                        <div class="project-actions">
                            <button class="btn btn-primary" onclick="window.app.openProject('${project.project_id}')">
                                <i class="fas fa-play"></i> 打开
                            </button>
                            <button class="btn btn-secondary" onclick="window.app.editProject('${project.project_id}')">
                                <i class="fas fa-edit"></i> 编辑
                            </button>
                            <button class="btn btn-danger" onclick="window.app.deleteProject('${project.project_id}')">
                                <i class="fas fa-trash"></i> 删除
                            </button>
                        </div>
                    </div>
                `).join('');
                projectsList.style.display = '';
                if (projectsEmpty) projectsEmpty.style.display = 'none';
            } else {
                // 没有项目，显示空状态
                projectsList.innerHTML = '';
                projectsList.style.display = 'none';
                if (projectsEmpty) projectsEmpty.style.display = '';
            }
            
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
            const sessionId = this.state.get('session.sessionId');
            const params = sessionId ? `?session_id=${sessionId}` : '';
            const project = await this.api.get(`/project/load/${projectId}${params}`);
            
            console.log('加载的项目数据:', project);
            
            // 验证数据
            if (!project.audio_path) {
                throw new Error('项目缺少音频路径');
            }
            
            if (!project.timeline || project.timeline.length === 0) {
                throw new Error('项目缺少时间轴数据');
            }
            
            // 更新状态
            this.state.update('session', {
                projectId: project.project_id,
                projectName: project.title
            });
            
            // 准备数据
            const audioUrl = project.audio_path;
            const photoUrls = project.timeline.map(item => item.photo);
            const photoTimestamps = project.timeline.map(item => item.offset);
            
            console.log('播放器数据:', {
                audioUrl,
                photoUrls,
                photoTimestamps,
                photoCount: photoUrls.length,
                timestampCount: photoTimestamps.length
            });
            
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
                const sessionId = this.state.get('session.sessionId');
                const params = sessionId ? `?session_id=${sessionId}` : '';
                await this.api.delete(`/project/delete/${projectId}${params}`);
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
        console.log('播放按钮元素:', playBtn);
        console.log('播放按钮disabled状态:', playBtn?.disabled);
        
        if (playBtn) {
            playBtn.addEventListener('click', (e) => {
                e.preventDefault();
                console.log('播放按钮被点击！');
                console.log('播放器对象:', this.player);
                console.log('播放器状态:', this.player?.state);
                console.log('按钮disabled状态:', playBtn.disabled);
                
                if (!this.player) {
                    console.error('播放器未初始化');
                    return;
                }
                
                if (this.player.state.isPlaying) {
                    console.log('执行暂停');
                    this.player.pause();
                } else {
                    console.log('执行播放');
                    this.player.play().catch(error => {
                        console.error('播放失败:', error);
                    });
                }
            });
        } else {
            console.error('未找到播放按钮元素！');
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
        const volumeBtn = document.getElementById('volume-btn');
        let previousVolume = 1.0; // 存储静音前的音量
        
        if (volumeSlider) {
            volumeSlider.addEventListener('input', (e) => {
                const volume = e.target.value / 100;
                this.player.setVolume(volume);
                
                // 更新音量按钮图标
                if (volumeBtn) {
                    const icon = volumeBtn.querySelector('.control-icon');
                    if (icon) {
                        if (volume === 0) {
                            icon.textContent = '🔇';
                        } else if (volume < 0.5) {
                            icon.textContent = '🔉';
                        } else {
                            icon.textContent = '🔊';
                        }
                    }
                }
            });
        }
        
        // 音量按钮点击切换静音
        if (volumeBtn) {
            volumeBtn.addEventListener('click', () => {
                const currentVolume = this.player.state.volume;
                
                if (currentVolume > 0) {
                    // 当前有音量，静音
                    previousVolume = currentVolume;
                    this.player.setVolume(0);
                    if (volumeSlider) volumeSlider.value = 0;
                    
                    const icon = volumeBtn.querySelector('.control-icon');
                    if (icon) icon.textContent = '🔇';
                } else {
                    // 当前静音，恢复音量
                    const volumeToRestore = previousVolume > 0 ? previousVolume : 1.0;
                    this.player.setVolume(volumeToRestore);
                    if (volumeSlider) volumeSlider.value = volumeToRestore * 100;
                    
                    const icon = volumeBtn.querySelector('.control-icon');
                    if (icon) {
                        if (volumeToRestore < 0.5) {
                            icon.textContent = '🔉';
                        } else {
                            icon.textContent = '🔊';
                        }
                    }
                }
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
        
        // 如果切换到导出视图，更新项目列表并检查导出状态
        if (viewName === 'export') {
            this.updateExportProjectList();
            this.loadExportHistory();
            this.checkOngoingExport();
        }
    }
    
    /**
     * 更新导出视图的项目列表
     */
    async updateExportProjectList() {
        const projectSelect = document.getElementById('export-project-select');
        if (!projectSelect) return;
        
        const projects = this.state.get('projects') || [];
        
        // 清空现有选项（保留默认选项）
        projectSelect.innerHTML = '<option value="">-- 请选择项目 --</option>';
        
        // 添加项目选项
        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.project_id;
            option.textContent = `${project.title} (${project.photo_count || 0}张照片)`;
            projectSelect.appendChild(option);
        });
        
        // 不要在这里调用 resetExportView()，因为可能有正在进行的导出
        // resetExportView() 只应该在用户明确要重置时调用
    }

    /**
     * 恢复用户偏好设置
     */
    restorePreferences() {
        const prefs = this.state.get('preferences') || {};
        
        // 检查播放器是否正确初始化
        if (!this.player || !this.player.setVolume) {
            console.warn('播放器未正确初始化，跳过恢复播放器偏好设置');
            // 仅应用非播放器相关的偏好设置
            if (prefs.theme) {
                document.body.setAttribute('data-theme', prefs.theme);
            }
            return;
        }
        
        // 恢复音量
        if (prefs.volume !== undefined) {
            try {
                this.player.setVolume(prefs.volume);
            } catch (error) {
                console.error('恢复音量设置失败:', error);
            }
        }
        
        // 恢复播放速率
        if (prefs.playbackRate !== undefined) {
            try {
                this.player.setPlaybackRate(prefs.playbackRate);
            } catch (error) {
                console.error('恢复播放速率失败:', error);
            }
        }
        
        // 应用其他偏好设置
        this.applyPreferences(prefs);
    }

    /**
     * 应用偏好设置
     */
    applyPreferences(prefs) {
        if (!prefs) return;
        
        // 主题
        if (prefs.theme) {
            document.body.setAttribute('data-theme', prefs.theme);
        }
        
        // 过渡效果 - 检查播放器和方法是否存在
        if (this.player && typeof this.player.setOptions === 'function' && prefs.transitionType) {
            try {
                this.player.setOptions({
                    transitionType: prefs.transitionType,
                    transitionDuration: prefs.transitionDuration || 300
                });
            } catch (error) {
                console.error('应用过渡效果设置失败:', error);
            }
        }
    }

    /**
     * 初始化视频导出
     */
    initExport() {
        // 项目选择
        const exportProjectSelect = document.getElementById('export-project-select');
        if (exportProjectSelect) {
            exportProjectSelect.addEventListener('change', (e) => {
                const projectId = e.target.value;
                const exportSettings = document.getElementById('export-settings');
                if (projectId && exportSettings) {
                    exportSettings.style.display = 'block';
                } else if (exportSettings) {
                    exportSettings.style.display = 'none';
                }
            });
        }
        
        // 开始导出按钮
        const startExportBtn = document.getElementById('start-export-btn');
        if (startExportBtn) {
            startExportBtn.addEventListener('click', () => {
                this.startExport();
            });
        }
        
        // 下载按钮
        const downloadBtn = document.getElementById('download-export-btn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => {
                this.downloadExport();
            });
        }
        
        // 导出其他项目按钮
        const exportAnotherBtn = document.getElementById('export-another-btn');
        if (exportAnotherBtn) {
            exportAnotherBtn.addEventListener('click', () => {
                this.resetExportView();
            });
        }
        
        // 重试按钮
        const retryBtn = document.getElementById('retry-export-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                this.startExport();
            });
        }
    }
    
    /**
     * 开始导出
     */
    async startExport() {
        const projectSelect = document.getElementById('export-project-select');
        const projectId = projectSelect?.value;
        
        if (!projectId) {
            showNotification('请选择要导出的项目', 'warning');
            return;
        }
        
        // 获取导出设置
        const resolution = document.getElementById('export-resolution')?.value || '1920x1080';
        const fps = parseInt(document.getElementById('export-fps')?.value || '30');
        const format = document.getElementById('export-format')?.value || 'mp4';
        
        // 隐藏设置，显示进度
        document.getElementById('export-settings').style.display = 'none';
        document.getElementById('export-progress').style.display = 'block';
        document.getElementById('export-complete').style.display = 'none';
        document.getElementById('export-error').style.display = 'none';
        
        try {
            const sessionId = this.state.get('session.sessionId');
            
            // 开始导出
            const data = await this.api.post('/export/start', {
                project_id: projectId,
                session_id: sessionId,
                output_format: format,
                resolution: resolution,
                fps: fps
            });
            
            if (!data.success) {
                throw new Error(data.error || '导出失败');
            }
            
            const exportId = data.export_id;
            this.state.set('export.currentExportId', exportId);
            
            // 刷新导出历史列表（显示新创建的导出任务）
            this.loadExportHistory();
            
            // 开始轮询导出状态
            this.pollExportStatus(exportId);
            
        } catch (error) {
            console.error('开始导出失败:', error);
            this.showExportError(error.message);
        }
    }
    
    /**
     * 轮询导出状态
     */
    async pollExportStatus(exportId) {
        const pollInterval = 2000; // 2秒轮询一次
        
        const poll = async () => {
            try {
                const sessionId = this.state.get('session.sessionId');
                const params = sessionId ? `?session_id=${sessionId}` : '';
                const data = await this.api.get(`/export/status/${exportId}${params}`);
                
                if (!data.success) {
                    throw new Error(data.error || '获取导出状态失败');
                }
                
                const { status, progress, error } = data;
                
                // 更新进度显示
                this.updateExportProgress(progress, status);
                
                // 同步更新导出历史中的进度
                this.updateHistoryProgress(exportId, progress);
                
                if (status === 'completed') {
                    // 导出完成
                    this.showExportComplete();
                } else if (status === 'failed') {
                    // 导出失败
                    this.showExportError(error || '导出过程中发生错误');
                } else {
                    // 继续轮询
                    setTimeout(poll, pollInterval);
                }
                
            } catch (error) {
                console.error('轮询导出状态失败:', error);
                this.showExportError(error.message);
            }
        };
        
        poll();
    }
    
    /**
     * 更新导出历史中某个项目的进度
     */
    updateHistoryProgress(exportId, progress) {
        const historyItem = document.querySelector(`[data-export-id="${exportId}"]`);
        if (historyItem) {
            const progressElement = historyItem.querySelector('.history-progress');
            if (progressElement) {
                progressElement.textContent = `${progress}%`;
                progressElement.setAttribute('data-progress', progress);
            }
        }
    }
    
    /**
     * 更新导出进度
     */
    updateExportProgress(progress, status) {
        const progressFill = document.getElementById('export-progress-fill');
        const progressText = document.getElementById('export-progress-text');
        const exportStatus = document.getElementById('export-status');
        
        if (progressFill) {
            progressFill.style.width = `${progress}%`;
        }
        
        if (progressText) {
            progressText.textContent = `正在导出... ${progress}%`;
        }
        
        if (exportStatus) {
            const statusTexts = {
                'pending': '准备中...',
                'processing': '正在处理视频...',
                'completed': '导出完成',
                'failed': '导出失败'
            };
            exportStatus.textContent = statusTexts[status] || status;
        }
    }
    
    /**
     * 显示导出完成
     */
    showExportComplete() {
        document.getElementById('export-progress').style.display = 'none';
        document.getElementById('export-complete').style.display = 'block';
        showNotification('视频导出完成！', 'success');
        
        // 刷新导出历史列表
        this.loadExportHistory();
    }
    
    /**
     * 显示导出错误
     */
    showExportError(message) {
        document.getElementById('export-progress').style.display = 'none';
        document.getElementById('export-settings').style.display = 'none';
        document.getElementById('export-error').style.display = 'block';
        
        const errorMessage = document.getElementById('export-error-message');
        if (errorMessage) {
            errorMessage.textContent = `错误: ${message}`;
        }
        
        showNotification(`导出失败: ${message}`, 'error');
    }
    
    /**
     * 下载导出的视频
     */
    async downloadExport() {
        try {
            const exportId = this.state.get('export.currentExportId');
            if (!exportId) {
                throw new Error('未找到导出ID');
            }
            
            const sessionId = this.state.get('session.sessionId');
            const params = sessionId ? `?session_id=${sessionId}` : '';
            
            // 创建下载链接
            const downloadUrl = `/api/export/download/${exportId}${params}`;
            
            // 创建隐藏的 <a> 标签触发下载
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = '';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showNotification('开始下载视频...', 'success');
            
        } catch (error) {
            console.error('下载导出失败:', error);
            showNotification(`下载失败: ${error.message}`, 'error');
        }
    }
    
    /**
     * 加载导出历史
     */
    async loadExportHistory() {
        try {
            const sessionId = this.state.get('session.sessionId');
            const params = sessionId ? `?session_id=${sessionId}` : '';
            const data = await this.api.get(`/export/list${params}`);
            
            const historyList = document.getElementById('export-history-list');
            if (!historyList) return;
            
            if (!data.success || !data.exports || data.exports.length === 0) {
                historyList.innerHTML = '<p class="empty-hint">暂无导出历史</p>';
                return;
            }
            
            // 找出最新完成的项目（completed_at最大的已完成项目）
            const completedExports = data.exports.filter(exp => exp.status === 'completed' && exp.completed_at);
            const latestCompleted = completedExports.length > 0 ? completedExports[0] : null;
            
            // 显示导出历史列表
            historyList.innerHTML = data.exports.map(exp => {
                const statusEmoji = {
                    'pending': '⏳',
                    'processing': '⚙️',
                    'completed': '✅',
                    'failed': '❌'
                };
                
                const statusText = {
                    'pending': '等待中',
                    'processing': '处理中',
                    'completed': '已完成',
                    'failed': '失败'
                };
                
                const projectTitle = exp.project_title || '未知项目';
                const resolution = exp.resolution || '未知';
                const fps = exp.fps || '未知';
                const format = exp.format ? exp.format.toUpperCase() : '未知';
                
                // 判断是否为最新完成的项目
                const isLatest = latestCompleted && exp.export_id === latestCompleted.export_id;
                const latestMarker = isLatest ? ' ⭐' : '';
                
                // 格式化完成时间
                let completedTime = '';
                if (exp.completed_at) {
                    completedTime = `<div class="history-time">完成时间: ${exp.completed_at}</div>`;
                }
                
                return `
                    <div class="export-history-item${isLatest ? ' latest-export' : ''}" data-export-id="${exp.export_id}">
                        <div class="history-main">
                            <span class="history-status">${statusEmoji[exp.status] || '❓'}${latestMarker}</span>
                            <div class="history-details">
                                <div class="history-project-name">${projectTitle}</div>
                                <div class="history-config">
                                    ${resolution} | ${fps}FPS | ${format}
                                </div>
                                ${completedTime}
                            </div>
                        </div>
                        <div class="history-actions">
                            <span class="history-progress" data-progress="${exp.progress}">${exp.progress}%</span>
                            ${exp.status === 'completed' ? 
                                `<button class="btn btn-small btn-primary" onclick="app.downloadExportById('${exp.export_id}')">下载</button>` : 
                                ''}
                            <button class="btn btn-small btn-danger" onclick="app.deleteExportById('${exp.export_id}')" title="删除">🗑️</button>
                        </div>
                        ${exp.error ? `<div class="history-error">错误: ${exp.error}</div>` : ''}
                    </div>
                `;
            }).join('');
            
        } catch (error) {
            console.error('加载导出历史失败:', error);
        }
    }
    
    /**
     * 根据ID下载导出
     */
    async downloadExportById(exportId) {
        try {
            const sessionId = this.state.get('session.sessionId');
            const params = sessionId ? `?session_id=${sessionId}` : '';
            
            const downloadUrl = `/api/export/download/${exportId}${params}`;
            
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = '';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showNotification('开始下载视频...', 'success');
        } catch (error) {
            console.error('下载失败:', error);
            showNotification(`下载失败: ${error.message}`, 'error');
        }
    }
    
    /**
     * 根据ID删除导出
     */
    async deleteExportById(exportId) {
        confirm('确认删除该导出记录？', async () => {
            try {
                const sessionId = this.state.get('session.sessionId');
                const params = sessionId ? `?session_id=${sessionId}` : '';
                
                await this.api.delete(`/export/delete/${exportId}${params}`);
                
                showNotification('导出记录已删除', 'success');
                
                // 刷新导出历史列表
                await this.loadExportHistory();
                
            } catch (error) {
                console.error('删除导出失败:', error);
                showNotification(`删除失败: ${error.message}`, 'error');
            }
        });
    }
    
    /**
     * 检查是否有正在进行的导出任务
     */
    async checkOngoingExport() {
        const exportId = this.state.get('export.currentExportId');
        if (!exportId) {
            return; // 没有正在进行的导出
        }
        
        try {
            const sessionId = this.state.get('session.sessionId');
            const params = sessionId ? `?session_id=${sessionId}` : '';
            const data = await this.api.get(`/export/status/${exportId}${params}`);
            
            if (!data.success) {
                // 导出任务不存在或已失败，清除状态
                this.state.set('export.currentExportId', null);
                return;
            }
            
            const { status, progress } = data;
            
            if (status === 'pending' || status === 'processing') {
                // 有正在进行的导出，恢复显示进度
                console.log('检测到正在进行的导出任务，恢复显示进度');
                document.getElementById('export-settings').style.display = 'none';
                document.getElementById('export-progress').style.display = 'block';
                document.getElementById('export-complete').style.display = 'none';
                document.getElementById('export-error').style.display = 'none';
                
                // 更新进度显示
                this.updateExportProgress(progress, status);
                
                // 继续轮询状态
                this.pollExportStatus(exportId);
                
            } else if (status === 'completed') {
                // 导出已完成
                this.showExportComplete();
                
            } else if (status === 'failed') {
                // 导出失败
                this.showExportError(data.error || '导出失败');
            }
            
        } catch (error) {
            console.error('检查导出状态失败:', error);
            // 清除状态
            this.state.set('export.currentExportId', null);
        }
    }
    
    /**
     * 重置导出视图
     */
    resetExportView() {
        // 清除导出ID
        this.state.set('export.currentExportId', null);
        
        document.getElementById('export-settings').style.display = 'none';
        document.getElementById('export-progress').style.display = 'none';
        document.getElementById('export-complete').style.display = 'none';
        document.getElementById('export-error').style.display = 'none';
        
        const projectSelect = document.getElementById('export-project-select');
        if (projectSelect) {
            projectSelect.value = '';
        }
        
        // 重置进度
        const progressFill = document.getElementById('export-progress-fill');
        if (progressFill) {
            progressFill.style.width = '0%';
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

// 全局函数，供HTML内联事件使用
window.switchView = function(viewName) {
    if (window.app) {
        window.app.showView(viewName);
    }
};

window.deleteFile = function(path, type) {
    if (window.app) {
        window.app.deleteFile(path, type);
    }
};

window.openProject = function(projectId) {
    if (window.app) {
        window.app.openProject(projectId);
    }
};

window.editProject = function(projectId) {
    if (window.app) {
        window.app.editProject(projectId);
    }
};

window.deleteProject = function(projectId) {
    if (window.app) {
        window.app.deleteProject(projectId);
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});

export default App;
