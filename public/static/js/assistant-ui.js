(function(){
  // Assistant UI logic inside iframe/window
  const statusBox = document.getElementById('assistantQuickStatus');
  const streamBox = document.getElementById('assistantQuickStream');
  const textInput = document.getElementById('assistantQuickText');
  const submitBtn = document.getElementById('assistantQuickSubmit');
  const closeBtn = document.getElementById('assistantClose');

  let mediaRecorder = null;
  let mediaChunks = [];
  let isRecording = false;
  const userId = document.getElementById('assistantRoot')?.dataset.userId || '';
  const sessionId = document.getElementById('assistantRoot')?.dataset.sessionId || 'assistant-main';

  function setStatus(t){ if(statusBox) statusBox.textContent = t; }
  function showResponseText(t){ if(streamBox) streamBox.textContent = t; }

  async function sendQuick(payload){
    setStatus('Отправка запроса...');
    try{
      const resp = await fetch('/api/assistant/quick', {
        method: 'POST', headers: {'Content-Type':'application/json'}, credentials: 'same-origin',
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if(!resp.ok){ setStatus(data.detail || 'Ошибка ассистента'); return; }
      showResponseText(data.response_text || '');
      setStatus('Готово');
      // Debug: show raw LLM response if present
      try{
        const metaDiv = document.getElementById('assistantQuickMeta');
        if(metaDiv && data.raw_llm_response){
          metaDiv.classList.remove('assistant-hidden');
          metaDiv.textContent = 'raw_llm_response: ' + data.raw_llm_response.slice(0, 2000);
        }
      }catch(e){}
      if(data.action && data.action.confirmation_token){
        try{ localStorage.setItem(`assistantDraft:${data.action.confirmation_token}`, JSON.stringify({ draft: data.action.result, sessionId, userId })); }catch(e){}
      }
    }catch(e){ setStatus('Ошибка сети при обращении к ассистенту'); }
  }

  // Close control inside iframe: send message to parent to close panel
  if(closeBtn){ closeBtn.addEventListener('click', ()=>{
    try{ window.parent.postMessage({ type: 'close-panel' }, window.location.origin); } catch(e){}
  }); }

  // Listen for messages from parent
  window.addEventListener('message', (ev)=>{
    if(ev.origin !== window.location.origin) return;
    const msg = ev.data || {};
    if(msg.type === 'start-record'){ startRecording(); }
    if(msg.type === 'stop-record'){ stopRecording(); }
    if(msg.type === 'close-panel'){ /* optional: close UI inside iframe */ }
  });

  // Audio handling: same as before
  async function startRecording(){
    if (!navigator.mediaDevices?.getUserMedia) { setStatus('Микрофон не доступен'); return; }
    try{
      const stream = await navigator.mediaDevices.getUserMedia({ audio:true });
      mediaChunks = [];
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorder.ondataavailable = (e)=>{ if(e.data && e.data.size) mediaChunks.push(e.data); };
      mediaRecorder.onstop = async ()=>{
        setStatus('Обработка аудио...');
        const blob = new Blob(mediaChunks, { type: 'audio/webm' });
        const arrayBuffer = await blob.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        let binary = '';
        bytes.forEach(b=>binary += String.fromCharCode(b));
        const base64 = btoa(binary);
        try{
          const resp = await fetch('/api/assistant/audio-to-text', { method:'POST', headers:{'Content-Type':'application/json'}, credentials:'same-origin', body: JSON.stringify({ audio: base64, mime_type: 'audio/webm', user_id: userId }) });
          const j = await resp.json();
          if(!resp.ok){ setStatus(j.detail || 'Ошибка распознавания'); return; }
          const text = j.text || '';
          setStatus('Распознанный текст: ' + text);
          await sendQuick({ text, user_id: userId, session_id: sessionId });
        }catch(e){ setStatus('Ошибка при отправке аудио на сервер'); }
        stream.getTracks().forEach(t=>t.stop());
      };
      mediaRecorder.start();
      isRecording = true;
      setStatus('Запись... Отпустите кнопку, чтобы отправить');
    }catch(e){ setStatus('Не удалось получить доступ к микрофону'); }
  }
  function stopRecording(){ if(mediaRecorder && isRecording){ mediaRecorder.stop(); isRecording=false; } }

  // UI submit
  if(submitBtn){ submitBtn.addEventListener('click', ()=>{
    const text = (textInput?.value || '').trim();
    if(!text) { setStatus('Введите сообщение'); return; }
    sendQuick({ text, user_id: userId, session_id: sessionId });
  }); }

})();
