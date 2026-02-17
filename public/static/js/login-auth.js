// login-auth.js
// Externalized module to handle email login and Google Sign-In
// Reads config from #appConfig data attributes

import { auth, googleProvider, signInWithPopup } from '/static/js/firebase-config.js';

function getConfig() {
  const el = document.getElementById('appConfig');
  if (!el) return { baseUrl: '/quest-app', firebaseEnabled: false };
  return {
    baseUrl: el.dataset.baseUrl || '/quest-app',
    firebaseEnabled: el.dataset.firebaseEnabled === '1'
  };
}

function getNextRedirect() {
  const params = new URLSearchParams(window.location.search);
  const next = params.get('next');
  const cfg = getConfig();
  return next || cfg.baseUrl;
}

function showError(message) {
  const errorDiv = document.getElementById('errorMessage');
  if (!errorDiv) return;
  errorDiv.textContent = message;
  errorDiv.style.display = 'block';
}

async function handleEmailLogin(e) {
  e.preventDefault();
  const formData = {
    email: document.getElementById('email').value,
    password: document.getElementById('password').value
  };
  try {
    const response = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formData)
    });
    if (response.ok) {
      window.location.href = getNextRedirect();
    } else {
      const error = await response.json();
      showError(error.detail || 'Ошибка входа');
    }
  } catch (err) {
    showError('Ошибка соединения с сервером');
  }
}

async function handleGoogleSignIn() {
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const idToken = await result.user.getIdToken();
    const response = await fetch('/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken })
    });
    if (response.ok) {
      window.location.href = getNextRedirect();
    } else {
      const err = await response.json();
      showError(err.detail || 'Ошибка Google аутентификации');
    }
  } catch (err) {
    console.error('Google sign in error:', err);
    if (err && err.code === 'auth/unauthorized-domain') {
      const origin = window.location.origin || (window.location.protocol + '//' + window.location.host);
      showError('Ошибка Google Sign-In: домен приложения не добавлен в разрешённые домены Firebase. Добавьте ' + origin + ' в список Authorized domains в Firebase Console.');
    } else {
      showError('Ошибка входа через Google');
    }
  }
}

function init() {
  const loginForm = document.getElementById('loginForm');
  if (loginForm) loginForm.addEventListener('submit', handleEmailLogin);

  const cfg = getConfig();
  if (cfg.firebaseEnabled) {
    const googleBtn = document.getElementById('googleLoginBtn');
    if (googleBtn) googleBtn.addEventListener('click', handleGoogleSignIn);
  }
}

// Initialize on DOMContentLoaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

