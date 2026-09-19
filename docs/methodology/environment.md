# Compute environment

The settings tag is the reproducibility anchor. It is a hash of everything that changes a simulated
value — model checkpoint SHA-256, device, dtype and the full relaxation settings — and it is appended
to every job key, so changing the protocol cannot silently reuse stale results.

| engine | role | device / dtype | settings tag | checkpoint SHA-256 |
|---|---|---|---|---|
| MACE-MPA-0 medium | primary | cpu / float32 | `c2480e74` | `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638` |
| MACE-MP-0 medium | second (disagreement check) | cpu / float64 | `207ccc81` | `01bfe22100139f424713cf921144e5509cbe353d67aa9fa1be9c6e1e0ed35845` |

The two tags differ, so one engine's results can never overwrite the other's in the results store.

## Relaxation settings hashed into the tag

```json
{
  "fmax": 0.01,
  "max_stress_gpa": 0.01,
  "max_steps": 500,
  "optimizer": "BFGS",
  "cell_filter": "FrechetCellFilter",
  "timeout_s": 900.0
}
```

## Package versions

| package | version |
|---|---|
| Python | 3.12.14 |
| mace-torch | 0.3.16 |
| torch | 2.14.0 |
| pymatgen | 2026.5.4 |
| numpy | 2.5.3 |
| scipy | 1.18.1 |
| pandas | 3.0.5 |
| ase | 3.29.0 |

Exact pins for the whole environment are in `uv.lock`.

## Hardware, and what it implies for timings

Apple M4 Max, 14 cores (10 performance / 4 efficiency), 36 GB, macOS. **CPU only** — no GPU or MPS
was used for any published result.

Observed throughput for the round-4 work: **24,000 jobs in 38.7 minutes** (12,000 structures ×
relax + static), averaging ~10.3 jobs/s across 5 workers × 2 threads. The second-engine pass over the
same 12,000 structures was a further 24,000 jobs.

Two timing caveats worth carrying, because both have caused wrong estimates in this project:

- the harness status line's ETA divides by **median** job runtime, which is dominated by the fast
  static jobs and badly underestimates a relaxation-heavy queue;
- a **perturbed or compressed starting structure costs roughly 15×** a WBM initial structure. Timings
  from one kind of job do not transfer to the other.

## Determinism

Relaxations are deterministic given (checkpoint, device, dtype, settings). Draw stratification uses
seeded sampling; the seeds for **spent** development draws are recorded in the repository's split
files, and the seeds for any future held-out draw are deliberately absent from this export — see
`reports/public/WITHHELD.md`.
