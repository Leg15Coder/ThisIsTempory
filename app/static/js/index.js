// DOM elements
const cardsContainer = document.getElementById('cardsContainer');
const modal = document.getElementById('modal');

// Управление модальным окном фильтров
const openFiltersBtn = document.getElementById('openAdvancedFilters');
const filtersModal = document.getElementById('filtersModal');

const fastSortForm = document.getElementById('fastSortForm');
const fastSortFormFields = fastSortForm.querySelectorAll('input, select, textarea');

// Расширенные фильтры
const applyAdvancedBtn = document.getElementById('applyAdvancedFilters');
const resetFiltersBtn = document.getElementById('resetFilters');

const postURL = fastSortForm.action;

// Open modal with card details
function openModal(id) {
    let quest_card = document.getElementById(`quest_card_${id}`);
    if (quest_card) {
        quest_card.classList.remove("new");
    }

    fetch(`/quest-app/quest/${id}`)
        .then(res => res.text())
        .then(html => {
            modal.innerHTML = html;
        });

    modal.style.display = 'flex';
}

// Общая функция для отправки фильтров
async function applyFilters() {
    const formData = new FormData(fastSortForm);

    // Добавляем данные из расширенных фильтров
    formData.append('rarity', document.getElementById('advRarity').value);
    formData.append('deadline_filter', document.getElementById('advDeadline').value);
    formData.append('author', document.getElementById('advAuthor').value);

    try {
        const response = await fetch(postURL, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        cardsContainer.innerHTML = data.cards_html;
    } catch (error) {
        console.error('Filter error:', error);
    }
}

// Дебаунс для частых событий
let filterTimeout;
function debouncedApplyFilters() {
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(applyFilters, 300);
}

// Обработчики событий
fastSortFormFields.forEach(field => {
    field.addEventListener('change', debouncedApplyFilters);
    field.addEventListener('input', debouncedApplyFilters);
});

// Для расширенных фильтров
document.querySelectorAll('#filtersModal select, #filtersModal input[type="text"]').forEach(el => {
    el.addEventListener('change', () => {
        applyFilters();
    });
});

// Close modal when clicking outside
modal.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.style.display = 'none';
    }
});

openFiltersBtn.addEventListener('click', () => {
    filtersModal.style.display = 'flex';
});

filtersModal.addEventListener('click', (e) => {
    if (e.target === filtersModal) {
        applyFilters()
        filtersModal.style.display = 'none';
    }
});

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    applyFilters();
});

applyAdvancedBtn.addEventListener('click', function() {
    const filters = {
        sortBy: document.getElementById('advSortBy').value,
        sortOrder: document.getElementById('advSortOrder').value,
        rarity: document.getElementById('advRarity').value,
        deadline: document.getElementById('advDeadline').value,
        author: document.getElementById('advAuthor').value,
        searchQuery: document.getElementById('advSearchQuery').value,
        searchIn: {
            title: document.getElementById('searchInTitle').checked,
            description: document.getElementById('searchInDescription').checked,
            author: document.getElementById('searchInAuthor').checked
        }
    };

    console.log('Advanced filters:', filters);
    filtersModal.style.display = 'none';
    // Отправить фильтры на сервер
});

resetFiltersBtn.addEventListener('click', function() {
    // Сбросить все фильтры в форме
    document.querySelectorAll('#filtersModal select').forEach(el => {
        el.value = 'all';
    });
    document.getElementById('advSortBy').value = 'created';
    document.getElementById('advSortOrder').value = 'desc';
    document.getElementById('advAuthor').value = '';
    document.getElementById('advSearchQuery').value = '';
    document.querySelectorAll('#filtersModal input[type="checkbox"]').forEach(el => {
        el.checked = el.id === 'searchInTitle' || el.id === 'searchInDescription';
    });
});

function fetchProgress(questId) {
    fetch(`/quest-app/quest/${questId}/progress`)
        .then(response => response.json())
        .then(data => updateProgress(data.progress, data.total, data.completed));
}

function updateProgress(percent, total, completed) {
    const progressFill = document.getElementById('progressFill');
    const progressPercent = document.getElementById('progressPercent');


    progressFill.style.width = `${percent}%`;
    progressPercent.textContent = percent;

    // Смена цвета
    if (percent < 30) {
        progressFill.style.backgroundColor = 'var(--accent)';
    } else if (percent < 70) {
        progressFill.style.backgroundColor = 'var(--uncommon)';
    } else {
        progressFill.style.backgroundColor = 'var(--rare)';
    }
}

function updateCheckboxSubtask(questId, subtaskId, completed) {
    fetch(`/quest-app/subtask/${subtaskId}/checkbox`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ completed: completed })
    }).then(() => fetchProgress(questId));
}

function updateNumericSubtask(questId, subtaskId, current) {
    fetch(`/quest-app/subtask/${subtaskId}/numeric`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ current: parseFloat(current) })
    }).then(() => fetchProgress(questId));
}
