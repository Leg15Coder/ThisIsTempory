document.addEventListener('DOMContentLoaded', function() {
    const questTitle = document.getElementById('questTitle');
    const questAuthor = document.getElementById('questAuthor');
    const titleCounter = document.getElementById('titleCounter');
    const authorCounter = document.getElementById('authorCounter');
    const subtasksList = document.getElementById('subtasksList');
    const emptyObjectives = document.getElementById('emptyObjectives');
    const addCheckboxBtn = document.getElementById('addCheckbox');
    const addNumericBtn = document.getElementById('addNumeric');
    const parentQuestsSearch = document.getElementById('parentQuestsSearch');
    const parentQuestsSelect = document.getElementById('parentQuests');
    const selectedParentsDiv = document.getElementById('selectedParents');
    const questForm = document.getElementById('questForm');

    let subtasks = [];
    let selectedParents = new Set();

    if (questTitle) {
        questTitle.addEventListener('input', function() {
            titleCounter.textContent = this.value.length;
        });
    }

    if (questAuthor) {
        questAuthor.addEventListener('input', function() {
            if (authorCounter) {
                authorCounter.textContent = this.value.length;
            }
        });
    }

    if (parentQuestsSearch && parentQuestsSelect) {
        parentQuestsSearch.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const options = parentQuestsSelect.options;

            for (let i = 0; i < options.length; i++) {
                const option = options[i];
                const title = option.getAttribute('data-title').toLowerCase();
                const id = option.value;

                if (title.includes(searchTerm) || id.includes(searchTerm)) {
                    option.style.display = '';
                } else {
                    option.style.display = 'none';
                }
            }
        });

        parentQuestsSelect.addEventListener('change', function() {
            selectedParents.clear();

            for (let option of this.selectedOptions) {
                selectedParents.add({
                    id: option.value,
                    title: option.getAttribute('data-title'),
                    status: option.getAttribute('data-status')
                });
            }

            renderSelectedParents();
        });
    }

    function renderSelectedParents() {
        if (!selectedParentsDiv) return;

        selectedParentsDiv.innerHTML = '';

        selectedParents.forEach(parent => {
            const tag = document.createElement('div');
            tag.className = 'parent-tag';
            tag.innerHTML = `
                <span>#${parent.id} - ${parent.title}</span>
                <span class="parent-tag-remove" data-id="${parent.id}">×</span>
            `;

            tag.querySelector('.parent-tag-remove').addEventListener('click', function() {
                const id = this.getAttribute('data-id');
                // Снять выделение в select
                for (let option of parentQuestsSelect.options) {
                    if (option.value === id) {
                        option.selected = false;
                    }
                }
                selectedParents = new Set([...selectedParents].filter(p => p.id !== id));
                renderSelectedParents();
            });

            selectedParentsDiv.appendChild(tag);
        });
    }

    // ============================================
    // ПОДЗАДАЧИ
    // ============================================

    function toggleEmptyState() {
        if (subtasks.length === 0) {
            emptyObjectives.style.display = 'block';
        } else {
            emptyObjectives.style.display = 'none';
        }
    }

    function addSubtask(type) {
        const subtaskId = Date.now();

        const subtask = {
            id: subtaskId,
            type: type,
            description: '',
            weight: 1,
            completed: false,
            target: type === 'numeric' ? 1 : null,
            current: type === 'numeric' ? 0 : null
        };

        subtasks.push(subtask);
        renderSubtask(subtask);
        toggleEmptyState();
    }

    function renderSubtask(subtask) {
        const subtaskItem = document.createElement('div');
        subtaskItem.className = 'subtask-item';
        subtaskItem.dataset.id = subtask.id;

        if (subtask.type === 'checkbox') {
            subtaskItem.innerHTML = `
                <div class="subtask-header">
                    <div class="subtask-type-icon">☑</div>
                    <input 
                        type="text" 
                        class="subtask-input subtask-desc" 
                        placeholder="Название подзадачи..."
                        value="${subtask.description}"
                    >
                    <button type="button" class="subtask-delete" data-id="${subtask.id}">×</button>
                </div>
                <div class="subtask-weight">
                    <label>Вес</label>
                    <div class="weight-slider-wrapper">
                        <input 
                            type="range" 
                            class="weight-slider" 
                            min="1" 
                            max="10" 
                            value="${subtask.weight}"
                        >
                        <span class="weight-value">${subtask.weight}</span>
                    </div>
                </div>
            `;
        } else {
            subtaskItem.innerHTML = `
                <div class="subtask-header">
                    <div class="subtask-type-icon">🔢</div>
                    <input 
                        type="text" 
                        class="subtask-input subtask-desc" 
                        placeholder="Название числовой цели..."
                        value="${subtask.description}"
                    >
                    <button type="button" class="subtask-delete" data-id="${subtask.id}">×</button>
                </div>
                <div class="subtask-numeric-row">
                    <div class="subtask-field">
                        <label>Целевое значение</label>
                        <input 
                            type="number" 
                            class="subtask-field-input target-input" 
                            min="1" 
                            value="${subtask.target}"
                        >
                    </div>
                    <div class="subtask-field">
                        <label>Текущее</label>
                        <input 
                            type="number" 
                            class="subtask-field-input current-input" 
                            min="0" 
                            value="${subtask.current}"
                        >
                    </div>
                    <div class="subtask-field">
                        <label>Вес</label>
                        <input 
                            type="number" 
                            class="subtask-field-input weight-input" 
                            min="1" 
                            max="10"
                            value="${subtask.weight}"
                        >
                    </div>
                </div>
            `;
        }

        subtasksList.appendChild(subtaskItem);
        attachSubtaskListeners(subtaskItem, subtask.id, subtask.type);
    }

    function attachSubtaskListeners(element, subtaskId, type) {
        // Описание
        const descInput = element.querySelector('.subtask-desc');
        if (descInput) {
            descInput.addEventListener('input', function() {
                updateSubtask(subtaskId, { description: this.value });
            });
        }

        // Удаление
        const deleteBtn = element.querySelector('.subtask-delete');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function() {
                deleteSubtask(subtaskId);
            });
        }

        if (type === 'checkbox') {
            // Slider для веса
            const weightSlider = element.querySelector('.weight-slider');
            const weightValue = element.querySelector('.weight-value');

            if (weightSlider && weightValue) {
                weightSlider.addEventListener('input', function() {
                    weightValue.textContent = this.value;
                    updateSubtask(subtaskId, { weight: parseInt(this.value) });
                });
            }
        } else {
            // Numeric inputs
            const targetInput = element.querySelector('.target-input');
            const currentInput = element.querySelector('.current-input');
            const weightInput = element.querySelector('.weight-input');

            if (targetInput) {
                targetInput.addEventListener('change', function() {
                    updateSubtask(subtaskId, { target: parseInt(this.value) || 1 });
                });
            }

            if (currentInput) {
                currentInput.addEventListener('change', function() {
                    updateSubtask(subtaskId, { current: parseInt(this.value) || 0 });
                });
            }

            if (weightInput) {
                weightInput.addEventListener('change', function() {
                    updateSubtask(subtaskId, { weight: parseInt(this.value) || 1 });
                });
            }
        }
    }

    function updateSubtask(id, data) {
        subtasks = subtasks.map(st => {
            if (st.id === id) {
                return { ...st, ...data };
            }
            return st;
        });
    }

    function deleteSubtask(id) {
        subtasks = subtasks.filter(st => st.id !== id);
        const element = document.querySelector(`.subtask-item[data-id="${id}"]`);
        if (element) {
            element.remove();
        }
        toggleEmptyState();
    }

    // Обработчики кнопок добавления
    if (addCheckboxBtn) {
        addCheckboxBtn.addEventListener('click', function() {
            addSubtask('checkbox');
        });
    }

    if (addNumericBtn) {
        addNumericBtn.addEventListener('click', function() {
            addSubtask('numeric');
        });
    }

    // ============================================
    // ОТПРАВКА ФОРМЫ
    // ============================================

    if (questForm) {
        questForm.addEventListener('submit', function(e) {
            e.preventDefault();

            // Подготовка данных подзадач
            const subtasksData = subtasks.map(st => {
                const baseData = {
                    type: st.type,
                    description: st.description,
                    weight: st.weight
                };

                if (st.type === 'checkbox') {
                    return {
                        ...baseData,
                        completed: st.completed
                    };
                } else {
                    return {
                        ...baseData,
                        target: st.target,
                        current: st.current
                    };
                }
            });

            // Создание скрытых полей для подзадач
            subtasksData.forEach(subtask => {
                const input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'subtasks';
                input.value = JSON.stringify(subtask);
                this.appendChild(input);
            });

            // Отправка формы
            this.submit();
        });
    }

    // ============================================
    // ИНИЦИАЛИЗАЦИЯ
    // ============================================

    toggleEmptyState();
});
