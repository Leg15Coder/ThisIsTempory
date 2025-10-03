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
        this.lastPointIndex = 0;
        this.time = 0;
        this.step = 0.01;
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

        // Для случая вертикального броска (90 градусов) используем только масштабирование по Y
        if (this.stats.is_vertical_throw) {
            const maxY = Math.max(...this.trajectoryData.map(p => p.y));
            const scaleY = (height - 100) / (maxY || 1);

            return {
                x: width / 2, // Центрируем по горизонтали
                y: height - point.y * scaleY
            };
        } else {
            const maxX = Math.max(...this.trajectoryData.map(p => p.x));
            const maxY = Math.max(...this.trajectoryData.map(p => p.y));

            const scaleX = (width - 100) / (maxX || 1);
            const scaleY = (height - 50) / (maxY || 1);

            return {
                x: 50 + point.x * scaleX,
                y: height - point.y * scaleY
            };
        }
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

            const speed = Math.sqrt(
                Math.pow((currentPoint.x - this.trajectoryData[Math.max(0, this.currentPointIndex-1)].x) / currentPoint.dt, 2) +
                Math.pow((currentPoint.y - this.trajectoryData[Math.max(0, this.currentPointIndex-1)].y) / currentPoint.dt, 2)
            );

            if (this.trajectoryData[this.currentPointIndex].y >= this.trajectoryData[Math.max(0, this.currentPointIndex-1)].y) {
                document.getElementById('height-time').textContent = this.time.toFixed(3);
            }

            document.getElementById('current-time').textContent = this.time.toFixed(3);
            document.getElementById('current-speed').textContent = speed.toFixed(3);
        }
    }

    animate() {
        if (this.currentPointIndex >= this.trajectoryData.length) {
            this.stopAnimation();
            document.getElementById('current-speed').textContent = 0;
            return;
        }

        this.drawStaticElements();
        this.drawTrajectory();
        this.drawProjectile(this.trajectoryData[this.currentPointIndex]);
        this.updateStats();

        if (this.currentPointIndex === this.trajectoryData.length - 1) {
            this.stopAnimation();
            document.getElementById('current-speed').textContent = 0;
            return;
        }

        this.lastPointIndex = this.currentPointIndex;
        const time = this.time;
        while (this.time < time + this.step * this.animationSpeed) {
            this.currentPointIndex++;

            if (this.currentPointIndex >= this.trajectoryData.length) {
                this.currentPointIndex--;
                break;
            }

            this.time += this.trajectoryData[this.currentPointIndex].dt;
        }

        this.animationId = requestAnimationFrame(() => this.animate());
    }

    startAnimation() {
        if (this.trajectoryData.length === 0) return;

        this.isAnimating = true;
        this.time = 0;
        this.currentPointIndex = 0;
        this.lastPointIndex = 0;
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
        this.lastPointIndex = 0;
        this.time = 0;
        this.drawStaticElements();

        document.getElementById('current-time').textContent = '0.00';
        document.getElementById('height-time').textContent = '0.00';
        document.getElementById('current-speed').textContent = '-';
    }

    setTrajectoryData(data, stats) {
        this.trajectoryData = data;
        this.stats = stats;
        this.step = stats.flight_time / 666;
        this.stats.is_vertical_throw = Math.abs(parseFloat(document.getElementById('angle').value) - 90) < 0.00001;
        this.drawStaticElements();
        this.drawTrajectory();
    }

    findSpeedAtTime(targetTime) {
        if (this.trajectoryData.length === 0) {
            return null;
        }

        // Если запрошено время 0 - возвращаем начальную скорость
        if (targetTime <= 0) {
            const initialSpeed = Math.sqrt(this.vx0 * this.vx0 + this.vy0 * this.vy0);
            return {
                speed: initialSpeed,
                vx: this.vx0,
                vy: this.vy0,
                x: this.x0,
                y: this.y0,
                time: 0,
                exactMatch: true
            };
        }

        // Ищем ближайшую точку по времени
        let accumulatedTime = 0;
        let closestPoint = null;
        let minTimeDiff = Infinity;

        for (let i = 0; i < this.trajectoryData.length; i++) {
            const point = this.trajectoryData[i];
            accumulatedTime += point.dt || 0;

            const timeDiff = Math.abs(accumulatedTime - targetTime);

            if (timeDiff < minTimeDiff) {
                minTimeDiff = timeDiff;
                closestPoint = {
                    index: i,
                    point: point,
                    time: accumulatedTime,
                    timeDiff: timeDiff
                };
            }

            // Если нашли точку с достаточно маленькой разницей во времени
            if (timeDiff < 0.001) {
                break;
            }
        }

        if (!closestPoint) {
            return null;
        }

        // Вычисляем скорость в этой точке
        const speed = this.calculateSpeedAtPoint(closestPoint.index);
        const velocityComponents = this.calculateVelocityComponents(closestPoint.index);

        return {
            speed: speed,
            vx: velocityComponents.vx,
            vy: velocityComponents.vy,
            x: closestPoint.point.x,
            y: closestPoint.point.y,
            time: closestPoint.time,
            timeDiff: closestPoint.timeDiff,
            exactMatch: closestPoint.timeDiff < 0.001
        };
    }

    calculateSpeedAtPoint(pointIndex) {
        if (this.trajectoryData.length <= 1) {
            return Math.sqrt(this.vx0 * this.vx0 + this.vy0 * this.vy0);
        }

        if (pointIndex === 0) {
            // Начальная скорость
            return Math.sqrt(this.vx0 * this.vx0 + this.vy0 * this.vy0);
        }

        const currentPoint = this.trajectoryData[pointIndex];
        const prevPoint = this.trajectoryData[pointIndex - 1];

        const dx = currentPoint.x - prevPoint.x;
        const dy = currentPoint.y - prevPoint.y;
        const dt = currentPoint.dt || 0.01;

        return Math.sqrt((dx/dt)**2 + (dy/dt)**2);
    }

    calculateVelocityComponents(pointIndex) {
        if (this.trajectoryData.length <= 1 || pointIndex === 0) {
            return { vx: this.vx0, vy: this.vy0 };
        }

        const currentPoint = this.trajectoryData[pointIndex];
        const prevPoint = this.trajectoryData[pointIndex - 1];
        const dt = currentPoint.dt || 0.01;

        return {
            vx: (currentPoint.x - prevPoint.x) / dt,
            vy: (currentPoint.y - prevPoint.y) / dt
        };
    }

    // Метод для отображения точки на графике при запросе
    highlightPointAtTime(targetTime) {
        const result = this.findSpeedAtTime(targetTime);
        if (!result) return;

        this.drawStaticElements();
        this.drawTrajectory();

        // Рисуем маркер в найденной точке
        const ctx = this.ctx;
        const scaledPoint = this.scalePoint({ x: result.x, y: result.y });

        // Рисуем маркер точки
        ctx.fillStyle = '#28a745';
        ctx.beginPath();
        ctx.arc(scaledPoint.x, scaledPoint.y, 8, 0, Math.PI * 2);
        ctx.fill();

        // Обводка маркера
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Дополнительный круг для выделения
        ctx.strokeStyle = '#28a745';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(scaledPoint.x, scaledPoint.y, 12, 0, Math.PI * 2);
        ctx.stroke();

        // Подпись точки
        ctx.fillStyle = '#000';
        ctx.font = '12px Arial';
        ctx.fillText(`t=${result.time.toFixed(2)}с`, scaledPoint.x + 15, scaledPoint.y - 10);
        ctx.fillText(`v=${result.speed.toFixed(2)}м/с`, scaledPoint.x + 15, scaledPoint.y + 5);
    }
}

