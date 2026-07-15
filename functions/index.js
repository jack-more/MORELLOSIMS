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

      if (!priceId || !uid || !email) {
        res.status(400).json({ error: 'Missing required fields: priceId, uid, email' });
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

      const session = await stripe.checkout.sessions.create(sessionParams);
      res.json({ url: session.url });
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
