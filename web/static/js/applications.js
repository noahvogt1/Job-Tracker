/**
 * Applications Page JavaScript
 * 
 * Handles application tracking, Kanban board, timeline, calendar views,
 * and management of interviews and offers.
 */

// State management
let applications = [];
let currentView = 'kanban';
let currentMonth = new Date().getMonth();
let currentYear = new Date().getFullYear();
let currentApplicationId = null;

// Status columns for Kanban board
const STATUS_COLUMNS = [
    { id: 'applied', label: 'Applied', icon: 'documentText' },
    { id: 'under_review', label: 'Under Review', icon: 'eye' },
    { id: 'interviewing', label: 'Interviewing', icon: 'briefcase' },
    { id: 'offer', label: 'Offer', icon: 'gift' },
    { id: 'rejected', label: 'Rejected', icon: 'xCircle' },
    { id: 'withdrawn', label: 'Withdrawn', icon: 'arrowPath' }
];

// Initialize page
document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication status
    try {
        const authCheck = await JobTracker.apiCall('/auth/check');
        if (!authCheck.authenticated) {
            // Redirect to login with return URL
            window.location.href = `/login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
            return;
        }
    } catch (error) {
        // If auth check fails, redirect to login
        window.location.href = `/login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
        return;
    }
    
    // Render icons
    renderPageIcons();
    
    setupEventListeners();
    await loadApplications();
    await loadStats();
});

/**
 * Render icons on page load
 */
function renderPageIcons() {
    if (!window.JobTracker || !window.JobTracker.renderIcon) return;
    
    // Stat icons
    const statIconTotal = document.getElementById('stat-icon-total');
    const statIconInterviews = document.getElementById('stat-icon-interviews');
    const statIconOffers = document.getElementById('stat-icon-offers');
    const statIconSuccessRate = document.getElementById('stat-icon-success-rate');
    
    if (statIconTotal) statIconTotal.innerHTML = window.JobTracker.renderIcon('documentText', { size: 48 });
    if (statIconInterviews) statIconInterviews.innerHTML = window.JobTracker.renderIcon('calendar', { size: 48 });
    if (statIconOffers) statIconOffers.innerHTML = window.JobTracker.renderIcon('gift', { size: 48 });
    if (statIconSuccessRate) statIconSuccessRate.innerHTML = window.JobTracker.renderIcon('chartBar', { size: 48 });
    
    // View toggle icons
    const viewIconKanban = document.getElementById('view-icon-kanban');
    const viewIconTimeline = document.getElementById('view-icon-timeline');
    const viewIconCalendar = document.getElementById('view-icon-calendar');
    
    if (viewIconKanban) viewIconKanban.innerHTML = window.JobTracker.renderIcon('documentText', { size: 20 });
    if (viewIconTimeline) viewIconTimeline.innerHTML = window.JobTracker.renderIcon('calendar', { size: 20 });
    if (viewIconCalendar) viewIconCalendar.innerHTML = window.JobTracker.renderIcon('calendar', { size: 20 });
    
    // Empty state icon
    const emptyIcon = document.getElementById('empty-icon-applications');
    if (emptyIcon) emptyIcon.innerHTML = window.JobTracker.renderIcon('inbox', { size: 64 });
}

/**
 * Show authentication required message
 */
