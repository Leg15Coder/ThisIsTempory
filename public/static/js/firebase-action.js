import { initializeApp } from "https://www.gstatic.com/firebasejs/12.9.0/firebase-app.js";
import { getAuth, applyActionCode, signInWithEmailLink, isSignInWithEmailLink } from "https://www.gstatic.com/firebasejs/12.9.0/firebase-auth.js";

const firebaseConfig = {
  apiKey: "AIzaSyDRdSOkpKGKlmUCYijq77gV9dkPTGnsIz8",
  authDomain: "the-perfect-world-eeddf.firebaseapp.com",
  projectId: "the-perfect-world-eeddf",
  storageBucket: "the-perfect-world-eeddf.firebasestorage.app",
  messagingSenderId: "134803680458",
  appId: "1:134803680458:web:d43a9e2e76b9322a301833",
  measurementId: "G-81SEFFHL7Z"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

function setMessage(title, body) {
  document.getElementById('actionTitle').textContent = title;
  document.getElementById('actionBody').textContent = body;
}

const params = new URLSearchParams(window.location.search);
const mode = params.get('mode');
const oobCode = params.get('oobCode');

if (!mode || !oobCode) {
  setMessage('Ошибка', 'Некорректная ссылка.');
} else if (mode === 'verifyEmail') {
  applyActionCode(auth, oobCode).then(() => {
    setMessage('Почта подтверждена', 'Ваш email успешно подтверждён.');
  }).catch((err) => {
    setMessage('Ошибка подтверждения', err.message || 'Не удалось подтвердить email.');
  });
} else if (mode === 'resetPassword') {
  // Покажем форму для ввода нового пароля (упрощённо)
  setMessage('Сброс пароля', 'Перейдите в приложение и выполните сброс пароля');
} else {
  setMessage('Неизвестный режим', 'Действие не поддерживается.');
}
