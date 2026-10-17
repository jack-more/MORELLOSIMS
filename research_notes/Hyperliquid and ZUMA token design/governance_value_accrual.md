# Token Governance and Value-Accrual Mechanisms in Established DeFi Protocols (framed for ZUMA)

Research date: 2026-10-17. All figures carry the date of the source; "prior state" marks superseded designs. Source quality is flagged inline. Many 2025-2026 figures come from secondary crypto-news outlets; primary forum/docs pages are cited where found.

ZUMA framing used throughout: $ZUMA is a Solana utility token giving member pricing and referral multipliers; members vote on which factory makes each lot; a voting streak earns extra discount and referral boost. ZUMA must avoid anything that looks like revenue share or a promise of value.

---

## 1. Curve veCRV vote-escrow, gauge voting, bribe markets (Convex, Votium), and ve(3,3) variants (Velodrome/Aerodrome)

### Takeaway
Vote-escrow ties voting power to lock length (up to 4 years, linearly decaying) and pays lockers fees plus emissions-direction power; this created a durable "Curve Wars" bribe market in which aggregators (Convex) captured roughly half of veCRV by 2022 and voting power became a priced commodity sold weekly via Votium. ve(3,3) forks (Aerodrome) made the bribe market explicit and paid voters 100% of fees from pools they vote for, which works for a DEX but is exactly the "pay holders from revenue" pattern ZUMA must avoid.

