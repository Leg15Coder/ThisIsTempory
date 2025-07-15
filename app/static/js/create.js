const questTitle = document.getElementById('questTitle');
const questAuthor = document.getElementById('questAuthor');
const titleCounter = document.getElementById('titleCounter');
const authorCounter = document.getElementById('authorCounter');
const subtasksList = document.getElementById('subtasksList');
const addCheckboxBtn = document.getElementById('addCheckbox');
const addNumericBtn = document.getElementById('addNumeric');

let subtasks = [];

// Character counters
questTitle.addEventListener('input', function() {
    titleCounter.textContent = this.value.length;
});

questAuthor.addEventListener('input', function() {
    authorCounter.textContent = this.value.length;
});

document.addEventListener('DOMContentLoaded', function() {
    // Добавление нового чекбокса
    addCheckboxBtn.addEventListener('click', function() {
        addSubtask('checkbox');
    });

    // Добавление новой числовой цели
    addNumericBtn.addEventListener('click', function() {
        addSubtask('numeric');
    });

    function addSubtask(type) {
        const subtaskId = Date.now();
        const subtaskItem = document.createElement('div');
        subtaskItem.className = 'subtask-item';
        subtaskItem.dataset.id = subtaskId;

        if (type === 'checkbox') {
            subtaskItem.innerHTML = `
                    <input type="checkbox" id="st_${subtaskId}">
                    <input type="text" placeholder="Описание подзадачи" class="pixel-input small subtask-desc">
                    <input type="number" value="1" min="1" class="weight-input">
                    <button type="button" class="delete-subtask" data-id="${subtaskId}">×</button>
                `;
        } else {
            subtaskItem.innerHTML = `
                    <div class="numeric-inputs">
                        <input type="text" placeholder="Описание цели" class="pixel-input small subtask-desc">
                        <span>Цель:</span>
                        <input type="number" value="1" min="1" class="target-input">
                        <span>Текущее:</span>
                        <input type="number" value="0" min="0" class="current-input">
                    </div>
                    <input type="number" value="1" min="1" class="weight-input">
                    <button type="button" class="delete-subtask" data-id="${subtaskId}">×</button>
                `;
        }

        subtasksList.appendChild(subtaskItem);

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

        // Навешиваем обработчики
        const checkboxEl = subtaskItem.querySelector(`input[type="checkbox"]`);
        const descEl = subtaskItem.querySelector('.subtask-desc');
        const weightEl = subtaskItem.querySelector('.weight-input');
        const deleteBtn = subtaskItem.querySelector('.delete-subtask');

        if (checkboxEl) {
            checkboxEl.addEventListener('change', function() {
                updateSubtask(subtaskId, {
                    completed: this.checked
                });
                updateProgress();
            });
        }

        if (descEl) {
            descEl.addEventListener('input', function() {
                updateSubtask(subtaskId, {
                    description: this.value
                });
            });
        }

        if (weightEl) {
            weightEl.addEventListener('change', function() {
                updateSubtask(subtaskId, {
                    weight: parseInt(this.value) || 1
                });
                updateProgress();
            });
        }

        if (type === 'numeric') {
            const targetEl = subtaskItem.querySelector('.target-input');
            const currentEl = subtaskItem.querySelector('.current-input');

            targetEl.addEventListener('change', function() {
                const target = parseInt(this.value) || 1;
                const current = parseInt(currentEl.value) || 0;

                updateSubtask(subtaskId, {
                    target: target,
                    current: current,
                    completed: current >= target
                });
                updateProgress();
            });

            currentEl.addEventListener('change', function() {
                const current = parseInt(this.value) || 0;
                const target = parseInt(targetEl.value) || 1;

                updateSubtask(subtaskId, {
                    current: current,
                    completed: current >= target
                });
                updateProgress();
            });
        }

        deleteBtn.addEventListener('click', function() {
            deleteSubtask(subtaskId);
        });
    }

    // Обновление данных подзадачи
    function updateSubtask(id, data) {
        subtasks = subtasks.map(st => {
            if (st.id === id) {
                return { ...st, ...data };
            }
            return st;
        });
    }

    // Удаление подзадачи
    function deleteSubtask(id) {
        subtasks = subtasks.filter(st => st.id !== id);
        document.querySelector(`.subtask-item[data-id="${id}"]`).remove();

        if (subtasks.length === 0) {
            progressContainer.style.display = 'none';
        } else {
            updateProgress();
        }
    }

    // При отправке формы добавляем подзадачи в данные
    document.getElementById('questForm').addEventListener('submit', function(e) {
        e.preventDefault();

        // Prepare subtasks data
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

        // Create hidden inputs for each subtask
        subtasksData.forEach(subtask => {
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'subtasks';
            input.value = JSON.stringify(subtask);
            this.appendChild(input);
        });

        // Submit the form
        this.submit();
    });
});
