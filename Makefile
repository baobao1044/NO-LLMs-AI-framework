.PHONY: test replay regress mine gen-tasks gen-ts-tasks backlog select-backlog quality refresh daily daily-ab daily-full merge-logs dedup-report ci changelog training-day training-full training-247 training-247-once train train-status

CONFIG ?= configs/daily_config.json
PROPOSER_POLICY_B ?= configs/proposer_policy_training_v1.json
TRAINING_CONFIG ?= configs/daily_training_v1.json
TRAINING_PROPOSER_POLICY ?= configs/proposer_policy_training_v1.json
FULL_TRAINING_CONFIG ?= configs/daily_training_full.json
FULL_TRAINING_PROPOSER_POLICY ?= configs/proposer_policy_training_full.json
DEFAULT_LOCAL_PROPOSER_COMMAND ?= python3 tools/proposer_rule_adapter.py

test:
	python3 -m unittest discover -s tests -p "test_*.py"

replay:
	python3 tools/replay.py logs/agent_runs.jsonl --json-out reports/replay_metrics.json

regress:
	python3 tools/regress.py --golden-set configs/golden_set.json --baseline configs/regression_baseline.json
	python3 tools/regress.py --golden-set configs/ts_golden_set.json --baseline configs/ts_regression_baseline.json

mine:
	python3 tools/patch_mining.py --log logs/agent_runs.jsonl --top-k 50 --min-count 3
	python3 tools/build_patch_backlog.py --log logs/agent_runs.jsonl --language all --top-k 50 --min-count 3

gen-tasks:
	python3 tools/generate_tasks.py --out configs/tasks_generated.json --seed 123 --count 20

gen-ts-tasks:
	python3 tools/generate_tasks.py --out configs/ts_generated_tasks.json --seed 123 --count 20 --templates ts_union_narrowing,ts_optional_chaining,ts_generic_identity,ts_record_shape,ts_null_undefined_strict --tag generated

backlog:
	python3 tools/build_patch_backlog.py --log logs/agent_runs.jsonl --language all --top-k 50 --min-count 3 --out configs/patch_backlog_all.json

select-backlog:
	python3 tools/pick_backlog_items.py --backlog configs/patch_backlog_all.json --policy configs/backlog_policy.json --out configs/backlog_selected.json

quality:
	[ -s logs/agent_runs.jsonl ] || python3 examples/add_task_demo.py > /dev/null
	python3 tools/collect_quality_metrics.py --log logs/agent_runs.jsonl --out reports/metrics_before.json --allow-missing
	$(MAKE) test
	$(MAKE) regress
	$(MAKE) mine
	python3 tools/stats.py logs/agent_runs.jsonl > reports/stats_after.txt
	python3 tools/replay.py logs/agent_runs.jsonl --json-out reports/replay_metrics.json
	python3 tools/collect_quality_metrics.py --log logs/agent_runs.jsonl --out reports/metrics_after.json --allow-missing
	python3 tools/patcher_quality_gate.py --before reports/metrics_before.json --after reports/metrics_after.json --max_pass_rate_drop 0.01 --max_timeout_increase 0.01 --max_flaky_increase 0 --min_coverage_gain 0

refresh:
	[ -s logs/agent_runs.jsonl ] || python3 examples/add_task_demo.py > /dev/null
	python3 tools/collect_quality_metrics.py --log logs/agent_runs.jsonl --out reports/metrics_before_refresh.json --allow-missing
	$(MAKE) mine
	$(MAKE) backlog
	$(MAKE) select-backlog
	python3 tools/stats.py logs/agent_runs.jsonl > reports/stats_refresh.txt
	python3 tools/collect_quality_metrics.py --log logs/agent_runs.jsonl --out reports/metrics_after_refresh.json --allow-missing
	python3 tools/build_progress_report.py --before reports/metrics_before_refresh.json --after reports/metrics_after_refresh.json --patchers ts_ts2322_number_return_patcher

