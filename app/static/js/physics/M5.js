let customShape = [];
let axisPoint = null;
let drawingComplete = false;
let shapeAxisPoint = null;
let shapePreviewCanvas = document.getElementById('shapePreviewCanvas');
let axisControls = document.getElementById('axis-controls');
let resetAxisBtn = document.getElementById('resetAxisBtn');

const shapeSelect = document.getElementById('shape');
const customInertiaGroup = document.getElementById('custom-inertia-group');
const drawAreaControls = document.getElementById('draw-area-controls');
const drawCanvas = document.getElementById('drawCanvas');
const axisCanvas = document.getElementById('axisCanvas');
const inertiaInput = document.getElementById('inertia');
const tMaxInput = document.getElementById('t_max');
const theta0Input = document.getElementById('theta0');
const driveAmpInput = document.getElementById('drive_amp');
const drivePeriodInput = document.getElementById('drive_period');
const drivePhaseInput = document.getElementById('drive_phase');
const manualThetaToggle = document.getElementById('manual-theta-toggle');
const toggleDriveBtn = document.getElementById('toggleDriveBtn');
const driveParams = document.getElementById('driveParams');

const periodEstEl = document.getElementById('period-est');
const ipivotEl = document.getElementById('ipivot-val');
const hEl = document.getElementById('h-val');
const energyValEl = document.getElementById('energy-val');
const kineticEnergyEl = document.getElementById('kinetic-energy');
const potentialEnergyEl = document.getElementById('potential-energy');
const maxAngleEl = document.getElementById('max-angle');
const maxVelocityEl = document.getElementById('max-velocity');

let chartInstance = null;
let animationRunning = false;
let animationPaused = false;

let animationData = { t: [], theta: [], energy: [], omega: [], Ipivot: null, h: null, period_est: null };

let currentFrame = 0;
let playbackSpeed = 3.0;
let pxPerMeter = 100;
let tileIndex = 0;
let customBaseTheta = 0;
let thetaDiff = 0;

let requestInFlight = false;

let customCachePath = null;
let customCacheCx = 0;
let customCacheCy = 0;

let chartBufTheta = [];
let chartBufEnergy = [];

let loopingMode = false;
let baseLoop = { t: [], theta: [], energy: [], omega: [], period: null, dt: null };
let globalTime = 0;
let lastTs = 0;

let waitingForData = false;

function setupCanvasScaling() {
    const canvases = [
        'animationCanvas',
        'shapePreviewCanvas',
        'drawCanvas',
        'axisCanvas'
    ];

    canvases.forEach(canvasId => {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        if (!canvas.dataset.originalWidth) {
            canvas.dataset.originalWidth = canvas.width;
            canvas.dataset.originalHeight = canvas.height;
        }

        const container = canvas.parentElement;
        const rect = container.getBoundingClientRect();

        const dpr = window.devicePixelRatio || 1;
        const displayWidth = Math.floor(rect.width * dpr);
        const displayHeight = Math.floor(rect.height * dpr);

        if (canvas.width !== displayWidth || canvas.height !== displayHeight) {
            canvas.width = displayWidth;
            canvas.height = displayHeight;

            if (canvasId === 'animationCanvas') {
                const shapeType = shapeSelect.value;
                const length = parseFloat(document.getElementById('length').value);
                const currentTheta = animationData.theta[currentFrame] || 0;
                drawPendulum(currentTheta, shapeType, length);
            } else if (canvasId === 'shapePreviewCanvas') {
                drawShapePreview();
            } else if (canvasId === 'drawCanvas') {
                redrawCanvas(canvas, customShape);
            } else if (canvasId === 'axisCanvas') {
                redrawCanvas(canvas, customShape, axisPoint);
            }
        }
    });
}

function showNotification(message, type = 'error') {
    const notification = document.getElementById('notification');
    if (!notification) {
        console.log('Notification:', type, message);
        return;
    }
    notification.textContent = message;
    notification.className = `notification ${type}`;
    notification.style.display = 'block';
    notification.style.opacity = '1';

    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            notification.style.display = 'none';
        }, 300);
    }, 4000);
}

function calculateEnergies(theta, omega, Ipivot, m, g, h) {
    const kinetic = 0.5 * Ipivot * Math.pow(omega, 2);
    const potential = m * g * h * (1 - Math.cos(theta));
    const total = kinetic + potential;
    return { kinetic, potential, total };
}

