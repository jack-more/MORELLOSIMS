const functions = require('firebase-functions');
const admin = require('firebase-admin');
const Stripe = require('stripe');
const cors = require('cors')({ origin: true });
const https = require('https');

admin.initializeApp();
const db = admin.firestore();

// TODO: Set these via `firebase functions:config:set stripe.secret="sk_live_xxx" stripe.webhook_secret="whsec_xxx"`
// Or use Firebase environment config
const stripe = new Stripe(functions.config().stripe?.secret || process.env.STRIPE_SECRET_KEY);
const WEBHOOK_SECRET = functions.config().stripe?.webhook_secret || process.env.STRIPE_WEBHOOK_SECRET;

// Price ID to checkout package mapping. Old recurring prices are kept so
// in-flight sessions and existing subscription webhooks still resolve.
const PRICE_TO_PACKAGE = {
  'price_1TeeImA9KGX7mrlmZq17WalQ': { tier: 'pickmaker_nba', mode: 'payment', accessHours: 24 },
  'price_1TeeImA9KGX7mrlmwTtxcd6W': { tier: 'pickmaker_mlb', mode: 'payment', accessHours: 24 },
  'price_1TeeImA9KGX7mrlmyQ0usLv9': { tier: 'pickmaker_dual', mode: 'payment', accessHours: 24 },
  'price_1TefcKA9KGX7mrlmGqxce0pf': { tier: 'pickmaker_dual', mode: 'payment', accessHours: 168 },
  'price_1Tefu6A9KGX7mrlmLwobQ7CR': { tier: 'pickmaker_dual', mode: 'payment', accessHours: 720 },
  'price_1T3rqNA9KGX7mrlmCQi4QcnU': { tier: 'pickmaker_nba', mode: 'subscription' },
  'price_1T3rqqA9KGX7mrlmHncjyPlp': { tier: 'pickmaker_mlb', mode: 'subscription' },
  'price_1T3rvjA9KGX7mrlmxJI5V00r': { tier: 'pickmaker_dual', mode: 'subscription' },
  'price_1T3s0qA9KGX7mrlmA8KljtHG': { tier: 'all_access', mode: 'payment' }
};

// REFERRALS (owner, 2026-10-25): anyone with an account gets a code. A customer who
// uses one gets 25% off a first pass and is tied to that code's owner; the owner earns
// 30% of everything that customer pays, every purchase, for good. Payouts are manual
// (the owner's Telegram /refs and /paid); this only keeps the books.
//   affiliate_codes/{CODE}     {uid}                  one code per account, unique
//   users/{uid}                affiliateCode, referred_by_affiliate, referred_code
//   affiliate_earnings/{sess}  {affiliate_uid, buyer_uid, amount_cents, commission_cents, status}
//   affiliate_payouts/{id}     {affiliate_uid, amount_cents, note}
const REF_COUPON = 'MS_FRIEND25';
const REF_DISCOUNT_PCT = 25;
const REF_COMMISSION = 0.30;
const CODE_RE = /^[A-Z0-9]{4,12}$/;

async function refCoupon() {
  try {
    return (await stripe.coupons.retrieve(REF_COUPON)).id;
  } catch (err) {
    if (err.statusCode !== 404) throw err;
    return (await stripe.coupons.create({
      id: REF_COUPON, percent_off: REF_DISCOUNT_PCT, duration: 'once', name: 'Friend code: 25% off your first pass'
    })).id;
  }
}

// The account behind a code: its affiliate_codes doc, else a member's older refCode
async function codeOwner(code) {
  if (!CODE_RE.test(code)) return null;
  const doc = await db.collection('affiliate_codes').doc(code).get();
  if (doc.exists) return doc.data().uid;
  const q = await db.collection('users').where('refCode', '==', code).limit(1).get();
  return q.empty ? null : q.docs[0].id;
}

// A first purchase: nothing bought before on this account (pass, subscription or a coded buy)
const hasBought = (u) => !!(u && (u.packagePurchasedAt || u.checkoutMode || u.referred_by_affiliate));

