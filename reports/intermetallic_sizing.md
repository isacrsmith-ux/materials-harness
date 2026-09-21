# Track 1 — intermetallic sizing (analysis only)

Generated 2026-09-21T21:33:40+00:00. **Nothing was drawn and nothing was pre-registered.** This asks whether an independent test of the proposed intermetallic rule could distinguish pass from fail at a size the remaining pool can supply, before any fresh candidate is spent.

Procedure is the one a held-out evaluation would use, identical to the pnictide evaluation: one-sided Clopper-Pearson at **0.9875** (Bonferroni over 4 hypotheses), **no grid correction** (thresholds would be fixed in advance), **no family correction** (one family tested). Targets: stable precision 0.90, unstable NPV 0.95.

## The development starting point

| hypothesis | proposed rule | calls | errors | point | dev bound | target | dev margin |
|---|---|---:|---:|---:|---:|---:|---:|
| IA1 Path-A stable | -20 meV | 182 | 4 | 0.9780 | 0.9197 | 0.9 | **+0.0197** |
| IA2 Path-A unstable | -10 meV | 3,365 | 115 | 0.9658 | 0.9548 | 0.95 | **+0.0048** |
| IB1 Path-B stable | -20 meV | 181 | 4 | 0.9779 | 0.9193 | 0.9 | **+0.0193** |
| IB2 Path-B unstable | -10 meV | 3,300 | 115 | 0.9652 | 0.9539 | 0.95 | **+0.0039** |

The two unstable-side rows are the problem this analysis exists for: they clear their target by **+0.0048 and +0.0039** on the very data the thresholds were selected on, which is the most optimistic estimate available.

## Required size, powered against the development point estimate

| hypothesis | truth assumed | calls/structure | 80% power | 90% power | 95% power |
|---|---:|---:|---|---|---|
| IA1 Path-A stable | 0.9780 | 0.04550 | 2,066 str | 2,726 str | 3,033 str |
| IA2 Path-A unstable | 0.9658 | 0.84125 | 1,887 str | 2,424 str | 2,928 str |
| IB1 Path-B stable | 0.9779 | 0.04525 | 2,078 str | 2,741 str | 3,050 str |
| IB2 Path-B unstable | 0.9652 | 0.82500 | 2,145 str | 2,716 str | 3,307 str |

Unspent intermetallic pool: **33,707** candidates.

## Sensitivity — the question that actually decides feasibility

A study is only worth running if it can separate pass from fail at the truth values that are actually plausible. The development point estimate is the optimistic end of that range; the development *bound* is the pessimistic end. Both are plausible.

### IA1 Path-A stable (rule -20 meV, target 0.9)

| assumed true value | effect size vs target | 80% power | 90% power | feasible within pool? |
|---:|---:|---|---|---|
| 0.9000 | +0.0000 | not reachable | not reachable | **no** |
| 0.9200 *(development bound)* | +0.0200 | 43,495 | 56,264 | **no** |
| 0.9400 | +0.0400 | 9,957 | 12,792 | yes |
| 0.9600 | +0.0600 | 3,957 | 5,099 | yes |
| 0.9780 | +0.0780 | 2,066 | 2,726 | yes |
| 0.9800 | +0.0800 | 2,066 | 2,418 | yes |
| 0.9900 | +0.0900 | 1,363 | 1,737 | yes |

### IA2 Path-A unstable (rule -10 meV, target 0.95)

| assumed true value | effect size vs target | 80% power | 90% power | feasible within pool? |
|---:|---:|---|---|---|
| 0.9500 | +0.0000 | not reachable | not reachable | **no** |
| 0.9550 *(development bound)* | +0.0050 | 20,669 | 26,825 | yes |
| 0.9600 | +0.0100 | 5,058 | 6,593 | yes |
| 0.9650 | +0.0150 | 2,103 | 2,717 | yes |
| 0.9658 | +0.0158 | 1,887 | 2,424 | yes |
| 0.9700 | +0.0200 | 1,114 | 1,450 | yes |
| 0.9750 | +0.0250 | 679 | 885 | yes |

### IB1 Path-B stable (rule -20 meV, target 0.9)

