(function(){
  // Quick assistant UI with lazy iframe and postMessage commands for recording
  const btn = document.getElementById('quickAssistantBtn');
  const panel = document.getElementById('quickAssistantPanel');
  const content = document.getElementById('quickAssistantContent');
  let holdTimer = null;
  let isMobile = /Mobi|Android/i.test(navigator.userAgent);
  let iframeLoaded = false;
  let iframeEl = null;
  let isHolding = false;

  function buildIframeSrc() {
    const userId = document.body.dataset.userId || '';
    const sessionId = document.body.dataset.assistantSessionId || 'assistant-main';
    const params = new URLSearchParams({ session_id: sessionId, user_id: userId });
    return `/assistant/ui?${params.toString()}`;
  }

  function openPanel() {
    panel.classList.remove('assistant-hidden');
    panel.setAttribute('aria-hidden', 'false');
    if (!iframeLoaded) {
      iframeEl = document.createElement('iframe');
      iframeEl.style.width = '100%';
      iframeEl.style.height = '420px';
      iframeEl.style.border = '0';
      iframeEl.src = buildIframeSrc();
      iframeEl.onload = function(){ iframeLoaded = true; btn.classList.remove('loading'); };
      // build header + content
      content.innerHTML = '';
      const header = document.createElement('div'); header.className = 'panel-header';
      const title = document.createElement('div'); title.className = 'panel-title'; title.textContent = 'Быстрый AI-ассистент';
      const controls = document.createElement('div'); controls.className = 'panel-controls';
      const closeBtn = document.createElement('button'); closeBtn.title = 'Закрыть'; closeBtn.innerHTML = '✕';
      const popOutBtn = document.createElement('button'); popOutBtn.title = 'Открыть в новой вкладке'; popOutBtn.innerHTML = '⤢';
      controls.appendChild(popOutBtn); controls.appendChild(closeBtn);
      header.appendChild(title); header.appendChild(controls);
      content.appendChild(header);

      // add iframe container
      const frameWrap = document.createElement('div'); frameWrap.style.flex = '1 1 auto'; frameWrap.style.minHeight = '180px'; frameWrap.style.overflow = 'hidden';
      frameWrap.appendChild(iframeEl);
      content.appendChild(frameWrap);

      // resize handle
      const resizer = document.createElement('div'); resizer.style.height = '10px'; resizer.style.cursor = 'ns-resize'; resizer.title = 'Изменить высоту'; content.appendChild(resizer);

      // events
      closeBtn.addEventListener('click', closePanel);
      popOutBtn.addEventListener('click', () => { window.open(buildIframeSrc(), '_blank'); });

      let startY = 0; let startH = 420; let dragging = false;
      resizer.addEventListener('mousedown', (e)=>{ dragging = true; startY = e.clientY; startH = iframeEl.clientHeight; e.preventDefault(); });
      document.addEventListener('mousemove', (e)=>{ if(!dragging) return; const dy = startY - e.clientY; let nh = Math.max(200, startH + dy); iframeEl.style.height = nh + 'px'; });
      document.addEventListener('mouseup', ()=>{ dragging = false; });

      // show spinner while loading
      const spinner = document.createElement('div'); spinner.className = 'assistant-loading'; spinner.textContent = 'Загрузка ассистента…';
      frameWrap.appendChild(spinner);

      frameWrap.appendChild(iframeEl);
      btn.classList.add('loading');
    }
  }

  function closePanel() {
    panel.classList.add('assistant-hidden');
    panel.setAttribute('aria-hidden', 'true');
  }

  function postToIframe(message) {
    if (!iframeLoaded || !iframeEl || !iframeEl.contentWindow) return false;
    try {
      iframeEl.contentWindow.postMessage(message, window.location.origin);
      return true;
    } catch (e) {
      return false;
    }
  }

  function startHoldRecordingSequence() {
    isHolding = true;
    openPanel();
    if (iframeLoaded) {
      postToIframe({ type: 'start-record' });
      btn.classList.add('recording');
    } else {
      const onload = () => {
        setTimeout(() => { postToIframe({ type: 'start-record' }); btn.classList.add('recording'); }, 120);
        iframeEl.removeEventListener('load', onload);
      };
      if (iframeEl) iframeEl.addEventListener('load', onload);
    }
  }

  function stopHoldRecordingSequence() {
    isHolding = false;
    postToIframe({ type: 'stop-record' });
    btn.classList.remove('recording');
  }

  // Click toggles panel
  btn.addEventListener('click', (e) => {
    if (isHolding) return; // ignore click after hold
    if (panel.classList.contains('assistant-hidden')) openPanel(); else closePanel();
  });

  // Hold: start recording flow
  btn.addEventListener('mousedown', (e) => {
    if (!isMobile) {
      holdTimer = setTimeout(() => { startHoldRecordingSequence(); }, 300);
    }
  });
  btn.addEventListener('mouseup', (e) => {
    if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
    if (isHolding) stopHoldRecordingSequence();
  });
  btn.addEventListener('mouseleave', (e) => {
    if (holdTimer) { clearTimeout(holdTimer); holdTimer = null; }
    if (isHolding) stopHoldRecordingSequence();
  });

  btn.addEventListener('touchstart', (e) => {
    holdTimer = setTimeout(() => { startHoldRecordingSequence(); }, 300);
  }, {passive:true});
  btn.addEventListener('touchend', (e) => { if (holdTimer) { clearTimeout(holdTimer); holdTimer=null; } if (isHolding) stopHoldRecordingSequence(); });

  // Hotkey Ctrl/Cmd+K toggles panel
  window.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      if (panel.classList.contains('assistant-hidden')) openPanel(); else closePanel();
    }
  });

  // Close when clicking outside
  document.addEventListener('click', (e) => {
    if (!panel.classList.contains('assistant-hidden')) {
      if (!panel.contains(e.target) && e.target !== btn) closePanel();
    }
  });

  // Listen for messages from iframe (e.g., close-panel)
  window.addEventListener('message', (ev) => {
    if (ev.origin !== window.location.origin) return;
    const msg = ev.data || {};
    if (msg.type === 'close-panel') closePanel();
    if (msg.type === 'start-record') { startHoldRecordingSequence(); }
    if (msg.type === 'stop-record') { stopHoldRecordingSequence(); }
  });

})();
