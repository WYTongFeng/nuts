import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import textfeatures as tf  # noqa: E402

try:
    import perplexity
except ImportError:  # 没装 torch / transformers
    perplexity = None


@unittest.skipIf(perplexity is None, "需要 torch 和 transformers")
class PerplexityTest(unittest.TestCase):
    def test_sentences_align_with_spans(self):
        text = (ROOT / "samples" / "ai-style.txt").read_text(encoding="utf-8")
        _, sentences = perplexity.details(text)
        self.assertEqual(len(sentences), len(tf.sentence_spans(tf.normalize(text))))
        self.assertTrue(all(s and s["tokens"] > 0 for s in sentences))

    def test_surrounding_whitespace_does_not_change_scores(self):
        text = "The cat sat on the mat. It was happy about it."
        a, _ = perplexity.details(text)
        b, _ = perplexity.details("\n\n  " + text + "\n")
        self.assertAlmostEqual(a["ppl"], b["ppl"], places=6)

    def test_hard_wrapped_text_scores_like_one_line(self):
        wrapped = ("This sentence was copied out of a PDF file and it is\n"
                   "wrapped across several lines right in the middle of a\n"
                   "thought, which should not change how surprising it looks.")
        a, _ = perplexity.details(wrapped)
        b, _ = perplexity.details(wrapped.replace("\n", " "))
        self.assertAlmostEqual(a["ppl"], b["ppl"], places=6)

    def test_long_text_scores_every_token(self):
        text = "The quick brown fox jumps over the lazy dog. " * 150  # 超过 GPT-2 的 1024 token 上限
        _, tok = perplexity.load()
        self.assertEqual(len(perplexity.token_scores(text.strip())), len(tok(text.strip())["input_ids"]))

    def test_empty_text(self):
        self.assertEqual(perplexity.details("   "), ({}, []))


if __name__ == "__main__":
    unittest.main()