function showAuthRequired() {
    const container = document.querySelector('.applications-container');
    const lockIcon = window.JobTracker && window.JobTracker.renderIcon 
        ? window.JobTracker.renderIcon('lockClosed', { size: 64 })
        : '';
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">${lockIcon}</div>
            <h3>Authentication Required</h3>
            <p>Please log in to track your applications.</p>
            <button class="btn btn-primary" onclick="window.location.href='/login.html?redirect=' + encodeURIComponent(window.location.pathname)">Login</button>
        </div>
    `;
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // View toggle buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Don't allow view switching if there are no applications
            if (applications.length === 0) {
                return;
            }
            const view = btn.dataset.view;
            switchView(view);
        });
    });
    
    // New application button
    document.getElementById('new-application-btn').addEventListener('click', showNewApplicationModal);
    
    // Job search functionality
    setupJobSearch();
    
    // Modal close buttons
    document.getElementById('new-app-modal-close').addEventListener('click', closeNewApplicationModal);
    document.getElementById('new-app-cancel-btn').addEventListener('click', closeNewApplicationModal);
    document.getElementById('detail-modal-close').addEventListener('click', closeApplicationDetailModal);
    document.getElementById('detail-close-btn').addEventListener('click', closeApplicationDetailModal);
    document.getElementById('interview-modal-close').addEventListener('click', closeInterviewModal);
    document.getElementById('interview-cancel-btn').addEventListener('click', closeInterviewModal);
    document.getElementById('offer-modal-close').addEventListener('click', closeOfferModal);
    document.getElementById('offer-cancel-btn').addEventListener('click', closeOfferModal);
    
    // Form submissions
    document.getElementById('new-app-submit-btn').addEventListener('click', createApplication);
    document.getElementById('interview-submit-btn').addEventListener('click', saveInterview);
    document.getElementById('offer-submit-btn').addEventListener('click', saveOffer);
    
    // Detail edit button
    document.getElementById('detail-edit-btn').addEventListener('click', () => {
        if (currentApplicationId) {
            showEditApplicationModal(currentApplicationId);
        }
    });
    
    // Calendar navigation
    document.getElementById('calendar-prev-month').addEventListener('click', () => {
        currentMonth--;
        if (currentMonth < 0) {
            currentMonth = 11;
            currentYear--;
        }
        renderCalendar();
    });
    
    document.getElementById('calendar-next-month').addEventListener('click', () => {
        currentMonth++;
        if (currentMonth > 11) {
            currentMonth = 0;
            currentYear++;
        }
        renderCalendar();
    });
    
    // Detail tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchDetailTab(tab);
        });
    });
    
    // Close modals on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('show');
                setTimeout(() => {
                    modal.style.display = 'none';
                }, 300);
            }
        });
    });
}

/**
 * Load applications from API
 */
async function loadApplications() {
    const loadingState = document.getElementById('loading-state');
    const emptyState = document.getElementById('empty-state');
    
    loadingState.style.display = 'flex';
    emptyState.style.display = 'none';
    
    try {
        const data = await JobTracker.apiCall('/applications?page_size=1000');
        applications = data.applications || [];
        
        // Load interviews and offers only if calendar view is active
        if (currentView === 'calendar') {
            await loadInterviewsAndOffers();
        }
        
        loadingState.style.display = 'none';
        
        if (applications.length === 0) {
            emptyState.style.display = 'block';
            // Hide view toggle buttons when no applications
            const viewToggle = document.querySelector('.view-toggle');
            if (viewToggle) {
                viewToggle.style.display = 'none';
            }
            // Hide all view content
            document.querySelectorAll('.view-content').forEach(content => {
                content.style.display = 'none';
                content.classList.remove('active');
            });
        } else {
            // Show view toggle buttons when applications exist
            const viewToggle = document.querySelector('.view-toggle');
            if (viewToggle) {
                viewToggle.style.display = 'flex';
            }
            renderCurrentView();
        }
    } catch (error) {
        console.error('Failed to load applications:', error);
        loadingState.style.display = 'none';
        JobTracker.showNotification('Failed to load applications', 'error');
    }
}

/**
 * Load interviews and offers for calendar view
 */
async function loadInterviewsAndOffers() {
    // Load upcoming interviews
    try {
        const upcomingData = await JobTracker.apiCall('/applications/upcoming/interviews?days=90');
        const interviewMap = new Map();
        
        upcomingData.forEach(item => {
            if (!interviewMap.has(item.application_id)) {
                interviewMap.set(item.application_id, []);
            }
            interviewMap.get(item.application_id).push(item.interview);
        });
        
        // Attach interviews to applications
        applications.forEach(app => {
            app.interviews = interviewMap.get(app.application_id) || [];
        });
    } catch (error) {
        console.error('Failed to load interviews:', error);
    }
    
    // Load offers for applications with offer status
    const offerApps = applications.filter(app => app.status === 'offer');
    for (let app of offerApps) {
        try {
            const appDetail = await JobTracker.apiCall(`/applications/${app.application_id}`);
            app.offer = appDetail.offer || null;
        } catch (error) {
            console.error(`Failed to load offer for application ${app.application_id}:`, error);
            app.offer = null;
        }
    }
}

/**
 * Load application statistics
 */
async function loadStats() {
    try {
        const stats = await JobTracker.apiCall('/applications/stats');
        
        document.getElementById('stat-total').textContent = stats.total_applications || 0;
        document.getElementById('stat-interviews').textContent = stats.upcoming_interviews || 0;
        document.getElementById('stat-offers').textContent = stats.total_offers || 0;
        document.getElementById('stat-success-rate').textContent = `${stats.success_rate || 0}%`;
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

/**
 * Switch between views (Kanban, Timeline, Calendar)
 */
async function switchView(view) {
    // Don't switch views if there are no applications
    if (applications.length === 0) {
        return;
    }
    
    currentView = view;
    
    // Hide empty state when switching views
    const emptyState = document.getElementById('empty-state');
    if (emptyState) {
        emptyState.style.display = 'none';
    }
    
    // Update buttons
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.view === view);
    });
    
    // Update content
    document.querySelectorAll('.view-content').forEach(content => {
        content.classList.toggle('active', content.id === `${view}-view`);
        if (content.id === `${view}-view`) {
            content.style.display = 'block';
        } else {
            content.style.display = 'none';
        }
    });
    
    // Load additional data if needed for calendar view
    if (view === 'calendar') {
        await loadInterviewsAndOffers();
    }
    
    // Render appropriate view
    if (view === 'kanban') {
        renderKanbanBoard();
    } else if (view === 'timeline') {
        renderTimeline();
    } else if (view === 'calendar') {
        renderCalendar();
    }
}

/**
 * Render Kanban board
 */
function renderKanbanBoard() {
    const board = document.getElementById('kanban-board');
    board.innerHTML = '';
    
    STATUS_COLUMNS.forEach(column => {
        const columnApps = applications.filter(app => app.status === column.id);
        
        const columnEl = document.createElement('div');
        columnEl.className = 'kanban-column';
        columnEl.dataset.status = column.id;
        
        const columnIcon = window.JobTracker && window.JobTracker.renderIcon 
            ? window.JobTracker.renderIcon(column.icon, { size: 20 })
            : '';
        columnEl.innerHTML = `
            <div class="kanban-column-header">
                <div class="kanban-column-title">
                    <span class="kanban-column-icon">${columnIcon}</span>
                    <span>${column.label}</span>
                </div>
                <span class="kanban-column-count">${columnApps.length}</span>
            </div>
            <div class="kanban-column-content" data-status="${column.id}">
                ${columnApps.map(app => createKanbanCard(app)).join('')}
            </div>
        `;
        
        board.appendChild(columnEl);
    });
    
    // Setup drag and drop
    setupDragAndDrop();
}

/**
 * Create a Kanban card element
 */
function createKanbanCard(application) {
    const job = application.job || {};
    const priorityClass = application.priority === 2 ? 'priority-very-high' : 
                          application.priority === 1 ? 'priority-high' : '';
    
    return `
        <div class="kanban-card ${priorityClass}" 
             data-application-id="${application.application_id}"
             draggable="true">
            <div class="kanban-card-header">
                <h4 class="kanban-card-title">${escapeHtml(job.title || 'Unknown Title')}</h4>
            </div>
            <p class="kanban-card-company">${escapeHtml(job.company || 'Unknown Company')}</p>
            <div class="kanban-card-meta">
                ${application.applied_at ? `<span>${JobTracker.renderIcon ? JobTracker.renderIcon('calendar', { size: 16, class: 'inline-icon' }) : ''} ${JobTracker.formatDate(application.applied_at)}</span>` : ''}
                ${application.priority > 0 ? `<span>${JobTracker.renderIcon ? JobTracker.renderIcon('star', { size: 16, class: 'inline-icon' }) : ''} Priority ${application.priority}</span>` : ''}
            </div>
            <div class="kanban-card-actions">
                <button class="btn btn-primary btn-sm" onclick="viewApplicationDetail(${application.application_id})">
                    View
                </button>
                ${application.status === 'interviewing' ? `
                    <button class="btn btn-secondary btn-sm" onclick="showInterviewModal(${application.application_id})">
                        + Interview
                    </button>
                ` : ''}
                ${application.status === 'offer' ? `
                    <button class="btn btn-secondary btn-sm" onclick="showOfferModal(${application.application_id})">
                        + Offer
                    </button>
                ` : ''}
            </div>
        </div>
    `;
}

/**
 * Setup drag and drop for status changes
 */
function setupDragAndDrop() {
    const cards = document.querySelectorAll('.kanban-card');
    const columns = document.querySelectorAll('.kanban-column-content');
    
    cards.forEach(card => {
        card.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('application-id', card.dataset.applicationId);
            card.classList.add('dragging');
        });
        
        card.addEventListener('dragend', () => {
            card.classList.remove('dragging');
        });
    });
    
    columns.forEach(column => {
        column.addEventListener('dragover', (e) => {
            e.preventDefault();
            column.parentElement.classList.add('drag-over');
        });
        
        column.addEventListener('dragleave', () => {
            column.parentElement.classList.remove('drag-over');
        });
        
        column.addEventListener('drop', async (e) => {
            e.preventDefault();
            column.parentElement.classList.remove('drag-over');
            
            const applicationId = parseInt(e.dataTransfer.getData('application-id'));
            const newStatus = column.dataset.status;
            
            await updateApplicationStatus(applicationId, newStatus);
        });
    });
}

/**
 * Update application status
 */
async function updateApplicationStatus(applicationId, newStatus) {
    try {
        await JobTracker.apiCall(`/applications/${applicationId}`, {
            method: 'PATCH',
            body: JSON.stringify({ status: newStatus })
        });
        
        JobTracker.showNotification('Application status updated', 'success');
        await loadApplications();
        await loadStats();
    } catch (error) {
        console.error('Failed to update status:', error);
        JobTracker.showNotification('Failed to update status', 'error');
    }
}

/**
 * Render timeline view
 */
function renderTimeline() {
    const container = document.getElementById('timeline-container');
    
    if (applications.length === 0) {
        container.innerHTML = '<p class="text-center">No applications to display</p>';
        return;
    }
    
    // Sort by updated_at descending
    const sortedApps = [...applications].sort((a, b) => {
        return new Date(b.updated_at) - new Date(a.updated_at);
    });
    
    container.innerHTML = sortedApps.map(app => {
        const job = app.job || {};
        return `
            <div class="timeline-item">
                <div class="timeline-date">
                    <div class="timeline-dot"></div>
                    <div>${JobTracker.formatDate(app.updated_at)}</div>
                </div>
                <div class="timeline-content">
                    <div class="timeline-content-header">
                        <div>
                            <h3 class="timeline-content-title">${escapeHtml(job.title || 'Unknown')}</h3>
                            <p class="timeline-content-company">${escapeHtml(job.company || 'Unknown Company')}</p>
                        </div>
                        <span class="status-badge status-${app.status}">${app.status.replace('_', ' ')}</span>
                    </div>
                    <div class="timeline-content-body">
                        <p>${escapeHtml(app.notes || 'No notes')}</p>
                        <div style="margin-top: 1rem;">
                            <button class="btn btn-primary btn-sm" onclick="viewApplicationDetail(${app.application_id})">
                                View Details
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render calendar view
 */
function renderCalendar() {
    const monthYearEl = document.getElementById('calendar-month-year');
    const gridEl = document.getElementById('calendar-grid');
    
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                       'July', 'August', 'September', 'October', 'November', 'December'];
    
    monthYearEl.textContent = `${monthNames[currentMonth]} ${currentYear}`;
    
    // Get first day of month and number of days
    const firstDay = new Date(currentYear, currentMonth, 1).getDay();
    const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
    const prevMonthDays = new Date(currentYear, currentMonth, 0).getDate();
    
    // Day headers
    const dayHeaders = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    gridEl.innerHTML = dayHeaders.map(day => 
        `<div class="calendar-day-header">${day}</div>`
    ).join('');
    
    // Previous month days
    for (let i = firstDay - 1; i >= 0; i--) {
        const day = prevMonthDays - i;
        gridEl.appendChild(createCalendarDay(day, true, currentMonth - 1, currentYear));
    }
    
    // Current month days
    for (let day = 1; day <= daysInMonth; day++) {
        gridEl.appendChild(createCalendarDay(day, false, currentMonth, currentYear));
    }
    
    // Next month days to fill grid
    const totalCells = gridEl.children.length;
    const remainingCells = 42 - totalCells; // 6 weeks * 7 days
    for (let day = 1; day <= remainingCells; day++) {
        gridEl.appendChild(createCalendarDay(day, true, currentMonth + 1, currentYear));
    }
}

