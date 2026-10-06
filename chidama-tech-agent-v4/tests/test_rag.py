import unittest

from app.rag.chunking import Document, chunk_document, load_documents, slugify
from app.rag.retriever import BM25Index, HybridRetriever
from app.rag.text import stem, tokenize
from tests.helpers import KNOWLEDGE

DOC = Document("faq", "Shop FAQ", "# Shop FAQ\n\nWe sell bicycles.\n\n## Opening hours\nOpen Monday to Friday from 9:00 to 17:00.\n\n## Returns\n"
               "You may return a bicycle within 30 days. " * 6, "faq.md")


class TextTests(unittest.TestCase):
    def test_stemming_is_consistent_across_word_forms(self):
        self.assertEqual(len({stem(w) for w in ["price", "prices", "pricing"]}), 1)
        self.assertEqual(len({stem(w) for w in ["install", "installed", "installing", "installs"]}), 1)
        self.assertEqual(stem("warranties"), "warranty")

    def test_tokenize_drops_stopwords_and_folds_accents(self):
        self.assertEqual(tokenize("What is the Ñwosu panel?"), ["nwosu", "panel"])
        self.assertIn("24", tokenize("open 24/7"))


class ChunkingTests(unittest.TestCase):
    def test_sections_become_chunks_with_headings_and_stable_ids(self):
        chunks = chunk_document(DOC, max_chars=300)
        self.assertEqual({c.heading for c in chunks}, {"Shop FAQ", "Opening hours", "Returns"})
        self.assertEqual(len({c.id for c in chunks}), len(chunks))
        self.assertTrue(all(c.id.startswith("faq#") for c in chunks))

    def test_chunks_respect_size_limit_roughly(self):
        for c in chunk_document(DOC, max_chars=300, overlap=60):
            self.assertLess(len(c.text), 300 + 60 + 10)

    def test_giant_unbroken_text_is_still_split(self):
        doc = Document("x", "X", "# X\n\n" + "word " * 2000, "x.md")
        self.assertGreater(len(chunk_document(doc, max_chars=500)), 5)

    def test_loads_both_packs_and_skips_non_documents(self):
        for pack in ("brightside-solar", "chidama-tech"):
            docs = load_documents(f"{KNOWLEDGE}/{pack}")
            self.assertGreaterEqual(len(docs), 3)
            self.assertFalse(any(d.source.endswith((".json", ".jsonl")) for d in docs))

    def test_slugify(self):
        self.assertEqual(slugify("Sub Dir/My File"), "sub-dir-my-file")


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.chunks = chunk_document(DOC, max_chars=300)
        self.index = BM25Index(self.chunks)

    def test_finds_the_right_section(self):
        res = self.index.search("when are you open?")
        self.assertTrue(res.answerable)
        self.assertEqual(res.hits[0].chunk.heading, "Opening hours")

    def test_refuses_off_topic_questions(self):
        for q in ["what is the capital of France", "write a poem", "hello"]:
            self.assertFalse(self.index.search(q).answerable, q)

    def test_unknown_words_lower_coverage(self):
        full = self.index.search("return a bicycle").coverage
        mixed = self.index.search("return a bicycle to the moon station").coverage
        self.assertLess(mixed, full)

    def test_synonyms_are_applied(self):
        idx = BM25Index(self.chunks, synonyms={"refund": ["return"]})
        self.assertTrue(idx.search("can I get a refund").answerable)

    def test_empty_index_and_query(self):
        self.assertFalse(BM25Index([]).search("anything").answerable)
        self.assertFalse(self.index.search("the and of").answerable)

    def test_hybrid_accepts_semantic_match_the_lexical_gate_misses(self):
        class Vec:  # fake embedder index: pretends 'cycle' is semantically close to the Returns chunk
            def __init__(self, chunks):
                self.chunks = chunks

            def search(self, query, k=5):
                target = next(c for c in self.chunks if c.heading == "Returns")
                return [(target, 0.9)]

        hybrid = HybridRetriever(self.index, Vec(self.chunks), vector_min_sim=0.8)
        res = hybrid.search("zzzz qqqq")
        self.assertTrue(res.answerable)
        self.assertEqual(res.hits[0].chunk.heading, "Returns")


if __name__ == "__main__":
    unittest.main()
