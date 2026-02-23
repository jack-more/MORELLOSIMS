/* ═══════════════════════════════════════════════════════════ */
/* MORELLO AUTH — Shared authentication + tier access module   */
/* Included on: morellosims.com, cosmos, mlbsim, nbasim       */
/* ═══════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  // ── Firebase Config ──
  const FIREBASE_CONFIG = {
    apiKey: 'AIzaSyDlM08MICU2fR0H-sFWUNhpX98arnASXVE',
    authDomain: 'morello-sims.firebaseapp.com',
    projectId: 'morello-sims',
    storageBucket: 'morello-sims.firebasestorage.app',
    messagingSenderId: '1053398677633',
    appId: '1:1053398677633:web:030fc2bf41c5c5f31d7580'
  };

  // ── Stripe Config ──
  // ── Stripe Config ──
  const STRIPE_CONFIG = {
    publishableKey: 'pk_test_YOUR_STRIPE_KEY', // TODO: Replace with your Stripe publishable key
    prices: {
      pickmaker_nba: 'price_1T3rqNA9KGX7mrlmCQi4QcnU',
      pickmaker_mlb: 'price_1T3rqqA9KGX7mrlmHncjyPlp',
      pickmaker_dual: 'price_1T3rvjA9KGX7mrlmxJI5V00r',
      all_access: 'price_1T3s0qA9KGX7mrlmA8KljtHG'
    },
    // Cloud Function endpoint for creating checkout sessions
    checkoutUrl: 'https://us-central1-morello-sims.cloudfunctions.net/createCheckoutSession'
  };

  const ADMIN_EMAIL = 'jaidanmorello@gmail.com';

  // ── Pre-assigned email → tier whitelist ──
  // These users get their tier immediately on sign-up/sign-in,
  // even before Firestore or Cloud Functions are fully deployed.
  const EMAIL_WHITELIST = {
    'jaidanmorello@gmail.com': 'admin',
    'webb.little19@gmail.com': 'fnf',
    'samlittle2@gmail.com': 'fnf'
  };

  const TIER_LABELS = {
    free: 'FREE',
    fnf: 'FnF',
    pickmaker_nba: 'NBA PICKMAKER',
    pickmaker_mlb: 'MLB PICKMAKER',
    pickmaker_dual: 'DUAL PICKMAKER',
    all_access: 'ALL-ACCESS',
    admin: 'ADMIN'
  };

  const TIER_COLORS = {
    free: '#888',
    fnf: '#00FF55',
    pickmaker_nba: '#FFEA00',
    pickmaker_mlb: '#FFEA00',
    pickmaker_dual: '#FFEA00',
    all_access: '#FF6B00',
    admin: '#FF0040'
  };

  // ── State ──
  let currentUser = null;
  let currentTier = 'free';
  let adminOverrideTier = null; // For admin view-as feature
  let firebaseReady = false;

  // ── Detect which page we're on ──
  const PAGE = detectPage();

  function detectPage() {
    const path = window.location.pathname;
    const host = window.location.hostname;
    // All sites now under morellosims.com — detect by path
    if (path.startsWith('/atlas')) return 'atlas';
    if (path.startsWith('/mlbsim')) return 'mlbsim';
    if (path.startsWith('/nbasim')) return 'nbasim';
    // Legacy detection for old URLs / local dev
    if (path.includes('cosmos.html') || path.includes('cosmos')) return 'atlas';
    if (path.includes('mlbsim.html')) return 'mlbsim';
    if (host.includes('nbasim')) return 'nbasim';
    return 'home';
  }

  // ── Get effective tier (respects admin override) ──
  function getEffectiveTier() {
    if (adminOverrideTier && currentTier === 'admin') return adminOverrideTier;
    return currentTier;
  }

  function hasAccess(requiredTier) {
    const tier = getEffectiveTier();
    const hierarchy = ['free', 'fnf', 'pickmaker_nba', 'pickmaker_mlb', 'pickmaker_dual', 'all_access', 'admin'];
    // Special: pickmaker_dual grants both nba and mlb
    if (requiredTier === 'pickmaker_nba' && (tier === 'pickmaker_dual' || tier === 'pickmaker_nba')) return true;
    if (requiredTier === 'pickmaker_mlb' && (tier === 'pickmaker_dual' || tier === 'pickmaker_mlb')) return true;
    if (tier === 'admin' || tier === 'all_access') return true;
    if (tier === 'fnf' && requiredTier !== 'all_access' && requiredTier !== 'admin') return true;
    return hierarchy.indexOf(tier) >= hierarchy.indexOf(requiredTier);
  }

  // ══════════════════════════════════════════════════
  // FIREBASE INITIALIZATION
  // ══════════════════════════════════════════════════

  function initFirebase() {
    if (typeof firebase === 'undefined') {
      console.warn('[morello-auth] Firebase SDK not loaded');
      // Still render UI in demo mode
      onAuthReady(null);
      return;
    }

    if (!firebase.apps.length) {
      firebase.initializeApp(FIREBASE_CONFIG);
    }

    firebase.auth().onAuthStateChanged(async (user) => {
      if (user) {
        currentUser = user;
        const email = (user.email || '').toLowerCase();

        // 1) Check hardcoded whitelist first (works without Firestore)
        if (EMAIL_WHITELIST[email]) {
          currentTier = EMAIL_WHITELIST[email];
        } else {
          // 2) Try Firestore for Stripe-managed tiers
          try {
            const doc = await firebase.firestore().collection('users').doc(user.uid).get();
            if (doc.exists && doc.data().tier) {
              currentTier = doc.data().tier;
            } else {
              currentTier = 'free';
            }
            // Ensure user doc exists
            if (!doc.exists) {
              await firebase.firestore().collection('users').doc(user.uid).set({
                email: user.email,
                tier: currentTier,
                createdAt: firebase.firestore.FieldValue.serverTimestamp()
              });
            }
          } catch (e) {
            console.warn('[morello-auth] Firestore error, falling back to whitelist:', e);
            // Firestore failed — whitelist already checked above, default to free
            currentTier = EMAIL_WHITELIST[email] || 'free';
          }
        }
      } else {
        currentUser = null;
        currentTier = 'free';
      }
      firebaseReady = true;
      onAuthReady(user);
    });
  }

  // ══════════════════════════════════════════════════
  // AUTH STATE CHANGE HANDLER
  // ══════════════════════════════════════════════════

  function onAuthReady(user) {
    renderProfileButton();
    applyAccessControl();
    if (currentTier === 'admin') {
      renderAdminToolbar();
    }
  }

  // ══════════════════════════════════════════════════
  // PROFILE BUTTON (Header)
  // ══════════════════════════════════════════════════

  function renderProfileButton() {
    // Remove existing
    const existing = document.getElementById('ma-profile-btn');
    if (existing) existing.remove();

    const btn = document.createElement('div');
    btn.id = 'ma-profile-btn';
    btn.className = 'ma-profile-btn';

    if (currentUser) {
      const initial = (currentUser.email || '?')[0].toUpperCase();
      const tier = getEffectiveTier();
      btn.innerHTML = `
        <div class="ma-profile-avatar tier-${tier}">${initial}</div>
        <span class="ma-tier-badge tier-${tier}">${TIER_LABELS[tier]}</span>
      `;
      btn.onclick = () => openModal('profile');
    } else {
      btn.innerHTML = `<span style="font-weight:600;">SIGN UP</span>`;
      btn.onclick = () => openModal('signup');
    }

    // Insert into header status-indicators area
    const indicators = document.querySelector('.status-indicators');
    if (indicators) {
      indicators.appendChild(btn);
    } else {
      // Fallback: find or create a header container
      const header = document.querySelector('header') || document.querySelector('.top-bar') || document.querySelector('nav');
      if (header) {
        btn.style.position = 'absolute';
        btn.style.right = '16px';
        btn.style.top = '50%';
        btn.style.transform = 'translateY(-50%)';
        header.style.position = header.style.position || 'relative';
        header.appendChild(btn);
      } else {
        // Last resort: fixed position
        btn.style.position = 'fixed';
        btn.style.top = '12px';
        btn.style.right = '16px';
        btn.style.zIndex = '9999';
        document.body.appendChild(btn);
      }
    }
  }

  // ══════════════════════════════════════════════════
  // MODAL SYSTEM
  // ══════════════════════════════════════════════════

  function createModalOverlay() {
    let overlay = document.getElementById('ma-modal-overlay');
    if (overlay) return overlay;

    overlay = document.createElement('div');
    overlay.id = 'ma-modal-overlay';
    overlay.className = 'ma-modal-overlay';
    overlay.onclick = (e) => {
      if (e.target === overlay) closeModal();
    };
    document.body.appendChild(overlay);
    return overlay;
  }

  function openModal(view) {
    const overlay = createModalOverlay();
    const modal = document.createElement('div');
    modal.className = 'ma-modal';
    modal.innerHTML = `<button class="ma-modal-close" onclick="window.morelloAuth.closeModal()">&times;</button>`;

    if (view === 'signup') {
      modal.innerHTML += renderSignupForm();
    } else if (view === 'signin') {
      modal.innerHTML += renderSigninForm();
    } else if (view === 'profile') {
      modal.innerHTML += renderProfileView();
    } else if (view === 'pricing') {
      modal.innerHTML += renderPricingView();
    }

    overlay.innerHTML = '';
    overlay.appendChild(modal);
    requestAnimationFrame(() => overlay.classList.add('active'));

    // Prevent body scroll
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    const overlay = document.getElementById('ma-modal-overlay');
    if (overlay) {
      overlay.classList.remove('active');
      setTimeout(() => {
        overlay.innerHTML = '';
      }, 300);
    }
    document.body.style.overflow = '';
  }

  function renderSignupForm() {
    return `
      <h2>CREATE ACCOUNT</h2>
      <p class="ma-subtitle">JOIN MORELLO SIMS</p>
      <div class="ma-form-group">
        <label>EMAIL</label>
        <input type="email" id="ma-email" placeholder="your@email.com" autocomplete="email">
      </div>
      <div class="ma-form-group">
        <label>PASSWORD</label>
        <input type="password" id="ma-password" placeholder="Min 6 characters" autocomplete="new-password">
      </div>
      <div class="ma-error" id="ma-error"></div>
      <button class="ma-btn-primary" onclick="window.morelloAuth.handleSignup()">CREATE ACCOUNT</button>
      <button class="ma-toggle-link" onclick="window.morelloAuth.openModal('signin')">Already have an account? Sign In</button>
    `;
  }

  function renderSigninForm() {
    return `
      <h2>SIGN IN</h2>
      <p class="ma-subtitle">MORELLO SIMS</p>
      <div class="ma-form-group">
        <label>EMAIL</label>
        <input type="email" id="ma-email" placeholder="your@email.com" autocomplete="email">
      </div>
      <div class="ma-form-group">
        <label>PASSWORD</label>
        <input type="password" id="ma-password" placeholder="Password" autocomplete="current-password">
      </div>
      <div class="ma-error" id="ma-error"></div>
      <button class="ma-btn-primary" onclick="window.morelloAuth.handleSignin()">SIGN IN</button>
      <button class="ma-toggle-link" onclick="window.morelloAuth.openModal('signup')">No account? Create one</button>
    `;
  }

  function renderProfileView() {
    const tier = getEffectiveTier();
    const tierColor = TIER_COLORS[tier] || '#888';
    return `
      <h2>PROFILE</h2>
      <p class="ma-subtitle">MORELLO SIMS ACCOUNT</p>
      <div class="ma-profile-info">
        <div class="ma-profile-email">${currentUser.email}</div>
        <div class="ma-profile-tier-display" style="color:${tierColor}">${TIER_LABELS[tier]}</div>
      </div>
      ${tier === 'free' || tier === 'fnf' ? `
        <button class="ma-btn-primary" onclick="window.morelloAuth.openModal('pricing')" style="background:#FF6B00">UPGRADE ACCOUNT</button>
      ` : ''}
      ${(tier === 'pickmaker_nba' || tier === 'pickmaker_mlb' || tier === 'pickmaker_dual') ? `
        <button class="ma-btn-secondary" onclick="window.morelloAuth.openModal('pricing')">MANAGE PLAN</button>
      ` : ''}
      <button class="ma-btn-secondary ma-btn-danger" onclick="window.morelloAuth.handleSignout()" style="margin-top:12px">SIGN OUT</button>
    `;
  }

  function renderPricingView() {
    return `
      <h2>CHOOSE YOUR ACCESS</h2>
      <p class="ma-subtitle">MORELLO SIMS TIERS</p>
      <div class="ma-pricing-grid">
        <div class="ma-pricing-card">
          <div>
            <div class="ma-pricing-name">MLB ATLAS</div>
            <div class="ma-pricing-desc">3D pitcher galaxy + archetype browser</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount" style="color:#ff4400">FREE</div>
          </div>
        </div>

        <div class="ma-pricing-card">
          <div>
            <div class="ma-pricing-name">NBA PICKMAKER</div>
            <div class="ma-pricing-desc">Daily NBA SIM picks + spread analysis</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount">$11.99<span class="ma-pricing-period">/mo</span></div>
            <button class="ma-pricing-btn" onclick="window.morelloAuth.checkout('pickmaker_nba')">SUBSCRIBE</button>
          </div>
        </div>

        <div class="ma-pricing-card">
          <div>
            <div class="ma-pricing-name">MLB PICKMAKER</div>
            <div class="ma-pricing-desc">Daily MLB SIM matchups + batting props</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount">$11.99<span class="ma-pricing-period">/mo</span></div>
            <button class="ma-pricing-btn" onclick="window.morelloAuth.checkout('pickmaker_mlb')">SUBSCRIBE</button>
          </div>
        </div>

        <div class="ma-pricing-card highlight">
          <div>
            <div class="ma-pricing-name">DUAL PICKMAKER</div>
            <div class="ma-pricing-desc">NBA + MLB SIM access — best value</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount">$19.99<span class="ma-pricing-period">/mo</span></div>
            <button class="ma-pricing-btn" onclick="window.morelloAuth.checkout('pickmaker_dual')">SUBSCRIBE</button>
          </div>
        </div>

        <div class="ma-pricing-card limited">
          <span class="ma-limited-tag">LIMITED AVAILABILITY</span>
          <div>
            <div class="ma-pricing-name">ALL-ACCESS</div>
            <div class="ma-pricing-desc">Full methodology — NBA + MLB systems revealed</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount">$899<span class="ma-pricing-period"> ONE-TIME</span></div>
            <button class="ma-pricing-btn" onclick="window.morelloAuth.checkout('all_access')">PURCHASE</button>
          </div>
        </div>

        <div class="ma-pricing-card" style="opacity:0.5">
          <div>
            <div class="ma-pricing-name">FnF</div>
            <div class="ma-pricing-desc">Friends &amp; Family — dashboard access</div>
          </div>
          <div style="text-align:right">
            <span class="ma-invite-label">INVITE ONLY</span>
          </div>
        </div>
      </div>
      ${currentUser ? '' : '<button class="ma-toggle-link" onclick="window.morelloAuth.openModal(\'signin\')">Already have an account? Sign In</button>'}
    `;
  }

  // ══════════════════════════════════════════════════
  // AUTH HANDLERS
  // ══════════════════════════════════════════════════

  async function handleSignup() {
    const email = document.getElementById('ma-email')?.value?.trim();
    const password = document.getElementById('ma-password')?.value;
    const errorEl = document.getElementById('ma-error');

    if (!email || !password) {
      showError('Email and password required');
      return;
    }
    if (password.length < 6) {
      showError('Password must be at least 6 characters');
      return;
    }

    try {
      if (typeof firebase === 'undefined') {
        showError('Firebase not configured yet. Please set up Firebase project first.');
        return;
      }
      await firebase.auth().createUserWithEmailAndPassword(email, password);
      closeModal();
      // After brief delay, show pricing
      setTimeout(() => openModal('pricing'), 500);
    } catch (err) {
      showError(err.message);
    }
  }

  async function handleSignin() {
    const email = document.getElementById('ma-email')?.value?.trim();
    const password = document.getElementById('ma-password')?.value;

    if (!email || !password) {
      showError('Email and password required');
      return;
    }

    try {
      if (typeof firebase === 'undefined') {
        showError('Firebase not configured yet. Please set up Firebase project first.');
        return;
      }
      await firebase.auth().signInWithEmailAndPassword(email, password);
      closeModal();
    } catch (err) {
      showError(err.message);
    }
  }

  async function handleSignout() {
    if (typeof firebase !== 'undefined') {
      await firebase.auth().signOut();
    }
    adminOverrideTier = null;
    closeModal();
  }

  function showError(msg) {
    const el = document.getElementById('ma-error');
    if (el) {
      el.textContent = msg;
      el.classList.add('visible');
    }
  }

  // ══════════════════════════════════════════════════
  // STRIPE CHECKOUT
  // ══════════════════════════════════════════════════

  async function checkout(product) {
    if (!currentUser) {
      openModal('signup');
      return;
    }

    try {
      const resp = await fetch(STRIPE_CONFIG.checkoutUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          priceId: STRIPE_CONFIG.prices[product],
          uid: currentUser.uid,
          email: currentUser.email,
          successUrl: window.location.origin + '?checkout=success',
          cancelUrl: window.location.href
        })
      });
      const data = await resp.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        alert('Checkout error. Please try again.');
      }
    } catch (err) {
      console.error('[morello-auth] Checkout error:', err);
      alert('Payment system not yet configured. Contact @morello for access.');
    }
  }

  // ══════════════════════════════════════════════════
  // ACCESS CONTROL — Blur + Gate Logic
  // ══════════════════════════════════════════════════

  function applyAccessControl() {
    if (PAGE === 'home') applyHomeAccess();
    else if (PAGE === 'atlas') applyAtlasAccess();
    else if (PAGE === 'mlbsim') applyMlbSimAccess();
    else if (PAGE === 'nbasim') applyNbaSimAccess();
  }

  // ── HOME PAGE (morellosims.com) ──
  function applyHomeAccess() {
    const tier = getEffectiveTier();
    const isMethodologyUnlocked = tier === 'all_access' || tier === 'admin';

    // 1) Blur methodology text spans
    document.querySelectorAll('.ma-methodology-text').forEach(el => {
      if (isMethodologyUnlocked) {
        el.classList.add('ma-unblurred');
        el.classList.remove('ma-blur');
      } else {
        el.classList.add('ma-blur');
        el.classList.remove('ma-unblurred');
      }
    });

    // 2) Lock/unlock methodology blog EXPAND buttons
    const mlbPost = document.getElementById('post-mlb-system');
    const nbaPost = document.getElementById('post-nba-system');

    [mlbPost, nbaPost].forEach(post => {
      if (!post) return;
      if (isMethodologyUnlocked) {
        post.classList.remove('ma-locked');
        // Re-enable native <details> behavior
        post.removeAttribute('data-locked');
      } else {
        post.classList.add('ma-locked');
        post.setAttribute('data-locked', 'true');
      }
    });

    // 3) Add pricing tooltips to dashboard cards
    addPricingTooltips();
  }

  // ── ATLAS (cosmos.html) — Free access, no gate ──
  function applyAtlasAccess() {
    // Atlas is free. No access gate needed.
    // Methodology text is minimal on this page.
  }

  // ── MLB SIM ──
  function applyMlbSimAccess() {
    const tier = getEffectiveTier();
    const hasDashboardAccess = hasAccess('pickmaker_mlb');
    const isMethodologyUnlocked = tier === 'all_access' || tier === 'admin';

    // 1) Full-page access gate for non-authorized users
    applyPageGate(hasDashboardAccess, 'MLB SIM', 'PICKMAKER ACCESS REQUIRED', '$11.99', '/mo', 'DUAL: $19.99/mo for both NBA + MLB', 'pickmaker_mlb');

    // 2) Blur INFO tab cards
    const infoTab = document.getElementById('tab-info');
    if (infoTab) {
      const infoCards = infoTab.querySelectorAll('.info-card');
      infoCards.forEach(card => {
        if (isMethodologyUnlocked) {
          card.classList.remove('ma-blur-heavy');
          card.classList.add('ma-unblurred');
        } else {
          card.classList.add('ma-blur-heavy');
          card.classList.remove('ma-unblurred');
        }
      });

      // Add/remove lock overlay on info tab
      let lockEl = infoTab.querySelector('.ma-info-lock');
      if (!isMethodologyUnlocked) {
        if (!lockEl) {
          const container = document.createElement('div');
          container.className = 'ma-info-lock';
          container.innerHTML = `
            <div class="lock-icon">&#128274;</div>
            <div class="lock-title">ALL-ACCESS REQUIRED</div>
            <div class="lock-subtitle">Full methodology — $899 one-time</div>
            <button class="lock-btn" onclick="window.morelloAuth.openModal('pricing')">VIEW PLANS</button>
          `;
          infoTab.style.position = 'relative';
          infoTab.appendChild(container);
        }
      } else if (lockEl) {
        lockEl.remove();
      }
    }
  }

  // ── NBA SIM ──
  function applyNbaSimAccess() {
    const tier = getEffectiveTier();
    const hasDashboardAccess = hasAccess('pickmaker_nba');
    const isMethodologyUnlocked = tier === 'all_access' || tier === 'admin';

    // 1) Full-page access gate
    applyPageGate(hasDashboardAccess, 'NBA SIM', 'PICKMAKER ACCESS REQUIRED', '$11.99', '/mo', 'DUAL: $19.99/mo for both NBA + MLB', 'pickmaker_nba');

    // 2) Blur INFO sections (look for common info containers)
    const infoSections = document.querySelectorAll('.info-card, .info-section, [data-section="info"]');
    infoSections.forEach(el => {
      if (isMethodologyUnlocked) {
        el.classList.remove('ma-blur-heavy');
        el.classList.add('ma-unblurred');
      } else {
        el.classList.add('ma-blur-heavy');
        el.classList.remove('ma-unblurred');
      }
    });
  }

  // ── Generic page access gate ──
  function applyPageGate(hasAccess, title, subtitle, price, period, dual, product) {
    let gate = document.getElementById('ma-access-gate');

    if (hasAccess) {
      if (gate) gate.classList.remove('active');
      return;
    }

    if (!gate) {
      gate = document.createElement('div');
      gate.id = 'ma-access-gate';
      gate.className = 'ma-access-gate';
      gate.innerHTML = `
        <h2>${title}</h2>
        <p class="gate-desc">${subtitle}</p>
        <div class="gate-price">${price}<span class="gate-period">${period}</span></div>
        <div class="gate-dual">${dual}</div>
        <button class="ma-gate-btn" onclick="window.morelloAuth.openModal(currentUser ? 'pricing' : 'signup')">
          ${currentUser ? 'VIEW PLANS' : 'SIGN UP'}
        </button>
        <div class="ma-gate-signin">
          ${currentUser ? '' : 'Already have an account? <a onclick="window.morelloAuth.openModal(\'signin\')">Sign In</a>'}
        </div>
      `;
      document.body.appendChild(gate);
    }

    gate.classList.add('active');
  }

  // ── Pricing tooltips on dashboard cards (home page) ──
  function addPricingTooltips() {
    const tier = getEffectiveTier();
    const atlasCard = document.querySelector('.card-atlas');
    const nbaCard = document.querySelector('.card-nba');
    const mlbCard = document.querySelector('.card-mlb');

    // Clear any existing tooltips (so admin view-as refresh works)
    document.querySelectorAll('.ma-card-price').forEach(el => el.remove());

    // ATLAS — always free, always clickable. Show "FREE" badge for everyone.
    if (atlasCard) {
      const tip = document.createElement('div');
      tip.className = 'ma-card-price price-free';
      tip.textContent = 'FREE';
      atlasCard.appendChild(tip);
    }

    // NBA — show price only if user does NOT have NBA access
    if (nbaCard) {
      if (!hasAccess('pickmaker_nba')) {
        const tip = document.createElement('div');
        tip.className = 'ma-card-price price-pickmaker';
        tip.innerHTML = '$11.99/mo<br><span style="font-size:8px;opacity:0.6">DUAL: $19.99/mo</span>';
        nbaCard.appendChild(tip);
      }
      // Gate the button — one-time listener that checks access dynamically
      gateCardButton(nbaCard, 'pickmaker_nba');
    }

    // MLB — show price only if user does NOT have MLB access
    if (mlbCard) {
      if (!hasAccess('pickmaker_mlb')) {
        const tip = document.createElement('div');
        tip.className = 'ma-card-price price-pickmaker-mlb';
        tip.innerHTML = '$11.99/mo<br><span style="font-size:8px;opacity:0.6">DUAL: $19.99/mo</span>';
        mlbCard.appendChild(tip);
      }
      // Gate the button — one-time listener that checks access dynamically
      gateCardButton(mlbCard, 'pickmaker_mlb');
    }
  }

  // ── Gate a card's button: if no access at click-time, show pricing instead ──
  function gateCardButton(card, requiredTier) {
    const btn = card.querySelector('.btn-action');
    if (!btn || btn.dataset.maGateListenerSet) return;
    btn.dataset.maGateListenerSet = 'true';
    btn.addEventListener('click', function(e) {
      // Check access at the moment of click (respects admin view-as)
      if (!hasAccess(requiredTier)) {
        e.preventDefault();
        openModal(currentUser ? 'pricing' : 'signup');
      }
      // If hasAccess → event proceeds normally, <a> navigates
    });
  }

  // ══════════════════════════════════════════════════
  // BLOG EXPAND LOCK (intercept <details> open)
  // ══════════════════════════════════════════════════

  function interceptBlogExpand() {
    document.querySelectorAll('.blog-card[data-locked="true"]').forEach(details => {
      details.addEventListener('toggle', function (e) {
        if (this.getAttribute('data-locked') === 'true' && this.open) {
          e.preventDefault();
          this.open = false;
          openModal(currentUser ? 'pricing' : 'signup');
        }
      });

      // Also intercept click on summary
      const summary = details.querySelector('summary');
      if (summary) {
        summary.addEventListener('click', function (e) {
          if (details.getAttribute('data-locked') === 'true' && !details.open) {
            e.preventDefault();
            openModal(currentUser ? 'pricing' : 'signup');
          }
        });
      }
    });
  }

  // ══════════════════════════════════════════════════
  // ADMIN TOOLBAR
  // ══════════════════════════════════════════════════

  function renderAdminToolbar() {
    if (currentTier !== 'admin') return;

    let toolbar = document.getElementById('ma-admin-toolbar');
    if (toolbar) {
      toolbar.classList.add('active');
      return;
    }

    toolbar = document.createElement('div');
    toolbar.id = 'ma-admin-toolbar';
    toolbar.className = 'ma-admin-toolbar';

    const tiers = [
      { key: 'free', label: 'FREE' },
      { key: 'fnf', label: 'FnF' },
      { key: 'pickmaker_dual', label: 'PICKMAKER' },
      { key: 'all_access', label: 'ALL-ACCESS' },
      { key: 'admin', label: 'ADMIN' }
    ];

    toolbar.innerHTML = `<span class="ma-admin-label">ADMIN MODE</span>`;
    tiers.forEach(t => {
      const btn = document.createElement('button');
      btn.className = 'ma-admin-btn' + ((!adminOverrideTier && t.key === 'admin') || adminOverrideTier === t.key ? ' active' : '');
      btn.setAttribute('data-tier', t.key);
      btn.textContent = t.label;
      btn.onclick = () => {
        if (t.key === 'admin') {
          adminOverrideTier = null;
        } else {
          adminOverrideTier = t.key;
        }
        // Update active state
        toolbar.querySelectorAll('.ma-admin-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        // Re-apply access control
        renderProfileButton();
        applyAccessControl();
      };
      toolbar.appendChild(btn);
    });

    document.body.appendChild(toolbar);
    requestAnimationFrame(() => toolbar.classList.add('active'));
  }

  // ══════════════════════════════════════════════════
  // INITIALIZATION
  // ══════════════════════════════════════════════════

  function init() {
    initFirebase();

    // Intercept blog expand on home page after DOM is ready
    if (PAGE === 'home') {
      // Use MutationObserver to catch when locked state is applied
      const observer = new MutationObserver(() => {
        interceptBlogExpand();
      });
      observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['data-locked'] });
      // Also run once
      setTimeout(interceptBlogExpand, 500);
    }
  }

  // ── Public API ──
  window.morelloAuth = {
    openModal,
    closeModal,
    handleSignup,
    handleSignin,
    handleSignout,
    checkout,
    getEffectiveTier,
    getCurrentUser: () => currentUser,
    getCurrentTier: () => currentTier
  };

  // ── Auto-init ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
