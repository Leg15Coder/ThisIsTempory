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
      // show spinner while loading
      content.innerHTML = '<div class="assistant-loading">Загрузка ассистента…</div>';
      content.appendChild(iframeEl);
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
    // open panel and attempt to send start-record to iframe once loaded
    openPanel();
    // If iframe already loaded, post immediately
    if (iframeLoaded) {
      postToIframe({ type: 'start-record' });
      btn.classList.add('recording');
    } else {
      // wait for load then post
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

})();
