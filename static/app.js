const { createApp, ref, computed, onMounted, reactive, nextTick, watch } = Vue;
        const { ElMessage, ElMessageBox } = ElementPlus;

        const API_BASE = '/api';

        // ==========================================
        // 需求一：配置 Axios 全局拦截器
        // ==========================================
        // 从 localStorage 恢复已保存的密码
        const savedToken = localStorage.getItem('reading_tracker_token');
        if (savedToken) {
            axios.defaults.headers.common['X-Auth-Token'] = savedToken;
        }

        // 全局响应拦截器：捕获 401 未授权错误
        axios.interceptors.response.use(
            response => response,
            error => {
                if (error.response && error.response.status === 401) {
                    // 清除本地保存的密码
                    localStorage.removeItem('reading_tracker_token');
                    delete axios.defaults.headers.common['X-Auth-Token'];
                    // 如果当前 Vue 实例已挂载，更新认证状态
                    if (window.__vueApp__) {
                        window.__vueApp__.isAuthenticated = false;
                    } else {
                        window.location.reload();
                    }
                }
                return Promise.reject(error);
            }
        );

        const app = createApp({
            setup() {
                // ==========================================
                // 页面切换状态
                // ==========================================
                const currentPage = ref('home'); // 'home' 或 'stats'

                // ==========================================
                // 需求一：密码锁状态
                // ==========================================
                const isAuthenticated = ref(!!localStorage.getItem('reading_tracker_token'));
                const authPassword = ref('');
                const isAuthLoading = ref(false);
                const authError = ref('');

                const handleAuth = async () => {
                    if (!authPassword.value) {
                        authError.value = '请输入访问密码';
                        return;
                    }
                    isAuthLoading.value = true;
                    authError.value = '';
                    try {
                        // 用一次简单的 API 调用来验证密码
                        await axios.get(`${API_BASE}/books/`, {
                            headers: { 'X-Auth-Token': authPassword.value }
                        });
                        // 验证成功，保存密码
                        localStorage.setItem('reading_tracker_token', authPassword.value);
                        axios.defaults.headers.common['X-Auth-Token'] = authPassword.value;
                        isAuthenticated.value = true;
                        authPassword.value = '';
                        // 登录成功后加载数据
                        fetchBooks();
                        fetchCategories();
                        fetchPlatforms();
                    } catch (error) {
                        authError.value = '密码错误，请重试';
                    } finally {
                        isAuthLoading.value = false;
                    }
                };

                // 需求一：退出登录（锁定应用）
                const handleLogout = () => {
                    localStorage.removeItem('reading_tracker_token');
                    delete axios.defaults.headers.common['X-Auth-Token'];
                    isAuthenticated.value = false;
                    authPassword.value = '';
                    authError.value = '';
                    books.value = [];
                };

                // ==========================================
                // 需求四：夜间模式切换
                // ==========================================
                const isDarkMode = ref(localStorage.getItem('reading_tracker_dark') === 'true');
                // 初始化时应用夜间模式
                if (isDarkMode.value) {
                    document.body.classList.add('dark-mode');
                }
                const toggleDarkMode = () => {
                    isDarkMode.value = !isDarkMode.value;
                    if (isDarkMode.value) {
                        document.body.classList.add('dark-mode');
                        localStorage.setItem('reading_tracker_dark', 'true');
                    } else {
                        document.body.classList.remove('dark-mode');
                        localStorage.setItem('reading_tracker_dark', 'false');
                    }
                };

                // 响应式状态变量
                const books = ref([]);
                const searchQuery = ref('');
                const showAddDialog = ref(false);
                const showTimeline = ref(false);
                const isSubmitting = ref(false);
                
                const currentBookTitle = ref('');
                const currentLogs = ref([]);
                const currentBookInfo = ref(null);

                // 编辑书籍相关状态
                const showEditDialog = ref(false);
                const isEditing = ref(false);
                const editingBookId = ref(null);
                const editForm = reactive({
                    title: '',
                    cover: '',
                    category: '未分类',
                    rating: 0,
                    read_url: ''  // 需求一：阅读链接
                });

                // 编辑阅读记录相关状态
                const showEditLogDialog = ref(false);
                const isEditingLog = ref(false);
                const editingLogId = ref(null);
                const editLogForm = reactive({
                    platform: '微信读书',
                    status: '阅读中',
                    startDate: '',
                    progress: '',
                    notes: ''
                });

                // 录入表单的数据
                const formData = reactive({
                    title: '',
                    platform: '微信读书',
                    status: '阅读中',
                    startDate: new Date().toISOString().split('T')[0],
                    cover: '',
                    progress: '',
                    notes: '',
                    category: '未分类',
                    rating: 0,
                    read_url: ''  // 需求一：阅读链接
                });

                // 需求三：分类筛选
                const categoryFilter = ref('');

                // ==========================================
                // 分类管理相关状态
                // ==========================================
                const showCategoryDialog = ref(false);
                const categoryList = ref([]);
                const newCategoryName = ref('');
                const newCategoryIcon = ref('');
                const isAddingCategory = ref(false);
                // 图标选择对话框
                const showIconPickerDialog = ref(false);
                const editingCategory = ref(null);
                const editingCategoryIcon = ref('');
                // 常用 Emoji 图标列表，供分类选择
                const emojiList = ['📖', '📜', '💻', '🧠', '🧩', '📊', '🌱', '📂', '📚', '📕', '📗', '📘', '📙', '📔', '📓', '📒', '📃', '📄', '📁', '🗂️', '🏛️', '⚙️', '🔧', '🎨', '🎵', '🎬', '🎮', '🏀', '⚽', '🎯', '✈️', '🚀', '🌍', '🔬', '🧪', '💡', '💼', '💰', '🏆', '🥇', '⭐', '❤️', '💛', '💚', '💙', '💜', '🌈', '🔥', '💎', '🎁', '🎉', '🎊', '📌', '🔖', '📎', '🖊️', '✏️', '📝', '📋', '📅', '📆', '⏰', '🔔', '💬', '🗨️', '💭', '🧘', '🍎', '🍀', '🌻', '🌙', '☀️', '🌟', '✨', '💫', '🎈', '🎪', '🎭', '🎤', '🎧', '🎶', '🎹', '🎸', '🎺', '🎻', '🎲', '♟️', '🔮', '🕹️', '🖼️', '🗺️', '🧭', '🔍', '🔎', '🧲', '🎀', '🧸', '🪄', '🛡️', '⚔️', '🏹', '🧬', '🦠', '🔭', '🪐', '🌌', '🌊', '🏔️', '🏝️', '🌴', '🌸', '🌺', '🍁', '🍂', '🌾'];

                // ==========================================
                // 平台管理相关状态
                // ==========================================
                const showPlatformDialog = ref(false);
                const platformList = ref([]);
                const newPlatformName = ref('');
                const isAddingPlatform = ref(false);

                // ==========================================
                // 系统设置相关状态
                // ==========================================
                const siteSettings = reactive({
                    site_name: '个人阅读档案',
                    welcome_title: '欢迎回来，阅读者 👋',
                    welcome_subtitle: '今天又读了什么好书？赶快记录下你的阅读进度或听书历程吧。每一次记录都是灵魂的脚印。',
                    site_icon: '',
                    ai_provider: 'deepseek'
                });
                const showSettingsDialog = ref(false);
                const isSavingSettings = ref(false);
                const settingsActiveTab = ref('basic');

                // AI 服务商预设配置
                const aiProviderPresets = {
                    deepseek: {
                        name: 'DeepSeek',
                        icon: '🔮',
                        base_url: 'https://api.deepseek.com',
                        models: ['deepseek-chat', 'deepseek-reasoner'],
                        needApiKey: true,
                        apiKeyPlaceholder: '输入 DeepSeek API Key',
                        description: '国产高性能大模型，性价比极高'
                    },
                    openai: {
                        name: 'OpenAI',
                        icon: '🤖',
                        base_url: 'https://api.openai.com/v1',
                        models: ['gpt-4o', 'gpt-4o-mini', 'gpt-3.5-turbo'],
                        needApiKey: true,
                        apiKeyPlaceholder: '输入 OpenAI API Key (sk-...)',
                        description: '全球领先的 AI 模型，功能强大'
                    },
                    gemini: {
                        name: 'Google Gemini',
                        icon: '✨',
                        base_url: 'https://generativelanguage.googleapis.com/v1beta/openai',
                        models: ['gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-2.5-pro'],
                        needApiKey: true,
                        apiKeyPlaceholder: '输入 Google AI Studio API Key',
                        description: 'Google 旗舰多模态模型'
                    },
                    ollama: {
                        name: 'Ollama (本地)',
                        icon: '🦙',
                        base_url: 'http://localhost:11434/v1',
                        models: ['qwen2.5:7b', 'llama3.1:8b', 'deepseek-r1:7b', 'gemma2:9b', 'mistral:7b'],
                        needApiKey: false,
                        apiKeyPlaceholder: '',
                        description: '本地运行，无需 API Key，隐私安全'
                    },
                    custom: {
                        name: '自定义',
                        icon: '⚙️',
                        base_url: '',
                        models: [],
                        needApiKey: true,
                        apiKeyPlaceholder: '输入 API Key',
                        description: '兼容 OpenAI 格式的第三方服务'
                    }
                };

                // 当前选中服务商的预设信息（计算属性）
                const currentProviderPreset = computed(() => {
                    return aiProviderPresets[settingsForm.ai_provider] || aiProviderPresets.custom;
                });

                // 切换 AI 服务商时自动填充预设配置
                const onAiProviderChange = (provider) => {
                    const preset = aiProviderPresets[provider];
                    if (!preset) return;
                    // 自动填充 Base URL
                    settingsForm.ai_base_url = preset.base_url;
                    // 自动选择第一个模型
                    if (preset.models.length > 0) {
                        settingsForm.ai_model_name = preset.models[0];
                    } else {
                        settingsForm.ai_model_name = '';
                    }
                    // 如果不需要 API Key（如 Ollama），清空密钥输入
                    if (!preset.needApiKey) {
                        settingsForm.ai_api_key = '';
                    }
                };

                const settingsForm = reactive({
                    site_name: '',
                    welcome_title: '',
                    welcome_subtitle: '',
                    site_icon: '',
                    // AI 配置
                    ai_provider: 'deepseek',
                    ai_api_key: '',
                    ai_api_key_set: false,
                    ai_base_url: '',
                    ai_model_name: ''
                });

                // 从后端加载系统设置
                const fetchSettings = async () => {
                    try {
                        const res = await axios.get(`${API_BASE}/settings/`);
                        Object.assign(siteSettings, res.data);
                    } catch (error) {
                        console.error('获取系统设置失败', error);
                    }
                };

                // 打开系统设置对话框
                const openSettingsDialog = () => {
                    settingsForm.site_name = siteSettings.site_name;
                    settingsForm.welcome_title = siteSettings.welcome_title;
                    settingsForm.welcome_subtitle = siteSettings.welcome_subtitle;
                    settingsForm.site_icon = siteSettings.site_icon;
                    // AI 配置
                    settingsForm.ai_provider = siteSettings.ai_provider || 'deepseek';
                    settingsForm.ai_api_key = '';  // 不回显密钥，留空表示不修改
                    settingsForm.ai_api_key_set = siteSettings.ai_api_key_set;
                    settingsForm.ai_base_url = siteSettings.ai_base_url;
                    settingsForm.ai_model_name = siteSettings.ai_model_name;
                    settingsActiveTab.value = 'basic';
                    showSettingsDialog.value = true;
                };

                // 保存系统设置
                const handleSaveSettings = async () => {
                    if (!settingsForm.site_name.trim()) {
                        ElMessage.warning('系统名称不能为空');
                        return;
                    }
                    if (!settingsForm.welcome_title.trim()) {
                        ElMessage.warning('欢迎标题不能为空');
                        return;
                    }
                    // 验证：如果服务商需要 API Key 且未配置过，则必须填写
                    const preset = aiProviderPresets[settingsForm.ai_provider];
                    if (preset && preset.needApiKey && !settingsForm.ai_api_key && !settingsForm.ai_api_key_set) {
                        ElMessage.warning('当前服务商需要 API Key，请填写');
                        settingsActiveTab.value = 'ai';
                        return;
                    }
                    isSavingSettings.value = true;
                    try {
                        const payload = {
                            site_name: settingsForm.site_name.trim(),
                            welcome_title: settingsForm.welcome_title.trim(),
                            welcome_subtitle: settingsForm.welcome_subtitle.trim(),
                            site_icon: settingsForm.site_icon,
                            ai_provider: settingsForm.ai_provider
                        };
                        // AI 配置：仅在用户填写了 API Key 时才发送（留空表示不修改）
                        if (settingsForm.ai_api_key) {
                            payload.ai_api_key = settingsForm.ai_api_key;
                        }
                        if (settingsForm.ai_base_url) {
                            payload.ai_base_url = settingsForm.ai_base_url.trim();
                        }
                        if (settingsForm.ai_model_name) {
                            payload.ai_model_name = settingsForm.ai_model_name.trim();
                        }
                        await axios.post(`${API_BASE}/settings/`, payload);
                        // 更新本地状态
                        Object.assign(siteSettings, {
                            site_name: settingsForm.site_name.trim(),
                            welcome_title: settingsForm.welcome_title.trim(),
                            welcome_subtitle: settingsForm.welcome_subtitle.trim(),
                            site_icon: settingsForm.site_icon,
                            ai_provider: settingsForm.ai_provider,
                            ai_api_key_set: settingsForm.ai_api_key ? true : siteSettings.ai_api_key_set,
                            ai_base_url: settingsForm.ai_base_url.trim() || siteSettings.ai_base_url,
                            ai_model_name: settingsForm.ai_model_name.trim() || siteSettings.ai_model_name
                        });
                        // 更新页面标题
                        document.title = settingsForm.site_name.trim();
                        ElMessage.success('系统设置保存成功！');
                        showSettingsDialog.value = false;
                    } catch (error) {
                        ElMessage.error('保存设置失败，请检查网络');
                    } finally {
                        isSavingSettings.value = false;
                    }
                };

                // 系统设置图标上传
                const handleSettingsIconUpload = async (options) => {
                    const uploadData = new FormData();
                    uploadData.append('file', options.file);
                    try {
                        const res = await axios.post(`${API_BASE}/upload/cover`, uploadData, {
                            headers: { 'Content-Type': 'multipart/form-data' }
                        });
                        settingsForm.site_icon = res.data.url;
                        ElMessage.success('图标上传成功！');
                    } catch (error) {
                        ElMessage.error('图标上传失败');
                    }
                };

                // 修改密码相关状态
                const showChangePasswordDialog = ref(false);
                const isChangingPassword = ref(false);
                const changePasswordForm = reactive({
                    oldPassword: '',
                    newPassword: '',
                    confirmPassword: ''
                });

                // 从 API 获取分类列表
                const fetchCategories = async () => {
                    try {
                        const res = await axios.get(`${API_BASE}/categories/`);
                        categoryList.value = res.data;
                    } catch (error) {
                        console.error('获取分类列表失败', error);
                    }
                };

                // 打开分类管理对话框
                const openCategoryManager = () => {
                    showCategoryDialog.value = true;
                };

                // 添加分类
                const handleAddCategory = async () => {
                    const name = newCategoryName.value.trim();
                    if (!name) {
                        ElMessage.warning('请输入分类名称');
                        return;
                    }
                    isAddingCategory.value = true;
                    try {
                        const payload = { name };
                        if (newCategoryIcon.value) {
                            payload.icon = newCategoryIcon.value;
                        }
                        await axios.post(`${API_BASE}/categories/`, payload);
                        ElMessage.success(`分类「${name}」创建成功`);
                        newCategoryName.value = '';
                        newCategoryIcon.value = '';
                        await fetchCategories();
                    } catch (error) {
                        if (error.response?.data?.detail) {
                            ElMessage.error(error.response.data.detail);
                        } else {
                            ElMessage.error('创建分类失败');
                        }
                    } finally {
                        isAddingCategory.value = false;
                    }
                };

                // 更新分类图标
                const updateCategoryIcon = async (cat, emoji) => {
                    try {
                        await axios.put(`${API_BASE}/categories/${cat.id}`, { icon: emoji });
                        cat.icon = emoji;
                        ElMessage.success(`图标已更新`);
                    } catch (error) {
                        ElMessage.error('图标更新失败');
                    }
                };

                // 打开图标选择器
                const openIconPicker = (cat) => {
                    editingCategory.value = cat;
                    editingCategoryIcon.value = cat.icon || '';
                    showIconPickerDialog.value = true;
                };

                // 确认选择图标
                const confirmCategoryIcon = (emoji) => {
                    if (!editingCategory.value) return;
                    if (!emoji) {
                        ElMessage.warning('请选择一个图标');
                        return;
                    }
                    updateCategoryIcon(editingCategory.value, emoji);
                    showIconPickerDialog.value = false;
                };

                // 删除分类
                const handleDeleteCategory = async (id, name) => {
                    try {
                        await ElMessageBox.confirm(
                            `确定要删除分类「${name}」吗？`,
                            '删除确认',
                            { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
                        );
                        await axios.delete(`${API_BASE}/categories/${id}`);
                        ElMessage.success(`分类「${name}」已删除`);
                        await fetchCategories();
                    } catch (error) {
                        if (error !== 'cancel') {
                            ElMessage.error('删除分类失败');
                        }
                    }
                };

                // ==========================================
                // 平台管理 API 方法
                // ==========================================
                // 从 API 获取平台列表
                const fetchPlatforms = async () => {
                    try {
                        const res = await axios.get(`${API_BASE}/platforms/`);
                        platformList.value = res.data;
                    } catch (error) {
                        console.error('获取平台列表失败', error);
                    }
                };

                // 打开平台管理对话框
                const openPlatformManager = () => {
                    showPlatformDialog.value = true;
                };

                // 添加平台
                const handleAddPlatform = async () => {
                    const name = newPlatformName.value.trim();
                    if (!name) {
                        ElMessage.warning('请输入平台名称');
                        return;
                    }
                    isAddingPlatform.value = true;
                    try {
                        await axios.post(`${API_BASE}/platforms/`, { name });
                        ElMessage.success(`平台「${name}」创建成功`);
                        newPlatformName.value = '';
                        await fetchPlatforms();
                    } catch (error) {
                        if (error.response?.data?.detail) {
                            ElMessage.error(error.response.data.detail);
                        } else {
                            ElMessage.error('创建平台失败');
                        }
                    } finally {
                        isAddingPlatform.value = false;
                    }
                };

                // 删除平台
                const handleDeletePlatform = async (id, name) => {
                    try {
                        await ElMessageBox.confirm(
                            `确定要删除平台「${name}」吗？`,
                            '删除确认',
                            { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
                        );
                        await axios.delete(`${API_BASE}/platforms/${id}`);
                        ElMessage.success(`平台「${name}」已删除`);
                        await fetchPlatforms();
                    } catch (error) {
                        if (error !== 'cancel') {
                            ElMessage.error('删除平台失败');
                        }
                    }
                };

                // 修改访问密码
                const handleChangePassword = async () => {
                    const { oldPassword, newPassword, confirmPassword } = changePasswordForm;
                    
                    // 表单校验
                    if (!oldPassword) {
                        ElMessage.warning('请输入原密码');
                        return;
                    }
                    if (!newPassword) {
                        ElMessage.warning('请输入新密码');
                        return;
                    }
                    if (newPassword.length < 4) {
                        ElMessage.warning('新密码长度不能少于 4 位');
                        return;
                    }
                    if (newPassword !== confirmPassword) {
                        ElMessage.warning('两次输入的新密码不一致');
                        return;
                    }

                    isChangingPassword.value = true;
                    try {
                        const res = await axios.post(`${API_BASE}/settings/change-password`, {
                            old_password: oldPassword,
                            new_password: newPassword,
                            confirm_password: confirmPassword
                        });
                        
                        // 修改成功，更新 localStorage 中的 token
                        localStorage.setItem('reading_tracker_token', newPassword);
                        axios.defaults.headers.common['X-Auth-Token'] = newPassword;
                        
                        ElMessage.success('密码修改成功！');
                        showChangePasswordDialog.value = false;
                        // 清空表单
                        changePasswordForm.oldPassword = '';
                        changePasswordForm.newPassword = '';
                        changePasswordForm.confirmPassword = '';
                    } catch (error) {
                        if (error.response?.data?.detail) {
                            ElMessage.error(error.response.data.detail);
                        } else {
                            ElMessage.error('密码修改失败，请检查网络');
                        }
                    } finally {
                        isChangingPassword.value = false;
                    }
                };

                // 根据分类名称获取图标
                const getCategoryIcon = (categoryName) => {
                    if (!categoryName) return '📁';
                    const found = categoryList.value.find(cat => cat.name === categoryName);
                    return found?.icon || '📁';
                };

                // 计算属性：从 API 分类列表 + 书籍中已有的分类合并去重
                const availableCategories = computed(() => {
                    const cats = new Set();
                    // 1. 从 API 获取的分类列表
                    categoryList.value.forEach(cat => {
                        if (cat.name && cat.name !== '未分类') {
                            cats.add(cat.name);
                        }
                    });
                    // 2. 从已有书籍中提取分类（兼容旧数据）
                    books.value.forEach(book => {
                        if (book.category && book.category !== '未分类') {
                            cats.add(book.category);
                        }
                    });
                    return Array.from(cats).sort();
                });

                // 计算属性：模糊搜索 + 分类筛选
                const filteredBooks = computed(() => {
                    let result = books.value;
                    // 按书名搜索
                    if (searchQuery.value) {
                        result = result.filter(book => book.title.includes(searchQuery.value));
                    }
                    // 按分类筛选
                    if (categoryFilter.value) {
                        result = result.filter(book => book.category === categoryFilter.value);
                    }
                    return result;
                });

                // 计算属性：统计数据
                const totalBooks = computed(() => books.value.length);
                const readingBooks = computed(() => books.value.filter(book => book.status === '阅读中' || book.status === '正在听').length);
                const completedBooks = computed(() => books.value.filter(book => book.status === '已读完' || book.status === '已听完').length);

                // ==========================================
                // 阅读统计看板
                // ==========================================
                const statsSummary = reactive({ this_week_logs: 0, this_week_books: 0 });
                let weekTrendChartInstance = null;
                let monthTrendChartInstance = null;
                let statusChartInstance = null;
                let platformChartInstance = null;

                const colorPalette = [
                    '#4f46e5', '#10b981', '#f59e0b', '#ef4444',
                    '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
                    '#14b8a6', '#6366f1', '#84cc16', '#d946ef'
                ];

                const fetchStats = async () => {
                    try {
                        const res = await axios.get(`${API_BASE}/stats/`);
                        const data = res.data;
                        statsSummary.this_week_logs = data.summary.this_week_logs;
                        statsSummary.this_week_books = data.summary.this_week_books;
                        renderWeekTrendChart(data.week);
                        renderMonthTrendChart(data.month);
                        renderStatusChart(data.status);
                        renderPlatformChart(data.platform);
                    } catch (error) {
                        console.error('获取统计数据失败', error);
                    }
                };

                const getChartThemeColors = () => {
                    const isDark = isDarkMode.value;
                    return {
                        textColor: isDark ? '#9ca3af' : '#6b7280',
                        axisLineColor: isDark ? '#334155' : '#e5e7eb',
                        splitLineColor: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
                        bgColor: 'transparent'
                    };
                };

                const renderWeekTrendChart = (weekData) => {
                    const chartDom = document.getElementById('weekTrendChart');
                    if (!chartDom) return;
                    if (weekTrendChartInstance) weekTrendChartInstance.dispose();
                    weekTrendChartInstance = echarts.init(chartDom);
                    const theme = getChartThemeColors();
                    weekTrendChartInstance.setOption({
                        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
                        grid: { left: '8%', right: '4%', top: '10%', bottom: '15%' },
                        xAxis: {
                            type: 'category',
                            data: weekData.labels,
                            axisLabel: { color: theme.textColor, fontSize: 11 },
                            axisLine: { lineStyle: { color: theme.axisLineColor } }
                        },
                        yAxis: {
                            type: 'value',
                            minInterval: 1,
                            axisLabel: { color: theme.textColor, fontSize: 11 },
                            splitLine: { lineStyle: { color: theme.splitLineColor } }
                        },
                        series: [{
                            data: weekData.data,
                            type: 'bar',
                            barWidth: '45%',
                            itemStyle: {
                                borderRadius: [6, 6, 0, 0],
                                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                    { offset: 0, color: '#818cf8' },
                                    { offset: 1, color: '#4f46e5' }
                                ])
                            },
                            emphasis: {
                                itemStyle: {
                                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                        { offset: 0, color: '#a5b4fc' },
                                        { offset: 1, color: '#6366f1' }
                                    ])
                                }
                            }
                        }]
                    });
                };

                const renderMonthTrendChart = (monthData) => {
                    const chartDom = document.getElementById('monthTrendChart');
                    if (!chartDom) return;
                    if (monthTrendChartInstance) monthTrendChartInstance.dispose();
                    monthTrendChartInstance = echarts.init(chartDom);
                    const theme = getChartThemeColors();
                    // 简化月份标签显示
                    const shortLabels = monthData.labels.map(l => l.split('-')[1] + '月');
                    monthTrendChartInstance.setOption({
                        tooltip: { trigger: 'axis' },
                        grid: { left: '8%', right: '4%', top: '10%', bottom: '15%' },
                        xAxis: {
                            type: 'category',
                            data: shortLabels,
                            axisLabel: { color: theme.textColor, fontSize: 10, rotate: 30 },
                            axisLine: { lineStyle: { color: theme.axisLineColor } }
                        },
                        yAxis: {
                            type: 'value',
                            minInterval: 1,
                            axisLabel: { color: theme.textColor, fontSize: 11 },
                            splitLine: { lineStyle: { color: theme.splitLineColor } }
                        },
                        series: [{
                            data: monthData.data,
                            type: 'line',
                            smooth: true,
                            symbol: 'circle',
                            symbolSize: 6,
                            lineStyle: { width: 3, color: '#10b981' },
                            itemStyle: { color: '#10b981', borderWidth: 2, borderColor: '#fff' },
                            areaStyle: {
                                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                    { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
                                    { offset: 1, color: 'rgba(16, 185, 129, 0.02)' }
                                ])
                            }
                        }]
                    });
                };

                const renderStatusChart = (statusData) => {
                    const chartDom = document.getElementById('statusChart');
                    if (!chartDom) return;
                    if (statusChartInstance) statusChartInstance.dispose();
                    statusChartInstance = echarts.init(chartDom);
                    const statusColorMap = { '阅读中': '#f59e0b', '正在听': '#f59e0b', '已读完': '#10b981', '已听完': '#10b981', '已弃坑': '#9ca3af' };
                    const coloredData = statusData.map(item => ({
                        ...item,
                        itemStyle: { color: statusColorMap[item.name] || colorPalette[0] }
                    }));
                    statusChartInstance.setOption({
                        tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
                        legend: { bottom: '2%', textStyle: { fontSize: 11, color: getChartThemeColors().textColor }, itemWidth: 10, itemHeight: 10 },
                        series: [{
                            type: 'pie',
                            radius: ['40%', '65%'],
                            center: ['50%', '42%'],
                            avoidLabelOverlap: true,
                            padAngle: 3,
                            itemStyle: { borderRadius: 6, borderColor: isDarkMode.value ? '#16213e' : '#fff', borderWidth: 2 },
                            label: { show: false },
                            emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
                            data: coloredData
                        }]
                    });
                };

                const renderPlatformChart = (platformData) => {
                    const chartDom = document.getElementById('platformChart');
                    if (!chartDom) return;
                    if (platformChartInstance) platformChartInstance.dispose();
                    platformChartInstance = echarts.init(chartDom);
                    platformChartInstance.setOption({
                        tooltip: { trigger: 'item', formatter: '{b}: {c} 条 ({d}%)' },
                        legend: { bottom: '2%', textStyle: { fontSize: 11, color: getChartThemeColors().textColor }, itemWidth: 10, itemHeight: 10 },
                        series: [{
                            type: 'pie',
                            radius: ['40%', '65%'],
                            center: ['50%', '42%'],
                            roseType: 'area',
                            avoidLabelOverlap: true,
                            padAngle: 3,
                            itemStyle: { borderRadius: 6, borderColor: isDarkMode.value ? '#16213e' : '#fff', borderWidth: 2 },
                            label: { show: false },
                            emphasis: { label: { show: true, fontSize: 13, fontWeight: 'bold' } },
                            data: platformData,
                            color: colorPalette
                        }]
                    });
                };

                // 窗口大小变化时自适应所有统计图表
                const statsResizeHandler = () => {
                    weekTrendChartInstance && weekTrendChartInstance.resize();
                    monthTrendChartInstance && monthTrendChartInstance.resize();
                    statusChartInstance && statusChartInstance.resize();
                    platformChartInstance && platformChartInstance.resize();
                };
                window.addEventListener('resize', statsResizeHandler);

                // 获取所有书籍列表
                const fetchBooks = async () => {
                    try {
                        const res = await axios.get(`${API_BASE}/books/`);
                        books.value = res.data;
                        
                        // 补充获取每本书的最新 platform
                        for(let book of books.value) {
                            try {
                                const logsRes = await axios.get(`${API_BASE}/books/${book.id}/logs`);
                                book.logs = logsRes.data;
                            } catch(e) {}
                        }
                        
                        // 需求三：数据获取完成后，渲染分类占比饼图
                        renderCategoryChart();
                    } catch (error) {
                        if (error.response && error.response.status !== 401) {
                            ElMessage.error('无法连接到后端数据库，请检查网络');
                        }
                        console.error(error);
                    }
                };

                // 需求三：渲染藏书分类占比饼图
                let categoryChartInstance = null;
                const renderCategoryChart = () => {
                    const chartDom = document.getElementById('categoryChart');
                    if (!chartDom) return;
                    
                    // 如果已有实例，先销毁再重建（确保数据刷新）
                    if (categoryChartInstance) {
                        categoryChartInstance.dispose();
                    }
                    categoryChartInstance = echarts.init(chartDom);
                    
                    // 统计各分类的书籍数量
                    const categoryMap = {};
                    books.value.forEach(book => {
                        const cat = book.category && book.category !== '未分类' ? book.category : '未分类';
                        categoryMap[cat] = (categoryMap[cat] || 0) + 1;
                    });
                    
                    // 转换为 ECharts 数据格式，按数量降序排列
                    const sortedData = Object.entries(categoryMap)
                        .map(([name, value]) => ({ name, value }))
                        .sort((a, b) => b.value - a.value);
                    
                    // 定义一组柔和的配色
                    const colorPalette = [
                        '#4f46e5', '#10b981', '#f59e0b', '#ef4444',
                        '#8b5cf6', '#06b6d4', '#f97316', '#ec4899',
                        '#14b8a6', '#6366f1', '#84cc16', '#d946ef'
                    ];
                    
                    const option = {
                        tooltip: {
                            trigger: 'item',
                            formatter: '{b}: {c} 本 ({d}%)'
                        },
                        legend: {
                            orient: 'vertical',
                            right: '2%',
                            top: 'center',
                            textStyle: { fontSize: 10, color: '#6b7280' },
                            itemWidth: 8,
                            itemHeight: 8,
                            itemGap: 4
                        },
                        series: [
                            {
                                type: 'pie',
                                radius: ['30%', '60%'],
                                center: ['32%', '50%'],
                                avoidLabelOverlap: true,
                                padAngle: 2,
                                itemStyle: {
                                    borderRadius: 4,
                                    borderColor: '#fff',
                                    borderWidth: 1
                                },
                                label: {
                                    show: false
                                },
                                emphasis: {
                                    label: {
                                        show: true,
                                        fontSize: 12,
                                        fontWeight: 'bold'
                                    },
                                    itemStyle: {
                                        shadowBlur: 8,
                                        shadowOffsetX: 0,
                                        shadowColor: 'rgba(0, 0, 0, 0.2)'
                                    }
                                },
                                labelLine: {
                                    show: false
                                },
                                data: sortedData,
                                color: colorPalette
                            }
                        ]
                    };
                    
                    categoryChartInstance.setOption(option);
                    
                    // 窗口大小变化时自适应
                    const resizeHandler = () => {
                        categoryChartInstance && categoryChartInstance.resize();
                    };
                    window.removeEventListener('resize', resizeHandler);
                    window.addEventListener('resize', resizeHandler);
                };

                // 提交逻辑
                const handleCheckAndSubmit = async () => {
                    if (!formData.title || !formData.platform) {
                        ElMessage.warning('书名和平台不能为空哦！');
                        return;
                    }
                    isSubmitting.value = true;
                    try {
                        const checkRes = await axios.get(`${API_BASE}/books/check`, { params: { title: formData.title } });
                        
                        if (checkRes.data.exists) {
                            await ElMessageBox.confirm(
                                '此书已在书架中，是否要增加一次新的阅读记录？',
                                '发现重复书籍',
                                { confirmButtonText: '增加记录', cancelButtonText: '取消', type: 'info' }
                            );
                            await axios.post(`${API_BASE}/books/${checkRes.data.book_id}/logs`, {
                                platform: formData.platform,
                                status: formData.status,
                                start_date: formData.startDate,
                                progress: formData.progress || null,
                                notes: formData.notes || null
                            });
                            ElMessage.success('成功追加一条阅读记录！');
                        } else {
                            await axios.post(`${API_BASE}/books/`, {
                                title: formData.title,
                                cover: formData.cover,
                                category: formData.category || '未分类',
                                rating: formData.rating || 0,
                                read_url: formData.read_url || null,  // 需求一：阅读链接
                                log: {
                                    platform: formData.platform,
                                    status: formData.status,
                                    start_date: formData.startDate,
                                    progress: formData.progress || null,
                                    notes: formData.notes || null
                                }
                            });
                            ElMessage.success('新书录入成功！');
                        }
                        showAddDialog.value = false;
                        fetchBooks();
                    } catch (error) {
                        if (error !== 'cancel') {
                            ElMessage.error('操作失败，请检查网络');
                        }
                    } finally {
                        isSubmitting.value = false;
                    }
                };

                // 打开时间轴抽屉
                const openTimeline = async (book) => {
                    currentBookTitle.value = book.title;
                    currentLogs.value = [];
                    // 保存当前书籍的分类和评分信息
                    currentBookInfo.value = {
                        category: book.category,
                        rating: book.rating
                    };
                    showTimeline.value = true;
                    try {
                        const res = await axios.get(`${API_BASE}/books/${book.id}/logs`);
                        currentLogs.value = res.data;
                    } catch (error) {
                        ElMessage.error('获取阅读记录失败');
                    }
                };

                // 删除阅读记录
                const deleteLog = async (logId, bookId) => {
                    try {
                        await ElMessageBox.confirm(
                            '确定要删除这条阅读记录吗？',
                            '删除确认',
                            { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'error' }
                        );
                        
                        await axios.delete(`${API_BASE}/logs/${logId}`);
                        ElMessage.success('删除成功！');
                        
                        const res = await axios.get(`${API_BASE}/books/${bookId}/logs`);
                        currentLogs.value = res.data;
                        fetchBooks();
                        
                        if(currentLogs.value.length === 0) {
                            showTimeline.value = false;
                        }
                    } catch (error) {
                        if (error !== 'cancel') {
                            ElMessage.error('删除失败');
                        }
                    }
                };

                // 需求二：快捷更新阅读进度
                const quickUpdateProgress = async (book) => {
                    // 找到该书最新一条阅读记录的 ID
                    let logId = null;
                    try {
                        const logsRes = await axios.get(`${API_BASE}/books/${book.id}/logs`);
                        const logs = logsRes.data;
                        if (logs && logs.length > 0) {
                            logId = logs[0].id;
                        }
                    } catch (e) {
                        ElMessage.error('获取阅读记录失败');
                        return;
                    }

                    if (!logId) {
                        ElMessage.warning('该书暂无阅读记录，无法更新进度');
                        return;
                    }

                    try {
                        const { value } = await ElMessageBox.prompt(
                            `更新《${book.title}》的阅读进度`,
                            '✏️ 更新进度',
                            {
                                confirmButtonText: '保存',
                                cancelButtonText: '取消',
                                inputPlaceholder: '如：第823章、50%、看到第3卷...',
                                inputValue: book.progress || '',
                                inputPattern: /.+/,
                                inputErrorMessage: '进度内容不能为空',
                                closeOnClickModal: false,
                                distinguishCancelAndClose: true
                            }
                        );

                        // 调用 PATCH 接口快速更新进度
                        await axios.patch(`${API_BASE}/logs/${logId}/progress`, {
                            progress: value
                        });

                        ElMessage.success('进度更新成功！');
                        // 局部刷新：更新当前书籍的 progress 字段
                        book.progress = value;
                        // 同时刷新后端数据以保持一致性
                        fetchBooks();
                    } catch (error) {
                        if (error === 'cancel' || error === 'close') {
                            // 用户取消或点击关闭，不做任何操作
                            return;
                        }
                        if (error.response?.data?.detail) {
                            ElMessage.error(error.response.data.detail);
                        } else {
                            ElMessage.error('进度更新失败，请检查网络');
                        }
                    }
                };

                // 打开编辑书籍对话框
                const openEditDialog = () => {
                    const book = books.value.find(b => b.title === currentBookTitle.value);
                    if (book) {
                        editingBookId.value = book.id;
                        editForm.title = book.title;
                        editForm.cover = book.cover || '';
                        editForm.category = book.category || '未分类';
                        editForm.rating = book.rating || 0;
                        editForm.read_url = book.read_url || '';  // 需求一：阅读链接
                        showEditDialog.value = true;
                    }
                };

                // 提交编辑书籍
                const handleEditSubmit = async () => {
                    if (!editForm.title) {
                        ElMessage.warning('书名不能为空！');
                        return;
                    }
                    isEditing.value = true;
                    try {
                        await axios.put(`${API_BASE}/books/${editingBookId.value}`, {
                            title: editForm.title,
                            cover: editForm.cover,
                            category: editForm.category,
                            rating: editForm.rating,
                            read_url: editForm.read_url  // 需求一：阅读链接（空字符串表示清空）
                        });
                        ElMessage.success('书籍信息更新成功！');
                        showEditDialog.value = false;
                        await fetchBooks();
                        currentBookTitle.value = editForm.title;
                    } catch (error) {
                        if (error.response?.data?.detail) {
                            ElMessage.error(error.response.data.detail);
                        } else {
                            ElMessage.error('更新失败，请检查网络');
                        }
                    } finally {
                        isEditing.value = false;
                    }
                };

                // 打开编辑阅读记录对话框
                const openEditLogDialog = (log) => {
                    editingLogId.value = log.id;
                    editLogForm.platform = log.platform;
                    editLogForm.status = log.status;
                    editLogForm.startDate = formatDate(log.start_date);
                    editLogForm.progress = log.progress || '';
                    editLogForm.notes = log.notes || '';
                    showEditLogDialog.value = true;
                };

                // 提交编辑阅读记录
                const handleEditLogSubmit = async () => {
                    if (!editLogForm.platform) {
                        ElMessage.warning('平台不能为空！');
                        return;
                    }
                    isEditingLog.value = true;
                    try {
                        await axios.put(`${API_BASE}/logs/${editingLogId.value}`, {
                            platform: editLogForm.platform,
                            status: editLogForm.status,
                            start_date: editLogForm.startDate || null,
                            progress: editLogForm.progress || null,
                            notes: editLogForm.notes || null
                        });
                        ElMessage.success('阅读记录更新成功！');
                        showEditLogDialog.value = false;
                        // 刷新当前时间轴的阅读记录
                        const res = await axios.get(`${API_BASE}/books/${currentLogs.value[0]?.book_id}/logs`);
                        currentLogs.value = res.data;
                        fetchBooks();
                    } catch (error) {
                        if (error.response?.data?.detail) {
                            ElMessage.error(error.response.data.detail);
                        } else {
                            ElMessage.error('更新失败，请检查网络');
                        }
                    } finally {
                        isEditingLog.value = false;
                    }
                };

                // 需求三：分类筛选变化时
                const onCategoryFilterChange = (value) => {
                    categoryFilter.value = value || '';
                };

                // 需求四：导出备份
                const handleExport = async () => {
                    try {
                        const res = await axios.get(`${API_BASE}/export`);
                        const today = new Date().toISOString().split('T')[0];
                        const filename = `reading_backup_${today}.json`;
                        const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = filename;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                        ElMessage.success(`备份文件 ${filename} 已下载！`);
                    } catch (error) {
                        ElMessage.error('导出备份失败，请检查网络');
                        console.error(error);
                    }
                };

                // 需求四：导入备份 - 触发文件选择
                const importFileInput = ref(null);
                const triggerImport = () => {
                    importFileInput.value?.click();
                };

                // ==========================================
                // 需求四：设置下拉菜单命令处理
                // ==========================================
                const handleSettingsCommand = (command) => {
                    switch (command) {
                        case 'settings':
                            openSettingsDialog();
                            break;
                        case 'category':
                            openCategoryManager();
                            break;
                        case 'platform':
                            openPlatformManager();
                            break;
                        case 'import':
                            triggerImport();
                            break;
                        case 'export':
                            handleExport();
                            break;
                        case 'changePassword':
                            showChangePasswordDialog.value = true;
                            break;
                        case 'lock':
                            handleLogout();
                            break;
                        case 'darkmode':
                            toggleDarkMode();
                            break;
                    }
                };

                // 需求四：导入备份 - 读取并上传 JSON 文件
                const handleImport = async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;

                    // 检查文件类型
                    if (!file.name.endsWith('.json')) {
                        ElMessage.error('请选择 JSON 格式的备份文件');
                        event.target.value = '';
                        return;
                    }

                    try {
                        // 读取文件内容
                        const text = await file.text();
                        const data = JSON.parse(text);

                        // 验证备份文件格式
                        if (!data.books || !Array.isArray(data.books)) {
                            ElMessage.error('备份文件格式无效，缺少 books 字段');
                            event.target.value = '';
                            return;
                        }

                        // 确认导入
                        try {
                            await ElMessageBox.confirm(
                                `即将导入 ${data.books.length} 本书籍数据（书名重复的书籍将自动跳过），是否继续？`,
                                '导入备份确认',
                                { confirmButtonText: '开始导入', cancelButtonText: '取消', type: 'info' }
                            );
                        } catch {
                            event.target.value = '';
                            return;
                        }

                        // 发送导入请求
                        const res = await axios.post(`${API_BASE}/import`, data);
                        ElMessage.success(res.data.message);
                        event.target.value = '';
                        // 刷新数据
                        fetchBooks();
                        fetchCategories();
                        fetchPlatforms();
                    } catch (error) {
                        if (error.response?.data?.detail) {
                            ElMessage.error(error.response.data.detail);
                        } else if (error.name === 'SyntaxError') {
                            ElMessage.error('备份文件格式错误，不是有效的 JSON 文件');
                        } else if (error !== 'cancel') {
                            ElMessage.error('导入备份失败，请检查文件格式');
                        }
                        console.error(error);
                        event.target.value = '';
                    }
                };

                // 封面上传前校验
                const beforeCoverUpload = (file) => {
                    const isImage = file.type.startsWith('image/');
                    const isLt5M = file.size / 1024 / 1024 < 5;
                    if (!isImage) {
                        ElMessage.error('只能上传图片文件！');
                        return false;
                    }
                    if (!isLt5M) {
                        ElMessage.error('图片大小不能超过 5MB！');
                        return false;
                    }
                    return true;
                };

                // 自定义封面上传处理
                const handleCoverUpload = async (options) => {
                    const uploadData = new FormData();
                    uploadData.append('file', options.file);
                    try {
                        const res = await axios.post(`${API_BASE}/upload/cover`, uploadData, {
                            headers: { 'Content-Type': 'multipart/form-data' }
                        });
                        if (showEditDialog.value) {
                            editForm.cover = res.data.url;
                        } else if (showAddDialog.value) {
                            formData.cover = res.data.url;
                        }
                        ElMessage.success('封面上传成功！');
                    } catch (error) {
                        ElMessage.error('封面上传失败');
                    }
                };

                // 辅助函数
                const formatDate = (dateString) => {
                    if (!dateString) return '未知时间';
                    const date = new Date(dateString);
                    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
                };

                const getStatusType = (status) => {
                    // 兼容新旧文案
                    if (status === '已读完' || status === '已听完') return 'success';
                    if (status === '已弃坑') return 'info';
                    return 'warning';
                };

                const getStatusEn = (status) => {
                    // 兼容新旧文案
                    if (status === '已读完' || status === '已听完') return 'completed';
                    if (status === '已弃坑') return 'dropped';
                    return 'reading';
                };

                const getPlatformClass = (platform) => {
                    // 从 platformList 中查找匹配的平台
                    const matched = platformList.value.find(p => p.name === platform);
                    if (!matched) return 'platform-other';
                    // 为已知平台返回对应的 CSS 类名
                    const classMap = {
                        '微信读书': 'platform-wechat',
                        '喜马拉雅': 'platform-ximalaya',
                        '本地文件': 'platform-local',
                        '实体书': 'platform-physical'
                    };
                    return classMap[platform] || 'platform-other';
                };

                const resetForm = () => {
                    formData.title = '';
                    formData.platform = '微信读书';
                    formData.status = '阅读中';
                    formData.startDate = new Date().toISOString().split('T')[0];
                    formData.cover = '';
                    formData.progress = '';
                    formData.notes = '';
                    formData.category = '未分类';
                    formData.rating = 0;
                    formData.read_url = '';  // 需求一：阅读链接
                };

                const handleImageError = (e) => {
                    e.target.style.display = 'none';
                };

                const onSiteIconError = (e) => {
                    e.target.style.display = 'none';
                };

                // ==========================================
                // AI 阅读助手
                // ==========================================
                const showChatWindow = ref(false);
                const chatMessages = ref([]);
                const chatInput = ref('');
                const isChatLoading = ref(false);
                const chatMessagesRef = ref(null);

                const toggleChatWindow = () => {
                    showChatWindow.value = !showChatWindow.value;
                };

                // 滚动到底部
                const scrollChatToBottom = () => {
                    nextTick(() => {
                        if (chatMessagesRef.value) {
                            chatMessagesRef.value.scrollTop = chatMessagesRef.value.scrollHeight;
                        }
                    });
                };

                // 发送消息
                const sendChatMessage = async () => {
                    const userMsg = chatInput.value.trim();
                    if (!userMsg || isChatLoading.value) return;

                    // 添加用户消息到列表
                    chatMessages.value.push({ role: 'user', content: userMsg });
                    chatInput.value = '';
                    isChatLoading.value = true;
                    scrollChatToBottom();

                    try {
                        // 构建历史记录（用于发送给后端）
                        const history = chatMessages.value.slice(0, -1).map(msg => ({
                            role: msg.role === 'ai' ? 'assistant' : msg.role,
                            content: msg.content
                        }));

                        const response = await axios.post(`${API_BASE}/chat`, {
                            message: userMsg,
                            history: history
                        });

                        // 添加 AI 回复到列表
                        chatMessages.value.push({ role: 'ai', content: response.data.reply });

                        // 如果 AI 执行了工具调用（添加新书/更新进度），自动刷新书架数据
                        if (response.data.data_updated) {
                            fetchBooks();
                        }
                    } catch (error) {
                        console.error('AI 聊天请求失败:', error);
                        const errorMsg = error.response?.data?.detail || '抱歉，AI 服务暂时不可用，请稍后再试。';
                        chatMessages.value.push({ role: 'ai', content: `⚠️ ${errorMsg}` });
                    } finally {
                        isChatLoading.value = false;
                        scrollChatToBottom();
                    }
                };

                onMounted(() => {
                    // 先获取系统设置（包括自定义名称、欢迎语、图标）
                    fetchSettings().then(() => {
                        // 更新页面标题
                        document.title = siteSettings.site_name;
                    });
                    if (isAuthenticated.value) {
                        fetchBooks();
                        fetchCategories();
                        fetchPlatforms();
                    }
                });

                // 监听页面切换，当切换到统计看板时重新渲染图表
                watch(currentPage, (newPage) => {
                    if (newPage === 'stats') {
                        nextTick(() => {
                            fetchStats();
                        });
                    }
                });

                return {
                    // 页面切换
                    currentPage,
                    // 密码锁
                    isAuthenticated, authPassword, isAuthLoading, authError, handleAuth, handleLogout,
                    // 书籍数据
                    books, searchQuery, categoryFilter, filteredBooks, availableCategories,
                    totalBooks, readingBooks, completedBooks,
                    // 录入
                    showAddDialog, formData, isSubmitting, handleCheckAndSubmit, resetForm,
                    // 时间轴
                    showTimeline, currentBookTitle, currentBookInfo, currentLogs, openTimeline, deleteLog,
                    // 辅助函数
                    formatDate, getStatusType, getPlatformClass, getStatusEn, handleImageError, fetchBooks,
                    // 编辑书籍
                    showEditDialog, isEditing, editForm, openEditDialog, handleEditSubmit,
                    // 需求二：快捷更新进度
                    quickUpdateProgress,
                    // 编辑阅读记录
                    showEditLogDialog, isEditingLog, editLogForm, openEditLogDialog, handleEditLogSubmit,
                    // 封面上传
                    handleCoverUpload, beforeCoverUpload,
                    // 分类筛选
                    onCategoryFilterChange,
                    // 导出/导入
                    handleExport, importFileInput, triggerImport, handleImport,
                    // 分类管理
                    showCategoryDialog, categoryList, newCategoryName, newCategoryIcon, isAddingCategory, emojiList,
                    fetchCategories, openCategoryManager, handleAddCategory, handleDeleteCategory,
                    updateCategoryIcon, openIconPicker, getCategoryIcon,
                    // 图标选择器
                    showIconPickerDialog, editingCategory, editingCategoryIcon, confirmCategoryIcon,
                    // 平台管理
                    showPlatformDialog, platformList, newPlatformName, isAddingPlatform,
                    fetchPlatforms, openPlatformManager, handleAddPlatform, handleDeletePlatform,
                    // 系统设置
                    siteSettings, showSettingsDialog, isSavingSettings, settingsActiveTab, settingsForm,
                    openSettingsDialog, handleSaveSettings, handleSettingsIconUpload, onSiteIconError,
                    // AI 服务商选择
                    aiProviderPresets, currentProviderPreset, onAiProviderChange,
                    // 修改密码
                    showChangePasswordDialog, isChangingPassword, changePasswordForm, handleChangePassword,
                    // 设置下拉菜单 & 夜间模式
                    isDarkMode, handleSettingsCommand,
                    // AI 阅读助手
                    showChatWindow, chatMessages, chatInput, isChatLoading, chatMessagesRef,
                    toggleChatWindow, sendChatMessage,
                    // 阅读统计看板
                    statsSummary
                };
            }
        });

        // 安全注册图标组件
        try {
            if (window.ElementPlusIconsVue) {
                for (const [key, component] of Object.entries(window.ElementPlusIconsVue)) {
                    app.component(key, component);
                }
            }
        } catch (e) {
            console.warn('图标注册失败，部分图标可能无法显示:', e);
        }

        app.use(ElementPlus, { locale: ElementPlusLocaleZhCn });
        
        // 使用错误边界挂载应用，防止渲染错误导致白屏
        let vm;
        try {
            vm = app.mount('#app');
        } catch (e) {
            console.error('Vue 应用挂载失败:', e);
            // 降级显示：直接显示基本内容
            document.getElementById('app').innerHTML = '<div style="padding:40px;text-align:center;"><h2>加载失败</h2><p>应用初始化出错，请刷新页面重试</p><button onclick="location.reload()" style="padding:8px 24px;border-radius:8px;border:none;background:#4f46e5;color:white;font-size:16px;cursor:pointer;">刷新页面</button></div>';
        }
// 暴露 Vue 实例到全局，供 Axios 拦截器使用
window.__vueApp__ = vm;