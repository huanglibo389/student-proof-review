from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from student_proof_review.config import APPROVED_MODEL_NAME, configured_model
from student_proof_review.workflow import create_case, load_case, status


class WorkflowTests(unittest.TestCase):
    def test_create_case_copies_inputs_hashes_them_and_writes_audit_template(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "proof.jpg"
            Image.new("RGB", (20, 20), "white").save(source)
            case = create_case(root / "outputs", "测试任务", "第1题学生解答审查", [source])
            metadata = load_case(case)
            self.assertEqual(metadata["title"], "第1题学生解答审查")
            self.assertEqual(len(metadata["inputs"]), 1)
            self.assertEqual(len(metadata["inputs"][0]["sha256"]), 64)
            self.assertTrue((case / metadata["inputs"][0]["copied_path"]).is_file())
            self.assertIn("第一处需要修补的地方", (case / "audit.md").read_text(encoding="utf-8"))
            self.assertIn("transcription: pending", status(case))

    def test_model_policy_only_accepts_qwen38(self):
        self.assertIn("Qwen3.8-27B", configured_model())
        self.assertEqual(APPROVED_MODEL_NAME, "Qwen3.8-27B-MLX-Mixed-4.95bpw")

    def test_metadata_is_valid_json(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "proof.png"
            Image.new("RGB", (10, 10), "white").save(source)
            case = create_case(root / "outputs", "case", "题目", [source])
            loaded = json.loads((case / "case.json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema"], "student-proof-review/case-v1")


if __name__ == "__main__":
    unittest.main()