// CREATE CHECKOUT SESSION
// Called from morello-auth.js when user clicks a checkout CTA
exports.createCheckoutSession = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }

    try {
      const { priceId, uid, email, successUrl, cancelUrl } = req.body;
      const code = String(req.body.code || '').trim().toUpperCase();

      if (!priceId || !uid || !email) {
        res.status(400).json({ error: 'Missing required fields: priceId, uid, email' });
        return;
      }
      // before any Stripe call, so a bad request leaves nothing behind
      if (!PRICE_TO_PACKAGE[priceId]) {
        res.status(400).json({ error: 'Unknown priceId' });
        return;
      }

      // Check if user already has a Stripe customer ID
      const userDoc = await db.collection('users').doc(uid).get();
      let customerId;

      if (userDoc.exists && userDoc.data().stripeCustomerId) {
        customerId = userDoc.data().stripeCustomerId;
      } else {
        // Create Stripe customer
        const customer = await stripe.customers.create({
          email: email,
          metadata: { firebaseUid: uid }
        });
        customerId = customer.id;

        // Save customer ID to Firestore
        await db.collection('users').doc(uid).set(
          { stripeCustomerId: customerId },
          { merge: true }
        );
      }

      const checkoutPackage = PRICE_TO_PACKAGE[priceId];
      if (!checkoutPackage) {
        res.status(400).json({ error: 'Unknown priceId' });
        return;
      }

      const { tier, mode, accessHours } = checkoutPackage;

      const sessionParams = {
        customer: customerId,
        payment_method_types: ['card'],
        line_items: [{ price: priceId, quantity: 1 }],
        mode: mode,
        success_url: successUrl || 'https://morellosims.com/?checkout=success',
        cancel_url: cancelUrl || 'https://morellosims.com/?checkout=cancel',
        metadata: {
          firebaseUid: uid,
          tier: tier,
          accessHours: accessHours || ''
        }
      };

      if (mode === 'subscription') {
        sessionParams.subscription_data = {
          metadata: { firebaseUid: uid, tier: tier }
        };
      }

      // referral: a customer already tied to a code owner pays that owner on every buy;
      // a new customer with a valid code (not their own) gets 25% off this first pass
      const u = userDoc.exists ? userDoc.data() : {};
      let codeNote = '';
      if (u.referred_by_affiliate) {
        sessionParams.metadata.affiliate_uid = u.referred_by_affiliate;
      } else if (code && mode === 'payment') {
        const owner = await codeOwner(code);
        if (!owner) codeNote = 'That code isn’t one of ours.';
        else if (owner === uid) codeNote = 'You can’t use your own code.';
        else if (hasBought(u)) codeNote = 'Codes work on a first pass only.';
        else {
          sessionParams.discounts = [{ coupon: await refCoupon() }];
          Object.assign(sessionParams.metadata, { affiliate_uid: owner, ref_code: code });
          codeNote = 'applied';
        }
      }

      const session = await stripe.checkout.sessions.create(sessionParams);
      res.json({ url: session.url, code: codeNote });
    } catch (err) {
      console.error('Checkout session error:', err);
      res.status(500).json({ error: err.message });
    }
  });
});

