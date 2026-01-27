/**
 * Job Tracker - Main JavaScript Application
 * 
 * Provides API communication utilities and shared functionality
 * across all pages of the application.
 */

// API base URL
const API_BASE = '/api';

// ============================================================================
// API Communication
// ============================================================================

/**
 * Make an API call with automatic authentication and error handling.
 * 
 * @param {string} endpoint - API endpoint (e.g., '/health', '/jobs')
 * @param {object} options - Fetch options (method, body, headers, etc.)
 * @returns {Promise<any>} - Parsed JSON response
 * @throws {Error} - If the API call fails
 */
async function apiCall(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };
    
    // Add auth token if available
    const token = localStorage.getItem('session_token');
    if (token) {
        defaultOptions.headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Merge options
    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {}),
        },
    };
    
    try {
        const response = await fetch(url, finalOptions);
        
        // Handle non-JSON responses
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            if (!response.ok) {
                throw new Error(`API error: ${response.status} ${response.statusText}`);
            }
            return await response.text();
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            // Handle validation errors (422) with more detail
            if (response.status === 422 && data.detail) {
                let errorMessage = 'Validation error: ';
                if (Array.isArray(data.detail)) {
                    // Pydantic validation errors
                    const errors = data.detail.map(err => {
                        const field = err.loc ? err.loc.join('.') : 'field';
                        return `${field}: ${err.msg}`;
                    }).join(', ');
                    errorMessage += errors;
                } else {
                    errorMessage += data.detail;
                }
                throw new Error(errorMessage);
            }
            throw new Error(data.detail || `API error: ${response.status}`);
        }
        
        return data;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

/**
 * Check if user is authenticated.
 * @returns {boolean}
 */
function isAuthenticated() {
    return !!localStorage.getItem('session_token');
}

/**
 * Get current user ID from token (if available).
 * Note: This is a placeholder - in a real app, you'd decode the JWT
 * or make an API call to get user info.
 * @returns {number|null}
 */
function getCurrentUserId() {
    const userId = localStorage.getItem('user_id');
    return userId ? parseInt(userId, 10) : null;
}

/**
 * Store authentication token.
 * @param {string} token - Session token
 * @param {object} userInfo - User information object
 */
function setAuthToken(token, userInfo = null) {
    localStorage.setItem('session_token', token);
    if (userInfo && userInfo.user_id) {
        localStorage.setItem('user_id', userInfo.user_id.toString());
    }
}

/**
 * Clear authentication token.
 */
function clearAuthToken() {
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_id');
}

/**
 * Format a date for display.
 * @param {string|Date} date - Date to format
 * @param {object} options - Intl.DateTimeFormat options
 * @returns {string}
 */
function formatDate(date, options = {}) {
    if (!date) return 'N/A';
    
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
    };
    
    try {
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        return new Intl.DateTimeFormat('en-US', { ...defaultOptions, ...options }).format(dateObj);
    } catch (error) {
        return 'Invalid Date';
    }
}

/**
 * Format a datetime for display.
 * @param {string|Date} datetime - Datetime to format
 * @returns {string}
 */
function formatDateTime(datetime) {
    if (!datetime) return 'N/A';
    
    try {
        const dateObj = typeof datetime === 'string' ? new Date(datetime) : datetime;
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        }).format(dateObj);
    } catch (error) {
        return 'Invalid Date';
    }
}

/**
 * Show a notification/toast message.
 * @param {string} message - Message to display
 * @param {string} type - 'success', 'error', 'info', 'warning'
 * @param {number} duration - Duration in milliseconds
 */
