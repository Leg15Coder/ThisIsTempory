(function(){
    'use strict';
    var overlayId = 'shopModalOverlay_v1';
    var tplId = 'createItemTemplate';
    var containerId = 'createItemModalContainer';
    var ignoreBackdropClicksUntil = 0;
    var modalOpen = false;

    function log() {}
    function trace() {}

    function createOverlayFromTemplate() {
        var existing = document.getElementById(overlayId);
        if (existing) existing.remove();
        var tpl = document.getElementById(tplId);
        var overlay = document.createElement('div');
        overlay.id = overlayId;
        overlay.style.position = 'fixed';
        overlay.style.inset = '0';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.background = 'rgba(0,0,0,0.6)';
        overlay.style.zIndex = '1200000';
        overlay.style.backdropFilter = 'blur(3px)';

        var inner = null;
        if (tpl && tpl.content) {
            var innerTpl = tpl.content.querySelector('.modal-inner');
            if (innerTpl) inner = innerTpl.cloneNode(true);
        }
        if (!inner) {
            inner = document.createElement('div');
            inner.className = 'shop-dialog-inner';
            inner.innerHTML = '<div style="padding:1rem;color:#fff;">Форма загрузки недоступна</div>';
        }

        inner.style.background = '#15151b';
        inner.style.padding = '1.25rem';
        inner.style.borderRadius = '12px';
        inner.style.border = '1px solid rgba(255,255,255,0.06)';
        inner.style.color = '#fff';
        inner.style.maxHeight = 'calc(90vh - 40px)';
        inner.style.overflow = 'auto';
        inner.style.width = '94%';
        inner.style.maxWidth = '720px';
        inner.style.boxShadow = '0 20px 60px rgba(0,0,0,0.6)';
        inner.style.position = 'relative';

        overlay.appendChild(inner);

        overlay.addEventListener('click', function(e){
            if (Date.now() < ignoreBackdropClicksUntil) return;
            if (e.target === overlay) {
                closeModal();
            }
        });

        var closeBtn = inner.querySelector('#modalClose');
        if (closeBtn) closeBtn.addEventListener('click', closeModal);
        var cancelBtn = inner.querySelector('#modalCancel');
        if (cancelBtn) cancelBtn.addEventListener('click', closeModal);

        document.body.appendChild(overlay);
        return overlay;
    }

    function openModal() {
        if (modalOpen) { return; }
        try {
            modalOpen = true;
            ignoreBackdropClicksUntil = Date.now() + 600;
            var overlay = createOverlayFromTemplate();
            overlay.style.display = 'flex';
            var el = overlay.querySelector('input,textarea,select,button'); if (el) el.focus();
        } catch(err) { modalOpen = false; console && console.warn && console.warn('shop-init open failed', err); }
    }

    function closeModal() {
        var overlay = document.getElementById(overlayId);
        if (!overlay) return;
        try {
            modalOpen = false;
            overlay.remove();
            var opener = document.getElementById('openCreateItem'); if (opener) opener.focus();
        } catch(e) { console && console.warn && console.warn('shop-init close failed', e); }
    }

    function delegatedClickHandler(e) {
        try {
            var target = e.target && e.target.closest ? e.target.closest('#openCreateItem') : null;
            if (target) {
                e.preventDefault();
                e.stopPropagation();
                openModal();
            }
        } catch(err) { console && console.warn && console.warn('shop-init delegated handler error', err); }
    }

    function attachListeners() {
        document.addEventListener('click', delegatedClickHandler, true);
        document.addEventListener('keydown', function(ev){ if (ev.key === 'Escape') closeModal(); });

        try { window.openShopModal = openModal; window.closeShopModal = closeModal; window.__shopModalOpenFlag = function(){ return !!modalOpen; }; } catch(e){}
    }

    function init() {
        try {
            attachListeners();
            var btn = document.getElementById('openCreateItem');
            if (btn) {
                btn.style.zIndex = '1100000';
            }
        } catch(e) { console && console.warn && console.warn('shop-init init failed', e); }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
