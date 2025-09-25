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
        this.animationSpeed = 10;
        this.isAnimating = false;
        this.stats = {};
        this.viewMode = 'solar';
        this.request = null;

        this.setupEventListeners();
        this.resizeCanvas();
    }

    setupEventListeners() {
        window.addEventListener('resize', () => this.resizeCanvas());

        const speedSlider = document.getElementById('animation-speed');
        if (speedSlider) {
            speedSlider.addEventListener('input', (e) => {
                this.animationSpeed = parseInt(e.target.value);
                const speedValue = document.getElementById('speed-value');
                if (speedValue) {
                    speedValue.textContent = this.animationSpeed + 'x';
                }
            });
        }

        const viewModeSelect = document.getElementById('view-mode');
        if (viewModeSelect) {
            viewModeSelect.addEventListener('change', (e) => {
                this.viewMode = e.target.value;
                this.drawCurrentFrame();
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
        const scale = Math.min(width, height) / (3 * 1.524 * 1.496e11);

        // Центр системы
        const centerX = width / 2;
        const centerY = height / 2;

        // Рисуем Солнце
        ctx.fillStyle = '#ffeb3b';
        ctx.beginPath();
        ctx.arc(centerX, centerY, 25, 0, Math.PI * 2);
        ctx.fill();

        // Рисуем орбиты планет (эллипсы)
        this.drawPlanetaryOrbits(centerX, centerY, scale);

        // Рисуем планеты в их текущих позициях
        this.drawPlanets(centerX, centerY, scale);

        // Корабль
        if (point) {
            const shipX = centerX + point.x * scale;
            const shipY = centerY + point.y * scale;

            // Рисуем траекторию
            this.drawTrajectory(centerX, centerY, scale);

            // Рисуем корабль
            ctx.fillStyle = '#fff';
            ctx.beginPath();
            ctx.arc(shipX, shipY, 5, 0, Math.PI * 2);
            ctx.fill();

            // Подсветка корабля
            ctx.strokeStyle = '#00ff00';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(shipX, shipY, 8, 0, Math.PI * 2);
            ctx.stroke();
        }
    }

    drawPlanetaryOrbits(centerX, centerY, scale) {
        if (!this.ctx) return;

        const ctx = this.ctx;

        // Орбита Земли (эллипс)
        ctx.strokeStyle = 'rgba(0, 191, 255, 0.3)';
        ctx.lineWidth = 1;
        this.drawEllipse(ctx, centerX, centerY,
                        1.496e11 * scale,
                        1.496e11 * scale,
                        0);

        // Орбита Марса (эллипс)
        ctx.strokeStyle = 'rgba(255, 87, 51, 0.3)';
        this.drawEllipse(ctx, centerX, centerY,
                        1.524 * 1.496e11 * scale,
                        1.524 * 1.496e11 * scale,
                        1.85 * Math.PI/180);
    }

    drawEllipse(ctx, x, y, a, b, rotation) {
        ctx.save();
        ctx.translate(x, y);
        ctx.rotate(rotation);
        ctx.scale(a, b);
        ctx.beginPath();
        ctx.arc(0, 0, 1, 0, Math.PI * 2);
        ctx.restore();
        ctx.stroke();
    }

    drawPlanets(centerX, centerY, scale) {
        if (!this.ctx || !this.planetaryData) return;

        const ctx = this.ctx;
        const time = this.currentIndex / this.trajectory.length * this.stats.total_time / 86400;

        // Земля
        const earthPos = this.calculatePlanetPosition(time, 'earth');
        ctx.fillStyle = '#2196f3';
        ctx.beginPath();
        // ctx.arc(centerX + earthPos[0] * scale, centerY + earthPos[1] * scale, 12, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.fillText('🌍', centerX + earthPos[0] * scale - 6, centerY + earthPos[1] * scale + 4);

        // Марс
        const marsPos = this.calculatePlanetPosition(time, 'mars');
        ctx.fillStyle = '#ff5722';
        ctx.beginPath();
        // ctx.arc(centerX + marsPos[0] * scale, centerY + marsPos[1] * scale, 10, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.fillText('🔴', centerX + marsPos[0] * scale - 6, centerY + marsPos[1] * scale + 4);
    }

    calculatePlanetPosition(timeDays, planet) {
        // Упрощенная модель движения планет по эллиптическим орбитам
        const orbits = {
            'earth': { a: 1.0, e: 0.0167, period: 365.25, w: 0 },
            'mars': { a: 1.524, e: 0.0934, period: 687.0, w: 286.5 * Math.PI/180 }
        };

        const orbit = orbits[planet];
        const distance = orbit.a * 1.496e11;
        const angle = orbit.w - Math.PI/2 + 2 * Math.PI * (timeDays % orbit.period) / orbit.period;

        return [
            distance * Math.cos(angle),
            distance * Math.sin(angle)
        ];
    }

    drawTrajectory(centerX, centerY, scale) {
        if (!this.ctx || this.trajectory.length === 0) return;

        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(0, 255, 0, 0.5)';
        ctx.lineWidth = 2;
        ctx.beginPath();

        // Рисуем только часть траектории до текущей точки
        for (let i = 0; i <= this.currentIndex; i += 10) {
            if (i < this.trajectory.length) {
                const point = this.trajectory[i];
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

        // Динамический масштаб в зависимости от высоты
        const maxHeight = Math.max(100000, point.y * 1.5); // Запас 50%
        const scale = height / maxHeight;

        // Земля с динамическим размером
        const baseEarthRadius = Math.min(width, height) * 0.4;
        const earthRadius = baseEarthRadius * (1 - point.y / maxHeight * 0.5);
        const gradient = ctx.createRadialGradient(
            width/2, height, earthRadius,
            width/2, height, earthRadius * 0.8
        );
        gradient.addColorStop(0, '#1e88e5');
        gradient.addColorStop(1, '#0d47a1');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.arc(width/2, height, earthRadius, 0, Math.PI, true);
        ctx.fill();

        // Атмосфера
        if (this.request?.include_atmosphere) {
            ctx.strokeStyle = 'rgba(135, 206, 235, 0.3)';
            ctx.lineWidth = 20;
            ctx.beginPath();
            ctx.arc(width/2, height, earthRadius + 20, 0, Math.PI, true);
            ctx.stroke();
        }

        // Корабль
        if (point && point.y > 0) {
            const shipX = width/2;
            const shipY = height - point.y * scale;

            if (shipY < height * 0.3) {
                ctx.translate(0, height * 0.3 - shipY);
            }

            this.drawSpacecraft(shipX, shipY, 0);
        }
    }

    drawLandingView(point) {
        if (!this.ctx || !this.canvas) return;

        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        ctx.clearRect(0, 0, width, height);

        // Марс
        const marsRadius = Math.min(width, height) * 0.4;
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

        // Корабль
        if (point && point.y > 0) {
            const scale = height / 100000;
            const shipX = width/2;
            const shipY = height - point.y * scale;

            this.drawSpacecraft(shipX, shipY, -90);
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
        ctx.moveTo(0, -20);
        ctx.lineTo(-10, 20);
        ctx.lineTo(10, 20);
        ctx.closePath();
        ctx.fill();

        // Окна
        ctx.fillStyle = '#87ceeb';
        ctx.beginPath();
        ctx.arc(0, -5, 3, 0, Math.PI * 2);
        ctx.fill();

        ctx.restore();
    }

    drawStars() {
        if (!this.ctx || !this.canvas) return;

        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        ctx.fillStyle = '#fff';
        for (let i = 0; i < 200; i++) {
            const x = Math.random() * width;
            const y = Math.random() * height;
            const size = Math.random() * 2;

            ctx.beginPath();
            ctx.arc(x, y, size, 0, Math.PI * 2);
            ctx.fill();
        }
    }

    drawCurrentFrame() {
        if (!this.ctx || !this.canvas) return;

        const currentPoint = this.trajectory[this.currentIndex];

        switch (this.viewMode) {
            case 'solar':
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

        updateElement('current-altitude', (point.y / 1000).toFixed(1));
        updateElement('current-velocity', (point.velocity / 1000).toFixed(2));
        updateElement('current-mass', Math.round(point.mass));
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

    animate() {
        if (this.currentIndex >= this.trajectory.length) {
            this.stopAnimation();
            return;
        }

        this.drawCurrentFrame();
        this.currentIndex += this.animationSpeed;
        this.animationId = requestAnimationFrame(() => this.animate());
    }

    startAnimation() {
        if (this.trajectory.length === 0) return;
        console.log(this.trajectory)

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
        if (this.stats.delta_v !== undefined) {
            updateStat('delta-v', (this.stats.delta_v / 1000).toFixed(1) + ' км/с');
        }
        if (this.stats.fuel_consumed !== undefined) {
            updateStat('fuel-consumed', this.stats.fuel_consumed.toLocaleString() + ' кг');
        }
        if (this.stats.max_acceleration !== undefined) {
            updateStat('max-acceleration', (this.stats.max_acceleration / 9.81).toFixed(1) + ' g');
        }
        if (this.stats.arrival_velocity !== undefined) {
            updateStat('arrival-velocity', (this.stats.arrival_velocity).toFixed(1) + ' м/с');
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

    const request = {
        initial_mass: parseFloat(document.getElementById('initial_mass').value) || 1000000,
        thrust: parseFloat(document.getElementById('thrust').value) || 20000000,
        specific_impulse: parseFloat(document.getElementById('specific_impulse').value) || 350,
        landing_mass: parseFloat(document.getElementById('landing_mass').value) || 10000,
        landing_thrust: parseFloat(document.getElementById('landing_thrust').value) || 500000,
        departure_date: document.getElementById('departure_date').value || '2024-01-01',
        transfer_time: parseFloat(document.getElementById('transfer_time').value) || 200,
        include_atmosphere: document.getElementById('include_atmosphere').checked,
        include_planetary_gravity: document.getElementById('include_planetary_gravity').checked,
        include_orientation: document.getElementById('include_orientation').checked
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
            throw new Error(result.error || 'Неизвестная ошибка');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка: ' + error.message);
    }
}

function pauseMission() {
    if (missionAnimation) {
        missionAnimation.stopAnimation();
    }
}

function resetMission() {
    if (missionAnimation) {
        missionAnimation.stopAnimation();
        missionAnimation.trajectory = [];
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
                    backgroundColor: 'rgba(255, 99, 132, 0.5)',
                    yAxisID: 'y',
                },
                {
                    label: 'Масса (тонны)',
                    data: masses,
                    borderColor: 'rgb(54, 162, 235)',
                    backgroundColor: 'rgba(54, 162, 235, 0.5)',
                    yAxisID: 'y1',
                }
            ]
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Время (дни)'
                    }
                },
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    title: {
                        display: true,
                        text: 'Скорость (км/с)'
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
            }
        }
    });
}
