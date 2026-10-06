import unittest
from dataclasses import replace
from pathlib import Path

from app.agent import build_retriever
from app.config import Settings
from app.tenant import load_tenant
from evals.run_eval import load_questions, retrieval_eval
from tests.helpers import KNOWLEDGE


class PackEvalTests(unittest.TestCase):
    """A regression test for the knowledge itself: edit a document, break a question, CI tells you."""

    def check(self, slug, min_recall=0.85, min_refusal=0.9):
        settings = replace(Settings(), knowledge_dir=KNOWLEDGE, tenant=slug)
        report = retrieval_eval(build_retriever(settings, load_tenant(KNOWLEDGE, slug)),
                                load_questions(Path(KNOWLEDGE) / slug / "eval.jsonl"))
        self.assertGreaterEqual(report["answerable_recall"], min_recall, [r for r in report["rows"] if r["passed"] is False])
        self.assertGreaterEqual(report["refusal_accuracy"], min_refusal, [r for r in report["rows"] if r["passed"] is False])

    def test_brightside_solar(self):
        self.check("brightside-solar")

    def test_chidama_tech(self):
        self.check("chidama-tech")


if __name__ == "__main__":
    unittest.main()
