// Extracted JS (minimal) for main hub if needed in future. Currently hub is static; keep file for future interactive features.
document.addEventListener('DOMContentLoaded', function(){
    // placeholder for hub interactions
    try {
        // Example: highlight active card if route matches
        const path = location.pathname || '/';
        document.querySelectorAll('.hub-card a').forEach(a => {
            if (a.getAttribute('href') === path) {
                a.classList.add('active');
            }
        });
    } catch(e) {}

    // Support both main hub and iframe assistant UI
    const root = document.getElementById('assistantMainHub') || document.getElementById('assistantRoot');
    if (!root) return;

    const userId = root.dataset.userId || document.body.dataset.userId || '';
    const sessionId = root.dataset.sessionId || root.dataset.sessionId || document.body.dataset.assistantSessionId || 'assistant-main';
    const audioMime = root.dataset.audioMime || 'audio/webm';

    const textInput = document.getElementById('assistantQuickText');
    const submitBtn = document.getElementById('assistantQuickSubmit');
    const streamBox = document.getElementById('assistantQuickStream');
    const statusBox = document.getElementById('assistantQuickStatus');
    const metaBox = document.getElementById('assistantQuickMeta');
    const draftCard = document.getElementById('assistantQuestDraftCard');
    const draftList = document.getElementById('assistantQuestDraftList');
    const confirmLink = document.getElementById('assistantConfirmLink');
    const voiceBtn = document.getElementById('assistantVoiceBtn');
    const voiceState = document.getElementById('assistantVoiceState');

    let mediaRecorder = null;
    let mediaChunks = [];
    let isRecording = false;

    function setStatus(message) {
        if (statusBox) statusBox.textContent = message || '';
    }

    function fakeTypeText(text) {
        if (!streamBox) return;
        streamBox.textContent = '';
        const content = text || '';
        let index = 0;
        const interval = setInterval(() => {
            streamBox.textContent += content[index] || '';
            index += 1;
            if (index >= content.length) {
                clearInterval(interval);
            }
        }, 12);
    }

    function buildConfirmUrl(token, draft) {
        const params = new URLSearchParams({ token, session_id: sessionId });
        Object.entries(draft || {}).forEach(([key, value]) => {
            if (value !== null && value !== undefined && String(value).length) {
                params.set(key, String(value));
            }
        });
        return `/main/assistant/confirm?${params.toString()}`;
    }

    function renderDraft(action) {
        if (!draftCard || !draftList || !confirmLink) return;
        const draft = action?.result?.quest || action?.params;
        const token = action?.confirmation_token;
        if (!draft || !token) {
            draftCard.classList.add('assistant-hidden');
            draftList.innerHTML = '';
            confirmLink.href = '#';
            return;
        }
        draftCard.classList.remove('assistant-hidden');
        draftList.innerHTML = `
            <div class="assistant-draft-item"><strong>Название:</strong> ${draft.title || '—'}</div>
            <div class="assistant-draft-item"><strong>Автор:</strong> ${draft.author || '—'}</div>
            <div class="assistant-draft-item"><strong>Редкость:</strong> ${draft.rarity || 'common'}</div>
            <div class="assistant-draft-item"><strong>Награда:</strong> ${draft.cost || 0}</div>
            <div class="assistant-draft-item"><strong>Дедлайн:</strong> ${(draft.deadline_date || '—')} ${(draft.deadline_time || '')}</div>
            <div class="assistant-draft-item"><strong>Описание:</strong> ${draft.description || '—'}</div>
        `;
        const confirmUrl = buildConfirmUrl(token, draft);
        confirmLink.href = confirmUrl;
        try { localStorage.setItem(`assistantDraft:${token}`, JSON.stringify({ draft, sessionId, userId })); } catch (e) {}
    }

    async function sendQuickRequest(payload) {
        setStatus('Ассистент думает...');
        try {
            const response = await fetch('/api/assistant/quick', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok) {
                setStatus(data.detail || 'Не удалось получить ответ ассистента.');
                return;
            }
            fakeTypeText(data.response_text || 'Пустой ответ.');
            if (metaBox) {
                metaBox.classList.remove('assistant-hidden');
                metaBox.innerHTML = `
                    <span>Токены: ${data.tokens_used || 0}</span>
                    <span>Кеш: ${data.cached ? 'да' : 'нет'}</span>
                    <span>Нужно уточнение: ${data.requires_clarification ? 'да' : 'нет'}</span>
                `;
            }
            renderDraft(data.action);
            setStatus(data.requires_clarification ? (data.clarification_question || 'Нужно уточнение.') : 'Ответ готов.');
        } catch (error) {
            setStatus('Ошибка соединения с ассистентом.');
        }
    }

    if (submitBtn) {
        submitBtn.addEventListener('click', async () => {
            const text = textInput?.value?.trim();
            if (!text) {
                setStatus('Сначала введи запрос.');
                return;
            }
            await sendQuickRequest({ text, user_id: String(userId), session_id: sessionId });
        });
    }

    async function blobToBase64(blob) {
        const arrayBuffer = await blob.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        let binary = '';
        bytes.forEach((b) => { binary += String.fromCharCode(b); });
        return btoa(binary);
    }

    async function toggleVoiceRecording() {
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
            setStatus('Голосовой ввод не поддерживается в этом браузере.');
            return;
        }
        if (!isRecording) {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaChunks = [];
            mediaRecorder = new MediaRecorder(stream, { mimeType: MediaRecorder.isTypeSupported(audioMime) ? audioMime : '' });
            mediaRecorder.ondataavailable = (event) => {
                if (event.data?.size) mediaChunks.push(event.data);
            };
            mediaRecorder.onstop = async () => {
                voiceState.textContent = 'Распознаю аудио...';
                const actualMime = mediaRecorder.mimeType || audioMime;
                const blob = new Blob(mediaChunks, { type: actualMime });
                const audioBase64 = await blobToBase64(blob);
                await sendQuickRequest({ audio: audioBase64, user_id: String(userId), session_id: sessionId, metadata: { mime_type: actualMime } });
                voiceState.textContent = 'Голосовой ввод: готов';
                stream.getTracks().forEach(track => track.stop());
            };
            mediaRecorder.start();
            isRecording = true;
            if (voiceBtn) voiceBtn.textContent = '⏹ Остановить запись';
            if (voiceState) voiceState.textContent = 'Идёт запись...';
            return;
        }
        mediaRecorder?.stop();
        isRecording = false;
        if (voiceBtn) voiceBtn.textContent = '🎙 Запись голоса';
    }

    if (voiceBtn) {
        voiceBtn.addEventListener('click', async () => {
            try { await toggleVoiceRecording(); } catch (e) { setStatus('Не удалось получить доступ к микрофону.'); }
        });
    }
});