// STRIPE WEBHOOK
// Handles: checkout.session.completed, customer.subscription.deleted
exports.stripeWebhook = functions.https.onRequest(async (req, res) => {
  const sig = req.headers['stripe-signature'];

  let event;
  try {
    event = stripe.webhooks.constructEvent(req.rawBody, sig, WEBHOOK_SECRET);
  } catch (err) {
    console.error('Webhook signature verification failed:', err.message);
    res.status(400).send(`Webhook Error: ${err.message}`);
    return;
  }

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object;
      const uid = session.metadata?.firebaseUid;
      const tier = session.metadata?.tier;
      const accessHours = Number(session.metadata?.accessHours || 0);

      if (uid && tier) {
        const updates = {
          tier: tier,
          stripeCustomerId: session.customer,
          checkoutMode: session.mode,
          updatedAt: admin.firestore.FieldValue.serverTimestamp()
        };

        if (accessHours > 0) {
          const expiresAtMs = Date.now() + accessHours * 60 * 60 * 1000;
          updates.accessExpiresAt = admin.firestore.Timestamp.fromMillis(expiresAtMs);
          updates.packageAccessHours = accessHours;
          updates.packagePurchasedAt = admin.firestore.FieldValue.serverTimestamp();
        }

        await db.collection('users').doc(uid).set(
          updates,
          { merge: true }
        );
        console.log(`Updated user ${uid} to tier: ${tier}`);
        await recordReferral(session, uid);
      }
      break;
    }

    case 'charge.refunded': {
      // a refunded purchase earns no commission
      const charge = event.data.object;
      if (charge.payment_intent) {
        const q = await db.collection('affiliate_earnings').where('payment_intent', '==', charge.payment_intent).get();
        for (const d of q.docs) {
          await d.ref.set({ status: 'reversed', reversedAt: admin.firestore.FieldValue.serverTimestamp() }, { merge: true });
        }
      }
      break;
    }

    case 'customer.subscription.deleted': {
      const subscription = event.data.object;
      const uid = subscription.metadata?.firebaseUid;

      if (uid) {
        await db.collection('users').doc(uid).set(
          {
            tier: 'free',
            updatedAt: admin.firestore.FieldValue.serverTimestamp()
          },
          { merge: true }
        );
        console.log(`Subscription cancelled for user ${uid}, reverted to free`);
      }
      break;
    }

    case 'customer.subscription.updated': {
      const subscription = event.data.object;
      const uid = subscription.metadata?.firebaseUid;

      // If subscription went past_due or cancelled, revert tier
      if (uid && (subscription.status === 'past_due' || subscription.status === 'canceled' || subscription.status === 'unpaid')) {
        await db.collection('users').doc(uid).set(
          {
            tier: 'free',
            updatedAt: admin.firestore.FieldValue.serverTimestamp()
          },
          { merge: true }
        );
        console.log(`Subscription status changed to ${subscription.status} for user ${uid}`);
      }
      break;
    }

    default:
      console.log(`Unhandled event type: ${event.type}`);
  }

  res.json({ received: true });
});

// A paid checkout with a code owner on it: tie a new customer to the code they used (once,
// for good) and book 30% of what they paid. Keyed by session id, so a retried webhook
// books nothing twice.
async function recordReferral(session, buyerUid) {
  const affiliateUid = session.metadata?.affiliate_uid;
  if (!affiliateUid || affiliateUid === buyerUid || session.payment_status !== 'paid') return;
  const buyerRef = db.collection('users').doc(buyerUid);
  const earnRef = db.collection('affiliate_earnings').doc(session.id);
  const amount = Number(session.amount_total || 0);
  await db.runTransaction(async (tx) => {
    const [buyer, earned] = await Promise.all([tx.get(buyerRef), tx.get(earnRef)]);
    if (earned.exists) return;
    const b = buyer.exists ? buyer.data() : {};
    if (b.referred_by_affiliate && b.referred_by_affiliate !== affiliateUid) return;   // tied to someone else
    if (!b.referred_by_affiliate) {
      if (!session.metadata?.ref_code) return;                                         // never used a code
      tx.set(buyerRef, { referred_by_affiliate: affiliateUid, referred_code: session.metadata.ref_code,
                         referredAt: admin.firestore.FieldValue.serverTimestamp() }, { merge: true });
    }
    tx.set(earnRef, {
      affiliate_uid: affiliateUid, buyer_uid: buyerUid, ref_code: session.metadata?.ref_code || b.referred_code || '',
      amount_cents: amount, commission_cents: Math.round(amount * REF_COMMISSION), currency: session.currency || 'usd',
      tier: session.metadata?.tier || '', access_hours: Number(session.metadata?.accessHours || 0),
      payment_intent: session.payment_intent || '', status: 'owed',
      createdAt: admin.firestore.FieldValue.serverTimestamp()
    });
  });
}

// A readable starting code from the email's name part, made unique: JAIDAN, JAIDAN2...
async function claimDefaultCode(uid, email) {
  const base = (String(email || '').split('@')[0].toUpperCase().replace(/[^A-Z0-9]/g, '') || 'FRIEND').slice(0, 9).padEnd(4, 'X');
  for (let i = 0; i < 50; i++) {
    const code = i === 0 ? base : `${base}${i + 1}`;
    const ok = await db.runTransaction(async (tx) => {
      const ref = db.collection('affiliate_codes').doc(code);
      if ((await tx.get(ref)).exists) return false;
      tx.set(ref, { uid, createdAt: admin.firestore.FieldValue.serverTimestamp() });
      tx.set(db.collection('users').doc(uid), { affiliateCode: code }, { merge: true });
      return true;
    });
    if (ok) return code;
  }
  throw new Error('no free code');
}

