// ========================================
// BIZTRACK PRO - Dashboard (FIXED VERSION)
// ========================================

console.log('🔍 Dashboard.js loading...');

// Check if Chart.js is loaded
if (typeof Chart === 'undefined') {
    console.error('❌ Chart.js NOT LOADED! Dashboard will fail.');
    alert('ERROR: Chart.js library not loaded. Check your internet connection and refresh the page.');
} else {
    console.log('✅ Chart.js loaded:', Chart.version);
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('🎯 DOM Content Loaded - Initializing dashboard...');
    
    // Chart.js Global Config
    if (typeof Chart !== 'undefined') {
        Chart.defaults.font.family = 'Segoe UI, -apple-system, BlinkMacSystemFont, Roboto, sans-serif';
        const isDarkMode = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        Chart.defaults.color = isDarkMode ? '#adb5bd' : '#6c757d';
        Chart.defaults.borderColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
    }

    const CURRENCY = 'M';

    // ========================================
    // MONTH REVENUE MODULE (ADDED)
    // ========================================
    const MonthRevenueModule = (() => {
        const fetchMonthRevenue = async () => {
            console.log('💰 Fetching month revenue...');
            try {
                const response = await fetch("/api/dashboard/month-revenue");
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                console.log('✅ Month revenue data received:', data);

                const revenueEl = document.getElementById('monthRevenue');
                if (revenueEl) {
                    revenueEl.textContent = `${CURRENCY}${data.revenue.toFixed(2)}`;
                }

            } catch (error) {
                console.error('❌ Month revenue fetch failed:', error);
                const revenueEl = document.getElementById('monthRevenue');
                if (revenueEl) {
                    revenueEl.textContent = `${CURRENCY}0.00`;
                    revenueEl.classList.add('text-danger');
                }
            }
        };

        const init = () => {
            console.log('🚀 Initializing MonthRevenueModule...');
            fetchMonthRevenue();
            // Update every 5 minutes
            setInterval(fetchMonthRevenue, 300000);
            console.log('✅ MonthRevenueModule initialized');
        };

        return { init };
    })();

    // ========================================
    // REAL-TIME DATA MODULE
    // ========================================
    const RealtimeModule = (() => {
        let hourlyChartInstance = null;

        const updateText = (elementId, text) => {
            const el = document.getElementById(elementId);
            if (el) {
                el.textContent = text;
                console.log(`✅ Updated ${elementId}:`, text);
            } else {
                console.warn(`⚠️ Element not found: ${elementId}`);
            }
        };

        const updateHourlyChart = (hourlyData) => {
            console.log('📊 Updating hourly chart with data:', hourlyData);
            
            const canvas = document.getElementById('hourlyChart');
            if (!canvas) {
                console.warn('⚠️ hourlyChart canvas not found');
                return;
            }
            
            const ctx = canvas.getContext('2d');
            const labels = hourlyData.map(h => h.hour);
            const data = hourlyData.map(h => h.revenue);

            console.log('📊 Chart data:', { labels, data });

            if (hourlyChartInstance) {
                hourlyChartInstance.data.labels = labels;
                hourlyChartInstance.data.datasets[0].data = data;
                hourlyChartInstance.update('none');
            } else {
                hourlyChartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: `Sales (${CURRENCY})`,
                            data: data,
                            borderColor: '#0d6efd',
                            backgroundColor: 'rgba(13, 110, 253, 0.1)',
                            fill: true,
                            tension: 0.4
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { 
                            y: { 
                                beginAtZero: true,
                                ticks: {
                                    callback: function(value) {
                                        return CURRENCY + value.toFixed(0);
                                    }
                                }
                            } 
                        }
                    }
                });
            }

            // Show canvas and hide spinner
            canvas.style.display = 'block';
            const spinner = canvas.parentElement.querySelector('.spinner-border');
            if (spinner) spinner.style.display = 'none';
            
            console.log('✅ Hourly chart rendered');
        };

        const updateLiveFeed = (transactions) => {
            const feedContainer = document.getElementById('liveTransactions');
            if (!feedContainer) {
                console.warn('⚠️ liveTransactions container not found');
                return;
            }

            console.log('🔔 Updating live feed with', transactions?.length || 0, 'transactions');

            if (!transactions || transactions.length === 0) {
                feedContainer.innerHTML = `
                    <div class="text-center text-muted py-5">
                        <i class="fas fa-coffee fa-2x mb-3"></i>
                        <p>No transactions yet today. Time for a coffee!</p>
                    </div>`;
                return;
            }

            const feedHTML = transactions.map(t => `
                <div class="transaction-item mb-3 p-3 bg-light-subtle rounded-3">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong class="text-body">${t.customer || 'Walk-in Customer'}</strong>
                            <small class="text-muted d-block">Invoice: ${t.invoice_number}</small>
                        </div>
                        <div class="text-end">
                            <h5 class="text-success mb-0 fw-bold">${CURRENCY}${t.total.toFixed(2)}</h5>
                            <small class="text-muted">${new Date(t.date).toLocaleTimeString()}</small>
                        </div>
                    </div>
                </div>
            `).join('');
            feedContainer.innerHTML = feedHTML;
            
            console.log('✅ Live feed updated');
        };

        const fetchData = async () => {
            console.log('🔄 Fetching realtime data...');
            
            try {
                const response = await fetch("/api/dashboard/realtime");
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const data = await response.json();
                console.log('✅ Realtime data received:', data);

                updateText('todayRevenue', `${CURRENCY}${data.today.revenue.toFixed(2)}`);
                updateText('todayTransactions', data.today.transactions);
                updateText('avgTransaction', `${CURRENCY}${data.today.avg_transaction.toFixed(2)}`);

                updateLiveFeed(data.recent_transactions);
                updateHourlyChart(data.hourly);

            } catch (error) {
                console.error('❌ Real-time update failed:', error);
                const feedContainer = document.getElementById('liveTransactions');
                if (feedContainer) {
                    feedContainer.innerHTML = `
                        <div class="text-center text-danger py-5">
                            <i class="fas fa-exclamation-triangle fa-2x mb-3"></i>
                            <p>Connection error: ${error.message}</p>
                            <small>Check browser console for details</small>
                        </div>`;
                }
            }
        };

        const init = () => {
            console.log('🚀 Initializing RealtimeModule...');
            fetchData();
            setInterval(fetchData, 60000); // Every 60 seconds
            console.log('✅ RealtimeModule initialized');
        };

        return { init };
    })();

    // ========================================
    // STATIC CHARTS MODULE
    // ========================================
    const ChartsModule = (() => {
        const createChart = async (elementId, url, configFactory) => {
            console.log(`📊 Creating chart: ${elementId} from ${url}`);
            
            const canvas = document.getElementById(elementId);
            if (!canvas) {
                console.warn(`⚠️ Canvas ${elementId} not found`);
                return;
            }
            
            const ctx = canvas.getContext('2d');
            const container = canvas.parentElement;
            const spinner = container.querySelector('.spinner-border');

            try {
                console.log(`🔄 Fetching data for ${elementId}...`);
                const response = await fetch(url);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const data = await response.json();
                console.log(`✅ Data received for ${elementId}:`, data);
                
                if (spinner) spinner.style.display = 'none';
                canvas.style.display = 'block';

                const config = configFactory(data);
                console.log(`🎨 Rendering ${elementId} chart...`);
                new Chart(ctx, config);
                console.log(`✅ ${elementId} chart rendered`);

            } catch (error) {
                console.error(`❌ Failed to load ${elementId}:`, error);
                if (spinner) spinner.style.display = 'none';
                
                const errorEl = document.createElement('div');
                errorEl.className = 'alert alert-warning text-center';
                errorEl.innerHTML = `
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Unable to load chart: ${error.message}<br>
                    <small>Check browser console for details</small>
                `;
                container.appendChild(errorEl);
                canvas.style.display = 'none';
            }
        };

        const initDailyChart = () => {
            createChart('dailyChart', '/api/dashboard/daily', d => {
                if (!d.dates || d.dates.length === 0) {
                    console.warn('No daily data available');
                    return { type: 'bar', data: { labels: [], datasets: [] }, options: {} };
                }

                return {
                    type: "bar",
                    data: {
                        labels: d.dates,
                        datasets: [
                            {
                                label: `Revenue (${CURRENCY})`,
                                data: d.revenue,
                                backgroundColor: "rgba(13, 110, 253, 0.8)",
                                borderRadius: 4,
                                yAxisID: 'y',
                                order: 2
                            },
                            {
                                label: "Margin (%)",
                                data: d.margin,
                                type: "line",
                                borderColor: "#198754",
                                backgroundColor: "rgba(25, 135, 84, 0.1)",
                                fill: true,
                                tension: 0.4,
                                yAxisID: 'y1',
                                pointRadius: 4,
                                order: 1
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { 
                            legend: { display: true, position: 'top' },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        let label = context.dataset.label || '';
                                        if (label) label += ': ';
                                        if (context.dataset.yAxisID === 'y1') {
                                            label += context.parsed.y.toFixed(1) + '%';
                                        } else {
                                            label += CURRENCY + context.parsed.y.toFixed(2);
                                        }
                                        return label;
                                    }
                                }
                            }
                        },
                        scales: {
                            y: { 
                                beginAtZero: true, 
                                position: 'left',
                                ticks: {
                                    callback: function(value) {
                                        return CURRENCY + value.toFixed(0);
                                    }
                                }
                            },
                            y1: {
                                beginAtZero: true,
                                position: 'right',
                                grid: { display: false },
                                ticks: {
                                    callback: function(value) {
                                        return value.toFixed(1) + '%';
                                    }
                                }
                            }
                        }
                    }
                };
            });
        };

        const initSalesChart = () => {
            createChart('salesChart', '/api/dashboard/sales', data => ({
                type: "line",
                data: {
                    labels: data.months,
                    datasets: [{
                        label: `Sales (${CURRENCY})`,
                        data: data.sales,
                        borderColor: "#198754",
                        backgroundColor: "rgba(25, 135, 84, 0.1)",
                        fill: true,
                        tension: 0.4,
                        pointRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { 
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return CURRENCY + context.parsed.y.toFixed(2);
                                }
                            }
                        }
                    },
                    scales: { 
                        y: { 
                            beginAtZero: true,
                            ticks: {
                                callback: function(value) {
                                    return CURRENCY + value.toFixed(0);
                                }
                            }
                        } 
                    }
                }
            }));
        };

        const initCategoriesChart = () => {
            createChart('categoriesChart', '/api/dashboard/categories', data => ({
                type: "doughnut",
                data: {
                    labels: data.categories,
                    datasets: [{
                        data: data.counts,
                        backgroundColor: [
                            'rgba(13, 110, 253, 0.8)',
                            'rgba(25, 135, 84, 0.8)',
                            'rgba(255, 193, 7, 0.8)',
                            'rgba(220, 53, 69, 0.8)',
                            'rgba(108, 117, 125, 0.8)'
                        ],
                        hoverOffset: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { position: 'bottom' } }
                }
            }));
        };

        const init = () => {
            console.log('🚀 Initializing ChartsModule...');
            initDailyChart();
            initSalesChart();
            initCategoriesChart();
            console.log('✅ ChartsModule initialized');
        };

        return { init };
    })();

    // Initialize ALL Modules
    console.log('🎬 Starting module initialization...');
    MonthRevenueModule.init(); // ADDED
    RealtimeModule.init();
    ChartsModule.init();
    
    console.log('✅ Dashboard fully initialized');
});