function updateInfoPanel() {
    if (animationData.t.length === 0 || currentFrame >= animationData.t.length) return;

    const theta = animationData.theta[currentFrame];
    const omega = animationData.omega[currentFrame];
    const m = parseFloat(document.getElementById('mass').value);
    const g = parseFloat(document.getElementById('gravity').value);
    const h = animationData.h;
    const Ipivot = animationData.Ipivot;

    if (!m || !g || !h || !Ipivot) return;

    const energies = calculateEnergies(theta, omega, Ipivot, m, g, h);

    energyValEl.textContent = energies.total.toFixed(8) + ' Дж';
    kineticEnergyEl.textContent = energies.kinetic.toFixed(8) + ' Дж';
    potentialEnergyEl.textContent = energies.potential.toFixed(8) + ' Дж';

    const maxAngle = Math.max(...animationData.theta.map(Math.abs));
    const maxVelocity = Math.max(...animationData.omega.map(Math.abs));

    maxAngleEl.textContent = (maxAngle * 180 / Math.PI).toFixed(4) + '°';
    maxVelocityEl.textContent = maxVelocity.toFixed(6) + ' рад/с';

    if (animationData.period_est) {
        periodEstEl.textContent = animationData.period_est.toFixed(6) + ' с';
    }

    if (Ipivot) ipivotEl.textContent = Ipivot.toFixed(8) + ' кг·м²';
    if (h) hEl.textContent = h.toFixed(8) + ' м';
}

function enableFreeAngle(inputEl) {
    inputEl.type = 'text';
    inputEl.addEventListener('input', () => {
        let v = parseFloat(String(inputEl.value).replace(',', '.'));
        if (!isFinite(v)) return;
        if (v > Math.PI || v < -Math.PI) {
            v = ((v + Math.PI) % (2 * Math.PI)) - Math.PI;
            inputEl.value = v.toFixed(6);
        }
    });
}

function setCustomControlsVisibility(isCustom) {
    customInertiaGroup.style.display = "";
    inertiaInput.disabled = true;
    drawAreaControls.style.display = isCustom ? "flex" : "none";
    axisControls.style.display = isCustom ? "none" : "block";
    theta0Input.disabled = isCustom && !manualThetaToggle.checked;
    if (!isCustom) {
        drawShapePreview();
    }
}

function initCharts() {
    const ctx = document.getElementById('chart').getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            datasets: [
                { label: 'Угол (°)', borderColor: 'blue', borderWidth: 2, pointRadius: 0, data: [], fill: false, yAxisID: 'y' },
                { label: 'Энергия (Дж)', borderColor: 'green', borderWidth: 2, pointRadius: 0, data: [], fill: false, yAxisID: 'y1' }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            parsing: true,
            interaction: { mode: 'index' },
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Время (с)' } },
                y: { position: 'left', title: { display: true, text: 'Угол (рад)' } },
                y1: { position: 'right', title: { display: true, text: 'Энергия (Дж)' }, grid: { drawOnChartArea: false } }
            }
        }
    });
}

function chartReset() {
    chartBufTheta = [];
    chartBufEnergy = [];
    if (chartInstance && chartInstance.data) {
        chartInstance.data.datasets[0].data = [];
        chartInstance.data.datasets[1].data = [];
        chartInstance.update('none');
    }
}

function chartAppend(x, theta, energy) {
    chartBufTheta.push({ x, y: theta + thetaDiff });
    chartBufEnergy.push({ x, y: energy });
    if (chartBufTheta[chartBufTheta.length - 1].x - chartBufTheta[0].x > tMaxInput.value) chartBufTheta.shift();
    if (chartBufEnergy[chartBufEnergy.length - 1].x - chartBufEnergy[0].x > tMaxInput.value) chartBufEnergy.shift();
    if (chartInstance && chartInstance.data) {
        chartInstance.data.datasets[0].data = chartBufTheta;
        chartInstance.data.datasets[1].data = chartBufEnergy;
        chartInstance.update('none');
    }
}

function polygonAreaCentroid(points) {
    let area2 = 0, cx2 = 0, cy2 = 0;
    const n = points.length;
    for (let i = 0; i < n; i++) {
        const [x0, y0] = points[i];
        const [x1, y1] = points[(i + 1) % n];
        const cross = x0 * y1 - x1 * y0;
        area2 += cross;
        cx2 += (x0 + x1) * cross;
        cy2 += (y0 + y1) * cross;
    }
    const A = area2 / 2;
    const Cx = cx2 / (3 * area2);
    const Cy = cy2 / (3 * area2);
    return { A: Math.abs(A), Cx, Cy };
}

function polygonSecondMomentsAboutOrigin(points) {
    let Ix = 0, Iy = 0;
    const n = points.length;
    for (let i = 0; i < n; i++) {
        const [x0, y0] = points[i];
        const [x1, y1] = points[(i + 1) % n];
        const cross = x0 * y1 - x1 * y0;
        Ix += (y0 * y0 + y0 * y1 + y1 * y1) * cross;
        Iy += (x0 * x0 + x0 * x1 + x1 * x1) * cross;
    }
    return { Ix: Math.abs(Ix / 12.0), Iy: Math.abs(Iy / 12.0) };
}

