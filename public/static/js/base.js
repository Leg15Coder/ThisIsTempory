const menuBtn = document.getElementById('menuBtn');
const sidebar = document.getElementById('sidebar');
const main = document.getElementById('main');

// Toggle sidebar
if (menuBtn && sidebar && main) {
    menuBtn.addEventListener('click', () => {
        sidebar.classList.toggle('opened');
        menuBtn.classList.toggle('open');
        main.classList.toggle('sidebar-open');
    });
}

// --- modal and subtask helpers (available on all pages) ---
function el(id){ return document.getElementById(id); }

async function openModal(id){
    try{
        const modal = el('modal');
        if (!modal) return;
        const quest_card = el(`quest_card_${id}`);
        if (quest_card) quest_card.classList.remove('new');

        const res = await fetch(`/quest-app/quest/${id}`, { credentials: 'same-origin' });
        const html = await res.text();
        modal.innerHTML = html;
        modal.style.display = 'flex';
    }catch(e){ console.error('openModal', e); }
}

function fetchProgress(questId){
    fetch(`/quest-app/quest/${questId}/progress`, { credentials: 'same-origin' })
        .then(r=>r.json()).then(data=>{
            try{ const percent = data.progress; const fill = el('progressFill'); const pct = el('progressPercent'); if (fill) fill.style.width = percent + '%'; if (pct) pct.textContent = percent; }catch(e){}
        }).catch(()=>{});
}

function updateCheckboxSubtask(questId, subtaskId, completed){
    fetch(`/quest-app/subtask/${subtaskId}/checkbox`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ completed: completed })
    }).then(()=>fetchProgress(questId));
}

function updateNumericSubtask(questId, subtaskId, current){
    fetch(`/quest-app/subtask/${subtaskId}/numeric`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ current: parseFloat(current) })
    }).then(()=>fetchProgress(questId));
}

try{ window.openModal = openModal; window.updateCheckboxSubtask = updateCheckboxSubtask; window.updateNumericSubtask = updateNumericSubtask; window.fetchProgress = fetchProgress; }catch(e){}