/**
 * Create a calendar day element
 */
function createCalendarDay(day, isOtherMonth, month, year) {
    const dayEl = document.createElement('div');
    dayEl.className = 'calendar-day';
    if (isOtherMonth) {
        dayEl.classList.add('other-month');
    }
    
    const date = new Date(year, month, day);
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
        dayEl.classList.add('today');
    }
    
    // Get events for this day
    const events = getEventsForDate(date);
    
    dayEl.innerHTML = `
        <div class="calendar-day-number">${day}</div>
        <div class="calendar-day-events">
            ${events.map(event => `
                <div class="calendar-event ${event.type}" title="${escapeHtml(event.title)}">
                    ${escapeHtml(event.title)}
                </div>
            `).join('')}
        </div>
    `;
    
    if (events.length > 0) {
        dayEl.addEventListener('click', () => {
            showDayEvents(date, events);
        });
    }
    
    return dayEl;
}

/**
 * Get events (interviews, deadlines) for a specific date
 */
function getEventsForDate(date) {
    const events = [];
    const dateStr = date.toISOString().split('T')[0];
    
    applications.forEach(app => {
        // Check interviews
        if (app.interviews) {
            app.interviews.forEach(interview => {
                if (interview.scheduled_at) {
                    const interviewDate = new Date(interview.scheduled_at).toISOString().split('T')[0];
                    if (interviewDate === dateStr) {
                        events.push({
                            type: 'interview',
                            title: `${app.job?.company || 'Company'}: ${interview.interview_type}`,
                            interview: interview,
                            application: app
                        });
                    }
                }
            });
        }
        
        // Check offer deadlines
        if (app.offer && app.offer.decision_deadline) {
            const deadlineDate = new Date(app.offer.decision_deadline).toISOString().split('T')[0];
            if (deadlineDate === dateStr) {
                events.push({
                    type: 'deadline',
                    title: `Offer Deadline: ${app.job?.company || 'Company'}`,
                    offer: app.offer,
                    application: app
                });
            }
        }
    });
    
    return events;
}

/**
 * Show events for a specific day
 */
function showDayEvents(date, events) {
    // This could open a modal or highlight the events
    console.log('Events for', date, events);
    // For now, just show a notification
    JobTracker.showNotification(`${events.length} event(s) on ${date.toLocaleDateString()}`, 'info');
}

/**
 * Setup job search functionality
 */
