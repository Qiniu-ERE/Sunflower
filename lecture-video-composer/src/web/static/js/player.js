/**
 * 演讲视频播放器
 */

import { formatTime, debounce, throttle, drawImageCentered, easing, lerp, EventBus } from './utils.js';

export class LecturePlayer extends EventBus {
    constructor(canvasId, options = {}) {
        super();
        
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            throw new Error(`Canvas element with id "${canvasId}" not found`);
        }
        
        this.ctx = this.canvas.getContext('2d');
        
        // 配置选项
        this.options = {
            transitionDuration: 0.5, // 照片过渡时间（秒）
            transitionType: 'fade',  // 过渡类型：fade, slide, zoom
            autoPlay: false,
            volume: 0.8,
            ...options
        };
        
        // 播放状态
        this.state = {
            isPlaying: false,
            isPaused: false,
            currentTime: 0,
            duration: 0,
            volume: this.options.volume,
            playbackRate: 1.0,
            currentPhotoIndex: 0,
            isTransitioning: false
        };
        
        // 媒体资源
        this.audio = null;
        this.photos = [];
        this.photoTimeline = [];
        
        // 动画相关
        this.animationFrameId = null;
        this.transitionStartTime = null;
        this.previousPhoto = null;
        this.currentPhoto = null;
        
