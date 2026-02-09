# Patch Backlog

## Summary

- source_log: logs/agent_runs.jsonl
- language_filter: all
- total_candidates: 4
- backlog_items: 4

## Top Priorities

- priority=4.0000 | py | assertion_fail | unit_test | AssertionError:case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[] (count=4, solve=0.000, patch_hit=0.250, patch_success=0.000, category=other)
  task_id=gen_regex_findall_86483f0e5840 artifact_hash=3b042e7a743017052da2b03a78ed3a2de5d12b379cb8b56846a904f4e401a375 parent=9791981e01b7dd8a1f6a3d6cf0433641916c4f63f7575381e4a89b097d4b5828
  error=case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[]
  task_id=gen_regex_findall_86483f0e5840 artifact_hash=9791981e01b7dd8a1f6a3d6cf0433641916c4f63f7575381e4a89b097d4b5828 parent=9938f7d1146256ed7946350802f412b8b34b4c3bb7fdb231173748860bd88265
  error=case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[]
- priority=0.0000 | ts | assertion_fail | unit_test | AssertionError:case 2 mismatch: expected="" actual=undefined (count=12, solve=1.000, patch_hit=0.000, patch_success=0.000, category=other)
  task_id=gen_ts_optional_chaining_c8c8cb42d012 artifact_hash=d03b7f4725e00b2bdc70e8cd519bacfb77dbee26bf488db613574ce89334913c parent=None
  error=case 2 mismatch: expected="" actual=undefined
- priority=0.0000 | ts | runtime_error | unit_test | RuntimeError:case 2 raised TypeError: Cannot read properties of null (reading 'trim') (count=12, solve=1.000, patch_hit=0.000, patch_success=0.000, category=other)
  task_id=gen_ts_null_undefined_strict_3859896f583b artifact_hash=5b1f272871b1654b3fd88f848b573b980f830c73f307952bbe814b9d4b82cdf0 parent=None
  error=case 2 raised TypeError: Cannot read properties of null (reading 'trim')
- priority=0.0000 | ts | ts_syntax_error | tsc | TS1005:<path> (count=12, solve=1.000, patch_hit=0.000, patch_success=0.000, category=syntax_fix)
  task_id=gen_ts_generic_identity_8995ee15cd40 artifact_hash=e3f89faa50ba2dc8fda5a6292eb8f470314ada877569c1505bb760942b658063 parent=None
  error=<path>
