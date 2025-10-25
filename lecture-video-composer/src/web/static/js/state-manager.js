/**
 * StateManager 应用状态管理器
 * 
 * 功能：
 * - 集中管理应用状态
 * - 状态持久化（LocalStorage）
 * - 状态变更通知
 * - 撤销/重做支持
 */

import { EventBus } from './utils.js';

export class StateManager extends EventBus {
    /**
     * 构造函数
     * @param {Object} initialState - 初始状态
     * @param {Object} options - 配置选项
     */
    constructor(initialState = {}, options = {}) {
        super();
        
        this.options = {
            persist: true,
            persistKey: 'lecture_video_composer_state',
            maxHistory: 50,
            ...options
        };
        
        // 状态
        this.state = {
            // 用户偏好
            preferences: {
                theme: 'light',
                volume: 0.8,
                playbackRate: 1.0,
                transitionType: 'fade',
                transitionDuration: 0.5,
                autoSave: true,
                ...initialState.preferences
            },
            
            // 当前会话
            session: {
                sessionId: null,
                projectId: null,
                projectName: null,
                isPlaying: false,
                currentTime: 0,
                duration: 0,
                ...initialState.session
            },
            
            // 项目列表
            projects: initialState.projects || [],
            
            // 上传状态
            uploads: {
                audioFiles: [],
                photoFiles: [],
                inProgress: false,
                ...initialState.uploads
            },
            
            // UI 状态
            ui: {
                currentView: 'upload',
                sidebarCollapsed: false,
                timelineExpanded: true,
                fullscreen: false,
                ...initialState.ui
            }
        };
        
        // 历史记录（用于撤销/重做）
        this.history = [];
        this.historyIndex = -1;
        
        // 加载持久化状态
        if (this.options.persist) {
            this.loadState();
        }
        
        // 自动保存
        if (this.options.persist) {
            this.on('stateChange', () => {
                this.saveState();
            });
        }
    }

    /**
     * 获取状态
     * @param {string} path - 状态路径，如 'session.projectId'
     * @returns {*} 状态值
     */
    get(path) {
        if (!path) return this.state;
        
        const keys = path.split('.');
        let value = this.state;
        
        for (const key of keys) {
            if (value && typeof value === 'object' && key in value) {
                value = value[key];
            } else {
                return undefined;
            }
        }
        
        return value;
    }

    /**
     * 设置状态
     * @param {string|Object} pathOrState - 状态路径或状态对象
     * @param {*} value - 状态值（如果第一个参数是路径）
     * @param {boolean} addToHistory - 是否添加到历史记录
     */
    set(pathOrState, value, addToHistory = true) {
        const oldState = JSON.parse(JSON.stringify(this.state));
        
        if (typeof pathOrState === 'string') {
            // 路径方式设置
            const keys = pathOrState.split('.');
            let target = this.state;
            
            for (let i = 0; i < keys.length - 1; i++) {
                const key = keys[i];
                if (!(key in target) || typeof target[key] !== 'object') {
                    target[key] = {};
                }
                target = target[key];
            }
            
            const lastKey = keys[keys.length - 1];
            target[lastKey] = value;
            
        } else if (typeof pathOrState === 'object') {
            // 对象方式设置
            this.state = this._deepMerge(this.state, pathOrState);
        }
        
        // 添加到历史
        if (addToHistory) {
            this._addToHistory(oldState);
        }
        
        // 触发变更事件
        this.emit('stateChange', {
            oldState,
            newState: this.state,
            path: typeof pathOrState === 'string' ? pathOrState : null
        });
    }

    /**
     * 更新状态（浅合并）
     * @param {string} path - 状态路径
     * @param {Object} updates - 更新对象
     */
    update(path, updates) {
        const current = this.get(path);
        if (typeof current === 'object' && typeof updates === 'object') {
            this.set(path, { ...current, ...updates });
        } else {
            this.set(path, updates);
        }
    }

    /**
     * 深度合并对象
     */
    _deepMerge(target, source) {
        const output = { ...target };
        
        for (const key in source) {
            if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
                if (target[key] && typeof target[key] === 'object') {
                    output[key] = this._deepMerge(target[key], source[key]);
                } else {
                    output[key] = source[key];
                }
            } else {
                output[key] = source[key];
            }
        }
        
