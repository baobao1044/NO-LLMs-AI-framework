# NO-LLMs-AI-framework

README ban de hieu nhat.

Neu ban chi nho 2 lenh, nho 2 lenh nay:

```bash
make train
make train-status
```

## 1) Du an nay la gi?
Tuong tu nhu be lam bai tap:
1. Nhan de bai.
2. Lam bai.
3. Co dap an dung/sai de cham.
4. Sai thi sua.
5. Ghi lai de lan sau tot hon.

Vong lap:

```text
task -> execute -> verify -> log -> done
```

## 2) Dang train cai gi?
Dang train **he thong agent** (workflow + patchers + verifier + logging),
KHONG train neural weights.

Nghia la:
- Co chay 24/7 duoc.
- Toc do cao la binh thuong.
- KHONG co backprop PyTorch trong loop nay.

## 3) Chay nhanh trong 30 giay
### Bat train 24/7
```bash
make train
```

### Xem tinh trang
```bash
make train-status
```

### Chay 1 vong de test nhanh
```bash
make training-247-once
```

### Dung train
```bash
pkill -f "tools/run_training_247.py"
```

## 4) Status nghia la gi?
`make train-status` se in ra:
- `running`: co dang chay khong.
- `state`: dang o buoc nao (`running`, `sleeping`, `completed`, `failed`, `stale`).
- `current_step`: buoc hien tai (`daily_ab`, `merge_logs`, `dedup_report`, `refresh`, `ci`).
- `total_cycles`: tong so chu ky da chay.
- `successful_cycles`: so chu ky pass.
- `success_rate`: ti le pass.
- `consecutive_failures`: so lan fail lien tiep.
- `last_cycle_key`: ma cycle gan nhat.
- `latest_solve_rate_delta`: chenhlech B - A gan nhat.
- `latest_proposer_calls`: so lan proposer duoc goi o cycle gan nhat.

File status goc:
```text
reports/training_247_status.json
```

## 5) Du lieu train nam o dau?
- Log hien tai:
  - `logs/agent_runs.jsonl`
- Run packs:
  - `runs/YYYYMMDDHHMMSS_A/agent_runs.jsonl`
  - `runs/YYYYMMDDHHMMSS_B/agent_runs.jsonl`
- Bao cao moi cycle:
  - `reports/YYYYMMDDHHMMSS/ab_compare.json`
  - `reports/YYYYMMDDHHMMSS/daily_summary_A.json`
  - `reports/YYYYMMDDHHMMSS/daily_summary_B.json`

## 6) Neu muon chay nen (khuyen dung)
```bash
tmux new -s train247 'cd /workspaces/NO-LLMs-AI-framework && make train'
```

Mo lai:
```bash
tmux attach -t train247
```

## 7) Cac lenh quan trong
```bash
make test
make ci
make train
make train-status
make training-247-once
make training-full
make replay
make regress
make quality
```

## 8) Cau hinh chinh
- Daily full workload:
  - `configs/daily_training_full.json`
- Proposer full policy:
  - `configs/proposer_policy_training_full.json`

Muon tang tai:
- Tang `generated_task_count`, `max_tasks_per_day`, `max_total_seconds` trong `configs/daily_training_full.json`.
- Tang `max_calls_per_day`, `max_total_seconds_per_day` trong `configs/proposer_policy_training_full.json`.

## 9) Luu y quan trong
- He thong nay verifier-first va deterministic.
- Replay phai giu `100% match`.
- Neu train dang chay ma status bi dung lau khong doi, kiem tra process:

```bash
pgrep -af "run_training_247.py|run_daily.py"
```

- Neu can reset stale status, dung process cu roi chay lai `make train`.

## 10) Danh cho ky su (chi tiet ky thuat)
- Core loop: `core/agent.py`
- Proposer runtime: `core/proposers/runtime.py`
- TS verifier pipeline: `core/verifiers/ts_composite_verifier.py`
- 24/7 runner: `tools/run_training_247.py`
- Status command: `tools/training_status.py`

---

Neu ban moi vao du an:
1. Chay `make train`.
2. Sau 1-2 phut, chay `make train-status`.
3. Neu `running=True` va `consecutive_failures=0` la on.
