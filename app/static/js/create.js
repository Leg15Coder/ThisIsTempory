const questTitle = document.getElementById('questTitle');
const questAuthor = document.getElementById('questAuthor');
const titleCounter = document.getElementById('titleCounter');
const authorCounter = document.getElementById('authorCounter');
const createModal = document.getElementById('createModal');
const createModalClose = document.getElementById('createModalClose');
const questForm = document.getElementById('questForm');

// Character counters
questTitle.addEventListener('input', function() {
    titleCounter.textContent = this.value.length;
});

questAuthor.addEventListener('input', function() {
    authorCounter.textContent = this.value.length;
});
