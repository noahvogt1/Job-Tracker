/**
 * Notification management JavaScript
 */

const Notifications = {
    unreadCount: 0,
    notifications: [],
    _pollIntervalId: null,
    _pollIntervalActiveMs: 30000,
    _pollIntervalInactiveMs: 120000,

    async load() {
        try {
            const notifications = await JobTracker.apiCall('/notifications?unread_only=true&limit=10');
            this.notifications = notifications;
            this.unreadCount = notifications.length;
            this.render();
            this.updateBadge();
        } catch (error) {
            console.error('Failed to load notifications:', error);
            if (error.message.includes('401') || error.message.includes('session')) {
                // Not logged in, hide notifications
                this.hideNotifications();
            }
        }
    },

    render() {
        const container = document.getElementById('notifications-container');
        if (!container) return;
        
        if (this.notifications.length === 0) {
            container.innerHTML = '<div class="notification-empty">No new notifications</div>';
            return;
        }
        
        container.innerHTML = this.notifications.map(n => `
            <div class="notification ${n.read ? 'read' : 'unread'}" data-id="${n.notification_id}">
                <div class="notification-content">
                    <h4>${JobTracker.escapeHtml ? JobTracker.escapeHtml(n.title) : n.title}</h4>
                    <p>${JobTracker.escapeHtml ? JobTracker.escapeHtml(n.message) : n.message}</p>
                    <span class="notification-time">${this.formatTime(n.created_at)}</span>
                </div>
                ${!n.read ? `<button class="notification-mark-read" onclick="Notifications.markRead(${n.notification_id})">Mark read</button>` : ''}
            </div>
        `).join('');
    },

    async markRead(notificationId) {
        try {
            await JobTracker.apiCall(`/notifications/${notificationId}/read`, { method: 'PUT' });
            await this.load();
        } catch (error) {
            console.error('Failed to mark read:', error);
        }
    },

    async markAllRead() {
        try {
            await JobTracker.apiCall('/notifications/read-all', { method: 'PUT' });
            await this.load();
        } catch (error) {
            console.error('Failed to mark all read:', error);
        }
    },

    updateBadge() {
        const badge = document.getElementById('notification-badge');
        if (badge) {
            if (this.unreadCount > 0) {
                badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
    },

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        const seconds = Math.floor(diff / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (days > 0) return `${days} day${days > 1 ? 's' : ''} ago`;
        if (hours > 0) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        if (minutes > 0) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        return 'Just now';
    },

    hideNotifications() {
        const bell = document.getElementById('notification-bell');
        if (bell) {
            bell.style.display = 'none';
        }
    },

    toggleDropdown() {
        const dropdown = document.getElementById('notification-dropdown');
        if (dropdown) {
            dropdown.classList.toggle('active');
        }
    },

    _startPolling(intervalMs) {
        if (this._pollIntervalId) {
            clearInterval(this._pollIntervalId);
        }
        this._pollIntervalId = setInterval(() => this.load(), intervalMs);
    },

    init() {
        // Only load notifications for authenticated users
        if (!(window.JobTracker && window.JobTracker.isAuthenticated && window.JobTracker.isAuthenticated())) {
            const bell = document.getElementById('notification-bell');
            if (bell) {
                bell.style.display = 'none';
            }
            return;
        }

        const bell = document.getElementById('notification-bell');
        if (bell) {
            bell.style.display = 'inline-flex';
        }

        // Initial load
        this.load();

        // Poll more frequently when tab is active, back off when inactive
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible') {
                this._startPolling(this._pollIntervalActiveMs);
            } else {
                this._startPolling(this._pollIntervalInactiveMs);
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);
        handleVisibilityChange();
    }
};

// Close dropdown when clicking outside
document.addEventListener('click', (e) => {
    const bell = document.getElementById('notification-bell');
    const dropdown = document.getElementById('notification-dropdown');
    if (bell && dropdown && !bell.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.classList.remove('active');
    }
});

// Make Notifications available globally
window.Notifications = Notifications;

// Initialize notifications on page load
document.addEventListener('DOMContentLoaded', () => {
    Notifications.init();
});
