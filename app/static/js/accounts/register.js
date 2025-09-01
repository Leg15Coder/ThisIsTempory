const pass = document.getElementById('password');
const pass2 = document.getElementById('password_confirm');
const hint = document.getElementById('passHint');
const match = document.getElementById('matchHint');

function strengthScore(p) {
    let s = 0;
    if (p.length >= 8) s++;
    if (/[A-ZА-Я]/.test(p)) s++;
    if (/[a-zа-я]/.test(p)) s++;
    if (/\d/.test(p)) s++;
    if (/[^\w\s]/.test(p)) s++;
    return s; // 0..5
}

function renderStrength() {
    const val = pass.value || '';
    const score = strengthScore(val);
    const labels = ['Очень слабый', 'Слабый', 'Средний', 'Хороший', 'Сильный'];
    if (!val) { hint.textContent = ''; hint.className = 'hint'; return; }
    hint.textContent = 'Надёжность пароля: ' + labels[Math.max(0, score-1)];
    hint.className = 'hint ' + (score >= 4 ? 'ok' : 'bad');
}

function renderMatch() {
    if (!pass2.value) { match.textContent = ''; match.className = 'hint'; return; }
    const ok = pass.value && pass.value === pass2.value;
    match.textContent = ok ? 'Пароли совпадают' : 'Пароли не совпадают';
    match.className = 'hint ' + (ok ? 'ok' : 'bad');
}

pass.addEventListener('input', () => { renderStrength(); renderMatch(); });
pass2.addEventListener('input', renderMatch);