// AFFILIATE: a signed-in account's code and books.
// POST {action: 'me'} -> {code, link, customers, purchases, earned_cents, paid_cents, owed_cents, recent}
// POST {action: 'set_code', code} -> the same, under the new code (one change, while unused)
// POST {action: 'set_payout', payout} -> the same; payout is where the owner sends the money (Venmo / Zelle / Cash App)
exports.affiliate = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    if (req.method === 'GET' && req.query.health !== undefined) {
      // deploy check: can this deploy reach Stripe with its key? (says nothing else)
      try {
        await stripe.coupons.list({ limit: 1 });
        res.json({ stripe: true });
      } catch (err) {
        res.status(503).json({ stripe: false });
      }
      return;
    }
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }
    const decoded = await verifyAuthHeader(req);
    if (!decoded) {
      res.status(401).json({ error: 'Sign in required' });
      return;
    }
    try {
      const uid = decoded.uid;
      const userRef = db.collection('users').doc(uid);
      let u = (await userRef.get()).data() || {};
      let code = u.affiliateCode || await claimDefaultCode(uid, decoded.email);
      const action = String((req.body && req.body.action) || 'me');
      const earnQ = await db.collection('affiliate_earnings').where('affiliate_uid', '==', uid).get();
      const earnings = earnQ.docs.map(d => d.data());

      if (action === 'set_code') {
        const want = String(req.body.code || '').trim().toUpperCase();
        if (!CODE_RE.test(want)) return res.status(400).json({ error: 'Codes are 4 to 12 letters or numbers.' });
        if (u.affiliateCodeChanged) return res.status(400).json({ error: 'You’ve already changed your code once.' });
        if (earnings.length) return res.status(400).json({ error: 'Your code is already in use by a customer.' });
        const taken = await db.runTransaction(async (tx) => {
          const ref = db.collection('affiliate_codes').doc(want);
          const cur = await tx.get(ref);
          if (cur.exists && cur.data().uid !== uid) return true;
          tx.set(ref, { uid, createdAt: admin.firestore.FieldValue.serverTimestamp() });
          if (code !== want) tx.delete(db.collection('affiliate_codes').doc(code));
          tx.set(userRef, { affiliateCode: want, affiliateCodeChanged: true }, { merge: true });
          return false;
        });
        if (taken) return res.status(409).json({ error: 'That code is taken.' });
        code = want;
      }
      if (action === 'set_payout') {
        const handle = String(req.body.payout || '').trim().slice(0, 80);
        await userRef.set({ affiliatePayout: handle }, { merge: true });
        u = Object.assign({}, u, { affiliatePayout: handle });
      }

      const live = earnings.filter(e => e.status !== 'reversed');
      const payQ = await db.collection('affiliate_payouts').where('affiliate_uid', '==', uid).get();
      const earned = live.reduce((a, e) => a + Number(e.commission_cents || 0), 0);
      const paid = payQ.docs.reduce((a, d) => a + Number(d.data().amount_cents || 0), 0);
      const recent = live.sort((a, b) => (b.createdAt?.toMillis?.() || 0) - (a.createdAt?.toMillis?.() || 0)).slice(0, 12)
        .map(e => ({ at: e.createdAt?.toMillis?.() || 0, hours: e.access_hours, amount_cents: e.amount_cents, commission_cents: e.commission_cents }));
      res.set('Cache-Control', 'no-store');
      res.json({
        code, link: `https://morellosims.com/?ref=${code}`, changed: !!u.affiliateCodeChanged || action === 'set_code',
        payout: u.affiliatePayout || '',
        customers: new Set(live.map(e => e.buyer_uid)).size, purchases: live.length,
        earned_cents: earned, paid_cents: paid, owed_cents: Math.max(0, earned - paid), recent,
        discount_pct: REF_DISCOUNT_PCT, commission_pct: Math.round(REF_COMMISSION * 100)
      });
    } catch (err) {
      console.error('Affiliate error:', err);
      res.status(500).json({ error: 'Could not load your code' });
    }
  });
});

