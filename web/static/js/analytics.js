/**
 * Analytics Dashboard JavaScript
 */

const Analytics = {
    personalData: null,
    marketData: null,
    charts: {},

    /**
     * Get theme colors from CSS variables
     */
    getThemeColors() {
        const root = getComputedStyle(document.documentElement);
        return {
            primary: root.getPropertyValue('--primary-color').trim() || '#4a6fa5',
            primaryLight: root.getPropertyValue('--primary-light').trim() || '#5a7fb8',
            success: root.getPropertyValue('--success-color').trim() || '#10b981',
            error: root.getPropertyValue('--error-color').trim() || '#ef4444',
            warning: root.getPropertyValue('--warning-color').trim() || '#f59e0b',
            secondary: root.getPropertyValue('--secondary-color').trim() || '#64748b'
        };
    },

    async init() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.switchTab(tab);
            });
        });

        // Watch for theme changes and re-render charts
        const themeObserver = new MutationObserver(() => {
            // Re-render charts when theme changes
            if (this.personalData) {
                this.renderStatusChart();
                this.renderCompaniesChart();
                this.renderSectorsChart();
            }
            if (this.marketData) {
                this.renderSectorTrendsChart();
            }
        });
        
        themeObserver.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ['data-theme']
        });

        // Load data
        await this.loadPersonalAnalytics();
        await this.loadMarketAnalytics();
    },

    switchTab(tab) {
        // Update buttons
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

        // Update content
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        document.getElementById(`${tab}-tab`).classList.add('active');
    },

    async loadPersonalAnalytics() {
        try {
            const apiCall = window.JobTracker?.apiCall || (async () => { throw new Error('JobTracker not available'); });
            this.personalData = await apiCall('/analytics/personal');
            this.renderPersonalAnalytics();
        } catch (error) {
            console.error('Failed to load personal analytics:', error);
            if (error.message.includes('401') || error.message.includes('session')) {
                // Redirect to login
                window.location.href = '/login.html';
            }
        }
    },

    async loadMarketAnalytics() {
        try {
            const apiCall = window.JobTracker?.apiCall || (async () => { throw new Error('JobTracker not available'); });
            this.marketData = await apiCall('/analytics/market');
            this.renderMarketAnalytics();
        } catch (error) {
            console.error('Failed to load market analytics:', error);
        }
    },

    renderPersonalAnalytics() {
        if (!this.personalData) return;

        // Update stats
        document.getElementById('stat-total-applications').textContent = 
            this.personalData.total_applications || 0;
        document.getElementById('stat-saved-jobs').textContent = 
            this.personalData.total_saved_jobs || 0;
        document.getElementById('stat-success-rate').textContent = 
            `${this.personalData.success_rate || 0}%`;
        document.getElementById('stat-offers').textContent = 
            this.personalData.applications_by_status?.offers || 0;

        // Status chart
        this.renderStatusChart();

        // Companies chart
        this.renderCompaniesChart();

        // Sectors chart
        this.renderSectorsChart();
    },

    renderStatusChart() {
        const ctx = document.getElementById('status-chart');
        if (!ctx) return;

        const colors = this.getThemeColors();
        const statusData = this.personalData.applications_by_status || {};
        const data = {
            labels: ['Applied', 'Offers', 'Rejected'],
            datasets: [{
                label: 'Applications',
                data: [
                    statusData.applied || 0,
                    statusData.offers || 0,
                    statusData.rejected || 0
                ],
                backgroundColor: [
                    colors.primary,
                    colors.success,
                    colors.error
                ]
            }]
        };

        if (this.charts.status) {
            this.charts.status.destroy();
        }

        const root = getComputedStyle(document.documentElement);
        this.charts.status = new Chart(ctx, {
            type: 'doughnut',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: {
                            color: root.getPropertyValue('--text-primary').trim() || '#1e293b'
                        }
                    }
                }
            }
        });
    },

    renderCompaniesChart() {
        const ctx = document.getElementById('companies-chart');
        if (!ctx) return;

        const colors = this.getThemeColors();
        const companies = this.personalData.top_companies || [];
        const data = {
            labels: companies.map(c => c.name),
            datasets: [{
                label: 'Applications',
                data: companies.map(c => c.count),
                backgroundColor: colors.primary
            }]
        };

        if (this.charts.companies) {
            this.charts.companies.destroy();
        }

        const root = getComputedStyle(document.documentElement);
        this.charts.companies = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: root.getPropertyValue('--text-secondary').trim() || '#64748b'
                        },
                        grid: {
                            color: root.getPropertyValue('--border-color').trim() || '#e2e8f0'
                        }
                    },
                    x: {
                        ticks: {
                            color: root.getPropertyValue('--text-secondary').trim() || '#64748b'
                        },
                        grid: {
                            color: root.getPropertyValue('--border-color').trim() || '#e2e8f0'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: root.getPropertyValue('--text-primary').trim() || '#1e293b'
                        }
                    }
                }
            }
        });
    },

    renderSectorsChart() {
        const ctx = document.getElementById('sectors-chart');
        if (!ctx) return;

        const colors = this.getThemeColors();
        const sectors = this.personalData.top_sectors || [];
        const data = {
            labels: sectors.map(s => s.sector),
            datasets: [{
                label: 'Applications',
                data: sectors.map(s => s.count),
                backgroundColor: colors.success
            }]
        };

        if (this.charts.sectors) {
            this.charts.sectors.destroy();
        }

        const root = getComputedStyle(document.documentElement);
        this.charts.sectors = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: root.getPropertyValue('--text-secondary').trim() || '#64748b'
                        },
                        grid: {
                            color: root.getPropertyValue('--border-color').trim() || '#e2e8f0'
                        }
                    },
                    x: {
                        ticks: {
                            color: root.getPropertyValue('--text-secondary').trim() || '#64748b'
                        },
                        grid: {
                            color: root.getPropertyValue('--border-color').trim() || '#e2e8f0'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: root.getPropertyValue('--text-primary').trim() || '#1e293b'
                        }
                    }
                }
            }
        });
    },

    renderMarketAnalytics() {
        if (!this.marketData) return;

        // Sector trends chart
        this.renderSectorTrendsChart();

        // Company reliability
        this.renderReliabilityList();
    },

    renderSectorTrendsChart() {
        const ctx = document.getElementById('sector-trends-chart');
        if (!ctx) return;

        const colors = this.getThemeColors();
        const sectors = this.marketData.sector_trends || [];
        const data = {
            labels: sectors.map(s => s.sector),
            datasets: [{
                label: 'Job Count',
                data: sectors.map(s => s.count),
                backgroundColor: colors.primary
            }]
        };

        if (this.charts.sectorTrends) {
            this.charts.sectorTrends.destroy();
        }

        const root = getComputedStyle(document.documentElement);
        this.charts.sectorTrends = new Chart(ctx, {
            type: 'bar',
            data: data,
            options: {
                responsive: true,
                maintainAspectRatio: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: root.getPropertyValue('--text-secondary').trim() || '#64748b'
                        },
                        grid: {
                            color: root.getPropertyValue('--border-color').trim() || '#e2e8f0'
                        }
                    },
                    x: {
                        ticks: {
                            color: root.getPropertyValue('--text-secondary').trim() || '#64748b'
                        },
                        grid: {
                            color: root.getPropertyValue('--border-color').trim() || '#e2e8f0'
                        }
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: root.getPropertyValue('--text-primary').trim() || '#1e293b'
                        }
                    }
                }
            }
        });
    },

    renderReliabilityList() {
        const container = document.getElementById('reliability-list');
        if (!container) return;

        const companies = this.marketData.company_reliability || [];
        container.innerHTML = companies.map(c => `
            <div class="reliability-item">
                <span class="company-name">${c.name}</span>
                <span class="score">${c.score.toFixed(1)}</span>
            </div>
        `).join('');
    }
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    Analytics.init();
});
