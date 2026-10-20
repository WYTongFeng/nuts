"""读取 model.json，用评测训练出的综合模型给整篇文本和每个句子打分。

nuts-core.js 里有同样的计算（网页用），两边要保持一致。
"""
import json
import math
from pathlib import Path

MODEL_PATH = Path(__file__).with_name("model.json")
MIN_SENTENCE_TOKENS = 5  # 句子太短时困惑度不稳定，当作缺失

# 三种检测引擎：bino = Binoculars + GPT-2 + 规则，full = GPT-2 + 规则，rules = 只用规则。
# 词汇多样性和平均句长在评测里单独的区分力接近 0.5（等于瞎猜），不放进模型。
DOC_FEATURES = {
    "bino": ["bino", "log_ppl", "log_sent_ppl_std", "top10", "burst", "avg_word_len", "log_phrases",
             "commas_per_sentence"],
    "full": ["log_ppl", "log_sent_ppl_std", "top10", "burst", "avg_word_len", "log_phrases", "commas_per_sentence"],
    "rules": ["burst", "avg_word_len", "log_phrases", "commas_per_sentence"],
}
SENTENCE_FEATURES = {
    "bino": ["bino", "log_ppl", "top10", "log_hits", "log_words", "avg_word_len", "commas"],
    "full": ["log_ppl", "top10", "log_hits", "log_words", "avg_word_len", "commas"],
    "rules": ["log_hits", "log_words", "avg_word_len", "commas"],
}


def engine(model, lm):
    """按拿到的语言模型分数挑最好的引擎。"""
    if lm and lm.get("bino") is not None and "bino" in model["doc"]:
        return "bino"
    return "full" if lm else "rules"


def load(path=MODEL_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def doc_values(rule, lm=None):
    """整篇的模型输入。rule 来自 textfeatures.analyze()，lm 来自 perplexity.details() 的整体部分。"""
    v = {
        "burst": rule["burst"],
        "mattr": rule["mattr"],
        "avg_word_len": rule["avg_word_len"],
        "log_phrases": math.log1p(rule["phrases_per_1k"]),
        "commas_per_sentence": rule["commas_per_sentence"],
        "mean_len": rule["mean_len"],
    }
    if lm:
        v["log_ppl"] = math.log(lm["ppl"])
        v["log_sent_ppl_std"] = math.log1p(lm["sent_ppl_std"]) if lm["sent_ppl_std"] is not None else None
        v["top10"] = lm["top10"]
        v["bino"] = lm.get("bino")
    return v


def sentence_values(sentence, lm_sentence=None):
    """单句的模型输入。sentence 是 analyze() 里 sentence_details 的一项。"""
    v = {
        "log_hits": math.log1p(len(sentence["hits"])),
        "log_words": math.log1p(sentence["words"]),
        "avg_word_len": sentence["avg_word_len"],
        "commas": sentence["commas"],
        "log_ppl": None,
        "top10": None,
        "bino": None,
    }
    if lm_sentence and lm_sentence["tokens"] >= MIN_SENTENCE_TOKENS:
        v["log_ppl"] = math.log(lm_sentence["ppl"])
        v["top10"] = lm_sentence["top10"]
        v["bino"] = lm_sentence.get("bino")
    return v


def probability(m, values):
    """逻辑回归：先按训练集的均值、标准差标准化，缺失的特征当作均值。"""
    z = m["intercept"]
    for name, mean, scale, coef in zip(m["features"], m["mean"], m["scale"], m["coef"]):
        x = values.get(name)
        z += coef * (((mean if x is None else x) - mean) / scale)
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def doc_verdict(model, prob, words):
    if words < model["min_words"]:
        return "too_short"
    t = model["thresholds"]
    return "likely" if prob >= t["likely"] else "possible" if prob >= t["possible"] else "unlikely"


def sentence_level(model, prob):
    t = model["thresholds"]
    return 2 if prob >= t["high"] else 1 if prob >= t["mid"] else 0
