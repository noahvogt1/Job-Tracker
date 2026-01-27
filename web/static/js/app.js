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
 * Currently checks for a session token in storage; once
 * httpOnly cookies are used in production this will be
 * updated to consult cookie-based session state instead.
 * @returns {boolean}
 */
function isAuthenticated() {
    // Prefer cookie-based token when available (future-friendly)
    const cookieToken = document.cookie
        .split('; ')
        .find(row => row.startsWith('session_token='));
    if (cookieToken) {
        return true;
    }
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
 * For now this stores the token in localStorage for compatibility.
 * When the backend moves to httpOnly cookies, this can become a
 * no-op for production while still supporting local dev tokens.
 * @param {string} token - Session token
 * @param {object} userInfo - User information object
 */
function setAuthToken(token, userInfo = null) {
    if (token) {
        localStorage.setItem('session_token', token);
    }
    if (userInfo && userInfo.user_id) {
        localStorage.setItem('user_id', userInfo.user_id.toString());
    }
}

/**
 * Clear authentication token from client-visible storage.
 * Once httpOnly cookies are used, logout should also rely on
 * server-side session invalidation in addition to this.
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
 * Toast notification queue manager
 */
const ToastManager = {
    container: null,
    notifications: [],
    maxNotifications: 5,
    spacing: 12, // pixels between notifications

    init() {
        // Create notification container if it doesn't exist
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.style.cssText = `
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: ${this.spacing}px;
                max-width: 400px;
                pointer-events: none;
            `;
            document.body.appendChild(this.container);
        }
    },

    add(notification) {
        this.init();
        this.notifications.push(notification);
        this.container.appendChild(notification.element);
        this.updatePositions();
        
        // Remove oldest if we exceed max
        if (this.notifications.length > this.maxNotifications) {
            const oldest = this.notifications.shift();
            oldest.remove();
        }
    },

    remove(notification) {
        const index = this.notifications.indexOf(notification);
        if (index > -1) {
            this.notifications.splice(index, 1);
            notification.element.remove();
            this.updatePositions();
        }
    },

    updatePositions() {
        // Positions are handled by CSS flexbox gap, but we ensure proper stacking
        this.notifications.forEach((notif, index) => {
            notif.element.style.transform = `translateY(0)`;
        });
    }
};

/**
 * Show a notification/toast message with queueing support.
 * @param {string} message - Message to display
 * @param {string} type - 'success', 'error', 'info', 'warning'
 * @param {number} duration - Duration in milliseconds
 * @param {string} actionsHtml - Optional HTML for inline actions (links/buttons)
 */
function showNotification(message, type = 'info', duration = 3000, actionsHtml = '') {
    ToastManager.init();
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `toast-notification toast-${type}`;
    
    const closeBtn = '<button class="toast-close" aria-label="Close notification">&times;</button>';
    
    if (actionsHtml) {
        notification.innerHTML = `
            <div class="toast-content">
                <span class="toast-message">${escapeHtml(message)}</span>
                <span class="toast-actions">${actionsHtml}</span>
            </div>
            ${closeBtn}
        `;
    } else {
        notification.innerHTML = `
            <div class="toast-content">
                <span class="toast-message">${escapeHtml(message)}</span>
            </div>
            ${closeBtn}
        `;
    }
    
    // Add click handler for close button
    const closeButton = notification.querySelector('.toast-close');
    const notificationObj = {
        element: notification,
        remove: () => {
            notification.style.animation = 'toastSlideOut 0.3s ease-out';
            setTimeout(() => {
                ToastManager.remove(notificationObj);
            }, 300);
        }
    };
    
    closeButton.addEventListener('click', () => {
        notificationObj.remove();
    });
    
    // Add to queue
    ToastManager.add(notificationObj);
    
    // Trigger animation
    setTimeout(() => {
        notification.style.animation = 'toastSlideIn 0.3s ease-out';
    }, 10);
    
    // Auto-remove after duration (unless it's an error, which stays longer)
    const autoRemoveDuration = type === 'error' ? Math.max(duration, 5000) : duration;
    setTimeout(() => {
        if (ToastManager.notifications.includes(notificationObj)) {
            notificationObj.remove();
        }
    }, autoRemoveDuration);
}

