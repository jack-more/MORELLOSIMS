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
    publishableKey: 'pk_live_51IgymQA9KGX7mrlm4mMSnHke0kSV7SkFtrJOMDat2cffozI5Y0Ih5V4sqawFIhnEWpuJ18WTtItxBmvUsCSb95y100kulsQoe8',
    prices: {
      pickmaker_nba: 'price_1TeeImA9KGX7mrlmZq17WalQ',
      pickmaker_mlb: 'price_1TeeImA9KGX7mrlmwTtxcd6W',
      pickmaker_dual: 'price_1TeeImA9KGX7mrlmyQ0usLv9',
      weekly_board: 'price_1TefcKA9KGX7mrlmGqxce0pf',
      monthly_board: 'price_1Tefu6A9KGX7mrlmLwobQ7CR',
      all_access: 'price_1T3s0qA9KGX7mrlmA8KljtHG'
    },
    // Cloud Function endpoint for creating checkout sessions
    checkoutUrl: 'https://us-central1-morello-sims.cloudfunctions.net/createCheckoutSession'
  };

  // Cloud Function endpoints (direct — morellosims.com is GitHub Pages,
  // so /api/* hosting rewrites only work on the web.app domain)
  const FUNCTIONS_BASE = 'https://us-central1-morello-sims.cloudfunctions.net';
  const REF_STORAGE_KEY = 'ma_ref_code';

  const GA_MEASUREMENT_ID = 'G-00PNGPWNPV';
  const GA_TRACKING_HOSTS = [
    'morellosims.com',
    'www.morellosims.com',
    'morello-sims.web.app',
    'morello-sims.firebaseapp.com',
    'jack-more.github.io'
  ];

  const PRODUCT_ANALYTICS = {
    pickmaker_nba: { name: 'NBA Slate Pass', price: 11.99, billing: 'one_time' },
    pickmaker_mlb: { name: 'MLB Slate Pass', price: 11.99, billing: 'one_time' },
    pickmaker_dual: { name: 'Daily Board Pass', price: 19.99, billing: 'one_time' },
    weekly_board: { name: 'Weekly Board Pass', price: 69.99, billing: 'one_time' },
    monthly_board: { name: 'Monthly Board Pass', price: 199.99, billing: 'one_time' },
    all_access: { name: 'All-Access Methodology', price: 899, billing: 'one_time' }
  };

  const ADMIN_EMAIL = 'jaidanmorello@gmail.com';

  // ── Pre-assigned email → tier whitelist ──
  // These users get their tier immediately on sign-up/sign-in,
  // even before Firestore or Cloud Functions are fully deployed.
  const EMAIL_WHITELIST = {
    'jaidanmorello@gmail.com': 'admin',
    'webb.little19@gmail.com': 'fnf',
    'samlittle2@gmail.com': 'fnf',
    'kynanbarer@gmail.com': 'fnf'
  };

  const TIER_LABELS = {
    free: 'FREE',
    fnf: 'FnF',
    pickmaker_nba: 'DAILY BOARD PASS',
    pickmaker_mlb: 'DAILY BOARD PASS',
    pickmaker_dual: 'DAILY BOARD PASS',
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
  let currentAccessExpiresAt = null;
  let currentPackageAccessHours = null;
  let adminOverrideTier = null; // For admin view-as feature
  let firebaseReady = false;
  let analyticsReady = false;
  let packageViewTracked = false;
  let freePickViewTracked = false;
  let currentRefCode = null;
  let currentReferralCount = 0;
  let currentStreak = 0;
  let checkInDone = false;
  let userVotes = {}; // pickId -> 'tail' | 'fade'
  const PICK_PACKAGE_TIERS = ['pickmaker_nba', 'pickmaker_mlb', 'pickmaker_dual'];

  // ── Detect which page we're on ──
  const PAGE = detectPage();

  function detectPage() {
    const path = window.location.pathname;
    const host = window.location.hostname;
    // All sites now under morellosims.com — detect by path
    if (path.startsWith('/atlas')) return 'atlas';
    if (path.startsWith('/mlbsim')) return 'mlbsim';
    if (path.startsWith('/nbasim')) return 'nbasim';
    if (path.startsWith('/goyard')) return 'goyard';
    if (path.startsWith('/fantasy')) return 'fantasy';
    // Legacy detection for old URLs / local dev
    if (path.includes('cosmos.html') || path.includes('cosmos')) return 'atlas';
    if (path.includes('mlbsim.html')) return 'mlbsim';
    if (host.includes('nbasim')) return 'nbasim';
    return 'home';
  }

  function shouldTrackAnalytics() {
    if (!GA_MEASUREMENT_ID) return false;
    try {
      if (window.localStorage && window.localStorage.getItem('morelloAnalyticsOptOut') === 'true') return false;
    } catch (err) {
      // Some privacy modes block localStorage. Keep analytics loading rules host-based.
    }
    return GA_TRACKING_HOSTS.includes(window.location.hostname);
  }

  function initAnalytics() {
    if (!shouldTrackAnalytics() || window.__morelloAnalyticsLoaded) return;

    window.__morelloAnalyticsLoaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = window.gtag || function () {
      window.dataLayer.push(arguments);
    };

    const script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(GA_MEASUREMENT_ID);
    document.head.appendChild(script);

    window.gtag('js', new Date());
    window.gtag('config', GA_MEASUREMENT_ID, {
      page_title: document.title,
      page_path: window.location.pathname + window.location.search,
      page_location: window.location.href
    });
    analyticsReady = true;
    setAnalyticsUserProperties();
  }

  function productAnalyticsParams(product) {
    const meta = PRODUCT_ANALYTICS[product] || {};
    return {
      product_id: product,
      product_name: meta.name || product || 'Unknown Product',
      value: meta.price || 0,
      currency: 'USD',
      billing_period: meta.billing || 'unknown'
    };
  }

  function productEcommerceParams(product) {
    const params = productAnalyticsParams(product);
    return Object.assign({}, params, {
      items: [{
        item_id: params.product_id,
        item_name: params.product_name,
        price: params.value,
        quantity: 1
      }]
    });
  }

  function trackEvent(name, params) {
    if (!analyticsReady || typeof window.gtag !== 'function') return;
    window.gtag('event', name, Object.assign({
      page_surface: PAGE,
      access_tier: getEffectiveTier()
    }, params || {}));
  }

  function setAnalyticsUserProperties() {
    if (!analyticsReady || typeof window.gtag !== 'function') return;
    window.gtag('set', 'user_properties', {
      access_tier: getEffectiveTier(),
      page_surface: PAGE
    });
  }

  function observePackageSection() {
    const section = document.querySelector('.packages-section');
    if (!section || packageViewTracked) return;

    const trackView = () => {
      if (packageViewTracked) return;
      packageViewTracked = true;
      const packageProducts = Array.from(section.querySelectorAll('[data-ma-product]'))
        .map(card => card.getAttribute('data-ma-product'))
        .filter(Boolean);
      trackEvent('view_package_section', {
        item_list_name: 'Homepage Packages',
        items: packageProducts.map(product => {
          const params = productAnalyticsParams(product);
          return {
            item_id: params.product_id,
            item_name: params.product_name,
            price: params.value
          };
        })
      });
    };

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
          trackView();
          observer.disconnect();
        }
      }, { threshold: 0.3 });
      observer.observe(section);
    } else {
      setTimeout(trackView, 1000);
    }
  }

  // ── Get effective tier (respects admin override) ──
  function getEffectiveTier() {
    if (adminOverrideTier && currentTier === 'admin') return adminOverrideTier;
    if (isCurrentPackageExpired()) return 'free';
    return currentTier;
  }

  function timestampToMillis(value) {
    if (!value) return null;
    if (typeof value.toMillis === 'function') return value.toMillis();
    if (typeof value === 'number') return value;
    if (typeof value === 'string') {
      const parsed = Date.parse(value);
      return Number.isNaN(parsed) ? null : parsed;
    }
    if (typeof value.seconds === 'number') return value.seconds * 1000;
    return null;
  }

  function isCurrentPackageExpired() {
    if (!PICK_PACKAGE_TIERS.includes(currentTier)) return false;
    if (!currentAccessExpiresAt) return false;
    return currentAccessExpiresAt <= Date.now();
  }

  function getCurrentPassLabel(tier) {
    if (tier === 'pickmaker_dual' || tier === 'pickmaker_nba' || tier === 'pickmaker_mlb') {
      if (currentPackageAccessHours >= 720) return 'MONTHLY BOARD PASS';
      if (currentPackageAccessHours >= 168) return 'WEEKLY BOARD PASS';
      return 'DAILY BOARD PASS';
    }
    return TIER_LABELS[tier] || 'MEMBER ACCESS';
  }

  function hasAccess(requiredTier) {
    const tier = getEffectiveTier();
    if (requiredTier === 'free') return true;
    if (tier === 'admin' || tier === 'all_access') return true;
    if (tier === 'fnf' && requiredTier !== 'all_access' && requiredTier !== 'admin') return true;
    if (requiredTier === 'pickmaker_nba') return tier === 'pickmaker_nba' || tier === 'pickmaker_dual';
    if (requiredTier === 'pickmaker_mlb') return tier === 'pickmaker_mlb' || tier === 'pickmaker_dual';
    if (requiredTier === 'pickmaker_dual') return tier === 'pickmaker_dual';
    return tier === requiredTier;
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
          currentAccessExpiresAt = null;
          currentPackageAccessHours = null;
        } else {
          // 2) Try Firestore for Stripe-managed tiers
          try {
            const doc = await firebase.firestore().collection('users').doc(user.uid).get();
            if (doc.exists) {
              currentRefCode = doc.data().refCode || null;
              currentReferralCount = Number(doc.data().referral_count || 0);
            }
            if (doc.exists && doc.data().tier) {
              const data = doc.data();
              currentTier = data.tier;
              currentAccessExpiresAt = timestampToMillis(data.accessExpiresAt);
              currentPackageAccessHours = Number(data.packageAccessHours || 0) || null;
            } else {
              currentTier = 'free';
              currentAccessExpiresAt = null;
              currentPackageAccessHours = null;
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
            currentAccessExpiresAt = null;
            currentPackageAccessHours = null;
          }
        }
      } else {
        currentUser = null;
        currentTier = 'free';
        currentAccessExpiresAt = null;
        currentPackageAccessHours = null;
        currentRefCode = null;
        currentReferralCount = 0;
        currentStreak = 0;
        checkInDone = false;
        userVotes = {};
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
    setAnalyticsUserProperties();
    if (currentTier === 'admin') {
      renderAdminToolbar();
    }
    if (user) {
      runCheckIn();
    } else {
      removeStreakChip();
    }
    setupTailButtons();
  }

  // ══════════════════════════════════════════════════
  // SITE NAVIGATION (cross-site nav in header)
  // ══════════════════════════════════════════════════

  function renderSiteNav() {
    // Only render once
    if (document.getElementById('ma-site-nav')) return;

    const nav = document.createElement('div');
    nav.id = 'ma-site-nav';
    nav.className = 'ma-site-nav';

    const sites = [
      { label: 'HOME',    path: '/',         color: '#AAAAAA', page: 'home' },
      { label: 'NBA',     path: '/nbasim/',  color: '#00FF55', page: 'nbasim' },
      { label: 'MLB',     path: '/mlbsim/',  color: '#FFEA00', page: 'mlbsim' },
      { label: 'ATLAS',   path: '/atlas/',   color: '#FF6B00', page: 'atlas' },
      { label: 'GOYARD',  path: '/goyard/',  color: '#00CFFF', page: 'goyard' },
      { label: 'FANTASY', path: '/fantasy/', color: '#B266FF', page: 'fantasy' }
    ];

    sites.forEach(site => {
      const link = document.createElement('a');
      link.href = site.path;
      link.className = 'ma-site-link' + (PAGE === site.page ? ' active' : '');
      link.innerHTML = '<span class="ma-site-dot" style="background:' + site.color + '"></span><span class="ma-site-label">' + site.label + '</span>';
      nav.appendChild(link);
    });

    // Find insertion point — look for .status-indicators first
    const indicators = document.querySelector('.status-indicators');
    if (indicators) {
      indicators.prepend(nav);
      return;
    }

    // Fallback: find header right-side area
    const header = document.querySelector('header') || document.querySelector('.header');
    if (header) {
      const brandRow = header.querySelector('.brand-row');
      if (brandRow) {
        // MLB SIM layout: insert into the right-side div
        const rightDiv = brandRow.querySelector('div:last-child');
        if (rightDiv) {
          rightDiv.prepend(nav);
          return;
        }
      }
      // Generic fallback: absolute position in header
      nav.style.position = 'absolute';
      nav.style.right = '16px';
      nav.style.top = '50%';
      nav.style.transform = 'translateY(-50%)';
      header.style.position = header.style.position || 'relative';
      header.appendChild(nav);
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
    trackEvent('modal_open', {
      modal_view: view,
      logged_in: Boolean(currentUser)
    });

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
    const tierLabel = getCurrentPassLabel(tier);
    return `
      <h2>PROFILE</h2>
      <p class="ma-subtitle">MORELLO SIMS ACCOUNT</p>
      <div class="ma-profile-info">
        <div class="ma-profile-email">${currentUser.email}</div>
        <div class="ma-profile-tier-display" style="color:${tierColor}">${tierLabel}</div>
      </div>
      ${tier === 'free' || tier === 'fnf' ? `
        <button class="ma-btn-primary" onclick="window.morelloAuth.openModal('pricing')" style="background:#FF6B00">UPGRADE ACCOUNT</button>
      ` : ''}
      ${(tier === 'pickmaker_nba' || tier === 'pickmaker_mlb' || tier === 'pickmaker_dual') ? `
        <button class="ma-btn-secondary" onclick="window.morelloAuth.openModal('pricing')">BUY ANOTHER PASS</button>
      ` : ''}
      ${currentRefCode ? `
        <div class="ma-invite-box">
          <div class="ma-invite-label">YOUR INVITE LINK</div>
          <div class="ma-invite-link" id="ma-invite-link" onclick="window.morelloAuth.copyInviteLink()">morellosims.com/?ref=${currentRefCode}</div>
          <div class="ma-invite-meta">3 signups = 1 week free &middot; ${currentReferralCount} signup${currentReferralCount === 1 ? '' : 's'} so far</div>
        </div>
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
            <div class="ma-pricing-name">DAILY BOARD PASS</div>
            <div class="ma-pricing-desc">Access to the Morello board, HR LOTTO, and model notes. Valid for 24 hours after purchase.</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount">$19.99<span class="ma-pricing-period"> ONE-TIME</span></div>
            <button class="ma-pricing-btn" onclick="window.morelloAuth.checkout('pickmaker_dual')">BUY DAILY BOARD</button>
          </div>
        </div>

        <div class="ma-pricing-card">
          <div>
            <div class="ma-pricing-name">WEEKLY BOARD PASS</div>
            <div class="ma-pricing-desc">Seven days of Morello board access, HR LOTTO, model notes, and tracked context.</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount">$69.99<span class="ma-pricing-period"> ONE-TIME</span></div>
            <button class="ma-pricing-btn" onclick="window.morelloAuth.checkout('weekly_board')">BUY WEEKLY BOARD</button>
          </div>
        </div>

        <div class="ma-pricing-card highlight">
          <div>
            <div class="ma-pricing-name">MONTHLY BOARD PASS</div>
            <div class="ma-pricing-desc">Thirty days of Morello board access, HR LOTTO, model notes, and tracked context.</div>
          </div>
          <div style="text-align:right">
            <div class="ma-pricing-amount">$199.99<span class="ma-pricing-period"> ONE-TIME</span></div>
            <button class="ma-pricing-btn" onclick="window.morelloAuth.checkout('monthly_board')">BUY MONTHLY BOARD</button>
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
      trackEvent('sign_up', { method: 'email' });
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
      trackEvent('login', { method: 'email' });
      closeModal();
    } catch (err) {
      showError(err.message);
    }
  }

  async function handleSignout() {
    trackEvent('logout');
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

  function openUpgradeModal(source) {
    trackEvent('upgrade_prompt_click', {
      prompt_source: source || 'unknown',
      logged_in: Boolean(currentUser)
    });
    openModal(currentUser ? 'pricing' : 'signup');
  }

  async function checkout(product) {
    trackEvent('package_cta_click', productAnalyticsParams(product));

    if (!currentUser) {
      trackEvent('checkout_auth_required', productAnalyticsParams(product));
      openModal('signup');
      return;
    }

    try {
      trackEvent('begin_checkout', productEcommerceParams(product));
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
        trackEvent('checkout_redirect', productAnalyticsParams(product));
        window.location.href = data.url;
      } else {
        trackEvent('checkout_error', Object.assign(productAnalyticsParams(product), {
          error_type: 'missing_url'
        }));
        alert('Checkout error. Please try again.');
      }
    } catch (err) {
      console.error('[morello-auth] Checkout error:', err);
      trackEvent('checkout_error', Object.assign(productAnalyticsParams(product), {
        error_type: 'request_failed'
      }));
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

    // 3) Lock/unlock pick-history dispatch rows by sport package.
    lockHomePickHistory('.post-nba-picks', 'pickmaker_nba', 'DAILY BOARD PASS');
    lockHomePickHistory('.post-mlb-picks', 'pickmaker_mlb', 'DAILY BOARD PASS');

    // 4) Add pricing tooltips to dashboard cards
    addPricingTooltips();

    // 5) Keep the homepage package shelf honest for members
    updateHomePackageSection();
  }

  function updateHomePackageSection() {
    const section = document.querySelector('.packages-section');
    if (!section) return;

    const tier = getEffectiveTier();
    const hasNba = hasAccess('pickmaker_nba');
    const hasMlb = hasAccess('pickmaker_mlb');
    const hasMethodology = tier === 'all_access' || tier === 'admin';
    const hasAnyPaidSurface = Boolean(currentUser && (hasNba || hasMlb || hasMethodology));
    const panel = section.querySelector('[data-ma-member-panel]');
    const title = section.querySelector('[data-ma-member-title]');
    const copy = section.querySelector('[data-ma-member-copy]');
    const eyebrow = section.querySelector('[data-ma-member-eyebrow]');

    section.classList.toggle('ma-member-active', hasAnyPaidSurface);

    if (panel) {
      panel.classList.toggle('is-visible', hasAnyPaidSurface);
      if (hasAnyPaidSurface) {
        if (eyebrow) eyebrow.textContent = getCurrentPassLabel(tier);
        if (title) {
          if (hasMethodology) title.textContent = 'All-Access Active';
          else title.textContent = getCurrentPassLabel(tier) + ' Active';
        }
        if (copy) {
          if (hasMethodology) {
            copy.textContent = 'The methodology room, NBA board, MLB board, and Atlas are open. No need to see checkout cards for access you already own.';
          } else if (hasNba && hasMlb) {
            copy.textContent = 'Both daily pick boards are active. Jump straight to the dashboards instead of staring at the sales shelf.';
          } else if (hasNba) {
            copy.textContent = 'Your NBA board is active. We hid the NBA checkout card and left only relevant upgrades below.';
          } else {
            copy.textContent = 'Your MLB board is active. We hid the MLB checkout card and left only relevant upgrades below.';
          }
        }
      }
    }

    section.querySelectorAll('[data-ma-member-link]').forEach(link => {
      const surface = link.getAttribute('data-ma-member-link');
      const visible =
        hasAnyPaidSurface &&
        (surface === 'atlas' ||
          (surface === 'nba' && hasNba) ||
          (surface === 'mlb' && hasMlb));
      link.classList.toggle('is-visible', visible);
    });

    section.querySelectorAll('[data-ma-product]').forEach(card => {
      const product = card.getAttribute('data-ma-product');
      let owned = false;

      if (hasAnyPaidSurface) {
        if (product === 'pickmaker_nba') owned = hasNba;
        if (product === 'pickmaker_mlb') owned = hasMlb;
        if (product === 'pickmaker_dual') owned = hasNba || hasMlb;
        if (product === 'weekly_board') owned = hasNba || hasMlb;
        if (product === 'monthly_board') owned = hasNba || hasMlb;
        if (product === 'all_access') owned = hasMethodology;
      }

      card.classList.toggle('ma-owned-hidden', owned);
    });

    const grid = section.querySelector('.packages-grid');
    if (grid) {
      const visibleCards = Array.from(grid.querySelectorAll('[data-ma-product]'))
        .filter(card => !card.classList.contains('ma-owned-hidden')).length;
      grid.style.display = visibleCards ? 'grid' : 'none';
      grid.classList.toggle('ma-single-offer', visibleCards === 1);
    }
  }

  function lockHomePickHistory(selector, requiredTier, label) {
    const post = document.querySelector(selector);
    if (!post) return;

    if (hasAccess(requiredTier)) {
      post.classList.remove('ma-locked', 'ma-pick-locked');
      post.removeAttribute('data-locked');
      post.removeAttribute('data-lock-label');
      post.removeAttribute('data-required-tier');
    } else {
      post.classList.add('ma-locked', 'ma-pick-locked');
      post.setAttribute('data-locked', 'true');
      post.setAttribute('data-lock-label', label);
      post.setAttribute('data-required-tier', requiredTier);
      post.open = false;
    }
  }

  function lockHomePickHistory(selector, requiredTier, label) {
    const post = document.querySelector(selector);
    if (!post) return;

    if (hasAccess(requiredTier)) {
      post.classList.remove('ma-locked', 'ma-pick-locked');
      post.removeAttribute('data-locked');
      post.removeAttribute('data-lock-label');
      post.removeAttribute('data-required-tier');
    } else {
      post.classList.add('ma-locked', 'ma-pick-locked');
      post.setAttribute('data-locked', 'true');
      post.setAttribute('data-lock-label', label);
      post.setAttribute('data-required-tier', requiredTier);
      post.open = false;
    }
  }

  // ── ATLAS (cosmos.html) — Free access, no gate ──
  function applyAtlasAccess() {
    // Atlas is free. No access gate needed.
    // Methodology text is minimal on this page.
  }

  // ── MLB SIM ──
  function applyMlbSimAccess() {
    const tier = getEffectiveTier();
    const hasPickAccess = hasAccess('pickmaker_mlb');
    const isMethodologyUnlocked = tier === 'all_access' || tier === 'admin';

    // 1) Selective blur on premium elements (replaces full-page gate).
    //    Freemium hook: the first C8+ pick of the day stays unblurred for
    //    everyone as the FREE PICK OF THE DAY.
    const freePickCard = hasPickAccess ? null : findFreePickCard();
    document.querySelectorAll('.ma-premium').forEach(el => {
      const isFreePick = freePickCard && freePickCard.contains(el);
      if (hasPickAccess || isFreePick) {
        el.classList.remove('ma-blur');
        el.classList.add('ma-unblurred');
      } else {
        el.classList.add('ma-blur');
        el.classList.remove('ma-unblurred');
      }
    });
    applyFreePickBadge(freePickCard);

    // 2) CTA banner for free users
    if (!hasPickAccess) {
      addPremiumOverlay('MLB');
    } else {
      const existing = document.getElementById('ma-premium-banner');
      if (existing) existing.remove();
    }

    // 3) Blur INFO tab cards (methodology — all_access only)
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
    const hasPickAccess = hasAccess('pickmaker_nba');
    const isMethodologyUnlocked = tier === 'all_access' || tier === 'admin';

    // 1) Freemium model: only gate picks with confidence >= 9
    //    Lower-confidence picks are visible to everyone to showcase the product.
    document.querySelectorAll('.ma-premium').forEach(el => {
      if (hasPickAccess) {
        el.classList.remove('ma-blur');
        el.classList.add('ma-unblurred');
      } else {
        const card = el.closest('.matchup-card');
        const conf = card ? parseInt(card.getAttribute('data-conf') || '0', 10) : 0;
        if (conf >= 9) {
          el.classList.add('ma-blur');
          el.classList.remove('ma-unblurred');
        } else {
          el.classList.remove('ma-blur');
          el.classList.add('ma-unblurred');
        }
      }
    });

    // 2) CTA banner only if there are locked (conf >= 9) picks today
    const hasLockedPicks = !hasPickAccess &&
      document.querySelectorAll('.matchup-card').length > 0 &&
      [...document.querySelectorAll('.matchup-card')].some(c => parseInt(c.getAttribute('data-conf') || '0', 10) >= 9);
    if (hasLockedPicks) {
      addPremiumOverlay('NBA');
    } else {
      const existing = document.getElementById('ma-premium-banner');
      if (existing) existing.remove();
    }

    // 3) Blur INFO sections (methodology — all_access only)
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

  // ══════════════════════════════════════════════════
  // GROWTH FEATURES — free pick, tail/fade, streaks,
  // referrals, email capture
  // ══════════════════════════════════════════════════

  // ── Injected styles for growth UI (dark mono aesthetic) ──
  function injectGrowthStyles() {
    if (document.getElementById('ma-growth-styles')) return;
    const style = document.createElement('style');
    style.id = 'ma-growth-styles';
    style.textContent = `
      .ma-free-pick { outline: 2px solid #FFEA00; }
      .ma-free-pick-badge { display:block; background:#FFEA00; color:#080808; font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700; letter-spacing:2px; padding:6px 12px; text-transform:uppercase; }
      .ma-free-pick-cta { display:block; width:calc(100% - 24px); margin:6px 12px 10px; padding:9px 12px; background:transparent; border:1px solid #FFEA00; color:#FFEA00; font-family:'JetBrains Mono',monospace; font-size:10px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; cursor:pointer; text-align:center; transition:background .12s,color .12s; }
      .ma-free-pick-cta:hover { background:#FFEA00; color:#080808; }
      .ma-tail-bar { display:flex; align-items:center; gap:8px; padding:7px 12px; border-top:1px solid #1e1e1e; font-family:'JetBrains Mono',monospace; }
      .ma-tail-bar-label { font-size:8px; color:#666; letter-spacing:2px; font-weight:700; margin-right:auto; }
      .ma-tail-btn { display:inline-flex; align-items:center; gap:6px; background:#0a0a0a; border:1px solid #2a2a2a; color:#888; font-family:inherit; font-size:9px; font-weight:700; letter-spacing:1.5px; padding:4px 10px; cursor:pointer; text-transform:uppercase; transition:border-color .12s,color .12s; }
      .ma-tail-btn:hover { border-color:#555; color:#ccc; }
      .ma-tail-btn:disabled { opacity:.5; cursor:wait; }
      .ma-tail-btn .ma-tail-count { color:#fff; }
      .ma-tail-btn.ma-vote-active[data-side="tail"] { border-color:#00FF55; color:#00FF55; }
      .ma-tail-btn.ma-vote-active[data-side="tail"] .ma-tail-count { color:#00FF55; }
      .ma-tail-btn.ma-vote-active[data-side="fade"] { border-color:#FF0040; color:#FF0040; }
      .ma-tail-btn.ma-vote-active[data-side="fade"] .ma-tail-count { color:#FF0040; }
      .ma-streak-chip { display:inline-flex; align-items:center; gap:6px; background:#0a0a0a; border:1px solid #2a2a2a; color:#fff; font-family:'JetBrains Mono',monospace; font-size:9px; font-weight:700; letter-spacing:1px; padding:4px 8px; white-space:nowrap; }
      .ma-streak-bonus { color:#FFEA00; }
      .ma-invite-box { margin-top:14px; padding:12px; border:1px dashed #333; background:#0a0a0a; text-align:left; font-family:'JetBrains Mono',monospace; }
      .ma-invite-box .ma-invite-label { font-size:8px; letter-spacing:2px; color:#666; font-weight:700; margin-bottom:6px; }
      .ma-invite-link { font-size:11px; color:#FFEA00; cursor:pointer; word-break:break-all; }
      .ma-invite-link:hover { text-decoration:underline; }
      .ma-invite-meta { margin-top:6px; font-size:9px; color:#888; letter-spacing:.5px; }
    `;
    document.head.appendChild(style);
  }

  // ── FREE PICK OF THE DAY (MLB) ──
  // The first C8+ game card of the slate; falls back to the highest-conf
  // card on slates with no C8 so the showcase always exists.
  function findFreePickCard() {
    let cards = Array.from(document.querySelectorAll('#tab-lines .game-card'));
    if (!cards.length) cards = Array.from(document.querySelectorAll('.game-card'));
    if (!cards.length) return null;
    const conf = (c) => parseInt(c.getAttribute('data-conf') || '0', 10);
    return cards.find(c => conf(c) >= 8) ||
      cards.reduce((best, c) => (conf(c) > conf(best) ? c : best), cards[0]);
  }

  function applyFreePickBadge(card) {
    // Clean up any previous state (admin view-as re-runs this)
    document.querySelectorAll('.ma-free-pick-badge, .ma-free-pick-cta').forEach(el => el.remove());
    document.querySelectorAll('.ma-free-pick').forEach(el => el.classList.remove('ma-free-pick'));
    if (!card) return;

    card.classList.add('ma-free-pick');

    const badge = document.createElement('div');
    badge.className = 'ma-free-pick-badge';
    badge.innerHTML = '&#9733; FREE PICK OF THE DAY';
    card.insertBefore(badge, card.firstChild);

    const cta = document.createElement('button');
    cta.className = 'ma-free-pick-cta';
    cta.innerHTML = 'Unlock all picks &rarr;';
    cta.onclick = () => {
      trackEvent('free_pick_cta_click', { pick_conf: card.getAttribute('data-conf') || '' });
      openUpgradeModal('free_pick_cta');
    };
    const header = card.querySelector('.card-header');
    if (header && header.parentNode === card) {
      card.insertBefore(cta, header.nextSibling);
    } else {
      card.insertBefore(cta, badge.nextSibling);
    }

    if (!freePickViewTracked) {
      freePickViewTracked = true;
      trackEvent('free_pick_viewed', {
        pick_conf: card.getAttribute('data-conf') || '',
        pick_id: pickIdForCard(card, 'mlb') || ''
      });
    }
  }

  // ── TAIL / FADE ──
  function slateSlug() {
    let label = '';
    const slateInfo = document.querySelector('.slate-info span');
    if (slateInfo) label = slateInfo.textContent || '';
    if (!/SLATE/i.test(label)) {
      const heading = Array.from(document.querySelectorAll('h2'))
        .find(h => /SLATE/i.test(h.textContent || ''));
      if (heading) label = heading.textContent || '';
    }
    const slug = label.replace(/SLATE/i, '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '');
    return String(new Date().getFullYear()) + (slug || 'day');
  }

  function pickIdForCard(card, sport, slug) {
    const abbrSel = sport === 'nba' ? '.mc-abbr' : '.team-abbr';
    const abbrs = Array.from(card.querySelectorAll(abbrSel))
      .map(el => (el.textContent || '').trim())
      .filter(Boolean);
    if (abbrs.length < 2) return null;
    const raw = [sport, slug || slateSlug(), abbrs[0], abbrs[1]].join('_');
    return raw.replace(/[^A-Za-z0-9_-]/g, '');
  }

  function setupTailButtons() {
    if (PAGE !== 'mlbsim' && PAGE !== 'nbasim') return;

    // Rebuild from scratch on each auth change — idempotent
    document.querySelectorAll('.ma-tail-bar').forEach(el => el.remove());

    const sport = PAGE === 'nbasim' ? 'nba' : 'mlb';
    let cards = [];
    if (currentUser) {
      cards = Array.from(document.querySelectorAll(sport === 'nba' ? '.matchup-card' : '.game-card'));
    } else if (sport === 'mlb') {
      // Anonymous users only vote on the free pick of the day
      const freeCard = findFreePickCard();
      if (freeCard) cards = [freeCard];
    }
    if (!cards.length) return;

    const slug = slateSlug();
    const bars = [];
    cards.forEach(card => {
      const pickId = pickIdForCard(card, sport, slug);
      if (!pickId) return;
      const bar = renderTailBar(card, pickId, sport);
      if (bar) bars.push({ pickId, bar });
    });

    loadTailData(bars);
  }

  function renderTailBar(card, pickId, sport) {
    const bar = document.createElement('div');
    bar.className = 'ma-tail-bar';
    bar.setAttribute('data-pick-id', pickId);
    bar.innerHTML = `
      <span class="ma-tail-bar-label">COMMUNITY</span>
      <button class="ma-tail-btn" data-side="tail">&#9650; TAIL <span class="ma-tail-count">0</span></button>
      <button class="ma-tail-btn" data-side="fade">&#9660; FADE <span class="ma-tail-count">0</span></button>
    `;
    bar.querySelectorAll('.ma-tail-btn').forEach(btn => {
      btn.addEventListener('click', () => handleTailVote(bar, pickId, btn.getAttribute('data-side')));
    });

    const anchor = card.querySelector(sport === 'nba' ? '.mc-header' : '.card-header');
    if (anchor && anchor.parentNode === card) {
      card.insertBefore(bar, anchor.nextSibling);
    } else {
      card.appendChild(bar);
    }
    updateTailBarActive(bar, pickId);
    return bar;
  }

  function updateTailBarCounts(bar, counts) {
    bar.querySelectorAll('.ma-tail-btn').forEach(btn => {
      const side = btn.getAttribute('data-side');
      const countEl = btn.querySelector('.ma-tail-count');
      if (countEl) countEl.textContent = String(Math.max(0, Number((counts || {})[side] || 0)));
    });
  }

  function updateTailBarActive(bar, pickId) {
    const vote = userVotes[pickId] || null;
    bar.querySelectorAll('.ma-tail-btn').forEach(btn => {
      btn.classList.toggle('ma-vote-active', btn.getAttribute('data-side') === vote);
    });
  }

  function loadTailData(bars) {
    if (!bars.length || typeof firebase === 'undefined' || !firebase.apps || !firebase.apps.length) return;
    const store = firebase.firestore();

    // Public aggregate counts
    bars.forEach(({ pickId, bar }) => {
      store.collection('tail_counts').doc(pickId).get()
        .then(doc => { if (doc.exists) updateTailBarCounts(bar, doc.data()); })
        .catch(() => {});
    });

    // Signed-in user's own votes
    if (currentUser) {
      store.collection('user_tails').doc(currentUser.uid).collection('picks').get()
        .then(snap => {
          userVotes = {};
          snap.forEach(doc => { userVotes[doc.id] = doc.data().side; });
          bars.forEach(({ pickId, bar }) => updateTailBarActive(bar, pickId));
        })
        .catch(() => {});
    }
  }

  async function handleTailVote(bar, pickId, side) {
    if (!currentUser) {
      trackEvent('tail_signup_prompt', { pick_id: pickId, tail_side: side });
      openModal('signup');
      return;
    }

    const btns = bar.querySelectorAll('.ma-tail-btn');
    btns.forEach(b => { b.disabled = true; });
    try {
      const token = await currentUser.getIdToken();
      const resp = await fetch(FUNCTIONS_BASE + '/recordTail', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify({ pickId, side })
      });
      const data = await resp.json();
      if (data && data.ok) {
        if (data.side) userVotes[pickId] = data.side;
        else delete userVotes[pickId];
        if (data.counts) updateTailBarCounts(bar, data.counts);
        updateTailBarActive(bar, pickId);
        trackEvent('tail_vote', { pick_id: pickId, tail_side: data.side || 'removed' });
      }
    } catch (err) {
      console.warn('[morello-auth] Tail vote failed:', err);
    } finally {
      btns.forEach(b => { b.disabled = false; });
    }
  }

  // ── CHECK-IN STREAK ──
  async function runCheckIn() {
    if (checkInDone || !currentUser) return;
    checkInDone = true;
    try {
      const token = await currentUser.getIdToken();
      const resp = await fetch(FUNCTIONS_BASE + '/checkIn', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token
        },
        body: JSON.stringify({ refCode: getStoredRefCode() })
      });
      const data = await resp.json();
      if (data && data.ok) {
        currentStreak = Number(data.streak || 0);
        if (data.refCode) currentRefCode = data.refCode;
        if (typeof data.referralCount === 'number') currentReferralCount = data.referralCount;
        if (data.referralApplied) clearStoredRefCode();
        renderStreakChip();
        trackEvent('daily_check_in', { streak_days: currentStreak });
      }
    } catch (err) {
      console.warn('[morello-auth] Check-in failed:', err);
    }
  }

  function renderStreakChip() {
    removeStreakChip();
    if (!currentUser || currentStreak < 1) return;

    const chip = document.createElement('div');
    chip.id = 'ma-streak-chip';
    chip.className = 'ma-streak-chip';
    chip.innerHTML = '&#128293; ' + currentStreak + '-day streak' +
      (currentStreak >= 5 ? ' <span class="ma-streak-bonus">STREAK BONUS</span>' : '');
    if (currentStreak >= 5) {
      chip.title = 'Streak bonus active — 5+ straight days on the board. Perks coming soon.';
    }

    const profileBtn = document.getElementById('ma-profile-btn');
    if (profileBtn && profileBtn.parentNode) {
      profileBtn.parentNode.insertBefore(chip, profileBtn);
    } else {
      const indicators = document.querySelector('.status-indicators');
      if (indicators) indicators.appendChild(chip);
    }
  }

  function removeStreakChip() {
    const existing = document.getElementById('ma-streak-chip');
    if (existing) existing.remove();
  }

  // ── REFERRALS ──
  function captureRefFromUrl() {
    try {
      const ref = new URLSearchParams(window.location.search).get('ref');
      if (ref && /^[A-Za-z0-9]{4,12}$/.test(ref)) {
        window.localStorage.setItem(REF_STORAGE_KEY, ref.toUpperCase());
      }
    } catch (err) {
      // localStorage blocked — referral attribution silently unavailable
    }
  }

  function getStoredRefCode() {
    try {
      return window.localStorage.getItem(REF_STORAGE_KEY) || '';
    } catch (err) {
      return '';
    }
  }

  function clearStoredRefCode() {
    try {
      window.localStorage.removeItem(REF_STORAGE_KEY);
    } catch (err) {
      // ignore
    }
  }

  function copyInviteLink() {
    if (!currentRefCode) return;
    const link = 'https://morellosims.com/?ref=' + currentRefCode;
    const flash = () => {
      const el = document.getElementById('ma-invite-link');
      if (el) {
        const original = el.textContent;
        el.textContent = 'COPIED';
        setTimeout(() => { el.textContent = original; }, 1200);
      }
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(link).then(flash).catch(() => {});
    } else {
      window.prompt('Copy your invite link:', link);
    }
    trackEvent('invite_link_copy');
  }

  // ── EMAIL CAPTURE (public helper for landing pages) ──
  async function submitEmailCapture(email, source) {
    try {
      const resp = await fetch(FUNCTIONS_BASE + '/emailCapture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email, source: source || PAGE })
      });
      const data = await resp.json();
      if (data && data.ok) {
        trackEvent('email_capture', { capture_source: source || PAGE });
        return true;
      }
      return false;
    } catch (err) {
      console.warn('[morello-auth] Email capture failed:', err);
      return false;
    }
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
        <button class="ma-gate-btn" onclick="window.morelloAuth.openUpgradeModal('page_gate')">
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

  // ── Premium upgrade CTA banner (selective blur model) ──
  function addPremiumOverlay(sport) {
    // Don't duplicate
    if (document.getElementById('ma-premium-banner')) return;

    const isNBA = sport === 'NBA';
    const accentColor = isNBA ? 'var(--accent-nba, #00FF55)' : 'var(--accent-mlb, #FFEA00)';

    const banner = document.createElement('div');
    banner.id = 'ma-premium-banner';
    banner.className = 'ma-premium-banner';
    banner.innerHTML = `
      <div class="premium-banner-text">
        <span class="premium-banner-lock">&#128274;</span>
        <strong>UNLOCK ${sport} PICKS</strong> — Projected spreads, confidence scores, edge calculations & pick recommendations
      </div>
      <div class="premium-banner-actions">
        <button class="cta-btn cta-btn-dual" onclick="window.morelloAuth.openUpgradeModal('premium_banner_daily_board')" style="background:${accentColor}">
          DAILY BOARD $19.99
        </button>
      </div>
    `;

    // Insert at top of the app content area. Keep body as the final fallback so
    // the banner does not jump above sticky app headers.
    const main = document.querySelector('main') ||
      document.querySelector('.container') ||
      document.querySelector('.sim-container') ||
      document.body;
    if (main) {
      main.insertBefore(banner, main.firstChild);
    }
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
        tip.innerHTML = '$19.99<br><span style="font-size:8px;opacity:0.6">DAILY BOARD PASS</span>';
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
        tip.innerHTML = '$19.99<br><span style="font-size:8px;opacity:0.6">DAILY BOARD PASS</span>';
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
        trackEvent('dashboard_card_locked_click', {
          required_tier: requiredTier
        });
        openUpgradeModal('dashboard_card');
      }
      // If hasAccess → event proceeds normally, <a> navigates
    });
  }

  // ══════════════════════════════════════════════════
  // BLOG EXPAND LOCK (intercept <details> open)
  // ══════════════════════════════════════════════════

  function interceptBlogExpand() {
    document.querySelectorAll('.blog-card[data-locked="true"]').forEach(details => {
      if (details.dataset.maBlogListenerSet) return;
      details.dataset.maBlogListenerSet = 'true';

      const source = details.classList.contains('post-nba-picks') ? 'locked_nba_pick_history' :
        details.classList.contains('post-mlb-picks') ? 'locked_mlb_pick_history' :
        'locked_methodology';

      const trackLockedClick = (interaction) => {
        trackEvent('locked_content_click', {
          prompt_source: source,
          interaction,
          lock_label: details.getAttribute('data-lock-label') || '',
          required_tier: details.getAttribute('data-required-tier') || ''
        });
      };

      details.addEventListener('toggle', function (e) {
        if (this.getAttribute('data-locked') === 'true' && this.open) {
          e.preventDefault();
          this.open = false;
          trackLockedClick('toggle');
          openUpgradeModal(source);
        }
      });

      // Also intercept click on summary
      const summary = details.querySelector('summary');
      if (summary) {
        summary.addEventListener('click', function (e) {
          if (details.getAttribute('data-locked') === 'true' && !details.open) {
            e.preventDefault();
            trackLockedClick('summary_click');
            openUpgradeModal(source);
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
      { key: 'pickmaker_dual', label: 'DAILY BOARD' },
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
        setAnalyticsUserProperties();
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
    initAnalytics();
    injectGrowthStyles();
    captureRefFromUrl();

    // Render site navigation immediately (no auth needed)
    renderSiteNav();
    observePackageSection();

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
    openUpgradeModal,
    closeModal,
    handleSignup,
    handleSignin,
    handleSignout,
    checkout,
    trackEvent,
    getEffectiveTier,
    getCurrentUser: () => currentUser,
    getCurrentTier: () => currentTier,
    copyInviteLink,
    emailCapture: submitEmailCapture,
    getStreak: () => currentStreak,
    getRefCode: () => currentRefCode
  };

  // ── Auto-init ──
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // ── MLB Sort Fix (survives pipeline overwrites) ──
  if (document.body && document.body.getAttribute('data-ma-theme') === 'mlb') {
    var _cards = Array.from(document.querySelectorAll('#tab-lines .game-card'));
    if (_cards.length) {
      window.sortGames = function(mode, el) {
        var container = document.querySelector('#tab-lines');
        if (!container) return;
        var cards = Array.from(container.querySelectorAll('.game-card'));
        if (!cards.length) return;
        document.querySelectorAll('.chips .chip').forEach(function(c) { c.classList.remove('active'); });
        el.classList.add('active');
        var sorted;
        if (mode === 'value') {
          sorted = cards.slice().sort(function(a, b) { return (parseFloat(b.dataset.value) || 0) - (parseFloat(a.dataset.value) || 0); });
        } else if (mode === 'confidence') {
          sorted = cards.slice().sort(function(a, b) { return (parseFloat(b.dataset.conf) || 0) - (parseFloat(a.dataset.conf) || 0); });
        } else {
          sorted = _cards.slice();
        }
        var parent = cards[0].parentNode;
        sorted.forEach(function(card) { parent.appendChild(card); });
      };
    }
  }
})();
