class MarsMissionAnimation {
    constructor() {
        this.canvas = document.getElementById('missionCanvas');
        if (!this.canvas) {
            console.error('Canvas element not found');
            return;
        }

        this.ctx = this.canvas.getContext('2d');
        this.animationId = null;
        this.trajectory = [];
        this.currentIndex = 0;
        this.baseAnimationSpeed = 1;
        this.phaseSpeedMultipliers = {
            'launch': 0.1,
            'transfer': 1.0,
            'landing': 0.1
        };
        this.isAnimating = false;
        this.stats = {};
        this.viewMode = 'transfer';
        this.request = null;
        this.stars = [];
        this.planetaryData = {};
        this.marsStartPos = [0, 0];

        this.setupEventListeners();
        this.resizeCanvas();
        this.generateStars();
    }

    setupEventListeners() {
        window.addEventListener('resize', () => {
            this.resizeCanvas();
            this.generateStars(); // Перегенерируем звезды при изменении размера
        });

        const speedSlider = document.getElementById('animation-speed');
        if (speedSlider) {
            speedSlider.addEventListener('input', (e) => {
                this.baseAnimationSpeed = parseInt(e.target.value);
                const speedValue = document.getElementById('speed-value');
                if (speedValue) {
                    speedValue.textContent = this.baseAnimationSpeed + 'x';
                }
            });
        }
    }

    generateStars() {
        this.stars = [];
        const width = this.canvas.width;
        const height = this.canvas.height;

        for (let i = 0; i < 200; i++) {
            this.stars.push({
                x: Math.random() * width,
                y: Math.random() * height,
                size: Math.random() * 2,
                brightness: Math.random() * 0.8 + 0.2
            });
        }
    }

    resizeCanvas() {
        if (!this.canvas) return;

        const container = this.canvas.parentElement;
        if (container) {
            this.canvas.width = container.clientWidth;
            this.canvas.height = 600;
            this.drawCurrentFrame();
        }
    }

    drawSolarSystemView(point) {
        if (!this.ctx || !this.canvas) return;

        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        // Очищаем canvas
        ctx.clearRect(0, 0, width, height);

        // Рисуем космос
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, width, height);

        // Рисуем звезды
        this.drawStars();

        // Масштаб для солнечной системы
        const scale = Math.min(width, height) / (2.22 * 1.524 * 1.496e11);

        // Центр системы
        const centerX = width / 2;
        const centerY = height / 2;

        // Рисуем Солнце
        ctx.fillStyle = '#ffeb3b';
        ctx.beginPath();
        ctx.arc(centerX, centerY, 25, 0, Math.PI * 2);
        ctx.fill();

        // Рисуем орбиты планет
        this.drawPlanetaryOrbits(centerX, centerY, scale);

        // Рисуем планеты в их текущих позициях
        this.drawPlanets(centerX, centerY, scale, point);