function showNotification(message, type = 'info', duration = 3000) {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${type === 'error' ? '#ef4444' : type === 'success' ? '#10b981' : '#3b82f6'};
        color: white;
        border-radius: 0.5rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
    `;
    
    document.body.appendChild(notification);
    
    // Remove after duration
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, duration);
}

// Add CSS animations for notifications
if (!document.getElementById('notification-styles')) {
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

/**
 * Debounce function to limit how often a function is called.
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function}
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Load theme from localStorage or user preferences
 */
async function loadTheme() {
    // Check localStorage first for immediate application
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
    }
    
    // If authenticated, try to load from user preferences
    if (isAuthenticated()) {
        try {
            const prefs = await apiCall('/settings/preferences');
            if (prefs.theme) {
                document.documentElement.setAttribute('data-theme', prefs.theme);
                localStorage.setItem('theme', prefs.theme);
            }
        } catch (error) {
            // If settings endpoint doesn't exist yet, that's okay
            console.debug('Settings endpoint not available:', error);
        }
    }
}

/**
 * Initialize common functionality when DOM is ready.
 */
document.addEventListener('DOMContentLoaded', async () => {
    // Load theme first
    await loadTheme();
    
    // Check API health on page load
    try {
        const health = await apiCall('/health');
        console.log('API connected:', health);
    } catch (error) {
        console.error('Failed to connect to API:', error);
        showNotification('Unable to connect to API. Some features may not work.', 'error', 5000);
    }
    
    // Update navigation based on auth status
    updateNavigation();
});

/**
 * Update navigation to show login/logout based on auth status.
 */
async function updateNavigation() {
    const navAuth = document.getElementById('nav-auth');
    if (!navAuth) return;
    
    // Check auth status
    let authenticated = false;
    let userInfo = null;
    
    try {
        const authCheck = await apiCall('/auth/check');
        authenticated = authCheck.authenticated;
        if (authenticated && authCheck.user_id) {
            try {
                userInfo = await apiCall('/auth/me');
            } catch (error) {
                // If /auth/me fails, clear token
                clearAuthToken();
                authenticated = false;
            }
        }
    } catch (error) {
        // If check fails, assume not authenticated
        authenticated = false;
    }
    
    if (authenticated && userInfo) {
        navAuth.innerHTML = `
            <span style="color: rgba(255,255,255,0.9); margin-right: 1rem;">${escapeHtml(userInfo.username)}</span>
            <button class="btn btn-secondary" id="logout-btn">Logout</button>
        `;
        
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', async () => {
                try {
                    await apiCall('/auth/logout', { method: 'POST' });
                } catch (error) {
                    console.error('Logout error:', error);
                }
                clearAuthToken();
                updateNavigation();
                window.location.href = '/';
            });
        }
    } else {
        navAuth.innerHTML = `
            <a href="/login.html" class="btn btn-primary">Login</a>
        `;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Icon Utilities
// ============================================================================

/**
 * Heroicons SVG paths (24x24 outline style)
 */
const ICONS = {
    documentText: '<path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />',
    calendar: '<path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />',
    gift: '<path stroke-linecap="round" stroke-linejoin="round" d="M21 11.25v8.25a1.5 1.5 0 01-1.5 1.5H5.25a1.5 1.5 0 01-1.5-1.5v-8.25M12 4.875A2.625 2.625 0 109.375 7.5H12m0-2.625V7.5m0 0V9.75m0-2.625A2.625 2.625 0 1114.625 7.5H12m-8.25 3.75h16.5" />',
    chartBar: '<path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C19.996 3 20.5 3.504 20.5 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />',
    briefcase: '<path stroke-linecap="round" stroke-linejoin="round" d="M20.25 14.15v4.25c0 .414-.336.75-.75.75h-4.5a.75.75 0 01-.75-.75v-4.25m0 0h-9m9 0V9.375c0-.621-.504-1.125-1.125-1.125h-9.75c-.621 0-1.125.504-1.125 1.125v4.875m9 0H8.25m9 0H18m.75-9H5.625c-.621 0-1.125.504-1.125 1.125v9.75c0 .621.504 1.125 1.125 1.125H18m.75-9v-1.5c0-.621-.504-1.125-1.125-1.125h-9.75c-.621 0-1.125.504-1.125 1.125v1.5m9 0H18" />',
    star: '<path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />',
    buildingOffice: '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 21h19.5m-18-18v18m10.5-18v18m6-13.5V21M6.75 6.75h.75m-.75 3h.75m-.75 3h.75m3-6h.75m-.75 3h.75m-.75 3h.75M6.75 21v-3.375c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21M3 3h12m-.75 4.5H21m-3.75 3.75h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008zm0 3h.008v.008h-.008v-.008z" />',
    chartPie: '<path stroke-linecap="round" stroke-linejoin="round" d="M10.5 6a7.5 7.5 0 107.5 7.5h-7.5V6z" /><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 10.5H21A7.5 7.5 0 0013.5 3v7.5z" />',
    eye: '<path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />',
    xCircle: '<path stroke-linecap="round" stroke-linejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />',
    arrowPath: '<path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />',
    inbox: '<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 13.5h3.86a2.25 2.25 0 012.012 1.423l.883 2.927a2.25 2.25 0 002.013 1.423h2.14a2.25 2.25 0 002.013-1.423l.883-2.927a2.25 2.25 0 012.013-1.423h3.86m-7.5 0V18a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0021.75 18v-4.5m-15 0V6a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121.75 6v4.5" />',
    lockClosed: '<path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />',
    checkCircle: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />',
};

/**
 * Render an icon as SVG
 * @param {string} iconName - Name of the icon
 * @param {object} options - Options for the icon (size, class, color)
 * @returns {string} SVG HTML string
 */
function renderIcon(iconName, options = {}) {
    const size = options.size || 24;
    const className = options.class || '';
    const color = options.color || 'currentColor';
    const path = ICONS[iconName];
    
    if (!path) {
        console.warn(`Icon "${iconName}" not found`);
        return '';
    }
    
    return `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="${color}" class="${className}" width="${size}" height="${size}">${path}</svg>`;
}

// Export functions for use in other scripts
window.JobTracker = {
    apiCall,
    isAuthenticated,
    getCurrentUserId,
    setAuthToken,
    clearAuthToken,
    formatDate,
    formatDateTime,
    showNotification,
    debounce,
    updateNavigation,
    renderIcon,
    loadTheme,
};
