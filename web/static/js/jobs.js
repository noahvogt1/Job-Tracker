/**
 * Job Search Page JavaScript
 * 
 * Handles job search, filtering, pagination, and job detail display.
 */

// State management
let currentPage = 1;
let pageSize = 50;
let totalPages = 1;
let totalJobs = 0;
let currentFilters = {
    keywords: '',
    location: '',
    remote: null,
    company: [],
    sector: [],
    new_grad: null
};
let filterOptions = {
    companies: [],
    sectors: []
};
let savedJobIds = new Set();
let currentSort = 'recent';

// Initialize page
document.addEventListener('DOMContentLoaded', async () => {
    // Render icons
    renderPageIcons();
    
    await initializePage();
    setupEventListeners();
});

/**
 * Render icons on page load
 */
function renderPageIcons() {
    if (!window.JobTracker || !window.JobTracker.renderIcon) return;
    
    // Empty state icon
    const emptyIcon = document.getElementById('empty-icon-jobs');
    if (emptyIcon && window.JobTracker.renderEmptyStateIllustration) {
        emptyIcon.innerHTML = window.JobTracker.renderEmptyStateIllustration('jobs');
    } else if (emptyIcon && window.JobTracker.renderIcon) {
        emptyIcon.innerHTML = window.JobTracker.renderIcon('inbox', { size: 64 });
    }
    
    // Quick apply button icon
    const quickApplyIcon = document.getElementById('quick-apply-icon');
    if (quickApplyIcon) quickApplyIcon.innerHTML = window.JobTracker.renderIcon('documentText', { size: 18 });
}

/**
 * Initialize the page by loading filter options and jobs
 */
async function initializePage() {
    try {
        // Load filter options
        await loadFilterOptions();
        
        // Load initial jobs
        await loadJobs();
        
        // Load saved jobs if authenticated
        if (JobTracker.isAuthenticated()) {
            await loadSavedJobs();
            // Show save search button
            const saveSearchBtn = document.getElementById('save-search-btn');
            if (saveSearchBtn) {
                saveSearchBtn.style.display = 'inline-block';
            }
        }
    } catch (error) {
        console.error('Failed to initialize page:', error);
        showError('Failed to load page. Please refresh.');
    }
}

/**
 * Load available filter options (companies, sectors)
 */
