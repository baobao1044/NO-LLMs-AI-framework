import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent import AgentLoop
from core.logger import JsonlLogger
from core.task import CodeTask
from core.verifier import FunctionCase, build_composite_function_verifier


def main() -> None:
    task = CodeTask(
        task_id="task_add_function_v1",
        prompt="Write a Python function add(a, b) that returns their sum.",
        target_file=Path("workspace/solution_add.py"),
        attempts=[
            "def add(a, b):\n    return a - b\n",
            "def add(a, b):\n    return a + b\n",
        ],
    )

    verifier = build_composite_function_verifier(
        function_name="add",
        cases=[
            FunctionCase(args=(1, 2), expected=3),
            FunctionCase(args=(-1, 5), expected=4),
            FunctionCase(args=(10, 0), expected=10),
        ],
        timeout_seconds=1.0,
    )
    logger = JsonlLogger(Path("logs/agent_runs.jsonl"))

    result = AgentLoop().run(task=task, verifier=verifier, logger=logger)
    print(f"run_id={result.run_id}")
    print(f"done={result.done}")
    print(f"attempts_used={result.attempts_used}")
    print(f"last_error={result.last_error}")
    print(f"log_file={logger.log_file}")
    print(f"final_code_file={task.target_file}")


if __name__ == "__main__":
    main()
