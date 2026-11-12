/**
 * Modular Firebase Authentication SDK v11 Web Bridge for e-Panchayat Automation.
 * Replaces legacy custom Google OAuth / GSI client scripts cleanly.
 */
import { getApps, initializeApp } from 'https://www.gstatic.com/firebasejs/11.6.1/firebase-app.js';
import {
  GoogleAuthProvider,
  connectAuthEmulator,
  getAuth,
  getRedirectResult,
  signInWithPopup,
  signInWithRedirect,
  signOut,
} from 'https://www.gstatic.com/firebasejs/11.6.1/firebase-auth.js';

let firebaseApp = null;
let firebaseAuth = null;
let googleProvider = null;
let emulatorConnected = false;

function buildProvider() {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: 'select_account' });
  return provider;
}

function normalizeFirebaseConfig(cfg) {
  if (!cfg || !cfg.apiKey || !cfg.projectId) {
    return null;
  }
  return {
    apiKey: String(cfg.apiKey),
    authDomain: String(cfg.authDomain || `${cfg.projectId}.firebaseapp.com`),
    projectId: String(cfg.projectId),
    storageBucket: String(cfg.storageBucket || `${cfg.projectId}.firebasestorage.app`),
    messagingSenderId: String(cfg.messagingSenderId || ''),
    appId: String(cfg.appId || ''),
  };
}

function init(config, authEmulatorHost) {
  const normalized = normalizeFirebaseConfig(config);
  if (!normalized) return null;

  if (!firebaseApp) {
    const existing = getApps();
    firebaseApp = existing.length ? existing[0] : initializeApp(normalized);
  }
  if (!firebaseAuth) {
    firebaseAuth = getAuth(firebaseApp);
  }
  if (authEmulatorHost && !emulatorConnected) {
    const cleanHost = String(authEmulatorHost).replace(/^https?:\/\//i, '');
    try {
      connectAuthEmulator(firebaseAuth, `http://${cleanHost}`, { disableWarnings: true });
      emulatorConnected = true;
    } catch (e) {}
  }
  if (!googleProvider) {
    googleProvider = buildProvider();
  }
  return firebaseAuth;
}

async function ensureReady() {
  if (firebaseAuth && googleProvider) return firebaseAuth;
  const res = await fetch('/api/auth/firebase-config');
  if (!res.ok) {
    throw new Error('Unable to load Firebase client configuration.');
  }
  const data = await res.json();
  const auth = init(data.firebase_config, data.auth_emulator_host);
  if (!auth) {
    throw new Error('Firebase Web SDK configuration is incomplete.');
  }
  return auth;
}

async function consumeRedirectSignIn() {
  if (!firebaseAuth) return null;
  try {
    const result = await getRedirectResult(firebaseAuth);
    if (result && result.user) {
      const idToken = await result.user.getIdToken(true);
      return { idToken, user: result.user };
    }
  } catch (err) {
    if (err && err.code && err.code !== 'auth/no-auth-event') {
      throw err;
    }
  }
  return null;
}

async function signInWithGoogle() {
  // Run signInWithPopup immediately when initialized so browser keeps user activation gesture
  const auth = firebaseAuth || (await ensureReady());
  const provider = googleProvider || buildProvider();
  try {
    const credential = await signInWithPopup(auth, provider);
    const idToken = await credential.user.getIdToken(true);
    return { idToken, user: credential.user };
  } catch (err) {
    const code = err && err.code ? String(err.code) : '';
    if (code === 'auth/popup-blocked') {
      await signInWithRedirect(auth, provider);
      return { redirected: true };
    }
    throw err;
  }
}

async function firebaseSignOut() {
  if (!firebaseAuth) return;
  try {
    await signOut(firebaseAuth);
  } catch (e) {}
}

window.FirebasePortalAuth = {
  init,
  ensureReady,
  consumeRedirectSignIn,
  signInWithGoogle,
  signOut: firebaseSignOut,
};
