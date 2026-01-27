/**
 * Companies Page JavaScript
 * 
 * Handles company listing, search, detail views, analytics, notes, and jobs.
 */

// State management
let companies = [];
let companiesPage = 1;
let companiesPageSize = 50;
let companiesHasMore = true;
let companiesSearchQuery = '';
let currentCompanyId = null;
let currentCompany = null;
let currentAnalytics = null;
let currentJobs = [];
let searchTimeout = null;

// Initialize page
document.addEventListener('DOMContentLoaded', async () => {
    // Render icons
    renderPageIcons();
    
    setupEventListeners();
    await loadCompanies(true);

    // Infinite scroll: load additional pages as user nears bottom
    const grid = document.getElementById('companies-grid');
    if (grid) {
        window.addEventListener('scroll', () => {
            const scrollPosition = window.innerHeight + window.scrollY;
            const threshold = document.body.offsetHeight - 400;
            if (scrollPosition >= threshold && companiesHasMore) {
                loadCompanies();
            }
        });
    }
});

/**
 * Render icons on page load
 */
function renderPageIcons() {
    if (!window.JobTracker || !window.JobTracker.renderIcon) return;
    
    const emptyIcon = document.getElementById('empty-icon-companies');
    if (emptyIcon && window.JobTracker.renderEmptyStateIllustration) {
        emptyIcon.innerHTML = window.JobTracker.renderEmptyStateIllustration('companies');
    } else if (emptyIcon && window.JobTracker.renderIcon) {
        emptyIcon.innerHTML = window.JobTracker.renderIcon('buildingOffice', { size: 64 });
    }
    
    // Render tab icons
    const tabIcons = {
        'tab-icon-overview': 'informationCircle',
        'tab-icon-analytics': 'chartBar',
        'tab-icon-jobs': 'briefcase',
        'tab-icon-notes': 'documentText'
    };
    
    Object.entries(tabIcons).forEach(([id, iconName]) => {
        const el = document.getElementById(id);
        if (el && window.JobTracker.renderIcon) {
            el.innerHTML = window.JobTracker.renderIcon(iconName, { size: 18, class: 'tab-icon' });
        }
    });
    
    // Render refresh icon
    const refreshIcon = document.getElementById('refresh-icon');
    if (refreshIcon && window.JobTracker.renderIcon) {
        refreshIcon.innerHTML = window.JobTracker.renderIcon('arrowPath', { size: 16, class: 'btn-icon' });
    }
    
    // Render add note icon
    const addNoteIcon = document.getElementById('add-note-icon');
    if (addNoteIcon && window.JobTracker.renderIcon) {
        addNoteIcon.innerHTML = window.JobTracker.renderIcon('plus', { size: 16, class: 'btn-icon' });
    }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Company search (server-side, debounced)
    const searchInput = document.getElementById('company-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            companiesSearchQuery = e.target.value.trim();
            
            if (searchTimeout) {
                clearTimeout(searchTimeout);
            }
            
            searchTimeout = setTimeout(() => {
                // Reset state and load from first page on new search
                companiesPage = 1;
                companiesHasMore = true;
                companies = [];
                loadCompanies(true);
            }, 300);
        });
    }
    
    // Modal close buttons
    document.getElementById('company-detail-close')?.addEventListener('click', closeCompanyDetailModal);
    document.getElementById('company-detail-close-btn')?.addEventListener('click', closeCompanyDetailModal);
    document.getElementById('add-note-close')?.addEventListener('click', closeAddNoteModal);
    document.getElementById('add-note-cancel-btn')?.addEventListener('click', closeAddNoteModal);
    
    // Detail tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchDetailTab(tab);
        });
    });
    
    // Add note button
    document.getElementById('add-note-btn')?.addEventListener('click', () => {
        if (currentCompanyId) {
            showAddNoteModal(currentCompanyId);
        }
    });
    
    // Add note form submission
    document.getElementById('add-note-submit-btn')?.addEventListener('click', saveNote);
    
    // Refresh analytics button
    document.getElementById('refresh-analytics-btn')?.addEventListener('click', refreshAnalytics);
    
    // Jobs sort
    document.getElementById('jobs-sort-select')?.addEventListener('change', (e) => {
        sortJobs(e.target.value);
    });
    
    // Close modals on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeCompanyDetailModal();
            }
        });
    });
}

/**
 * Load companies from API
 */
async function loadCompanies(reset = false) {
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const companiesGrid = document.getElementById('companies-grid');
    const emptyState = document.getElementById('empty-state');
    
    if (reset) {
        companiesPage = 1;
        companiesHasMore = true;
        companies = [];
    }

    // If we've already loaded all available pages, don't show loading again
    if (!companiesHasMore && !reset) {
        return;
    }

    loadingState.style.display = 'flex';
    errorState.style.display = 'none';
    companiesGrid.style.display = companies.length > 0 ? 'grid' : 'none';
    emptyState.style.display = 'none';
    
    try {
        const params = new URLSearchParams({
            page: companiesPage.toString(),
            page_size: companiesPageSize.toString(),
        });

        if (companiesSearchQuery) {
            params.append('search', companiesSearchQuery);
        }

        const data = await JobTracker.apiCall(`/companies?${params.toString()}`);
        const pageCompanies = data || [];

        if (pageCompanies.length < companiesPageSize) {
            companiesHasMore = false;
        } else {
            companiesPage += 1;
        }

        companies = companies.concat(pageCompanies);
        
        loadingState.style.display = 'none';
        
        if (companies.length === 0) {
            emptyState.style.display = 'block';
            companiesGrid.style.display = 'none';
        } else {
            renderCompanies(companies);
            companiesGrid.style.display = 'grid';
        }
    } catch (error) {
        console.error('Failed to load companies:', error);
        loadingState.style.display = 'none';
        errorState.style.display = 'block';
        document.getElementById('error-message').textContent = 
            error.message || 'Failed to load companies. Please try again.';
    }
}

