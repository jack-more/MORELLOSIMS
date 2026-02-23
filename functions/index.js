const functions = require('firebase-functions');
const admin = require('firebase-admin');
const Stripe = require('stripe');
const cors = require('cors')({ origin: true });

admin.initializeApp();
const db = admin.firestore();

// TODO: Set these via `firebase functions:config:set stripe.secret="sk_live_xxx" stripe.webhook_secret="whsec_xxx"`
// Or use Firebase environment config
const stripe = new Stripe(functions.config().stripe?.secret || process.env.STRIPE_SECRET_KEY);
const WEBHOOK_SECRET = functions.config().stripe?.webhook_secret || process.env.STRIPE_WEBHOOK_SECRET;

// ── Price ID → Tier mapping ──
const PRICE_TO_TIER = {
  'price_1T3rqNA9KGX7mrlmCQi4QcnU': 'pickmaker_nba',
  'price_1T3rqqA9KGX7mrlmHncjyPlp': 'pickmaker_mlb',
  'price_1T3rvjA9KGX7mrlmxJI5V00r': 'pickmaker_dual',
  'price_1T3s0qA9KGX7mrlmA8KljtHG': 'all_access'
};

// ══════════════════════════════════════════════════
// CREATE CHECKOUT SESSION
// Called from morello-auth.js when user clicks Subscribe/Purchase
// ══════════════════════════════════════════════════
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

      // Determine if this is a one-time or subscription
      const tier = PRICE_TO_TIER[priceId];
      const isOneTime = tier === 'all_access';

      const sessionParams = {
        customer: customerId,
        payment_method_types: ['card'],
        line_items: [{ price: priceId, quantity: 1 }],
        mode: isOneTime ? 'payment' : 'subscription',
        success_url: successUrl || 'https://morellosims.com/?checkout=success',
        cancel_url: cancelUrl || 'https://morellosims.com/?checkout=cancel',
        metadata: {
          firebaseUid: uid,
          tier: tier
        }
      };

      // For subscriptions, add subscription metadata too
      if (!isOneTime) {
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

// ══════════════════════════════════════════════════
// STRIPE WEBHOOK
// Handles: checkout.session.completed, customer.subscription.deleted
// ══════════════════════════════════════════════════
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

      if (uid && tier) {
        await db.collection('users').doc(uid).set(
          {
            tier: tier,
            stripeCustomerId: session.customer,
            updatedAt: admin.firestore.FieldValue.serverTimestamp()
          },
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

// ══════════════════════════════════════════════════
// ON USER CREATE — Check FnF whitelist
// ══════════════════════════════════════════════════
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
    createdAt: admin.firestore.FieldValue.serverTimestamp()
  });

  console.log(`Created user doc for ${email} with tier: ${tier}`);
});