function computeCustomIcmAndH(mass, points, axisPt) {
    const shifted = points.map(([x, y]) => [x - axisPt[0], y - axisPt[1]]);
    const { A, Cx, Cy } = polygonAreaCentroid(shifted);
    if (!isFinite(A) || A <= 0) return { Icm: null, h: null, Cx: null, Cy: null, shifted: null };
    const { Ix, Iy } = polygonSecondMomentsAboutOrigin(shifted);
    const rho = mass / A;
    const I_about_axis = rho * (Ix + Iy);
    const h = Math.hypot(Cx, Cy);
    const Icm = I_about_axis - mass * h * h;
    return { Icm, h, Cx, Cy, shifted };
}

function autoParamsForShapeWithAxis(m, L, shape, axisPoint) {
    if (shape === 'stick') {
        const IcmFull = (1 / 12) * m * L * L;
        const defaultH = L / 2;
        if (!axisPoint) {
            return { Icm: IcmFull, h: defaultH, theta: 0 };
        }
        const scale = 80;
        const axisXMeters = axisPoint.x / scale;
        const axisYMeters = axisPoint.y / scale;
        const h = Math.sqrt(axisXMeters * axisXMeters + axisYMeters * axisYMeters);
        const Icm = IcmFull;
        const cmY = L / 2;
        const cmOffsetX = 0 - axisXMeters;
        const cmOffsetY = cmY - axisYMeters;
        const theta = Math.atan2(cmOffsetX, cmOffsetY);
        return { Icm, h, theta };
    }
    if (shape === 'disc') {
        const R = L / 2;
        const IcmFull = 0.5 * m * R * R;
        const defaultH = R;
        if (!axisPoint) {
            return { Icm: IcmFull, h: defaultH, theta: 0 };
        }
        const scale = 80;
        const axisXMeters = axisPoint.x / scale;
        const axisYMeters = axisPoint.y / scale;
        const distance = Math.sqrt(axisXMeters * axisXMeters + axisYMeters * axisYMeters);
        const Icm = IcmFull;
        const h = distance;
        const cmOffsetX = 0 - axisXMeters;
        const cmOffsetY = 0 - axisYMeters;
        const theta = Math.atan2(cmOffsetX, cmOffsetY);
        return { Icm, h, theta };
    }
    if (shape === 'rect') {
        const w = 0.4 * L;
        const IcmFull = (1 / 12) * m * (w * w + L * L);
        const defaultH = L / 2;
        if (!axisPoint) {
            return { Icm: IcmFull, h: defaultH, theta: 0 };
        }
        const scale = 80;
        const axisXMeters = axisPoint.x / scale;
        const axisYMeters = axisPoint.y / scale;
        const distance = Math.sqrt(axisXMeters * axisXMeters + axisYMeters * axisYMeters);
        const Icm = IcmFull;
        const h = distance;
        const cmOffsetX = 0 - axisXMeters;
        const cmOffsetY = L / 2 - axisYMeters;
        const theta = Math.atan2(cmOffsetX, cmOffsetY);
        return { Icm, h, theta };
    }
    return { Icm: null, h: null, theta: null };
}

function updateInertia() {
    const m = parseFloat(document.getElementById('mass').value);
    const L = parseFloat(document.getElementById('length').value);
    const shape = shapeSelect.value;
    let Icm = null, h = null;
    if (shape !== "custom") {
        const res = autoParamsForShapeWithAxis(m, L, shape, shapeAxisPoint);
        Icm = res.Icm;
        h = res.h;
        customBaseTheta = res.theta;
        if (!manualThetaToggle.checked) theta0Input.value = customBaseTheta.toFixed(6);
    } else {
        if (customShape.length > 2 && axisPoint) {
            const r = computeCustomIcmAndH(m, customShape, axisPoint);
            Icm = r.Icm;
            h = r.h;
            customBaseTheta = Math.atan2(r.Cx, r.Cy);
            if (!manualThetaToggle.checked) theta0Input.value = customBaseTheta.toFixed(6);
        }
    }
    if (Icm != null && h != null) inertiaInput.value = Icm.toFixed(8);
    if (h != null && hEl) hEl.textContent = h.toFixed(8) + ' м';
}

