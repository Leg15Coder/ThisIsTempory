let currentMode = 'separated';

const MODE_CONFIG = {
    separated: {
        subtitle:   'Расчёт поля двух разделённых заряженных сфер',
        labelR1:    'Радиус первой сферы R₁ (м)',
        labelR2:    'Радиус второй сферы R₂ (м)',
        hintR1:     'Диапазон: 0.001 – 1.0 м',
        hintR2:     'Диапазон: 0.001 – 1.0 м',
        showD:      true,
        labelD:     'Расстояние между центрами d (м)',
        hintD:      'Должно быть > R₁ + R₂',
        defaultD:   0.15,
        labelQ1:    'Заряд сферы 1:',
        labelQ2:    'Заряд сферы 2:',
        labelCTh:   'Ёмкость (теор.):',
        vizTitle1:  '🎨 Распределение заряда на сферах (3D)',
    },
    concentric: {
        subtitle:   'Расчёт поля концентрических сфер (сферичний конденсатор, смещение центров допускается)',
        labelR1:    'Радиус внутренней сферы R₁ (м)',
        labelR2:    'Радиус внешней сферы R₂ (м)',
        hintR1:     'Должен быть < R₂',
        hintR2:     'Должен быть > R₁',
        showD:      true,
        labelD:     '',
        hintD:      'Смещение центров d (м)',
        defaultD:   0,
        labelQ1:    'Заряд внутренней сферы:',
        labelQ2:    'Заряд внешней сферы:',
        labelCTh:   'Ёмкость (теор.):',
        vizTitle1:  '🎨 Распределение заряда (2D)',
    },
    plates: {
        subtitle:   'Расчёт поля плоского конденсатора (параллельные пластины)',
        labelR1:    'Полуразмер пластины 1 a₁ (м)',
        labelR2:    'Полуразмер пластины 2 a₂ (м)',
        hintR1:     'Полусторона квадратной пластины',
        hintR2:     'Полусторона квадратной пластины',
        showD:      true,
        labelD:     'Расстояние между пластинами d (м)',
        hintD:      'Должно быть > 0',
        defaultD:   0.05,
        labelQ1:    'Заряд пластины 1:',
        labelQ2:    'Заряд пластины 2:',
        labelCTh:   'Ёмкость (теор.):',
        vizTitle1:  '🎨 Распределение заряда на пластинах (2D)',
    },
};

function setMode(mode) {
    currentMode = mode;
    const cfg = MODE_CONFIG[mode];

    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    document.getElementById('header-subtitle').textContent = cfg.subtitle;

    document.getElementById('label-R1').textContent = cfg.labelR1;
    document.getElementById('label-R2').textContent = cfg.labelR2;
    document.getElementById('hint-R1').textContent  = cfg.hintR1;
    document.getElementById('hint-R2').textContent  = cfg.hintR2;

    const groupD = document.getElementById('group-d');
    const inputD = document.getElementById('d');
    if (cfg.showD) {
        groupD.style.display = '';
        document.getElementById('label-d').textContent = cfg.labelD;
        document.getElementById('hint-d').textContent  = cfg.hintD;
        if (mode === 'plates') {
            inputD.value = cfg.defaultD;
            inputD.min   = '0.001';
        } else {
            inputD.min = '0.001';
            updateMinDistance();
        }
    } else {
        groupD.style.display = 'none';
        inputD.value = '0';
    }

    document.getElementById('label-Q1').textContent     = cfg.labelQ1;
    document.getElementById('label-Q2').textContent     = cfg.labelQ2;
    document.getElementById('label-C-theory').textContent = cfg.labelCTh;
    document.getElementById('viz-title-1').textContent  = cfg.vizTitle1;

    document.getElementById('results').classList.remove('active');
    document.getElementById('error').classList.remove('active');
}

async function calculate() {
    const R1 = parseFloat(document.getElementById('R1').value);
    const R2 = parseFloat(document.getElementById('R2').value);
    const n_divisions = parseInt(document.getElementById('n_divisions').value);
    const V  = parseFloat(document.getElementById('V').value);
    let d    = parseFloat(document.getElementById('d').value);

    if (currentMode === 'separated' && d <= R1 + R2) {
        showError(`Расстояние d должно быть больше суммы радиусов (${(R1 + R2).toFixed(3)} м)`);
        return;
    }
    if (currentMode === 'concentric' && Math.abs(R1 - R2) < 0.001) {
        showError('Радиусы концентрических сфер должны отличаться минимум на 0.001 м');
        return;
    }
    if (currentMode === 'plates' && d <= 0) {
        showError('Расстояние между пластинами должно быть > 0');
        return;
    }

    document.getElementById('results').classList.remove('active');
    document.getElementById('error').classList.remove('active');
    document.getElementById('loading').classList.add('active');
    document.querySelector('.calculate-btn').disabled = true;

    try {
        const response = await fetch('/physics/M21/calculate', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: currentMode, R1, R2, d, V, n_divisions }),
        });

        const data = await response.json();

        if (!response.ok) {
            let msg = 'Ошибка расчёта';
            if (data.detail) {
                if (typeof data.detail === 'string') {
                    msg = data.detail;
                } else if (Array.isArray(data.detail)) {
                    msg = data.detail.map(e => e.msg || JSON.stringify(e)).join('; ');
                } else {
                    msg = JSON.stringify(data.detail);
                }
            }
            throw new Error(msg);
        }

        displayResults(data);

    } catch (error) {
        const msg = (error instanceof Error) ? error.message : JSON.stringify(error);
        showError(msg);
    } finally {
        document.getElementById('loading').classList.remove('active');
        document.querySelector('.calculate-btn').disabled = false;
    }
}

function displayResults(data) {
    document.getElementById('Q1-value').textContent  = data.Q1.toExponential(3) + ' Кл';
    document.getElementById('Q2-value').textContent  = data.Q2.toExponential(3) + ' Кл';
    document.getElementById('C-numerical').textContent = (data.C_numerical * 1e12).toFixed(4) + ' пФ';
    document.getElementById('n-elements').textContent  = data.n_elements;

    document.getElementById('field-viz').src      = 'data:image/png;base64,' + data.field_img;

    document.getElementById('results').classList.add('active');
    document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
}

function showError(message) {
    document.getElementById('error-text').textContent = message;
    document.getElementById('error').classList.add('active');
    document.getElementById('error').scrollIntoView({ behavior: 'smooth' });
}

function updateMinDistance() {
    if (currentMode !== 'separated') return;
    const R1 = parseFloat(document.getElementById('R1').value) || 0;
    const R2 = parseFloat(document.getElementById('R2').value) || 0;
    const minD = (R1 + R2 + 0.001).toFixed(3);
    const inputD = document.getElementById('d');
    inputD.min = minD;
    document.getElementById('hint-d').textContent = `Должно быть > ${minD} м`;
    if (parseFloat(inputD.value) <= R1 + R2) {
        inputD.value = minD;
    }
}

document.addEventListener('DOMContentLoaded', function () {
    const r1 = document.getElementById('R1');
    const r2 = document.getElementById('R2');
    if (r1) r1.addEventListener('input', updateMinDistance);
    if (r2) r2.addEventListener('input', updateMinDistance);
    setMode('separated');
});
