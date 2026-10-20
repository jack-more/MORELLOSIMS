# White-label clinician networks and 503A compounding pharmacies for a US cash-pay telehealth brand (as of Oct 20, 2026)

Confidence legend used below: **[P]** = primary (vendor's own page about itself, FDA, regulator); **[S]** = secondary (news, law firm, directory); **[LC]** = low confidence (a vendor writing about a competitor, an affiliate or SEO blog, or a search-engine summary I could not open). Almost every competitor figure in this space comes from competitor blogs written by Cuvo, FUSE, MyOrbitHealth, Karpa or Rimo. Read them as leads, not quotes.

---

## Table 1 – Clinician networks (what each actually supports)

"NS" means not stated in any source I could reach. Blank cells are gaps, not "no".

| Network | Setup fee | Monthly fee | Per-consult | Revenue share | Sync / async | 50-state | API / headless with own storefront | Bring-your-own pharmacy | LegitScript help | Categories (confirmed only) |
|---|---|---|---|---|---|---|---|---|---|---|
| **Qualiphy** | NS | NS | $27.99/exam [LC, Cuvo]; $28.99 per completed GLP-1 exam, Rx billed separately [S, Aesthetic Record help] | NS | NS | 48 states + DC (Qualiphy's own description, via Prospeo) [S] | API keys + no-code "Quidget" embeddable exam widget; no endpoint reference found [S/LC] | NS | NS | Med-spa "good faith exams", GLP-1 exams. Peptides and TRT not shown |
| **Karpa Health** | NS | "From $297" (Capterra listing) [S]; FUSE says "$0 per patient" claimed [LC] | NS | NS | NS | 50-state licensed network, 24-hr consult review (Karpa press release / Capterra) [S] | Turnkey: provider network, pharmacy, patient software, payments [P press release] | Fulfillment through Karpa's 503A partners (G2 reviewer); BYO not confirmed [S] | Holds LegitScript certification per FUSE [LC]; partners are LegitScript-certified per Capterra [S] | GLP-1, peptides, hormones (press-release headline) [P] |
| **FUSE Health** | DIY $0; Growth $5,600; Partner $30,000 onboarding | DIY $499; Growth $699; Partner $3,000 (from month 13) | None listed | 3% (DIY) / 2% "merchant service fee" on sales [P-ish, FUSE blog] | NS | All 50 | API/SDK only on Partner ($3,000/mo) plan [LC, Cuvo]; FUSE says API + AI-connector pages | Optional add-on on Partner plan only | Says it is certified | 70 visit types / 11 categories: GLP-1, hormones/TRT, sexual health, hair, skin, sleep, longevity, peptides (self-reported) |
| **Cuvo** | $9,800 (Launch) / $15,000 (Grow) | $997 / $2,500; Enterprise custom | $25 per completed consult | None | Event/webhook + polling | 50 + DC, PR, Guam, territories | API, 32 webhook events, MCP, OpenAPI 3.1 sandbox **only on Grow ($2,500/mo)**; Launch = hosted | Uses "licensed partner pharmacies"; BYO NS | LegitScript listed in stack | GLP-1, TRT/hormones, women's health, peptides (self-reported) |
| **MD Integrations (MDI)** | NS | NS | Custom-quoted [LC] | NS | Async visits + Rx routing [LC] | NS | API-first clinician network; you build the front end [LC] | NS | LegitScript "listed" per FUSE [LC] | No verified category list |
| **Beluga Health** | One-time integration fee, "fully applied to future visit volume" (a prepayment); amount NS | One flat platform fee, not tied to seats or visits; amount NS | Flat per visit, volume-tiered; async and sync priced separately; amounts given on scoping call | **None** ("We don't take a cut") | Async: hair loss, ED, derm. Sync: TRT, HRT, other | 50 + DC [LC Cuvo]; own page: "availability varies by state" | API (docs on request) **or** Beluga-hosted checkout on your subdomain | **Yes**, no extra fee; via Surescripts or a partner API. Beluga partner pharmacies add a disclosed coordination fee | LegitScript-certified badge in footer | TRT, HRT, hair, ED, derm named; 70+ visit types; prescribes controlled substances per Cuvo [LC] |
| **OpenLoop** | $9,000 in one May-2026 proposal [LC] | $1,500/mo from the first patient in that proposal [LC] | NS | Brand **keeps** 42–59% of patient revenue in that proposal [LC] | NS | 50-state PC network | API-first, EHR-ready, plus hosted "Launchpad" storefront; no public API docs found [LC] | Has pharmacy/lab network; BYO NS | Certified per FUSE [LC] | 35+ specialties; GLP-1 programs; insurance/RCM is a core service |
| **Telegra (TelegraMD)** | $5,000 (Plus) / $10,000 (Pro) onboarding | $2,999 (Plus) / $5,999 (Pro), as of Sept 30, 2026 | Varies by visit type, not published | NS | Signed v2 webhooks | NS | Public docs; credentials issued at onboarding; no SDK | NS | NS | NS |
| **Bask Health** | NS | $499 or $3,500 (named only in a blog post) [LC] | NS | Transaction fees; built-in processing, not BYO processor [LC] | NS | NS | No-code builder [LC] | Has 503A/503B pharmacy links; BYO NS | NS | NS. Read the export and cancellation terms [LC] |
| **Rimo Health** | NS | From $2,500/mo (as of Oct 3, 2026) [LC] | NS | None claimed; **brand brings its own Stripe** [LC] | NS | 50 states [LC] | **No partner-facing API** documented as of Oct 2026; the brand runs its clinic in Rimo's dashboard [LC] | 10+ pre-integrated pharmacies [LC] | Claims LegitScript clearance in 7–14 days [LC] | NS |
| **CareValidate** | Implementation fee (NS) | Pro $2,500 (one Cuvo section says $2,000) / Enterprise $5,000 [LC, conflicting] | Per-order fees | 3.7% processing [LC] | Webhooks (unsigned timestamps) | 50 | Hosted white-label + Postman API (20 requests) | Has 503A/503B relationships; BYO NS | LegitScript customer spotlight | Weight, men's health, women's health, derm |
| **Wheel** (other) | Custom | Custom | Custom | NS | NS | 50 + DC + PR | White-label or API-first (Horizon); its terms let it change or kill the API at any time [LC] | Amazon Pharmacy integration | NS | 70+ care programs |
| **SteadyMD** (other) | Per engagement | — | — | NS | NS | 50 | API-first, OpenAPI 3.0.3 | Pharmacy left to the client [LC] | NS | NS |
| **MyOrbitHealth** (other) | Scoped | Flat platform fee, scoped | NS | None; 0% medication markup (self-claim) | NS | 50, 2,400+ providers | REST, webhooks, React SDK, or hosted clinic | Routes through OrbitRx (LegitScript network) | Certified | GLP-1, HRT, TRT, peptides, hair/skin, longevity, EPCS for controlled substances (self-claim) |

Sources for Table 1: Cuvo networks roundup (published Sep 2, updated Oct 13, 2026) https://cuvo.co/blog/best-telehealth-provider-networks [vendor, LC for competitors]; Cuvo API test (checked Oct 1, 2026) https://cuvo.co/blog/white-label-telehealth-api-platforms-tested [LC]; FUSE roundup (Sep–Oct 2026) https://www.fusehealth.com/blogs/best-white-label-telehealth-platform [LC for competitors]; MyOrbitHealth comparison (Sep 19, 2026) https://myorbithealth.com/blog/beluga-vs-openloop-vs-myorbit [LC]; Beluga pricing page https://belugahealth.com/pricing [P]; Aesthetic Record Qualiphy help https://learn.aestheticrecord.com/en/articles/10199016-create-an-glp-1-exam-with-a-prescription-via-qualiphy-ios [S]; Karpa on Capterra https://www.capterra.com/p/10049354/Karpa-Health/ [S]; Karpa press release https://www.accessnewswire.com/newsroom/en/healthcare-and-pharmaceutical/karpa-health-launches-turnkey-nationwide-telehealth-platform-as-glp-1-1185822 [P]; Rimo roundup https://rimo.co/blog/best-white-label-telehealth-2026 [LC]; Bask profile https://www.embedcare.com/compare/bask [LC].

---

## Table 2 – Compounding pharmacies

| Pharmacy | 503A / 503B | HQ | States | Catalog highlights | Works with telehealth | API / EHR | FDA / legal record | Published wholesale price |
|---|---|---|---|---|---|---|---|---|
| **Empower** | Both (503A + 503B) [P] | Houston, TX | Many; multi-state nonresident permits [S, TrueEval] | GLP-1 combos (sema/B12, tirz/niacinamide, cited by FDA), sermorelin injection + ODT, NAD+ injection, hormones, men's health [P] | Yes; FDA letter framed around telehealth menus [S] | **Yes. Public developer platform/API** to "programmatically prescribe, compound, and fulfill"; LifeFile login for 503A ordering [P] | 483 (May 2024) [S]; **WL #700964, Apr 2, 2025** [P, FDA]; **WL #738238, Sep 18, 2026** (Nov 2025 inspection): GLP-1 combos called essential copies made in "pretextual" volumes, plus aseptic and data-integrity findings [P, FDA; content via law-firm summaries]; Lilly suit (Jul 2025) [S] | No. Quote by form only [P] |
| **Belmar Pharma Solutions** | Both (6 × 503A, 2 × 503B) [S] | Colorado | Claims all 50 [S] | Women's hormones, men's health, longevity, wellness [S] | Not stated | NS | "No recent action" per TrueEval; another guide cites a Mar 2023 WL to a Florida affiliate, **unconfirmed / conflicting** [LC] | NS |
| **Olympia** | Both [S] (sister facility Wesley opened May 2025) | Orlando, FL | Many [S] | GLP-1 (now **liraglutide**; **dropped sema/tirz** after shortage ended), peptides, weight, hormones [S] | Yes (broad) | NS | 483s 2013–2025, no WL found; May 2024 483 for semi-annual reporting failure [S] | NS |
| **Strive** | 503A | Gilbert, AZ | Claims 50 [S]; PCAB-accredited [LC] | GLP-1, weight, wellness, hormones | Supplied Hims & Hers GLP-1 until Feb 2025 [S] | NS | AZ Board inspection (Sep 2025) cited continued single-ingredient GLP-1 compounding; Lilly suit (Apr 2025); 2022 WL reportedly closed May 2026 [S/LC] | NS |
| **Hallandale** | 503A | Florida | Many [S] | GLP-1, general compounding | **Yes**, e.g. Zappy Health and other platforms [S] | NS | WL Mar 2020 → closeout May 2022; Jun 2025 483 (2 sterile observations: ISO-5 wipes, smoke studies) [LC, review site citing FDA] | NS |
| **Tailor Made Compounding** | 503A | Kentucky | Unverified | Hormones, peptides, anti-aging | **Owned by Noom** (acquired 2022) [S] | NS | **Pleaded guilty** federally to distributing unapproved new drugs; forfeited $1.78M [S] | NS |
| **ReviveRX** | 503A | Texas | Unverified | Hormones, weight, **peptides**, wellness, sexual health | NS | NS | **Class I recall (Apr 2024)**: tirzepatide vials actually held testosterone cypionate [S] | NS |
| **Wells Pharmacy Network** | Both [S] | Florida | 49 states + PR (self-claim) [S] | Hormone pellets, anti-aging, weight, sexual wellness | Not a main GLP-1 telehealth supplier [S] | NS | None found. **Do not confuse with Wells Pharma of Houston (503B)**: WL Nov 7, 2025 for sterility assurance, after a Mar 2025 483 [P, FDA] | NS |
| **Red Rock Pharmacy** | 503A, closed-door | Utah | Many [S] | GLP-1 (tirzepatide with glycine), USP 795/797/800 | Ships nationwide for telehealth [S] | NS | No recent action [S] | NS |
| **Partell** | — | — | — | — | — | — | **No reliable data found** | — |
| **AnazaoHealth (Fagron)** (other) | Both | Florida | Many | Hormones, weight, IV, sexual wellness, aesthetics | Multi-specialty telehealth supplier [S] | NS | No recent action | NS |
| **Contigo (Eden)** / **Precision Compounding** (other) | 503A | — | Unverified | GLP-1 | Vertically tied to telehealth brands (Contigo bought by Eden, Aug 2025; Precision includes a COA with each Rx) [S] | NS | Contigo on TrueEval "watch list" | NS |
| **University Compounding** (other) | 503A | California | — | Hormones, urology, derm | NS | NS | Acquired by Fagron Jan 2026 [S] | NS |

Sources for Table 2: TrueEval pharmacy map (accessed Oct 18, 2026) https://trueeval.com/compounding-pharmacy-map [S, directory with its own risk ratings]; Empower developer platform https://www.empowerpharmacy.com/api/ [P]; Empower pricing page https://www.empowerpharmacy.com/compound-medication/pricing-advantage/ [P]; Empower categories https://www.empowerpharmacy.com/compound-medication-categories/ [P]; FDA WL 738238 (Sep 18, 2026) https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/empower-clinic-services-llc-dba-empower-pharmacy-738238-09182026 [P; the page returned HTTP 401 to my fetcher, so its content comes from https://www.bipc.com/fda-warning-letter-to-empower-pharmacy-and-what-it-means-for-503a-compounding-pharmacies and https://mflrc.com/article/fda-warning-letter-glp1-compounding-aseptic-data-integrity-2026]; FDA WL 700964 (Apr 2, 2025) https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/empower-clinic-services-llc-dba-empower-pharmacy-700964-04022025 [P, not opened]; Wells Pharma of Houston WL https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/wells-pharma-houston-llc-713015-11072025 [P, from search listing]; Hallandale review https://www.ozarihealth.com/blog/hallandale-pharmacy-reviews [LC].

---

## Which network gives the most catalog breadth for the lowest fixed cost?

### Takeaway
On published numbers, the cheapest entry points are Karpa (from $297/mo), FUSE DIY ($0 setup, $499/mo plus 3% of sales) and Qualiphy (pay per exam, about $28, no published monthly fee). FUSE and Karpa are the only low-cost options that **claim** GLP-1 plus peptides plus hormones. Beluga is the strongest primary-sourced option for a brand with its own storefront and pharmacy (API, bring-your-own pharmacy at no fee, no revenue share, sync TRT/HRT), but its prices are hidden until the scoping call.

### Cited Findings
- Karpa lists a starting price of US$297 [S]. It sells a turnkey bundle: provider network, pharmacy fulfillment, patient software, payments. Its launch release is pitched at GLP-1, peptide and hormone demand — [Capterra](https://www.capterra.com/p/10049354/Karpa-Health/); [Karpa press release](https://www.accessnewswire.com/newsroom/en/healthcare-and-pharmaceutical/karpa-health-launches-turnkey-nationwide-telehealth-platform-as-glp-1-1185822)
- FUSE DIY: $0 build, then $499/mo once live, plus a 3% merchant fee. Growth: $5,600 + $699/mo + 2%. Partner: $30k onboarding, $3,000/mo from month 13, + 2%. No per-visit fees listed. It claims 70 visit types including GLP-1, TRT, hair, skin, sleep, longevity and peptides — [FUSE (self-published)](https://www.fusehealth.com/blogs/best-white-label-telehealth-platform)
- Cuvo says FUSE API/SDK access exists **only** on the $3,000/mo plan — [Cuvo API test (LC)](https://cuvo.co/blog/white-label-telehealth-api-platforms-tested)
- Qualiphy: $28.99 per completed GLP-1 exam, prescriptions billed separately — [Aesthetic Record help](https://learn.aestheticrecord.com/en/articles/10199016-create-an-glp-1-exam-with-a-prescription-via-qualiphy-ios). Cuvo gives $27.99 per exam and describes Qualiphy as med-spa-focused, covering 48 states + DC — [Cuvo (LC)](https://cuvo.co/blog/turnkey-telehealth-clinical-operations). **Conflict:** $27.99 vs $28.99. The difference may be exam type or date.
- Cuvo: $9,800 + $997/mo + $25/consult (Launch, hosted only). API/MCP needs Grow at $15,000 + $2,500/mo. No revenue share — [Cuvo](https://cuvo.co/blog/best-telehealth-provider-networks)
- Beluga: an integration fee credited against future visits, one flat monthly platform fee, volume-tiered per-visit fees (async hair/ED/derm vs sync TRT/HRT), no revenue share, BYO pharmacy at no extra charge, API or hosted checkout on your subdomain, nothing billed for visits until live — [Beluga pricing](https://belugahealth.com/pricing); [Beluga search summary of pharmacy-labs page](https://belugahealth.com/pharmacy-labs)
- Telegra publishes Plus at $2,999/mo + $5,000 onboarding and Pro at $5,999/mo + $10,000 (as of Sep 30, 2026); per-consult fees vary and are not published — [Cuvo API test (LC)](https://cuvo.co/blog/white-label-telehealth-api-platforms-tested). A FUSE summary gives the same figures — [FUSE (LC)](https://www.fusehealth.com/blogs/best-white-label-telehealth-platform)
- OpenLoop (one May-2026 proposal reviewed by a competitor): $9,000 setup, $1,500/mo from the first patient, 12-month term, brand retains 42–59% of patient revenue, patient payments run through OpenLoop's merchant account — [Cuvo (LC)](https://cuvo.co/blog/white-label-telehealth-api-platforms-tested); proposal figures came from a search summary of Cuvo pages that I could not open directly
- Rimo: from $2,500/mo, brand brings its own Stripe, no partner API — [Cuvo (LC)](https://cuvo.co/blog/white-label-telehealth-api-platforms-tested); [Rimo-authored roundup (LC)](https://rimo.co/blog/best-white-label-telehealth-2026)
- CareValidate: Pro $2,500/mo (one section of the same article says $2,000) and Enterprise $5,000/mo, plus implementation and per-order fees and 3.7% processing — [Cuvo (LC)](https://cuvo.co/blog/best-telehealth-provider-networks)

### Inferences
- Lowest fixed cost: Qualiphy (pay per exam, but med-spa scope, 48 states, thin API) < Karpa (~$297/mo) < FUSE DIY ($499/mo + 3% of GMV). Under FUSE's percentage fee, fixed cost turns into variable cost: at $100k/mo in sales, 3% is $3,000/mo.
- For a brand with **its own storefront and its own pharmacy**, Beluga (API + BYO pharmacy + no revenue share) and MDI (API-first) fit that architecture best. Turnkey bundles (Karpa, FUSE DIY, Bask, Rimo) usually tie you to their pharmacy, processor or front end.
- "Peptides" in vendor catalogs almost certainly means peptides that can lawfully be compounded today (sermorelin, NAD+, GHK-Cu topicals, and so on), not BPC-157 (see the pharmacy section). Category claims are self-reported.

### Gaps
- No verified per-consult price for MDI, Beluga, OpenLoop, Telegra, Bask, Karpa or CareValidate.
- Karpa's $297 tier: no source says what it includes (clinician fees? pharmacy margin?).
- Sync vs async and controlled-substance (TRT/DEA) support are unconfirmed for most vendors. Only Beluga (sync TRT/HRT) and MyOrbitHealth (EPCS, self-claim) address them. I found no source on how any vendor will handle the DEA special telemedicine registration.
- The Telegra pricing page (telegramd.com/pricing) returned no content to my fetcher.

---

## Which pharmacies carry the broadest peptide and wellness catalog in 2026, and what did they drop after FDA actions?

### Takeaway
Empower (503A + 503B, public API, sermorelin, NAD+, GLP-1 combos) is the broadest pharmacy that is also integration-ready. Belmar, Olympia, AnazaoHealth, ReviveRX and Tailor Made cover hormones and wellness. The main "drop" is compounded semaglutide and tirzepatide after the shortage ended (Olympia moved to liraglutide). BPC-157 left Category 2 in April 2026 but still **cannot lawfully be compounded** until FDA adds it to the 503A bulks list through rulemaking.

### Cited Findings
- Empower lists semaglutide/cyanocobalamin, sermorelin acetate (injection and ODT) and NAD+ injection. It runs a developer platform for programmatic prescribe, compound and fulfill. Pricing requires a form request — [Empower API](https://www.empowerpharmacy.com/api/); [Empower categories](https://www.empowerpharmacy.com/compound-medication-categories/); [Empower pricing](https://www.empowerpharmacy.com/compound-medication/pricing-advantage/)
- FDA warning letter to Empower dated Sep 18, 2026 (Nov 3–14, 2025 inspection, Houston 503A): it says tirzepatide/niacinamide and semaglutide/cyanocobalamin are essential copies made in "pretextual" volumes, and it cites aseptic and media-fill data-integrity problems — [FDA WL 738238](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/empower-clinic-services-llc-dba-empower-pharmacy-738238-09182026) (401 to my fetcher; content from [Buchanan Ingersoll](https://www.bipc.com/fda-warning-letter-to-empower-pharmacy-and-what-it-means-for-503a-compounding-pharmacies) and [MFLRC](https://mflrc.com/article/fda-warning-letter-glp1-compounding-aseptic-data-integrity-2026)). One outlet misdates it to 2025 — [Newsy Today](https://www.newsy-today.com/fda-warns-empower-pharmacy-over-unauthorized-weight-loss-drugs/)
- Earlier Empower warning letter Apr 2, 2025 (WL 700964) — [FDA](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/empower-clinic-services-llc-dba-empower-pharmacy-700964-04022025)
- Olympia "currently compounds liraglutide; dropped sema/tirz" — [TrueEval](https://trueeval.com/compounding-pharmacy-map)
- BPC-157 and 11 other peptides were removed from Category 2 in April 2026. Dates conflict: Apr 15 [djholtlaw](https://djholtlaw.com/regulatory-alert-the-legal-status-of-bpc-157-in-compounding-and-clinical-practice/), Apr 22 [projectbiohacking (LC)](https://www.projectbiohacking.com/guide-to-compounding-pharmacy-peptides), Apr 23 [nationwidecompounding (LC)](https://nationwidecompounding.com/peptide-compounding-pharmacy-2026/). The removal **does not** authorize compounding, because BPC-157 is not on the 503A bulks list — [Frier Levitt](https://www.frierlevitt.com/articles/fda-peptides-do-not-compound-list-update-2026/)
- The FDA PCAC met Jul 23–24, 2026 and backed six peptides, including BPC-157 and TB-500, for the 503A list. The vote is non-binding and rulemaking is still needed (one estimate: 8–12 months). **Tally conflicts:** 8–6 for BPC-157 [mypeptidematch (LC)](https://www.mypeptidematch.com/blog/fda-peptide-compounding-vote-july-2026) vs "6 of 7" [NWT Law](https://nwtlaw.com/blog/fda-advisory-panel-peptides-compounding-telehealth-prescribing/)
- In Sep 2025 FDA sent 50+ warning letters about GLP-1s (sema, tirz, retatrutide), some naming BPC-157 and "research use only" labeling — [Health Law Alliance](https://www.healthlawalliance.com/blog/fda-targets-glp-1-and-peptide-compounding-advertising-and-research-use-only-labeling)
- ReviveRX: Class I recall Apr 2024 (tirzepatide-labeled vials contained testosterone). Tailor Made (owned by Noom): federal guilty plea for distributing unapproved new drugs, $1.78M forfeiture — [TrueEval](https://trueeval.com/compounding-pharmacy-map)

### Inferences
- For a brand that wants a wide wellness menu (sermorelin, NAD+, B12/lipotropic injections, hormones), Empower is the only pharmacy here with a published developer API. Its two warning letters in 18 months (2025, 2026), both GLP-1-centric, are a concentration risk. A second pharmacy (Belmar or Olympia) is prudent.
- No legitimate 503A should currently dispense BPC-157 or TB-500 as compounded drugs. A network or pharmacy offering them in Oct 2026 is a red flag.

### Gaps
- No published wholesale prices for any pharmacy. Empower requires a form request.
- Partell: no reliable information found.
- State licensure for each pharmacy is a company claim (TrueEval says "verify per state"). I did not check state board records.
- Pharmacy-specific peptide catalog removals (who dropped what, and when) are not documented by any authoritative source. NAD+ regulatory status was not found.
- The Belmar Florida-affiliate warning letter (Mar 2023) is unconfirmed and conflicts with "no recent action."

---

## Any contracts, minimums, or merchant-of-record requirements to know?

### Takeaway
Who holds the merchant account is a key difference. Cuvo and Rimo settle to the brand's own account or Stripe. OpenLoop runs patient payments through its own merchant account and pays the brand out. Bask and FUSE take a percentage via built-in processing. OpenLoop's known proposal carries a 12-month term. Beluga's setup fee works as a visit prepayment.

### Cited Findings
- Cuvo: month-to-month; revenue settles to the brand's merchant account — [Cuvo (self)](https://cuvo.co/blog/white-label-telehealth-api-platforms-tested)
- OpenLoop: patient payments go through OpenLoop's merchant account; weekly fee remittance; 12-month term — [Cuvo (LC)](https://cuvo.co/blog/white-label-telehealth-api-platforms-tested); [Cuvo networks (LC)](https://cuvo.co/blog/best-telehealth-provider-networks)
- Rimo: the brand brings its own Stripe — [Rimo (LC)](https://rimo.co/blog/best-white-label-telehealth-2026)
- Bask: built-in processing rather than BYO, plus transaction fees; read the export and cancellation terms — [EmbedCare (LC)](https://www.embedcare.com/compare/bask)
- FUSE: 2–3% "merchant service fee" on every sale — [FUSE](https://www.fusehealth.com/blogs/best-white-label-telehealth-platform)
- Beluga: the integration fee is "fully applied to your future visit volume"; partner pharmacies carry a coordination fee — [Beluga](https://belugahealth.com/pricing)
- Wheel's API terms let it change, suspend or discontinue the API at any time — [Cuvo (LC)](https://cuvo.co/blog/white-label-telehealth-api-platforms-tested)
- MyOrbitHealth says enterprise vendors typically carry enterprise-sized minimums (category claim, no figures) — [MyOrbitHealth (LC)](https://myorbithealth.com/blog/beluga-vs-openloop-vs-myorbit)

### Inferences
- For a brand that wants its own storefront, its own pharmacy and its own processor, prefer a network where the brand is merchant of record (Beluga API, Cuvo, Rimo). Card processors will then underwrite the brand itself, which ties into the LegitScript requirement.

### Gaps
- No published minimum visit volumes for any vendor. Contract terms for Beluga, MDI, Telegra and Karpa were not found.

---

## Any compliance red flags (fee-splitting, CPOM, LegitScript for ads and processors)?

### Takeaway
Use a friendly-PC/MSO structure with **flat, fair-market-value** management fees. Fees tied to revenue or volume look like fee-splitting, and CA, TX and NY are the strictest CPOM states. LegitScript certification is effectively required for Google and Meta pharma/telehealth ads and for Visa/Mastercard high-risk MCC registration (5122/5912).

### Cited Findings
- The MSO + physician-owned PC model is standard. The PC must control all medical decisions. MSOs typically charge flat fees to avoid fee-splitting. Fees tied to volume or revenue resemble prohibited fee-splitting. Regulators are probing MSOs that set GLP-1 protocols, visit frequency and prescribing criteria. CA, TX and NY are the strong CPOM states — [Dickinson Wright (Feb 2026)](https://healthlawblog.dickinson-wright.com/2026/02/telehealths-weight-loss-boom-and-the-corporate-practice-of-medicine/); [Cohen Healthcare Law](https://cohenhealthcarelaw.com/?p=25315)
- Lilly's 2025 suits against telehealth companies over compounded GLP-1s alleged Lanham Act violations and CPOM-related deceptive practices — [WSGR](https://www.wsgr.com/print/v2/content/49047879/Telehealth-Companies-Sued-for-Selling-Compounded-GLP-1-Drugs-and-Violations-of-Corporate-Practice-of-Medicine-Laws.pdf)
- OIG Advisory Opinion 25-03: hourly clinician leasing paid regardless of reimbursement; fees must be fair market value — [Hinshaw](https://www.hinshawlaw.com/newsroom-updates-health-care-alert-oig-advisory-opinion-25-03-anti-kickback-rules-telehealth-contractual-arrangements.html)
- LegitScript says Google, Meta, Microsoft, TikTok, Visa and Mastercard recognize its certification. Visa and Mastercard use it in high-risk merchant registration for MCCs 5122/5912 — [LegitScript GLP-1 FAQ (vendor)](https://www.legitscript.com/healthcare/navigating-legitscript-certification-for-weight-loss-medications-common-inquiries-and-answers); [LegitScript pharmacies](https://www.legitscript.com/certification/pharmacies)
- Telehealth certification applications more than doubled in a year (Sep 22, 2026). LegitScript publishes no processing times or pricing. Google direct ads still require certification (a programmatic-side change in Dec 2025) — [PPC Land](https://ppc.land/telemedicine-applications-to-ad-certifier-legitscript-jump-101-in-a-year/)
- The Empower 2026 warning letter was framed around compounded GLP-1 "telehealth menus" (copies of approved drugs made with nominal additives such as B12 or niacinamide) — [ecommerce4im (LC)](https://ecommerce4im.com/fda-warning-letter-empower-pharmacy-compounded-glp-1-telehealth-menus/); [Luma Law](https://www.lumalexlaw.com/2026/09/24/empower-the-b-vitamin-and-the-word-pretextual/)

### Inferences
- Red flags in vendor contracts: revenue-share payouts to a physician network (FUSE's percentage fee is labeled a merchant fee, but have counsel review it); per-prescription payments from pharmacies to the brand or network (likely state anti-kickback and fee-splitting exposure, plus federal AKS if any federal payer is touched); and menus built on "GLP-1 + B12/niacinamide" combos, which FDA now calls pretextual.
- Marketing BPC-157 or TB-500 (or "research use only" peptides) would jeopardize LegitScript certification and Meta/Google ad accounts.

### Gaps
- No primary Google or Meta policy text retrieved, and no 2026 Visa/Mastercard rule changes found.
- No source directly addressed pharmacy-to-telehealth per-prescription payments under state law.
- LegitScript cost and timeline are unpublished. Rimo's "7–14 days" is a vendor claim.
