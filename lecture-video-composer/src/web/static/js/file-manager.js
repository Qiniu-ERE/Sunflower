/**
 * FileManager 文件管理器
 * 
 * 功能：
 * - 文件拖拽上传
 * - 文件类型验证
 * - 上传进度显示
 * - 文件预览
 * - 批量上传管理
 */

import { showNotification, showLoading, hideLoading } from './utils.js';

export class FileManager {
    /**
     * 构造函数
     * @param {Object} options - 配置选项
     */
    constructor(options = {}) {
        this.options = {
            maxFileSize: 100 * 1024 * 1024, // 100MB
            allowedAudioTypes: ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/x-m4a'],
            allowedImageTypes: ['image/jpeg', 'image/jpg', 'image/png'],
            concurrentUploads: 3,
            chunkSize: 1024 * 1024, // 1MB chunks for large files
            ...options
        };
        
        // 上传队列
        this.uploadQueue = [];
        this.activeUploads = 0;
        this.uploadCallbacks = {};
        
        // 事件监听器
        this.listeners = {
            uploadStart: [],
            uploadProgress: [],
            uploadComplete: [],
            uploadError: [],
            queueComplete: []
        };
    }

    /**
     * 初始化拖拽区域
     * @param {HTMLElement} dropzone - 拖拽区域元素
     * @param {HTMLInputElement} fileInput - 文件输入元素
     * @param {string} fileType - 文件类型 ('audio' 或 'image')
     */
    initDropzone(dropzone, fileInput, fileType) {
        if (!dropzone || !fileInput) {
            throw new Error('Dropzone and fileInput elements are required');
        }
        
        // 点击上传
        dropzone.addEventListener('click', (e) => {
            if (e.target === dropzone || e.target.closest('.dropzone-content')) {
                fileInput.click();
            }
        });
        
        // 文件选择
        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            this.handleFiles(files, fileType);
            fileInput.value = ''; // 清空以允许重复选择同一文件
        });
        
        // 拖拽事件
        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
        
        dropzone.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
        
        dropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // 只在真正离开时移除样式（不是离开子元素）
            if (e.target === dropzone) {
                dropzone.classList.remove('dragover');
            }
        });
        
        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
            
            const files = Array.from(e.dataTransfer.files);
            this.handleFiles(files, fileType);
        });
        
        // 粘贴上传
        document.addEventListener('paste', (e) => {
            if (dropzone.classList.contains('active')) {
                const items = e.clipboardData?.items;
                if (items) {
                    const files = [];
                    for (let i = 0; i < items.length; i++) {
                        if (items[i].kind === 'file') {
                            files.push(items[i].getAsFile());
                        }
                    }
                    if (files.length > 0) {
                        e.preventDefault();
                        this.handleFiles(files, fileType);
                    }
                }
            }
        });
    }

    /**
     * 处理文件
     * @param {File[]} files - 文件数组
     * @param {string} fileType - 文件类型
     */
    async handleFiles(files, fileType) {
        if (files.length === 0) return;
        
        // 验证文件
        const validFiles = [];
        const errors = [];
        
        for (const file of files) {
            const validation = this.validateFile(file, fileType);
            if (validation.valid) {
                validFiles.push(file);
            } else {
                errors.push({ file: file.name, error: validation.error });
            }
        }
        
        // 显示错误
        if (errors.length > 0) {
            errors.forEach(({ file, error }) => {
                showNotification(`${file}: ${error}`, 'error');
            });
        }
        
        // 添加到上传队列
        if (validFiles.length > 0) {
            for (const file of validFiles) {
                this.addToQueue(file, fileType);
            }
            this.processQueue();
        }
    }

    /**
     * 验证文件
     * @param {File} file - 文件对象
     * @param {string} fileType - 文件类型
     * @returns {Object} 验证结果
     */
    validateFile(file, fileType) {
        // 检查文件大小
        if (file.size > this.options.maxFileSize) {
            return {
                valid: false,
                error: `文件大小超过限制 (${(this.options.maxFileSize / 1024 / 1024).toFixed(0)}MB)`
            };
        }
        
        // 检查文件类型
        const allowedTypes = fileType === 'audio' 
            ? this.options.allowedAudioTypes 
            : this.options.allowedImageTypes;
        
        if (!allowedTypes.includes(file.type)) {
            return {
                valid: false,
                error: `不支持的文件类型: ${file.type}`
            };
        }
        
        // 文件名验证已移除 - 后端会自动根据文件创建时间重命名
        // 用户可以上传任意文件名的文件
        
        return { valid: true };
    }

    /**
     * 添加到上传队列
     * @param {File} file - 文件对象
     * @param {string} fileType - 文件类型
     */
    addToQueue(file, fileType) {
        const uploadId = `upload_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        this.uploadQueue.push({
            id: uploadId,
            file,
            fileType,
            status: 'pending',
            progress: 0,
            error: null
        });
        
        this.emit('uploadStart', { id: uploadId, file, fileType });
    }

    /**
     * 处理上传队列
     */
    async processQueue() {
        while (this.uploadQueue.length > 0 && this.activeUploads < this.options.concurrentUploads) {
            const uploadTask = this.uploadQueue.shift();
            if (uploadTask.status === 'pending') {
                this.activeUploads++;
                this.uploadFile(uploadTask).finally(() => {
                    this.activeUploads--;
                    this.processQueue();
                });
            }
        }
        
        // 队列完成
        if (this.uploadQueue.length === 0 && this.activeUploads === 0) {
            this.emit('queueComplete', {});
        }
    }

    /**
     * 上传文件
     * @param {Object} uploadTask - 上传任务
     */
    async uploadFile(uploadTask) {
        const { id, file, fileType } = uploadTask;
        
        try {
            uploadTask.status = 'uploading';
            
            const formData = new FormData();
            
            // 音频使用 'file' 字段，照片使用 'files' 字段
            if (fileType === 'audio') {
                formData.append('file', file);
            } else {
                formData.append('files', file);
            }
            
            // 添加 session_id（从应用状态获取）
            if (window.app && window.app.state) {
                const sessionId = window.app.state.get('session.sessionId');
                if (sessionId) {
                    formData.append('session_id', sessionId);
                }
            }
            
            // 确定上传端点
            const endpoint = fileType === 'audio' 
                ? '/api/file/upload/audio'
                : '/api/file/upload/photos';
            
            // 使用 XMLHttpRequest 以支持进度追踪
            const xhr = new XMLHttpRequest();
            
            // 进度事件
            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const progress = (e.loaded / e.total) * 100;
                    uploadTask.progress = progress;
                    this.emit('uploadProgress', { id, file, progress });
                }
            });
            
            // 完成事件
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    uploadTask.status = 'completed';
                    uploadTask.progress = 100;
                    
                    let response;
                    try {
                        response = JSON.parse(xhr.responseText);
                    } catch (e) {
                        response = { success: true };
                    }
                    
                    this.emit('uploadComplete', { id, file, response });
                } else {
                    throw new Error(`上传失败: ${xhr.status} ${xhr.statusText}`);
                }
            });
            
            // 错误事件
            xhr.addEventListener('error', () => {
                throw new Error('网络错误');
            });
            
            // 超时事件
            xhr.addEventListener('timeout', () => {
                throw new Error('上传超时');
            });
            
            // 发送请求
            xhr.open('POST', endpoint);
            xhr.timeout = 300000; // 5分钟超时
            xhr.send(formData);
            
            // 等待完成
            await new Promise((resolve, reject) => {
                xhr.addEventListener('load', () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        resolve();
                    } else {
                        reject(new Error(`HTTP ${xhr.status}`));
                    }
                });
                xhr.addEventListener('error', reject);
                xhr.addEventListener('timeout', reject);
            });
            
        } catch (error) {
            uploadTask.status = 'failed';
            uploadTask.error = error.message;
            this.emit('uploadError', { id, file, error: error.message });
            throw error;
        }
    }

    /**
     * 取消上传
     * @param {string} uploadId - 上传ID
     */
    cancelUpload(uploadId) {
        const index = this.uploadQueue.findIndex(task => task.id === uploadId);
        if (index > -1) {
            this.uploadQueue.splice(index, 1);
            this.emit('uploadError', { 
                id: uploadId, 
                error: '用户取消' 
            });
        }
    }

    /**
     * 获取队列状态
     */
    getQueueStatus() {
        return {
            pending: this.uploadQueue.filter(t => t.status === 'pending').length,
            uploading: this.uploadQueue.filter(t => t.status === 'uploading').length,
            completed: this.uploadQueue.filter(t => t.status === 'completed').length,
            failed: this.uploadQueue.filter(t => t.status === 'failed').length
        };
    }

    /**
     * 添加事件监听
     */
    on(event, callback) {
        if (this.listeners[event]) {
            this.listeners[event].push(callback);
        }
    }

    /**
     * 移除事件监听
     */
    off(event, callback) {
        if (this.listeners[event]) {
            const index = this.listeners[event].indexOf(callback);
            if (index > -1) {
                this.listeners[event].splice(index, 1);
            }
        }
    }

    /**
     * 触发事件
     */
    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`Error in file manager ${event} listener:`, error);
                }
            });
        }
    }

    /**
     * 清理资源
     */
    destroy() {
        this.uploadQueue = [];
        this.listeners = {
            uploadStart: [],
            uploadProgress: [],
            uploadComplete: [],
            uploadError: [],
            queueComplete: []
        };
    }
}

export default FileManager;