        return output;
    }

    /**
     * 重置状态
     * @param {string} path - 状态路径（可选，不指定则重置全部）
     */
    reset(path) {
        if (path) {
            this.set(path, this._getInitialValue(path));
        } else {
            const oldState = this.state;
            this.state = this._getInitialState();
            this._addToHistory(oldState);
            this.emit('stateChange', { oldState, newState: this.state });
        }
    }

    /**
     * 获取初始状态
     */
    _getInitialState() {
        return {
            preferences: {
                theme: 'light',
                volume: 0.8,
                playbackRate: 1.0,
                transitionType: 'fade',
                transitionDuration: 0.5,
                autoSave: true
            },
            session: {
                sessionId: null,
                projectId: null,
                projectName: null,
                isPlaying: false,
                currentTime: 0,
                duration: 0
            },
            projects: [],
            uploads: {
                audioFiles: [],
                photoFiles: [],
                inProgress: false
            },
            ui: {
                currentView: 'upload',
                sidebarCollapsed: false,
                timelineExpanded: true,
                fullscreen: false
            }
        };
    }

    /**
     * 获取路径的初始值
     */
    _getInitialValue(path) {
        const initialState = this._getInitialState();
        return this._getValueByPath(initialState, path);
    }

    /**
     * 通过路径获取值
     */
    _getValueByPath(obj, path) {
        const keys = path.split('.');
        let value = obj;
        
        for (const key of keys) {
            if (value && typeof value === 'object' && key in value) {
                value = value[key];
            } else {
                return undefined;
            }
        }
        
        return value;
    }

    /**
     * 添加到历史记录
     */
    _addToHistory(state) {
        // 移除当前索引之后的历史
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // 添加新状态
        this.history.push(JSON.parse(JSON.stringify(state)));
        
        // 限制历史记录数量
        if (this.history.length > this.options.maxHistory) {
            this.history.shift();
        } else {
            this.historyIndex++;
        }
    }

    /**
     * 撤销
     */
    undo() {
        if (this.canUndo()) {
            this.historyIndex--;
            this.state = JSON.parse(JSON.stringify(this.history[this.historyIndex]));
            this.emit('stateChange', { action: 'undo', newState: this.state });
            return true;
        }
        return false;
    }

    /**
     * 重做
     */
    redo() {
        if (this.canRedo()) {
            this.historyIndex++;
            this.state = JSON.parse(JSON.stringify(this.history[this.historyIndex]));
            this.emit('stateChange', { action: 'redo', newState: this.state });
            return true;
        }
        return false;
    }

    /**
     * 是否可以撤销
     */
    canUndo() {
        return this.historyIndex > 0;
    }

    /**
     * 是否可以重做
     */
    canRedo() {
        return this.historyIndex < this.history.length - 1;
    }

    /**
     * 保存状态到 LocalStorage
     */
    saveState() {
        try {
            const serialized = JSON.stringify({
                state: this.state,
                timestamp: Date.now()
            });
            localStorage.setItem(this.options.persistKey, serialized);
        } catch (error) {
            console.error('Failed to save state:', error);
        }
    }

    /**
     * 从 LocalStorage 加载状态
     */
    loadState() {
        try {
            const serialized = localStorage.getItem(this.options.persistKey);
            if (serialized) {
                const { state, timestamp } = JSON.parse(serialized);
                
                // 检查状态是否过期（7天）
                const age = Date.now() - timestamp;
                const maxAge = 7 * 24 * 60 * 60 * 1000;
                
                if (age < maxAge) {
                    this.state = this._deepMerge(this.state, state);
                    
                    // 重置会话相关状态（不持久化）
                    this.state.session = {
                        ...this.state.session,
                        sessionId: null,
                        isPlaying: false,
                        currentTime: 0
                    };
                }
            }
        } catch (error) {
            console.error('Failed to load state:', error);
        }
    }

    /**
     * 清除持久化状态
     */
    clearPersistedState() {
        try {
            localStorage.removeItem(this.options.persistKey);
        } catch (error) {
            console.error('Failed to clear state:', error);
        }
    }

    /**
     * 订阅状态变更
     * @param {string} path - 状态路径（可选）
     * @param {Function} callback - 回调函数
     */
    subscribe(path, callback) {
        if (typeof path === 'function') {
            callback = path;
            path = null;
        }
        
        const handler = (data) => {
            if (!path || !data.path || data.path.startsWith(path)) {
                callback(this.get(path), data);
            }
        };
        
        this.on('stateChange', handler);
        
        // 返回取消订阅函数
        return () => this.off('stateChange', handler);
    }

    /**
     * 获取完整状态快照
     */
    getSnapshot() {
        return JSON.parse(JSON.stringify(this.state));
    }

    /**
     * 恢复状态快照
     */
    restoreSnapshot(snapshot) {
        const oldState = this.state;
        this.state = JSON.parse(JSON.stringify(snapshot));
        this._addToHistory(oldState);
        this.emit('stateChange', { oldState, newState: this.state, action: 'restore' });
    }

    /**
     * 导出状态为 JSON
     */
    exportState() {
        return JSON.stringify(this.state, null, 2);
    }

    /**
     * 从 JSON 导入状态
     */
    importState(json) {
        try {
            const imported = JSON.parse(json);
            this.restoreSnapshot(imported);
            return true;
        } catch (error) {
            console.error('Failed to import state:', error);
            return false;
        }
    }
}

export default StateManager;