// Add CSS styles for toast notifications
if (!document.getElementById('toast-notification-styles')) {
    const style = document.createElement('style');
    style.id = 'toast-notification-styles';
    style.textContent = `
        .toast-notification {
            background: var(--surface, #ffffff);
            color: var(--text-primary, #1e293b);
            border-radius: var(--radius-md, 0.5rem);
            padding: 1rem 1.25rem;
            box-shadow: var(--shadow-lg, 0 10px 15px -3px rgba(0, 0, 0, 0.1));
            border: 1px solid var(--border-color, #e2e8f0);
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
            min-width: 300px;
            max-width: 400px;
            pointer-events: auto;
            position: relative;
        }
        
        .toast-success {
            border-left: 4px solid var(--success-color, #10b981);
        }
        
        .toast-error {
            border-left: 4px solid var(--error-color, #ef4444);
        }
        
        .toast-info {
            border-left: 4px solid var(--primary-color, #3b82f6);
        }
        
        .toast-warning {
            border-left: 4px solid var(--warning-color, #f59e0b);
        }
        
        .toast-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }
        
        .toast-message {
            font-size: 0.9375rem;
            line-height: 1.5;
            color: var(--text-primary, #1e293b);
        }
        
        .toast-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.25rem;
        }
        
        .toast-actions a,
        .toast-actions button {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--primary-color, #3b82f6);
            text-decoration: none;
            background: none;
            border: none;
            cursor: pointer;
            padding: 0;
        }
        
        .toast-actions a:hover,
        .toast-actions button:hover {
            text-decoration: underline;
        }
        
        .toast-close {
            background: none;
            border: none;
            color: var(--text-secondary, #64748b);
            font-size: 1.5rem;
            line-height: 1;
            cursor: pointer;
            padding: 0;
            width: 1.5rem;
            height: 1.5rem;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            border-radius: var(--radius-sm, 0.125rem);
            transition: background-color 0.2s, color 0.2s;
        }
        
        .toast-close:hover {
            background: var(--background, #f8fafc);
            color: var(--text-primary, #1e293b);
        }
        
        @keyframes toastSlideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes toastSlideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
        
        @media (max-width: 768px) {
            #toast-container {
                left: 20px;
                right: 20px;
                max-width: none;
            }
            
            .toast-notification {
                min-width: auto;
                max-width: none;
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
 * Initialize responsive mobile navigation (hamburger menu).
 */
function initMobileNav() {
    const navContainer = document.querySelector('.navbar .nav-container');
    const navMenu = document.querySelector('.navbar .nav-menu');
    if (!navContainer || !navMenu) return;

    const toggle = document.createElement('button');
    toggle.className = 'nav-toggle';
    toggle.type = 'button';
    toggle.setAttribute('aria-label', 'Toggle navigation menu');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.innerHTML = '<span class="nav-toggle-bar"></span><span class="nav-toggle-bar"></span><span class="nav-toggle-bar"></span>';

    const authSection = navContainer.querySelector('.nav-auth');
    if (authSection) {
        navContainer.insertBefore(toggle, authSection);
    } else {
        navContainer.appendChild(toggle);
    }

    toggle.addEventListener('click', () => {
        const isOpen = navMenu.classList.toggle('nav-menu-open');
        toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    });
}

/**
 * Basic modal focus management: keep Tab focus within open modal and
 * allow Escape key to close the active modal.
 */
function initModalFocusManagement() {
    function getActiveModal() {
        return document.querySelector('.modal.show');
    }

    document.addEventListener('keydown', (event) => {
        const modal = getActiveModal();
        if (!modal) return;

        const focusableSelectors = [
            'a[href]',
            'button:not([disabled])',
            'textarea:not([disabled])',
            'input:not([disabled])',
            'select:not([disabled])',
            '[tabindex]:not([tabindex="-1"])',
        ];
        const focusable = Array.from(
            modal.querySelectorAll(focusableSelectors.join(','))
        ).filter(el => el.offsetParent !== null);

        if (event.key === 'Tab' && focusable.length > 0) {
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            const current = document.activeElement;

            if (event.shiftKey) {
                if (current === first || !modal.contains(current)) {
                    event.preventDefault();
                    last.focus();
                }
            } else {
                if (current === last || !modal.contains(current)) {
                    event.preventDefault();
                    first.focus();
                }
            }
        }

        if (event.key === 'Escape') {
            const closeButton = modal.querySelector('.modal-close, [data-close-modal="true"]');
            if (closeButton) {
                event.preventDefault();
                closeButton.click();
            }
        }
    });
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

    // Enhance navigation and modals for accessibility and mobile
    initMobileNav();
    initModalFocusManagement();
});

/**
 * Update navigation to show login/logout based on auth status.
 * This only updates the user/auth area and intentionally preserves
 * the notification bell and dropdown structure.
 */
async function updateNavigation() {
    const navAuthUser = document.getElementById('nav-auth-user');
    const bell = document.getElementById('notification-bell');
    const dropdown = document.getElementById('notification-dropdown');
    if (!navAuthUser) return;
    
    // Check auth status from API (source of truth)
    let authenticated = false;
    let userInfo = null;
    
    try {
        const authCheck = await apiCall('/auth/check');
        authenticated = !!authCheck.authenticated;
        if (authenticated && authCheck.user_id) {
            try {
                userInfo = await apiCall('/auth/me');
            } catch (error) {
                // If /auth/me fails, clear token and treat as logged out
                console.warn('Failed to load user info, clearing token:', error);
                clearAuthToken();
                authenticated = false;
            }
        }
    } catch (error) {
        // If check fails, assume not authenticated
        console.debug('Auth check failed, treating as unauthenticated:', error);
        authenticated = false;
    }
    
    // Show or hide notification UI based on auth status
    if (bell) {
        bell.style.display = authenticated ? 'inline-flex' : 'none';
    }
    if (!authenticated && dropdown) {
        dropdown.classList.remove('active');
    }
    
    if (authenticated && userInfo) {
        navAuthUser.innerHTML = `
            <span class="nav-username" aria-label="Signed in as ${escapeHtml(userInfo.username)}">
                ${escapeHtml(userInfo.username)}
            </span>
            <button class="btn btn-secondary" id="logout-btn" type="button">Logout</button>
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
                // Immediately update nav and hide notifications on logout
                if (bell) bell.style.display = 'none';
                if (dropdown) dropdown.classList.remove('active');
                await updateNavigation();
                window.location.href = '/';
            });
        }
    } else {
        navAuthUser.innerHTML = `
            <a href="/login.html" class="btn btn-primary" id="login-btn">Login</a>
        `;
    }
}

