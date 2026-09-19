# What this export deliberately withholds, and why

Publishing a reproducible result must not destroy the ability to test it later. Held-out evaluation
depends on a population that has never influenced a fitting decision, so some information is
withheld on purpose. This document is the complete list.

## Withheld

| withheld | why |
|---|---|
| **All material identifiers.** No WBM id appears anywhere in `results/public/` or `reports/public/`. | Publishing the ids of *spent* development structures would, by complement against the public WBM pool, narrow the set of candidates still eligible for future held-out draws. |
| **The pnictide held-out sample.** | It does not exist. The protocol is frozen; no id has been selected. There is no membership to leak because there is no membership. |
| **The eligible-candidate pool for future draws** — neither its ids nor its size broken down in a way that would let it be reconstructed. | This is the population a future held-out test must come from. |
| **Random seeds for any future draw.** | A seed plus a documented stratification rule plus the public pool reconstructs the sample exactly. The seeds of *spent* development draws are already in the repository's split files, which is harmless because those structures can never serve as held-out data again. |
| **Per-bin draw counts.** | Combined with a stratification rule these narrow reconstruction. Base rates are published; the per-bin counts they came from are not. |
| **Row-level results.** Every published record aggregates at least 20 rows. | A per-material table is a label lookup for whatever ids it covers. |
| **Source datasets.** No WBM or Materials Project structures, energies or hulls. | Redistribution is not ours to grant in the form the licences contemplate, and it is unnecessary: retrieval instructions and DOIs are published instead. See `docs/methodology/data_provenance.md`. |
| **Model checkpoints.** | MIT-licensed and redistributable in principle, but large and already canonically hosted. SHA-256 values and download URLs are published so a reader can verify they have the same weights. |
| **NIST Standard Reference Data values.** | Copyrighted under 15 U.S.C. §290e. Cite-and-locator only. |
| **`.env`, API keys, tokens, local filesystem paths, email addresses.** | Never committed; the preflight check scans the full history for them on every run. |

## Published even though it is unflattering

Withholding is for protecting future tests and honouring licences. It is not for tidying results.
Published in full:

- **f-electron lost its stable certification** on a fresh, composition-matched development draw. The
  live production rule scored a corrected bound of 0.8944 against a 0.90 target.
- **The apparent second-engine rescue of f-electron does not survive** the family-level multiplicity
  correction: the bound falls to **0.892556**, a margin of −0.0074. f-electron is unresolved.
- **Supplying a second engine makes the product measurably worse** across these three families,
  more than doubling the share of candidates routed to DFT.
- **intermetallic's unstable-side margin is +0.0039**, which is thin enough that it is flagged rather
  than reported as a clean pass.
- Every population count, exclusion and the count of rows that pass the disagreement check untested.

## A disclosure about the existing repository

This export adds no identifiers. But the repository's **already-public history** contains the
identifier lists of held-out sets that have not been opened: the round-1 oxide half (2,000), the
round-2 sulfide half (874), and the two round-3 residual halves (1,500 each).

That exposure predates this export and is not created by it. Its practical significance is limited —
WBM is a public dataset, so the true labels for any id were always publicly derivable, and the
integrity of a held-out evaluation here rests on committed preregistrations, recorded hashes and
one-time opening logs rather than on the ids being secret. A reader can audit that chain
independently, which is the stronger guarantee.

It is nonetheless a real weakness in the design and is recorded here rather than left for someone to
discover. Anyone planning to rely on those specific halves as *independent* evidence should know
their membership has been public.
