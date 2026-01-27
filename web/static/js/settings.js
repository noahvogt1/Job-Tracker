/**
 * Settings Page JavaScript
 */

const Settings = {
    preferences: {},
    originalPreferences: {},
    notificationPreferences: {},

    async init() {
        await this.loadPreferences();
        this.setupEventListeners();
        this.loadUserInfo();
        await this.loadDocuments();
    },

    async loadPreferences() {
        try {
            if (!window.JobTracker || !window.JobTracker.apiCall) {
                throw new Error('JobTracker not available');
            }
            this.preferences = await window.JobTracker.apiCall('/settings/preferences');
            this.originalPreferences = { ...this.preferences };
            this.applyPreferences();

            // Load notification-specific preferences as well
            this.notificationPreferences = await window.JobTracker.apiCall('/notifications/preferences');
            this.applyNotificationPreferences();
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
        
        // Apply high-level notifications toggle
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

        // After applying server preferences, no unsaved changes yet for main settings
        this.setDirty(false);
    },

    applyNotificationPreferences() {
        const prefs = this.notificationPreferences || {};
        const setChecked = (id, value, fallback = true) => {
            const el = document.getElementById(id);
            if (el) {
                el.checked = value !== undefined ? Boolean(value) : fallback;
            }
        };

        setChecked('notify-job-alerts', prefs.job_alerts);
        setChecked('notify-status-changes', prefs.status_changes);
        setChecked('notify-reminders', prefs.reminders);
        setChecked('notify-deadlines', prefs.deadlines);
        setChecked('notify-weekly-digest', prefs.weekly_digest);
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
            
            // Hover preview - temporarily apply theme on hover
            let hoverTimeout;
            option.addEventListener('mouseenter', () => {
                const theme = option.dataset.theme;
                if (theme) {
                    hoverTimeout = setTimeout(() => {
                        // Store current theme
                        const currentTheme = document.documentElement.getAttribute('data-theme');
                        option.dataset.originalTheme = currentTheme || 'light';
                        // Apply preview theme
                        document.documentElement.setAttribute('data-theme', theme);
                    }, 150); // Small delay to avoid accidental previews
                }
            });
            
            option.addEventListener('mouseleave', () => {
                if (hoverTimeout) {
                    clearTimeout(hoverTimeout);
                }
                // Restore original theme
                const originalTheme = option.dataset.originalTheme || 'light';
                const currentRadio = document.querySelector('input[name="theme"]:checked');
                if (currentRadio) {
                    document.documentElement.setAttribute('data-theme', currentRadio.value);
                } else {
                    document.documentElement.setAttribute('data-theme', originalTheme);
                }
                delete option.dataset.originalTheme;
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

        // Mark form as dirty when any setting changes
        const markDirty = () => this.setDirty(true);
        document.querySelectorAll('#default-view, #items-per-page, #notifications-enabled, #email-digest, #auto-refresh, #refresh-interval, #notify-job-alerts, #notify-status-changes, #notify-reminders, #notify-deadlines, #notify-weekly-digest')
            .forEach(el => {
                el.addEventListener('change', markDirty);
                el.addEventListener('input', markDirty);
            });
        document.querySelectorAll('input[name="theme"]').forEach(radio => {
            radio.addEventListener('change', markDirty);
        });
    },

    toggleRefreshInterval(enabled) {
        const intervalGroup = document.getElementById('refresh-interval-group');
        if (intervalGroup) {
            intervalGroup.style.display = enabled ? 'block' : 'none';
        }
    },

    setDirty(isDirty) {
        this.dirty = isDirty;
        const saveBtn = document.getElementById('save-settings');
        const indicator = document.getElementById('unsaved-indicator');
        if (saveBtn) {
            saveBtn.disabled = !isDirty;
        }
        if (indicator) {
            indicator.style.display = isDirty ? 'flex' : 'none';
        }
    },

    async saveSettings() {
        try {
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
            
            const saved = await window.JobTracker.apiCall('/settings/preferences', {
                method: 'PATCH',
                body: JSON.stringify(updates)
            });
            
            this.preferences = saved;
            this.originalPreferences = { ...saved };

            // Persist notification type preferences
            try {
                await window.JobTracker.apiCall('/notifications/preferences', {
                    method: 'PUT',
                    body: JSON.stringify({
                        job_alerts: document.getElementById('notify-job-alerts').checked,
                        status_changes: document.getElementById('notify-status-changes').checked,
                        reminders: document.getElementById('notify-reminders').checked,
                        deadlines: document.getElementById('notify-deadlines').checked,
                        weekly_digest: document.getElementById('notify-weekly-digest').checked,
                    })
                });
            } catch (e) {
                console.error('Failed to update notification preferences:', e);
            }
            
            showNotification('Settings saved successfully', 'success');
            this.setDirty(false);
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
            
            const saved = await window.JobTracker.apiCall('/settings/preferences', {
                method: 'PATCH',
                body: JSON.stringify(defaults)
            });
            
            this.preferences = saved;
            this.applyPreferences();
            
            showNotification('Settings reset to defaults', 'success');
            this.setDirty(false);
        } catch (error) {
            console.error('Failed to reset settings:', error);
            const showNotification = window.JobTracker?.showNotification || (() => {});
            showNotification('Failed to reset settings', 'error');
        }
    },

    async loadUserInfo() {
        try {
            if (!window.JobTracker || !window.JobTracker.apiCall) {
                throw new Error('JobTracker not available');
            }
            const userInfo = await window.JobTracker.apiCall('/auth/me');
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
    },

    async loadDocuments() {
        try {
            // Load resumes
            const resumes = await window.JobTracker.apiCall('/documents/resumes');
            this.renderResumes(resumes);
            
            // Load cover letters
            const coverLetters = await window.JobTracker.apiCall('/documents/cover-letters');
            this.renderCoverLetters(coverLetters);
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    },

    renderResumes(resumes) {
        const container = document.getElementById('resumes-list');
        if (!container) return;
        
        if (resumes.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary);">No resumes added yet.</p>';
            return;
        }
        
        container.innerHTML = resumes.map(resume => `
            <div class="document-item" style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; background: var(--background); border-radius: var(--radius-md); margin-bottom: 0.5rem;">
                <div>
                    <strong>${window.JobTracker.escapeHtml(resume.name)}</strong>
                    ${resume.is_default ? '<span class="badge" style="margin-left: 0.5rem; font-size: 0.75rem;">Default</span>' : ''}
                    ${resume.version ? `<span style="color: var(--text-secondary); font-size: 0.875rem;"> - ${window.JobTracker.escapeHtml(resume.version)}</span>` : ''}
                </div>
                <div>
                    <button class="btn btn-secondary btn-sm" onclick="Settings.setDefaultResume(${resume.resume_id})" ${resume.is_default ? 'disabled' : ''}>Set Default</button>
                    <button class="btn btn-secondary btn-sm" onclick="Settings.deleteResume(${resume.resume_id})">Delete</button>
                </div>
            </div>
        `).join('');
    },

    renderCoverLetters(coverLetters) {
        const container = document.getElementById('cover-letters-list');
        if (!container) return;
        
        if (coverLetters.length === 0) {
            container.innerHTML = '<p style="color: var(--text-secondary);">No cover letters added yet.</p>';
            return;
        }
        
        container.innerHTML = coverLetters.map(cl => `
            <div class="document-item" style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; background: var(--background); border-radius: var(--radius-md); margin-bottom: 0.5rem;">
                <div>
                    <strong>${window.JobTracker.escapeHtml(cl.name)}</strong>
                    ${cl.is_default ? '<span class="badge" style="margin-left: 0.5rem; font-size: 0.75rem;">Default</span>' : ''}
                    ${cl.version ? `<span style="color: var(--text-secondary); font-size: 0.875rem;"> - ${window.JobTracker.escapeHtml(cl.version)}</span>` : ''}
                </div>
                <div>
                    <button class="btn btn-secondary btn-sm" onclick="Settings.editCoverLetter(${cl.cover_letter_id})">Edit</button>
                    <button class="btn btn-secondary btn-sm" onclick="Settings.setDefaultCoverLetter(${cl.cover_letter_id})" ${cl.is_default ? 'disabled' : ''}>Set Default</button>
                    <button class="btn btn-secondary btn-sm" onclick="Settings.deleteCoverLetter(${cl.cover_letter_id})">Delete</button>
                </div>
            </div>
        `).join('');
    },

    async setDefaultResume(resumeId) {
        try {
            await window.JobTracker.apiCall(`/documents/resumes/${resumeId}`, {
                method: 'PUT',
                body: JSON.stringify({ is_default: true })
            });
            await this.loadDocuments();
            window.JobTracker.showNotification('Default resume updated', 'success');
        } catch (error) {
            console.error('Failed to set default resume:', error);
            window.JobTracker.showNotification('Failed to update default resume', 'error');
        }
    },

    async deleteResume(resumeId) {
        if (!confirm('Are you sure you want to delete this resume?')) return;
        try {
            await window.JobTracker.apiCall(`/documents/resumes/${resumeId}`, { method: 'DELETE' });
            await this.loadDocuments();
            window.JobTracker.showNotification('Resume deleted', 'success');
        } catch (error) {
            console.error('Failed to delete resume:', error);
            window.JobTracker.showNotification('Failed to delete resume', 'error');
        }
    },

    async setDefaultCoverLetter(coverLetterId) {
        try {
            await window.JobTracker.apiCall(`/documents/cover-letters/${coverLetterId}`, {
                method: 'PUT',
                body: JSON.stringify({ is_default: true })
            });
            await this.loadDocuments();
            window.JobTracker.showNotification('Default cover letter updated', 'success');
        } catch (error) {
            console.error('Failed to set default cover letter:', error);
            window.JobTracker.showNotification('Failed to update default cover letter', 'error');
        }
    },

    async deleteCoverLetter(coverLetterId) {
        if (!confirm('Are you sure you want to delete this cover letter?')) return;
        try {
            await window.JobTracker.apiCall(`/documents/cover-letters/${coverLetterId}`, { method: 'DELETE' });
            await this.loadDocuments();
            window.JobTracker.showNotification('Cover letter deleted', 'success');
        } catch (error) {
            console.error('Failed to delete cover letter:', error);
            window.JobTracker.showNotification('Failed to delete cover letter', 'error');
        }
    },

    editCoverLetter(coverLetterId) {
        // Simple prompt for now - could be enhanced with a modal
        const name = prompt('Enter cover letter name:');
        if (!name) return;
        
        const content = prompt('Enter cover letter content (or leave empty):');
        
        window.JobTracker.apiCall(`/documents/cover-letters/${coverLetterId}`, {
            method: 'PUT',
            body: JSON.stringify({ name, content: content || null })
        }).then(() => {
            this.loadDocuments();
            window.JobTracker.showNotification('Cover letter updated', 'success');
        }).catch(error => {
            console.error('Failed to update cover letter:', error);
            window.JobTracker.showNotification('Failed to update cover letter', 'error');
        });
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    Settings.init();
});