// TELEGRAM INVITE
// A paid member taps "Join the members channel" on the site. We check their
// access window in Firestore, then mint a one-person invite link that dies in
// an hour (or when their access does, whichever is first). The link's name
// carries the uid, so the channel bot can match the Telegram account that
// joins with it to this purchase and remove it when access ends.
// Secrets (set once): firebase functions:secrets:set TELEGRAM_BOT_TOKEN
//                     firebase functions:secrets:set TELEGRAM_PREMIUM_CHANNEL_ID
function hasActiveAccess(data) {
  if (!data) return false;
  if (data.tier === 'admin') return true;
  const exp = data.accessExpiresAt && data.accessExpiresAt.toMillis ? data.accessExpiresAt.toMillis() : 0;
  if (exp > Date.now()) return true;
  // legacy recurring subscriptions carry no expiry; the webhook flips them to free when they lapse
  return data.checkoutMode === 'subscription' && data.tier && data.tier !== 'free';
}

exports.telegramInvite = functions
  .runWith({ secrets: ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_PREMIUM_CHANNEL_ID'] })
  .https.onRequest((req, res) => {
    cors(req, res, async () => {
      if (req.method !== 'POST') {
        res.status(405).json({ error: 'Method not allowed' });
        return;
      }
      try {
        const authHeader = req.headers.authorization || '';
        if (!authHeader.startsWith('Bearer ')) {
          res.status(401).json({ error: 'Sign in first' });
          return;
        }
        const decoded = await admin.auth().verifyIdToken(authHeader.slice(7));
        const uid = decoded.uid;
        const snap = await db.collection('users').doc(uid).get();
        const data = snap.exists ? snap.data() : null;
        if (!hasActiveAccess(data)) {
          res.status(403).json({ error: 'No active pass' });
          return;
        }
        const token = process.env.TELEGRAM_BOT_TOKEN;
        const channel = process.env.TELEGRAM_PREMIUM_CHANNEL_ID;
        if (!token || !channel) {
          res.status(503).json({ error: 'Channel not open yet' });
          return;
        }
        const accessEnd = data.accessExpiresAt && data.accessExpiresAt.toMillis ? data.accessExpiresAt.toMillis() : Infinity;
        const expireSec = Math.floor(Math.min(Date.now() + 60 * 60 * 1000, accessEnd) / 1000);
        const tg = await fetch(`https://api.telegram.org/bot${token}/createChatInviteLink`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chat_id: channel, name: `u:${uid}`.slice(0, 32), member_limit: 1, expire_date: expireSec })
        }).then(r => r.json());
        if (!tg.ok) {
          console.error('createChatInviteLink failed:', tg.description);
          res.status(502).json({ error: 'Telegram did not issue a link' });
          return;
        }
        await db.collection('tg_invites').add({
          uid,
          link: tg.result.invite_link,
          expiresAt: admin.firestore.Timestamp.fromMillis(expireSec * 1000),
          createdAt: admin.firestore.FieldValue.serverTimestamp()
        });
        res.json({ link: tg.result.invite_link });
      } catch (err) {
        console.error('telegramInvite error:', err);
        res.status(500).json({ error: 'Could not create invite' });
      }
    });
  });

// ON USER CREATE - Check FnF whitelist
exports.onUserCreate = functions.auth.user().onCreate(async (user) => {
  const email = user.email;
  if (!email) return;

  // Check FnF whitelist
  let tier = 'free';
  try {
    const fnfDoc = await db.collection('fnf_whitelist').doc(email).get();
    if (fnfDoc.exists) {
      tier = 'fnf';
    }
  } catch (err) {
    console.error('FnF check error:', err);
  }

  // Admin check
  if (email === 'jaidanmorello@gmail.com') {
    tier = 'admin';
  }

  await db.collection('users').doc(user.uid).set({
    email: email,
    tier: tier,
    refCode: refCodeForUid(user.uid),
    referral_count: 0,
    createdAt: admin.firestore.FieldValue.serverTimestamp()
  });

  console.log(`Created user doc for ${email} with tier: ${tier}`);
});

