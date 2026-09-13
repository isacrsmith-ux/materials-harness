# Licensing and attribution

What this repository uses, what it redistributes, what each licence requires of us, and whether we
currently comply. Written for publication review — **no licence has been chosen for this project**;
the options are laid out at the end for the owner to decide.

Not legal advice. Where a judgement is close, it is flagged as close.

---

## 1. Data this repository redistributes

"Redistributes" means: a file in this repository contains the third party's values, not just code
that fetches them.

### 1.1 Materials Project — **CC BY 4.0, attribution required, and we currently do not give it**

| what | where |
|:--|:--|
| MP material ids, formulas, space groups, hull distances, PBE energies | `data/auto_pairs.json`, `data/auto_pairs_v1.json`, `data/unseen_test.json`, `data/polymorph_sets.json`, `data/substitution_pairs.json`, `data/substitution_candidates.csv`, `data/screening_subset.json`, `data/mode_b_sample.json` |
| MP reference energies and hull distances as comparison values | every table in `reports/`, and `results/results.parquet` if published |
| structures derived from MP PBE structures by substitution and relaxation | `data/unseen_test_run.json` (325 relaxed CIFs) |

**Licence.** Materials Project content is released under
[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/). Copying,
distribution and adaptation are permitted **provided proper attribution is given**. Derived values —
which is what almost everything above is — are adaptations and carry the same requirement.

**What CC BY 4.0 requires of us:** name the source, link the licence, state that changes were made,
and keep the notice with any redistribution. It does **not** require us to license our own code the
same way (it is not copyleft) and does not restrict commercial use.

**Compliance today: NO.** The repository cites Materials Project throughout the code and reports
(`reference_provenance: "mp_computed"`, `reference_source` per row) but has **no licence notice and
no attribution statement**. That is the one genuine licensing gap found.

**Fix:** the NOTICE block in §4, plus the citation:

