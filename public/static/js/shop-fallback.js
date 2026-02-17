(function(){
    'use strict';
    function buildOverlay(){
        if (document.getElementById('shopModalOverlay_v1')) return document.getElementById('shopModalOverlay_v1');
        var tpl = document.getElementById('createItemTemplate');
        var overlay = document.createElement('div');
        overlay.id = 'shopModalOverlay_v1';
        overlay.style.position = 'fixed'; overlay.style.inset = '0'; overlay.style.display = 'flex';
        overlay.style.alignItems = 'center'; overlay.style.justifyContent = 'center';
        overlay.style.background = 'rgba(0,0,0,0.6)'; overlay.style.zIndex = '1300000';
        var inner = null;
        if (tpl && tpl.content) {
            var innerTpl = tpl.content.querySelector('.modal-inner');
            if (innerTpl) inner = innerTpl.cloneNode(true);
        }
        if (!inner) { inner = document.createElement('div'); inner.className = 'shop-dialog-inner'; inner.innerHTML = '<div style="padding:1rem;color:#fff;">Форма загрузки недоступна</div>'; }
        inner.style.background = '#15151b'; inner.style.padding = '1.25rem'; inner.style.borderRadius = '12px';
        inner.style.border = '1px solid rgba(255,255,255,0.06)'; inner.style.color = '#fff'; inner.style.maxHeight = 'calc(90vh - 40px)';
        inner.style.overflow = 'auto'; inner.style.width = '94%'; inner.style.maxWidth = '720px'; inner.style.boxShadow = '0 20px 60px rgba(0,0,0,0.6)'; inner.style.position = 'relative';
        overlay.appendChild(inner);
        overlay.addEventListener('click', function(e){ if (e.target === overlay) overlay.remove(); });
        var closeBtn = inner.querySelector('#modalClose'); if (closeBtn) closeBtn.addEventListener('click', function(){ overlay.remove(); });
        document.body.appendChild(overlay);
        return overlay;
    }

    function init(){
        try{
            var attach = function(){
                var btn = document.getElementById('openCreateItem');
                if (!btn) return;
                btn.addEventListener('click', function(e){
                    try{ e.preventDefault(); buildOverlay(); }catch(err){ /* ignore */ }
                });
            };
            if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attach);
            else attach();
        }catch(e){ /* ignore */ }
    }
    init();
})();