async function loadFilterOptions() {
    try {
        const data = await JobTracker.apiCall('/jobs/filters/options');
        filterOptions = data;
        
        // Populate company filter
        const companySelect = document.getElementById('filter-company');
        companySelect.innerHTML = '<option value="">All Companies</option>';
        data.companies.forEach(company => {
            const option = document.createElement('option');
            option.value = company.id;
            option.textContent = `${company.name} (${company.job_count})`;
            companySelect.appendChild(option);
        });
        
        // Populate sector filter
        const sectorSelect = document.getElementById('filter-sector');
        sectorSelect.innerHTML = '<option value="">All Sectors</option>';
        data.sectors.forEach(sector => {
            const option = document.createElement('option');
            option.value = sector.name;
            option.textContent = `${sector.name} (${sector.job_count})`;
            sectorSelect.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load filter options:', error);
    }
}

/**
 * Load saved job IDs for authenticated users
 */
async function loadSavedJobs() {
    try {
        // Backend enforces page_size <= 100
        const data = await JobTracker.apiCall('/jobs/saved/list?page_size=100');
        savedJobIds = new Set(data.jobs.map(j => j.job.job_id));
        updateSaveButtons();
    } catch (error) {
        console.error('Failed to load saved jobs:', error);
    }
}

/**
 * Load jobs based on current filters and page
 */
async function loadJobs() {
    const loadingState = document.getElementById('loading-state');
    const errorState = document.getElementById('error-state');
    const jobsList = document.getElementById('jobs-list');
    const emptyState = document.getElementById('empty-state');
    const pagination = document.getElementById('pagination');
    
    // Show loading
    loadingState.style.display = 'flex';
    errorState.style.display = 'none';
    jobsList.innerHTML = '';
    emptyState.style.display = 'none';
    pagination.style.display = 'none';
    
    try {
        // Build query parameters
        const params = new URLSearchParams({
            page: currentPage.toString(),
            page_size: pageSize.toString()
        });
        
        if (currentFilters.keywords) {
            params.append('keywords', currentFilters.keywords);
        }
        if (currentFilters.location) {
            params.append('location', currentFilters.location);
        }
        if (currentFilters.remote !== null) {
            params.append('remote', currentFilters.remote.toString());
        }
        if (currentFilters.company.length > 0) {
            params.append('company', currentFilters.company.join(','));
        }
        if (currentFilters.sector.length > 0) {
            params.append('sector', currentFilters.sector.join(','));
        }
        if (currentFilters.new_grad !== null) {
            params.append('new_grad', currentFilters.new_grad.toString());
        }
        
        const data = await JobTracker.apiCall(`/jobs?${params.toString()}`);
        
        totalJobs = data.total;
        totalPages = data.total_pages;
        currentPage = data.page;
        
        // Update results header
        updateResultsHeader();
        
        // Hide loading
        loadingState.style.display = 'none';
        
        if (data.jobs.length === 0) {
            emptyState.style.display = 'block';
        } else {
            // Display jobs
            displayJobs(data.jobs);
            
            // Display pagination
            if (totalPages > 1) {
                displayPagination();
            }
        }
    } catch (error) {
        console.error('Failed to load jobs:', error);
        loadingState.style.display = 'none';
        errorState.style.display = 'block';
        document.getElementById('error-message').textContent = 
            error.message || 'Failed to load jobs. Please try again.';
    }
}

/**
 * Display jobs in the jobs list
 */
function displayJobs(jobs) {
    const jobsList = document.getElementById('jobs-list');
    jobsList.innerHTML = '';
    
    // Sort jobs if needed
    let sortedJobs = [...jobs];
    if (currentSort === 'company') {
        sortedJobs.sort((a, b) => a.company.localeCompare(b.company));
    } else if (currentSort === 'title') {
        sortedJobs.sort((a, b) => a.title.localeCompare(b.title));
    }
    // 'recent' is already sorted by API (last_seen DESC)
    
    sortedJobs.forEach(job => {
        const jobCard = createJobCard(job);
        jobsList.appendChild(jobCard);
    });
}

/**
 * Extract salary information from job extra data
 */
function getSalaryInfo(job) {
    if (!job.extra) return null;
    
    const extra = typeof job.extra === 'string' ? JSON.parse(job.extra) : job.extra;
    if (!extra) return null;
    
    // Try various salary field formats
    if (extra.salary_range) return extra.salary_range;
    if (extra.salaryRange) return extra.salaryRange;
    if (extra.salary) return extra.salary;
    
    // Try min/max format
    const min = extra.salary_min || extra.salaryMin || extra.min_salary || extra.minSalary;
    const max = extra.salary_max || extra.salaryMax || extra.max_salary || extra.maxSalary;
    const currency = extra.salary_currency || extra.salaryCurrency || extra.currency || 'USD';
    const period = extra.salary_period || extra.salaryPeriod || extra.period || '';
    
    if (min && max) {
        return `${currency} ${min.toLocaleString()} - ${max.toLocaleString()}${period ? ' ' + period : ''}`;
    } else if (min) {
        return `${currency} ${min.toLocaleString()}+${period ? ' ' + period : ''}`;
    }
    
    return null;
}

/**
 * Extract experience level from job extra data
 */
function getExperienceLevel(job) {
    if (!job.extra) return null;
    
    const extra = typeof job.extra === 'string' ? JSON.parse(job.extra) : job.extra;
    if (!extra) return null;
    
    const level = extra.experience_level || extra.experienceLevel || extra.level || extra.seniority;
    if (!level) return null;
    
    // Normalize common values
    const normalized = String(level).toLowerCase();
    if (normalized.includes('entry') || normalized.includes('junior') || normalized.includes('intern')) {
        return 'Entry';
    } else if (normalized.includes('mid') || normalized.includes('intermediate')) {
        return 'Mid';
    } else if (normalized.includes('senior') || normalized.includes('staff') || normalized.includes('lead')) {
        return 'Senior';
    } else if (normalized.includes('principal') || normalized.includes('architect')) {
        return 'Principal';
    }
    
    // Return capitalized first word
    return String(level).split(/[\s-]/)[0].charAt(0).toUpperCase() + String(level).split(/[\s-]/)[0].slice(1);
}

/**
 * Create a job card element
 */
function createJobCard(job) {
    const card = document.createElement('div');
    card.className = 'job-card';
    card.dataset.jobId = job.job_id;
    
    const isSaved = savedJobIds.has(job.job_id);
    const salary = getSalaryInfo(job);
    const experienceLevel = getExperienceLevel(job);
    
    card.innerHTML = `
        <div class="job-card-header">
            <div class="job-card-title-section">
                <h3 class="job-card-title">${escapeHtml(job.title)}</h3>
                <p class="job-card-company">${escapeHtml(job.company)}</p>
                <div class="job-card-meta">
                    <span class="job-card-meta-item">
                        ${JobTracker.renderIcon ? JobTracker.renderIcon('mapPin', { size: 16, class: 'inline-icon' }) : ''}
                        ${escapeHtml(job.location || 'Location not specified')}
                    </span>
                    ${job.remote ? `<span class="job-card-meta-item">${JobTracker.renderIcon ? JobTracker.renderIcon('wifi', { size: 16, class: 'inline-icon' }) : ''} Remote</span>` : ''}
                    ${job.sector ? `<span class="job-card-meta-item">${JobTracker.renderIcon ? JobTracker.renderIcon('buildingOffice', { size: 16, class: 'inline-icon' }) : ''} ${escapeHtml(job.sector)}</span>` : ''}
                    ${job.posted_at ? `<span class="job-card-meta-item">${JobTracker.renderIcon ? JobTracker.renderIcon('calendar', { size: 16, class: 'inline-icon' }) : ''} ${JobTracker.formatDate(job.posted_at)}</span>` : ''}
                </div>
                <div class="job-card-highlights">
                    ${salary ? `<span class="job-card-highlight salary-highlight">
                        ${JobTracker.renderIcon ? JobTracker.renderIcon('currencyDollar', { size: 16, class: 'inline-icon' }) : '💰'}
                        ${escapeHtml(salary)}
                    </span>` : ''}
                    ${experienceLevel ? `<span class="job-card-highlight experience-highlight">
                        ${JobTracker.renderIcon ? JobTracker.renderIcon('academicCap', { size: 16, class: 'inline-icon' }) : '🎓'}
                        ${escapeHtml(experienceLevel)}
                    </span>` : ''}
                </div>
                <div class="job-card-badges">
                    ${job.is_new_grad ? '<span class="badge badge-new-grad">New Grad</span>' : ''}
                    ${job.remote ? '<span class="badge badge-remote">Remote</span>' : ''}
                    ${job.sector ? `<span class="badge badge-sector">${escapeHtml(job.sector)}</span>` : ''}
                </div>
            </div>
        </div>
        <div class="job-card-actions">
            <button class="btn btn-primary" onclick="viewJobDetail('${job.job_id}')">
                View Details
            </button>
            ${JobTracker.isAuthenticated() ? `
                <button class="btn btn-secondary" onclick="toggleSaveJob('${job.job_id}', this)" 
                        data-saved="${isSaved}">
                    ${isSaved ? '✓ Saved' : 'Save'}
                </button>
                <button class="btn btn-primary" onclick="quickApply('${job.job_id}', this)" 
                        title="Quick Apply - Track this application">
                    ${JobTracker.renderIcon ? JobTracker.renderIcon('documentText', { size: 18, class: 'btn-icon' }) : ''}
                    <span>Quick Apply</span>
                </button>
            ` : ''}
            <a href="${escapeHtml(job.url)}" target="_blank" class="btn btn-primary" 
               onclick="event.stopPropagation()" title="Apply on company website">
                Apply
            </a>
        </div>
        <div class="job-card-hover-preview" style="display: none;">
            <div class="hover-preview-content">
                <p class="hover-preview-text">Click to view full details</p>
            </div>
        </div>
    `;
    
    // Make entire card clickable
    card.addEventListener('click', (e) => {
        if (!e.target.closest('button') && !e.target.closest('a')) {
            viewJobDetail(job.job_id);
        }
    });
    
    return card;
}

/**
 * View job details in modal
 */
async function viewJobDetail(jobId) {
    const modal = document.getElementById('job-modal');
    const modalTitle = document.getElementById('modal-job-title');
    const modalBody = document.getElementById('modal-body');
    const modalApplyLink = document.getElementById('modal-apply-link');
    const modalSaveBtn = document.getElementById('modal-save-btn');
    
    try {
        const job = await JobTracker.apiCall(`/jobs/${jobId}`);
        
        // Store job ID in modal for button handlers
        modal.dataset.jobId = jobId;
        
        modalTitle.textContent = job.title;
        modalApplyLink.href = job.url;
        
        const isSaved = savedJobIds.has(job.job_id);
        if (JobTracker.isAuthenticated()) {
            modalSaveBtn.style.display = 'inline-block';
            modalSaveBtn.textContent = isSaved ? '✓ Saved' : 'Save Job';
            modalSaveBtn.dataset.saved = isSaved;
            modalSaveBtn.onclick = () => toggleSaveJob(jobId, modalSaveBtn);
            
            // Show quick apply button
            const modalQuickApplyBtn = document.getElementById('modal-quick-apply-btn');
            if (modalQuickApplyBtn) {
                modalQuickApplyBtn.style.display = 'inline-block';
            }
        } else {
            modalSaveBtn.style.display = 'none';
            const modalQuickApplyBtn = document.getElementById('modal-quick-apply-btn');
            if (modalQuickApplyBtn) {
                modalQuickApplyBtn.style.display = 'none';
            }
        }
        
        modalBody.innerHTML = `
            <div class="modal-body-section">
                <h3>Company</h3>
                <p>${escapeHtml(job.company)}</p>
            </div>
            <div class="modal-body-section">
                <h3>Location</h3>
                <p>${escapeHtml(job.location || 'Not specified')} ${job.remote ? '(Remote)' : ''}</p>
            </div>
            ${job.sector ? `
                <div class="modal-body-section">
                    <h3>Sector</h3>
                    <p>${escapeHtml(job.sector)}</p>
                </div>
            ` : ''}
            ${job.description ? `
                <div class="modal-body-section">
                    <h3>Description</h3>
                    <p>${escapeHtml(job.description)}</p>
                </div>
            ` : ''}
            ${job.extra ? `
                <div class="modal-body-section">
                    <h3>Additional Information</h3>
                    <pre style="white-space: pre-wrap; font-family: inherit;">${escapeHtml(JSON.stringify(job.extra, null, 2))}</pre>
                </div>
            ` : ''}
            <div class="modal-body-section">
                <h3>Posted</h3>
                <p>${job.posted_at ? JobTracker.formatDate(job.posted_at) : 'Unknown'}</p>
            </div>
            ${job.is_new_grad ? `
                <div class="modal-body-section">
                    <span class="badge badge-new-grad">New Grad Position</span>
                </div>
            ` : ''}
        `;
        
        modal.classList.add('show');
        modal.style.display = 'flex';
    } catch (error) {
        console.error('Failed to load job details:', error);
        JobTracker.showNotification('Failed to load job details', 'error');
    }
}

/**
 * Toggle save/unsave job
 */
async function toggleSaveJob(jobId, buttonElement) {
    if (!JobTracker.isAuthenticated()) {
        JobTracker.showNotification('Please log in to save jobs', 'info');
        return;
    }
    
    const isSaved = savedJobIds.has(jobId);
    
    try {
        if (isSaved) {
            await JobTracker.apiCall(`/jobs/${jobId}/save`, { method: 'DELETE' });
            savedJobIds.delete(jobId);
            buttonElement.textContent = 'Save';
            buttonElement.dataset.saved = 'false';
            JobTracker.showNotification('Job unsaved', 'success');
        } else {
            await JobTracker.apiCall(`/jobs/${jobId}/save`, { method: 'POST' });
            savedJobIds.add(jobId);
            buttonElement.textContent = '✓ Saved';
            buttonElement.dataset.saved = 'true';
            JobTracker.showNotification('Job saved', 'success');
        }
        
        // Update all save buttons for this job
        document.querySelectorAll(`[onclick*="toggleSaveJob('${jobId}'"]`).forEach(btn => {
            btn.textContent = savedJobIds.has(jobId) ? '✓ Saved' : 'Save';
            btn.dataset.saved = savedJobIds.has(jobId);
        });
    } catch (error) {
        console.error('Failed to toggle save job:', error);
        JobTracker.showNotification('Failed to save/unsave job', 'error');
    }
}

/**
 * Update save buttons visibility
 */
function updateSaveButtons() {
    document.querySelectorAll('[data-saved]').forEach(btn => {
        const jobId = btn.getAttribute('onclick')?.match(/'([^']+)'/)?.[1];
        if (jobId && savedJobIds.has(jobId)) {
            btn.textContent = '✓ Saved';
            btn.dataset.saved = 'true';
        }
    });
}

/**
 * Update results header with count and summary
 */
function updateResultsHeader() {
    const resultsCount = document.getElementById('results-count');
    const resultsSummary = document.getElementById('results-summary');
    
    const start = totalJobs === 0 ? 0 : (currentPage - 1) * pageSize + 1;
    const end = Math.min(currentPage * pageSize, totalJobs);
    
    resultsCount.textContent = `${totalJobs.toLocaleString()} job${totalJobs !== 1 ? 's' : ''} found`;
    if (totalJobs > 0) {
        const pageInfo = `Page ${currentPage} of ${totalPages}`;
        const rangeInfo = `Showing ${start.toLocaleString()} - ${end.toLocaleString()} of ${totalJobs.toLocaleString()}`;
        resultsSummary.textContent = `${rangeInfo} • ${pageInfo}`;
    } else {
        resultsSummary.textContent = '';
    }
}

/**
 * Display pagination controls
 */
function displayPagination() {
    const pagination = document.getElementById('pagination');
    pagination.style.display = 'flex';
    pagination.innerHTML = '';
    
    // Previous button
    const prevBtn = document.createElement('button');
    prevBtn.className = 'pagination-btn';
    prevBtn.textContent = '← Previous';
    prevBtn.disabled = currentPage === 1;
    prevBtn.onclick = () => {
        if (currentPage > 1) {
            currentPage--;
            loadJobs();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };
    pagination.appendChild(prevBtn);
    
    // Page numbers
    const maxPages = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxPages / 2));
    let endPage = Math.min(totalPages, startPage + maxPages - 1);
    
    if (endPage - startPage < maxPages - 1) {
        startPage = Math.max(1, endPage - maxPages + 1);
    }
    
    if (startPage > 1) {
        const firstBtn = createPageButton(1);
        pagination.appendChild(firstBtn);
        if (startPage > 2) {
            const ellipsis = document.createElement('span');
            ellipsis.textContent = '...';
            ellipsis.className = 'pagination-info';
            pagination.appendChild(ellipsis);
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        pagination.appendChild(createPageButton(i));
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsis = document.createElement('span');
            ellipsis.textContent = '...';
            ellipsis.className = 'pagination-info';
            pagination.appendChild(ellipsis);
        }
        const lastBtn = createPageButton(totalPages);
        pagination.appendChild(lastBtn);
    }
    
    // Next button
    const nextBtn = document.createElement('button');
    nextBtn.className = 'pagination-btn';
    nextBtn.textContent = 'Next →';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.onclick = () => {
        if (currentPage < totalPages) {
            currentPage++;
            loadJobs();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        }
    };
    pagination.appendChild(nextBtn);
}

