# Hyperliquid as a model of community-owned, revenue-backed protocol design

Research date: 2026-10-17. Every figure carries a date. "Official" means Hyperliquid docs or Hyper Foundation statements. "Third-party" means media, analysts or data sites. A few numbers came only from search-engine summaries of pages that could not be fetched in full; these are flagged "(search summary)". Several crypto-media sources disagree with each other, and the conflicts are noted inline.

## 1. HYPE token: supply, genesis distribution, no VC, vesting and unlocks

### Takeaway
HYPE launched on Nov 29, 2024 with a 1B max supply. 31% (310M) was airdropped fully unlocked to points earners, and there was no allocation to private investors, centralized exchanges or market makers. Core contributors got 23.8% under a 1-year lock. Their monthly unlocks began Jan 6, 2026 (about 9.92M HYPE per tranche), while fee-funded HYPE purchases (the Assistance Fund) have partly offset that supply.

### Cited Findings
- Genesis event: 07:30 UTC, Nov 29, 2024. The airdrop went to holders of reward points — [The Block](https://www.theblock.co/post/328631/hyperliquid-plans-to-launch-hype-token-in-nov-29-genesis-event)
- Allocation (official, as reported by The Block): 1B total supply. Airdrop 31.0% (310M), fully unlocked at genesis. Future emissions and community rewards 38.8% (388M). Core contributors 23.8% (238M), locked for 1 year after genesis. Hyper Foundation budget 6.0% (60M). The listed shares add to 99.6%. Other outlets put community grants at 0.3%, and the remainder is commonly attributed to HIP-2 (not verified here) — [The Block](https://www.theblock.co/post/328631/hyperliquid-plans-to-launch-hype-token-in-nov-29-genesis-event); grants 0.3% per [Decrypt](https://decrypt.co/294067/hyperliquid-airdrop-1-6-billion)
- Official wording: "no allocations for private investors, centralized exchanges, or market makers" — [The Block](https://www.theblock.co/post/328631/hyperliquid-plans-to-launch-hype-token-in-nov-29-genesis-event)
- Value of the airdrop: about $1.2B at the $3.90 launch price — [The Block](https://www.theblock.co/amp/post/328769/hyperliquid-airdrops-over-1-2-billion-worth-of-tokens-to-users-as-hype-crosses-4-billion-fdv). About $1.6B at the $5.40 peak — [Decrypt](https://decrypt.co/294067/hyperliquid-airdrop-1-6-billion). HYPE rose about 63% within roughly 12 hours of launch — [Cointelegraph](https://cointelegraph.com/news/hyperliquid-hype-token-surges-after-billion-dollar-airdrop)
- Reported conversion rate: about 5 HYPE per point earned — [Decrypt via search summary](https://decrypt.co/294067/hyperliquid-airdrop-1-6-billion)
- Team unlock schedule (third-party): the first monthly team unlock was Jan 6, 2026, under a 24-month vesting plan, and Hyperliquid said all future team unlocks would fall on the 6th of each month for predictability — [Netcoins](https://netcoins.com/blog/hyperliquids-hype-token-unlocks); [Bitget News](https://www.bitget.com/amp/news/detail/12560605125336). Sources disagree on the end date (2027 vs 2028) — same sources
- Before the first unlock, Hyperliquid unstaked 1.2M HYPE ahead of the Jan 6, 2026 vesting start — [Bitget News](https://www.bitget.com/amp/news/detail/12560605125336); [Yahoo Finance](https://finance.yahoo.com/news/hyperliquid-unstaking-alert-1-2m-084715569.html)
- Sept 6, 2026 unlock: about 9.92M HYPE (about 0.99% of max supply), roughly $820M at $82.60. The article also cites an Aug 29, 2026 batch of about 14.18M HYPE near the $86.71 all-time high. It does not explain why a batch fell off the 6th-of-month cadence — [crypto.news, Sept 7, 2026](https://crypto.news/hyperliquid-hype-token-unlock-820m-misleading/)
- After the March 2026 unlock, about 1.75% of unlocked tokens reached exchange deposit addresses within 30 days (Arkham). Deposits are not confirmed sales — [crypto.news, Sept 7, 2026](https://crypto.news/hyperliquid-hype-token-unlock-820m-misleading/)
- Aug 8, 2026: HyperLabs unlocked 433,025 HYPE (about $23.46M), and 165,000 of those tokens went to market maker Flowdesk — [BigGo Finance](https://finance.biggo.com/news/4cb0fbab-3c66-40dc-ba61-129abd171ffa)
- Founder Jeff Yan has said the project was "entirely self-funded" and never took VC money. He described a large VC stake as "a bit of a scar on the network itself" — [Wu Blockchain interview](https://wublock.substack.com/p/exclusive-interview-with-hyperliquid); [Antoine Buteau summary](https://www.antoinebuteau.com/lessons-from-jeff-yan-of-hyperliquid/) (third-party transcriptions)

### Inferences
- The two halves of the design do different jobs. The 31% fully unlocked airdrop with zero insider allocation created the "people's chain" identity. The 23.8% team share, locked for a year and then vested monthly, is roughly a normal startup team stake, so the "community-owned" claim comes from having no VC slice and a big, liquid user slice, not from a small team slice.
- The team unlocks were the first real test of community trust. A fixed, pre-announced unlock date combined with on-chain transparency and offsetting fee-funded buys appears to have limited the fallout, with some exceptions such as the Flowdesk transfer.

### Gaps
- No official Hyperliquid source found for the exact team vesting tranche size or end date. The tokenomics page in the docs now returns 404.
- The exact use of the 38.8% future-emissions pool (staking rewards vs. future airdrops) is not confirmed. No second airdrop had been announced as of Oct 2026 (see section 2).
- Circulating supply as of Oct 2026 was not confirmed. crypto.news implies about 232M from market cap divided by price, but that is a derived number.

## 2. Points program (seasons, criteria, transparency, sybil handling, perception)

### Takeaway
Points were distributed at fixed weekly amounts (1M a week, then 700K a week) from Nov 2023 to Nov 2024, under criteria Hyperliquid deliberately kept vague and reserved the right to revise. They converted to the 31% airdrop. There has been no Season 3 or second airdrop as of Oct 2026.

### Cited Findings
- Official: closed-alpha activity through Oct 31, 2023 counted. The initial program ran from Nov 1, 2023 to May 1, 2024 at 1,000,000 points per week. Activity from May 1–28, 2024 received a multiplier ("Season 1.5"). The L1 phase ("Season 2") ran from May 29, 2024 to Nov 2024 at 700,000 points per week — [Hyperliquid Docs: Points](https://hyperliquid.gitbook.io/hyperliquid-docs/points.md)
- Official: points "reward users who contribute to the protocol's success". Criteria "updated on a recurring basis". Weekly cut-off was Wednesday 00:00 UTC, with distribution on Thursday. Referrers (affiliates) earned 1 point for every 4 points their referees earned. Hyperliquid "reserves the right to modify previous point distributions under its sole discretion" — [Hyperliquid Docs: Points](https://hyperliquid.gitbook.io/hyperliquid-docs/points.md)
- Third-party: Season 1.5 carried 2x rewards. Season 2 ran at 700K per week until Sept 29, 2024, followed by an undisclosed "Season 2.5" — [MEXC News](https://www.mexc.com/news/how-the-hyperliquid-points-system-created-the-most-successful-airdrop-in-history/478)
- Sybil handling: the official docs say nothing on this. Secondary sources say wash trading and sybil attempts were filtered before the TGE and that some wallets were excluded — [OneKey](https://onekey.so/blog/ecosystem/hype-airdrop-breakdown/); [Eco](https://eco.com/support/en/articles/15039718-hyperliquid-airdrop-hype-genesis-facts-and-season-2-status) (unverified against primary sources)
- Perception: secondary analysis says the design significantly increased positive community sentiment — [MEXC News](https://www.mexc.com/news/how-the-hyperliquid-points-system-created-the-most-successful-airdrop-in-history/478)
- Season 3 speculation in 2025 was never confirmed. As of Oct 2026 the official points page lists no phase after Nov 2024 — [DeFi Education](https://defieducation.substack.com/p/hyperliquid-airdrop-speculation-and); [Eco](https://eco.com/support/en/articles/15039718-hyperliquid-airdrop-hype-genesis-facts-and-season-2-status)

### Inferences
- Several mechanics are directly reusable: a fixed weekly emission (scarcity is known while each person's share is not), a referral share paid as a fraction of referees' points, and opaque criteria to resist gaming. The tradeoff is less transparency: users had to trust the team's discretion, which worked because the eventual airdrop was large and fully unlocked.
- Ending points at genesis, with no follow-on seasons, avoided the "farm-and-dump" cycle that drags on many tokens. It also removed a growth incentive.

### Gaps
- No primary statement on sybil methodology or the number of wallets excluded.
- No primary data on the number of eligible wallets. Third-party figures (around 94K addresses) circulate but were not verified in this research.

## 3. Revenue: fees, scale, Assistance Fund, HLP vault and its incidents

### Takeaway
Fees go entirely to "the community" (HLP, the Assistance Fund, and deployers), not to the team. The Assistance Fund automatically converts fees into HYPE as part of L1 execution. Officially those tokens are described as burned, not as a "buyback" or "returns". As of Oct 2026, DefiLlama shows roughly $690M in annualized revenue. HLP, the community market-making vault, has been both profitable and the main absorber of manipulation losses (JELLY, the ETH whale, POPCAT).

### Cited Findings
**Fee structure (official, Oct 2026 docs)**
- Perps base tier: 0.045% taker / 0.015% maker, falling to 0.024% / 0.000% above $7B in 14-day volume. Spot base: 0.070% / 0.040%. Maker rebates go up to -0.003%. Staking discounts on fees: Wood (>10 HYPE) 5%, Bronze (>100) 10%, Silver (>1K) 15%, Gold (>10K) 20%, Platinum (>100K) 30%, Diamond (>500K) 40% — [Hyperliquid Docs: Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees.md)
- Official framing: "On Hyperliquid, fees are entirely directed to the community (HLP, the assistance fund, and deployers)." Spot and HIP-3 deployers may keep up to 50% of fees from their assets — [Hyperliquid Docs: Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees.md)
- Assistance Fund (official): it sits at system address 0xfefe…fefe and "converts trading fees to HYPE in a fully automated manner as part of the L1 execution." Also: "HYPE in the assistance fund is burned, removing the tokens permanently from the circulating and total supply" — [Hyperliquid Docs: Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees.md)
- Burn recognition vote: on Dec 17–18, 2025 the Hyper Foundation proposed a stake-weighted validator vote to treat Assistance Fund HYPE (about 37M HYPE at the time) as permanently burned. The vote involved no code change and no token movement, and amounted to "binding social consensus to never authorize a protocol upgrade to access this address." Results were due Dec 24, 2025 — [The Defiant](https://thedefiant.io/hyperliquid-proposes-burning-13-percent-of-circulating-token-supply); [Cointelegraph](https://regional-front.cointelegraph.com/news/hyperliquid-validators-vote-assistance-fund-supply). The current docs' "is burned" wording suggests it passed. No result announcement was retrieved
- Third-party: the Assistance Fund receives 99% of eligible trading fees. It bought about $500K a day in early 2025 and about $1M a day (about $30M a month) by mid-2026, with a peak day of $3.97M. Cumulative burns reached 48.42M HYPE (4.84% of max supply) by Sept 6, 2026 — [crypto.news, Sept 7, 2026](https://crypto.news/hyperliquid-hype-token-unlock-820m-misleading/). Holdings figures differ across outlets (about 29.8M vs about 45.65M HYPE at different dates) — [search summary of DEXTools/others](https://www.dextools.io/news/hyperliquid-hype-unlock-july-2026-buyback-fund-onchain-data) (page 404 on fetch)

**Revenue scale**
- DefiLlama, Oct 17, 2026 (search summary): 30-day fees of about $88.23M, 30-day revenue of about $71.05M, roughly $691M annualized, and TVL of about $6.9B. The Perps sub-page shows about $999.6M in annualized fees and $911.4M in annualized revenue, which likely reflects a different scope or window — [DefiLlama](https://defillama.com/protocol/hyperliquid); [DefiLlama Perps](https://defillama.com/protocol/fees/hyperliquid-perps)
- Apr 18, 2026: a $5.23M revenue day, the largest since February 2026 — [The Crypto Times](https://www.cryptotimes.io/2026/04/18/hyperliquid-posts-5-23m-revenue-day-biggest-since-february-as-bitcoin-tops-77k/)
- Market share estimates conflict: about 70% of on-chain perps volume, monthly volume above $200B, and fees "on the order of $1B/yr" ([crypto.news, July 27, 2026](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/)); 44% in April 2026 ([DefiLlama Pro dashboard](https://defillama.com/pro/hyperliquid-vs-the-opps-iujwua)); 31.9% over a 30-day window ([Datawallet](https://www.datawallet.com/crypto/hyperliquid-statistics)); about 32% of on-chain perps and above 6% of global perps including centralized exchanges ([VanEck](https://www.vaneck.com/pl/en/blog/digital-assets/exploring-hyperliquid-redefining-derivatives-trading/))

**HLP vault and incidents**
- Mar 12, 2025, ETH whale: a 50x ETH long (reported at 113K–175K ETH) withdrew about $17.09M in margin, leaving the position under-collateralized. HLP inherited it at about $1,915 and took about $4M in losses while unwinding. The trader made about $1.8M. Hyperliquid said there was no exploit and that "HLP is not a risk-free strategy," then cut max leverage to 40x on BTC and 25x on ETH and raised maintenance margin for large positions. Bybit CEO Ben Zhou called this a short-term fix and suggested dynamic risk limits instead — [The Defiant](https://thedefiant.io/news/defi/whale-s-nine-figure-eth-liquidation-costs-hyperliquid-usd4-million); [CryptoSlate](https://cryptoslate.com/hyperliquid-hit-by-4-million-loss-after-whales-high-risk-trading-incident/); [Benzinga](https://benzinga.com/content/44300092/bybit-ceo-questions-dexs-risk-controls-after-hyperliquid-eth-liquidation)
- Mar 26, 2025, JELLY: a manipulated, thinly traded JELLYJELLY perp left HLP inheriting a short with about $12M of unrealized loss (some reports say $13.5M). Validators voted to delist the perp and settle at $0.0095 (the attacker's entry price) rather than the roughly $0.50 market price. The Hyper Foundation promised to make all users except flagged addresses whole — [The Block](https://www.theblock.co/post/348314/hyperliquid-delists-jellyjelly-memecoin-amid-whale-manipulation-fiasco); [Halborn](https://halborn.com/blog/post/explained-the-hyperliquid-hack-march-2025)
- Unverified, single competitor source: HLP TVL fell from $540M to about $150M in the weeks after JELLY — [BIT Knowledge Hub](https://www.bit.com/knowledge-hub/hyperliquid)
- Oct 10, 2025: market-wide deleveraging of about $19B, with more than $10B of it on Hyperliquid. This was Hyperliquid's first cross-margin auto-deleveraging (ADL) in over two years. HLP reportedly earned about $40M–41.5M that weekend — [Wu Blockchain](https://wublock.substack.com/p/hyperliquid-activates-cross-margin); [CoinGecko HLP analysis](https://www.coingecko.com/learn/hyperliquid-hlp-vault-analysis)
- Nov 12, 2025, POPCAT: about $3M spread across 19 wallets opened $26M in leveraged longs and placed a $20M fake buy wall. When the wall was pulled, the price fell about 30% and HLP took about $4.5–4.9M in bad debt. Hyperliquid said there was no protocol exploit — [The Defiant](https://thedefiant.io/news/defi/large-popcat-trades-result-in-usd5-million-loss-for-hyperliquid-vault); [Yahoo Finance](https://finance.yahoo.com/news/hyperliquid-hit-third-market-manipulation-113215395.html)

### Inferences
- The official language matters. Hyperliquid describes the Assistance Fund as an automated protocol mechanism that converts fees and burns the result, never as a "dividend" or "return to holders". Media nonetheless call it a "buyback". For a project weighing securities-law exposure, how the mechanism is described is a design choice in its own right.
- HLP shows the cost of "community-owned" infrastructure: depositors get the profits and also absorb the losses from manipulation, and the foundation stepped in with discretionary make-whole payments in the JELLY case.

### Gaps
- No official figure for the exact split of fees between HLP and the Assistance Fund was found. The 99% figure is third-party.
- HLP's current TVL and APR as of Oct 2026 were not retrieved.
- The official result of the Dec 24, 2025 burn vote was not retrieved directly.

## 4. Builder ecosystem: builder codes, referrals, HIP-1/2/3, HyperEVM

### Takeaway
Third-party front-ends (wallets such as Phantom and MetaMask) earn on-chain "builder fees" on every fill they route, up to 0.1% on perps and 1% on spot. HIP-1 auctions spot-token tickers for HYPE. HIP-3 lets anyone who stakes 500K HYPE run their own perp exchange and keep up to 50% of fees. Together these turned outside developers into distribution partners with a stake in the outcome.

### Cited Findings
- Builder codes (official): users approve a maximum fee per builder from their main wallet (up to 10 active approvals, revocable at any time). Builders need at least 100 USDC in perps account value. Caps are 0.1% on perps and 1% on spot. Builders claim fees through the referral reward flow, and per-builder fill data is published publicly — [Hyperliquid Docs: Builder codes](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/builder-codes.md)
- Builder revenue (third-party, varying dates): Phantom leads with about $20.6M cumulative in one analysis and above $25M in a later Castle Labs-based report. MetaMask was at about $6.5M, later above $10.5M — [Crowdfund Insider](https://www.crowdfundinsider.com/?p=281809); [Blockworks: the frontend wars](https://blockworks.com/news/hyperliquid-the-frontend-wars). Another source estimates HIP-3 plus builder codes at about $100M a year, roughly 19% of revenue (unverified) — [Blockmedia](https://www.blockmedia.co.kr/research-english/957390)
- Referrals: during points, referrers received 1 point for every 4 points their referees earned — [Hyperliquid Docs: Points](https://hyperliquid.gitbook.io/hyperliquid-docs/points.md). A staking-based referral proposal page exists in the docs, but its contents were not retrieved — [Docs: staking referral proposal](https://hyperliquid.gitbook.io/hyperliquid-docs/referrals/proposal-staking-referral-program.md)
- HIP-1 (official): spot token tickers are sold in a 31-hour Dutch auction paid in HYPE. The price falls linearly from twice the last clearing price (or 500 HYPE if the previous auction failed) down to 500 HYPE — [Hyperliquid Docs: HIP-1](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-1-native-token-standard.md)
- HIP-3 (official): a 500K HYPE stake is required on mainnet, "expected to decrease over time". It must be kept for at least 183 days after a dex is deployed. Validators can vote to slash a deployer for harmful inputs, and slashed HYPE is burned. The stake does not insure traders — [Hyperliquid Docs: HIP-3](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-3-builder-deployed-perpetuals); some secondary sources say 30 days after halting instead — [Cryptonews](https://cryptonews.com/news/hyperliquid-goes-permissionless-with-hip-3-challenging-cex-but-entry-costs-500000-hype/)
- HIP-3 fees (official, Oct 2026): deployers can set an additional fee share of 0–300% (0–100% in "growth mode"). Growth mode cuts all-in fees by at least 90%, to about a 0.0045%–0.009% taker fee, for markets that don't overlap with validator-operated perps — [Hyperliquid Docs: Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees.md)
- HIP-3 traction (third-party, Aug 31, 2026): about $3.6B in open interest, 10 registered builder dexes, 5 of them live with 144 markets — [search summary of HIP-3 explainers](https://hiperwire.io/explainers/what-is-hip3-builder-deployed-perpetuals) (not independently verified)
- HIP-4 (outcome markets) now exists in the docs — [Hyperliquid Docs: HIP-4](https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-4-outcome-markets.md) (not read in detail)

### Inferences
- Builder codes are the most transferable mechanism for ZUMA. A referrer or front-end earns a capped, user-approved, on-chain fee on each order it routes, which makes "partners" into permanent stakeholders without handing them tokens. Requiring a large stake to deploy (HIP-3) is another reusable pattern: whoever gets to create supply must put skin in the game, and that stake can be slashed.

### Gaps
- HIP-2 (Hyperliquidity) mechanics were not retrieved from the docs.
- No sourced 2026 metrics for HyperEVM (TVL, apps). The governance audit mentions only that "EVM builder slots are allocated through a periodic auction" — [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/)
- Current referral program terms (discount rates, rebate shares) were not retrieved.

## 5. Validators and staking

### Takeaway
Hyperliquid uses delegated proof-of-stake. Validators must self-stake 10K HYPE locked for a year, delegators face a 1-day lock and a 7-day unstaking queue, and rewards scale inversely with the square root of total stake (about 2.37% a year at 400M staked). The validator set grew from 4 Foundation nodes at launch to 27 by June 2026. The Foundation's stake share fell from about 81% (Jan 2025) to about 49% (June 2026), and the node software is still closed source.

### Cited Findings
- Official: validators must self-delegate 10K HYPE, locked for 1 year. Delegations lock for 1 day, and unstaking takes 7 days. The reward rate is inversely proportional to the square root of total staked (about 2.37% a year at 400M staked). There is no slashing at present (it is reserved for provable malice such as double-signing). Jailing happens when more than two-thirds of stake votes to jail a validator for latency failures. Validators may raise their commission only to 1% or below — [Hyperliquid Docs: Staking](https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/staking.md)
- Validator count over time: 4 (launch, all run by the Foundation), 16 (Jan 2025), 21 (Apr 2025, open registration with the top-21 by stake active), 24 (later 2025), 27 (June 2026). Entering the active set takes roughly 1M+ HYPE in stake. The Foundation runs 5 of the 27 — [crypto.news governance audit, July 27, 2026](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/); [FXStreet, Apr 2025](https://www.fxstreet.com/cryptocurrencies/news/hyperliquid-updates-validator-to-21-permissionless-nodes-hype-price-breaks-out-202504220700)
- Foundation stake share: about 81% across 16 validators (early 2025, per a node operator's letter), down to about 49.3% by June 2026, with 50.7% across 22 independent operators — [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/); [Edgen](https://www.edgen.tech/news/post/hyperliquid-foundation-stake-falls-to-493-as-27-validators-secure-200b-venue)
- Jan 2025 criticism, led by a Chorus One employee: closed-source node code left validators poorly informed and exposed to jailing. The Foundation replied that open-sourcing matters and would happen when secure. HYPE fell about 15% around that time — [The Block](https://www.theblock.co/post/333559/hyperliquid-responds-to-community-concerns-over-validator-issues); [CoinDesk](https://coindesk.com/tech/2025/01/08/the-protocol-hyperliquid-responds-to-decentralization-criticism); [The Defiant](https://thedefiant.io/hyperliquid-fights-back-against-lack-of-decentralization-complaints)
- As of July 2026 the node software was still closed, the network ran a single client, and nodes that refused an upgrade dropped out of consensus — [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/); see also [OpenSourceForU, July 2026](https://www.opensourceforu.com/2026/07/hyperliquids-validator-model-faces-open-source-scrutiny/)
- Staking also earns trading-fee discounts of 5% to 40% by tier (see section 3) — [Hyperliquid Docs: Fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees.md)

### Inferences
- Holding-based utility tiers (fee discounts for staked HYPE) closely match ZUMA's "referral multipliers by holdings". Hyperliquid ties the tier to *staked* tokens rather than just held tokens, which adds a lock and commitment.

### Gaps
- Total HYPE staked as of Oct 2026 was not retrieved.

## 6. Governance in practice

### Takeaway
Formal governance is stake-weighted validator voting. Examples include the JELLY delisting, HIP votes and the Dec 2025 Assistance Fund burn vote. In practice the Foundation proposes and validators ratify, and until recently Foundation nodes held most of the stake. Critics argue this makes emergency votes look like centralized intervention.

### Cited Findings
- Governance weight follows delegated stake, not the number of validators. Peer jailing and forced upgrades are the main levers — [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/)
- JELLY (Mar 26, 2025): a validator vote delisted the asset and settled it at a price favorable to HLP — [The Block](https://www.theblock.co/post/348314/hyperliquid-delists-jellyjelly-memecoin-amid-whale-manipulation-fiasco). Later called a "validator put" in the trade press — [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/)
- Dec 2025: the Foundation proposed a validator vote to treat Assistance Fund HYPE as burned, with delegators able to redelegate to express a view, and stake-weighted results due Dec 24, 2025 — [The Defiant](https://thedefiant.io/hyperliquid-proposes-burning-13-percent-of-circulating-token-supply); [FXStreet](https://www.fxstreet.com/cryptocurrencies/news/hyperliquid-price-forecast-hype-stabilizes-amid-plans-to-burn-assistance-fund-202512170509)
- Apr 7, 2026: Bitget CEO Gracy Chen said Hyperliquid is "not a true DEX" but a centralized exchange, citing JELLY. June 2026: an investor (identified elsewhere as Kyle Samani) argued it is not permissionless without open-source validator software. June 18, 2026: CZ praised the model but questioned the decentralization claims — [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/). Note that Bitget, Bybit and CZ are competitors

### Inferences
- The community appears to tolerate Foundation-led governance because outcomes have favored holders: fees to the Assistance Fund, burns, and make-whole payments. Legitimacy here came from aligned outcomes more than from procedural decentralization. That works only as long as outcomes stay favorable.

### Gaps
- No complete record of validator votes or turnout was found. The USDH stablecoin ticker vote (Sept 2025) was not researched.

## 7. Culture and community identity

### Takeaway
The ownership culture rests on a few verifiable facts the community repeats: no VC money, the largest airdrop on record by value, all fees going to the community rather than the team, and a very small team. Jeff Yan presents himself as anti-VC and uninterested in money.

### Cited Findings
- Yan: the project was "entirely self-funded". VC stakes are "a bit of a scar on the network itself". He has said he was not doing it for money, calling money "really just a number" — [Wu Blockchain](https://wublock.substack.com/p/exclusive-interview-with-hyperliquid); [Antoine Buteau](https://www.antoinebuteau.com/lessons-from-jeff-yan-of-hyperliquid/)
- The team is widely reported as about 11 people (secondary sources) — [Eternal Growth](https://eternalgrowth.substack.com/p/hyperliquid); [Wu Blockchain](https://wublock.substack.com/p/exclusive-interview-with-hyperliquid)
- Avoiding centralized-exchange listing deals and market-maker allocations at launch was part of the stance — [The Block](https://www.theblock.co/post/328631/hyperliquid-plans-to-launch-hype-token-in-nov-29-genesis-event); [4 Pillars](https://research.4pillars.io/en/research/how-can-you-not-love-hype)
- Price context: HYPE at about $82.60 on Sept 7, 2026, with an all-time high of $86.71 near Aug 29, 2026 — [crypto.news](https://crypto.news/hyperliquid-hype-token-unlock-820m-misleading/) (compare the $3.90 genesis price)

### Inferences
- The "no VC" message is credible because it can be checked on-chain and in the genesis table. A small shop like ZUMA can copy the honesty (publish the allocation table, publish where fees go) even though it cannot copy the scale.

### Gaps
- No sourced community metrics (holder count, Discord or X size, active traders) as of Oct 2026.

## 8. Regulatory posture and legal structure

### Takeaway
The front end blocks US users and the Terms of Service bar US persons, but the L1 protocol itself does not geofence. In 2026 Hyperliquid moved from avoiding regulators to lobbying them: it launched the Hyperliquid Policy Center (Feb 2026, 1M HYPE committed) and argued that regulation should fall on the companies that deploy markets on Hyperliquid (HIP-3), not on the chain itself.

### Cited Findings
- US status: the front end blocks US IP addresses and the ToS bar US persons. The L1 does not geo-block — [Datawallet](https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa); [Hyperliquid Guide](https://hyperliquidguide.com/privacy/hyperliquid-us-availability)
- Feb 2026: Hyperliquid Policy Center launched with 1M HYPE committed to engage the CFTC and SEC — [Crypto Briefing](https://cryptobriefing.com/hyperliquid-us-perpetual-contracts-compliance/); [Yahoo Finance](https://finance.yahoo.com/markets/crypto/articles/hyperliquid-turns-cftc-path-u-153400685.html) (search summary)
- Aug 2026: President Trump said the CFTC (Chair Mike Selig) was working to bring Hyperliquid into the US "in a fully compliant and legal fashion". Sept 16, 2026: Payward (Kraken's parent) reportedly plans to offer US investors derivatives built on Hyperliquid technology through a regulated exchange. Oct 15, 2026: Yan told Bloomberg that "regulation belongs where control is exercised", meaning on the deploying companies — [CoinDesk, Oct 15, 2026](https://www.coindesk.com/policy/2026/10/15/hyperliquid-founder-wants-u-s-oversight-of-trading-platforms-not-his-blockchain)
- June 26, 2026: Singapore's MAS added Hyperliquid to its Investor Alert List. This is not a ban or enforcement action — [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/)

### Inferences
- Hyperliquid spent its first two years outside the US and grew because of it. US-facing products are only now arriving, through regulated intermediaries. That path is not available to a US-facing peptide shop, whose token utility (member pricing, votes) sits much closer to the consumer.

### Gaps
- The legal entities and jurisdictions of the Hyper Foundation and Hyperliquid Labs were not confirmed in this research.
- No primary CFTC or SEC filing text was retrieved.

## 9. What failed or drew criticism, and lessons

### Takeaway
The recurring failures were (a) thin-market manipulation draining the community vault, (b) emergency discretionary interventions that undercut decentralization claims, (c) closed-source software and concentrated Foundation stake, and (d) supply overhang from team unlocks. The fixes were risk-parameter changes, make-whole payments, gradual decentralization of stake, and predictable unlock schedules.

### Cited Findings
- Manipulation losses to HLP: ETH whale, about $4M (Mar 12, 2025); JELLY, about $12–13.5M unrealized (Mar 26, 2025); POPCAT, about $4.5–4.9M (Nov 12, 2025) — [The Defiant](https://thedefiant.io/news/defi/whale-s-nine-figure-eth-liquidation-costs-hyperliquid-usd4-million); [The Block](https://www.theblock.co/post/348314/hyperliquid-delists-jellyjelly-memecoin-amid-whale-manipulation-fiasco); [The Defiant](https://thedefiant.io/news/defi/large-popcat-trades-result-in-usd5-million-loss-for-hyperliquid-vault)
- Responses: leverage cuts (40x BTC / 25x ETH) and higher maintenance margins for large positions after the ETH whale — [CryptoSlate](https://cryptoslate.com/hyperliquid-hit-by-4-million-loss-after-whales-high-risk-trading-incident/). Foundation make-whole after JELLY — [The Block](https://www.theblock.co/post/348314/hyperliquid-delists-jellyjelly-memecoin-amid-whale-manipulation-fiasco)
- Decentralization criticism and the still-closed node code (Jan 2025 to July 2026) — [The Block](https://www.theblock.co/post/333559/hyperliquid-responds-to-community-concerns-over-validator-issues); [crypto.news](https://crypto.news/who-actually-runs-hyperliquid-the-governance-audit/)
- The Oct 10, 2025 ADL showed that socialized liquidation mechanics can close profitable positions without warning, a fairness complaint even though the system stayed solvent — [Wu Blockchain](https://wublock.substack.com/p/hyperliquid-activates-cross-margin); [Cointelegraph](https://cointelegraph.com/news/trader-loses-3m-fartcoin-hyperliquid-adl-liquidation)

### Inferences (lessons relevant to ZUMA)
- Publish the allocation table and the fee destination on day one, and keep to them. That is the root of Hyperliquid's credibility.
- If members vote on outcomes with money attached (for example, which factory makes a lot), expect pressure for emergency overrides. Write the override rules in advance, because an ad-hoc override reads as centralization (the JELLY lesson).
- Describe any fee-funded token purchase as a protocol or utility mechanism (burn, supply reduction), not as holder "returns". Hyperliquid's docs never call it yield.
- Thinly traded, low-liquidity markets are where manipulation happens. A small token with holdings-based multipliers is exposed to whales who briefly accumulate to capture tier benefits. Hyperliquid uses *staked* balances, with lockups and unstaking queues, to blunt this.

### Gaps
- No measured data on community sentiment after each incident (holder churn, for example) beyond price moves.