// Note: previous client-side filterCompanies(query) has been replaced by
// server-side search via the loadCompanies() function for scalability.

/**
 * Render companies grid
 */
function renderCompanies(companiesToRender) {
    const grid = document.getElementById('companies-grid');
    
    if (companiesToRender.length === 0) {
        grid.innerHTML = '';
        return;
    }
    
    grid.innerHTML = companiesToRender.map(company => `
        <div class="company-card" onclick="viewCompanyDetail(${company.id})">
            <div class="company-card-logo">
                ${JobTracker.renderCompanyLogo ? JobTracker.renderCompanyLogo(company.name, company.slug, company.website, 56) : ''}
            </div>
            <div class="company-card-header">
                <h3 class="company-card-name">${escapeHtml(company.name)}</h3>
                <span class="company-card-source">${escapeHtml(company.source)}</span>
            </div>
            <div class="company-card-info">
                ${company.industry ? `
                    <div class="company-card-info-item">
                        ${JobTracker.renderIcon ? JobTracker.renderIcon('buildingOffice', { size: 16, class: 'inline-icon' }) : ''}
                        <span>${escapeHtml(company.industry)}</span>
                    </div>
                ` : ''}
                ${company.size ? `
                    <div class="company-card-info-item">
                        ${JobTracker.renderIcon ? JobTracker.renderIcon('briefcase', { size: 16, class: 'inline-icon' }) : ''}
                        <span>${escapeHtml(company.size)}</span>
                    </div>
                ` : ''}
                ${company.headquarters ? `
                    <div class="company-card-info-item">
                        ${JobTracker.renderIcon ? JobTracker.renderIcon('mapPin', { size: 16, class: 'inline-icon' }) : ''}
                        <span>${escapeHtml(company.headquarters)}</span>
                    </div>
                ` : ''}
            </div>
            <div class="company-card-actions">
                <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); viewCompanyDetail(${company.id})">
                    ${JobTracker.renderIcon ? JobTracker.renderIcon('eye', { size: 16, class: 'btn-icon' }) : ''}
                    <span>View Details</span>
                </button>
            </div>
        </div>
    `).join('');
}

/**
 * View company detail
 */