// ESPN API PROXY
// Bypasses CORS for browser-based ESPN fantasy API calls
exports.espnProxy = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    try {
      const { leagueId, season, views, espnS2, swid } = req.query;

      if (!leagueId || !season) {
        res.status(400).json({ error: 'Missing required params: leagueId, season' });
        return;
      }

      // Build ESPN API URL
      let espnPath = `/apis/v3/games/flb/seasons/${encodeURIComponent(season)}/segments/0/leagues/${encodeURIComponent(leagueId)}`;
      const viewList = views ? views.split(',') : ['mRoster', 'mTeam'];
      const viewParams = viewList.map(v => `view=${encodeURIComponent(v)}`).join('&');
      espnPath += `?${viewParams}`;

      const headers = {
        'Accept': 'application/json',
        'User-Agent': 'MorellosimsDraftAssistant/1.0',
      };
      if (espnS2) {
        headers['Cookie'] = `espn_s2=${espnS2}${swid ? `; SWID=${swid}` : ''}`;
      }

      // Make server-side request to ESPN
      const espnData = await new Promise((resolve, reject) => {
        const options = {
          hostname: 'lm-api-reads.fantasy.espn.com',
          path: espnPath,
          method: 'GET',
          headers,
        };

        const request = https.request(options, (response) => {
          let body = '';
          response.on('data', chunk => { body += chunk; });
          response.on('end', () => {
            if (response.statusCode >= 400) {
              reject(new Error(`ESPN API returned ${response.statusCode}`));
            } else {
              try {
                resolve(JSON.parse(body));
              } catch (e) {
                reject(new Error('Invalid JSON from ESPN'));
              }
            }
          });
        });

        request.on('error', reject);
        request.setTimeout(15000, () => {
          request.destroy();
          reject(new Error('ESPN API timeout'));
        });
        request.end();
      });

      res.json(espnData);
    } catch (err) {
      console.error('ESPN proxy error:', err.message);
      res.status(502).json({ error: err.message });
    }
  });
});

// ══════════════════════════════════════════════════
// SHARED HELPERS (growth features)
// ══════════════════════════════════════════════════

// Deterministic short referral code from a uid (djb2-xor, base36, 7 chars)
function refCodeForUid(uid) {
  let h = 5381;
  for (let i = 0; i < uid.length; i++) {
    h = ((h * 33) ^ uid.charCodeAt(i)) >>> 0;
  }
  return h.toString(36).toUpperCase().padStart(7, '0').slice(0, 7);
}

// "YYYY-MM-DD" for the current calendar day in US Eastern time
function etDayString(date = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  }).format(date);
}

// The ET calendar day immediately before an ET "YYYY-MM-DD" string
function etDayBefore(dayString) {
  const [y, m, d] = dayString.split('-').map(Number);
  const prev = new Date(Date.UTC(y, m - 1, d - 1));
  const pad = (n) => String(n).padStart(2, '0');
  return `${prev.getUTCFullYear()}-${pad(prev.getUTCMonth() + 1)}-${pad(prev.getUTCDate())}`;
}

// Verify a Firebase ID token from the Authorization: Bearer header.
// Returns the decoded token or null.
async function verifyAuthHeader(req) {
  const header = req.get('authorization') || '';
  const match = header.match(/^Bearer (.+)$/i);
  if (!match) return null;
  try {
    return await admin.auth().verifyIdToken(match[1]);
  } catch (err) {
    console.warn('Auth token verification failed:', err.message);
    return null;
  }
}

// EMAIL CAPTURE
// POST { email, source } → stores in email_leads, deduped on lowercase email.
// Rewritten from /api/email-capture (firebase.json).
exports.emailCapture = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }

    try {
      const payload = req.body && typeof req.body === 'object' ? req.body : {};
      const clean = (value, maxLength = 400) => String(value || '').trim().slice(0, maxLength);

      // Honeypot — bots fill this, humans never see it
      if (clean(payload.website, 80)) {
        res.json({ ok: true });
        return;
      }

      const email = clean(payload.email, 200).toLowerCase();
      const source = clean(payload.source, 80) || 'unknown';

      if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) {
        res.status(400).json({ error: 'Invalid email' });
        return;
      }

      // Doc ID = email → natural dedupe. Only write on first sighting.
      const leadRef = db.collection('email_leads').doc(email);
      const existing = await leadRef.get();
      if (!existing.exists) {
        await leadRef.set({
          email: email,
          source: source,
          created: admin.firestore.FieldValue.serverTimestamp(),
          ua: clean(req.get('user-agent'), 260)
        });
      }

      res.set('Cache-Control', 'no-store');
      res.json({ ok: true, duplicate: existing.exists });
    } catch (err) {
      console.error('Email capture error:', err);
      res.status(500).json({ error: 'Email could not be saved' });
    }
  });
});