| assumed true value | effect size vs target | 80% power | 90% power | feasible within pool? |
|---:|---:|---|---|---|
| 0.9000 | +0.0000 | not reachable | not reachable | **no** |
| 0.9200 | +0.0200 | 43,735 | 56,575 | **no** |
| 0.9400 | +0.0400 | 10,012 | 12,862 | yes |
| 0.9600 | +0.0600 | 3,978 | 5,128 | yes |
| 0.9779 | +0.0779 | 2,078 | 2,741 | yes |
| 0.9800 | +0.0800 | 2,078 | 2,431 | yes |
| 0.9900 | +0.0900 | 1,371 | 1,746 | yes |

### IB2 Path-B unstable (rule -10 meV, target 0.95)

| assumed true value | effect size vs target | 80% power | 90% power | feasible within pool? |
|---:|---:|---|---|---|
| 0.9500 | +0.0000 | not reachable | not reachable | **no** |
| 0.9550 | +0.0050 | 21,076 | 27,353 | yes |
| 0.9600 | +0.0100 | 5,158 | 6,723 | yes |
| 0.9650 | +0.0150 | 2,145 | 2,770 | yes |
| 0.9652 | +0.0152 | 2,089 | 2,689 | yes |
| 0.9700 | +0.0200 | 1,136 | 1,478 | yes |
| 0.9750 | +0.0250 | 693 | 902 | yes |

## Power at candidate draw sizes (development point estimates)

| n drawn | IA1 | IA2 | IB1 | IB2 | worst case |
|---:|---:|---:|---:|---:|---:|
| 2,000 | 0.677 | 0.828 | 0.680 | 0.753 | **0.677** |
| 2,500 | 0.893 | 0.897 | 0.894 | 0.875 | **0.875** |
| 2,750 | 0.941 | 0.935 | 0.942 | 0.903 | **0.903** |
| 3,000 | 0.919 | 0.950 | 0.918 | 0.924 | **0.918** |
| 3,500 | 0.975 | 0.976 | 0.975 | 0.962 | **0.962** |
| 4,000 | 0.993 | 0.991 | 0.993 | 0.982 | **0.982** |

Power is not monotone in n: the number of allowed errors is an integer, so it sawtooths (2,750 beats 3,000 on the stable side). That is why a size should be read off this table rather than from a single power target.

### Recommended: n = 3,500 if this is ever pre-registered

At 3,500 drawn structures every hypothesis has power >= 0.96 against the development point estimates, and 30,207 candidates would remain unspent. Expected calls and error budgets:

| hypothesis | expected calls | expected errors | max errors allowed |
|---|---:|---:|---:|
| IA1 Path-A stable | 159 | 3.5 | 7 |
| IA2 Path-A unstable | 2,944 | 100.6 | 120 |
| IB1 Path-B stable | 158 | 3.5 | 7 |
| IB2 Path-B unstable | 2,888 | 100.6 | 118 |

### What this design could NOT settle

The binding constraint is **not** the thin unstable-side margin. It is the stable side's call rate: only about 4.5% of drawn structures become a stable call, against 82-84% for the unstable side. The unstable side's margin is thin but its *effect size* is large (0.0152-0.0158 above target), and effect size is what drives power.

The real limit is the pessimistic branch. If intermetallic's true stable precision were 0.9200 - the development lower bound, and entirely plausible - certifying it would need roughly **43,500 structures at 80% power**, which exceeds the whole remaining pool of 33,707. On the unstable side a true value at the development bound (0.9550) would need about 20,700, which the pool can just afford but which is seven times the recommended draw.

So a pass at n = 3,500 would mean the rule behaves as development suggested. A failure would be genuinely ambiguous: it could not distinguish 'the rule is worse than development implied' from 'the truth is in the 0.92-0.96 band where this size has no power'. That asymmetry should be written into any pre-registration before the draw, not discovered afterwards.

Neither the stable nor the unstable side can be certified if the truth sits exactly at target: at an effect size of zero no finite sample clears a one-sided bound, which is why the 0.9000 and 0.9500 rows read 'not reachable'. That is arithmetic, not pessimism.

