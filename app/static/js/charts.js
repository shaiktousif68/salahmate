/**
 * Charts functionality using Chart.js
 */

function initCharts() {
    // Check if chart canvases exist and Chart.js is loaded
    if (typeof Chart === 'undefined') return;

    Chart.defaults.font.family = "'Poppins', sans-serif";
    Chart.defaults.color = '#94a3b8';

    const emerald = '#10b981';
    const gold = '#d4af37';
    const blue = '#3b82f6';
    const warning = '#f59e0b';
    const danger = '#ef4444';

    // Daily Completion Chart
    const dailyCanvas = document.getElementById('dailyChart');
    if (dailyCanvas && typeof dailyData !== 'undefined') {
        const labels = dailyData.map(d => d.label);
        const values = dailyData.map(d => d.percentage);

        new Chart(dailyCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Completion %',
                    data: values,
                    backgroundColor: values.map(v => 
                        v >= 80 ? emerald : v >= 50 ? gold : danger
                    ),
                    borderRadius: 6,
                    barPercentage: 0.8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.parsed.y}% completed`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    // Prayer Breakdown Chart
    const prayerCanvas = document.getElementById('prayerChart');
    if (prayerCanvas && typeof prayerData !== 'undefined') {
        const labels = Object.keys(prayerData);
        const jamaatValues = labels.map(label => prayerData[label].jamaat || 0);
        const aloneValues = labels.map(label => prayerData[label].alone || 0);
        const qazaValues = labels.map(label => prayerData[label].qaza || 0);
        const missedValues = labels.map(label => prayerData[label].missed || 0);

        new Chart(prayerCanvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Jamaat',
                        data: jamaatValues,
                        backgroundColor: emerald,
                        borderRadius: 4
                    },
                    {
                        label: 'Alone',
                        data: aloneValues,
                        backgroundColor: blue,
                        borderRadius: 4
                    },
                    {
                        label: 'Qaza',
                        data: qazaValues,
                        backgroundColor: warning,
                        borderRadius: 4
                    },
                    {
                        label: 'Missed',
                        data: missedValues,
                        backgroundColor: danger,
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            usePointStyle: true
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }

    // Weekly Performance Chart
    const weeklyCanvas = document.getElementById('weeklyChart');
    if (weeklyCanvas && typeof weeklyData !== 'undefined') {
        const labels = weeklyData.map(d => d.label);
        const percentages = weeklyData.map(d => d.percentage);

        new Chart(weeklyCanvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Weekly Completion %',
                    data: percentages,
                    borderColor: emerald,
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4,
                    borderWidth: 3,
                    pointBackgroundColor: emerald,
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 6,
                    pointHoverRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.parsed.y}% completed`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        },
                        grid: {
                            color: 'rgba(255, 255, 255, 0.05)'
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }
}

// Initialize charts on DOMContentLoaded, or immediately if the DOM is already
// loaded (e.g., when this script is re-executed by SPA navigation after the
// DOMContentLoaded event has already fired).
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCharts);
} else {
    initCharts();
}