/**
 * Create a page number button
 */
function createPageButton(pageNum) {
    const btn = document.createElement('button');
    btn.className = 'pagination-btn';
    if (pageNum === currentPage) {
        btn.classList.add('active');
    }
    btn.textContent = pageNum.toString();
    btn.onclick = () => {
        currentPage = pageNum;
        loadJobs();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    return btn;
}

/**
 * Setup event listeners
 */
/**
 * Export jobs to CSV
 */
async function exportJobs() {
    try {
        const token = localStorage.getItem('session_token');
        if (!token) {
            JobTracker.showNotification('Please log in to export', 'error');
            return;
        }
        
        // Build query params from current filters
        updateFiltersFromUI();
        const params = new URLSearchParams();
        
        if (currentFilters.location) params.append('location', currentFilters.location);
        if (currentFilters.remote !== null) params.append('remote', currentFilters.remote.toString());
        if (currentFilters.company.length > 0) params.append('company', currentFilters.company.join(','));
        if (currentFilters.sector.length > 0) params.append('sector', currentFilters.sector.join(','));
        if (currentFilters.keywords) params.append('keywords', currentFilters.keywords);
        if (currentFilters.new_grad !== null) params.append('new_grad', currentFilters.new_grad.toString());
        
        const url = `/api/export/jobs/csv?${params.toString()}`;
        const response = await fetch(url, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Export failed');
        }
        
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `jobs_export_${new Date().toISOString().split('T')[0]}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(downloadUrl);
        
        JobTracker.showNotification('Jobs exported successfully', 'success');
    } catch (error) {
        console.error('Export failed:', error);
        JobTracker.showNotification('Failed to export jobs', 'error');
    }
}

/**
 * Save current search as a saved search/alert
 */
async function saveCurrentSearch() {
    if (!JobTracker.isAuthenticated()) {
        JobTracker.showNotification('Please log in to save searches', 'info');
        return;
    }
    
    updateFiltersFromUI();
    const searchInput = document.getElementById('search-input');
    const keywords = searchInput.value.trim();
    
    // Build filters object
    const filters = {
        keywords: keywords || undefined,
        location: currentFilters.location || undefined,
        remote: currentFilters.remote !== null ? currentFilters.remote : undefined,
        company: currentFilters.company.length > 0 ? currentFilters.company : undefined,
        sector: currentFilters.sector.length > 0 ? currentFilters.sector : undefined,
        new_grad: currentFilters.new_grad !== null ? currentFilters.new_grad : undefined
    };
    
    // Remove undefined values
    Object.keys(filters).forEach(key => {
        if (filters[key] === undefined) {
            delete filters[key];
        }
    });
    
    // Prompt for search name
    const searchName = prompt('Enter a name for this saved search:');
    if (!searchName || !searchName.trim()) {
        return;
    }
    
    try {
        await JobTracker.apiCall('/searches', {
            method: 'POST',
            body: JSON.stringify({
                name: searchName.trim(),
                filters: filters,
                notification_enabled: true
            })
        });
        
        JobTracker.showNotification('Search saved! You\'ll receive notifications when new jobs match.', 'success');
    } catch (error) {
        console.error('Failed to save search:', error);
        JobTracker.showNotification('Failed to save search', 'error');
    }
}

function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
    
    searchBtn.addEventListener('click', performSearch);
    
    // Filter inputs
    document.getElementById('filter-location').addEventListener('change', updateFiltersFromUI);
    document.getElementById('filter-remote').addEventListener('change', updateFiltersFromUI);
    document.getElementById('filter-new-grad').addEventListener('change', updateFiltersFromUI);
    
    // Apply filters button
    document.getElementById('apply-filters-btn').addEventListener('click', applyFilters);
    document.getElementById('reset-filters-btn').addEventListener('click', resetFilters);
    document.getElementById('clear-filters-btn').addEventListener('click', clearFilters);
    
    // Save search button
    const saveSearchBtn = document.getElementById('save-search-btn');
    if (saveSearchBtn) {
        saveSearchBtn.addEventListener('click', saveCurrentSearch);
    }
    
    // Export jobs button
    const exportJobsBtn = document.getElementById('export-jobs-btn');
    if (exportJobsBtn) {
        exportJobsBtn.addEventListener('click', exportJobs);
        // Show button if authenticated
        if (JobTracker.isAuthenticated()) {
            exportJobsBtn.style.display = 'inline-block';
        }
    }
    
    // Sort select
    document.getElementById('sort-select').addEventListener('change', (e) => {
        currentSort = e.target.value;
        loadJobs();
    });
    
    // Collapse filters button and mobile toggle
    const collapseFiltersBtn = document.getElementById('collapse-filters');
    if (collapseFiltersBtn) {
        // Restore previous collapse state from localStorage
        const savedState = localStorage.getItem('jobs_filters_collapsed');
        const sidebar = document.getElementById('filters-sidebar');
        if (sidebar && savedState === 'true') {
            sidebar.classList.add('collapsed');
            collapseFiltersBtn.textContent = '+';
        }
        
        collapseFiltersBtn.addEventListener('click', () => {
            const sidebar = document.getElementById('filters-sidebar');
            if (sidebar) {
                sidebar.classList.toggle('collapsed');
                const isCollapsed = sidebar.classList.contains('collapsed');
                collapseFiltersBtn.textContent = isCollapsed ? '+' : '−';
                // Persist state
                localStorage.setItem('jobs_filters_collapsed', isCollapsed ? 'true' : 'false');
            }
        });
    }

    const toggleFiltersBtn = document.getElementById('toggle-filters-btn');
    if (toggleFiltersBtn) {
        toggleFiltersBtn.addEventListener('click', () => {
            const sidebar = document.getElementById('filters-sidebar');
            if (!sidebar) return;
            const isOpen = sidebar.classList.toggle('open');
            toggleFiltersBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });
    }
    
    // Modal close
    document.getElementById('modal-close').addEventListener('click', closeModal);
    document.getElementById('modal-close-btn').addEventListener('click', closeModal);
    document.getElementById('job-modal').addEventListener('click', (e) => {
        if (e.target.id === 'job-modal') {
            closeModal();
        }
    });
    
    // Modal save button
    const modalSaveBtn = document.getElementById('modal-save-btn');
    if (modalSaveBtn) {
        modalSaveBtn.addEventListener('click', () => {
            const jobId = document.getElementById('job-modal').dataset.jobId;
            if (jobId) {
                toggleSaveJob(jobId, modalSaveBtn);
            }
        });
    }
    
    // Modal quick apply button
    const modalQuickApplyBtn = document.getElementById('modal-quick-apply-btn');
    if (modalQuickApplyBtn) {
        modalQuickApplyBtn.addEventListener('click', () => {
            const jobId = document.getElementById('job-modal').dataset.jobId;
            if (jobId) {
                quickApply(jobId, modalQuickApplyBtn);
            }
        });
    }
    
    // Debounced search
    const debouncedSearch = JobTracker.debounce(performSearch, 500);
    searchInput.addEventListener('input', () => {
        currentFilters.keywords = searchInput.value.trim();
        debouncedSearch();
    });
}

/**
 * Update filters from UI inputs
 */
function updateFiltersFromUI() {
    currentFilters.location = document.getElementById('filter-location').value.trim();
    
    const remoteValue = document.getElementById('filter-remote').value;
    currentFilters.remote = remoteValue === '' ? null : remoteValue === 'true';
    
    const newGradValue = document.getElementById('filter-new-grad').value;
    currentFilters.new_grad = newGradValue === '' ? null : newGradValue === 'true';
    
    const companySelect = document.getElementById('filter-company');
    currentFilters.company = Array.from(companySelect.selectedOptions)
        .map(opt => opt.value)
        .filter(v => v !== '');
    
    const sectorSelect = document.getElementById('filter-sector');
    currentFilters.sector = Array.from(sectorSelect.selectedOptions)
        .map(opt => opt.value)
        .filter(v => v !== '');
}

/**
 * Apply filters and reload jobs
 */
function applyFilters() {
    updateFiltersFromUI();
    currentPage = 1;
    loadJobs();
}

/**
 * Reset filters to defaults
 */
function resetFilters() {
    document.getElementById('search-input').value = '';
    document.getElementById('filter-location').value = '';
    document.getElementById('filter-remote').value = '';
    document.getElementById('filter-new-grad').value = '';
    document.getElementById('filter-company').selectedIndex = 0;
    document.getElementById('filter-sector').selectedIndex = 0;
    
    currentFilters = {
        keywords: '',
        location: '',
        remote: null,
        company: [],
        sector: [],
        new_grad: null
    };
    
    currentPage = 1;
    loadJobs();
}

/**
 * Clear all filters (alias for reset)
 */
function clearFilters() {
    resetFilters();
}

/**
 * Perform search
 */
function performSearch() {
    const searchInput = document.getElementById('search-input');
    currentFilters.keywords = searchInput.value.trim();
    currentPage = 1;
    loadJobs();
}

/**
 * Close job detail modal
 */
function closeModal() {
    const modal = document.getElementById('job-modal');
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
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

/**
 * Quick apply to a job (create application)
 */
async function quickApply(jobId, buttonElement) {
    if (!JobTracker.isAuthenticated()) {
        JobTracker.showNotification('Please log in to track applications', 'info');
        return;
    }
    
    // Disable button to prevent double-clicks
    if (buttonElement) {
        buttonElement.disabled = true;
        buttonElement.textContent = 'Applying...';
    }
    
    try {
        // Check if application already exists
        const apps = await JobTracker.apiCall('/applications?page_size=1000');
        const existingApp = apps.applications?.find(app => app.job_id === jobId);
        
        if (existingApp) {
            JobTracker.showNotification('Application already exists for this job', 'info');
            if (buttonElement) {
                buttonElement.disabled = false;
                buttonElement.textContent = '✓ Applied';
            }
            return;
        }
        
        // Try to get default template
        let templateData = {
            job_id: jobId,
            status: 'applied',
            application_method: 'Quick Apply',
            priority: 0
        };
        
        try {
            const defaultTemplate = await JobTracker.apiCall('/templates/default');
            if (defaultTemplate) {
                templateData.application_method = defaultTemplate.application_method || templateData.application_method;
                templateData.notes = defaultTemplate.default_notes;
                if (defaultTemplate.resume_id) {
                    templateData.resume_id = defaultTemplate.resume_id;
                }
                if (defaultTemplate.cover_letter_id) {
                    templateData.cover_letter_id = defaultTemplate.cover_letter_id;
                }
            }
        } catch (error) {
            // No template, use defaults
        }
        
        // Create application
        await JobTracker.apiCall('/applications', {
            method: 'POST',
            body: JSON.stringify(templateData)
        });
        
        JobTracker.showNotification(
            'Application tracked successfully!',
            'success',
            5000,
            '<button class="btn btn-link" type="button" onclick="window.location.href=\'/applications.html\'">View applications</button>'
        );
        if (buttonElement) {
            buttonElement.disabled = false;
            buttonElement.textContent = '✓ Applied';
            buttonElement.classList.add('applied');
        }
    } catch (error) {
        console.error('Failed to create application:', error);
        JobTracker.showNotification(error.message || 'Failed to track application', 'error');
        if (buttonElement) {
            buttonElement.disabled = false;
            if (buttonElement) {
                buttonElement.innerHTML = `${JobTracker.renderIcon ? JobTracker.renderIcon('documentText', { size: 18, class: 'btn-icon' }) : ''}<span>Quick Apply</span>`;
            }
        }
    }
}

// Make functions available globally for onclick handlers
window.viewJobDetail = viewJobDetail;
window.toggleSaveJob = toggleSaveJob;
window.quickApply = quickApply;
window.clearFilters = clearFilters;
window.loadJobs = loadJobs;