function setupJobSearch() {
    const jobInput = document.getElementById('app-job-id');
    const searchResults = document.getElementById('job-search-results');
    let searchTimeout = null;
    
    if (!jobInput || !searchResults) return;
    
    // Search as user types
    jobInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        
        // Clear stored job ID when user types
        jobInput.dataset.selectedJobId = '';
        
        // Clear timeout if user is still typing
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }
        
        // If query is empty, hide results
        if (!query || query.length < 2) {
            searchResults.classList.remove('show');
            searchResults.innerHTML = '';
            return;
        }
        
        // Debounce search
        searchTimeout = setTimeout(async () => {
            await searchJobs(query);
        }, 300);
    });
    
    // Hide results when clicking outside
    document.addEventListener('click', (e) => {
        if (!jobInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.classList.remove('show');
        }
    });
    
    /**
     * Search for jobs
     */
    async function searchJobs(query) {
        try {
            // Check if it's a job ID (alphanumeric, no spaces)
            if (/^[a-zA-Z0-9_-]+$/.test(query) && query.length > 5) {
                // Try to fetch job by ID
                try {
                    const job = await JobTracker.apiCall(`/jobs/${query}`);
                    displayJobResult(job, true);
                    return;
                } catch (error) {
                    // If not found by ID, continue with search
                }
            }
            
            // Search by keywords
            const data = await JobTracker.apiCall(`/jobs?keywords=${encodeURIComponent(query)}&page_size=10`);
            
            if (data.jobs && data.jobs.length > 0) {
                displayJobResults(data.jobs);
            } else {
                searchResults.innerHTML = '<div class="job-search-item" style="padding: 1rem; text-align: center; color: var(--text-secondary);">No jobs found</div>';
                searchResults.classList.add('show');
            }
        } catch (error) {
            console.error('Job search error:', error);
            searchResults.innerHTML = '<div class="job-search-item" style="padding: 1rem; text-align: center; color: var(--error-color);">Error searching jobs</div>';
            searchResults.classList.add('show');
        }
    }
    
    /**
     * Display single job result (when found by ID)
     */
    function displayJobResult(job, isExactMatch = false) {
        searchResults.innerHTML = `
            <div class="job-search-item" data-job-id="${job.job_id}">
                <div class="job-search-item-title">${escapeHtml(job.title)}</div>
                <div class="job-search-item-company">${escapeHtml(job.company)}${job.location ? ' • ' + escapeHtml(job.location) : ''}</div>
            </div>
        `;
        searchResults.classList.add('show');
        
        // Add click handler
        const item = searchResults.querySelector('.job-search-item');
        if (item) {
            item.addEventListener('click', () => {
                jobInput.dataset.selectedJobId = job.job_id;
                jobInput.value = `${job.title} - ${job.company}`;
                searchResults.classList.remove('show');
            });
        }
        
        // Auto-select if exact match
        if (isExactMatch) {
            jobInput.dataset.selectedJobId = job.job_id;
            jobInput.value = `${job.title} - ${job.company}`;
        }
    }
    
    /**
     * Display multiple job results
     */
    function displayJobResults(jobs) {
        searchResults.innerHTML = jobs.map(job => `
            <div class="job-search-item" data-job-id="${job.job_id}">
                <div class="job-search-item-title">${escapeHtml(job.title)}</div>
                <div class="job-search-item-company">${escapeHtml(job.company)}${job.location ? ' • ' + escapeHtml(job.location) : ''}</div>
            </div>
        `).join('');
        
        // Add click handlers
        searchResults.querySelectorAll('.job-search-item').forEach(item => {
            item.addEventListener('click', () => {
                const jobId = item.dataset.jobId;
                const job = jobs.find(j => j.job_id === jobId);
                if (job) {
                    jobInput.dataset.selectedJobId = jobId;
                    jobInput.value = `${job.title} - ${job.company}`;
                    searchResults.classList.remove('show');
                }
            });
        });
        
        searchResults.classList.add('show');
    }
    
}

/**
 * Show new application modal
 */
function showNewApplicationModal() {
    const modal = document.getElementById('new-application-modal');
    modal.style.display = 'flex';
    modal.classList.add('show');
    
    // Reset form
    document.getElementById('new-application-form').reset();
    document.getElementById('app-status').value = 'applied';
    document.getElementById('app-priority').value = '0';
    
    // Clear job search results
    const searchResults = document.getElementById('job-search-results');
    if (searchResults) {
        searchResults.classList.remove('show');
        searchResults.innerHTML = '';
    }
    
    // Clear selected job ID
    const jobInput = document.getElementById('app-job-id');
    if (jobInput) {
        jobInput.dataset.selectedJobId = '';
    }
    
    // Focus on job input
    setTimeout(() => {
        document.getElementById('app-job-id').focus();
    }, 100);
}

/**
 * Close new application modal
 */
function closeNewApplicationModal() {
    const modal = document.getElementById('new-application-modal');
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
        // Reset form
        document.getElementById('new-application-form').reset();
        document.getElementById('app-job-id').disabled = false;
        const submitBtn = document.getElementById('new-app-submit-btn');
        submitBtn.dataset.editMode = 'false';
        delete submitBtn.dataset.applicationId;
        submitBtn.textContent = 'Create Application';
        const modalTitle = modal.querySelector('.modal-header h2');
        if (modalTitle) modalTitle.textContent = 'New Application';
    }, 300);
}

/**
 * Create a new application (or update if in edit mode)
 */
