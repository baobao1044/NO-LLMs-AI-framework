.PHONY: test replay regress mine gen-tasks gen-ts-tasks backlog select-backlog quality refresh daily merge-logs dedup-report

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

daily:
	DAY=$$(date -u +%Y%m%d); \
	python3 tools/run_daily.py --config configs/daily_config.json --date $$DAY; \
	$(MAKE) refresh; \
	$(MAKE) quality; \
	$(MAKE) regress; \
	python3 tools/replay.py logs/agent_runs.jsonl --json-out reports/$$DAY/replay_metrics.json; \
	python3 tools/build_daily_summary.py --before reports/metrics_before_refresh.json --after reports/metrics_after_refresh.json --out reports/$$DAY/daily_summary.json
