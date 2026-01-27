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

    /**
     * Get color-blind safe palette for charts
     * Uses colors that are distinguishable for all types of color vision
     */
    getColorBlindSafePalette(count = 5) {
        // Color-blind safe palette (works for protanopia, deuteranopia, tritanopia)
        // Based on ColorBrewer Set2 and other accessible palettes
        const palette = [
            '#4a6fa5', // Blue
            '#f59e0b', // Orange/Amber
            '#10b981', // Green
            '#ef4444', // Red
            '#8b5cf6', // Purple
            '#ec4899', // Pink
            '#14b8a6', // Teal
            '#f97316', // Orange
            '#6366f1', // Indigo
            '#84cc16'  // Lime
        ];
        
        // Return requested number of colors, cycling if needed
        return palette.slice(0, Math.min(count, palette.length));
    },

    /**
     * Get gradient palette for bar charts (single color with varying opacity)
     */
    getGradientPalette(baseColor, count = 5) {
        const colors = [];
        for (let i = 0; i < count; i++) {
            const opacity = 0.4 + (0.6 * (i + 1) / count);
            // Convert hex to rgba
            const r = parseInt(baseColor.slice(1, 3), 16);
            const g = parseInt(baseColor.slice(3, 5), 16);
            const b = parseInt(baseColor.slice(5, 7), 16);
            colors.push(`rgba(${r}, ${g}, ${b}, ${opacity})`);
        }
        return colors;
    },

    async init() {
        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const tab = btn.dataset.tab;
                this.switchTab(tab);
            });
        });

        // Watch for theme changes and re-render charts (debounced)
        const themeObserver = new MutationObserver(() => {
            // Debounce theme-driven re-renders to avoid heavy thrashing
            if (this._themeRerenderTimeout) {
                clearTimeout(this._themeRerenderTimeout);
            }
            this._themeRerenderTimeout = setTimeout(() => {
                if (this.personalData) {
                    this.renderStatusChart();
                    this.renderCompaniesChart();
                    this.renderSectorsChart();
                }
                if (this.marketData) {
                    this.renderSectorTrendsChart();
                }
            }, 200);
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
            if (!window.JobTracker || !window.JobTracker.apiCall) {
                throw new Error('JobTracker not available');
            }
            this.personalData = await window.JobTracker.apiCall('/analytics/personal');
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
            if (!window.JobTracker || !window.JobTracker.apiCall) {
                throw new Error('JobTracker not available');
            }
            this.marketData = await window.JobTracker.apiCall('/analytics/market');
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

        const palette = this.getColorBlindSafePalette(3);
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
                    palette[0], // Blue for Applied
                    palette[2], // Green for Offers
                    palette[3]  // Red for Rejected
                ],
                borderColor: [
                    palette[0],
                    palette[2],
                    palette[3]
                ],
                borderWidth: 2
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

        const companies = this.personalData.top_companies || [];
        const palette = this.getColorBlindSafePalette(companies.length);
        const data = {
            labels: companies.map(c => c.name),
            datasets: [{
                label: 'Applications',
                data: companies.map(c => c.count),
                backgroundColor: palette,
                borderColor: palette.map(c => {
                    // Darken border slightly for better definition
                    const r = parseInt(c.slice(1, 3), 16);
                    const g = parseInt(c.slice(3, 5), 16);
                    const b = parseInt(c.slice(5, 7), 16);
                    return `rgb(${Math.max(0, r - 20)}, ${Math.max(0, g - 20)}, ${Math.max(0, b - 20)})`;
                }),
                borderWidth: 1
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

        const sectors = this.personalData.top_sectors || [];
        const palette = this.getColorBlindSafePalette(sectors.length);
        const data = {
            labels: sectors.map(s => s.sector),
            datasets: [{
                label: 'Applications',
                data: sectors.map(s => s.count),
                backgroundColor: palette,
                borderColor: palette.map(c => {
                    const r = parseInt(c.slice(1, 3), 16);
                    const g = parseInt(c.slice(3, 5), 16);
                    const b = parseInt(c.slice(5, 7), 16);
                    return `rgb(${Math.max(0, r - 20)}, ${Math.max(0, g - 20)}, ${Math.max(0, b - 20)})`;
                }),
                borderWidth: 1
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

        const sectors = this.marketData.sector_trends || [];
        const palette = this.getColorBlindSafePalette(sectors.length);
        const data = {
            labels: sectors.map(s => s.sector),
            datasets: [{
                label: 'Job Count',
                data: sectors.map(s => s.count),
                backgroundColor: palette,
                borderColor: palette.map(c => {
                    const r = parseInt(c.slice(1, 3), 16);
                    const g = parseInt(c.slice(3, 5), 16);
                    const b = parseInt(c.slice(5, 7), 16);
                    return `rgb(${Math.max(0, r - 20)}, ${Math.max(0, g - 20)}, ${Math.max(0, b - 20)})`;
                }),
                borderWidth: 1
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