async function createApplication() {
    const submitBtn = document.getElementById('new-app-submit-btn');
    const isEdit = submitBtn.dataset.editMode === 'true';
    const applicationId = submitBtn.dataset.applicationId;
    
    if (isEdit && applicationId) {
        await updateApplication(parseInt(applicationId));
        return;
    }
    
    const form = document.getElementById('new-application-form');
    const jobInput = document.getElementById('app-job-id');
    const jobInputValue = jobInput.value.trim();
    
    if (!jobInputValue) {
        JobTracker.showNotification('Job is required', 'error');
        return;
    }
    
    // Extract job ID from input
    let jobId = jobInput.dataset.selectedJobId;
    
    if (!jobId) {
        if (/^[a-zA-Z0-9_-]+$/.test(jobInputValue) && jobInputValue.length > 5) {
            jobId = jobInputValue;
        } else {
            if (jobInputValue.includes(' - ')) {
                const parts = jobInputValue.split(' - ');
                try {
                    const searchData = await JobTracker.apiCall(`/jobs?keywords=${encodeURIComponent(parts[0])}&page_size=1`);
                    if (searchData.jobs && searchData.jobs.length > 0) {
                        jobId = searchData.jobs[0].job_id;
                    } else {
                        JobTracker.showNotification('Could not find job. Please select from search results or enter a job ID.', 'error');
                        return;
                    }
                } catch (error) {
                    console.error('Error finding job:', error);
                    JobTracker.showNotification('Could not find job. Please select from search results or enter a job ID.', 'error');
                    return;
                }
            } else {
                JobTracker.showNotification('Please select a job from the search results or enter a job ID.', 'error');
                return;
            }
        }
    }
    
    const formData = {
        job_id: jobId,
        status: document.getElementById('app-status').value || 'applied',
        priority: parseInt(document.getElementById('app-priority').value) || 0
    };
    
    const method = document.getElementById('app-method').value.trim();
    if (method) {
        formData.application_method = method;
    }
    
    const url = document.getElementById('app-url').value.trim();
    if (url) {
        formData.application_url = url;
    }
    
    const notes = document.getElementById('app-notes').value.trim();
    if (notes) {
        formData.notes = notes;
    }
    
    try {
        await JobTracker.apiCall('/applications', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        JobTracker.showNotification('Application created successfully', 'success');
        closeNewApplicationModal();
        await loadApplications();
        await loadStats();
        
        if (applications.length > 0) {
            const viewToggle = document.querySelector('.view-toggle');
            if (viewToggle) {
                viewToggle.style.display = 'flex';
            }
            const emptyState = document.getElementById('empty-state');
            if (emptyState) {
                emptyState.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to create application:', error);
        JobTracker.showNotification(error.message || 'Failed to create application', 'error');
    }
}

/**
 * Update application
 */
async function updateApplication(applicationId) {
    const formData = {
        status: document.getElementById('app-status').value || 'applied',
        priority: parseInt(document.getElementById('app-priority').value) || 0
    };
    
    const method = document.getElementById('app-method').value.trim();
    if (method) {
        formData.application_method = method;
    }
    
    const url = document.getElementById('app-url').value.trim();
    if (url) {
        formData.application_url = url;
    }
    
    const notes = document.getElementById('app-notes').value.trim();
    if (notes) {
        formData.notes = notes;
    }
    
    try {
        await JobTracker.apiCall(`/applications/${applicationId}`, {
            method: 'PUT',
            body: JSON.stringify(formData)
        });
        
        JobTracker.showNotification('Application updated successfully', 'success');
        closeNewApplicationModal();
        
        // Reset form state
        const submitBtn = document.getElementById('new-app-submit-btn');
        submitBtn.dataset.editMode = 'false';
        delete submitBtn.dataset.applicationId;
        submitBtn.textContent = 'Create Application';
        const modalTitle = document.getElementById('new-application-modal').querySelector('.modal-header h2');
        if (modalTitle) modalTitle.textContent = 'New Application';
        
        await loadApplications();
        await loadStats();
        
        if (currentApplicationId === applicationId) {
            await viewApplicationDetail(applicationId);
        }
    } catch (error) {
        console.error('Failed to update application:', error);
        JobTracker.showNotification(error.message || 'Failed to update application', 'error');
    }
}

/**
 * Show edit application modal
 */
async function showEditApplicationModal(applicationId) {
    try {
        const data = await JobTracker.apiCall(`/applications/${applicationId}`);
        const app = data.application;
        
        // Populate the new application form with existing data
        document.getElementById('app-job-id').value = app.job_id || '';
        document.getElementById('app-job-id').disabled = true; // Don't allow changing job
        document.getElementById('app-status').value = app.status || 'applied';
        document.getElementById('app-method').value = app.application_method || '';
        document.getElementById('app-url').value = app.application_url || '';
        document.getElementById('app-notes').value = app.notes || '';
        document.getElementById('app-priority').value = app.priority || 0;
        
        // Change modal title and submit button
        const modal = document.getElementById('new-application-modal');
        const modalTitle = modal.querySelector('.modal-header h2');
        const submitBtn = document.getElementById('new-app-submit-btn');
        
        if (modalTitle) modalTitle.textContent = 'Edit Application';
        if (submitBtn) {
            submitBtn.textContent = 'Update Application';
            submitBtn.dataset.editMode = 'true';
            submitBtn.dataset.applicationId = applicationId;
        }
        
        // Show modal
        modal.style.display = 'flex';
        modal.classList.add('show');
    } catch (error) {
        console.error('Failed to load application for editing:', error);
        JobTracker.showNotification('Failed to load application', 'error');
    }
}

/**
 * View application details
 */
async function viewApplicationDetail(applicationId) {
    try {
        const data = await JobTracker.apiCall(`/applications/${applicationId}`);
        currentApplicationId = applicationId;
        
        const modal = document.getElementById('application-detail-modal');
        const app = data.application;
        const job = data.job || {};
        
        document.getElementById('detail-app-title').textContent = 
            `${job.title || 'Application'} - ${job.company || 'Unknown'}`;
        
        // Render overview
        renderApplicationOverview(data);
        
        // Render timeline
        renderApplicationTimeline(data.timeline || []);
        
        // Render interviews
        renderApplicationInterviews(data.interviews || []);
        
        // Render offer
        renderApplicationOffer(data.offer);
        
        modal.style.display = 'flex';
        modal.classList.add('show');
    } catch (error) {
        console.error('Failed to load application details:', error);
        JobTracker.showNotification('Failed to load application details', 'error');
    }
}

/**
 * Render application overview
 */
function renderApplicationOverview(data) {
    const app = data.application;
    const job = data.job || {};
    
    document.getElementById('detail-overview').innerHTML = `
        <div class="detail-section">
            <h3>Application Information</h3>
            <div class="detail-field">
                <div class="detail-field-label">Status</div>
                <div class="detail-field-value">
                    <span class="status-badge status-${app.status}">${app.status.replace('_', ' ')}</span>
                </div>
            </div>
            <div class="detail-field">
                <div class="detail-field-label">Applied Date</div>
                <div class="detail-field-value">${app.applied_at ? JobTracker.formatDateTime(app.applied_at) : 'Not set'}</div>
            </div>
            <div class="detail-field">
                <div class="detail-field-label">Application Method</div>
                <div class="detail-field-value">${app.application_method || 'Not specified'}</div>
            </div>
            ${app.application_url ? `
                <div class="detail-field">
                    <div class="detail-field-label">Application URL</div>
                    <div class="detail-field-value">
                        <a href="${escapeHtml(app.application_url)}" target="_blank">View Application</a>
                    </div>
                </div>
            ` : ''}
            <div class="detail-field">
                <div class="detail-field-label">Priority</div>
                <div class="detail-field-value">${app.priority === 2 ? 'Very High' : app.priority === 1 ? 'High' : 'Normal'}</div>
            </div>
        </div>
        <div class="detail-section">
            <h3>Job Information</h3>
            <div class="detail-field">
                <div class="detail-field-label">Company</div>
                <div class="detail-field-value">${escapeHtml(job.company || 'Unknown')}</div>
            </div>
            <div class="detail-field">
                <div class="detail-field-label">Title</div>
                <div class="detail-field-value">${escapeHtml(job.title || 'Unknown')}</div>
            </div>
            <div class="detail-field">
                <div class="detail-field-label">Location</div>
                <div class="detail-field-value">${escapeHtml(job.location || 'Not specified')}</div>
            </div>
            ${job.url ? `
                <div class="detail-field">
                    <div class="detail-field-label">Job URL</div>
                    <div class="detail-field-value">
                        <a href="${escapeHtml(job.url)}" target="_blank">View Job Posting</a>
                    </div>
                </div>
            ` : ''}
        </div>
        ${app.notes ? `
            <div class="detail-section">
                <h3>Notes</h3>
                <p>${escapeHtml(app.notes)}</p>
            </div>
        ` : ''}
    `;
}

/**
 * Render application timeline
 */
function renderApplicationTimeline(timeline) {
    const container = document.getElementById('detail-timeline');
    
    if (timeline.length === 0) {
        container.innerHTML = '<p>No timeline events yet.</p>';
        return;
    }
    
    container.innerHTML = timeline.map(event => {
        const eventData = event.event_data || {};
        let eventDescription = '';
        
        switch (event.event_type) {
            case 'created':
                eventDescription = `Application created with status: ${eventData.status || 'applied'}`;
                break;
            case 'status_changed':
                eventDescription = `Status changed from ${eventData.old_status || 'unknown'} to ${eventData.new_status || 'unknown'}`;
                break;
            case 'interview_scheduled':
                eventDescription = `Interview scheduled: ${eventData.interview_type || 'Interview'}`;
                break;
            case 'offer_received':
                eventDescription = `Offer received${eventData.salary_amount ? ` - $${eventData.salary_amount}` : ''}`;
                break;
            default:
                eventDescription = event.event_type.replace('_', ' ');
        }
        
        return `
            <div class="timeline-item">
                <div class="timeline-date">
                    <div class="timeline-dot"></div>
                    <div>${JobTracker.formatDateTime(event.created_at)}</div>
                </div>
                <div class="timeline-content">
                    <div class="timeline-content-header">
                        <h4 class="timeline-content-title">${eventDescription}</h4>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Render application interviews
 */
function renderApplicationInterviews(interviews) {
    const container = document.getElementById('detail-interviews');
    
    if (interviews.length === 0) {
        container.innerHTML = `
            <p>No interviews scheduled yet.</p>
            <button class="btn btn-primary" onclick="showInterviewModal(${currentApplicationId})">
                Schedule Interview
            </button>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="interview-list">
            ${interviews.map(interview => `
                <div class="interview-item">
                    <div class="interview-item-header">
                        <div>
                            <div class="interview-item-type">${escapeHtml(interview.interview_type)}</div>
                            <div class="interview-item-date">
                                ${interview.scheduled_at ? JobTracker.formatDateTime(interview.scheduled_at) : 'Not scheduled'}
                            </div>
                        </div>
                        <span class="status-badge">${interview.status}</span>
                    </div>
                    ${interview.interviewer_name ? `
                        <p><strong>Interviewer:</strong> ${escapeHtml(interview.interviewer_name)}</p>
                    ` : ''}
                    ${interview.location ? `
                        <p><strong>Location:</strong> ${escapeHtml(interview.location)}</p>
                    ` : ''}
                    ${interview.notes ? `
                        <p>${escapeHtml(interview.notes)}</p>
                    ` : ''}
                    <div class="interview-item-actions">
                        <button class="btn btn-secondary btn-sm" onclick="editInterview(${interview.interview_id})">
                            Edit
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
        <div style="margin-top: 1rem;">
            <button class="btn btn-primary" onclick="showInterviewModal(${currentApplicationId})">
                Schedule New Interview
            </button>
        </div>
    `;
}

/**
 * Render application offer
 */
function renderApplicationOffer(offer) {
    const container = document.getElementById('detail-offer');
    
    if (!offer) {
        container.innerHTML = `
            <p>No offer received yet.</p>
            <button class="btn btn-primary" onclick="showOfferModal(${currentApplicationId})">
                Add Offer
            </button>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="detail-section">
            <h3>Offer Details</h3>
            <div class="detail-field">
                <div class="detail-field-label">Offer Date</div>
                <div class="detail-field-value">${JobTracker.formatDate(offer.offer_date)}</div>
            </div>
            ${offer.salary_amount ? `
                <div class="detail-field">
                    <div class="detail-field-label">Salary</div>
                    <div class="detail-field-value">
                        ${offer.salary_currency || 'USD'} ${offer.salary_amount.toLocaleString()}
                        ${offer.salary_period ? `/${offer.salary_period}` : ''}
                    </div>
                </div>
            ` : ''}
            ${offer.equity ? `
                <div class="detail-field">
                    <div class="detail-field-label">Equity</div>
                    <div class="detail-field-value">${escapeHtml(offer.equity)}</div>
                </div>
            ` : ''}
            ${offer.benefits ? `
                <div class="detail-field">
                    <div class="detail-field-label">Benefits</div>
                    <div class="detail-field-value">${escapeHtml(offer.benefits)}</div>
                </div>
            ` : ''}
            ${offer.start_date ? `
                <div class="detail-field">
                    <div class="detail-field-label">Start Date</div>
                    <div class="detail-field-value">${JobTracker.formatDate(offer.start_date)}</div>
                </div>
            ` : ''}
            ${offer.decision_deadline ? `
                <div class="detail-field">
                    <div class="detail-field-label">Decision Deadline</div>
                    <div class="detail-field-value">${JobTracker.formatDate(offer.decision_deadline)}</div>
                </div>
            ` : ''}
            <div class="detail-field">
                <div class="detail-field-label">Status</div>
                <div class="detail-field-value">
                    <span class="status-badge">${offer.status}</span>
                </div>
            </div>
            ${offer.notes ? `
                <div class="detail-field">
                    <div class="detail-field-label">Notes</div>
                    <div class="detail-field-value">${escapeHtml(offer.notes)}</div>
                </div>
            ` : ''}
            <div style="margin-top: 1rem;">
                <button class="btn btn-primary" onclick="showOfferModal(${currentApplicationId}, true)">
                    Edit Offer
                </button>
            </div>
        </div>
    `;
}

/**
 * Switch detail tab
 */
function switchDetailTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    
    document.querySelectorAll('.detail-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `detail-${tab}`);
    });
}

/**
 * Close application detail modal
 */
function closeApplicationDetailModal() {
    const modal = document.getElementById('application-detail-modal');
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
    currentApplicationId = null;
}

/**
 * Show interview modal
 */
async function showInterviewModal(applicationId, interviewId = null) {
    const modal = document.getElementById('interview-modal');
    document.getElementById('interview-application-id').value = applicationId;
    
    if (interviewId) {
        // Load existing interview for editing
        try {
            const appData = await JobTracker.apiCall(`/applications/${applicationId}`);
            const interview = appData.interviews.find(i => i.interview_id === interviewId);
            if (interview) {
                document.getElementById('interview-modal-title').textContent = 'Edit Interview';
                document.getElementById('interview-type').value = interview.interview_type;
                if (interview.scheduled_at) {
                    const date = new Date(interview.scheduled_at);
                    document.getElementById('interview-scheduled-at').value = 
                        date.toISOString().slice(0, 16);
                }
                document.getElementById('interview-duration').value = interview.duration_minutes || '';
                document.getElementById('interview-interviewer-name').value = interview.interviewer_name || '';
                document.getElementById('interview-interviewer-email').value = interview.interviewer_email || '';
                document.getElementById('interview-location').value = interview.location || '';
                document.getElementById('interview-notes').value = interview.notes || '';
                document.getElementById('interview-prep-notes').value = interview.preparation_notes || '';
            }
        } catch (error) {
            console.error('Failed to load interview:', error);
        }
    } else {
        document.getElementById('interview-modal-title').textContent = 'Schedule Interview';
        document.getElementById('interview-form').reset();
    }
    
    modal.style.display = 'flex';
    modal.classList.add('show');
}

/**
 * Close interview modal
 */
function closeInterviewModal() {
    const modal = document.getElementById('interview-modal');
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
}

/**
 * Save interview
 */
async function saveInterview() {
    const applicationId = parseInt(document.getElementById('interview-application-id').value);
    const interviewType = document.getElementById('interview-type').value;
    const scheduledAt = document.getElementById('interview-scheduled-at').value;
    
    if (!interviewType) {
        JobTracker.showNotification('Interview type is required', 'error');
        return;
    }
    
    // Build form data, only including non-empty values
    const formData = {
        interview_type: interviewType
    };
    
    // Add scheduled_at if provided, convert to ISO string
    if (scheduledAt) {
        formData.scheduled_at = new Date(scheduledAt).toISOString();
    }
    
    // Add optional fields only if they have values
    const duration = document.getElementById('interview-duration').value;
    if (duration) {
        formData.duration_minutes = parseInt(duration) || null;
    }
    
    const interviewerName = document.getElementById('interview-interviewer-name').value.trim();
    if (interviewerName) {
        formData.interviewer_name = interviewerName;
    }
    
    const interviewerEmail = document.getElementById('interview-interviewer-email').value.trim();
    if (interviewerEmail) {
        formData.interviewer_email = interviewerEmail;
    }
    
    const location = document.getElementById('interview-location').value.trim();
    if (location) {
        formData.location = location;
    }
    
    const notes = document.getElementById('interview-notes').value.trim();
    if (notes) {
        formData.notes = notes;
    }
    
    const prepNotes = document.getElementById('interview-prep-notes').value.trim();
    if (prepNotes) {
        formData.preparation_notes = prepNotes;
    }
    
    try {
        await JobTracker.apiCall(`/applications/${applicationId}/interviews`, {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        JobTracker.showNotification('Interview scheduled successfully', 'success');
        closeInterviewModal();
        await loadApplications();
        if (currentApplicationId === applicationId) {
            await viewApplicationDetail(applicationId);
        }
    } catch (error) {
        console.error('Failed to save interview:', error);
        JobTracker.showNotification(error.message || 'Failed to save interview', 'error');
    }
}

/**
 * Show offer modal
 */
async function showOfferModal(applicationId, isEdit = false) {
    const modal = document.getElementById('offer-modal');
    document.getElementById('offer-application-id').value = applicationId;
    
    if (isEdit) {
        try {
            const appData = await JobTracker.apiCall(`/applications/${applicationId}`);
            const offer = appData.offer;
            if (offer) {
                document.getElementById('offer-modal-title').textContent = 'Edit Offer';
                document.getElementById('offer-date').value = offer.offer_date;
                document.getElementById('offer-salary').value = offer.salary_amount || '';
                document.getElementById('offer-currency').value = offer.salary_currency || 'USD';
                document.getElementById('offer-period').value = offer.salary_period || '';
                document.getElementById('offer-equity').value = offer.equity || '';
                document.getElementById('offer-benefits').value = offer.benefits || '';
                document.getElementById('offer-start-date').value = offer.start_date || '';
                document.getElementById('offer-deadline').value = offer.decision_deadline || '';
                document.getElementById('offer-status').value = offer.status || 'pending';
                document.getElementById('offer-notes').value = offer.notes || '';
            }
        } catch (error) {
            console.error('Failed to load offer:', error);
        }
    } else {
        document.getElementById('offer-modal-title').textContent = 'Add Offer';
        document.getElementById('offer-form').reset();
        document.getElementById('offer-date').value = new Date().toISOString().split('T')[0];
        document.getElementById('offer-currency').value = 'USD';
        document.getElementById('offer-status').value = 'pending';
    }
    
    modal.style.display = 'flex';
    modal.classList.add('show');
}

/**
 * Close offer modal
 */
function closeOfferModal() {
    const modal = document.getElementById('offer-modal');
    modal.classList.remove('show');
    setTimeout(() => {
        modal.style.display = 'none';
    }, 300);
}

/**
 * Save offer
 */
async function saveOffer() {
    const applicationId = parseInt(document.getElementById('offer-application-id').value);
    
    // Get form values and clean them up
    const offerDate = document.getElementById('offer-date').value;
    const startDate = document.getElementById('offer-start-date').value;
    const deadline = document.getElementById('offer-deadline').value;
    
    const formData = {
        offer_date: offerDate || null,
        salary_amount: parseFloat(document.getElementById('offer-salary').value) || null,
        salary_currency: document.getElementById('offer-currency').value || 'USD',
        salary_period: document.getElementById('offer-period').value || null,
        equity: document.getElementById('offer-equity').value.trim() || null,
        benefits: document.getElementById('offer-benefits').value.trim() || null,
        start_date: startDate || null,
        decision_deadline: deadline || null,
        status: document.getElementById('offer-status').value || 'pending',
        notes: document.getElementById('offer-notes').value.trim() || null
    };
    
    // Remove null values for optional date fields to avoid validation issues
    if (!formData.start_date) {
        delete formData.start_date;
    }
    if (!formData.decision_deadline) {
        delete formData.decision_deadline;
    }
    
    if (!formData.offer_date) {
        JobTracker.showNotification('Offer date is required', 'error');
        return;
    }
    
    try {
        await JobTracker.apiCall(`/applications/${applicationId}/offers`, {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        JobTracker.showNotification('Offer saved successfully', 'success');
        closeOfferModal();
        await loadApplications();
        await loadStats();
        if (currentApplicationId === applicationId) {
            await viewApplicationDetail(applicationId);
        }
    } catch (error) {
        console.error('Failed to save offer:', error);
        JobTracker.showNotification(error.message || 'Failed to save offer', 'error');
    }
}

/**
 * Render current view based on state
 */
function renderCurrentView() {
    // Don't render if no applications
    if (applications.length === 0) {
        return;
    }
    
    // Ensure view toggle is visible
    const viewToggle = document.querySelector('.view-toggle');
    if (viewToggle) {
        viewToggle.style.display = 'flex';
    }
    
    // Hide empty state
    const emptyState = document.getElementById('empty-state');
    if (emptyState) {
        emptyState.style.display = 'none';
    }
    
    if (currentView === 'kanban') {
        renderKanbanBoard();
    } else if (currentView === 'timeline') {
        renderTimeline();
    } else if (currentView === 'calendar') {
        renderCalendar();
    }
}

/**
 * Edit interview (placeholder - would load interview data)
 */
function editInterview(interviewId) {
    if (currentApplicationId) {
        showInterviewModal(currentApplicationId, interviewId);
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

/**
 * Show edit application modal
 */
async function showEditApplicationModal(applicationId) {
    try {
        const data = await JobTracker.apiCall(`/applications/${applicationId}`);
        const app = data.application;
        
        // Populate the new application form with existing data
        document.getElementById('app-job-id').value = app.job_id || '';
        document.getElementById('app-status').value = app.status || 'applied';
        document.getElementById('app-method').value = app.application_method || '';
        document.getElementById('app-url').value = app.application_url || '';
        document.getElementById('app-notes').value = app.notes || '';
        document.getElementById('app-priority').value = app.priority || 0;
        
        // Change modal title and submit button
        const modal = document.getElementById('new-application-modal');
        const modalTitle = modal.querySelector('.modal-header h2');
        const submitBtn = document.getElementById('new-app-submit-btn');
        
        if (modalTitle) modalTitle.textContent = 'Edit Application';
        if (submitBtn) {
            submitBtn.textContent = 'Update Application';
            submitBtn.dataset.editMode = 'true';
            submitBtn.dataset.applicationId = applicationId;
        }
        
        // Show modal
        modal.style.display = 'flex';
        modal.classList.add('show');
    } catch (error) {
        console.error('Failed to load application for editing:', error);
        JobTracker.showNotification('Failed to load application', 'error');
    }
}

/**
 * Update createApplication to handle edits
 */
async function createApplication() {
    const submitBtn = document.getElementById('new-app-submit-btn');
    const isEdit = submitBtn.dataset.editMode === 'true';
    const applicationId = submitBtn.dataset.applicationId;
    
    if (isEdit && applicationId) {
        await updateApplication(parseInt(applicationId));
        return;
    }
    
    // Original create logic continues...
    const form = document.getElementById('new-application-form');
    const jobInput = document.getElementById('app-job-id');
    const jobInputValue = jobInput.value.trim();
    
    if (!jobInputValue) {
        JobTracker.showNotification('Job is required', 'error');
        return;
    }
    
    // Extract job ID from input
    let jobId = jobInput.dataset.selectedJobId;
    
    if (!jobId) {
        if (/^[a-zA-Z0-9_-]+$/.test(jobInputValue) && jobInputValue.length > 5) {
            jobId = jobInputValue;
        } else {
            if (jobInputValue.includes(' - ')) {
                const parts = jobInputValue.split(' - ');
                try {
                    const searchData = await JobTracker.apiCall(`/jobs?keywords=${encodeURIComponent(parts[0])}&page_size=1`);
                    if (searchData.jobs && searchData.jobs.length > 0) {
                        jobId = searchData.jobs[0].job_id;
                    } else {
                        JobTracker.showNotification('Could not find job. Please select from search results or enter a job ID.', 'error');
                        return;
                    }
                } catch (error) {
                    console.error('Error finding job:', error);
                    JobTracker.showNotification('Could not find job. Please select from search results or enter a job ID.', 'error');
                    return;
                }
            } else {
                JobTracker.showNotification('Please select a job from the search results or enter a job ID.', 'error');
                return;
            }
        }
    }
    
    const formData = {
        job_id: jobId,
        status: document.getElementById('app-status').value || 'applied',
        priority: parseInt(document.getElementById('app-priority').value) || 0
    };
    
    const method = document.getElementById('app-method').value.trim();
    if (method) {
        formData.application_method = method;
    }
    
    const url = document.getElementById('app-url').value.trim();
    if (url) {
        formData.application_url = url;
    }
    
    const notes = document.getElementById('app-notes').value.trim();
    if (notes) {
        formData.notes = notes;
    }
    
    try {
        await JobTracker.apiCall('/applications', {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        JobTracker.showNotification('Application created successfully', 'success');
        closeNewApplicationModal();
        await loadApplications();
        await loadStats();
        
        if (applications.length > 0) {
            const viewToggle = document.querySelector('.view-toggle');
            if (viewToggle) {
                viewToggle.style.display = 'flex';
            }
            const emptyState = document.getElementById('empty-state');
            if (emptyState) {
                emptyState.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to create application:', error);
        JobTracker.showNotification(error.message || 'Failed to create application', 'error');
    }
}

/**
 * Update application
 */
async function updateApplication(applicationId) {
    const formData = {
        status: document.getElementById('app-status').value || 'applied',
        priority: parseInt(document.getElementById('app-priority').value) || 0
    };
    
    const method = document.getElementById('app-method').value.trim();
    if (method) {
        formData.application_method = method;
    }
    
    const url = document.getElementById('app-url').value.trim();
    if (url) {
        formData.application_url = url;
    }
    
    const notes = document.getElementById('app-notes').value.trim();
    if (notes) {
        formData.notes = notes;
    }
    
    try {
        await JobTracker.apiCall(`/applications/${applicationId}`, {
            method: 'PUT',
            body: JSON.stringify(formData)
        });
        
        JobTracker.showNotification('Application updated successfully', 'success');
        closeNewApplicationModal();
        
        // Reset form state
        const submitBtn = document.getElementById('new-app-submit-btn');
        submitBtn.dataset.editMode = 'false';
        delete submitBtn.dataset.applicationId;
        submitBtn.textContent = 'Create Application';
        const modalTitle = document.getElementById('new-application-modal').querySelector('.modal-header h2');
        if (modalTitle) modalTitle.textContent = 'New Application';
        
        await loadApplications();
        await loadStats();
        
        if (currentApplicationId === applicationId) {
            await viewApplicationDetail(applicationId);
        }
    } catch (error) {
        console.error('Failed to update application:', error);
        JobTracker.showNotification(error.message || 'Failed to update application', 'error');
    }
}

// Make functions available globally
window.viewApplicationDetail = viewApplicationDetail;
window.showNewApplicationModal = showNewApplicationModal;
window.showInterviewModal = showInterviewModal;
window.showOfferModal = showOfferModal;
window.editInterview = editInterview;
window.showEditApplicationModal = showEditApplicationModal;
window.showEditApplicationModal = showEditApplicationModal;
