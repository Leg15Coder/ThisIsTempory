// DOM elements
const cardsContainer = document.getElementById('cardsContainer');
const modal = document.getElementById('modal');
const modalClose = document.getElementById('modalClose');
const modalTitle = document.getElementById('modalTitle');
const modalAuthor = document.getElementById('modalAuthor');
const modalDeadline = document.getElementById('modalDeadline');
const modalText = document.getElementById('modalText');
const modalType = document.getElementById('modalType');

// Open modal with card details
function openModal(id) {
    fetch(`/quest/${id}`)
        .then(res => res.text())
        .then(html => {
            modal.innerHTML = html;
        });

    modal.style.display = 'flex';
}

// Close modal when clicking outside
modal.addEventListener('click', (e) => {
    if (e.target === modal) {
        modal.style.display = 'none';
    }
});