function buildParamsForTile(tileIdx) {
    try {
        const m = parseFloat(document.getElementById('mass').value);
        if (m <= 0 || !isFinite(m)) throw new Error('Масса должна быть положительным числом');

        const L = parseFloat(document.getElementById('length').value);
        if (L <= 0 || !isFinite(L)) throw new Error('Длина должна быть положительным числом');

        const b = parseFloat(document.getElementById('friction').value);
        if (b < 0 || !isFinite(b)) throw new Error('Коэффициент трения не может быть отрицательным');

        let theta0, omega0;
        if (tileIdx === 0) {
            if (manualThetaToggle.checked) {
                theta0 = parseFloat(String(theta0Input.value).replace(',', '.'));
                if (!isFinite(theta0)) throw new Error('Некорректный начальный угол');
            } else {
                const shape = shapeSelect.value;
                if (shape !== 'custom') {
                    const ap = autoParamsForShapeWithAxis(m, L, shape, shapeAxisPoint);
                    theta0 = ap.theta;
                } else {
                    if (!(customShape.length > 2 && axisPoint)) throw new Error('Для произвольной формы нужно нарисовать фигуру и выбрать ось вращения');
                    const r = computeCustomIcmAndH(m, customShape, axisPoint);
                    theta0 = Math.atan2(r.Cx, r.Cy);
                }
            }
            omega0 = 0;
        } else {
            const lastIdx = animationData.theta.length - 1;
            theta0 = animationData.theta[lastIdx] || 0;
            omega0 = animationData.omega[lastIdx] || 0;
        }

        const gravity = parseFloat(document.getElementById('gravity').value);
        if (gravity <= 0 || !isFinite(gravity)) throw new Error('Ускорение свободного падения должно быть положительным');

        const t_max = parseFloat(tMaxInput.value) || 8;
        if (t_max <= 0 || !isFinite(t_max)) throw new Error('Длительность симуляции должна быть положительной');

        const shape = shapeSelect.value;
        let Icm = null, h = null;

        if (shape !== 'custom') {
            const ap = autoParamsForShapeWithAxis(m, L, shape, shapeAxisPoint);
            Icm = ap.Icm;
            h = ap.h;
        } else {
            if (!(customShape.length > 2 && axisPoint)) throw new Error('Для произвольной формы нужно нарисовать фигуру и выбрать ось вращения');
            const r = computeCustomIcmAndH(m, customShape, axisPoint);
            Icm = r.Icm;
            h = r.h;
        }

        if (!Icm || Icm <= 0 || !isFinite(Icm)) throw new Error('Не удалось рассчитать момент инерции');
        if (!h || h <= 0 || !isFinite(h)) throw new Error('Не удалось рассчитать расстояние до центра масс');
        if (theta0 > Math.PI || theta0 < -Math.PI) {
            let theta1 = ((theta0 + 3 * Math.PI) % (2 * Math.PI)) - Math.PI;
            thetaDiff = theta0 - theta1 + thetaDiff;
            theta0 = theta1;
        }

        const drive_amp = parseFloat(driveAmpInput.value) || 0;
        const drive_period = parseFloat(drivePeriodInput.value) || 0;
        const drive_phase = parseFloat(drivePhaseInput.value) || 0;

        return {
            mass: m,
            gravity,
            inertia_cm: Icm,
            h,
            friction: b,
            theta0,
            t_max,
            n_points: 5000,
            rtol: 1e-12,
            atol: 1e-14,
            method: "DOP853",
            drive_amp,
            drive_period,
            drive_phase,
            tile_index: tileIdx,
            initial_omega: omega0
        };
    } catch (error) {
        throw new Error(`Ошибка в параметрах: ${error.message}`);
    }
}

function drawShapePreview() {
    if (!shapePreviewCanvas) return;
    const ctx = shapePreviewCanvas.getContext('2d');
    ctx.clearRect(0, 0, shapePreviewCanvas.width, shapePreviewCanvas.height);
    const shape = shapeSelect.value;
    const length = parseFloat(document.getElementById('length').value);
    const scale = 80;
    const centerX = shapePreviewCanvas.width / 2;
    const centerY = shapePreviewCanvas.height / 2;
    ctx.save();
    ctx.translate(centerX, centerY);
    if (shape === "stick") {
        const Lpx = length * scale;
        ctx.strokeStyle = "#007bff";
        ctx.lineWidth = 8;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(0, Lpx);
        ctx.stroke();
    } else if (shape === "disc") {
        const Rpx = (length / 2) * scale;
        const centerY = 0;
        ctx.beginPath();
        ctx.arc(centerY, centerY, Rpx, 0, 2 * Math.PI);
        ctx.lineWidth = 3;
        ctx.strokeStyle = "#007bff";
        ctx.stroke();
        ctx.fillStyle = "#55b7ff";
        ctx.globalAlpha = 0.75;
        ctx.fill();
        ctx.globalAlpha = 1;
    } else if (shape === "rect") {
        const hpx = length * scale;
        const wpx = 0.4 * length * scale;
        ctx.fillStyle = "#55b7ff";
        ctx.globalAlpha = 0.7;
        ctx.fillRect(-wpx / 2, 0, wpx, hpx);
        ctx.globalAlpha = 1;
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#007bff";
        ctx.strokeRect(-wpx / 2, 0, wpx, hpx);
    }
    if (shapeAxisPoint) {
        ctx.beginPath();
        ctx.arc(shapeAxisPoint.x, shapeAxisPoint.y, 6, 0, 2 * Math.PI);
        ctx.fillStyle = "#ff0000";
        ctx.fill();
        ctx.strokeStyle = "#000000";
        ctx.lineWidth = 1;
        ctx.stroke();
    }
    ctx.restore();
}

