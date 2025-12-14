let currentSnapshot = null;
let isRunning = false;
let isPaused = false;
let stepCount = 0;
let animationFrameId = null;

function updateValueDisplay(inputId, displayId, suffix = '') {
    const input = document.getElementById(inputId);
    const display = document.getElementById(displayId);
    if (input && display) {
        display.textContent = input.value + suffix;
    }
}

function updateFieldArrowByStrength(strength) {
    const arrow = document.getElementById('fieldArrow');
    const val = parseFloat(strength);
    if (isNaN(val) || val === 0) {
        arrow.textContent = '·';
    } else if (val > 0) {
        arrow.textContent = '↓';
    } else {
        arrow.textContent = '↑';
    }
}

function setStatus(message, type = 'idle') {
    const statusEl = document.getElementById('status');
    statusEl.textContent = message;
    statusEl.className = 'status-line ' + type;
}

function updateStepCounter() {
    document.getElementById('stepCounter').textContent = stepCount;
}

document.getElementById('temperature').addEventListener('input', (e) => {
    updateValueDisplay('temperature', 'tempValue', ' K');
});
document.getElementById('fieldStrength').addEventListener('input', (e) => {
    updateValueDisplay('fieldStrength', 'fieldValue', ' T');
    updateFieldArrowByStrength(e.target.value);
});

const angleInput = document.getElementById('fieldAngle');
if (angleInput) {
    angleInput.addEventListener('input', (e) => {
        angleInput.value = 0;
        updateValueDisplay('fieldAngle', 'angleValue', '°');
    });
}
document.getElementById('framePause').addEventListener('input', (e) => {
    updateValueDisplay('framePause', 'pauseValue', ' мс');
});
document.getElementById('cubeSize').addEventListener('input', (e) => {
    const size = parseInt(e.target.value) || 1;
    document.getElementById('sizeValue').textContent = size + '×' + size + '×' + size;
});

function drawVisualization(snapshot) {
    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');

    const gridSize = snapshot.up_count.length;
    const cellSize = canvas.width / gridSize;

    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const showArrows = gridSize < 50;

    for (let i = 0; i < gridSize; i++) {
        for (let j = 0; j < gridSize; j++) {
            const up = snapshot.up_count[i][j];
            const down = snapshot.down_count[i][j];
            const total = up + down;

            const ratio = total > 0 ? up / total : 0.5;
            const red = Math.round(255 * (1 - ratio));
            const blue = Math.round(255 * ratio);

            const x = i * cellSize;
            const y = j * cellSize;

            ctx.fillStyle = `rgb(${red}, 0, ${blue})`;
            ctx.fillRect(x, y, cellSize, cellSize);

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
            ctx.lineWidth = 0.5;
            ctx.strokeRect(x, y, cellSize, cellSize);

            if (!showArrows) continue;

            const angle = snapshot.directions[i][j];
            const centerX = x + cellSize / 2;
            const centerY = y + cellSize / 2;
            const arrowLen = cellSize * 0.3;

            ctx.save();
            ctx.translate(centerX, centerY);
            ctx.rotate(angle);

            ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(-arrowLen/2, 0);
            ctx.lineTo(arrowLen/2, 0);
            ctx.stroke();

            ctx.beginPath();
            ctx.moveTo(arrowLen/2, 0);
            ctx.lineTo(arrowLen/2 - 4, -3);
            ctx.lineTo(arrowLen/2 - 4, 3);
            ctx.closePath();
            ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.fill();

            ctx.restore();
        }
    }
}

function resetField() {
    const fieldInput = document.getElementById('fieldStrength');
    if (!fieldInput) return;
    fieldInput.value = 0;
    updateValueDisplay('fieldStrength', 'fieldValue', ' T');
    updateFieldArrowByStrength(0);
}

function updateStatistics(snapshot) {
    document.getElementById('energyValue').textContent = snapshot.energy.toFixed(2);
    document.getElementById('magnetizationValue').textContent = snapshot.magnetization.toFixed(3);
    document.getElementById('tempStatValue').textContent = snapshot.temperature.toFixed(1) + ' K';
    document.getElementById('fieldStatValue').textContent = snapshot.field.toFixed(2) + ' T';

    updateFieldArrowByStrength(snapshot.field);
}

async function stepSimulation() {
    if (!isRunning) return;
    if (isPaused) {
        setTimeout(() => stepSimulation(), 50);
        return;
    }

    const request = {
        temperature_K: parseFloat(document.getElementById('temperature').value),
        field_angle: 0.0,
        field_strength_T: parseFloat(document.getElementById('fieldStrength').value),
        cube_size: parseInt(document.getElementById('cubeSize').value) || 1,
        num_steps: 1
    };

    try {
        const response = await fetch('/physics/M10/step', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        currentSnapshot = data.snapshot;
        drawVisualization(currentSnapshot);
        updateStatistics(currentSnapshot);

        stepCount++;
        updateStepCounter();

        const pauseMs = parseInt(document.getElementById('framePause').value) || 0;
        setTimeout(() => stepSimulation(), pauseMs);

    } catch (error) {
        console.error('Error:', error);
        setStatus('❌ Ошибка: ' + error.message, 'error');
        isRunning = false;
        document.getElementById('startBtn').disabled = false;
        document.getElementById('pauseBtn').disabled = true;
    }
}

function startSimulation() {
    if (isRunning) return;

    setStatus('▶️ Симуляция работает...', 'running');
    document.getElementById('startBtn').disabled = true;
    document.getElementById('pauseBtn').disabled = false;

    isRunning = true;
    isPaused = false;
    stepCount = 0;
    updateStepCounter();
    stepSimulation();
}

function togglePause() {
    if (!isRunning) return;

    isPaused = !isPaused;
    if (isPaused) {
        setStatus('⏸️ Пауза', 'idle');
        document.getElementById('pauseBtn').textContent = '▶️ Продолжить';
    } else {
        setStatus('▶️ Симуляция работает...', 'running');
        document.getElementById('pauseBtn').textContent = '⏸️ Пауза';
        stepSimulation();
    }
}

async function resetSimulation() {
    isRunning = false;
    isPaused = false;
    stepCount = 0;
    currentSnapshot = null;
    updateStepCounter();

    const canvas = document.getElementById('canvas');
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    document.getElementById('startBtn').disabled = false;
    document.getElementById('pauseBtn').disabled = true;
    document.getElementById('pauseBtn').textContent = '⏸️ Пауза';

    const request = {
        temperature_K: parseFloat(document.getElementById('temperature').value),
        field_angle: 0.0,
        field_strength_T: parseFloat(document.getElementById('fieldStrength').value),
        cube_size: parseInt(document.getElementById('cubeSize').value) || 1,
        num_steps: 1
    };

    const response = await fetch('/physics/M10/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request)
    });

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    setStatus('🔄 Система сброшена', 'idle');
}

window.addEventListener('load', () => {
    updateValueDisplay('temperature', 'tempValue', ' K');
    updateValueDisplay('fieldStrength', 'fieldValue', ' T');
    updateValueDisplay('fieldAngle', 'angleValue', '°');
    updateValueDisplay('framePause', 'pauseValue', ' мс');
    updateFieldArrowByStrength(0);

    const canvas = document.getElementById('canvas');
    canvas.width = 600;
    canvas.height = 600;

    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    setStatus('✅ Готово. Нажмите "Запустить"', 'idle');
});

window.addEventListener('beforeunload', () => {
    isRunning = false;
});