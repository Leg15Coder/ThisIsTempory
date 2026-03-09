// DOM elements
const cardsContainer = document.getElementById('cardsContainer');
const modal = document.getElementById('modal');

// Safe element access helpers
function el(id){ return document.getElementById(id); }

// Управление модальным окном фильтров
const openFiltersBtn = el('openAdvancedFilters');
const filtersModal = el('filtersModal');

const fastSortForm = el('fastSortForm');
const fastSortFormFields = fastSortForm ? fastSortForm.querySelectorAll('input, select, textarea') : [];

// Open modal with card details
function openModal(id) {
    try {
        let quest_card = document.getElementById(`quest_card_${id}`);
        if (quest_card) {
            quest_card.classList.remove("new");
        }

        fetch(`/quest-app/quest/${id}`, { credentials: 'same-origin' })
            .then(res => res.text())
            .then(html => {
                if (!modal) return;
                modal.innerHTML = html;
                modal.style.display = 'flex';
            })
            .catch(err => {
                console.error('Failed to load quest modal:', err);
            });
    } catch (e) {
        console.error('openModal error', e);
    }
}

// export to global so inline onclick handlers can call it reliably
try { window.openModal = openModal; } catch(e){}

// Общая функция для отправки фильтров
async function applyFilters() {
    if (!fastSortForm) return;
    const formData = new FormData(fastSortForm);

    // Добавляем данные из расширенных фильтров, если есть
    const advRarity = el('advRarity');
    const advDeadline = el('advDeadline');
    const advAuthor = el('advAuthor');
    if (advRarity) formData.append('rarity', advRarity.value);
    if (advDeadline) formData.append('deadline_filter', advDeadline.value);
    if (advAuthor) formData.append('author', advAuthor.value);

    try {
        const response = await fetch(fastSortForm.action, {
            method: 'POST',
            body: formData,
            credentials: 'same-origin'
        });

        const data = await response.json();
        if (cardsContainer && data.cards_html) cardsContainer.innerHTML = data.cards_html;
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
if (fastSortFormFields && fastSortFormFields.length) {
    fastSortFormFields.forEach(field => {
        field.addEventListener('change', debouncedApplyFilters);
        field.addEventListener('input', debouncedApplyFilters);
    });
}

// Для расширенных фильтров
if (el('filtersModal')) {
    document.querySelectorAll('#filtersModal select, #filtersModal input[type="text"]').forEach(elm => {
        elm.addEventListener('change', () => {
            applyFilters();
        });
    });
}

// Close modal when clicking outside
if (modal) {
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
}

if (openFiltersBtn) {
    openFiltersBtn.addEventListener('click', () => {
        if (filtersModal) filtersModal.style.display = 'flex';
    });
}

if (filtersModal) {
    filtersModal.addEventListener('click', (e) => {
        if (e.target === filtersModal) {
            applyFilters()
            filtersModal.style.display = 'none';
        }
    });
}

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', () => {
    applyFilters();
});

// handlers for apply/reset buttons
if (el('applyAdvancedFilters')) {
    el('applyAdvancedFilters').addEventListener('click', function() {
        const filters = {
            sortBy: el('advSortBy') ? el('advSortBy').value : 'created',
            sortOrder: el('advSortOrder') ? el('advSortOrder').value : 'desc',
            rarity: el('advRarity') ? el('advRarity').value : 'all',
            deadline: el('advDeadline') ? el('advDeadline').value : 'all',
            author: el('advAuthor') ? el('advAuthor').value : '',
            searchQuery: el('advSearchQuery') ? el('advSearchQuery').value : '',
            searchIn: {
                title: el('searchInTitle') ? el('searchInTitle').checked : true,
                description: el('searchInDescription') ? el('searchInDescription').checked : true,
                author: el('searchInAuthor') ? el('searchInAuthor').checked : false
            }
        };

        console.log('Advanced filters:', filters);
        if (filtersModal) filtersModal.style.display = 'none';
        // Отправить фильтры на сервер (если нужно)
    });
}

if (el('resetFilters')) {
    el('resetFilters').addEventListener('click', function() {
        // Сбросить все фильтры в форме
        document.querySelectorAll('#filtersModal select').forEach(elm => {
            elm.value = 'all';
        });
        if (el('advSortBy')) el('advSortBy').value = 'created';
        if (el('advSortOrder')) el('advSortOrder').value = 'desc';
        if (el('advAuthor')) el('advAuthor').value = '';
        if (el('advSearchQuery')) el('advSearchQuery').value = '';
        document.querySelectorAll('#filtersModal input[type="checkbox"]').forEach(ch => {
            ch.checked = (ch.id === 'searchInTitle' || ch.id === 'searchInDescription');
        });
    });
}

function fetchProgress(questId) {
    fetch(`/quest-app/quest/${questId}/progress`, { credentials: 'same-origin' })
        .then(response => response.json())
        .then(data => updateProgress(data.progress, data.total, data.completed)).catch(()=>{});
}

// export helper functions
try { window.fetchProgress = fetchProgress; } catch(e){}

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
        credentials: 'same-origin',
        body: JSON.stringify({ completed: completed })
    }).then(() => fetchProgress(questId));
}

function updateNumericSubtask(questId, subtaskId, current) {
    fetch(`/quest-app/subtask/${subtaskId}/numeric`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'same-origin',
        body: JSON.stringify({ current: parseFloat(current) })
    }).then(() => fetchProgress(questId));
}

// export to global so inline handlers can call them
try { window.updateCheckboxSubtask = updateCheckboxSubtask; window.updateNumericSubtask = updateNumericSubtask; } catch(e){}
