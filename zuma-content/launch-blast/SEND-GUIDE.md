# ZUMA launch blast: how to send it

Theme: **The new era of research is here.** Offer: launch pricing (already 20% under list on the site) plus **10% off the first order with code LAUNCH10**.

## What is in this folder

| File | What it is |
|---|---|
| `email/launch-email.html` | The email to send. Images load from `https://zumatides.com/email/launch/`. |
| `email/launch-email-preview.html` | The same email with local images, for checking in a browser. |
| `email/launch-email.txt` | Plain-text part (send it alongside the HTML). |
| `email/preview-desktop.png`, `email/preview-phone.png` | Screenshots. |
| `email/img/` | The images the email uses (JPG/PNG, because Outlook does not show WebP). |
| `email/build_email.py` | Rebuilds all three email files. Edit copy, prices or the code here, then run it. |
| `sms/launch-texts.txt` | Launch text, short version, and a 48-hour reminder, each one SMS segment. |

## Subject lines (pick one, A/B test two if the tool allows)

1. The new era of research is here.
2. ZUMA is open.
3. Twelve compounds. Every lot tested. Now open.

Preview text (already in the email): *Twelve research compounds. Every lot tested. Launch pricing is live, and your first order takes another 10% off.*

## Before anything goes out (in this order)

1. **Store is live.** Netlify env set per GO-LIVE.md, a $1 test order goes through end to end. Do not blast a store that cannot take an order.
2. **Lot reports are up.** The email and the box both say every lot is tested and the report is published. Send only once order #1's reports are on zumatides.com/lots, or change that line in `build_email.py`.
3. **KLOW is on the site** (the site change in progress). Then set KLOW's page slug in `build_email.py` (it links to the shop until then) and rerun it. Decide KLOW's price: the email shows $139, the old GHK+BT 70 mg price.
4. **Make LAUNCH10 work.** The store gives 10% off a first order only through a referral code. The simplest way, with no code change: create a ZUMA "house" account whose referral code is `LAUNCH10`. Every first order using it then gets 10% off. Two side effects to accept: referral credit for those orders goes to the house account (ZUMA paying itself, harmless), and those customers are tied to the house referrer for 12 months, so a friend cannot claim them later. If that matters, ask for a proper promo-code feature instead.
5. **Host the images.** Copy `email/img/*` to `site/email/launch/` in the zuma repo and deploy (today `https://zumatides.com/email/launch/collection.jpg` returns 404).
6. **Fill in `{{ADDRESS}}`** in the email footer with a real postal address (US law, CAN-SPAM, requires one in marketing email; a PO box or a mailbox service works if you do not want a home address).

## Email: sending with Resend (already wired up for the store's order emails)

1. Resend → Domains: zumatides.com verified (SPF + DKIM), and add a DMARC record. Send from something like `hello@zumatides.com`.
2. Resend → Audiences: create "Launch list", import your list as CSV (email, first name). Only people who agreed to hear from ZUMA.
3. Resend → Broadcasts → New: paste `launch-email.html` (HTML) and `launch-email.txt` (text), pick the subject, select the audience. `{{{RESEND_UNSUBSCRIBE_URL}}}` is already in the footer; Resend fills it in.
4. Send a test to yourself first: Gmail on a phone, Apple Mail, and Outlook if you can. Click every link.
5. If the list is more than a few hundred and the domain is new, send to about 200 first, wait an hour, then the rest. New domains that blast thousands at once land in spam.

## Texts: what it really takes

- **Consent is the law here.** Marketing texts need prior written consent to receive marketing texts from ZUMA (US: TCPA). A phone number collected for something else does not count, and fines run per text. Only text people who opted in to texts.
- **A sender number takes time.** With Twilio (or Postscript, SimpleTexting, etc.) you need either a toll-free number with toll-free verification or a 10DLC registration. Expect several days to a few weeks for approval.
- **Carrier risk.** Carriers filter and can block messages they read as drugs or pharma. The texts carry no compound names for that reason, and they link to our own domain (no bit.ly, which carriers distrust). Even so, research-compound senders do get rejected in verification; describe the business plainly ("laboratory research supplies, research-use only") when registering.
- Every marketing text needs the brand name and "Reply STOP to opt out" (both versions in `launch-texts.txt` that need it have it).
- Send texts between 10am and 7pm in the recipient's time zone.

## Suggested timing

- Day 0, 10am Pacific: email + TEXT 1.
- Day 2: TEXT 2 to people who have not ordered. Optionally a short resend of the email to non-openers with subject 2.
