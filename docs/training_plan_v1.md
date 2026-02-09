# Training Plan v1

## Principles

- verifier-first
- deterministic replay
- CPU-first
- no baseline updates during first 7 observation days

## Ramp Schedule

- Week 1: `50` tasks/day
- Week 2: `100` tasks/day
- Week 3: `200` tasks/day

Use `configs/daily_training_v1.json` as the starting profile and increase:

- `generated_task_count`
- `max_tasks_per_day`
- `max_total_seconds`

Keep `max_attempts_per_task` bounded (`<= 8`) to avoid runaway loops.

## Stop Conditions

Stop ramp or auto-disable proposer when any condition is hit:

- timeout rate increase > `1%`
- flaky groups increase > `0`
- replay mismatch > `0`
- env fingerprint mismatch > `0`

## Daily Execution

```bash
make training-day
```

This performs:

1. daily A/B run
2. log merge + dedup report
3. refresh analytics
4. CI governance gate

## Baseline Discipline

For the first 7 days:

- do not update `configs/regression_baseline.json`
- do not update `configs/ts_regression_baseline.json`

Only allow baseline update after all of these hold:

- signature coverage increases
- top uncovered signatures decrease
- A/B shows proposer mode better without timeout/flaky regressions
