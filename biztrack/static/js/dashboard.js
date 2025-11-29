// ========================================
// FIXED BIZTRACK PRO - Dashboard Intelligence
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    
    // Chart.js Global Config
    Chart.defaults.font.family = 'Segoe UI, -apple-system, BlinkMacSystemFont, Roboto, Helvetica Neue, sans-serif';
    const isDarkMode = document.documentElement.getAttribute('data-bs-theme') === 'dark';
    Chart.defaults.color = isDarkMode ? '#adb5bd' : '#6c757d';
    Chart.defaults.borderColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';

    // Currency symbol (Lesotho Maloti)
    const CURRENCY = 'M';

    // Real-Time Data Module
    const RealtimeModule = (() => {
        let hourlyChartInstance = null;
        let lastTransactionsJSON = '';
        let lastHourlyDataJSON = '';

        const updateText = (elementId, text) => {
            const el = document.getElementById(elementId);
            if (el && el.textContent !== text) {
                el.textContent = text;
            }
        };

        const updateHourlyChart = (hourlyData) => {
            const newHourlyDataJSON = JSON.stringify(hourlyData);
            if (newHourlyDataJSON === lastHourlyDataJSON) return;
            lastHourlyDataJSON = newHourlyDataJSON;

            const ctx = document.getElementById('hourlyChart')?.getContext('2d');
            if (!ctx) return;

            const labels = hourlyData.map(h => h.hour);
            const data = hourlyData.map(h => h.revenue);

            if (hourlyChartInstance) {
                hourlyChartInstance.data.labels = labels;
                hourlyChartInstance.data.datasets[0].data = data;
                hourlyChartInstance.update('none'); // Skip animation for performance
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
                        scales: { y: { beginAtZero: true } }
                    }
                });
            }

            // Show canvas and hide spinner
            ctx.canvas.style.display = 'block';
            const spinner = ctx.canvas.parentElement.querySelector('.spinner-border');
            if (spinner) spinner.style.display = 'none';
        };

        const updateLiveFeed = (transactions) => {
            const feedContainer = document.getElementById('liveTransactions');
            if (!feedContainer) return;

            if (!transactions || transactions.length === 0) {
                feedContainer.innerHTML = '<div class="text-center text-muted py-5"><i class="fas fa-coffee fa-2x mb-3"></i><p>No transactions yet today. Time for a coffee!</p></div>';
                return;
            }

            const newTransactionsJSON = JSON.stringify(transactions);
            if (newTransactionsJSON === lastTransactionsJSON) return;
            lastTransactionsJSON = newTransactionsJSON;

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
        };

        const fetchData = async () => {
            try {
                const response = await fetch("/api/dashboard/realtime");
                if (!response.ok) throw new Error('Network error');
                const data = await response.json();

                updateText('todayRevenue', `${CURRENCY}${data.today.revenue.toFixed(2)}`);
                updateText('todayTransactions', data.today.transactions);
                updateText('avgTransaction', `${CURRENCY}${data.today.avg_transaction.toFixed(2)}`);

                updateLiveFeed(data.recent_transactions);
                updateHourlyChart(data.hourly);

            } catch (error) {
                console.error('Real-time update failed:', error);
                const feedContainer = document.getElementById('liveTransactions');
                if (feedContainer) {
                    feedContainer.innerHTML = '<div class="text-center text-danger py-5"><i class="fas fa-exclamation-triangle fa-2x mb-3"></i><p>Live data connection lost. Retrying...</p></div>';
                }
            }
        };

        const init = () => {
            fetchData();
            setInterval(fetchData, 5000); // Update every 5 seconds
        };

        return { init };
    })();

    // Static Charts Module
    const ChartsModule = (() => {
        const createChart = async (elementId, url, configFactory) => {
            const canvas = document.getElementById(elementId);
            if (!canvas) {
                console.warn(`Canvas ${elementId} not found`);
                return;
            }
            
            const ctx = canvas.getContext('2d');
            const container = canvas.parentElement;
            const spinner = container.querySelector('.spinner-border');

            try {
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                
                if (spinner) spinner.style.display = 'none';
                canvas.style.display = 'block';

                new Chart(ctx, configFactory(data));

            } catch (error) {
                console.error(`Failed to load ${elementId}:`, error);
                if (spinner) spinner.style.display = 'none';
                
                const errorEl = document.createElement('div');
                errorEl.className = 'alert alert-warning text-center';
                errorEl.innerHTML = '<i class="fas fa-exclamation-triangle me-2"></i>Unable to load chart. Please refresh the page.';
                container.appendChild(errorEl);
                canvas.style.display = 'none';
            }
        };

        const initDailyChart = () => {
            createChart('dailyChart', '/api/dashboard/daily', d => ({
                type: "bar",
                data: {
                    labels: d.dates,
                    datasets: [{
                        label: `Revenue (${CURRENCY})`,
                        data: d.revenue,
                        backgroundColor: "rgba(13, 110, 253, 0.8)",
                        borderRadius: 4,
                        yAxisID: 'y'
                    }, {
                        label: "Margin (%)",
                        data: d.margin,
                        type: "line",
                        borderColor: "#198754",
                        backgroundColor: "rgba(25, 135, 84, 0.1)",
                        fill: true,
                        tension: 0.4,
                        yAxisID: 'y1',
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: true } },
                    scales: {
                        y: { beginAtZero: true, position: 'left', title: { display: true, text: `Revenue (${CURRENCY})` } },
                        y1: {
                            beginAtZero: true,
                            position: 'right',
                            grid: { display: false },
                            title: { display: true, text: 'Margin (%)' }
                        }
                    }
                }
            }));
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
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { beginAtZero: true } }
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
            initDailyChart();
            initSalesChart();
            initCategoriesChart();
        };

        return { init };
    })();

    // Initialize Modules
    RealtimeModule.init();
    ChartsModule.init();
    
    console.log('✅ Dashboard initialized successfully');
});