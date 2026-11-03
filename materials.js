'use strict';
const current = location.pathname.split('/').pop() || 'index.html';
document.querySelectorAll('.site-nav a').forEach(link => {
  if (link.getAttribute('href') === current || (current === 'index.htm' && link.getAttribute('href') === 'index.html')) link.setAttribute('aria-current', 'page');
});
document.querySelectorAll('pre').forEach((pre, index) => {
  if (!navigator.clipboard) return;
  const button = document.createElement('button');
  button.className = 'copy-code'; button.type = 'button'; button.textContent = 'Копировать код';
  button.setAttribute('aria-label', `Копировать код, фрагмент ${index + 1}`);
  button.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(pre.textContent); button.textContent = 'Скопировано'; }
    catch { button.textContent = 'Выделить и скопировать вручную'; }
  });
  pre.after(button);
});