/**
 * Escape HTML to prevent XSS
 */
/**
 * Company logo registry - maps company slugs to logo URLs
 * Can be extended with API data or external logo services
 */
const COMPANY_LOGOS = {
    // Example entries - can be populated from API or external service
    // 'google': 'https://logo.clearbit.com/google.com',
    // 'microsoft': 'https://logo.clearbit.com/microsoft.com',
};

/**
 * Get company logo URL or return null if not available
 * @param {string} slug - Company slug
 * @param {string} website - Optional company website URL
 * @returns {string|null} Logo URL or null
 */
function getCompanyLogoUrl(slug, website = null) {
    // Check registry first
    if (COMPANY_LOGOS[slug]) {
        return COMPANY_LOGOS[slug];
    }
    
    // Try to generate from website if available
    if (website) {
        try {
            const url = new URL(website);
            const domain = url.hostname.replace('www.', '');
            // Use Clearbit logo service as fallback
            return `https://logo.clearbit.com/${domain}`;
        } catch (e) {
            // Invalid URL, skip
        }
    }
    
    return null;
}

/**
 * Render company logo or initials placeholder
 * @param {string} companyName - Company name
 * @param {string} slug - Company slug
 * @param {string} website - Optional company website
 * @param {number} size - Size in pixels (default 48)
 * @returns {string} HTML string for logo/initials
 */