async function viewCompanyDetail(companyId) {
    currentCompanyId = companyId;
    const modal = document.getElementById('company-detail-modal');
    
    try {
        // Load all data in parallel
        const [company, analytics, jobs] = await Promise.all([
            JobTracker.apiCall(`/companies/${companyId}`).catch(() => null),
            JobTracker.apiCall(`/companies/${companyId}/analytics`).catch(() => null),
            JobTracker.apiCall(`/companies/${companyId}/jobs?active_only=true`).catch(() => [])
        ]);
        
        currentCompany = company;
        currentAnalytics = analytics;
        currentJobs = jobs || [];
        
        if (!company) {
            throw new Error('Company not found');
        }
        
        // Render all sections
        renderCompanyHeader(company, analytics);
        // Quick actions bar removed
        renderCompanyOverview(company, analytics);
        renderAnalytics(analytics);
        renderCompanyJobs(jobs || []);
        
        // Load notes separately (may require auth)
        await loadCompanyNotes(companyId);
        
        // Prevent body scroll when modal is open
        document.body.style.overflow = 'hidden';
        
        // Show modal - ensure it's centered and visible
        modal.style.display = 'flex';
        // Force reflow to ensure display is applied
        void modal.offsetHeight;
        modal.classList.add('show');
        
        // Ensure modal is visible and centered
        setTimeout(() => {
            // Reset modal scroll position
            modal.scrollTop = 0;
            
            // Focus on modal for accessibility
            const modalContent = modal.querySelector('.modal-content');
            if (modalContent) {
                modalContent.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }, 50);
        
        // Restore last selected tab for this company, defaulting to overview
        const lastTabKey = `company_last_tab_${companyId}`;
        const lastTab = localStorage.getItem(lastTabKey) || 'overview';
        switchDetailTab(lastTab);
    } catch (error) {
        console.error('Failed to load company details:', error);
        JobTracker.showNotification('Failed to load company details', 'error');
    }
}

/**
 * Render company header with quick stats
 */
function renderCompanyHeader(company, analytics) {
    document.getElementById('company-detail-title').textContent = company.name;
    
    // Company logo or initials
    const logoContainer = document.getElementById('company-initials');
    if (logoContainer && JobTracker.renderCompanyLogo) {
        logoContainer.innerHTML = JobTracker.renderCompanyLogo(company.name, company.slug, company.website, 80);
    } else if (logoContainer) {
        const initials = company.name.split(' ').map(w => w[0]).join('').substring(0, 2).toUpperCase();
        logoContainer.textContent = initials;
    }
    
    // Quick stats in header
    const quickStats = document.getElementById('company-quick-stats');
    const stats = [];
    
    if (analytics) {
        if (analytics.reliability_score !== undefined) {
            const scoreClass = analytics.reliability_score >= 70 ? 'high' : 
                             analytics.reliability_score >= 40 ? 'medium' : 'low';
            stats.push(`
                <div class="quick-stat">
                    <span class="quick-stat-label">Reliability</span>
                    <span class="quick-stat-value ${scoreClass}">${analytics.reliability_score}/100</span>
                </div>
            `);
        }
        if (analytics.new_grad_friendly_score !== undefined) {
            const ngClass = analytics.new_grad_friendly_score >= 50 ? 'high' : 
                          analytics.new_grad_friendly_score >= 20 ? 'medium' : 'low';
            stats.push(`
                <div class="quick-stat">
                    <span class="quick-stat-label">New Grad Friendly</span>
                    <span class="quick-stat-value ${ngClass}">${analytics.new_grad_friendly_score}%</span>
                </div>
            `);
        }
        if (analytics.posting_frequency_per_month !== undefined) {
            stats.push(`
                <div class="quick-stat">
                    <span class="quick-stat-label">Postings/Month</span>
                    <span class="quick-stat-value">${analytics.posting_frequency_per_month}</span>
                </div>
            `);
        }
    }
    
    if (currentJobs.length > 0) {
        stats.push(`
            <div class="quick-stat">
                <span class="quick-stat-label">Active Jobs</span>
                <span class="quick-stat-value">${currentJobs.length}</span>
            </div>
        `);
    }
    
    quickStats.innerHTML = stats.join('');
}

/**
 * Render quick actions bar
 */
function renderQuickActions(company) {
    const actionsBar = document.getElementById('quick-actions-bar');
    const actions = [];
    
    if (company.website) {
        const icon = JobTracker.renderIcon ? JobTracker.renderIcon('globeAlt', { size: 16, class: 'btn-icon' }) : '';
        actions.push(`
            <a href="${escapeHtml(company.website)}" target="_blank" class="quick-action-btn">
                <span class="btn-icon">${icon}</span>
                <span>Website</span>
            </a>
        `);
    }
    
    if (company.linkedin_url) {
        const icon = JobTracker.renderIcon ? JobTracker.renderIcon('userGroup', { size: 16, class: 'btn-icon' }) : '';
        actions.push(`
            <a href="${escapeHtml(company.linkedin_url)}" target="_blank" class="quick-action-btn">
                <span class="btn-icon">${icon}</span>
                <span>LinkedIn</span>
            </a>
        `);
    }
    
    if (company.glassdoor_url) {
        const icon = JobTracker.renderIcon ? JobTracker.renderIcon('star', { size: 16, class: 'btn-icon' }) : '';
        actions.push(`
            <a href="${escapeHtml(company.glassdoor_url)}" target="_blank" class="quick-action-btn">
                <span class="btn-icon">${icon}</span>
                <span>Glassdoor</span>
            </a>
        `);
    }
    
    const jobsIcon = JobTracker.renderIcon ? JobTracker.renderIcon('briefcase', { size: 16, class: 'btn-icon' }) : '';
    actions.push(`
        <button class="quick-action-btn" onclick="switchDetailTab('jobs')">
            <span class="btn-icon">${jobsIcon}</span>
            <span>View Jobs</span>
        </button>
    `);
    
    const analyticsIcon = JobTracker.renderIcon ? JobTracker.renderIcon('chartBar', { size: 16, class: 'btn-icon' }) : '';
    actions.push(`
        <button class="quick-action-btn" onclick="switchDetailTab('analytics')">
            <span class="btn-icon">${analyticsIcon}</span>
            <span>Analytics</span>
        </button>
    `);
    
    actionsBar.innerHTML = actions.join('');
}

/**
 * Render company overview
 */
function renderCompanyOverview(company, analytics) {
    const metaDiv = document.getElementById('company-meta');
    const detailsDiv = document.getElementById('profile-details');
    const headerActions = document.getElementById('company-header-actions');
    const keyMetrics = document.getElementById('key-metrics-grid');
    
    // Company name
    document.getElementById('company-name').textContent = company.name;
    
    // Meta information
    const metaItems = [];
    if (company.industry) {
        metaItems.push(`
            <div class="company-meta-item">
                ${JobTracker.renderIcon ? JobTracker.renderIcon('buildingOffice', { size: 18, class: 'inline-icon' }) : ''}
                <span>${escapeHtml(company.industry)}</span>
            </div>
        `);
    }
    if (company.size) {
        metaItems.push(`
            <div class="company-meta-item">
                ${JobTracker.renderIcon ? JobTracker.renderIcon('briefcase', { size: 18, class: 'inline-icon' }) : ''}
                <span>${escapeHtml(company.size)}</span>
            </div>
        `);
    }
    if (company.founded_year) {
        metaItems.push(`
            <div class="company-meta-item">
                ${JobTracker.renderIcon ? JobTracker.renderIcon('calendar', { size: 18, class: 'inline-icon' }) : ''}
                <span>Founded ${company.founded_year}</span>
            </div>
        `);
    }
    if (company.headquarters) {
        metaItems.push(`
            <div class="company-meta-item">
                ${JobTracker.renderIcon ? JobTracker.renderIcon('mapPin', { size: 18, class: 'inline-icon' }) : ''}
                <span>${escapeHtml(company.headquarters)}</span>
            </div>
        `);
    }
    
    metaDiv.innerHTML = metaItems.join('');
    
    // Header actions
    const headerActionButtons = [];
    if (company.website) {
        const icon = JobTracker.renderIcon ? JobTracker.renderIcon('globeAlt', { size: 16, class: 'btn-icon' }) : '';
        headerActionButtons.push(`
            <a href="${escapeHtml(company.website)}" target="_blank" class="btn btn-primary btn-sm">
                <span class="btn-icon">${icon}</span>
                <span>Visit Website</span>
            </a>
        `);
    }
    headerActions.innerHTML = headerActionButtons.join('');
    
    // Key metrics
    const metrics = [];
    if (analytics) {
        if (analytics.reliability_score !== undefined) {
            const scoreClass = analytics.reliability_score >= 70 ? 'high' : 
                             analytics.reliability_score >= 40 ? 'medium' : 'low';
            const icon = JobTracker.renderIcon ? JobTracker.renderIcon('shieldCheck', { size: 24 }) : '';
            metrics.push(`
                <div class="key-metric-card">
                    <div class="key-metric-icon high">${icon}</div>
                    <div class="key-metric-content">
                        <div class="key-metric-label">Reliability Score</div>
                        <div class="key-metric-value ${scoreClass}">${analytics.reliability_score}/100</div>
                        <div class="key-metric-desc">Based on posting patterns</div>
                    </div>
                </div>
            `);
        }
        
        if (analytics.new_grad_friendly_score !== undefined) {
            const ngClass = analytics.new_grad_friendly_score >= 50 ? 'high' : 
                          analytics.new_grad_friendly_score >= 20 ? 'medium' : 'low';
            const icon = JobTracker.renderIcon ? JobTracker.renderIcon('academicCap', { size: 24 }) : '';
            metrics.push(`
                <div class="key-metric-card">
                    <div class="key-metric-icon ${ngClass}">${icon}</div>
                    <div class="key-metric-content">
                        <div class="key-metric-label">New Grad Friendly</div>
                        <div class="key-metric-value ${ngClass}">${analytics.new_grad_friendly_score}%</div>
                        <div class="key-metric-desc">% of new grad positions</div>
                    </div>
                </div>
            `);
        }
        
        if (analytics.posting_frequency_per_month !== undefined) {
            const icon = JobTracker.renderIcon ? JobTracker.renderIcon('chartBar', { size: 24 }) : '';
            metrics.push(`
                <div class="key-metric-card">
                    <div class="key-metric-icon">${icon}</div>
                    <div class="key-metric-content">
                        <div class="key-metric-label">Posting Frequency</div>
                        <div class="key-metric-value">${analytics.posting_frequency_per_month}</div>
                        <div class="key-metric-desc">Jobs per month</div>
                    </div>
                </div>
            `);
        }
        
        if (analytics.avg_posting_duration_days !== undefined) {
            const icon = JobTracker.renderIcon ? JobTracker.renderIcon('clock', { size: 24 }) : '';
            metrics.push(`
                <div class="key-metric-card">
                    <div class="key-metric-icon">${icon}</div>
                    <div class="key-metric-content">
                        <div class="key-metric-label">Avg Duration</div>
                        <div class="key-metric-value">${analytics.avg_posting_duration_days} days</div>
                        <div class="key-metric-desc">Job posting lifespan</div>
                    </div>
                </div>
            `);
        }
    }
    
    if (currentJobs.length > 0) {
        const icon = JobTracker.renderIcon ? JobTracker.renderIcon('briefcase', { size: 24 }) : '';
        metrics.push(`
            <div class="key-metric-card">
                <div class="key-metric-icon">${icon}</div>
                <div class="key-metric-content">
                    <div class="key-metric-label">Active Jobs</div>
                    <div class="key-metric-value">${currentJobs.length}</div>
                    <div class="key-metric-desc">Currently available</div>
                </div>
            </div>
        `);
    }
    
    keyMetrics.innerHTML = metrics.join('');
    
    // Profile details
    const detailItems = [];
    
    if (company.description) {
        detailItems.push(`
            <div class="profile-detail-item full-width">
                <span class="profile-detail-label">Description</span>
                <p class="profile-detail-value">${escapeHtml(company.description)}</p>
            </div>
        `);
    }
    
    if (company.website) {
        detailItems.push(`
            <div class="profile-detail-item">
                <span class="profile-detail-label">Website</span>
                <a href="${escapeHtml(company.website)}" target="_blank" class="profile-detail-value link">
                    ${escapeHtml(company.website.replace(/^https?:\/\//, ''))}
                    ${JobTracker.renderIcon ? JobTracker.renderIcon('arrowTopRightOnSquare', { size: 14, class: 'inline-icon' }) : ''}
                </a>
            </div>
        `);
    }
    
    if (company.headquarters) {
        detailItems.push(`
            <div class="profile-detail-item">
                <span class="profile-detail-label">Headquarters</span>
                <span class="profile-detail-value">${escapeHtml(company.headquarters)}</span>
            </div>
        `);
    }
    
    if (company.employee_count) {
        detailItems.push(`
            <div class="profile-detail-item">
                <span class="profile-detail-label">Employees</span>
                <span class="profile-detail-value">${company.employee_count.toLocaleString()}</span>
            </div>
        `);
    }
    
    if (company.founded_year) {
        detailItems.push(`
            <div class="profile-detail-item">
                <span class="profile-detail-label">Founded</span>
                <span class="profile-detail-value">${company.founded_year}</span>
            </div>
        `);
    }
    
    if (company.linkedin_url) {
        detailItems.push(`
            <div class="profile-detail-item">
                <span class="profile-detail-label">LinkedIn</span>
                <a href="${escapeHtml(company.linkedin_url)}" target="_blank" class="profile-detail-value link">
                    View Profile
                    ${JobTracker.renderIcon ? JobTracker.renderIcon('arrowTopRightOnSquare', { size: 14, class: 'inline-icon' }) : ''}
                </a>
            </div>
        `);
    }
    
    if (company.glassdoor_url) {
        detailItems.push(`
            <div class="profile-detail-item">
                <span class="profile-detail-label">Glassdoor</span>
                <a href="${escapeHtml(company.glassdoor_url)}" target="_blank" class="profile-detail-value link">
                    View Reviews
                    ${JobTracker.renderIcon ? JobTracker.renderIcon('arrowTopRightOnSquare', { size: 14, class: 'inline-icon' }) : ''}
                </a>
            </div>
        `);
    }
    
    detailsDiv.innerHTML = detailItems.length > 0 ? detailItems.join('') : '<p class="text-muted">No additional information available.</p>';
}

/**
 * Load and render company analytics
 */
async function loadCompanyAnalytics(companyId) {
    try {
        const analytics = await JobTracker.apiCall(`/companies/${companyId}/analytics`);
        currentAnalytics = analytics;
        renderAnalytics(analytics);
    } catch (error) {
        console.error('Failed to load analytics:', error);
        const analyticsContent = document.getElementById('analytics-content');
        analyticsContent.innerHTML = `
            <div class="empty-state">
                <p>Failed to load analytics. ${error.message || ''}</p>
            </div>
        `;
    }
}

/**
 * Render analytics
 */
function renderAnalytics(analytics) {
    if (!analytics) {
        document.getElementById('analytics-content').innerHTML = '<div class="empty-state"><p>No analytics data available.</p></div>';
        return;
    }
    
    const scoresDiv = document.getElementById('analytics-scores');
    const analyticsContent = document.getElementById('analytics-content');
    const insightsDiv = document.getElementById('analytics-insights');
    
    // Score cards
    const reliabilityClass = analytics.reliability_score >= 70 ? 'high' : 
                           analytics.reliability_score >= 40 ? 'medium' : 'low';
    
    const newGradClass = analytics.new_grad_friendly_score >= 50 ? 'high' : 
                        analytics.new_grad_friendly_score >= 20 ? 'medium' : 'low';
    
    const reliabilityIcon = JobTracker.renderIcon ? JobTracker.renderIcon('shieldCheck', { size: 32 }) : '';
    const newGradIcon = JobTracker.renderIcon ? JobTracker.renderIcon('academicCap', { size: 32 }) : '';
    
    scoresDiv.innerHTML = `
        <div class="score-card ${reliabilityClass}">
            <div class="score-card-header">
                <div class="score-card-icon">${reliabilityIcon}</div>
                <div class="score-card-info">
                    <div class="score-card-label">Reliability Score</div>
                    <div class="score-card-value">${analytics.reliability_score}/100</div>
                </div>
            </div>
            <div class="score-card-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${analytics.reliability_score}%"></div>
                </div>
            </div>
            <div class="score-card-desc">Measures posting consistency and reliability</div>
        </div>
        <div class="score-card ${newGradClass}">
            <div class="score-card-header">
                <div class="score-card-icon">${newGradIcon}</div>
                <div class="score-card-info">
                    <div class="score-card-label">New Grad Friendly</div>
                    <div class="score-card-value">${analytics.new_grad_friendly_score}%</div>
                </div>
            </div>
            <div class="score-card-progress">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${analytics.new_grad_friendly_score}%"></div>
                </div>
            </div>
            <div class="score-card-desc">Percentage of positions suitable for new graduates</div>
        </div>
    `;
    
    // Detailed metrics - prepare icons
    const icons = {
        briefcase: JobTracker.renderIcon ? JobTracker.renderIcon('briefcase', { size: 20 }) : '',
        chartBar: JobTracker.renderIcon ? JobTracker.renderIcon('chartBar', { size: 20 }) : '',
        clock: JobTracker.renderIcon ? JobTracker.renderIcon('clock', { size: 20 }) : '',
        exclamationTriangle: JobTracker.renderIcon ? JobTracker.renderIcon('exclamationTriangle', { size: 20 }) : '',
        arrowPath: JobTracker.renderIcon ? JobTracker.renderIcon('arrowPath', { size: 20 }) : '',
        xCircle: JobTracker.renderIcon ? JobTracker.renderIcon('xCircle', { size: 20 }) : ''
    };
    
    analyticsContent.innerHTML = `
        <div class="analytics-card">
            <div class="analytics-card-icon">${icons.briefcase}</div>
            <div class="analytics-card-content">
                <span class="analytics-card-label">Total Jobs Posted</span>
                <div class="analytics-card-value">${analytics.total_jobs_posted}</div>
                <span class="analytics-card-desc">Last 90 days</span>
            </div>
        </div>
        <div class="analytics-card">
            <div class="analytics-card-icon">${icons.chartBar}</div>
            <div class="analytics-card-content">
                <span class="analytics-card-label">Posting Frequency</span>
                <div class="analytics-card-value">${analytics.posting_frequency_per_month}<span class="analytics-card-unit">/month</span></div>
                <span class="analytics-card-desc">Average monthly postings</span>
            </div>
        </div>
        <div class="analytics-card">
            <div class="analytics-card-icon">${icons.clock}</div>
            <div class="analytics-card-content">
                <span class="analytics-card-label">Avg Duration</span>
                <div class="analytics-card-value">${analytics.avg_posting_duration_days}<span class="analytics-card-unit">days</span></div>
                <span class="analytics-card-desc">Average job posting lifespan</span>
            </div>
        </div>
        <div class="analytics-card">
            <div class="analytics-card-icon">${icons.exclamationTriangle}</div>
            <div class="analytics-card-content">
                <span class="analytics-card-label">Ghost Posting Rate</span>
                <div class="analytics-card-value ${analytics.ghost_posting_rate > 20 ? 'warning' : ''}">${analytics.ghost_posting_rate}<span class="analytics-card-unit">%</span></div>
                <span class="analytics-card-desc">Jobs removed within 7 days</span>
            </div>
        </div>
        <div class="analytics-card">
            <div class="analytics-card-icon">${icons.arrowPath}</div>
            <div class="analytics-card-content">
                <span class="analytics-card-label">Job Churn Rate</span>
                <div class="analytics-card-value ${analytics.job_churn_rate > 50 ? 'warning' : ''}">${analytics.job_churn_rate}<span class="analytics-card-unit">%</span></div>
                <span class="analytics-card-desc">Monthly removal rate</span>
            </div>
        </div>
        <div class="analytics-card">
            <div class="analytics-card-icon">${icons.xCircle}</div>
            <div class="analytics-card-content">
                <span class="analytics-card-label">Jobs Removed</span>
                <div class="analytics-card-value">${analytics.total_jobs_removed}</div>
                <span class="analytics-card-desc">Last 90 days</span>
            </div>
        </div>
    `;
    
    // Insights
    const insights = [];
    if (analytics.reliability_score >= 70) {
        insights.push({
            type: 'positive',
            icon: 'checkCircle',
            text: 'High reliability score indicates consistent and reliable hiring practices.'
        });
    } else if (analytics.reliability_score < 40) {
        insights.push({
            type: 'warning',
            icon: 'exclamationTriangle',
            text: 'Low reliability score suggests inconsistent posting patterns or high ghost posting rate.'
        });
    }
    
    if (analytics.new_grad_friendly_score >= 50) {
        insights.push({
            type: 'positive',
            icon: 'academicCap',
            text: 'Strong new grad hiring presence - good opportunity for recent graduates.'
        });
    } else if (analytics.new_grad_friendly_score < 20) {
        insights.push({
            type: 'info',
            icon: 'informationCircle',
            text: 'Limited new grad positions - may require more experience.'
        });
    }
    
    if (analytics.ghost_posting_rate > 20) {
        insights.push({
            type: 'warning',
            icon: 'exclamationTriangle',
            text: 'High ghost posting rate - many jobs are removed quickly, possibly indicating outdated listings.'
        });
    }
    
    if (analytics.avg_posting_duration_days > 30) {
        insights.push({
            type: 'positive',
            icon: 'clock',
            text: 'Jobs stay posted for extended periods, indicating active recruitment.'
        });
    }
    
    if (insights.length === 0) {
        insights.push({
            type: 'info',
            icon: 'informationCircle',
            text: 'Analytics data is limited. More data will provide better insights.'
        });
    }
    
    insightsDiv.innerHTML = insights.map(insight => {
        const icon = JobTracker.renderIcon ? JobTracker.renderIcon(insight.icon, { size: 20 }) : '';
        return `
            <div class="insight-item ${insight.type}">
                <div class="insight-icon">${icon}</div>
                <div class="insight-text">${escapeHtml(insight.text)}</div>
            </div>
        `;
    }).join('');
}

/**
 * Refresh analytics
 */
async function refreshAnalytics() {
    if (!currentCompanyId) return;
    
    const btn = document.getElementById('refresh-analytics-btn');
    const refreshIcon = document.getElementById('refresh-icon');
    const originalHTML = btn.innerHTML;
    
    try {
        btn.disabled = true;
        if (refreshIcon) {
            refreshIcon.innerHTML = JobTracker.renderIcon ? JobTracker.renderIcon('arrowPath', { size: 16, class: 'btn-icon spinning' }) : '';
        }
        
        await JobTracker.apiCall(`/companies/${currentCompanyId}/analytics/refresh`, {
            method: 'POST'
        });
        
        // Reload analytics
        await loadCompanyAnalytics(currentCompanyId);
        
        // Update header stats
        if (currentCompany) {
            renderCompanyHeader(currentCompany, currentAnalytics);
        }
        
        JobTracker.showNotification('Analytics refreshed successfully', 'success');
    } catch (error) {
        console.error('Failed to refresh analytics:', error);
        JobTracker.showNotification('Failed to refresh analytics', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalHTML;
    }
}

/**
 * Load and render company jobs
 */
async function loadCompanyJobs(companyId) {
    try {
        const jobs = await JobTracker.apiCall(`/companies/${companyId}/jobs?active_only=true`);
        currentJobs = jobs || [];
        renderCompanyJobs(jobs || []);
    } catch (error) {
        console.error('Failed to load company jobs:', error);
        const jobsList = document.getElementById('company-jobs-list');
        jobsList.innerHTML = `
            <div class="empty-state">
                <p>Failed to load jobs. ${error.message || ''}</p>
            </div>
        `;
    }
}

/**
 * Sort jobs
 */
function sortJobs(sortBy) {
    if (!currentJobs || currentJobs.length === 0) return;
    
    const sorted = [...currentJobs];
    
    switch(sortBy) {
        case 'title':
            sorted.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
            break;
        case 'location':
            sorted.sort((a, b) => (a.location || '').localeCompare(b.location || ''));
            break;
        case 'recent':
        default:
            sorted.sort((a, b) => {
                const dateA = new Date(a.last_seen || 0);
                const dateB = new Date(b.last_seen || 0);
                return dateB - dateA;
            });
            break;
    }
    
    renderCompanyJobs(sorted);
}

/**
 * Render company jobs
 */
function renderCompanyJobs(jobs) {
    const jobsList = document.getElementById('company-jobs-list');
    const jobsSubtitle = document.getElementById('jobs-subtitle');
    const jobsBadge = document.getElementById('jobs-count-badge');
    
    if (jobsBadge) {
        if (jobs.length > 0) {
            jobsBadge.textContent = jobs.length;
            jobsBadge.style.display = 'inline-flex';
        } else {
            jobsBadge.style.display = 'none';
        }
    }
    
    if (!jobs || jobs.length === 0) {
        jobsList.innerHTML = `
            <div class="empty-state">
                <p>No active jobs found for this company at the moment.</p>
            </div>
        `;
        if (jobsSubtitle) jobsSubtitle.textContent = 'No active positions available';
        return;
    }
    
    if (jobsSubtitle) {
        jobsSubtitle.textContent = `${jobs.length} ${jobs.length === 1 ? 'position' : 'positions'} available`;
    }
    
    jobsList.innerHTML = jobs.map(job => {
        const jobTitle = job.title || 'Unknown Title';
        const location = job.location || 'Location not specified';
        const remote = job.remote ? 'Remote' : '';
        const sector = job.sector || '';
        
        return `
            <div class="company-job-item">
                <div class="company-job-info">
                    <div class="company-job-title">${escapeHtml(jobTitle)}</div>
                    <div class="company-job-meta">
                        ${location ? `<span class="job-meta-item">
                            ${JobTracker.renderIcon ? JobTracker.renderIcon('mapPin', { size: 14, class: 'inline-icon' }) : ''}
                            ${escapeHtml(location)}
                        </span>` : ''}
                        ${remote ? `<span class="job-meta-item">
                            ${JobTracker.renderIcon ? JobTracker.renderIcon('wifi', { size: 14, class: 'inline-icon' }) : ''}
                            ${remote}
                        </span>` : ''}
                        ${sector ? `<span class="job-meta-item">
                            ${JobTracker.renderIcon ? JobTracker.renderIcon('tag', { size: 14, class: 'inline-icon' }) : ''}
                            ${escapeHtml(sector)}
                        </span>` : ''}
                    </div>
                </div>
                <div class="company-job-actions">
                    <a href="${escapeHtml(job.url)}" target="_blank" class="btn btn-primary btn-sm">
                        <span class="btn-icon">${JobTracker.renderIcon ? JobTracker.renderIcon('arrowTopRightOnSquare', { size: 16, class: 'btn-icon' }) : ''}</span>
                        <span>View Job</span>
                    </a>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Load and render company notes
 */
async function loadCompanyNotes(companyId) {
    const notesList = document.getElementById('company-notes-list');
    const addNoteBtn = document.getElementById('add-note-btn');
    const addNoteIcon = document.getElementById('add-note-icon');
    
    // Explicit auth check before hitting notes endpoints
    const isAuthed = JobTracker.isAuthenticated && JobTracker.isAuthenticated();
    
    // Show/hide add note button based on authentication
    if (addNoteBtn) {
        if (isAuthed) {
            addNoteBtn.style.display = 'inline-flex';
            if (addNoteIcon) {
                addNoteIcon.innerHTML = JobTracker.renderIcon ? JobTracker.renderIcon('plus', { size: 16, class: 'btn-icon' }) : '';
            }
        } else {
            addNoteBtn.style.display = 'none';
        }
    }
    
    if (!isAuthed) {
        notesList.innerHTML = `
            <div class="empty-state">
                <p>Login required to use company notes.</p>
                <button class="btn btn-primary" type="button" onclick="window.location.href='/login.html?redirect=' + encodeURIComponent(window.location.pathname)">
                    Login to add notes
                </button>
            </div>
        `;
        return;
    }
    
    try {
        const notes = await JobTracker.apiCall(`/companies/${companyId}/notes?user_only=false`);
        renderCompanyNotes(notes);
    } catch (error) {
        console.error('Failed to load company notes:', error);
        notesList.innerHTML = `
            <div class="empty-state">
                <p>Failed to load notes. ${error.message || ''}</p>
            </div>
        `;
    }
}

/**
 * Render company notes
 */
function renderCompanyNotes(notes) {
    const notesList = document.getElementById('company-notes-list');
    
    if (!notes || notes.length === 0) {
        const isAuthenticated = JobTracker.isAuthenticated();
        notesList.innerHTML = `
            <div class="empty-state">
                <p>${isAuthenticated ? 'No notes yet. Be the first to add a note about this company!' : 'No notes yet.'}</p>
            </div>
        `;
        return;
    }
    
    notesList.innerHTML = notes.map(note => {
        // Get current user ID from stored user info
        const currentUserId = JobTracker.getCurrentUserId ? JobTracker.getCurrentUserId() : null;
        const isOwnNote = currentUserId !== null && note.user_id === currentUserId;
        const ratingStars = note.rating ? '⭐'.repeat(note.rating) : '';
        
        return `
            <div class="note-item">
                <div class="note-header">
                    <div>
                        <div class="note-author">${escapeHtml(note.username || 'Anonymous')}</div>
                        <div class="note-date">${JobTracker.formatDateTime ? JobTracker.formatDateTime(note.created_at) : new Date(note.created_at).toLocaleDateString()}</div>
                    </div>
                    ${isOwnNote ? `
                        <div class="note-actions">
                            <button class="btn btn-secondary btn-sm" onclick="editNote(${note.note_id})">Edit</button>
                            <button class="btn btn-secondary btn-sm" onclick="deleteNote(${note.note_id})">Delete</button>
                        </div>
                    ` : ''}
                </div>
                ${ratingStars ? `<div class="note-rating">${ratingStars}</div>` : ''}
                <div class="note-text">${escapeHtml(note.note_text)}</div>
            </div>
        `;
    }).join('');
}

/**
 * Show add note modal
 */
function showAddNoteModal(companyId) {
    // Check if user is authenticated
    if (!JobTracker.isAuthenticated()) {
        JobTracker.showNotification('Please log in to add notes', 'error');
        return;
    }
    
    const modal = document.getElementById('add-note-modal');
    document.getElementById('note-company-id').value = companyId;
    document.getElementById('add-note-form').reset();
    
    modal.style.display = 'flex';
    modal.classList.add('show');
}

/**
 * Close add note modal
 */
function closeAddNoteModal() {
    const modal = document.getElementById('add-note-modal');
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
}

/**
 * Save note
 */
async function saveNote() {
    const companyId = parseInt(document.getElementById('note-company-id').value);
    const noteText = document.getElementById('note-text').value.trim();
    const rating = document.getElementById('note-rating').value;
    
    if (!noteText) {
        JobTracker.showNotification('Note text is required', 'error');
        return;
    }
    
    try {
        const noteData = {
            note_text: noteText,
            rating: rating ? parseInt(rating) : null
        };
        
        await JobTracker.apiCall(`/companies/${companyId}/notes`, {
            method: 'POST',
            body: JSON.stringify(noteData)
        });
        
        JobTracker.showNotification('Note added successfully', 'success');
        closeAddNoteModal();
        await loadCompanyNotes(companyId);
    } catch (error) {
        console.error('Failed to save note:', error);
        JobTracker.showNotification(error.message || 'Failed to save note', 'error');
    }
}

/**
 * Edit note (placeholder - would open edit modal)
 */
function editNote(noteId) {
    // TODO: Implement edit note functionality
    JobTracker.showNotification('Edit note functionality coming soon', 'info');
}

/**
 * Delete note
 */
async function deleteNote(noteId) {
    if (!currentCompanyId) return;
    
    if (!confirm('Are you sure you want to delete this note?')) {
        return;
    }
    
    try {
        await JobTracker.apiCall(`/companies/${currentCompanyId}/notes/${noteId}`, {
            method: 'DELETE'
        });
        
        JobTracker.showNotification('Note deleted successfully', 'success');
        await loadCompanyNotes(currentCompanyId);
    } catch (error) {
        console.error('Failed to delete note:', error);
        JobTracker.showNotification(error.message || 'Failed to delete note', 'error');
    }
}

/**
 * Switch detail tab
 */
function switchDetailTab(tab) {
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    // Update tab content
    document.querySelectorAll('.detail-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `detail-${tab}`);
        if (content.id === `detail-${tab}`) {
            content.style.display = 'block';
        } else {
            content.style.display = 'none';
        }
    });
    
    // Persist last selected tab per company
    if (typeof currentCompanyId === 'number' || typeof currentCompanyId === 'string') {
        const lastTabKey = `company_last_tab_${currentCompanyId}`;
        localStorage.setItem(lastTabKey, tab);
    }
}

/**
 * Close company detail modal
 */
function closeCompanyDetailModal() {
    const modal = document.getElementById('company-detail-modal');
    modal.classList.remove('show');
    
    // Restore body scroll
    document.body.style.overflow = '';
    
    setTimeout(() => {
        modal.style.display = 'none';
        currentCompanyId = null;
        currentCompany = null;
        currentAnalytics = null;
        currentJobs = [];
    }, 300);
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (window.JobTracker && window.JobTracker.escapeHtml) {
        return window.JobTracker.escapeHtml(text);
    }
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions for global access
window.viewCompanyDetail = viewCompanyDetail;
window.editNote = editNote;
window.deleteNote = deleteNote;
window.loadCompanies = loadCompanies;
window.switchDetailTab = switchDetailTab;