        // 初始化
        this._initCanvas();
    }

    /**
     * 初始化 Canvas
     */
    _initCanvas() {
        // 设置 Canvas 尺寸（16:9 比例）
        const rect = this.canvas.getBoundingClientRect();
        console.log('Canvas getBoundingClientRect:', rect);
        
        // 如果canvas还没有尺寸，使用父容器或默认尺寸
        let width = rect.width;
        let height = rect.height;
        
        if (width === 0 || height === 0) {
            // 尝试从父容器获取尺寸
            const parent = this.canvas.parentElement;
            if (parent) {
                const parentRect = parent.getBoundingClientRect();
                width = parentRect.width || 1280;
                height = parentRect.height || 720;
                console.log('使用父容器尺寸:', parentRect);
            } else {
                // 使用默认尺寸
                width = 1280;
                height = 720;
                console.log('使用默认尺寸');
            }
        }
        
        // 确保是16:9比例
        height = width * 9 / 16;
        
        this.canvas.width = width;
        this.canvas.height = height;
        
        console.log('Canvas最终尺寸:', {
            width: this.canvas.width,
            height: this.canvas.height
        });
        
        // 绘制初始状态
        this._drawPlaceholder();
    }

    /**
     * 绘制占位符
     */
    _drawPlaceholder() {
        this.ctx.fillStyle = '#1a1a2e';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        this.ctx.fillStyle = '#666';
        this.ctx.font = '24px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText('请加载项目', this.canvas.width / 2, this.canvas.height / 2);
    }

    /**
     * 加载项目
     */
    async loadProject(audioUrl, photoUrls, photoTimestamps) {
        try {
            // 加载音频
            await this._loadAudio(audioUrl);
            
            // 加载照片
            await this._loadPhotos(photoUrls, photoTimestamps);
            
            // 构建时间轴
            this._buildTimeline();
            
            // 显示第一张照片
            if (this.photos.length > 0) {
                this.currentPhoto = this.photos[0];
                this._drawPhoto(this.currentPhoto);
            }
            
            this.emit('loaded', {
                duration: this.state.duration,
                photoCount: this.photos.length
            });
            
            // 自动播放
            if (this.options.autoPlay) {
                this.play();
            }
            
        } catch (error) {
            this.emit('error', { message: '加载项目失败', error });
            throw error;
        }
    }

    /**
     * 加载音频
     */
    async _loadAudio(url) {
        return new Promise((resolve, reject) => {
            this.audio = new Audio(url);
            this.audio.volume = this.state.volume;
            this.audio.playbackRate = this.state.playbackRate;
            
            this.audio.addEventListener('loadedmetadata', () => {
                this.state.duration = this.audio.duration;
                resolve();
            });
            
            this.audio.addEventListener('error', (e) => {
                reject(new Error('音频加载失败'));
            });
            
            this.audio.addEventListener('ended', () => {
                this.stop();
                this.emit('ended');
            });
            
            this.audio.addEventListener('timeupdate', () => {
                this._onTimeUpdate();
            });
        });
    }

    /**
     * 加载照片
     */
    async _loadPhotos(urls, timestamps) {
        console.log('开始加载照片:', urls.length, '张');
        
        const promises = urls.map((url, index) => {
            return new Promise((resolve, reject) => {
                const img = new Image();
                // 移除crossOrigin，因为是同源请求
                // img.crossOrigin = 'anonymous';
                
                img.onload = () => {
                    console.log(`照片加载成功 [${index}]:`, url);
                    resolve({
                        image: img,
                        url: url,
                        timestamp: timestamps[index],
                        index: index
                    });
                };
                
                img.onerror = (e) => {
                    console.error(`照片加载失败 [${index}]:`, url, e);
                    reject(new Error(`照片加载失败: ${url}`));
                };
                
                console.log(`开始加载照片 [${index}]:`, url);
                img.src = url;
            });
        });
        
        try {
            this.photos = await Promise.all(promises);
            console.log('所有照片加载完成:', this.photos.length);
            
            // 按时间戳排序
            this.photos.sort((a, b) => a.timestamp - b.timestamp);
        } catch (error) {
            console.error('照片加载过程中出错:', error);
            throw error;
        }
    }

    /**
     * 构建时间轴
     */
    _buildTimeline() {
        this.photoTimeline = this.photos.map(photo => ({
            time: photo.timestamp,
            photo: photo
        }));
    }

    /**
     * 播放
     */
    async play() {
        console.log('尝试播放, audio对象:', this.audio);
        console.log('音频源:', this.audio?.src);
        console.log('音频状态:', {
            readyState: this.audio?.readyState,
            networkState: this.audio?.networkState,
            error: this.audio?.error
        });
        
        if (!this.audio) {
            console.error('未加载音频');
            throw new Error('未加载音频');
        }
        
        try {
            console.log('开始播放音频...');
            await this.audio.play();
            console.log('音频播放成功');
            this.state.isPlaying = true;
            this.state.isPaused = false;
            
            // 确保显示当前照片
            if (this.currentPhoto) {
                console.log('绘制当前照片:', this.currentPhoto.url);
                this._drawPhoto(this.currentPhoto);
            }
            
            this._startAnimation();
            this.emit('play');
        } catch (error) {
            console.error('播放失败:', error);
            this.emit('error', { message: '播放失败: ' + error.message, error });
            throw error;
        }
    }

    /**
     * 暂停
     */
    pause() {
        if (this.audio && this.state.isPlaying) {
            this.audio.pause();
            this.state.isPlaying = false;
            this.state.isPaused = true;
            this._stopAnimation();
            this.emit('pause');
        }
    }

    /**
     * 停止
     */
    stop() {
        if (this.audio) {
            this.audio.pause();
            this.audio.currentTime = 0;
            this.state.isPlaying = false;
            this.state.isPaused = false;
            this.state.currentTime = 0;
            this.state.currentPhotoIndex = 0;
            this._stopAnimation();
            
            // 显示第一张照片
            if (this.photos.length > 0) {
                this.currentPhoto = this.photos[0];
                this._drawPhoto(this.currentPhoto);
            }
            
            this.emit('stop');
        }
    }

    /**
     * 跳转到指定时间
     */
    seek(time) {
        if (!this.audio) return;
        
        time = Math.max(0, Math.min(time, this.state.duration));
        this.audio.currentTime = time;
        this.state.currentTime = time;
        
        // 更新照片
        this._updatePhotoByTime(time);
        
        this.emit('seek', { time });
    }

    /**
     * 设置音量
     */
    setVolume(volume) {
        volume = Math.max(0, Math.min(1, volume));
        this.state.volume = volume;
        
        if (this.audio) {
            this.audio.volume = volume;
        }
        
        this.emit('volumechange', { volume });
    }

    /**
     * 设置播放速率
     */
    setPlaybackRate(rate) {
        rate = Math.max(0.25, Math.min(2, rate));
        this.state.playbackRate = rate;
        
        if (this.audio) {
            this.audio.playbackRate = rate;
        }
        
        this.emit('ratechange', { rate });
    }

    /**
     * 时间更新回调
     */
    _onTimeUpdate() {
        this.state.currentTime = this.audio.currentTime;
        this._updatePhotoByTime(this.state.currentTime);
        this.emit('timeupdate', { 
            currentTime: this.state.currentTime,
            duration: this.state.duration
        });
    }

    /**
     * 根据时间更新照片
     */
    _updatePhotoByTime(time) {
        // 找到当前应该显示的照片
        let targetIndex = 0;
        for (let i = this.photoTimeline.length - 1; i >= 0; i--) {
            if (time >= this.photoTimeline[i].time) {
                targetIndex = i;
                break;
            }
        }
        
        // 如果需要切换照片
        if (targetIndex !== this.state.currentPhotoIndex) {
            this._switchPhoto(targetIndex);
        }
    }

    /**
     * 切换照片
     */
    _switchPhoto(index) {
        if (index < 0 || index >= this.photos.length) return;
        
        this.previousPhoto = this.currentPhoto;
        this.currentPhoto = this.photos[index];
        this.state.currentPhotoIndex = index;
        this.state.isTransitioning = true;
        this.transitionStartTime = performance.now();
        
        this.emit('photochange', { 
            index,
            photo: this.currentPhoto
        });
    }

    /**
     * 开始动画循环
     */
    _startAnimation() {
        const animate = (timestamp) => {
            if (!this.state.isPlaying) return;
            
            this._renderFrame(timestamp);
            this.animationFrameId = requestAnimationFrame(animate);
        };
        
        this.animationFrameId = requestAnimationFrame(animate);
    }

    /**
     * 停止动画循环
     */
    _stopAnimation() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    /**
     * 渲染帧
     */
    _renderFrame(timestamp) {
        if (this.state.isTransitioning) {
            this._renderTransition(timestamp);
        } else if (this.currentPhoto) {
            this._drawPhoto(this.currentPhoto);
        }
    }

    /**
     * 渲染过渡动画
     */
    _renderTransition(timestamp) {
        const elapsed = (timestamp - this.transitionStartTime) / 1000;
        const progress = Math.min(elapsed / this.options.transitionDuration, 1);
        
        if (progress >= 1) {
            // 过渡完成
            this.state.isTransitioning = false;
            this._drawPhoto(this.currentPhoto);
            return;
        }
        
        // 应用缓动函数
        const t = easing.easeInOutQuad(progress);
        
        // 根据过渡类型渲染
        switch (this.options.transitionType) {
            case 'fade':
                this._renderFadeTransition(t);
                break;
            case 'slide':
                this._renderSlideTransition(t);
                break;
            case 'zoom':
                this._renderZoomTransition(t);
                break;
            default:
                this._renderFadeTransition(t);
        }
    }

    /**
     * 淡入淡出过渡
     */
    _renderFadeTransition(t) {
        // 清空画布
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制前一张照片（淡出）
        if (this.previousPhoto) {
            this.ctx.globalAlpha = 1 - t;
            drawImageCentered(this.ctx, this.previousPhoto.image, 
                this.canvas.width, this.canvas.height);
        }
        
        // 绘制当前照片（淡入）
        if (this.currentPhoto) {
            this.ctx.globalAlpha = t;
            drawImageCentered(this.ctx, this.currentPhoto.image, 
                this.canvas.width, this.canvas.height);
        }
        
        // 恢复透明度
        this.ctx.globalAlpha = 1;
    }

    /**
     * 滑动过渡
     */
    _renderSlideTransition(t) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        const offset = lerp(this.canvas.width, 0, t);
        
        this.ctx.save();
        
        // 绘制前一张照片（向左滑出）
        if (this.previousPhoto) {
            this.ctx.translate(-offset, 0);
            drawImageCentered(this.ctx, this.previousPhoto.image, 
                this.canvas.width, this.canvas.height);
        }
        
        this.ctx.restore();
        this.ctx.save();
        
        // 绘制当前照片（从右滑入）
        if (this.currentPhoto) {
            this.ctx.translate(this.canvas.width - offset, 0);
            drawImageCentered(this.ctx, this.currentPhoto.image, 
                this.canvas.width, this.canvas.height);
        }
        
        this.ctx.restore();
    }

    /**
     * 缩放过渡
     */
    _renderZoomTransition(t) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制前一张照片（缩小）
        if (this.previousPhoto) {
            const scale = lerp(1, 0.8, t);
            this.ctx.save();
            this.ctx.globalAlpha = 1 - t;
            this.ctx.translate(this.canvas.width / 2, this.canvas.height / 2);
            this.ctx.scale(scale, scale);
            this.ctx.translate(-this.canvas.width / 2, -this.canvas.height / 2);
            drawImageCentered(this.ctx, this.previousPhoto.image, 
                this.canvas.width, this.canvas.height);
            this.ctx.restore();
        }
        
        // 绘制当前照片（放大）
        if (this.currentPhoto) {
            const scale = lerp(1.2, 1, t);
            this.ctx.save();
            this.ctx.globalAlpha = t;
            this.ctx.translate(this.canvas.width / 2, this.canvas.height / 2);
            this.ctx.scale(scale, scale);
            this.ctx.translate(-this.canvas.width / 2, -this.canvas.height / 2);
            drawImageCentered(this.ctx, this.currentPhoto.image, 
                this.canvas.width, this.canvas.height);
            this.ctx.restore();
        }
    }

    /**
     * 绘制照片
     */
    _drawPhoto(photo) {
        if (!photo || !photo.image) {
            console.log('没有照片或图片对象，绘制占位符');
            this._drawPlaceholder();
            return;
        }
        
        console.log('绘制照片:', {
            url: photo.url,
            imageWidth: photo.image.width,
            imageHeight: photo.image.height,
            canvasWidth: this.canvas.width,
            canvasHeight: this.canvas.height,
            complete: photo.image.complete
        });
        
        // 先清空画布并填充黑色背景
        this.ctx.fillStyle = '#000';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // 绘制图片
        try {
            drawImageCentered(this.ctx, photo.image, 
                this.canvas.width, this.canvas.height);
            console.log('图片绘制完成');
        } catch (error) {
            console.error('绘制图片时出错:', error);
        }
    }

    /**
     * 获取当前状态
     */
    getState() {
        return { ...this.state };
    }

    /**
     * 销毁播放器
     */
    destroy() {
        this.stop();
        
        if (this.audio) {
            this.audio.src = '';
            this.audio = null;
        }
        
        this.photos = [];
        this.photoTimeline = [];
        this.currentPhoto = null;
        this.previousPhoto = null;
        
        this.clear(); // 清除所有事件监听器
        
        this.emit('destroyed');
    }
}
