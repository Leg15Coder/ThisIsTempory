document.addEventListener('click', (e) => {
  const btn = e.target.closest('.btn');
  if (!btn) return;
  btn.animate([
    { transform: 'translateY(0) scale(1)' },
    { transform: 'translateY(1px) scale(0.99)' },
    { transform: 'translateY(0) scale(1)' }
  ], { duration: 160, easing: 'ease-out' });
});

(function spawnParticles(){
  const wrap = document.getElementById('hexParticles');
  if (!wrap) return;
  const count = Math.min(36, Math.max(18, Math.floor(window.innerWidth / 60)));
  for (let i = 0; i < count; i++) {
    const p = document.createElement('span');
    p.className = 'spark';
    p.style.left = Math.random() * 100 + 'vw';
    p.style.top = (Math.random() * 100 + 20) + 'vh';
    p.style.animationDelay = (Math.random() * 14) + 's';
    p.style.opacity = (0.4 + Math.random() * 0.6).toFixed(2);
    p.style.transform = `translateY(${Math.random()*40}vh)`;
    wrap.appendChild(p);
  }
})();
