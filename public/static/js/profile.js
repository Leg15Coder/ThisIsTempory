// profile.js extracted from profile.html
document.addEventListener('DOMContentLoaded', () => {
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                display_name: document.getElementById('displayName').value,
                username: document.getElementById('username').value || null,
                bio: document.getElementById('bio').value || null
            };
            try {
                const response = await fetch('/profile/api', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (response.ok) {
                    showSuccess('Профиль обновлён');
                    const result = await response.json();
                    document.getElementById('displayNameText').textContent = result.display_name;
                } else {
                    const error = await response.json();
                    showError(error.detail);
                }
            } catch (error) {
                showError('Ошибка соединения');
            }
        });
    }

    const settingsForm = document.getElementById('settingsForm');
    if (settingsForm) {
        settingsForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const data = {
                theme: document.getElementById('theme').value,
                language: document.getElementById('language').value,
                notifications_enabled: document.getElementById('notifications').checked
            };
            try {
                const response = await fetch('/profile/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                if (response.ok) showSuccess('Настройки сохранены');
                else {
                    const err = await response.json();
                    showError(err.detail || 'Ошибка при сохранении настроек');
                }
            } catch (err) { showError('Ошибка соединения'); }
        });
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', async () => {
        await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
        window.location.href = '/';
    });
});

function showSuccess(msg) {
    const el = document.getElementById('successMessage');
    if (!el) return;
    el.textContent = msg; el.style.display = 'block'; setTimeout(()=>el.style.display='none', 3000);
}
function showError(msg) { const el = document.getElementById('errorMessage'); if (!el) return; el.textContent = msg; el.style.display='block'; setTimeout(()=>el.style.display='none', 6000); }

