// Extracted JS for physics/base.html
const models = [
    {
        id: 'projectile-motion',
        title: 'Бросок под углом к горизонту',
        description: 'Моделирование траектории полёта тела с учётом вязкого трения и лобового сопротивления. Позволяет изучать влияние различных параметров на дальность и высоту полёта.',
        image: '/static/img/projectile-motion.png',
        category: 'mechanics',
        url: '/physics/M1'
    },
    {
        id: 'solar-system',
        title: 'Симуляция полёта космического корабля с Земли на Марс',
        description: 'Симуляция полёта космического корабля с Земли на Марс.',
        image: '/static/img/solar-system.png',
        category: 'mechanics',
        url: '/physics/M3'
    },
    {
        id: 'physical-pendulum',
        title: 'Физический Маятник',
        description: 'Исследование физического маятника подвешенного в поле силы тяжести при наличии внешней силы.',
        image: '/static/img/physical-pendulum.png',
        category: 'mechanics',
        url: '/physics/M5'
    },
    {
        id: 'spins-system',
        title: 'Спиновые системы',
        description: 'Исследование спиновой системы при постоянной температуре во внешнем магнитном поле.',
        image: '/static/img/spins-system.png',
        category: 'mkt',
        url: '/physics/M10'
    }
];

function renderModels(filteredModels = models) {
    const grid = document.getElementById('modelsGrid');
    if (!grid) return;
    if (filteredModels.length === 0) {
        grid.innerHTML = '<div class="no-results">Модели не найдены. Попробуйте изменить поисковый запрос.</div>';
        return;
    }

    grid.innerHTML = filteredModels.map(model => `
        <div class="model-card" data-category="${model.category}">
            <div class="card-image">
                <img src="${model.image}" alt="${model.title}" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="image-fallback" style="display: none;">
                    <div class="fallback-content">
                        <span style="font-size: 48px; margin-bottom: 10px;">📊</span>
                        <span style="font-weight: bold; color: white;">Физическая модель</span>
                    </div>
                </div>
            </div>
            <div class="card-content">
                <h3>${model.title}</h3>
                <p>${model.description}</p>
                <div class="card-meta">
                    <a href="${model.url}" class="card-link">Открыть модель →</a>
                </div>
            </div>
        </div>
    `).join('');

    document.querySelectorAll('.model-card').forEach(card => {
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.card-link')) {
                const link = card.querySelector('.card-link');
                if (link) window.location.href = link.href;
            }
        });
    });
}

document.addEventListener('DOMContentLoaded', () => renderModels());

// global fallback for images
window.addEventListener('error', (e) => {
    const t = e.target;
    if (t && t.tagName === 'IMG' && t.parentElement && t.parentElement.classList.contains('card-image')) {
        t.style.display = 'none';
        const fallback = document.createElement('div');
        fallback.style.cssText = 'width:100%;height:100%;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;align-items:center;justify-content:center;color:white;font-weight:bold;';
        fallback.textContent = '📊 Модель';
        t.parentElement.appendChild(fallback);
    }
}, true);