function redrawCanvas(canvas, points, axis = null) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (points.length === 0) return;
    ctx.strokeStyle = '#007bff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for (let i = 1; i < points.length; ++i) ctx.lineTo(points[i][0], points[i][1]);
    if (drawingComplete || canvas === axisCanvas) ctx.closePath();
    ctx.stroke();
    for (const [x, y] of points) {
        ctx.fillStyle = '#FF7B00';
        ctx.beginPath();
        ctx.arc(x, y, 4, 0, 2 * Math.PI);
        ctx.fill();
    }
    if (axis) {
        ctx.beginPath();
        ctx.fillStyle = '#45b7d1';
        ctx.arc(axis[0], axis[1], 8, 0, 2 * Math.PI);
        ctx.fill();
    }
}

function drawPendulum(theta, shapeType, length) {
    const canvas = document.getElementById('animationCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const width = canvas.width, height = canvas.height;
    const hMeters = animationData.h || (length / 2);
    const Lmax = Math.max(length, hMeters);

    const availableHeight = height * 0.7;
    pxPerMeter = availableHeight / (Lmax * 1.5);

    const margin = width * 0.1;
    const pivotX = width / 2;
    const pivotY = height * 0.2;

    ctx.save();
    ctx.strokeStyle = 'rgba(0,0,0,0.2)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pivotX, pivotY);
    ctx.lineTo(pivotX, pivotY + (Lmax * pxPerMeter + 150));
    ctx.stroke();
    ctx.restore();
    ctx.save();
    ctx.translate(pivotX, pivotY);
    ctx.rotate(theta + customBaseTheta);
    if (shapeType === "custom" && customCachePath) {
        ctx.save();
        const scaleFactor = pxPerMeter / 100;
        ctx.scale(scaleFactor, scaleFactor);

        ctx.fillStyle = "#55b7ff";
        ctx.globalAlpha = 0.85;
        ctx.fill(customCachePath);
        ctx.globalAlpha = 1;
        ctx.lineWidth = 3;
        ctx.strokeStyle = "#007bff";
        ctx.stroke(customCachePath);
        ctx.restore();
        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, 2 * Math.PI);
        ctx.fillStyle = "#f093fb";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(customCacheCx, customCacheCy, 5, 0, 2 * Math.PI);
        ctx.fillStyle = "#45b7d1";
        ctx.fill();
    } else {
        drawStandardShape(ctx, shapeType, length, shapeAxisPoint);
    }
    ctx.restore();
}

function drawStandardShape(ctx, shapeType, length, axisPoint) {
    const scale = pxPerMeter;

    if (shapeType === "stick") {
        const Lpx = length * scale;
        const axisOffsetX = axisPoint ? axisPoint.x * (scale / 80) : 0;
        const axisOffsetY = axisPoint ? axisPoint.y * (scale / 80) : 0;

        ctx.strokeStyle = "#007bff";
        ctx.lineWidth = Math.max(3, scale / 10);
        ctx.beginPath();
        ctx.moveTo(-axisOffsetX, -axisOffsetY);
        ctx.lineTo(-axisOffsetX, Lpx - axisOffsetY);
        ctx.stroke();

        const cmY = Lpx / 2 - axisOffsetY;

        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, 2 * Math.PI);
        ctx.fillStyle = "#f093fb";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(-axisOffsetX, cmY, 5, 0, 2 * Math.PI);
        ctx.fillStyle = "#45b7d1";
        ctx.fill();

    } else if (shapeType === "disc") {
        const Rpx = (length / 2) * scale;
        const axisOffsetX = axisPoint ? axisPoint.x * (scale / 80) : 0;
        const axisOffsetY = axisPoint ? axisPoint.y * (scale / 80) : 0;

        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, 2 * Math.PI);
        ctx.fillStyle = "#f093fb";
        ctx.fill();

        ctx.beginPath();
        ctx.arc(-axisOffsetX, -axisOffsetY, Rpx, 0, 2 * Math.PI);
        ctx.lineWidth = 3;
        ctx.strokeStyle = "#007bff";
        ctx.stroke();
        ctx.fillStyle = "#55b7ff";
        ctx.globalAlpha = 0.75;
        ctx.fill();
        ctx.globalAlpha = 1;

        const cmX = -axisOffsetX;
        const cmY = -axisOffsetY;

        ctx.beginPath();
        ctx.arc(cmX, cmY, 5, 0, 2 * Math.PI);
        ctx.fillStyle = "#45b7d1";
        ctx.fill();

    } else if (shapeType === "rect") {
        const hpx = length * scale;
        const wpx = 0.4 * length * scale;
        const axisOffsetX = axisPoint ? axisPoint.x * (scale / 80) : 0;
        const axisOffsetY = axisPoint ? axisPoint.y * (scale / 80) : 0;

        ctx.fillStyle = "#55b7ff";
        ctx.globalAlpha = 0.7;
        ctx.fillRect(-wpx / 2 - axisOffsetX, -axisOffsetY, wpx, hpx);
        ctx.globalAlpha = 1;
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#007bff";
        ctx.strokeRect(-wpx / 2 - axisOffsetX, -axisOffsetY, wpx, hpx);

        ctx.beginPath();
        ctx.arc(0, 0, 6, 0, 2 * Math.PI);
        ctx.fillStyle = "#f093fb";
        ctx.fill();

        const cmX = -axisOffsetX;
        const cmY = hpx / 2 - axisOffsetY;

        ctx.beginPath();
        ctx.arc(cmX, cmY, 5, 0, 2 * Math.PI);
        ctx.fillStyle = "#45b7d1";
        ctx.fill();
    }
}

