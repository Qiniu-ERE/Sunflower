/**
 * Timeline 时间轴可视化组件
 * 
 * 功能：
 * - 可视化展示照片在时间轴上的分布
 * - 支持拖拽进度条跳转
 * - 显示当前播放位置
 * - 照片标记点交互
 */

import { formatTime, throttle } from './utils.js';

export class Timeline {
    /**
     * 构造函数
     * @param {string|HTMLElement} container - 容器元素或选择器
     * @param {Object} options - 配置选项
     */
    constructor(container, options = {}) {
        this.container = typeof container === 'string' 
            ? document.querySelector(container) 
            : container;
        
        if (!this.container) {
            throw new Error('Timeline container not found');
        }
        
        // 配置选项
        this.options = {
            height: 60,
            markerSize: 12,
            markerColor: '#4CAF50',
            progressColor: '#2196F3',
            backgroundColor: '#e0e0e0',
            hoverColor: '#FFC107',
            showThumbnails: false,
            thumbnailSize: 100,
            ...options
        };
        
        // 状态
        this.duration = 0;
        this.currentTime = 0;
        this.photos = [];
        this.isDragging = false;
        this.hoverMarkerIndex = -1;
        
        // 事件监听器
        this.listeners = {
            seek: [],
            markerClick: [],
            markerHover: []
        };
        
        // 初始化
        this.init();
    }

    /**
     * 初始化时间轴
     */
    init() {
        this.container.classList.add('timeline-component');
        this.container.innerHTML = `
            <div class="timeline-track">
                <div class="timeline-background"></div>
                <div class="timeline-progress"></div>
                <div class="timeline-markers"></div>
                <div class="timeline-cursor"></div>
            </div>
            <div class="timeline-labels">
                <span class="timeline-label-start">00:00</span>
                <span class="timeline-label-end">00:00</span>
            </div>
            <div class="timeline-tooltip" style="display: none;">
                <div class="timeline-tooltip-time"></div>
                <div class="timeline-tooltip-photo"></div>
            </div>
        `;
        
        // 获取元素引用
        this.track = this.container.querySelector('.timeline-track');
        this.background = this.container.querySelector('.timeline-background');
        this.progress = this.container.querySelector('.timeline-progress');
        this.markersContainer = this.container.querySelector('.timeline-markers');
        this.cursor = this.container.querySelector('.timeline-cursor');
        this.tooltip = this.container.querySelector('.timeline-tooltip');
        this.tooltipTime = this.container.querySelector('.timeline-tooltip-time');
        this.tooltipPhoto = this.container.querySelector('.timeline-tooltip-photo');
        this.labelStart = this.container.querySelector('.timeline-label-start');
        this.labelEnd = this.container.querySelector('.timeline-label-end');
        
        // 设置样式
        this.applyStyles();
        
        // 绑定事件
        this.bindEvents();
    }

