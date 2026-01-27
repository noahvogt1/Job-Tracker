/**
 * Notification management JavaScript
 */

const Notifications = {
    unreadCount: 0,
    notifications: [],

    async load() {
        try {
            const notifications = await apiCall('/notifications?unread_only=true&limit=10');
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
                    <h4>${n.title}</h4>
                    <p>${n.message}</p>
                    <span class="notification-time">${this.formatTime(n.created_at)}</span>
                </div>
                ${!n.read ? `<button class="notification-mark-read" onclick="Notifications.markRead(${n.notification_id})">Mark read</button>` : ''}
            </div>
        `).join('');
    },

    async markRead(notificationId) {
        try {
            await apiCall(`/notifications/${notificationId}/read`, { method: 'PUT' });
            await this.load();
        } catch (error) {
            console.error('Failed to mark read:', error);
        }
    },

    async markAllRead() {
        try {
            await apiCall('/notifications/read-all', { method: 'PUT' });
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

// Initialize notifications on page load
document.addEventListener('DOMContentLoaded', () => {
    // Check if user is logged in
    const token = localStorage.getItem('session_token');
    if (token) {
        Notifications.load();
        // Refresh notifications every 30 seconds
        setInterval(() => Notifications.load(), 30000);
    }
});
