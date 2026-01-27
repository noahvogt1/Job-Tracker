/**
 * Settings Page JavaScript
 */

const Settings = {
    preferences: {},
    originalPreferences: {},

    async init() {
        await this.loadPreferences();
        this.setupEventListeners();
        this.loadUserInfo();
    },

    async loadPreferences() {
        try {
            const apiCall = window.JobTracker?.apiCall || (async () => { throw new Error('JobTracker not available'); });
            this.preferences = await apiCall('/settings/preferences');
            this.originalPreferences = { ...this.preferences };
            this.applyPreferences();
        } catch (error) {
            console.error('Failed to load preferences:', error);
            if (error.message.includes('401') || error.message.includes('session')) {
                window.location.href = '/login.html';
            }
        }
    },

    applyPreferences() {
        // Apply theme
        const theme = this.preferences.theme || localStorage.getItem('theme') || 'light';
        this.setTheme(theme);
        
        // Apply default view
        const defaultView = this.preferences.default_view || 'kanban';
        const viewSelect = document.getElementById('default-view');
        if (viewSelect) {
            viewSelect.value = defaultView;
        }
        
        // Apply items per page
        const itemsPerPage = this.preferences.items_per_page || 25;
        const itemsSelect = document.getElementById('items-per-page');
        if (itemsSelect) {
            itemsSelect.value = itemsPerPage;
        }
        
        // Apply notifications
        const notificationsEnabled = this.preferences.notifications_enabled !== false;
        const notificationsCheckbox = document.getElementById('notifications-enabled');
        if (notificationsCheckbox) {
            notificationsCheckbox.checked = notificationsEnabled;
        }
        
        // Apply email digest
        const emailDigest = this.preferences.email_digest_frequency || 'weekly';
        const emailDigestSelect = document.getElementById('email-digest');
        if (emailDigestSelect) {
            emailDigestSelect.value = emailDigest;
        }
        
        // Apply auto-refresh
        const autoRefresh = this.preferences.auto_refresh || false;
        const autoRefreshCheckbox = document.getElementById('auto-refresh');
        if (autoRefreshCheckbox) {
            autoRefreshCheckbox.checked = autoRefresh;
            this.toggleRefreshInterval(autoRefresh);
        }
        
        // Apply refresh interval
        const refreshInterval = this.preferences.auto_refresh_interval || 300;
        const refreshIntervalInput = document.getElementById('refresh-interval');
        if (refreshIntervalInput) {
            refreshIntervalInput.value = refreshInterval;
        }
    },

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // Update radio buttons and selected state
        document.querySelectorAll('input[name="theme"]').forEach(radio => {
            radio.checked = radio.value === theme;
            const option = radio.closest('.theme-option');
            if (option) {
                if (radio.checked) {
                    option.classList.add('selected');
                } else {
                    option.classList.remove('selected');
                }
            }
        });
    },

    setupEventListeners() {
        // Theme selection - handle both label click and radio change
        document.querySelectorAll('input[name="theme"]').forEach(radio => {
            radio.addEventListener('change', (e) => {
                this.setTheme(e.target.value);
            });
        });
        
        // Also handle clicking the theme option label
        document.querySelectorAll('.theme-option').forEach(option => {
            option.addEventListener('click', (e) => {
                // Only handle if not clicking the radio directly
                if (e.target.type !== 'radio') {
                    const radio = option.querySelector('input[type="radio"]');
                    if (radio) {
                        radio.checked = true;
                        radio.dispatchEvent(new Event('change'));
                    }
                }
            });
        });
        
        // Auto-refresh toggle
        const autoRefreshCheckbox = document.getElementById('auto-refresh');
        if (autoRefreshCheckbox) {
            autoRefreshCheckbox.addEventListener('change', (e) => {
                this.toggleRefreshInterval(e.target.checked);
            });
        }
        
        // Save button
        const saveBtn = document.getElementById('save-settings');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.saveSettings());
        }
        
        // Reset button
        const resetBtn = document.getElementById('reset-settings');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetSettings());
        }
    },

    toggleRefreshInterval(enabled) {
        const intervalGroup = document.getElementById('refresh-interval-group');
        if (intervalGroup) {
            intervalGroup.style.display = enabled ? 'block' : 'none';
        }
    },

    async saveSettings() {
        try {
            const apiCall = window.JobTracker?.apiCall || (async () => { throw new Error('JobTracker not available'); });
            const showNotification = window.JobTracker?.showNotification || (() => {});
            const updates = {
                theme: document.querySelector('input[name="theme"]:checked')?.value || 'light',
                default_view: document.getElementById('default-view').value,
                items_per_page: parseInt(document.getElementById('items-per-page').value),
                notifications_enabled: document.getElementById('notifications-enabled').checked,
                email_digest_frequency: document.getElementById('email-digest').value,
                auto_refresh: document.getElementById('auto-refresh').checked,
                auto_refresh_interval: parseInt(document.getElementById('refresh-interval').value) || 300
            };
            
            const saved = await apiCall('/settings/preferences', {
                method: 'PATCH',
                body: JSON.stringify(updates)
            });
            
            this.preferences = saved;
            this.originalPreferences = { ...saved };
            
            showNotification('Settings saved successfully', 'success');
        } catch (error) {
            console.error('Failed to save settings:', error);
            const showNotification = window.JobTracker?.showNotification || (() => {});
            showNotification('Failed to save settings', 'error');
        }
    },

    async resetSettings() {
        if (!confirm('Are you sure you want to reset all settings to defaults?')) {
            return;
        }
        
        try {
            const apiCall = window.JobTracker?.apiCall || (async () => { throw new Error('JobTracker not available'); });
            const showNotification = window.JobTracker?.showNotification || (() => {});
            const defaults = {
                theme: 'light',
                default_view: 'kanban',
                items_per_page: 25,
                notifications_enabled: true,
                email_digest_frequency: 'weekly',
                auto_refresh: false,
                auto_refresh_interval: 300
            };
            
            const saved = await apiCall('/settings/preferences', {
                method: 'PATCH',
                body: JSON.stringify(defaults)
            });
            
            this.preferences = saved;
            this.applyPreferences();
            
            showNotification('Settings reset to defaults', 'success');
        } catch (error) {
            console.error('Failed to reset settings:', error);
            const showNotification = window.JobTracker?.showNotification || (() => {});
            showNotification('Failed to reset settings', 'error');
        }
    },

    async loadUserInfo() {
        try {
            const apiCall = window.JobTracker?.apiCall || (async () => { throw new Error('JobTracker not available'); });
            const userInfo = await apiCall('/auth/me');
            if (userInfo) {
                const usernameDisplay = document.getElementById('username-display');
                const emailDisplay = document.getElementById('email-display');
                const createdAtDisplay = document.getElementById('created-at-display');
                
                if (usernameDisplay) {
                    usernameDisplay.textContent = userInfo.username || '-';
                }
                if (emailDisplay) {
                    emailDisplay.textContent = userInfo.email || '-';
                }
                if (createdAtDisplay && userInfo.created_at) {
                    const date = new Date(userInfo.created_at);
                    createdAtDisplay.textContent = date.toLocaleDateString('en-US', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric'
                    });
                }
            }
        } catch (error) {
            console.error('Failed to load user info:', error);
        }
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    Settings.init();
});
