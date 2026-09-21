# External-validation design note

**Nothing here has been acquired, queried or run.** This is a design assessment of candidate
independent sources outside WBM, written so that the independence question is settled *before*
anyone spends effort on a source that turns out not to be independent.

Every result this project has produced — development and held-out alike — comes from one dataset,
WBM, with one hull convention, MP2020-corrected against the Materials Project. The pnictide rule is
confirmed on held-out **WBM** data. That is a real confirmation and it is also a bounded one: it says
nothing about whether the rule holds on candidates drawn from a different generator, relaxed with
different DFT settings, or referenced against a different hull.

## The independence constraint, from our own model registry

This is the fact that disqualifies the most obvious candidate, and it is verifiable in-repo:

| engine | training data (from `harness.config.MODELS`) |
|---|---|
| MACE-MPA-0 medium (primary) | `MPtrj + sAlex (subsampled Alexandria, WBM-overlapping structures removed)` |
| MACE-MP-0 medium (second) | `MPtrj (Materials Project PBE/PBE+U relaxation trajectories, 2022.9)` |

So **Alexandria is training data for the primary engine**, and **Materials Project relaxation
trajectories are training data for both**. A validation source overlapping either is not measuring
generalisation; it is measuring memorisation. The registry notes that WBM-overlapping structures were
removed from sAlex — that protects WBM as a test set, not Alexandria as one.

## Candidate sources

Licensing and population figures below are marked **unverified** wherever I have not retrieved them
from the source in this session. This follows the rule the reference-data collection already runs on:
no value is written from recall. Verify each before acquisition, and record the date checked.

### 1. Targeted DFT campaign (our own calculations)

| | |
|---|---|
| independence | **Complete.** We choose the candidates, the settings and the reference. No overlap with any training set by construction. |
| provenance | Ours, fully controlled and reproducible. |
| licensing | Ours. No redistribution constraint. |
| usable population | Whatever we pay for. A few hundred structures is a realistic first campaign. |
| what it could validate | Everything, including the claims no public source can: that a rule holds on candidates *we* generate rather than ones someone else curated, and the fluoride question that WBM cannot answer. |
| cost | The only real monetary cost on this list. Compute hours, and someone's time to set up and converge a consistent DFT protocol. |

**The gold standard, and the only source here that is unambiguously independent.** Its weakness is
size: a few hundred structures cannot certify a stable side whose call rate is 5–10%.

### 2. OQMD (Open Quantum Materials Database)

| | |
|---|---|
| independence | **Probably good, needs verification.** Not named in either engine's training data. Independent DFT settings and an independent hull construction. |
| overlap risk | Moderate and checkable: OQMD and MP share many ICSD-derived prototypes, so overlap must be measured by reduced formula *and* prototype, not assumed absent. Compositions already in MPtrj are contaminated even if OQMD's own calculation is independent. |
| provenance | Published, versioned, citable. |
| licensing | **Unverified.** Check the current terms before downloading anything. |
| usable population | Large (order 10⁵–10⁶ entries), but the usable fraction after removing MPtrj-overlapping compositions is the real number and is **unknown until measured**. |
| what it could validate | Whether a threshold holds under a *different DFT protocol and hull* — the single most valuable thing after a DFT campaign, because it tests the convention, not just the sample. |

**The strongest public candidate.** The catch is that a different hull convention changes the label
definition, so a disagreement would be genuinely ambiguous between "the rule fails" and "the two
hulls disagree". That ambiguity has to be designed for up front — e.g. by quantifying hull
disagreement on the *overlap* first, on compositions where both databases have an answer.

### 3. Materials Project additions after the training cutoff