        // Корабль
        if (point) {
            const shipX = centerX + point.x * scale;
            const shipY = centerY + point.y * scale;

            // Рисуем траекторию
            this.drawTrajectory(centerX, centerY, scale);

            // Рисуем корабль
            this.drawSpacecraft(shipX, shipY, this.getSpacecraftAngle(point.phase));
        }
    }

    getSpacecraftAngle(phase) {
        switch (phase) {
            case 'launch': return 0;
            case 'transfer': return 90;
            case 'landing': return -90;
            default: return 0;
        }
    }

    drawPlanetaryOrbits(centerX, centerY, scale) {
        if (!this.ctx) return;

        const ctx = this.ctx;

        // Орбита Земли
        ctx.strokeStyle = 'rgba(0, 191, 255, 0.3)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(centerX, centerY, 1.0 * 1.496e11 * scale, 0, Math.PI * 2);
        ctx.stroke();

        // Орбита Марса
        ctx.strokeStyle = 'rgba(255, 87, 51, 0.3)';
        ctx.beginPath();
        ctx.arc(centerX, centerY, 1.524 * 1.496e11 * scale, 0, Math.PI * 2);
        ctx.stroke();
    }

    drawPlanets(centerX, centerY, scale, currentPoint) {
        if (!this.ctx) return;

        const ctx = this.ctx;
        const currentTime = currentPoint ? currentPoint.time : 0;

        // Позиция Земли (упрощенно - на орбите)
        const earthAngle = (currentTime / 86400) * (2 * Math.PI / 365.25) + Math.PI / 2;
        const earthX = centerX + Math.cos(earthAngle) * 1.0 * 1.496e11 * scale;
        const earthY = centerY + Math.sin(earthAngle) * 1.0 * 1.496e11 * scale;

        // Земля
        ctx.fillStyle = '#2196f3';
        ctx.beginPath();
        ctx.arc(earthX, earthY, 12, 0, Math.PI * 2);
        ctx.fill();

        // Позиция Марса с учетом начального положения из бэкенда
        const marsOrbitRadius = 1.524 * 1.496e11 * scale;
        let marsX, marsY;

        if (this.marsStartPos && this.marsStartPos.length >= 2) {
            // Используем реальное начальное положение Марса
            const marsStartAngle = Math.atan2(this.marsStartPos[1], this.marsStartPos[0]);
            const marsAngle = marsStartAngle + (currentTime / 86400) * (2 * Math.PI / 687);
            marsX = centerX + Math.cos(marsAngle) * marsOrbitRadius;
            marsY = centerY + Math.sin(marsAngle) * marsOrbitRadius;
        } else {
            // Резервный расчет
            const marsAngle = (currentTime / 86400) * (2 * Math.PI / 687);
            marsX = centerX + Math.cos(marsAngle) * marsOrbitRadius;
            marsY = centerY + Math.sin(marsAngle) * marsOrbitRadius;
        }

        // Марс
        ctx.fillStyle = '#ff5722';
        ctx.beginPath();
        ctx.arc(marsX, marsY, 10, 0, Math.PI * 2);
        ctx.fill();

        // Подписи планет
        ctx.fillStyle = '#fff';
        ctx.font = '12px Arial';
        ctx.fillText('Земля', earthX - 20, earthY - 15);
        ctx.fillText('Марс', marsX - 15, marsY - 15);
    }

    drawTrajectory(centerX, centerY, scale) {
        if (!this.ctx || this.trajectory.length === 0) return;

        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(0, 255, 0, 0.6)';
        ctx.lineWidth = 1;
        ctx.beginPath();

        // Рисуем всю траекторию полупрозрачной
        for (let i = 0; i < this.trajectory.length; i += 5) {
            const point = this.trajectory[i];

            if (point.phase !== "transfer") continue;
            const x = centerX + point.x * scale;
            const y = centerY + point.y * scale;

            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.stroke();

        // Рисуем пройденную часть траектории более яркой
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 3;
        ctx.beginPath();

        for (let i = 0; i <= this.currentIndex; i += 5) {
            if (i < this.trajectory.length) {
                const point = this.trajectory[i];

                if (point.phase !== "transfer") continue;
                const x = centerX + point.x * scale;
                const y = centerY + point.y * scale;

                if (i === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
        }
        ctx.stroke();
    }

    drawLaunchView(point) {
        if (!this.ctx || !this.canvas) return;

        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        ctx.clearRect(0, 0, width, height);

        // Рисуем звезды (неподвижные)
        this.drawStars();

        // Динамический масштаб - Земля должна уменьшаться по мере удаления
        const maxVisibleHeight = 6000000; // 500 км
        const currentHeight = point ? point.y : 0;
        const scale = height / maxVisibleHeight;

        // Размер Земли уменьшается линейно с высотой
        const minEarthRadius = Math.min(width, height) * 0.01;
        const maxEarthRadius = Math.min(width, height) * 0.45;
        const earthRadius = Math.max(minEarthRadius,
            maxEarthRadius * (1 - currentHeight / maxVisibleHeight));

        // Земля
        const gradient = ctx.createRadialGradient(
            width/2, height, earthRadius,
            width/2, height, earthRadius * 0.5
        );
        gradient.addColorStop(0, '#1e88e5');
        gradient.addColorStop(1, '#0d47a1');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(width/2, height, earthRadius, 0, Math.PI, true);
        ctx.fill();

        // Атмосфера
        if (this.request?.include_atmosphere) {
            const atmosphereThickness = earthRadius * 0.05;
            ctx.strokeStyle = 'rgba(135, 206, 235, 0.3)';
            ctx.lineWidth = atmosphereThickness;
            ctx.beginPath();
            ctx.arc(width/2, height, earthRadius + atmosphereThickness/2, 0, Math.PI, true);
            ctx.stroke();
        }

        // Корабль
        if (point && point.y > 0) {
            const shipX = width/2;
            const shipY = height - point.y * scale;

            this.drawSpacecraft(shipX, shipY, 0);
        }

        // Отображение высоты
        ctx.fillStyle = '#fff';
        ctx.font = '14px Arial';
        ctx.fillText(`Высота: ${(currentHeight / 1000).toFixed(1)} км`, 20, 30);
        ctx.fillText(`Скорость: ${(point?.velocity / 1000 || 0).toFixed(2)} км/с`, 20, 50);
    }

    drawLandingView(point) {
        if (!this.ctx || !this.canvas) return;

        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        ctx.clearRect(0, 0, width, height);

        // Рисуем звезды (неподвижные)
        this.drawStars();

        // Динамический масштаб для посадки
        const maxVisibleHeight = 3000000;
        const currentHeight = point ? point.y : 0;
        const scale = height / maxVisibleHeight;

        // Марс увеличивается по мере приближения
        const minMarsRadius = Math.min(width, height) * 0.01;
        const maxMarsRadius = Math.min(width, height) * 0.45;
        const marsRadius = Math.max(minMarsRadius,
            maxMarsRadius * (1 - currentHeight / maxVisibleHeight));

        // Марс
        const gradient = ctx.createRadialGradient(
            width/2, height, marsRadius,
            width/2, height, marsRadius * 0.8
        );
        gradient.addColorStop(0, '#e53935');
        gradient.addColorStop(1, '#b71c1c');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(width/2, height, marsRadius, 0, Math.PI, true);
        ctx.fill();

        // Атмосфера Марса
        if (this.request?.include_atmosphere) {
            const atmosphereThickness = marsRadius * 0.03;
            ctx.strokeStyle = 'rgba(255, 152, 0, 0.2)';
            ctx.lineWidth = atmosphereThickness;
            ctx.beginPath();
            ctx.arc(width/2, height, marsRadius + atmosphereThickness/2, 0, Math.PI, true);
            ctx.stroke();
        }

        // Корабль
        if (point && point.y > 0) {
            const shipX = width/2;
            const shipY = height - point.y * scale;

            this.drawSpacecraft(shipX, shipY, 0);
        }

        // Отображение высоты
        ctx.fillStyle = '#fff';
        ctx.font = '14px Arial';
        ctx.fillText(`Высота: ${(currentHeight / 1000).toFixed(1)} км`, 20, 30);
        ctx.fillText(`Скорость: ${(point?.velocity || 0).toFixed(1)} м/с`, 20, 50);
        if (point && point.y < 1000) {
            ctx.fillText('ПОСАДКА!', width/2 - 30, height/2);
        }
    }

    drawSpacecraft(x, y, angle) {
        if (!this.ctx) return;

        const ctx = this.ctx;
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(angle * Math.PI / 180);

        // Корпус
        ctx.fillStyle = '#ccc';
        ctx.beginPath();
        ctx.moveTo(0, -15);
        ctx.lineTo(-8, 15);
        ctx.lineTo(8, 15);
        ctx.closePath();
        ctx.fill();

        // Окна
        ctx.fillStyle = '#87ceeb';
        ctx.beginPath();
        ctx.arc(0, -5, 2, 0, Math.PI * 2);
        ctx.fill();

        // Сопло (если есть тяга)
        ctx.fillStyle = '#ff4444';
        ctx.beginPath();
        ctx.moveTo(-5, 15);
        ctx.lineTo(0, 20);
        ctx.lineTo(5, 15);
        ctx.closePath();
        ctx.fill();

        ctx.restore();
    }

    drawStars() {
        if (!this.ctx || !this.canvas || this.stars.length === 0) return;

        const ctx = this.ctx;

        this.stars.forEach(star => {
            ctx.fillStyle = `rgba(255, 255, 255, ${star.brightness})`;
            ctx.beginPath();
            ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    drawCurrentFrame() {
        if (!this.ctx || !this.canvas) return;

        const currentPoint = this.trajectory[this.currentIndex];

        switch (this.viewMode) {
            case 'transfer':
                this.drawSolarSystemView(currentPoint);
                break;
            case 'launch':
                this.drawLaunchView(currentPoint);
                break;
            case 'landing':
                this.drawLandingView(currentPoint);
                break;
        }

        this.updateRealTimeData(currentPoint);
        this.updatePhaseIndicator(currentPoint?.phase);
    }

    updateRealTimeData(point) {
        if (!point) return;

        const updateElement = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        };

        if (this.viewMode !== 'transfer') {
            updateElement('current-altitude', (point.y / 1000).toFixed(1));
        } else {
            updateElement('current-altitude', '-');
        }
        updateElement('current-velocity', (point.velocity / 1000).toFixed(2));
        updateElement('current-mass', Math.round(point.mass));
        updateElement('current-overload', (point.overload).toFixed(1));
        updateElement('current-time', (point.time / 86400).toFixed(1));
    }

    updatePhaseIndicator(phase) {
        if (!phase) return;

        // Сброс всех индикаторов
        document.querySelectorAll('.phase-indicator').forEach(indicator => {
            indicator.classList.remove('active');
        });

        // Активация текущей фазы
        const indicator = document.getElementById(`phase-${phase}`);
        if (indicator) {
            indicator.classList.add('active');
        }
    }

    getCurrentPhaseSpeed() {
        const currentPoint = this.trajectory[this.currentIndex];
        if (!currentPoint) return this.baseAnimationSpeed;

        const phase = currentPoint.phase;
        const multiplier = this.phaseSpeedMultipliers[phase] || 1.0;
        return Math.max(1, Math.floor(this.baseAnimationSpeed * multiplier));
    }

    animate() {
        if (this.currentIndex >= this.trajectory.length) {
            this.stopAnimation();
            return;
        }

        const currentPoint = this.trajectory[this.currentIndex];
        this.viewMode = currentPoint.phase;

        this.drawCurrentFrame();

        // Динамическая скорость в зависимости от фазы
        const phaseSpeed = this.getCurrentPhaseSpeed();
        this.currentIndex += phaseSpeed;

        this.animationId = requestAnimationFrame(() => this.animate());
    }

    startAnimation() {
        if (this.trajectory.length === 0) return;

        this.isAnimating = true;
        this.currentIndex = 0;
        this.animate();
    }

    stopAnimation() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        this.isAnimating = false;
    }

    setMissionData(response) {
        this.trajectory = response.trajectory || [];
        this.stats = response.stats || {};
        this.request = response.request || {};
        this.planetaryData = response.planetary_positions || {};
        this.marsStartPos = this.stats.mars_start_pos || [0, 0];
        this.drawCurrentFrame();
        this.updateMissionStats();
    }

    updateMissionStats() {
        const updateStat = (id, value) => {
            const element = document.getElementById(id);
            if (element) element.textContent = value;
        };

        if (this.stats.total_time !== undefined) {
            updateStat('total-time', (this.stats.total_time / 86400).toFixed(1) + ' дней');
        }

        if (this.stats.fuel_consumed !== undefined) {
            updateStat('fuel-consumed', Math.round(this.stats.fuel_consumed).toLocaleString() + ' кг');
        }

        if (this.stats.fuel_consumed_earth !== undefined) {
            updateStat('fuel-consumed-earth', Math.round(this.stats.fuel_consumed_earth).toLocaleString() + ' кг');
        }

        if (this.stats.fuel_consumed_mars !== undefined) {
            updateStat('fuel-consumed-mars', Math.round(this.stats.fuel_consumed_mars).toLocaleString() + ' кг');
        }

        if (this.trajectory.length > 0) {
            const maxOverload = Math.max(...this.trajectory.map(p => Math.abs(p.overload || 0)));
            updateStat('max-acceleration', (maxOverload / 9.81).toFixed(1) + ' g');
        }
    }
}

// Глобальные переменные
let missionAnimation = null;
let velocityMassChart = null;

// Инициализация после полной загрузки DOM
document.addEventListener('DOMContentLoaded', function() {
    missionAnimation = new MarsMissionAnimation();

    // Установка сегодняшней даты по умолчанию
    const today = new Date().toISOString().split('T')[0];
    const dateInput = document.getElementById('departure_date');
    if (dateInput) {
        dateInput.value = today;
    }
});

async function startMission() {
    if (!missionAnimation) {
        console.error('Mission animation not initialized');
        return;
    }

    // Сбор параметров согласно новому Python API
    const request = {
        initial_mass: parseFloat(document.getElementById('initial_mass').value) || 1000000,
        gases_velocity: parseFloat(document.getElementById('gases_velocity').value) || 20000000,
        velocity: parseFloat(document.getElementById('velocity').value) || 350,
        landing_velocity: parseFloat(document.getElementById('landing_velocity').value) || 350,
        landing_mass: parseFloat(document.getElementById('landing_mass').value) || 10000,
        include_atmosphere: document.getElementById('include_atmosphere').checked,
        bounded_overload: document.getElementById('bounded_overload').checked,
        safety_margin: parseFloat(document.getElementById('safety_margin').value) || 66,
        max_landing_velocity: parseFloat(document.getElementById('max_landing_velocity').value) || 0.8,
        max_dm_dt: parseFloat(document.getElementById('max_dm_dt').value) || 10,
    };

    try {
        const response = await fetch('/physics/M3/simulate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка сервера');
        }

        const result = await response.json();

        if (result.success) {
            missionAnimation.setMissionData(result);
            createCharts(result.trajectory);
            missionAnimation.startAnimation();
        } else {
            throw new Error(result.message || 'Неизвестная ошибка');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка: ' + error.message);
    }
}

function pauseMission() {
    if (missionAnimation) {
        if (missionAnimation.isAnimating) {
            missionAnimation.stopAnimation();
        } else {
            missionAnimation.startAnimation();
        }
    }
}

function resetMission() {
    if (missionAnimation) {
        missionAnimation.stopAnimation();
        missionAnimation.trajectory = [];
        missionAnimation.currentIndex = 0;
        missionAnimation.drawCurrentFrame();
    }

    if (velocityMassChart) {
        velocityMassChart.destroy();
        velocityMassChart = null;
    }

    // Сброс статистики
    document.querySelectorAll('.stat-value').forEach(el => {
        el.textContent = '-';
    });

    // Сброс индикаторов фаз
    document.querySelectorAll('.phase-indicator').forEach(indicator => {
        indicator.classList.remove('active');
    });

    // Сброс реального времени
    document.querySelectorAll('.real-time-stats span').forEach(el => {
        const span = el.querySelector('span');
        if (span) span.textContent = '-';
    });
}

function createCharts(trajectory) {
    createVelocityMassChart(trajectory);
}

function createVelocityMassChart(trajectory) {
    const ctx = document.getElementById('velocityMassChart');
    if (!ctx) return;

    if (velocityMassChart) {
        velocityMassChart.destroy();
    }

    const times = trajectory.map(point => point.time / 86400);
    const velocities = trajectory.map(point => point.velocity / 1000);
    const masses = trajectory.map(point => point.mass / 1000);

    velocityMassChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: times,
            datasets: [
                {
                    label: 'Скорость (км/с)',
                    data: velocities,
                    borderColor: 'rgb(255, 99, 132)',
                    backgroundColor: 'rgba(255, 99, 132, 0.1)',
                    yAxisID: 'y',
                    borderWidth: 2,
                    tension: 0.1
                },
                {
                    label: 'Масса (тонны)',
                    data: masses,
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.1)',
                    yAxisID: 'y1',
                    borderWidth: 2,
                    tension: 0.1
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Время (дни)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Скорость (км/с)'
                    },
                    grid: {
                        color: 'rgba(255, 255, 255, 0.1)'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    title: {
                        display: true,
                        text: 'Масса (тонны)'
                    },
                    grid: {
                        drawOnChartArea: false,
                    },
                }
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#fff'
                    }
                }
            }
        }
    });
}