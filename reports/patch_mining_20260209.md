# Patch Mining Report

## Summary

- total_records: 242
- eligible_records: 123
- solved_records: 118
- overall_solve_rate: 95.9350%
- language_breakdown:
  py: eligible=20 solved=15 solve_rate=75.0000%
  ts: eligible=36 solved=36 solve_rate=100.0000%

## Top Groups By Count

- ts | assertion_fail | unit_test | AssertionError:case 2 mismatch: expected="" actual=undefined (count=12, solve_rate=100.0000%, patch_hit_rate=0.0000%, patch_success_rate=0.0000%)
- ts | runtime_error | unit_test | RuntimeError:case 2 raised TypeError: Cannot read properties of null (reading 'trim') (count=12, solve_rate=100.0000%, patch_hit_rate=0.0000%, patch_success_rate=0.0000%)
- ts | ts_syntax_error | tsc | TS1005:<path> (count=12, solve_rate=100.0000%, patch_hit_rate=0.0000%, patch_success_rate=0.0000%)
- py | runtime_error | unit_test | NameError:case 1 raised name 'json' is not defined (count=8, solve_rate=100.0000%, patch_hit_rate=100.0000%, patch_success_rate=100.0000%)
- py | runtime_error | unit_test | NameError:case 1 raised name 're' is not defined (count=8, solve_rate=87.5000%, patch_hit_rate=100.0000%, patch_success_rate=87.5000%)
- py | assertion_fail | unit_test | AssertionError:case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[] (count=4, solve_rate=0.0000%, patch_hit_rate=25.0000%, patch_success_rate=0.0000%)

## Low Solve-Rate Groups

- py | assertion_fail | unit_test | AssertionError:case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[] (count=4, solve_rate=0.0000%)
- py | runtime_error | unit_test | NameError:case 1 raised name 're' is not defined (count=8, solve_rate=87.5000%)
- ts | assertion_fail | unit_test | AssertionError:case 2 mismatch: expected="" actual=undefined (count=12, solve_rate=100.0000%)
- ts | runtime_error | unit_test | RuntimeError:case 2 raised TypeError: Cannot read properties of null (reading 'trim') (count=12, solve_rate=100.0000%)
- ts | ts_syntax_error | tsc | TS1005:<path> (count=12, solve_rate=100.0000%)
- py | runtime_error | unit_test | NameError:case 1 raised name 'json' is not defined (count=8, solve_rate=100.0000%)

## Suggested Patchers

### py | assertion_fail | unit_test | AssertionError:case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[]

- patchers_tried: missing_import_patcher
- top_patchers: none
- notes: prioritize deterministic patcher for this signature group.
- examples:
  task_id=gen_regex_findall_86483f0e5840 artifact_hash=3b042e7a743017052da2b03a78ed3a2de5d12b379cb8b56846a904f4e401a375 parent=9791981e01b7dd8a1f6a3d6cf0433641916c4f63f7575381e4a89b097d4b5828
  prompt=Write regex_findall(pattern, text) returning re.findall result.
  error_message=case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[]
  code=import re def regex_findall(pattern, text): return re.findall(pattern, text)
  task_id=gen_regex_findall_86483f0e5840 artifact_hash=9791981e01b7dd8a1f6a3d6cf0433641916c4f63f7575381e4a89b097d4b5828 parent=9938f7d1146256ed7946350802f412b8b34b4c3bb7fdb231173748860bd88265
  prompt=Write regex_findall(pattern, text) returning re.findall result.
  error_message=case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[]
  code=import re def regex_findall(pattern, text): return re.findall(pattern, text)
  task_id=gen_regex_findall_86483f0e5840 artifact_hash=5254718768db155414ec8a1ee4335481b25a0d108c5906deee4f4b52efbdf6ca parent=None
  prompt=Write regex_findall(pattern, text) returning re.findall result.
  error_message=case 1 mismatch: args=('\\\\d+', 'a1 b22 c333'), expected=['1', '22', '333'], actual=[]
  code=import re def regex_findall(pattern, text): return re.findall(pattern, text)

### py | runtime_error | unit_test | NameError:case 1 raised name 're' is not defined

