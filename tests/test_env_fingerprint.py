import unittest

from core.env_fingerprint import get_env_fingerprint
from core.task_spec import is_json_only


class EnvFingerprintTests(unittest.TestCase):
    def test_fingerprint_is_json_only_and_has_stable_keys(self) -> None:
        payload = get_env_fingerprint()
        self.assertTrue(is_json_only(payload))

        expected_keys = {
            "python_version",
            "node_version",
            "tsc_version",
            "platform",
            "git_commit",
        }
        self.assertEqual(set(payload.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