function lowerBound(arr, x) {
    let l = 0, r = arr.length;
    while (l < r) {
        const m = (l + r) >> 1;
        if (arr[m] < x) l = m + 1; else r = m;
    }
    return l === 0 ? 0 : l - 1;
}

function rebuildCustomCache() {
    customCachePath = null;
    customCacheCx = 0;
    customCacheCy = 0;
    if (!(customShape.length > 2 && axisPoint)) return;
    const p = new Path2D();
    p.moveTo(customShape[0][0] - axisPoint[0], customShape[0][1] - axisPoint[1]);
    for (let i = 1; i < customShape.length; i++) {
        p.lineTo(customShape[i][0] - axisPoint[0], customShape[i][1] - axisPoint[1]);
    }
    p.closePath();
    customCachePath = p;
    const m = parseFloat(document.getElementById('mass').value);
    const r = computeCustomIcmAndH(m, customShape, axisPoint);
    if (r) {
        customCacheCx = r.Cx || 0;
        customCacheCy = r.Cy || 0;
    }
}

function isConservative() {
    const b = parseFloat(document.getElementById('friction').value) || 0;
    const A = parseFloat(driveAmpInput.value) || 0;
    return b === 0 && A === 0;
}

function estimatePeriodFromOmega(t, omega) {
    const idx = [];
    for (let i = 1; i < omega.length; i++) {
        if (omega[i - 1] > 0 && omega[i] <= 0) idx.push(i);
        if (idx.length >= 3) break;
    }
    if (idx.length >= 2) {
        const t1 = t[idx[0]];
        const t2 = t[idx[1]];
        const T = Math.abs(t2 - t1);
        if (isFinite(T) && T > 0) return T;
    }
    return null;
}

function runSimulation(params) {
    return fetch('/physics/M5/simulate/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
    }).then(r => {
        if (!r.ok) {
            if (r.status === 422) throw new Error('Некорректные параметры симуляции');
            if (r.status === 500) throw new Error('Ошибка сервера при вычислениях');
            throw new Error('Ошибка сети: ' + r.statusText);
        }
        return r.json();
    });
}

function animate(ts) {
    if (!animationRunning || animationPaused) return;
    if (!lastTs) lastTs = ts;
    const dtWall = (ts - lastTs) / 1000;
    lastTs = ts;

    if (loopingMode) {
        globalTime += dtWall * playbackSpeed;
        const T = baseLoop.period;
        const tloc = ((globalTime % T) + T) % T;
        const i = lowerBound(baseLoop.t, tloc);
        const i0 = Math.max(0, Math.min(baseLoop.t.length - 2, i));
        const i1 = i0 + 1;
        const t0 = baseLoop.t[i0], t1 = baseLoop.t[i1];
        const w = t1 > t0 ? (tloc - t0) / (t1 - t0) : 0;
        const theta = baseLoop.theta[i0] * (1 - w) + baseLoop.theta[i1] * w;
        const energy = baseLoop.energy[i0] * (1 - w) + baseLoop.energy[i1] * w;
        const shapeType = shapeSelect.value;
        const length = parseFloat(document.getElementById('length').value);
        drawPendulum(theta, shapeType, length);
        chartAppend(globalTime, theta, energy);
        updateInfoPanel();
        requestAnimationFrame(animate);
        return;
    }

    if (currentFrame >= animationData.t.length) {
        if (!requestInFlight && !waitingForData) {
            waitingForData = true;
            prefetchNextTile().then(() => {
                waitingForData = false;
                if (animationRunning && !animationPaused) {
                    requestAnimationFrame(animate);
                }
            });
        } else {
            requestAnimationFrame(animate);
        }
        return;
    }

    const theta = animationData.theta[currentFrame] || 0;
    const energy = animationData.energy[currentFrame] || 0;
    const shapeType = shapeSelect.value;
    const length = parseFloat(document.getElementById('length').value);
    drawPendulum(theta, shapeType, length);
    chartAppend(animationData.t[currentFrame] || 0, theta, energy);
    updateInfoPanel();

    currentFrame += Math.max(1, Math.round(playbackSpeed));
    requestAnimationFrame(animate);
}

