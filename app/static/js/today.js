const modal = document.getElementById('modal');

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