- patchers_tried: missing_import_patcher
- top_patchers: missing_import_patcher(7)
- notes: prioritize deterministic patcher for this signature group.
- examples:
  task_id=gen_regex_findall_91cbf71c79b6 artifact_hash=9938f7d1146256ed7946350802f412b8b34b4c3bb7fdb231173748860bd88265 parent=None
  prompt=Write regex_findall(pattern, text) returning re.findall result.
  error_message=case 1 raised name 're' is not defined
  code=def regex_findall(pattern, text): return re.findall(pattern, text)

### ts | assertion_fail | unit_test | AssertionError:case 2 mismatch: expected="" actual=undefined

- patchers_tried: none
- top_patchers: none
- notes: prioritize deterministic patcher for this signature group.
- examples:
  task_id=gen_ts_optional_chaining_c8c8cb42d012 artifact_hash=d03b7f4725e00b2bdc70e8cd519bacfb77dbee26bf488db613574ce89334913c parent=None
  prompt=Write pick_user_name(input) using optional chaining; return empty string when missing.
  error_message=case 2 mismatch: expected="" actual=undefined
  code=export function pick_user_name(input: { user?: { name?: string } } | null): string { return input.user.name; }

### ts | runtime_error | unit_test | RuntimeError:case 2 raised TypeError: Cannot read properties of null (reading 'trim')

- patchers_tried: none
- top_patchers: none
- notes: prioritize deterministic patcher for this signature group.
- examples:
  task_id=gen_ts_null_undefined_strict_3859896f583b artifact_hash=5b1f272871b1654b3fd88f848b573b980f830c73f307952bbe814b9d4b82cdf0 parent=None
  prompt=Write normalize_text(value) returning trimmed string or empty for null/undefined.
  error_message=case 2 raised TypeError: Cannot read properties of null (reading 'trim')
  code=export function normalize_text(value: string | null | undefined): string { return value.trim(); }

### ts | ts_syntax_error | tsc | TS1005:<path>

- patchers_tried: none
- top_patchers: none
- notes: prioritize deterministic patcher for this signature group.
- examples:
  task_id=gen_ts_generic_identity_8995ee15cd40 artifact_hash=e3f89faa50ba2dc8fda5a6292eb8f470314ada877569c1505bb760942b658063 parent=None
  prompt=Write generic identity(value) preserving input type and value.
  error_message=<path>
  code=export function identity<T>(value: T): T { return undefined as unknown as T; }

### py | runtime_error | unit_test | NameError:case 1 raised name 'json' is not defined

- patchers_tried: missing_import_patcher
- top_patchers: missing_import_patcher(8)
- notes: prioritize deterministic patcher for this signature group.
- examples:
  task_id=gen_parse_json_field_1a909db8b8dc artifact_hash=0737e30e5b505a45ab038a46402c90650d952434fc9510b104ce673056194b65 parent=None
  prompt=Write parse_json_field(s, key) to return value from JSON string or None.
  error_message=case 1 raised name 'json' is not defined
  code=def parse_json_field(s, key): return json.loads(s).get(key)

## Coverage

- signatures_total: 68
- signatures_covered_by_patcher: 3
- signatures_uncovered: 65
- coverage_rate: 4.4118%
- top_uncovered_signatures:
  - ts | AssertionError:case 2 mismatch: expected="" actual=undefined (count=12)
  - ts | RuntimeError:case 2 raised TypeError: Cannot read properties of null (reading 'trim') (count=12)
  - ts | TS1005:<path> (count=12)
  - py | AssertionError:case 1 mismatch: args=('level',), expected=True, actual=False (count=0)
  - py | AssertionError:case 1 mismatch: args=('noon',), expected=True, actual=False (count=0)
  - py | AssertionError:case 1 mismatch: args=(-1, -18), expected=17, actual=-19 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-10, -18), expected=8, actual=-28 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-10, -7, 10), expected=-7, actual=-10 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-12, -20), expected=8, actual=-32 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-13, -10, 1), expected=-10, actual=-13 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-13, -10, 5), expected=-10, actual=-13 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-14, 0), expected=0, actual=-14 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-15, 15), expected=-225, actual=0 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-17, 17), expected=0, actual=-34 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-20, -6), expected=120, actual=-26 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-3, 0, 2), expected=0, actual=-3 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-3, 0, 5), expected=0, actual=-3 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-3, 18), expected=-21, actual=15 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-4, -12), expected=48, actual=-16 (count=0)
  - py | AssertionError:case 1 mismatch: args=(-4, 5), expected=-9, actual=1 (count=0)