| | |
|---|---|
| independence | **Partial at best.** MPtrj is MP's own relaxation trajectories, and MP is our hull reference. Only materials added after the 2022.9 cutoff are candidates, and even they are referenced against the same hull the engines were trained toward. |
| overlap risk | High for anything at or before the cutoff; must be filtered by MP addition date, not by id. |
| provenance | Excellent — versioned, DOI'd, API-accessible. |
| licensing | **CC BY 4.0** (already recorded in `NOTICE` for MP). Redistribution of derived aggregates is fine with attribution; we do not redistribute source data. |
| usable population | Small. Post-cutoff additions in any one family will be in the hundreds, not thousands. |
| what it could validate | A weak replication on new-but-same-convention data. Useful as a cheap sanity check, not as an independence claim. |

There is prior art here: the project already built an MP "unseen test" of **325** materials
(`data/unseen_test.json`, opened once on 2026-09-12) on exactly this logic. That n is the honest
indication of scale.

### 4. AFLOW

| | |
|---|---|
| independence | **Plausible, unverified.** Not in either engine's training data as recorded. |
| overlap risk | Same ICSD-prototype overlap problem as OQMD, plus AFLOW's own prototype-decoration approach may produce candidates structurally close to WBM's elemental-substitution ones. Worth measuring before trusting. |
| provenance | Published and citable. |
| licensing | **Unverified.** |
| usable population | Large, unknown after filtering. |
| what it could validate | Similar ground to OQMD, with a generator whose bias may be closer to WBM's — which makes it a weaker independence test than OQMD, not a stronger one. |

### 5. Experimental structure databases (COD, ICSD)

| | |
|---|---|
| independence | **Excellent for existence, irrelevant for hull distance.** |
| overlap risk | Low for the claim they can support. |
| provenance | Strong; COD entries carry per-row DOIs. |
| licensing | **COD: CC0 1.0, verified** and already vendored under `reference_data/raw/cod/`. **ICSD: commercial licence — cannot be redistributed, and may not be queryable at all without a subscription.** |
| usable population | Thousands of oxides already accessible via COD. |
| what it could validate | **A different claim.** "This compound has been synthesised" is not "this compound is within 0.025 eV/atom of the convex hull". A synthesised material can sit above the hull; an on-hull material may never have been made. |

Worth being explicit: this source cannot validate the routing rules. It could validate something
adjacent and still valuable — that candidates the harness calls *likely stable* are enriched in
experimentally-known compounds — but that is a new claim needing its own pre-registration, not a
substitute for a held-out test.

### 6. Recent literature syntheses

Rejected as a primary source. Sample sizes are tiny, selection is driven by publication interest, and
positive results are over-represented. Useful only as anecdote.

## What the sources can and cannot be asked

| claim | can a public source validate it? |
|---|---|
| the pnictide rule generalises to a different DFT protocol / hull | **OQMD, with the hull-disagreement problem designed for first** |
| a rule generalises to differently-generated candidates | **Targeted DFT campaign**; AFLOW only weakly |
| the fluoride question WBM cannot answer | **Targeted DFT campaign only** — 429 unspent WBM fluorides is not enough, and Alexandria is training data |
| *likely stable* calls are enriched in known compounds | COD, as a new and weaker claim |
| a cheap replication on new same-convention data | post-cutoff MP additions, at a few hundred structures |

## Recommended order, if this is ever pursued

1. **Measure overlap before acquiring anything.** For OQMD and AFLOW, quantify the reduced-formula
   and prototype overlap with MPtrj and with WBM. A source is only independent to the extent that
   number is small, and the number is currently unknown.
2. **Quantify hull disagreement on the overlap**, so a later disagreement can be attributed to the
   rule rather than the convention.
3. **Only then** size and pre-register an external evaluation, with its own held-out half.
4. A targeted DFT campaign is the only route to the claims nothing public can support, and is the
   only item here with a real monetary cost. It should be scoped against a specific question — most
   plausibly fluoride — rather than commissioned in general.

**Nothing in this note authorises acquisition.** Every licence marked unverified must be read from
the source, in-session, with the date recorded, before a byte is downloaded.