function prefetchNextTile() {
    if (loopingMode) return Promise.resolve();
    if (requestInFlight) return Promise.resolve();

    requestInFlight = true;
    const params = buildParamsForTile(tileIndex + 1);

    return fetch('/physics/M5/simulate/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params)
    }).then(r => {
        if (!r.ok) throw new Error('Ошибка сервера: ' + r.statusText);
        return r.json();
    }).then(d => {
        if (!d || !Array.isArray(d.t) || d.t.length === 0) {
            showNotification('Получены пустые данные от сервера');
            requestInFlight = false;
            return;
        }

        const allZero = arr => arr.every(v => Math.abs(v) < 1e-10);
        if (allZero(d.theta) && allZero(d.omega)) {
            showNotification('Симуляция завершена - система остановилась');
            requestInFlight = false;
            return;
        }

        const lastTime = animationData.t.length > 0 ? animationData.t[animationData.t.length - 1] : 0;
        const timeOffset = lastTime - d.t[0] + (d.t[1] - d.t[0]);

        const newT = d.t.map(t => t + timeOffset);

        animationData.t = animationData.t.concat(newT);
        animationData.theta = animationData.theta.concat(d.theta);
        animationData.omega = animationData.omega.concat(d.omega);
        animationData.energy = animationData.energy.concat(d.energy);

        tileIndex += 1;
        requestInFlight = false;

    }).catch(err => {
        console.error('Ошибка при запросе данных:', err);
        showNotification('Ошибка загрузки данных: ' + err.message);
        requestInFlight = false;
    });
}

window.addEventListener('load', () => {
    setupCanvasScaling();
    enableFreeAngle(theta0Input);
    inertiaInput.disabled = true;
    setCustomControlsVisibility(shapeSelect.value === "custom");
    updateInertia();
    redrawCanvas(drawCanvas, customShape);
    redrawCanvas(axisCanvas, customShape);
    initCharts();
    drawShapePreview();
});

window.addEventListener('resize', () => {
    setupCanvasScaling();
});

toggleDriveBtn.addEventListener('click', () => {
    if (driveParams.style.display === 'none') {
        driveParams.style.display = 'block';
        toggleDriveBtn.textContent = 'Внешняя сила ▲';
    } else {
        driveParams.style.display = 'none';
        toggleDriveBtn.textContent = 'Внешняя сила ▼';
    }
});

manualThetaToggle.addEventListener('change', () => {
    if (shapeSelect.value === 'custom') theta0Input.disabled = !manualThetaToggle.checked;
});

document.getElementById('mass').addEventListener('input', () => {
    updateInertia();
    if (shapeSelect.value === 'custom') rebuildCustomCache();
});

document.getElementById('length').addEventListener('input', updateInertia);

shapeSelect.addEventListener('change', function () {
    setCustomControlsVisibility(this.value === "custom");
    updateInertia();
});

shapePreviewCanvas.addEventListener('mousedown', function(e) {
    const rect = shapePreviewCanvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    const centerX = shapePreviewCanvas.width / 2;
    const centerY = shapePreviewCanvas.height / 2;
    const shapeX = x - centerX;
    const shapeY = y - centerY;
    shapeAxisPoint = { x: shapeX, y: shapeY };
    drawShapePreview();
    updateInertia();
});

resetAxisBtn.addEventListener('click', function() {
    shapeAxisPoint = null;
    drawShapePreview();
    updateInertia();
});

drawCanvas.addEventListener('mousedown', function (e) {
    if (drawingComplete) return;
    if (e.button === 2) customShape.pop(); else customShape.push([e.offsetX, e.offsetY]);
    redrawCanvas(drawCanvas, customShape);
    e.preventDefault();
});

