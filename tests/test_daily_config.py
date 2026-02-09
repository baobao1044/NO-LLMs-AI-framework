import json
import unittest
from pathlib import Path

from core.task_spec import is_json_only


class DailyConfigTests(unittest.TestCase):
    def test_daily_config_schema_defaults(self) -> None:
        path = Path("configs/daily_config.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        required = {
            "seed_base",
            "seed_daily_mode",
            "generated_task_count",
            "max_tasks_per_day",
            "max_attempts_per_task",
            "max_total_seconds",
            "languages_enabled",
        }
        self.assertTrue(required.issubset(payload.keys()))
        self.assertTrue(is_json_only(payload))
        self.assertIn(payload["seed_daily_mode"], ["fixed", "date-derived"])
        self.assertIsInstance(payload["languages_enabled"], list)


if __name__ == "__main__":
    unittest.main()