merge-logs:
	python3 tools/merge_logs.py "runs/*/agent_runs.jsonl" --out logs/merged.jsonl

dedup-report:
	python3 tools/dedup_report.py logs/merged.jsonl --json-out reports/dedup_report.json

daily-ab:
	DAY=$$(date -u +%Y%m%d); \
	python3 tools/run_daily.py --config $(CONFIG) --date $$DAY --ab --proposer-policy-b $(PROPOSER_POLICY_B); \
	echo "daily_reports=reports/$$DAY"; \
	echo "daily_runs=runs/$${DAY}_A,runs/$${DAY}_B"

daily-full:
	DAY=$$(date -u +%Y%m%d); \
	CODEX_PROPOSER_COMMAND="$${CODEX_PROPOSER_COMMAND:-$(DEFAULT_LOCAL_PROPOSER_COMMAND)}" \
	python3 tools/run_daily.py --config $(FULL_TRAINING_CONFIG) --date $$DAY --ab --proposer-policy-b $(FULL_TRAINING_PROPOSER_POLICY); \
	echo "daily_reports=reports/$$DAY"; \
	echo "daily_runs=runs/$${DAY}_A,runs/$${DAY}_B"

daily: daily-ab
	DAY=$$(date -u +%Y%m%d); \
	$(MAKE) refresh; \
	$(MAKE) quality; \
	$(MAKE) regress; \
	python3 tools/replay.py logs/agent_runs.jsonl --json-out reports/$$DAY/replay_metrics.json; \
	python3 tools/build_daily_summary.py --before reports/metrics_before_refresh.json --after reports/metrics_after_refresh.json --out reports/$$DAY/daily_metrics_summary.json

ci:
	python3 tools/ci_gate.py

changelog:
	python3 tools/build_changelog.py

training-day:
	$(MAKE) daily-ab CONFIG=$(TRAINING_CONFIG) PROPOSER_POLICY_B=$(TRAINING_PROPOSER_POLICY)
	$(MAKE) merge-logs
	$(MAKE) dedup-report
	$(MAKE) refresh
	$(MAKE) ci
	DAY=$$(date -u +%Y%m%d); \
	echo "training_reports=reports/$$DAY"; \
	echo "training_runs=runs/$${DAY}_A,runs/$${DAY}_B"; \
	echo "training_ab_compare=reports/$$DAY/ab_compare.json"

training-full:
	CODEX_PROPOSER_COMMAND="$${CODEX_PROPOSER_COMMAND:-$(DEFAULT_LOCAL_PROPOSER_COMMAND)}" \
	$(MAKE) training-day TRAINING_CONFIG=$(FULL_TRAINING_CONFIG) TRAINING_PROPOSER_POLICY=$(FULL_TRAINING_PROPOSER_POLICY)

training-247:
	CODEX_PROPOSER_COMMAND="$${CODEX_PROPOSER_COMMAND:-$(DEFAULT_LOCAL_PROPOSER_COMMAND)}" \
	python3 tools/run_training_247.py --config $(FULL_TRAINING_CONFIG) --policy-b $(FULL_TRAINING_PROPOSER_POLICY)

training-247-once:
	CODEX_PROPOSER_COMMAND="$${CODEX_PROPOSER_COMMAND:-$(DEFAULT_LOCAL_PROPOSER_COMMAND)}" \
	python3 tools/run_training_247.py --config $(FULL_TRAINING_CONFIG) --policy-b $(FULL_TRAINING_PROPOSER_POLICY) --once

train:
	CODEX_PROPOSER_COMMAND="$${CODEX_PROPOSER_COMMAND:-$(DEFAULT_LOCAL_PROPOSER_COMMAND)}" \
	python3 tools/run_training_247.py --config $(FULL_TRAINING_CONFIG) --policy-b $(FULL_TRAINING_PROPOSER_POLICY) --sleep-seconds 5 --ci-every 0

train-status:
	python3 tools/training_status.py
