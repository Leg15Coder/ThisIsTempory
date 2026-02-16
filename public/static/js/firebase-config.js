import { initializeApp } from "https://www.gstatic.com/firebasejs/12.9.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "https://www.gstatic.com/firebasejs/12.9.0/firebase-auth.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/12.9.0/firebase-analytics.js";

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
let analytics;
try {
  analytics = getAnalytics(app);
} catch (e) {
  analytics = null;
}

const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

export { app, analytics, auth, googleProvider, signInWithPopup };
