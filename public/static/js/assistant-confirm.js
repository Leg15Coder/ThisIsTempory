document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('assistantConfirmForm');
    const statusEl = document.getElementById('confirmStatus');
    if (!form) return;

    const tokenEl = document.getElementById('confirmToken');
    const token = tokenEl?.value || '';

    if (token) {
        try {
            const saved = JSON.parse(localStorage.getItem(`assistantDraft:${token}`) || 'null');
            const draft = saved?.draft;
            if (draft) {
                const byId = (id) => document.getElementById(id);
                if (byId('confirmTitle') && !byId('confirmTitle').value) byId('confirmTitle').value = draft.title || '';
                if (byId('confirmAuthor') && !byId('confirmAuthor').value) byId('confirmAuthor').value = draft.author || 'AI Assistant';
                if (byId('confirmDescription') && !byId('confirmDescription').value) byId('confirmDescription').value = draft.description || '';
                if (byId('confirmRarity')) byId('confirmRarity').value = draft.rarity || byId('confirmRarity').value || 'common';
                if (byId('confirmCost') && !byId('confirmCost').value) byId('confirmCost').value = draft.cost || 100;
                if (byId('confirmDeadlineDate') && !byId('confirmDeadlineDate').value) byId('confirmDeadlineDate').value = draft.deadline_date || '';
                if (byId('confirmDeadlineTime') && !byId('confirmDeadlineTime').value) byId('confirmDeadlineTime').value = draft.deadline_time || '';
            }
        } catch (e) {}
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const tokenValue = document.getElementById('confirmToken')?.value || '';
        const userId = document.getElementById('confirmUserId')?.value || '';
        const sessionId = document.getElementById('confirmSessionId')?.value || 'assistant-main';
        const payload = {
            confirmation_token: tokenValue,
            user_id: userId,
            session_id: sessionId,
            quest: {
                title: document.getElementById('confirmTitle')?.value || '',
                author: document.getElementById('confirmAuthor')?.value || 'AI Assistant',
                description: document.getElementById('confirmDescription')?.value || '',
                rarity: document.getElementById('confirmRarity')?.value || 'common',
                cost: Number(document.getElementById('confirmCost')?.value || 0),
                deadline_date: document.getElementById('confirmDeadlineDate')?.value || null,
                deadline_time: document.getElementById('confirmDeadlineTime')?.value || null,
            }
        };

        if (statusEl) statusEl.textContent = 'Создаю квест...';
        try {
            const response = await fetch('/api/assistant/confirm-quest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) {
                if (statusEl) statusEl.textContent = data.detail || 'Не удалось создать квест.';
                return;
            }
            try { localStorage.removeItem(`assistantDraft:${tokenValue}`); } catch (e) {}
            if (statusEl) statusEl.textContent = data.message || 'Квест создан.';
            if (data.redirect_to) {
                window.location.href = data.redirect_to;
            }
        } catch (error) {
            if (statusEl) statusEl.textContent = 'Ошибка соединения при подтверждении квеста.';
        }
    });
});
