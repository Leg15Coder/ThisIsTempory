// Глобальные переменные
let animation = null;
let trajectoryChart = null;

const EARTH_COLOR = '#8B4513';
const SKY_COLOR = '#87CEEB';
const STONE_COLOR = '#323232';
const TRAJECTORY_COLOR_AFTER = '#EE0000';
const TRAJECTORY_COLOR_BEFORE = '#FF000044';


class ProjectileAnimation {
    constructor() {
        this.canvas = document.getElementById('animationCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.animationId = null;
        this.trajectoryData = [];
        this.currentPointIndex = 0;
        this.animationSpeed = 5;
        this.isAnimating = false;
        this.stats = {};

        this.setupEventListeners();
        this.resizeCanvas();
    }

    setupEventListeners() {
        window.addEventListener('resize', () => this.resizeCanvas());

        const speedSlider = document.getElementById('animation-speed');
        speedSlider.addEventListener('input', (e) => {
            this.animationSpeed = parseInt(e.target.value);
            document.getElementById('speed-value').textContent = this.animationSpeed + 'x';
            if (this.isAnimating) {
                this.stopAnimation();
                this.startAnimation();
            }
        });
    }

    resizeCanvas() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth - 40;
        this.canvas.height = 400;
        this.drawStaticElements();
        if (this.trajectoryData.length > 0) {
            this.drawTrajectory();
        }
    }

    drawStaticElements() {
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;

        // Очищаем canvas
        ctx.clearRect(0, 0, width, height);

        // Рисуем землю
        ctx.fillStyle = EARTH_COLOR;
        ctx.fillRect(0, height - 50, width, 50);

        // Рисуем небо
        ctx.fillStyle = SKY_COLOR;
        ctx.fillRect(0, 0, width, height - 50);

        // Рисуем сетку
        ctx.strokeStyle = '#DDDDDD';
        ctx.lineWidth = 0.5;

        // Вертикальные линии
        for (let x = 0; x <= width; x += 50) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height - 50);
            ctx.stroke();
        }

        // Горизонтальные линии
        for (let y = 0; y <= height - 50; y += 50) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        // Подписи осей
        ctx.fillStyle = '#000';
        ctx.font = '12px Arial';
        ctx.fillText('Расстояние (м)', width / 2 - 30, height - 20);
        ctx.save();
        ctx.translate(20, height / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText('Высота (м)', 0, 0);
        ctx.restore();
    }

    scalePoint(point) {
        const width = this.canvas.width;
        const height = this.canvas.height - 50;

        const maxX = Math.max(...this.trajectoryData.map(p => p.x));
        const maxY = Math.max(...this.trajectoryData.map(p => p.y));

        const scaleX = (width - 100) / (maxX || 1);
        const scaleY = (height - 75) / (maxY || 1);

        return {
            x: 50 + point.x * scaleX,
            y: height - 50 - point.y * scaleY
        };
    }

    drawTrajectory() {
        const ctx = this.ctx;
        ctx.strokeStyle = TRAJECTORY_COLOR_BEFORE;
        ctx.lineWidth = 2;

        ctx.beginPath();
        for (let i = 0; i < this.trajectoryData.length; i++) {
            const scaledPoint = this.scalePoint(this.trajectoryData[i]);
            if (i === 0) {
                ctx.moveTo(scaledPoint.x, scaledPoint.y);
            } else {
                ctx.lineTo(scaledPoint.x, scaledPoint.y);
            }
        }
        ctx.stroke();
    }

    drawProjectile(point) {
        const ctx = this.ctx;
        const scaledPoint = this.scalePoint(point);

        // Рисуем камень
        ctx.fillStyle = STONE_COLOR;
        ctx.beginPath();
        ctx.arc(scaledPoint.x, scaledPoint.y, 8, 0, Math.PI * 2);
        ctx.fill();

        // Рисуем тень
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.beginPath();
        ctx.arc(scaledPoint.x, scaledPoint.y + 5, 6, 0, Math.PI * 2);
        ctx.fill();

        // Рисуем траекторию до текущей точки
        ctx.strokeStyle = TRAJECTORY_COLOR_AFTER;
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i <= this.currentPointIndex; i++) {
            const scaled = this.scalePoint(this.trajectoryData[i]);
            if (i === 0) {
                ctx.moveTo(scaled.x, scaled.y);
            } else {
                ctx.lineTo(scaled.x, scaled.y);
            }
        }
        ctx.stroke();
    }

    updateStats() {
        if (this.currentPointIndex < this.trajectoryData.length) {
            const currentPoint = this.trajectoryData[this.currentPointIndex];
            const time = (this.currentPointIndex / this.trajectoryData.length) * this.stats.flight_time;
            const speed = Math.sqrt(
                Math.pow((this.trajectoryData[this.currentPointIndex].x - this.trajectoryData[Math.max(0, this.currentPointIndex-1)].x) / 0.01, 2) +
                Math.pow((this.trajectoryData[this.currentPointIndex].y - this.trajectoryData[Math.max(0, this.currentPointIndex-1)].y) / 0.01, 2)
            );

            document.getElementById('current-time').textContent = time.toFixed(2);
            document.getElementById('current-speed').textContent = speed.toFixed(2);
        }
    }

    animate() {
        if (this.currentPointIndex >= this.trajectoryData.length) {
            this.stopAnimation();
            return;
        }

        this.drawStaticElements();
        this.drawTrajectory();
        this.drawProjectile(this.trajectoryData[this.currentPointIndex]);
        this.updateStats();

        this.currentPointIndex += this.animationSpeed;
        this.animationId = requestAnimationFrame(() => this.animate());
    }

    startAnimation() {
        if (this.trajectoryData.length === 0) return;

        this.isAnimating = true;
        this.currentPointIndex = 0;
        this.animate();
    }

    stopAnimation() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        this.isAnimating = false;
    }

    resetAnimation() {
        this.stopAnimation();
        this.trajectoryData = [];
        this.currentPointIndex = 0;
        this.drawStaticElements();

        document.getElementById('current-time').textContent = '0.00';
        document.getElementById('current-speed').textContent = '-';
    }

    setTrajectoryData(data, stats) {
        this.trajectoryData = data;
        this.stats = stats;
        this.drawStaticElements();
        this.drawTrajectory();
    }
}