> A. Jain, S.P. Ong, G. Hautier, W. Chen, W.D. Richards, S. Dacek, S. Cholia, D. Gunter, D. Skinner,
> G. Ceder, K.A. Persson, *Commentary: The Materials Project: A materials genome approach to
> accelerating materials innovation*, **APL Materials 1, 011002 (2013)**.
> doi:[10.1063/1.4812323](https://doi.org/10.1063/1.4812323)

### 1.2 WBM / Matbench Discovery — **CC BY 4.0; we redistribute only ids, which is fine**

`data/wbm_split.json` holds 8,000 WBM material ids plus our own bin labels. The WBM structures and
energies themselves live in `cache/external/wbm/`, which is **gitignored and not published** — the
README tells the reader to download them from figshare.

* **Matbench Discovery — Data Files**, Janosh Riebesell, figshare,
  doi:[10.6084/m9.figshare.22715158](https://doi.org/10.6084/m9.figshare.22715158) — **CC BY 4.0**
  (confirmed from the figshare API, v37).
* Underlying dataset: H.-C. Wang, S. Botti, M.A.L. Marques, *Predicting stable crystalline compounds
  using chemical similarity*, **npj Comput. Mater. 7, 12 (2021)**.
* Benchmark: J. Riebesell *et al.*, *Matbench Discovery*, **Nature Machine Intelligence (2025)**,
  arXiv:2308.14920.

`harness/unseen.py` also reads `2023-01-10-mp-energies.csv.gz` from the same figshare article. That
file is cached, not committed. **Compliant, provided the attribution block is added.**

### 1.3 MPtrj — **MIT; not redistributed**

Materials Project Trajectory (MPtrj) Dataset, Bowen Deng, figshare,
doi:[10.6084/m9.figshare.23713842](https://doi.org/10.6084/m9.figshare.23713842) — **MIT**. We never
downloaded it (see `reports/unseen_test.md` §2) and redistribute nothing from it. It is cited as the
training set of the engine under test.

### 1.4 Experimental lattice constants — **literature values, transcribed and cited**

| file | rows | source |
|:--|--:|:--|
| `data/experimental_lattice_constants.csv` | 40 | Lucero, Henderson & Scuseria, *J. Phys.: Condens. Matter* **24**, 145504 (2012), doi:[10.1088/0953-8984/24/14/145504](https://doi.org/10.1088/0953-8984/24/14/145504), Table I (the SC40 set) |
| `data/experimental_csonka2009.csv` | 29 | Csonka, Perdew *et al.*, *Phys. Rev. B* **79**, 155107 (2009), arXiv:0903.4037, Table II |

Both are small tables of measured physical constants transcribed from published papers, with the
citation in the file header and in `harness/suites/experimental.py`.

**Is that redistributable?** Individual measured values are facts and are not themselves
copyrightable in the US. What copyright can reach is the *selection and arrangement* of a table. We
reproduce a substantial part of the arrangement of two specific tables — 40 and 29 rows — from
papers published by IOP and APS, both of which assert copyright in the articles.

**Assessment: low risk, standard scientific practice, but it is the closest call in this document.**
Small numeric tables are reused across the DFT-benchmarking literature constantly and with citation;
these are benchmark reference sets that exist precisely to be reused. Both files already carry the
full citation and a note on what was transcribed and how.

**If you want the risk to be zero**, replace the two CSVs with a script that reconstructs them from
the papers the reader fetches themselves — the same pattern already used for WBM. That costs
reproducibility for anyone without journal access, which is why it is not recommended by default.
**Your call; not done.**

### 1.5 Model checkpoints — **not redistributed, and must stay that way**

`models/` is gitignored and contains no tracked files. `harness/config.py` pins each checkpoint by
URL and SHA-256 and the setup script downloads them.

| engine | code licence | checkpoint licence | in this repo? |
|:--|:--|:--|:--|
| MACE-MP-0 medium | MIT | MIT | URL + SHA-256 only |
| MACE-MPA-0 medium (**production engine**) | MIT | MIT | URL + SHA-256 only |
| SevenNet-Omni | MIT | MIT | URL + SHA-256 only |
| eSEN-30M-OAM | code MIT | **OMat24 licence** — commercial use permitted, subject to the FAIR acceptable-use policy; checkpoint is **gated** on Hugging Face and requires accepting terms | URL + SHA-256 only |

**Compliance: yes.** Redistributing the eSEN checkpoint would be the risky act — the gate exists so
that each user accepts the terms — and we do not. **Keep it that way:** the README must always link,
never mirror.

---

## 2. Python dependencies

Resolved from the installed package metadata, not guessed.

| package | version | licence |
|:--|:--|:--|
| pymatgen | 2026.5.4 | MIT |
| mp-api | 0.46.5 | BSD-3-Clause-LBNL |
| emmet-core | 0.87.2 | BSD-3-Clause-LBNL |
| **ase** | **3.29.0** | **LGPL-2.1-or-later** |
| mace-torch | 0.3.16 | MIT |
| e3nn | 0.4.4 | MIT |
| torch | 2.14.0 | Apache-2.0 / BSD-2 / BSD-3 / BSL-1.0 / MIT |
| numpy | 2.5.3 | BSD-3-Clause (+ 0BSD, MIT, Zlib, CC0-1.0) |
| scipy | 1.18.1 | BSD-3-Clause |
| pandas | 3.0.5 | BSD-3-Clause |
| pyarrow | 25.0.1 | Apache-2.0 |
| matplotlib | 3.11.1 | Matplotlib licence (PSF-style, BSD-compatible) |
| spglib | 2.7.0 | BSD-3-Clause |
| monty | 2026.7.16 | MIT |
| python-dotenv | 1.2.3 | BSD-3-Clause |
| tenacity | 9.1.4 | Apache-2.0 |
| pytest | 9.1.1 | MIT |

**Everything is permissive except ASE, which is LGPL-2.1-or-later — read this one.**

LGPL's obligations attach to *distributing* the library, which this repository does not do: it
declares `ase` as a dependency and the user's package manager fetches it. Your own code that imports
ASE is not made copyleft by that. The obligation bites if you later **ship a bundle** — a PyInstaller
binary, a Docker image, a vendored wheel — that contains ASE. Then you must let the recipient replace
their copy of ASE (ship the LGPL text, and either link dynamically or provide object files/source).

**For the commercial product this is the one dependency to plan around.** Either keep ASE as an
installed dependency rather than a bundled one, or check whether the relaxation loop can sit behind an
interface so ASE is swappable. Nothing to do for *this* repository.

---

## 3. Does the repository comply today?

| requirement | status |
|:--|:--|
| MP data: attribution and licence notice | ❌ **missing** — the only real gap |
| WBM / Matbench Discovery: attribution | ❌ missing (same fix) |
| Experimental tables: citation | ✅ present in the files and in the suite |
| Model checkpoints: not redistributed | ✅ URL + SHA-256 only, `models/` gitignored |
| Gated eSEN checkpoint: gate respected | ✅ not mirrored |
| Dependency licences: nothing vendored | ✅ nothing third-party is committed |
| A licence for this project's own code | ❌ **none** — see §5 |

---

## 4. NOTICE block for the README

Add verbatim (adjust once you pick a project licence):

```markdown
## Data sources and attribution

This project builds on data published by others. Every number in `reports/` is derived from one of
these sources; none of the underlying datasets or model checkpoints is redistributed here — the
setup instructions fetch them from their original homes.

- **Materials Project** — structures, energies and convex hulls, licensed
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Files under `data/` and tables in
  `reports/` contain values derived from Materials Project data; they are adaptations, and any
  further redistribution must keep this notice.
  A. Jain *et al.*, "Commentary: The Materials Project: A materials genome approach to accelerating
  materials innovation", *APL Materials* **1**, 011002 (2013). doi:10.1063/1.4812323

- **WBM dataset** — H.-C. Wang, S. Botti, M. A. L. Marques, "Predicting stable crystalline compounds
  using chemical similarity", *npj Computational Materials* **7**, 12 (2021).

- **Matbench Discovery** — benchmark and data files, licensed
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
  J. Riebesell *et al.*, *Nature Machine Intelligence* (2025), arXiv:2308.14920.
  Data files: doi:10.6084/m9.figshare.22715158

- **MPtrj** — the training set of the engine under test (not used or redistributed here).
  B. Deng *et al.*, *Nature Machine Intelligence* **5**, 1031 (2023). doi:10.6084/m9.figshare.23713842

- **Experimental lattice constants**, transcribed with citations in the file headers:
  R. A. Lucero, T. M. Henderson, G. E. Scuseria, *J. Phys.: Condens. Matter* **24**, 145504 (2012),
  Table I; and G. I. Csonka, J. P. Perdew *et al.*, *Phys. Rev. B* **79**, 155107 (2009), Table II.

- **Interatomic potentials** — MACE-MP-0 and MACE-MPA-0 (MIT), SevenNet-Omni (MIT), eSEN-30M-OAM
  (code MIT; checkpoint under the OMat24 licence and gated on Hugging Face). Checkpoints are
  downloaded by the user and pinned by SHA-256 in `harness/config.py`; none is mirrored here.

Changes were made: all values in `reports/` are computed by this harness from the above sources and
are not the sources' own published numbers.
```

---

## 5. Choosing a licence — options, and what each costs you commercially

**Not chosen. This is yours.** Context: you intend to build a commercial product on top of this work,
and the repository is a validation harness plus its reports.

### The options

| option | what others may do | what it costs you | fits when |
|:--|:--|:--|:--|
| **MIT** | anything, including closed commercial forks; must keep your notice | maximum adoption, zero leverage. A competitor can lift the harness into a closed product | you want the harness to be credibility and marketing, and the product's value is elsewhere (data, scale, service) |
| **Apache-2.0** | same as MIT | same, **plus an express patent grant and a patent-retaliation clause** — safer for you and for corporate users whose legal teams reject bare MIT | the default choice for a commercial-adjacent open release |
| **AGPL-3.0** | use and modify, but anyone offering it as a network service must publish their modifications | strong deterrent to closed forks and SaaS competitors, but **most companies ban AGPL internally** — it will cut adoption sharply, and it binds you too unless you hold all copyright and dual-license | you want the code public but not freely commercialised, and you own 100 % of it |
| **Source-available** (BUSL, PolyForm, "non-commercial") | read, audit, use non-commercially | preserves every commercial option; **not open source**, so no OSI badge, less goodwill, and academic users may not be able to use it | the harness itself is the product |
| **Reports only** | read the reports; code stays private | full control; **loses the point** — the reports' credibility rests on the code being inspectable | you only want the marketing value |

### What is actually at stake here

* **The code is a harness, not a moat.** Its value is that the numbers can be checked. A licence that
  prevents checking removes the reason to publish.
* **Nothing forces your hand.** No dependency is copyleft-in-distribution, and no input dataset
  requires share-alike — CC BY 4.0 is attribution-only. You are free to pick any of the above.
* **CC BY 4.0 does not reach your code.** MP's licence governs the data and its adaptations. It does
  require the attribution notice above to travel with the data files; it does not dictate your code
  licence.
* **Consider splitting the licence:** code under MIT or Apache-2.0, and the contents of `reports/` and
  `data/` under CC BY 4.0. That is honest about what the data already is, and it is what most
  benchmark repositories do.

**Recommendation if you want one: Apache-2.0 for the code, CC BY 4.0 for `reports/` and `data/`.**
It matches your inputs, gives corporate users the patent grant they need, and keeps the credibility
that publishing is for. It does *not* stop a competitor using the harness — no permissive licence
does — but the harness is not where a commercial moat lives.

**Whatever you choose, add:** a `LICENSE` file at the root, a one-line licence statement in the
README, and (if you split) a `data/LICENSE` and `reports/LICENSE` naming CC BY 4.0.