function renderCompanyLogo(companyName, slug, website = null, size = 48) {
    const logoUrl = getCompanyLogoUrl(slug, website);
    const initials = companyName.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
    
    if (logoUrl) {
        return `
            <img src="${escapeHtml(logoUrl)}" 
                 alt="${escapeHtml(companyName)} logo" 
                 class="company-logo"
                 style="width: ${size}px; height: ${size}px; border-radius: 50%; object-fit: cover;"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
            <div class="company-logo-initials" style="display: none; width: ${size}px; height: ${size}px; border-radius: 50%; background: var(--primary-color, #4a6fa5); color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: ${size * 0.4}px;">
                ${escapeHtml(initials)}
            </div>
        `;
    }
    
    return `
        <div class="company-logo-initials" style="width: ${size}px; height: ${size}px; border-radius: 50%; background: var(--primary-color, #4a6fa5); color: white; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: ${size * 0.4}px;">
            ${escapeHtml(initials)}
        </div>
    `;
}

/**
 * Render empty state illustration SVG
 * @param {string} type - 'jobs', 'applications', 'companies', 'analytics'
 * @returns {string} SVG HTML string
 */
function renderEmptyStateIllustration(type) {
    const illustrations = {
        jobs: `
            <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="20" y="30" width="80" height="60" rx="4" fill="currentColor" opacity="0.1"/>
                <rect x="25" y="40" width="50" height="6" rx="2" fill="currentColor" opacity="0.3"/>
                <rect x="25" y="52" width="40" height="4" rx="2" fill="currentColor" opacity="0.2"/>
                <rect x="25" y="60" width="35" height="4" rx="2" fill="currentColor" opacity="0.2"/>
                <circle cx="85" cy="45" r="8" fill="currentColor" opacity="0.2"/>
                <path d="M82 45 L85 48 L88 45" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.4"/>
            </svg>
        `,
        applications: `
            <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="30" y="20" width="60" height="80" rx="4" fill="currentColor" opacity="0.1"/>
                <rect x="35" y="30" width="50" height="8" rx="2" fill="currentColor" opacity="0.3"/>
                <rect x="35" y="45" width="40" height="6" rx="2" fill="currentColor" opacity="0.2"/>
                <rect x="35" y="58" width="35" height="6" rx="2" fill="currentColor" opacity="0.2"/>
                <circle cx="75" cy="35" r="6" fill="currentColor" opacity="0.2"/>
                <path d="M72 35 L75 38 L78 35" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.4"/>
            </svg>
        `,
        companies: `
            <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="25" y="35" width="70" height="50" rx="4" fill="currentColor" opacity="0.1"/>
                <rect x="30" y="45" width="60" height="8" rx="2" fill="currentColor" opacity="0.3"/>
                <rect x="30" y="60" width="45" height="6" rx="2" fill="currentColor" opacity="0.2"/>
                <rect x="30" y="72" width="35" height="6" rx="2" fill="currentColor" opacity="0.2"/>
                <circle cx="85" cy="50" r="10" fill="currentColor" opacity="0.15"/>
                <text x="85" y="55" text-anchor="middle" font-size="12" fill="currentColor" opacity="0.4" font-weight="600">Co</text>
            </svg>
        `,
        analytics: `
            <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="20" y="20" width="80" height="80" rx="4" fill="currentColor" opacity="0.1"/>
                <line x1="30" y1="80" x2="40" y2="60" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity="0.3"/>
                <line x1="40" y1="60" x2="50" y2="45" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity="0.3"/>
                <line x1="50" y1="45" x2="60" y2="55" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity="0.3"/>
                <line x1="60" y1="55" x2="70" y2="35" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity="0.3"/>
                <line x1="70" y1="35" x2="80" y2="50" stroke="currentColor" stroke-width="3" stroke-linecap="round" opacity="0.3"/>
                <circle cx="30" cy="80" r="3" fill="currentColor" opacity="0.4"/>
                <circle cx="40" cy="60" r="3" fill="currentColor" opacity="0.4"/>
                <circle cx="50" cy="45" r="3" fill="currentColor" opacity="0.4"/>
                <circle cx="60" cy="55" r="3" fill="currentColor" opacity="0.4"/>
                <circle cx="70" cy="35" r="3" fill="currentColor" opacity="0.4"/>
                <circle cx="80" cy="50" r="3" fill="currentColor" opacity="0.4"/>
            </svg>
        `
    };
    return illustrations[type] || illustrations.jobs;
}

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
    // Additional icons used across the app (Heroicons outline)
    globeAlt: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18z" /><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.522 5 12 5c4.477 0 8.268 2.943 9.542 7-1.274 4.057-5.065 7-9.542 7-4.478 0-8.268-2.943-9.542-7z" /><path stroke-linecap="round" stroke-linejoin="round" d="M12 3v18" />',
    userGroup: '<path stroke-linecap="round" stroke-linejoin="round" d="M18 20.25c0-2.485-2.239-4.5-5-4.5s-5 2.015-5 4.5M15 9.75a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" d="M21 20.25c0-2.485-1.79-4.5-4-4.5-.553 0-1.084.095-1.574.27M17.25 10.5a2.25 2.25 0 10-4.5 0" />',
    mapPin: '<path stroke-linecap="round" stroke-linejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" /><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />',
    informationCircle: '<path stroke-linecap="round" stroke-linejoin="round" d="M11.25 9.75h1.5m-1.5 3h1.5v4.5m-1.5 0h1.5M12 21a9 9 0 100-18 9 9 0 000 18z" />',
    plus: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />',
    shieldCheck: '<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75l2.25 2.25L15 9.75M21 5.25l-9-3-9 3v6.75c0 5.25 3.75 8.91 9 10.5 5.25-1.59 9-5.25 9-10.5V5.25z" />',
    academicCap: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 3L1.5 8.25 12 13.5l10.5-5.25L12 3z" /><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 10.5v5.25A8.25 8.25 0 0012 21a8.25 8.25 0 007.5-5.25V10.5" />',
    clock: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />',
    exclamationTriangle: '<path stroke-linecap="round" stroke-linejoin="round" d="M10.29 3.86L1.82 18a1.5 1.5 0 001.29 2.25h17.78A1.5 1.5 0 0022.18 18L13.71 3.86a1.5 1.5 0 00-2.42 0z" /><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v4.5m0 3h.01" />',
    arrowTopRightOnSquare: '<path stroke-linecap="round" stroke-linejoin="round" d="M13.5 6H21m0 0v7.5m0-7.5L10.5 16.5" /><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 4.5h7.5M4.5 19.5h7.5M4.5 4.5v15" />',
    wifi: '<path stroke-linecap="round" stroke-linejoin="round" d="M8.288 15.712A5.25 5.25 0 0112 14.25c1.45 0 2.762.586 3.712 1.537M5.106 12.53a9 9 0 0111.788 0M2.25 9.75a12.75 12.75 0 0119.5 0M12 18.75h.007v.007H12v-.007z" />',
    currencyDollar: '<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />',
    tag: '<path stroke-linecap="round" stroke-linejoin="round" d="M7.5 3.75h3.879a2.25 2.25 0 011.591.659l6.621 6.621a2.25 2.25 0 010 3.182l-4.94 4.94a2.25 2.25 0 01-3.182 0l-6.621-6.621A2.25 2.25 0 013 11.379V7.5A3.75 3.75 0 016.75 3.75z" /><path stroke-linecap="round" stroke-linejoin="round" d="M9 7.5h.008v.008H9V7.5z" />',
    eyeSlash: '<path stroke-linecap="round" stroke-linejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c1.612 0 3.14-.332 4.5-.934M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.774 3.162 10.066 7.498a10.52 10.52 0 01-1.592 3.038M6.228 6.228L3 3m3.228 3.228L3.98 8.223M6.228 6.228L9 9m6 6l3 3m-3-3L9.879 9.879M15 12a3 3 0 00-3-3" />',
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
    renderEmptyStateIllustration,
    renderCompanyLogo,
    getCompanyLogoUrl,
    loadTheme,
    escapeHtml,
};
