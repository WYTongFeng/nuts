"""Nuts 命令行版：分析英文文本里 AI 检测器关注的特征，并给出综合判断。

用法:
    .venv/bin/python analyzer.py 文件.txt
    .venv/bin/python analyzer.py 人写.txt AI写.txt      # 多个文件并排对比
    .venv/bin/python analyzer.py --sentences 文件.txt    # 另外列出最像 AI 的句子
    .venv/bin/python analyzer.py --no-lm 文件.txt        # 不用 GPT-2，只看规则指标

装了 torch 和 transformers 时会用 GPT-2 计算困惑度（见 perplexity.py）。
综合判断用的模型和阈值来自 evaluate.py 生成的 model.json，准确率见 reports/evaluation.md。
"""
import os
import sys
import unicodedata

import model as nm
import textfeatures as tf

try:
    import perplexity
except ImportError:  # 没装 torch / transformers
    perplexity = None

ROWS = [  # (键, 名称, 小数位)
    ("words", "词数", 0),
    ("sentences", "句数", 0),
    ("mean_len", "平均句长", 1),
    ("burst", "突发性（句长 CV）", 2),
    ("mattr", "词汇多样性（MATTR）", 2),
    ("avg_word_len", "平均词长", 2),
    ("phrases_per_1k", "AI 套话 / 千词", 1),
    ("commas_per_sentence", "逗号 / 句", 2),
    ("para_cv", "段落长度 CV", 2),
    ("ppl", "困惑度", 1),
    ("sent_ppl_std", "句困惑度波动", 1),
    ("top10", "Top-10 占比", 2),
]
VERDICTS = {"likely": "很可能是 AI", "possible": "可能有 AI 成分", "unlikely": "不太像 AI",
            "too_short": "文本太短，不下结论"}
LEVELS = {2: "很像 AI", 1: "有点像"}


def looks_non_english(text):
    """字母里超过三成不是英文字母时，认为不是英文文本。"""
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(1 for c in letters if not c.isascii()) / len(letters) > 0.3


def analyze_text(text, m, use_lm):
    rule = tf.analyze(text, m["phrases"])
    lm_overall, lm_sentences = (perplexity.details(text) if use_lm and text.strip() else (None, None))
    variant = "full" if lm_overall else "rules"
    prob = nm.probability(m["doc"][variant], nm.doc_values(rule, lm_overall))

    norm = tf.normalize(text)
    sm = m["sentence"][variant]
    sentences = []
    for i, s in enumerate(rule["sentence_details"]):
        lm_s = lm_sentences[i] if lm_sentences else None
        p = nm.probability(sm, nm.sentence_values(s, lm_s))
        sentences.append({
            "text": norm[s["start"]:s["end"]], "prob": p,
            # 模型只用 3 个词以上的句子训练过，标题和编号不判断
            "level": nm.sentence_level(sm, p) if s["words"] >= 3 else 0,
            "hits": [h[0] for h in s["hits"]],
            "ppl": lm_s["ppl"] if lm_s else None,
        })
    return {
        "values": {**rule, **(lm_overall or {})},
        "prob": prob,
        "verdict": nm.doc_verdict(m["doc"][variant], prob, rule["words"]),
        "variant": variant,
        "sentences": sentences,
        "non_english": looks_non_english(text),
    }


def pad(s, width):
    """按终端显示宽度补空格（中文占两格）。"""
    s = str(s)
    shown = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)
    return s + " " * max(width - shown, 1)


def fmt(value, decimals):
    return "-" if value is None else f"{value:.{decimals}f}"


def pct(p):
    return "<1%" if p < 0.01 else ">99%" if p > 0.99 else f"{p:.0%}"


def main(args):
    show_sentences = "--sentences" in args
    use_lm = perplexity is not None and "--no-lm" not in args
    paths = [a for a in args if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return
    missing = [p for p in paths if not os.path.isfile(p)]
    if missing:
        sys.exit("找不到文件：" + ", ".join(missing))
    if not os.path.isfile(nm.MODEL_PATH):
        sys.exit("缺少 model.json，先运行 .venv/bin/python evaluate.py run")

    m = nm.load()
    results = {}
    for path in paths:
        with open(path, encoding="utf-8") as f:
            results[path] = analyze_text(f.read(), m, use_lm)

    width = max(len(p) for p in paths) + 2
    print(pad("指标", 22) + "".join(pad(p, width) for p in paths))
    for key, label, decimals in ROWS:
        if key in ("ppl", "sent_ppl_std", "top10") and not use_lm:
            continue
        print(pad(label, 22) + "".join(pad(fmt(r["values"].get(key), decimals), width) for r in results.values()))

    print()
    for path, r in results.items():
        basis = "规则 + GPT-2" if r["variant"] == "full" else "仅规则"
        print(f"[{path}] AI 可能性 {pct(r['prob'])}：{VERDICTS[r['verdict']]}（{basis}）")
        if r["non_english"]:
            print("  注意：这段文字看起来不是英文，Nuts 只支持英文，结果没有意义。")

    if show_sentences:
        for path, r in results.items():
            flagged = sorted((s for s in r["sentences"] if s["level"]), key=lambda s: -s["prob"])
            print(f"\n[{path}] 最像 AI 的句子（{len(flagged)} / {len(r['sentences'])} 句被标出）：")
            for s in flagged[:10]:
                extra = [f"困惑度 {s['ppl']:.1f}"] if s["ppl"] is not None else []
                extra += [f"套话：{'、'.join(s['hits'])}"] if s["hits"] else []
                print(f"  {LEVELS[s['level']]} {pct(s['prob'])}  {s['text'][:90]}")
                if extra:
                    print(f"      {' · '.join(extra)}")

    ev = m.get("evaluation", {}).get("full" if use_lm else "rules")
    if ev:
        print(f"\n参考：在 RAID 测试集上，判为“可能有 AI 成分”时，人写文本的误判率 {ev['possible_fpr']:.0%}、"
              f"AI 文本的检出率 {ev['possible_tpr']:.0%}。这不是 Turnitin 或 GPTZero 的结果，详见 reports/evaluation.md。")
    if not use_lm and perplexity is None:
        print("（未安装 torch / transformers，只用了规则模型）")


if __name__ == "__main__":
    main(sys.argv[1:])