    /**
     * 应用样式
     */
    applyStyles() {
        this.track.style.height = `${this.options.height}px`;
        this.background.style.backgroundColor = this.options.backgroundColor;
        this.progress.style.backgroundColor = this.options.progressColor;
        this.cursor.style.backgroundColor = this.options.progressColor;
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 点击跳转
        this.track.addEventListener('click', (e) => {
            if (!this.isDragging) {
                this.handleSeek(e);
            }
        });
        
        // 拖拽进度
        this.track.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.handleSeek(e);
            
            const onMouseMove = throttle((e) => {
                if (this.isDragging) {
                    this.handleSeek(e);
                }
            }, 16); // ~60fps
            
            const onMouseUp = () => {
                this.isDragging = false;
                document.removeEventListener('mousemove', onMouseMove);
                document.removeEventListener('mouseup', onMouseUp);
            };
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
        });
        
        // 悬停提示
        this.track.addEventListener('mousemove', throttle((e) => {
            this.handleHover(e);
        }, 50));
        
        this.track.addEventListener('mouseleave', () => {
            this.hideTooltip();
            this.hoverMarkerIndex = -1;
            this.updateMarkers();
        });
    }

    /**
     * 处理跳转
     */
    handleSeek(e) {
        const rect = this.track.getBoundingClientRect();
        const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        const time = percent * this.duration;
        
        this.emit('seek', { time, percent });
    }

    /**
     * 处理悬停
     */
    handleHover(e) {
        const rect = this.track.getBoundingClientRect();
        const percent = (e.clientX - rect.left) / rect.width;
        const time = percent * this.duration;
        
        // 显示时间提示
        this.showTooltip(e.clientX, time);
        
        // 检查是否悬停在标记点上
        const markerIndex = this.findMarkerAtPosition(percent);
        if (markerIndex !== this.hoverMarkerIndex) {
            this.hoverMarkerIndex = markerIndex;
            this.updateMarkers();
            
            if (markerIndex >= 0) {
                this.emit('markerHover', { 
                    index: markerIndex, 
                    photo: this.photos[markerIndex] 
                });
            }
        }
    }

    /**
     * 查找位置处的标记点
     */
    findMarkerAtPosition(percent) {
        const threshold = 0.01; // 1% 容差
        
        for (let i = 0; i < this.photos.length; i++) {
            const photo = this.photos[i];
            const markerPercent = photo.timestamp / this.duration;
            
            if (Math.abs(markerPercent - percent) < threshold) {
                return i;
            }
        }
        
        return -1;
    }

    /**
     * 显示提示框
     */
    showTooltip(x, time) {
        this.tooltipTime.textContent = formatTime(time);
        
        // 如果悬停在标记点上，显示照片信息
        if (this.hoverMarkerIndex >= 0) {
            const photo = this.photos[this.hoverMarkerIndex];
            this.tooltipPhoto.textContent = `照片 ${this.hoverMarkerIndex + 1}`;
            this.tooltipPhoto.style.display = 'block';
        } else {
            this.tooltipPhoto.style.display = 'none';
        }
        
        this.tooltip.style.display = 'block';
        this.tooltip.style.left = `${x}px`;
    }

    /**
     * 隐藏提示框
     */
    hideTooltip() {
        this.tooltip.style.display = 'none';
    }

    /**
     * 加载时间轴数据
     * @param {Array} photos - 照片数组，每项包含 {timestamp, url, ...}
     * @param {number} duration - 总时长（秒）
     */
    loadData(photos, duration) {
        this.photos = photos.sort((a, b) => a.timestamp - b.timestamp);
        this.duration = duration;
        this.currentTime = 0;
        
        // 更新标签
        this.labelStart.textContent = formatTime(0);
        this.labelEnd.textContent = formatTime(duration);
        
        // 渲染标记点
        this.updateMarkers();
        
        // 重置进度
        this.updateProgress(0);
    }

    /**
     * 更新标记点
     */
    updateMarkers() {
        this.markersContainer.innerHTML = '';
        
        this.photos.forEach((photo, index) => {
            const marker = document.createElement('div');
            marker.className = 'timeline-marker';
            marker.dataset.index = index;
            
            const percent = (photo.timestamp / this.duration) * 100;
            marker.style.left = `${percent}%`;
            marker.style.backgroundColor = this.options.markerColor;
            marker.style.width = `${this.options.markerSize}px`;
            marker.style.height = `${this.options.markerSize}px`;
            
            // 悬停高亮
            if (index === this.hoverMarkerIndex) {
                marker.style.backgroundColor = this.options.hoverColor;
                marker.style.transform = 'scale(1.3)';
            }
            
            // 点击标记点跳转
            marker.addEventListener('click', (e) => {
                e.stopPropagation();
                this.emit('markerClick', { index, photo });
                this.emit('seek', { time: photo.timestamp, percent: photo.timestamp / this.duration });
            });
            
            this.markersContainer.appendChild(marker);
        });
    }

    /**
     * 更新进度
     * @param {number} currentTime - 当前时间（秒）
     */
    updateProgress(currentTime) {
        this.currentTime = currentTime;
        const percent = Math.max(0, Math.min(100, (currentTime / this.duration) * 100));
        
        this.progress.style.width = `${percent}%`;
        this.cursor.style.left = `${percent}%`;
    }

    /**
     * 获取当前照片索引
     */
    getCurrentPhotoIndex() {
        for (let i = this.photos.length - 1; i >= 0; i--) {
            if (this.photos[i].timestamp <= this.currentTime) {
                return i;
            }
        }
        return -1;
    }

    /**
     * 高亮当前照片标记
     */
    highlightCurrentMarker() {
        const currentIndex = this.getCurrentPhotoIndex();
        
        this.markersContainer.querySelectorAll('.timeline-marker').forEach((marker, index) => {
            if (index === currentIndex) {
                marker.classList.add('active');
            } else {
                marker.classList.remove('active');
            }
        });
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
                    console.error(`Error in timeline ${event} listener:`, error);
                }
            });
        }
    }

    /**
     * 清理资源
     */
    destroy() {
        this.container.innerHTML = '';
        this.listeners = { seek: [], markerClick: [], markerHover: [] };
    }

    /**
     * 设置选项
     */
    setOptions(options) {
        this.options = { ...this.options, ...options };
        this.applyStyles();
        this.updateMarkers();
    }

    /**
     * 获取状态
     */
    getState() {
        return {
            duration: this.duration,
            currentTime: this.currentTime,
            photos: this.photos,
            currentPhotoIndex: this.getCurrentPhotoIndex()
        };
    }
}

export default Timeline;
