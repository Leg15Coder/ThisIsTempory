const menuBtn = document.getElementById('menuBtn');
const sidebar = document.getElementById('sidebar');
const main = document.getElementById('main');

// Toggle sidebar
menuBtn.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    main.classList.toggle('sidebar-open');
});