### Cited Findings
- Lock mechanics: CRV locks run 1 week to 4 years; 1 CRV locked 4 years = 1 veCRV, 1 year = 0.25 veCRV; balance decays linearly as unlock approaches (e.g., 100 veCRV -> 75 after 1 year -> 50 after 2) — [Curve docs: What is veCRV](https://docs.curve.finance/user/vecrv/what-is-vecrv); [Dextools ve-tokenomics guide](https://www.dextools.io/tutorials/what-is-ve-tokenomics-vote-escrow-gauges)
- veCRV holders get gauge votes (directing CRV emissions to pools), a liquidity-mining boost of up to 2.5x, and a share of trading fees plus interest from Curve's stablecoin (crvUSD) markets — [Curve docs](https://docs.curve.finance/user/vecrv/what-is-vecrv); [Curve CRV/veCRV FAQ](https://resources.curve.finance/crv-token/faq)
- Convex aggregated CRV into permanently locked veCRV (users receive liquid cvxCRV); vlCVX holders direct the pooled votes and may delegate to Votium, where a "cottage industry" of CVX vote-bribing emerged — [GSR, "Curve Wars" (Jan 21, 2022)](https://www.gsr.io/wp-content/uploads/2022/01/2022.1.21_Curve-Wars.pdf); [Incentivized substack, "How Bribes Drive the Curve Wars"](https://incentivized.substack.com/p/how-bribes-drive-the-curve-wars)
- Prior state (2021-22): Convex share of veCRV grew from ~32% to ~39% (late 2021), later estimated ~47-48% of ~370M veCRV; one source cites >290M CRV (~50% of veCRV) — [Delphi Digital (paywalled summary)](https://members.delphidigital.io/reports/is-the-convex-flywheel-sustainable); [Incentivized substack](https://incentivized.substack.com/p/how-convex-stacked-as-much-crv-as); [spark.money glossary](https://www.spark.money/glossary/curve-war) (secondary). No 2025-26 figure found.
- Prior state: one week saw >$18M of bribes paid via Votium; one analysis found each $1 of bribes to CVX holders directed ~$2.05 of CRV emissions (i.e., buying votes was cheaper than buying the emissions they control) — [Incentivized substack](https://incentivized.substack.com/p/how-bribes-drive-the-curve-wars)
- Criticism framed by these sources is concentration (Convex realised CRV "was a mechanism to control liquidity"), not secrecy—bribes are public and vlCVX holders view them positively — [Incentivized substack](https://incentivized.substack.com/p/how-bribes-drive-the-curve-wars)
- Aerodrome (ve(3,3), Base): weekly epochs reset Thursday 00:00 UTC; veAERO voters receive 100% of trading fees from the pools they vote for plus any external incentives ("bribes") deposited for those pools, pro rata — [Paragraph explainer "How Aerodrome's veAERO System Works"](https://paragraph.com/@defi--world/how-aerodromes-veaero-system-actually-works-1) (secondary)
- Aerodrome said veAERO voters earned $8.8M voting rewards in one epoch (post dated Jan 27, 2025) — [Aerodrome on X](https://x.com/AerodromeFi/status/1883892773025468599)
- DefiLlama 2025 quarterly gross revenue for Aerodrome: Q1 $73.28M, Q2 $42.15M, Q3 $71.26M, Q4 $44.75M; external bribes Q1 ~$10.66M, Q2 ~$5.51M, Q3 ~$22.61M, Q4 ~$6.91M (swap fees dominate; volume fell after Oct 2025 peak) — [DefiLlama Aerodrome](https://defillama.com/protocol/aerodrome) (live page; figures as relayed by search, verify); [4pillars AERO thesis](https://research.4pillars.io/en/research/aero-thesis-base-s-cash-cow-coinbase-s-golden-child)

### Inferences
- The core lesson of veCRV is that any vote whose outcome has cash value to a third party will be priced and bought. A ZUMA factory-selection vote affects which supplier gets an order: factories (or their agents) have a direct financial incentive to "bribe" voters with discounts, kickbacks, or token buys. ZUMA's vote needs bribe-resistance designed in (e.g., factories pre-qualified by QA data; vote picks among already-vetted options; disclosure rules; ban on supplier-funded voter incentives).
- Lock-to-vote (ve) is useful for ZUMA only in a non-financial form: time-weighted membership (streaks, tenure) rather than locked capital earning fees. Linear-decay "commitment" weighting maps naturally onto a voting streak.
- ve(3,3)'s "voters get 100% of fees" is the clearest example of revenue share to token holders; it is the pattern ZUMA should explicitly not copy.

### Gaps
- No 2025-26 data found on Convex's current veCRV share, Votium weekly bribe volumes, or crvUSD fee flow to veCRV.
- Aerodrome official docs fetch returned no content; lock max (believed 4 years) and Aero Fed emissions governance not verified this session.
- No sourced academic quantification of bribe-market welfare effects was retrieved.

---

## 2. Aave: Aavenomics update, buybacks (2025-26), Umbrella safety module, governance participation and delegates

### Takeaway
Aave moved from "stake AAVE as insurance" to explicit buybacks: a committee-run buyback approved April 2025 (~$1M/week), budget cut in March 2026 when fees fell, then automated on-chain buybacks under "Aavenomics 3.0" from June 27, 2026. Umbrella replaced the governance-voted Safety Module slashing with automatic, asset-specific slashing of staked aTokens/GHO. The arc shows that revenue-funded buybacks are pro-cyclical and require a profitable, mature protocol—and are squarely "value accrual" in regulatory terms.

### Cited Findings
- Mar 4, 2025: Marc Zeller (Aave Chan Initiative) proposed the tokenomics revamp: revenue redistribution, "Umbrella" safety system, Aave Finance Committee — [Cointelegraph](https://cointelegraph.com/news/aave-revamp-include-revenue-redistribution-umbrella-safety-system); original [TEMP CHECK AAVEnomics update](https://governance.aave.com/t/temp-check-aavenomics-update/18379/4)
- April 2025: DAO approved AAVE buybacks (initial ~$4M; ~99.6% approval), run by the Finance Committee at ~$1M/week — [crypto.news](https://crypto.news/aave-dao-approves-aave-buybacks-as-part-of-the-broader-aavenomics-overhaul/) (secondary)
- By Feb 2026: ~$42M spent buying >205,000 AAVE (~1.28% of supply), held in the Ecosystem Reserve (funds staking incentives, grants, service providers) — per search summary of [Phemex](https://phemex.com/blogs/aave-surging-automated-buyback-engine)/[KuCoin](https://www.kucoin.com/news/flash/aave-considers-token-burn-pump-continues-buybacks-where-do-repurchased-tokens-go) (low-reliability aggregators; verify)
- March 2026: DAO cut annual buyback budget from $50M to $30M because lending fee income fell ~25% from peak; buybacks paused April-June 2026 — same aggregator sources (verify on governance.aave.com)
- June 2026: Stani Kulechov announced "Aavenomics 3.0" with automatic on-chain buybacks funded by protocol and GHO revenue, launched June 27, 2026, buying ~292 AAVE/day; follows April 2026 "Aave Will Win" framework under which 100% of Aave-branded product revenue goes to the DAO treasury — [ForkLog](https://forklog.com/en/aave-founder-announces-automatic-aave-buyback/); revenue cited by Kulechov ~$134M/yr (conflicts with a Phemex figure of $400M; Phemex less reliable)
- Umbrella: stakers deposit aTokens (aUSDC, aUSDT, aWETH) or GHO; automated slashing based on actual deficit, each staked asset covering only its own borrowed asset on the same network; prior state (legacy Safety Module) required an on-chain governance vote to slash staked AAVE/stkABPT — [Aave docs: Umbrella](https://aave.com/docs/primitives/umbrella); [Aave docs: Safety Module](https://aave.com/docs/primitives/safety-module); [BGD Umbrella proposal](https://governance.aave.com/t/bgd-aave-safety-module-umbrella/18366)
- Umbrella activation: max slashing up to 20% for stkAAVE/stkABPT, slashing disabled for stkGHO (moving to sGHO without cooldown or slashing); 20-day cooldown and 2-day withdrawal window retained; legacy stkAAVE/stkABPT stay live during transition — [ARFC Aave Umbrella activation](https://governance.aave.com/t/arfc-aave-umbrella-activation/21521); [Aave Umbrella help](https://aave.com/help/umbrella/umbrella)

### Inferences
- Aave's experience (buyback budget cut within a year when fees fell) shows token "value accrual" ties token sentiment to business cyclicality; a small shop with volatile margins would face the same pressure plus regulatory exposure.
- Umbrella's design move—replace discretionary governance votes with pre-set automatic rules for high-stakes, time-sensitive events—is transferable: ZUMA should hard-code QA failure responses (e.g., a lot failing COA testing auto-disqualifies a factory) rather than leave them to member votes.
- Aave relies on professional delegates (ACI, etc.) to drive proposals; a heavy-delegate model is overkill for ZUMA's narrow vote.

### Gaps
- Exact Umbrella mainnet launch date not confirmed in retrieved sources.
- No sourced 2025-26 Aave voter-turnout or delegate concentration statistics retrieved.
- 2026 buyback totals are from aggregator sites; primary governance posts not fetched.

---

## 3. Uniswap: fee switch history, "UNIfication" (passed Dec 2025), delegate participation

### Takeaway
Uniswap debated a fee switch for years (long blocked by legal caution and LP-impact worries) and finally passed "UNIfication" on Dec 25, 2025 with near-unanimous support, turning protocol fees on for v2 and selected v3 pools and routing them to UNI buy-and-burn, plus a retroactive 100M UNI (~$596M) burn. Turnout was propped up for years by token loans to delegates and paid delegate programs.

### Cited Findings
- UNIfication passed Dec 25, 2025: ~125.34M UNI for vs. 742 against (~99.9%), quorum 40M UNI cleared >3x — [The Defiant](https://thedefiant.io/news/defi/uniswap-passes-unification-fee-switch-proposal); [AMBCrypto](https://ambcrypto.com/uniswap-governance-approves-unification-clears-path-for-100m-uni-burn-and-protocol-fees/)
- After timelock, 100M UNI (~$596M) burned from treasury; framed as a retroactive estimate of what would have been burned had fees been on since launch — [DL News](https://www.dlnews.com/articles/defi/uniswap-dao-to-activate-fee-switch-and-burn-100m-uni-tokens/); [Startup Fortune](https://startupfortune.com/uniswap-torched-596-million-in-uni-the-same-week-its-fee-switch-passed/)
- Mechanics: protocol fees on for v2 and selected high-volume v3 mainnet pools; v2 LP fee 0.30% -> 0.25% with 0.05% to protocol (~1/6 of swap fees), routed to "TokenJar" contracts that buy and burn UNI — [Yahoo Finance](https://finance.yahoo.com/news/uniswap-approves-100m-uni-burn-073259869.html); [Block Editorial](https://blockeditorial.com/uniswap-fee-switch-turns-protocol-revenue-into-permanent-uni-burns/)
- Post-activation results conflict: one source ~ $23.15M cumulative protocol revenue ~8 months in; Ark Invest est. ~$90M annualized burns; an unverified ~$250M annualized figure attributed to Hayden Adams — [Phemex](https://phemex.com/blogs/uniswap-fee-switch-revenue); [crypto.news](https://crypto.news/uniswap-fee-switch-defi-governance/) (secondary; treat as unverified)
- Delegate pay: March 2025 the DAO renewed its Delegate Reward Initiative (cycle 3), up to $6,000 in UNI/month to top delegates, conditioned on voting participation and engagement — [The Block](https://www.theblock.co/post/344797/uniswap-votes-delegate-reward-initiative-pays-uni-tokens-incentivize-governance)
- May 2025: DAO considered reclaiming ~12.5M UNI (~$42M) lent to delegates and the Foundation in 2022-23; DAO statement said passed proposals since the DUNI structure averaged ~75M votes, ~88% above quorum (self-reported) — [DL News](https://www.dlnews.com/articles/defi/uniswap-dao-votes-to-take-back-loaned-uni-tokens/); [Bloomingbit](https://en.bloomingbit.io/feed/news/111429)
- Prior state baseline (academic, 2023): average Uniswap turnout ~18% (max ~41%), median 686 voters/proposal; top 50 delegatees held ~88% of delegated UNI — [arXiv 2305.17655](https://arxiv.org/html/2305.17655v4)

### Inferences
- Uniswap needed token loans and paid delegates just to clear quorum reliably; near-unanimous votes on value-accrual (burns) are unsurprising because they benefit every holder—which is exactly why such votes are economically "investment-like".
- The years-long delay of the fee switch was driven partly by securities-law risk; Uniswap only moved after a friendlier US regulatory environment (see Section 9 on the 2026 SEC interpretation). ZUMA should not assume that environment protects revenue routing for a small, centrally-run business token.

### Gaps
- No primary Tally/Agora 2025-26 turnout series retrieved; secondary-site figures (e.g., "median 67 voting addresses") unverifiable and excluded.
- Post-UNIfication primary revenue/burn dashboards not fetched.

---

## 4. Ethena: sENA, fee switch debate and revenue distribution

### Takeaway
Ethena's fee switch was debated from 2024, gated behind milestones, and approved in a vote closing ~Sept 2, 2026—but buybacks (95% of net revenue to ENA buybacks) only start once USDe supply reaches $7.5B, which had not happened as of late Sept 2026 (~$4.9B). sENA staking rewards are deferred to a separate proposal. It is an example of "conditional, milestone-gated" value accrual.

### Cited Findings
- Aug 27, 2026: Ethena Foundation proposed fee switch for ENA buybacks plus other updates — [The Block](https://www.theblock.co/news/ecosystems/2026-08-27-ethena-foundation-proposes-fee-switch-ena-token-buybacks-other-updates-412951); primary thread [ENA Fee Switch Activation – Ethena Governance](https://gov.ethenafoundation.com/t/ena-fee-switch-activation/830)
- Vote passed; reports conflict on tallies (one: unanimous, ~17.8M votes for; another: closed Sept 2, 2026 with 76 for, 0 against) — [ETH Daily](https://ethdaily.io/ethena-approves-protocol-fee-switch); [CryptoNexa](https://www.cryptonexa.com/ethena-ena-fee-switch-passes-vote-buybacks-tied-to-usde-growth-milestones)
- Trigger: buybacks begin when USDe circulating supply reaches $7.5B; 95% of net revenue to ENA buybacks; USDe ~ $4.07B (Aug 30, 2026), ~ $4.9B (late Sept 2026) — [CoinMarketCap AI updates](https://coinmarketcap.com/cmc-ai/ethena/latest-updates/); [CryptoTicker](https://cryptoticker.io/en/ethena-fee-switch-ena-buyback/)
- sENA staking rewards to be handled in a later governance proposal — [CryptoNexa](https://www.cryptonexa.com/ethena-ena-fee-switch-passes-vote-buybacks-tied-to-usde-growth-milestones)
- Remaining investor allocations consolidated into a single unlock on Oct 5, 2026 — [Tokenomist weekly digest](https://tokenomist.ai/research/weekly-unlock-digest-aug-31-sep-6-2026-ethenas-fee-switch-2); [CoinMarketCap](https://coinmarketcap.com/cmc-ai/ethena/latest-updates/)
- Conflict: a tokenomics.com article claims activation in Q1 2026, inconsistent with the Aug-Sept 2026 governance timeline; discounted — [tokenomics.com](https://tokenomics.com/articles/ethena-tokenomics-how-ena-captures-57m-monthly-from-synthetic-dollars)

### Inferences
- Even large protocols with clear revenue proceed slowly and with milestone gates on value accrual; ZUMA, a small retail business, has much less reason and much more risk to do anything comparable.
- Ethena's split (governance token votes; a separate staked wrapper gets any economics) is a pattern ZUMA can borrow in inverse: keep $ZUMA strictly as a member/discount tool, with no staked wrapper that receives cash flows.

### Gaps
- No confirmation buybacks have begun as of Oct 17, 2026; vote tallies conflict across secondary sources; primary forum thread not fetched in full.

---

## 5. MakerDAO/Sky and Compound: governance attacks, low turnout, delegate capture

### Takeaway
Compound's July 2024 "Humpy / Golden Boys" episode showed that low turnout lets a coordinated bloc (assembled partly from exchange-held tokens delegated in) pass a treasury-raid-like proposal with ~52% of votes cast. MakerDAO/Sky shows the opposite failure: chronic low turnout makes a founder's minority stake decisive (Endgame 2022 and the Sky rebrand votes).

### Cited Findings
- Compound Proposal 289 (July 2024) passed 51.84% for / 48.16% against, moving 499,000 COMP (~$24M) from treasury to "goldCOMP", a vault controlled by the Golden Boys' multisig; earlier versions had been cancelled or voted down (88% against) — [CoinDesk (Jul 29, 2024)](https://coindesk.com/markets/2024/07/29/comp-down-67-after-supposed-governance-attack-on-compound-dao); [The Defiant](https://thedefiant.io/news/defi/compound-governance-attack-reveals-inherent-vulnerabilities-of-daos)
- The proposer had >228,000 COMP delegated from five wallets holding Bybit exchange funds; the group controlled 325,333 COMP, >81% of the 400,000 quorum — [The Defiant](https://thedefiant.io/news/defi/compound-community-accuses-notorious-whale-of-engineering-governance-attack); [Unchained](https://unchainedcrypto.com/humpy-accused-of-governance-attack-on-compound-finance-dao/)
- OpenZeppelin's Michael Lewellen called it a governance attack; Wintermute noted withdrawals would be controlled by the Golden Boys' multisig, not the DAO; COMP fell ~6-7%; follow-up Proposal 290 sought to transfer Timelock admin with a 2-day delay — [CoinDesk](https://coindesk.com/markets/2024/07/29/comp-down-67-after-supposed-governance-attack-on-compound-dao)
- Prior state (2022): MakerDAO Endgame vote—a risk official claimed Rune Christensen represented 63% of the 122 voting addresses with ~74% economic influence — [BeInCrypto](https://beincrypto.com/makerdao-mkr-endgame-plan-passed-in-a-vote-where-founder-had-60-influence/); [CryptoSlate](https://cryptoslate.com/makerdao-mkr-community-approves-endgame-proposal/)
- Sky rebrand-continuation vote: ~20 participants; four large entities controlled ~80% of vote share (another report says 98%; conflicting) — [CryptoSlate](https://cryptoslate.com/makerdao-community-decides-to-continue-sky-rebrand-amid-centralization-concerns-in-vote/)
- Claim that many major Maker/Sky proposals passed with <10% of eligible tokens voting by 2024, and that S&P noted Rune held ~9% of governance tokens making him decisive given low turnout — [Chainscore Labs blog](https://www.chainscorelabs.com/blog/the-stablecoin-economy-regulation-and-adoption/stablecoin-governance-and-decentralization/the-hidden-cost-of-voter-apathy-in-multi-billion-dollar-daos) (low-reliability; S&P primary not found)

### Inferences
- For ZUMA: token-weighted votes with low turnout are capturable by anyone who can borrow, buy, or get exchange-held tokens delegated for a vote window. A factory (or competitor) could buy $ZUMA to steer lot production. Mitigations: snapshot voting power before the vote is announced, require holding/tenure, cap per-wallet weight, and keep a veto/safety rule (QA gate) held by the operator.
- Treasury-moving proposals are the high-value attack surface; ZUMA votes should never be able to move treasury funds.

### Gaps
- Final resolution of the Golden Boys/Compound dispute (settlement terms) not retrieved.
- No primary 2025-26 Sky governance turnout data found.

---

## 6. Rewarding contributors rather than capital: Optimism RetroPGF/Citizens' House, Gitcoin QF, Arbitrum DAO; Snapshot vs on-chain; paying voters

### Takeaway
Optimism's own 2025 assessment admits RetroPGF "lacks sufficient evidence that rewards have caused significant ecosystem growth," and community surveys favoured expert allocation. Gitcoin QF works but is structurally sybil-prone and needs identity/cluster-matching. Paying delegates (Arbitrum DIP/RAD, Uniswap delegate rewards) raises measured participation modestly (+12-13% in Arbitrum's self-reported first quarter) but produces box-ticking, scoring disputes, and a small active core (~91 of 986 Arbitrum delegates >65% participation). There is no strong evidence that paying voters improves decision quality.

### Cited Findings
- Optimism: 2024 Retro Funding rewarded 400+ builders with 20M OP across three rounds, but Optimism says it "still fails to reliably support important contributions" and "lacks sufficient evidence that rewards have caused significant ecosystem growth"; 2025 shifts to continuous, metrics-assisted evaluation — [Optimism blog, Retro Funding 2025](https://optimism.io/blog/retro-funding-2025)
- Citizens' House launched with 10M OP for public goods; badgeholders (non-token-weighted) vote — [Optimism blog](https://optimism.io/blog/introducing-the-citizens-house-10m-op-to-public-goods)
- RetroPGF Round 2: all 195 nominated projects received funding; badgeholders spread votes over ~40 projects each — [Optimism community hub (GitHub)](https://github.com/ethereum-optimism/community-hub/blob/main/pages/citizens-house/rounds/retropgf-2.mdx)
- Community: ~80% of surveyed respondents preferred the expert allocations from Round 5; proposal to separate "voting" from "judging" — [Optimism forum, Lessons learned from two years of RetroPGF](https://gov.optimism.io/t/lessons-learned-from-two-years-of-retroactive-public-goods-funding/9239); voting-design vulnerabilities — [arXiv 2505.16068](https://arxiv.org/pdf/2505.16068)
- Gitcoin QF: matching rewards breadth of contributors, which incentivises sybils; Gitcoin concedes sybils are unavoidable in any QF variant; COCM (connection-oriented cluster matching) simulations showed 1,000 sybils added only ~0.2 pp to a project vs standard QF — [Gitcoin research: QF sybil resistance](https://gitcoin.co/research/quadratic-funding-sybil-resistance); [Gitcoin forum GG20 sybil strategy](https://gov.gitcoin.co/t/our-sybil-resistance-strategy-for-gg20/18524)
- Study of a QF crowdfunding platform: popularity effects, not only sybils, distorted outcomes — [arXiv 2509.18343](https://arxiv.org/html/2509.18343v1)
- Arbitrum DIP v1.0 (self-reported): participation of enrolled delegates rose 12% on Snapshot and 13% on Tally in the 3 months after launch vs before — [Arbitrum forum DIP v1.0 analysis](https://forum.arbitrum.foundation/t/dip-v1-0-from-engagement-to-rewards-a-comprehensive-analysis-of-participation-and-incentives/25671)
- DIP v1.6 midterm (Nov 2024-Apr 2025): steadier participation, high-voting-power delegates key to quorum, but "disputes over subjective scoring have increased" — [Arbitrum forum DIP v1.6 analysis](https://forum.arbitrum.foundation/t/dip-v1-6-from-engagement-to-rewards-a-comprehensive-analysis-of-the-delegate-incentives-program/29475)
- Qualification rates: Feb 2025 72 enrolled / 68 qualified; Oct 2025 84 enrolled / 47 met base requirements — [DIP Feb 2025 results](https://forum.arbitrum.foundation/t/dip-v1-6-delegate-incentive-program-results-february-2025/28742/9); [DIP v1.7 Oct 2025 results](https://forum.arbitrum.foundation/t/dip-v1-7-delegate-incentive-program-results-october-2025/30265)
- 2026 successor "Rewarding Active Delegates" (RAD): May 2026, 36 enrolled delegates, 75.69% program participation, first month under OpCo eligibility changes — [Arbitrum forum RAD May 2026](https://forum.arbitrum.foundation/t/rewarding-active-delegates-may-2026-results/30944)
- Critique: of 986 Arbitrum delegates only 91 had 65%+ participation; 5 delegates disqualified in Feb 2026 for missing the 75% threshold — [Medium, MconnectDAO](https://medium.com/@MconnectDAO/arbitrum-has-986-delegates-only-91-actually-show-up-d4643e814328) (third-party opinion)
- Snapshot (off-chain, gasless signatures) vs on-chain: off-chain results can be executed by a Safe via the SafeSnap module (used by SafeDAO, GnosisDAO) — [Safe forum](https://forum.safe.global/t/best-practices-for-safe-multisig-management-in-a-growing-dao/6620)

### Inferences
- Paying for participation reliably buys participation metrics, not judgment. ZUMA's voting-streak reward (extra discount + referral boost) is a participation payment; expect click-through voting unless each vote carries information cost (e.g., must open the lot's COA/factory scorecard) or the reward is tied to a non-trivial action.
- Optimism's move toward experts + metrics suggests ZUMA's factory vote should be bounded: operator/QA shortlists factories that pass objective tests, members choose among them. That keeps the member vote meaningful (preference among safe options) while the safety-critical judgment stays with qualified people.
- A streak reward that is a discount on purchases is consumptive (reduces price of goods) rather than a cash payout—consistent with "digital tool" framing (Section 9)—but referral multipliers that pay in tokens or cash need care so they don't read as yield.

### Gaps
- No rigorous (independent, causal) study found showing paid voting improves decision quality; evidence is self-reported program metrics.
- No independent evaluation of Retro Funding impact beyond Optimism's own statements.

---

## 7. One-person-one-vote vs token-weighted vs conviction vs quadratic voting: real-world results

### Takeaway
Token-weighted voting reliably concentrates power (top delegates capture most effective weight); quadratic schemes reduce plutocracy only to the extent identity is sybil-resistant; one-person-one-vote exists in practice mainly as curated "badgeholder" or soul-bound systems (Optimism Citizens' House). Conviction voting outcomes lack good recent evidence.

### Cited Findings
- Delegation studies (5 protocols on-chain, 14 DAO forums): delegation reinforces visibility bias—a small set of highly ranked delegates accrue disproportionate influence regardless of alignment; ranking-based delegate UIs exacerbate concentration — [Messias & Ide, arXiv 2510.05830](https://arxiv.org/html/2510.05830v2)
- Secondhand: across 18 DAOs only ~17% of tokens delegated, yet top five delegates routinely capture >50% of effectively voted weight (citation garbled in source; verify) — [Frontiers in Blockchain (2026) review](https://www.frontiersin.org/journals/blockchain/articles/10.3389/fbloc.2026.1853465/full)
- Gini/Nakamoto analysis of Compound and Uniswap voting power shows high concentration — [ScienceDirect, "Analyzing voting power in decentralized governance: Who controls DAOs?"](https://www.sciencedirect.com/science/article/pii/S2096720924000216)
- Voting biases: choice position and author-selected options correlate with vote share in DAO proposals — [arXiv 2607.09435](https://arxiv.org/html/2607.09435v1)
- Preprint argues no wallet-level voting rule resists a rational sybil attacker, showing large amplification under quadratic voting ("Concave is the New Linear") — [arXiv 2605.18990](https://arxiv.org/html/2605.18990v1) (contested preprint)
- Quadratic costs make sybil splitting expensive, but richer holders still retain more power — [A Pattern Language for Blockchain Governance, arXiv 2203.00268](https://arxiv.org/pdf/2203.00268)
- Optimism's Citizens' House uses badgeholders (one citizen one vote) rather than OP weight — [Optimism blog](https://optimism.io/blog/introducing-the-citizens-house-10m-op-to-public-goods)

### Inferences
- ZUMA has an advantage most DAOs lack: verified customers (researcher attestation, order history). That makes one-member-one-vote or purchase-history-weighted voting feasible and far less sybil-prone than token weighting. A hybrid—one vote per verified member, perhaps a modest boost for streak/tenure, capped—avoids both plutocracy and turning $ZUMA into a governance-power investment.
- Tying vote weight to token balance would make buying $ZUMA a way to buy influence over supplier contracts; tying it to verified membership/purchase history removes that.
- Display factory options in randomised order and avoid "recommended" defaults to counter documented position/author bias.

### Gaps
- No sourced real-world outcome data on conviction voting (1Hive/Gardens) found in this session.
- No controlled comparisons of 1p1v vs token-weighted outcomes in commercial (non-DeFi) settings found.

---

## 8. Treasury management norms (multisig, transparency reports) for small DAOs

### Takeaway
Norms are practical rather than standardised: M-of-N multisig (Safe on EVM; Squads on Solana) for the operating treasury, hardware-wallet signers, ~60-80% thresholds, tested recovery, and documentation of every significant transaction; on Solana a common split is Squads for team treasury and Realms (SPL Governance) for community votes.

### Cited Findings
- Signer count/threshold "depends"; no single rule even for a 15-member DAO — [Safe forum: best practices for growing DAO](https://forum.safe.global/t/best-practices-for-safe-multisig-management-in-a-growing-dao/6620)
- Vendor guidance: hardware-wallet signers, approval thresholds 60-80% of signers, signers across jurisdictions, regular recovery tests (single commercial source) — [Definitive blog](https://definitive.fi/blog/how-to-manage-dao-treasury-onchain); [Multis guide](https://multis.com/post/nail-your-dao-a-guide-to-dao-treasury-management)
- Document every significant transaction (what, price, venue, why) as both a governance requirement and trust mechanism; on-chain multisig signatures provide auditable authorisation trails — [Multis](https://multis.com/post/nail-your-dao-a-guide-to-dao-treasury-management); [Elliptic corpus](https://www.elliptic.co/corpus/gen-3435/decentralized-autonomous-organization/dao-treasury-management-multisig-controls-and-on-chain-spend-monitoring.html)
- Solana: Realms is the front end for SPL Governance (proposals, configurable 3-7 day voting windows, execution delay, treasury tracking); Squads v4 is an audited M-of-N multisig that can hold program upgrade authority; common pattern = Squads for team treasury, Realms for community decisions — [Streamflow: Solana DAO tooling](https://streamflow.finance/blog/solana-dao-tooling); [madeonsol Squads guide](https://madeonsol.com/blog/how-to-use-squads-multisig-solana) (secondary/affiliate); Chainlink CCIP docs use Squads as the governance layer for token pool admin — [Chainlink docs](https://docs.chain.link/ccip/tutorials/svm/cross-chain-tokens/production-multisig-tutorial.md)

### Inferences
- For ZUMA: keep business funds in the company's normal accounts plus a Squads multisig for any on-chain token operations (mint authority, reward pools), with the token mint authority and any program upgrade authority under multisig. Publish a periodic plain-language report on token supply, rewards issued (discounts/referral boosts), and vote outcomes—not on revenue, to avoid implying holders have a claim on it.
- Member votes on factory choice can run off-chain (signed messages, Snapshot-style, or an in-app ballot tied to verified accounts) because they don't move funds; there is no need for on-chain execution.

### Gaps
- No small-DAO transparency-report template or empirical study of treasury failures in small DAOs was retrieved.

---

## 9. Regulatory framing relevant to "no revenue share / no promise of value" (context for ZUMA)

### Takeaway
The SEC's 2026 interpretive release (effective Mar 23, 2026) defines "digital tools"—memberships, tickets, credentials—as not securities when they lack passive yield or rights to income/profits and the issuer makes no representations of profit-generating managerial effort. Governance rights on their own are described as a normal feature of non-security "digital commodities." This supports ZUMA's design only if it avoids buybacks, revenue routing, and value-promising marketing.

### Cited Findings
- SEC/CFTC Release Nos. 33-11412; 34-105020, "Application of the Federal Securities Laws to Certain Types of Crypto Assets and Certain Transactions Involving Crypto Assets," effective March 23, 2026; taxonomy: digital commodities, digital collectibles, digital tools, stablecoins, digital securities — [SEC release PDF](https://www.sec.gov/files/rules/interp/2026/33-11412.pdf)
- "A digital tool is a crypto asset that performs a practical function, such as a membership, ticket, credential, title instrument, or identity badge... A digital tool does not have intrinsic economic properties or rights, such as generating a passive yield or conveying rights to future income, profits, or assets of a business enterprise" — [SEC release, §III.C](https://www.sec.gov/files/rules/interp/2026/33-11412.pdf)
- Analogy used: persons acquiring a digital tool are like those "acquiring a museum membership [who] do not expect to realize a profit from the essential managerial efforts of the museum's operators"; resale price "is based upon its functional utility" — [SEC release](https://www.sec.gov/files/rules/interp/2026/33-11412.pdf)
- Governance tokens are described as conveying voting on "software upgrades and treasury expenditures" within non-security digital commodities of functional crypto systems — [SEC release](https://www.sec.gov/files/rules/interp/2026/33-11412.pdf)
- Investment-contract analysis turns on issuer "representations or promises" to undertake essential managerial efforts; source, timing and manner of those representations matter — [SEC release §IV](https://www.sec.gov/files/rules/interp/2026/33-11412.pdf)
- Airdrops used to reward loyalty or build community are discussed as a distribution method — [SEC release](https://www.sec.gov/files/rules/interp/2026/33-11412.pdf)
- Prior 2025 staff positions: staking statement (May 29, 2025) relied on tokens lacking guaranteed yield/profit share; DePIN no-action letter (Sept 29, 2025) emphasised marketing focused on utility with no promises of passive returns; staff views are non-binding — [Jones Day](https://www.jonesday.com/en/insights/2025/06/crypto-staking-sec-staff-clarifies-nonsecurity-status-for-certain-protocol-activities); [fintechanddigitalassets.com](https://www.fintechanddigitalassets.com/2025/10/sec-staff-issues-no-action-letter-for-depin-token-distributions/)
- Courts look at the surrounding offering: in LBRY a token marketed partly for utility was still found offered as a security — [Winston & Strawn](https://www.winston.com/en/crypto-law-corner/when-it-comes-to-analyzing-utility-tokens-the-sec-staffs-framework-for-investment-contract-analysis-of-digital-assets-may-be-the-emperor-without-clothes-or-sometimes-an-orange-is-just-an-orange.html)

### Inferences
- Every value-accrual mechanism studied above (veCRV fee share, Aerodrome voter fees, Aave/Uniswap/Ethena buybacks and burns) conveys economic rights tied to protocol revenue—the opposite of the "digital tool" profile. ZUMA should adopt none of them: no buybacks, burns funded by sales, staking yield, fee share, or treasury-funded price support; no marketing of price, scarcity, or "accrual".
- Non-transferable (soul-bound) membership/streak status is explicitly cited as typical of digital tools; making the streak bonus and vote eligibility non-transferable (attached to verified accounts, not tokens) strengthens the utility framing.
- This is US-centric; ZUMA's jurisdiction and the regulatory status of research peptides are separate questions for counsel.

### Gaps
- Release's "Effective Date" confirmed; publication/announcement date and any subsequent amendments or litigation not checked.
- No legal analysis specific to referral multipliers or loyalty-token discounts retrieved; requires counsel.
