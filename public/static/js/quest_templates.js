document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('createTemplateForm');
    const list = document.getElementById('templateList');
    const empty = document.getElementById('templateEmpty');
    const recurrenceType = document.getElementById('tplRecurrenceType');
    const weekdays = document.getElementById('tplWeekdays');
    const interval = document.getElementById('tplInterval');

    function toggleRecurrenceOptions() {
        const value = recurrenceType.value;
        weekdays.style.display = value === 'weekly' ? 'block' : 'none';
        interval.style.display = value === 'interval' ? 'block' : 'none';
    }

    recurrenceType.addEventListener('change', toggleRecurrenceOptions);
    toggleRecurrenceOptions();

    async function loadTemplates() {
        const res = await fetch('/api/quest-templates');
        const items = await res.json();
        renderTemplates(items);
    }

    function renderTemplates(items) {
        list.innerHTML = '';
        if (!items || items.length === 0) {
            empty.style.display = 'block';
            return;
        }
        empty.style.display = 'none';

        items.forEach(t => {
            const card = document.createElement('div');
            card.className = 'template-card';
            card.innerHTML = `
                <div class="template-info">
                    <h3>${t.title}</h3>
                    <div class="template-meta">
                        <span class="badge">${t.recurrence_type}</span>
                        <span class="badge">${t.duration_hours}ч</span>
                        <span class="badge">${t.rarity}</span>
                    </div>
                </div>
                <div>
                    <button class="btn-buy" data-id="${t.id}">Создать сейчас</button>
                </div>
            `;
            const btn = card.querySelector('.btn-buy');
            btn.addEventListener('click', async () => {
                const resp = await fetch(`/api/quest-templates/${t.id}/generate`, { method: 'POST' });
                if (!resp.ok) {
                    const err = await resp.json();
                    alert(err.detail || 'Ошибка генерации');
                    return;
                }
                alert('Квест создан!');
            });
            list.appendChild(card);
        });
    }

    if (form) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = new FormData(form);
            const weekdaysSelected = data.getAll('weekdays');
            const payload = {
                title: data.get('title'),
                description: data.get('description') || null,
                cost: Number(data.get('cost') || 0),
                rarity: data.get('rarity') || 'Обычный',
                recurrence_type: data.get('recurrence_type'),
                duration_hours: Number(data.get('duration_hours') || 24),
                weekdays: weekdaysSelected.length ? weekdaysSelected.join(',') : null,
                interval_hours: data.get('interval_hours') ? Number(data.get('interval_hours')) : null,
                start_date: data.get('start_date') || null,
                start_time: data.get('start_time') || null,
                end_date: data.get('end_date') || null,
                end_time: data.get('end_time') || null,
                is_active: true
            };

            const resp = await fetch('/api/quest-templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!resp.ok) {
                const err = await resp.json();
                alert(err.detail || 'Ошибка создания');
                return;
            }
            form.reset();
            toggleRecurrenceOptions();
            await loadTemplates();
        });
    }

    loadTemplates();
});