// RECORD TAIL / FADE VOTE
// POST { pickId, side: 'tail'|'fade' } with Authorization: Bearer <idToken>.
// One vote per user per pick; clicking the same side again removes the vote,
// clicking the other side switches it. Aggregates live in tail_counts/{pickId}.
exports.recordTail = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }

    const decoded = await verifyAuthHeader(req);
    if (!decoded) {
      res.status(401).json({ error: 'Sign in required' });
      return;
    }

    try {
      const payload = req.body && typeof req.body === 'object' ? req.body : {};
      const pickId = String(payload.pickId || '').trim();
      const side = String(payload.side || '').trim();

      if (!/^[A-Za-z0-9_-]{3,120}$/.test(pickId)) {
        res.status(400).json({ error: 'Invalid pickId' });
        return;
      }
      if (side !== 'tail' && side !== 'fade') {
        res.status(400).json({ error: 'side must be tail or fade' });
        return;
      }

      const uid = decoded.uid;
      const voteRef = db.collection('user_tails').doc(uid).collection('picks').doc(pickId);
      const countRef = db.collection('tail_counts').doc(pickId);

      const result = await db.runTransaction(async (tx) => {
        const [voteDoc, countDoc] = await Promise.all([tx.get(voteRef), tx.get(countRef)]);
        const prevSide = voteDoc.exists ? voteDoc.data().side : null;
        const counts = countDoc.exists ? countDoc.data() : {};
        let tail = Number(counts.tail || 0);
        let fade = Number(counts.fade || 0);
        let newSide;

        if (prevSide === side) {
          // Toggle off
          tx.delete(voteRef);
          if (side === 'tail') tail = Math.max(0, tail - 1);
          else fade = Math.max(0, fade - 1);
          newSide = null;
        } else {
          tx.set(voteRef, {
            pickId: pickId,
            side: side,
            ts: admin.firestore.FieldValue.serverTimestamp()
          });
          if (prevSide === 'tail') tail = Math.max(0, tail - 1);
          if (prevSide === 'fade') fade = Math.max(0, fade - 1);
          if (side === 'tail') tail += 1;
          else fade += 1;
          newSide = side;
        }

        tx.set(countRef, {
          tail: tail,
          fade: fade,
          updatedAt: admin.firestore.FieldValue.serverTimestamp()
        }, { merge: true });

        return { side: newSide, tail: tail, fade: fade };
      });

      res.set('Cache-Control', 'no-store');
      res.json({ ok: true, side: result.side, counts: { tail: result.tail, fade: result.fade } });
    } catch (err) {
      console.error('Record tail error:', err);
      res.status(500).json({ error: 'Vote could not be saved' });
    }
  });
});