// Инициализация при загрузке страницы
window.addEventListener('load', () => {
    animation = new ProjectileAnimation();
    calculateTrajectory();
});

async function calculateTrajectory() {
    const data = {
        angle: parseFloat(document.getElementById('angle').value),
        velocity: parseFloat(document.getElementById('velocity').value),
        gravity: parseFloat(document.getElementById('gravity').value),
        viscous_friction: parseFloat(document.getElementById('viscous_friction').value),
        drag_coefficient: parseFloat(document.getElementById('drag_coefficient').value)
    };

    try {
        const response = await fetch('/physics/M1/calculate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Ошибка сервера');
        }

        const result = await response.json();

        if (result.success) {
            updateChart(result.trajectory);
            updateStats(result.stats);
            animation.setTrajectoryData(result.trajectory, result.stats);
        } else {
            throw new Error(result.error || 'Неизвестная ошибка');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Ошибка: ' + error.message);
    }
}

function startSimulation() {
    calculateTrajectory().then(() => {
        animation.startAnimation();
    });
}

function stopSimulation() {
    animation.stopAnimation();
}

function resetSimulation() {
    animation.resetAnimation();
    if (trajectoryChart) {
        trajectoryChart.destroy();
        trajectoryChart = null;
    }
    document.getElementById('range').textContent = '-';
    document.getElementById('max-height').textContent = '-';
    document.getElementById('flight-time').textContent = '-';
}

function updateChart(trajectoryData) {
    const ctx = document.getElementById('trajectoryChart').getContext('2d');

    if (trajectoryChart) {
        trajectoryChart.destroy();
    }

    trajectoryChart = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [{
                label: 'Траектория полета',
                data: trajectoryData.map(point => ({x: point.x, y: point.y})),
                borderColor: 'blue',
                backgroundColor: 'rgba(0, 0, 255, 0.1)',
                fill: false,
                pointRadius: 0,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                x: {
                    type: 'linear',
                    position: 'bottom',
                    title: {
                        display: true,
                        text: 'Расстояние (м)'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Высота (м)'
                    },
                    beginAtZero: true
                }
            },
            plugins: {
                title: {
                    display: true,
                    text: 'Траектория броска камня'
                }
            }
        }
    });
}

function updateStats(stats) {
    document.getElementById('range').textContent = stats.range.toFixed(2);
    document.getElementById('max-height').textContent = stats.max_height.toFixed(2);
    document.getElementById('flight-time').textContent = stats.flight_time.toFixed(2);
}