// Инициализация при загрузке страницы
window.addEventListener('load', () => {
    animation = new ProjectileAnimation();
    calculateTrajectory();
});

async function calculateTrajectory() {
    const data = {
        mass: parseFloat(document.getElementById('mass').value),
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
        console.error('Ошибка:', error);
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
    document.getElementById('height-time').textContent = '-';
    document.getElementById('current-speed').textContent = '-';

    document.getElementById('query-time').value = '0';
    document.getElementById('query-result').textContent = '';
}

function updateChart(trajectoryData) {
    const ctx = document.getElementById('trajectoryChart').getContext('2d');

    if (trajectoryChart) {
        trajectoryChart.destroy();
    }

    is_vertical_throw = Math.abs(parseFloat(document.getElementById('angle').value) - 90) < 0.00001;
    const xAxisConfig = is_vertical_throw ? {
        type: 'linear',
        position: 'bottom',
        title: {
            display: true,
            text: 'Расстояние (м)'
        },
        min: -1,
        max: 1
    } : {
        type: 'linear',
        position: 'bottom',
        title: {
            display: true,
            text: 'Расстояние (м)'
        }
    };


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
                x: xAxisConfig,
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
    document.getElementById('range').textContent = stats.range.toFixed(3);
    document.getElementById('max-height').textContent = stats.max_height.toFixed(3);
    document.getElementById('flight-time').textContent = stats.flight_time.toFixed(3);
}

function querySpeedAtTime() {
    const queryTimeInput = document.getElementById('query-time');
    const queryResult = document.getElementById('query-result');

    if (!animation.trajectoryData || animation.trajectoryData.length === 0) {
        queryResult.textContent = 'Сначала запустите моделирование';
        queryResult.style.color = '#dc3545';
        return;
    }

    const targetTime = parseFloat(queryTimeInput.value);

    if (isNaN(targetTime) || targetTime < 0) {
        queryResult.textContent = 'Введите корректное время (≥ 0)';
        queryResult.style.color = '#dc3545';
        return;
    }

    const result = animation.findSpeedAtTime(targetTime);

    if (!result) {
        queryResult.textContent = 'Не удалось найти данные для указанного времени';
        queryResult.style.color = '#dc3545';
        return;
    }

    // Форматируем результат
    let resultText = `Скорость в момент времени ${result.time.toFixed(3)}с: ${result.speed.toFixed(3)} м/с`;
    resultText += `\nКомпоненты: Vx=${result.vx.toFixed(3)} м/с, Vy=${result.vy.toFixed(3)} м/с`;
    resultText += `\nКоординаты: x=${result.x.toFixed(3)} м, y=${result.y.toFixed(3)} м`;

    if (!result.exactMatch) {
        resultText += `\n(ближайшая доступная точка, разница: ${result.timeDiff.toFixed(4)}с)`;
    }

    queryResult.innerHTML = resultText.replace(/\n/g, '<br>');
    queryResult.style.color = result.exactMatch ? '#088725' : '#0f0107';

    // Подсвечиваем точку на анимации
    animation.highlightPointAtTime(targetTime);
}