drawCanvas.addEventListener('contextmenu', e => e.preventDefault());

drawCanvas.addEventListener('dblclick', function () {
    if (customShape.length >= 3) {
        drawingComplete = true;
        axisPoint = null;
        redrawCanvas(drawCanvas, customShape);
        redrawCanvas(axisCanvas, customShape);
    }
});

axisCanvas.addEventListener('mousedown', function (e) {
    if (!drawingComplete) return;
    axisPoint = [e.offsetX, e.offsetY];
    redrawCanvas(axisCanvas, customShape, axisPoint);
    rebuildCustomCache();
    updateInertia();
});

document.getElementById('resetDrawBtn').addEventListener('click', () => {
    customShape = [];
    axisPoint = null;
    drawingComplete = false;
    customCachePath = null;
    redrawCanvas(drawCanvas, customShape);
    redrawCanvas(axisCanvas, customShape);
    updateInertia();
});

document.getElementById('animation-speed').addEventListener('input', function () {
    playbackSpeed = parseFloat(this.value) * 3.0;
    document.getElementById('speed-value').textContent = (this.value + 'x');
});

document.getElementById('pauseBtn').addEventListener('click', function () {
    animationPaused = !animationPaused;
    if (!animationPaused && animationRunning) {
        lastTs = 0;
        requestAnimationFrame(animate);
    }
});

document.getElementById('resetBtn').addEventListener('click', function () {
    animationPaused = false;
    animationRunning = false;
    currentFrame = 0;
    drawPendulum(animationData.theta[0] || 0, shapeSelect.value, parseFloat(document.getElementById('length').value));
    chartReset();
});

document.getElementById('pendulumForm').addEventListener('submit', async function (event) {
    event.preventDefault();

    try {
        animationPaused = false;
        animationRunning = false;
        currentFrame = 0;
        tileIndex = 0;
        lastTs = 0;
        globalTime = 0;
        chartReset();

        if (periodEstEl) periodEstEl.textContent = '—';
        if (ipivotEl) ipivotEl.textContent = '—';
        if (hEl) hEl.textContent = '—';
        if (energyValEl) energyValEl.textContent = '—';
        if (kineticEnergyEl) kineticEnergyEl.textContent = '—';
        if (potentialEnergyEl) potentialEnergyEl.textContent = '—';
        if (maxAngleEl) maxAngleEl.textContent = '—';
        if (maxVelocityEl) maxVelocityEl.textContent = '—';

        animationData = { t: [], theta: [], energy: [], omega: [], Ipivot: null, h: null, period_est: null };
        baseLoop = { t: [], theta: [], energy: [], omega: [], period: null, dt: null };

        const params = buildParamsForTile(0);
        const data = await runSimulation(params);
        animationData = data;

        if (Array.isArray(animationData.t) && animationData.t.length > 1) {
            const Ip = animationData.Ipivot;
            const hval = animationData.h;
            if (typeof Ip === 'number' && ipivotEl) ipivotEl.textContent = Ip.toFixed(8) + ' кг·м²';
            if (typeof hval === 'number' && hEl) hEl.textContent = hval.toFixed(8) + ' м';
        }

        loopingMode = false;
        if (isConservative() && Array.isArray(animationData.omega) && animationData.omega.length > 4) {
            const T = estimatePeriodFromOmega(animationData.t, animationData.omega);
            if (T && isFinite(T) && T > 0) {
                const t0 = animationData.t[0];
                const tend = t0 + T;
                let endIdx = animationData.t.findIndex(v => v >= tend);
                if (endIdx < 0) endIdx = animationData.t.length - 1;
                baseLoop.t = animationData.t.slice(0, endIdx + 1).map(v => v - t0);
                baseLoop.theta = animationData.theta.slice(0, endIdx + 1);
                baseLoop.energy = animationData.energy.slice(0, endIdx + 1);
                baseLoop.omega = animationData.omega.slice(0, endIdx + 1);
                baseLoop.period = baseLoop.t[baseLoop.t.length - 1];
                let sumDt = 0;
                for (let i = 1; i < baseLoop.t.length; i++) sumDt += (baseLoop.t[i] - baseLoop.t[i - 1]);
                baseLoop.dt = sumDt / Math.max(1, baseLoop.t.length - 1);
                if (baseLoop.period && baseLoop.period > 0 && periodEstEl) {
                    periodEstEl.textContent = baseLoop.period.toFixed(6) + ' с';
                    loopingMode = true;
                    globalTime = 0;
                }
            }
        }

        animationRunning = true;
        showNotification('Симуляция успешно запущена', 'success');
        requestAnimationFrame(animate);

    } catch (error) {
        console.error('Ошибка симуляции:', error);
        showNotification('Ошибка: ' + error.message);
    }
});