// DAILY CHECK-IN + STREAK (+ referral attribution)
// POST { refCode? } with Authorization: Bearer <idToken>.
// Upserts user_streaks/{uid} {last_day, streak} in ET: increments if last_day
// was yesterday, resets if older, no-ops if today. Also backfills the user's
// refCode and, on first check-in with a stored ?ref= code, sets referred_by
// and increments the referrer's referral_count (reward stays manual for now).
exports.checkIn = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }

    const decoded = await verifyAuthHeader(req);
    if (!decoded) {
      res.status(401).json({ error: 'Sign in required' });
      return;
    }

    try {
      const uid = decoded.uid;
      const today = etDayString();
      const yesterday = etDayBefore(today);

      // 1) Streak upsert (transactional so double-loads don't double-count)
      const streakRef = db.collection('user_streaks').doc(uid);
      const streak = await db.runTransaction(async (tx) => {
        const doc = await tx.get(streakRef);
        const data = doc.exists ? doc.data() : {};
        let value = Number(data.streak || 0);

        if (data.last_day === today) {
          return value || 1; // already checked in today
        }
        value = data.last_day === yesterday ? value + 1 : 1;
        tx.set(streakRef, {
          last_day: today,
          streak: value,
          updatedAt: admin.firestore.FieldValue.serverTimestamp()
        }, { merge: true });
        return value;
      });

      // 2) Ensure the user doc has a refCode (backfill for pre-existing users)
      const userRef = db.collection('users').doc(uid);
      const userDoc = await userRef.get();
      const userData = userDoc.exists ? userDoc.data() : {};
      const ownCode = userData.refCode || refCodeForUid(uid);
      if (!userData.refCode) {
        await userRef.set({ refCode: ownCode }, { merge: true });
      }

      // 3) Referral attribution — once, only if not already attributed
      let referralApplied = false;
      const incomingCode = String((req.body && req.body.refCode) || '').trim().toUpperCase();
      if (incomingCode && /^[A-Z0-9]{4,12}$/.test(incomingCode) &&
          !userData.referred_by && incomingCode !== ownCode) {
        try {
          // Only attribute recently created accounts (no retroactive claims)
          const userRecord = await admin.auth().getUser(uid);
          const ageMs = Date.now() - Date.parse(userRecord.metadata.creationTime);
          if (ageMs < 30 * 24 * 60 * 60 * 1000) {
            const refQuery = await db.collection('users')
              .where('refCode', '==', incomingCode).limit(1).get();
            if (!refQuery.empty && refQuery.docs[0].id !== uid) {
              const referrerRef = refQuery.docs[0].ref;
              const batch = db.batch();
              batch.set(userRef, {
                referred_by: incomingCode,
                referred_by_uid: referrerRef.id
              }, { merge: true });
              batch.set(referrerRef, {
                referral_count: admin.firestore.FieldValue.increment(1)
              }, { merge: true });
              await batch.commit();
              referralApplied = true;
            }
          }
        } catch (err) {
          console.error('Referral attribution error:', err);
        }
      }

      res.set('Cache-Control', 'no-store');
      res.json({
        ok: true,
        streak: streak,
        last_day: today,
        refCode: ownCode,
        referralCount: Number(userData.referral_count || 0),
        referralApplied: referralApplied
      });
    } catch (err) {
      console.error('Check-in error:', err);
      res.status(500).json({ error: 'Check-in failed' });
    }
  });
});

// DOG CLUB LEAD CAPTURE
// Stores founding member applications from /dogclub/
exports.dogClubLead = functions.https.onRequest((req, res) => {
  cors(req, res, async () => {
    if (req.method !== 'POST') {
      res.status(405).json({ error: 'Method not allowed' });
      return;
    }

    try {
      const payload = req.body && typeof req.body === 'object' ? req.body : {};
      const clean = (value, maxLength = 400) => String(value || '').trim().slice(0, maxLength);
      const cleanList = (value) => Array.isArray(value)
        ? value.map(item => clean(item, 80)).filter(Boolean).slice(0, 8)
        : [];

      if (clean(payload.website, 80)) {
        res.json({ ok: true });
        return;
      }

      const ownerName = clean(payload.ownerName, 120);
      const contact = clean(payload.contact, 160);
      const dogName = clean(payload.dogName, 120);

      if (!ownerName || !contact || !dogName) {
        res.status(400).json({ error: 'Missing required fields' });
        return;
      }

      await db.collection('dog_club_leads').add({
        ownerName,
        contact,
        dogName,
        weeklyWindow: clean(payload.weeklyWindow, 160),
        shirtSize: clean(payload.shirtSize, 40),
        neighborhood: clean(payload.neighborhood, 120),
        dogSize: clean(payload.dogSize, 80),
        temperament: clean(payload.temperament, 120),
        interests: cleanList(payload.interests),
        notes: clean(payload.notes, 1200),
        source: clean(payload.source, 80) || 'dogclub_landing',
        userAgent: clean(req.get('user-agent'), 260),
        ipHashSource: clean(req.ip || req.get('x-forwarded-for'), 160),
        status: 'new',
        createdAt: admin.firestore.FieldValue.serverTimestamp()
      });

      res.set('Cache-Control', 'no-store');
      res.json({ ok: true });
    } catch (err) {
      console.error('Dog club lead error:', err);
      res.status(500).json({ error: 'Lead could not be saved' });
    }
  });
});
