"""Nuts 的规则特征：文本清理、切句、分段和各项统计。

nuts-core.js 是这个文件的逐行对照版（网页用），两边必须算出一样的结果，
改这里时要同步改那边，tests/test_consistency.py 会检查。
"""
import bisect
import re
import statistics
from collections import Counter

# 句号后面紧跟这些词时不算句子结束
ABBREVIATIONS = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "e.g", "i.e", "cf", "fig", "figs",
    "no", "vol", "pp", "al", "approx", "inc", "ltd", "u.s", "u.k",
}
TERMINAL = ".!?:;\"')]”"
MATTR_WINDOW = 50
MIN_SENTENCE_WORDS = 3  # 少于 3 个词的片段（标题、编号）不参与句长统计

_BLOCK_SEP = re.compile(r"(\n[ \t]*\n\s*)")
_SENTENCE_END = re.compile(r"[.!?]+[\"')\]”]*(?=\s|$)")
_WORD_BEFORE = re.compile(r"([A-Za-z][A-Za-z.]*)$")
_WORD = re.compile(r"[a-z']+")


def normalize(text):
    """统一引号和换行，结果和原文长度相同（位置可以直接对回原文）。

    空行之间的一块文字里如果有单个换行：大多数行以标点结尾或很短时，当成一行一段
    （从 Word 粘贴的文字）；否则当成 PDF 的硬换行，换成空格。
    """
    text = text.replace("\r", " ").replace("’", "'").replace("‘", "'")
    pieces = _BLOCK_SEP.split(text)
    for i in range(0, len(pieces), 2):
        block = pieces[i]
        lines = block.split("\n")
        candidates = [line for line in lines[:-1] if line.strip()]
        if not candidates:
            continue
        paragraph_like = sum(1 for line in candidates
                             if line.rstrip()[-1] in TERMINAL or len(line.split()) <= 5)
        if paragraph_like / len(candidates) < 0.5:
            pieces[i] = block.replace("\n", " ")
    return "".join(pieces)


def paragraphs(norm):
    """normalize() 之后，剩下的换行都是段落分隔。"""
    return [p for p in re.split(r"\s*\n\s*", norm) if p.strip()]


def sentence_spans(norm):
    """切句，返回每句在文本里的 (起点, 终点)，已去掉首尾空白。段落分隔也算句子边界。"""
    cuts = {0, len(norm)}
    for m in _SENTENCE_END.finditer(norm):
        if m.group().count(".") == 1 and m.group()[0] == ".":
            before = _WORD_BEFORE.search(norm[max(0, m.start() - 20):m.start()])
            if before and (before.group(1).lower() in ABBREVIATIONS or re.fullmatch(r"[A-Z]", before.group(1))):
                continue
        cuts.add(m.end())
    for m in re.finditer(r"\n", norm):
        cuts.add(m.start())
    cuts = sorted(cuts)
    spans = []
    for a, b in zip(cuts, cuts[1:]):
        seg = norm[a:b]
        if seg.strip():
            spans.append((a + len(seg) - len(seg.lstrip()), b - (len(seg) - len(seg.rstrip()))))
    return spans


def sentence_of_tokens(spans, lead, token_offsets):
    """语言模型的 token 按它最后一个字符归到句子里，返回每个 token 所在句子的下标。

    token_offsets 是 token 在去掉首尾空白后的文本里的位置，lead 是去掉的开头空白长度。
    句子之间的空白 token（比如段落间的换行）不属于任何一句，是 None。
    """
    starts = [s for s, _ in spans]
    out = []
    for start, end in token_offsets:
        pos = lead + max(end, start + 1) - 1
        i = bisect.bisect_right(starts, pos) - 1
        out.append(i if i >= 0 and pos < spans[i][1] else None)
    return out


def words_with_pos(text):
    """英文单词（小写）和它们在 text 里的位置，去掉词两头的撇号。"""
    out = []
    for m in _WORD.finditer(text.lower()):
        word = m.group().strip("'")
        if word:
            start = m.start() + len(m.group()) - len(m.group().lstrip("'"))
            out.append((word, start, start + len(word)))
    return out


def words(text):
    return [w for w, _, _ in words_with_pos(text)]


def mattr(tokens, window=MATTR_WINDOW):
    """滑动窗口的词汇多样性（MATTR），不像普通 TTR 那样随文本变长而下降。"""
    if not tokens:
        return None
    if len(tokens) <= window:
        return len(set(tokens)) / len(tokens)
    counts = Counter(tokens[:window])
    unique = len(counts)
    total = unique
    for i in range(window, len(tokens)):
        old, new = tokens[i - window], tokens[i]
        counts[old] -= 1
        if counts[old] == 0:
            unique -= 1
        if counts[new] == 0:
            unique += 1
        counts[new] += 1
        total += unique
    return total / (len(tokens) - window + 1) / window


def phrase_hits(sentence_words, phrases):
    """句子里每个套话出现的位置，返回 [(套话, 第几个词起, 第几个词止)]，同一个套话不重叠计数。"""
    hits = []
    for phrase in phrases:
        parts = phrase.split(" ")
        n = len(parts)
        i = 0
        while i + n <= len(sentence_words):
            if sentence_words[i:i + n] == parts:
                hits.append((phrase, i, i + n))
                i += n
            else:
                i += 1
    return hits


def analyze(text, phrases):
    """整篇的规则特征，以及逐句的词、套话命中，供模型和逐句检查使用。"""
    norm = normalize(text)
    spans = sentence_spans(norm)
    sentences = []
    for start, end in spans:
        wp = words_with_pos(norm[start:end])
        ws = [w for w, _, _ in wp]
        hits = phrase_hits(ws, phrases)
        sentences.append({
            "start": start, "end": end, "words": len(ws),
            "avg_word_len": statistics.mean(len(w) for w in ws) if ws else 0,
            "commas": norm.count(",", start, end),
            "hits": [(p, start + wp[a][1], start + wp[b - 1][2]) for p, a, b in hits],
        })

    all_words = words(norm)
    lengths = [s["words"] for s in sentences if s["words"] >= MIN_SENTENCE_WORDS]
    mean_len = statistics.mean(lengths) if lengths else 0
    para_lens = [n for n in (len(words(p)) for p in paragraphs(norm)) if n]
    n_hits = sum(len(s["hits"]) for s in sentences)
    counted = sum(1 for s in sentences if s["words"])

    return {
        "words": len(all_words),
        "sentences": counted,
        "mean_len": mean_len,
        "burst": statistics.pstdev(lengths) / mean_len if len(lengths) > 1 else 0,
        "mattr": mattr(all_words),
        "avg_word_len": statistics.mean(len(w) for w in all_words) if all_words else 0,
        "phrases_per_1k": n_hits * 1000 / max(len(all_words), 1),
        "commas_per_sentence": norm.count(",") / max(counted, 1),
        "para_cv": statistics.pstdev(para_lens) / statistics.mean(para_lens) if len(para_lens) > 1 else None,
        "sentence_details": sentences,
    }
