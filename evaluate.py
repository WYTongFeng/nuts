"""Nuts 准确率评测：下载有标注的人写 / AI 文本，测出各指标和综合模型的真实表现，
并生成 model.json（套话表、综合模型权重、阈值）和 reports/evaluation.md。

用法:
    python evaluate.py fetch            # 下载评测数据到 data/（只需一次）
    python evaluate.py run              # 计算特征、训练、评测、写出 model.json 和报告
    python evaluate.py run --no-bino    # 跳过 Binoculars（没有显卡的电脑上很慢）

数据来源:
- RAID（Dugan et al., ACL 2024，MIT 许可）：人写的论文摘要、书籍概要、新闻，
  以及 GPT-4、ChatGPT、Llama-2-chat、Mistral-chat、Cohere-chat、MPT-chat 按同一标题生成的文本
- textsightai/ai-text-detection-benchmark-2026（CC BY-SA 4.0）：2026 年模型生成的文本，
  以及非英语母语作者的论文段落、2022 年前的维基百科、公版文学作品
"""
import json
import random
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"

RAID_DOMAINS = ["abstracts", "books", "news"]
RAID_AI_MODELS = ["gpt4", "chatgpt", "llama-chat", "mistral-chat", "cohere-chat", "mpt-chat"]
RAID_HUMAN_PER_DOMAIN = 150
RAID_AI_PER_CELL = 25  # 每个模型 × 每个领域

BENCH = "textsightai/ai-text-detection-benchmark-2026"
BENCH_CONFIGS = ["ai_generated_2026", "human_pmc_ccby_nonanglophone", "human_wikipedia_pre2022",
                 "human_literature_publicdomain"]


def _get_json(url, tries=5):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(url, timeout=120))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 ** i)


def fetch_raid():
    """RAID 太大（200 多万行），只按 parquet 的 row group 统计信息挑出没被攻击过的块来下载。"""
    import fsspec
    import pyarrow.parquet as pq

    files = _get_json("https://datasets-server.huggingface.co/parquet?dataset=liamdugan/raid")["parquet_files"]
    urls = [f["url"] for f in files if f["config"] == "raid" and f["split"] == "train"]
    fs = fsspec.filesystem("https")

    wanted = set(RAID_AI_MODELS) | {"human"}
    quota = {(m, d): RAID_HUMAN_PER_DOMAIN if m == "human" else RAID_AI_PER_CELL for m in wanted for d in RAID_DOMAINS}

    def in_range(value, lo_hi):
        lo, hi = lo_hi
        return lo is not None and lo <= value <= hi

    # 先用每个块的统计信息（各列的最小、最大值）挑出可能有需要内容的块
    candidates = []  # (只含一个模型的块排前面, url, 块下标, 可能包含的单元格)
    for url in urls:
        with fs.open(url, "rb", block_size=2**16, cache_type="none") as fh:
            md = pq.ParquetFile(fh).metadata
        col = {md.schema.column(i).name: i for i in range(md.num_columns)}
        for g in range(md.num_row_groups):
            rg = md.row_group(g)

            def stat(name):
                s = rg.column(col[name]).statistics
                return (s.min, s.max) if s is not None and s.has_min_max else (None, None)

            domain = stat("domain")
            if stat("attack") != ("none", "none") or domain[0] != domain[1] or domain[0] not in RAID_DOMAINS:
                continue
            model = stat("model")
            # AI 文本只要随机采样、没有重复惩罚的（最接近日常使用）；人写文本这两列是空的
            sampled = in_range("sampling", stat("decoding")) and in_range("no", stat("repetition_penalty"))
            cells = [(m, domain[0]) for m in wanted
                     if in_range(m, model) and (m == "human" or sampled)]
            if cells:
                candidates.append((model[0] != model[1], url, g, cells))
    candidates.sort(key=lambda c: c[0])

    def keep(r):
        return (r["attack"] == "none" and r["domain"] in RAID_DOMAINS and r["model"] in wanted
                and r["decoding"] in (None, "sampling") and r["repetition_penalty"] in (None, "no")
                and r["generation"] and len(r["generation"].split()) >= 50)

    # 逐块读取，直到每个单元格都够数；块内先打乱，避免总取到同一批标题
    rng = random.Random(0)
    taken, out = Counter(), []
    files_open = {}
    for _, url, g, cells in candidates:
        if all(taken[c] >= quota[c] for c in cells):
            continue
        if url not in files_open:
            files_open[url] = pq.ParquetFile(fs.open(url, "rb"))
        print(f"  读取 {url.split('/')[-1]} 第 {g} 块…", file=sys.stderr)
        rows = files_open[url].read_row_group(g, columns=[
            "id", "source_id", "model", "decoding", "repetition_penalty", "attack", "domain", "generation"]).to_pylist()
        rng.shuffle(rows)
        for r in rows:
            cell = (r["model"], r["domain"])
            if keep(r) and taken[cell] < quota[cell]:
                taken[cell] += 1
                out.append({
                    "id": r["id"], "group": r["source_id"], "dataset": "raid", "domain": r["domain"],
                    "model": r["model"], "label": "human" if r["model"] == "human" else "ai",
                    "text": r["generation"],
                })
        if all(taken[c] >= quota[c] for c in quota):
            break
    for cell in sorted(quota):
        print(f"  {cell}: {taken[cell]}", file=sys.stderr)
    return out


def fetch_bench():
    out = []
    for config in BENCH_CONFIGS:
        offset = 0
        while True:
            url = "https://datasets-server.huggingface.co/rows?" + urllib.parse.urlencode(
                {"dataset": BENCH, "config": config, "split": "train", "offset": offset, "length": 100})
            page = _get_json(url)
            for item in page["rows"]:
                r = item["row"]
                out.append({
                    "id": r["id"], "group": r["id"], "dataset": "bench2026", "domain": config,
                    "model": r.get("source") or config, "label": r["label"], "text": r["text"],
                })
            offset += len(page["rows"])
            if not page["rows"] or offset >= page["num_rows_total"]:
                break
            time.sleep(1)  # 避免被限流
        print(f"  {config}: {offset}", file=sys.stderr)
    return out


def write_jsonl(path, rows):
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def cmd_fetch():
    print("下载 RAID…", file=sys.stderr)
    write_jsonl(DATA / "raid.jsonl", fetch_raid())
    print("下载 2026 基准…", file=sys.stderr)
    write_jsonl(DATA / "bench2026.jsonl", fetch_bench())
    print("完成，数据在 data/", file=sys.stderr)


# ---------- 训练与评测 ----------

STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further had has have having he her here hers
herself him himself his how i if in into is it its itself just me more most my myself no nor not now of off on
once only or other our ours ourselves out over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very was we were what when where which
while who whom why will with would you your yours yourself yourselves don't it's i'm can't won't isn't
""".split())

OLD_PHRASES = [
    "delve", "it is important to note", "it's important to note", "in today's", "fast-paced", "plays a crucial role",
    "plays a vital role", "furthermore", "moreover", "in conclusion", "overall,", "a testament to", "tapestry",
    "navigate the", "landscape", "realm", "multifaceted", "pivotal", "foster", "underscore", "leverage", "seamless",
    "robust", "holistic", "nuanced", "embark", "not only", "in summary", "ever-evolving", "shed light",
]

LIKELY_FPR = 0.02    # “很可能是 AI”：训练集里只有 2% 的人写文本会超过这条线
POSSIBLE_FPR = 0.10  # “可能有 AI 成分”：10%
SENT_HIGH_FPR = 0.05  # 逐句“很像 AI”：5% 的人写句子会被标
SENT_MID_FPR = 0.15   # 逐句“有点像”：15%
MIN_WORDS = 80


def split_of(group):
    import hashlib
    return "test" if int(hashlib.md5(group.encode()).hexdigest(), 16) % 4 == 0 else "train"


def score_cache(docs, name, details):
    """语言模型打分很慢，按文本 id 缓存在 data/<name>_cache.jsonl，中断后可以接着跑。"""
    path = DATA / f"{name}_cache.jsonl"
    cache = {r["id"]: r for r in read_jsonl(path)} if path.exists() else {}
    todo = [d for d in docs if d["id"] not in cache]
    with open(path, "a", encoding="utf-8") as f:
        for i, d in enumerate(todo, 1):
            overall, sentences = details(d["text"])
            cache[d["id"]] = {"id": d["id"], "overall": overall, "sentences": sentences}
            f.write(json.dumps(cache[d["id"]]) + "\n")
            f.flush()
            if i % 100 == 0 or i == len(todo):
                print(f"  {name} 打分 {i}/{len(todo)}", file=sys.stderr)
    return cache


def lm_scores(docs, use_bino=True):
    """GPT-2 分数，加上 Binoculars 分数（模型已下载且没加 --no-bino 时）。返回 id -> {"overall", "sentences"}。"""
    import perplexity

    gpt2 = score_cache(docs, "lm", perplexity.details)
    bino = None
    if use_bino:
        try:
            import binoculars
            bino = score_cache(docs, "bino", binoculars.details) if binoculars.downloaded() else None
        except ImportError:
            pass
    if bino is None:
        print("  没有 Binoculars 模型，只用 GPT-2", file=sys.stderr)
        return gpt2
    merged = {}
    for doc_id, g in gpt2.items():
        b = bino[doc_id]
        merged[doc_id] = {
            "overall": {**g["overall"], **b["overall"]},
            "sentences": [{**gs, "bino": bs["bino"]} if gs and bs else gs
                          for gs, bs in zip(g["sentences"], b["sentences"], strict=True)],
        }
    return merged


def log_odds(a, n_a, h, n_h):
    """加 0.5 平滑的对数优势比和它的标准误。"""
    import math
    lo = math.log((a + .5) / (n_a - a + .5)) - math.log((h + .5) / (n_h - h + .5))
    se = math.sqrt(1 / (a + .5) + 1 / (n_a - a + .5) + 1 / (h + .5) + 1 / (n_h - h + .5))
    return lo, se


def learn_phrases(train_docs, limit=60):
    """统计 1-3 个词的短语在 AI 和人写文本里各出现在多少篇，挑出明显偏向 AI 的。

    只保留在每个领域里都偏向 AI 的短语：只在某个领域偏向 AI 的词（比如 AI 写书籍概要爱用的
    novel、journey）换到学生论文里会造成误判。旧版手写套话里，数据没有反驳的也保留。
    """
    import math
    import textfeatures

    df = {"ai": Counter(), "human": Counter()}
    df_domain = defaultdict(Counter)  # (label, domain) -> 短语篇数
    n = Counter(d["label"] for d in train_docs)
    n_domain = Counter((d["label"], d["domain"]) for d in train_docs)
    for d in train_docs:
        norm = textfeatures.normalize(d["text"])
        seen = set()
        for a, b in textfeatures.sentence_spans(norm):
            ws = textfeatures.words(norm[a:b])
            for k in (1, 2, 3):
                for i in range(len(ws) - k + 1):
                    gram = tuple(ws[i:i + k])
                    if not all(w in STOPWORDS for w in gram):
                        seen.add(" ".join(gram))
        df[d["label"]].update(seen)
        df_domain[(d["label"], d["domain"])].update(seen)

    domains = sorted({dom for _, dom in n_domain})
    rows = []
    for gram, a in df["ai"].items():
        h = df["human"][gram]
        if a < max(5, 0.02 * n["ai"]):
            continue
        lo, se = log_odds(a, n["ai"], h, n["human"])
        if lo < math.log(2) or lo / se < 3:
            continue
        per_domain = [log_odds(df_domain[("ai", dom)][gram], n_domain[("ai", dom)],
                               df_domain[("human", dom)][gram], n_domain[("human", dom)])[0] for dom in domains]
        spread = sum(1 for dom in domains if df_domain[("ai", dom)][gram] >= 2)
        if min(per_domain) > 0 and spread >= 2:
            rows.append((lo / se, gram, a, h))
    rows.sort(reverse=True)
    learned = [g for _, g, _, _ in rows[:limit]]

    kept_old = []
    for p in OLD_PHRASES:
        key = " ".join(textfeatures.words(p))
        a, h = df["ai"][key], df["human"][key]
        if all(w in STOPWORDS for w in key.split()):
            continue  # 比如 not only：全是常用词，人写文本里也很常见
        if h == 0 or (a + .5) / n["ai"] >= 2 * (h + .5) / n["human"]:
            kept_old.append(key)
    phrases = learned + [p for p in kept_old if p not in learned]
    return phrases, rows[:limit], kept_old, n, df


def fit_with_thresholds(rows, features, groups, fprs):
    """在全部训练数据上拟合；阈值用 5 折交叉验证的预测来定，避免在训练过的数据上定线太乐观。"""
    import model as nm
    from sklearn.model_selection import GroupKFold

    final = fit_logistic(rows, features)
    human = []
    for train_idx, val_idx in GroupKFold(n_splits=5).split(rows, groups=groups):
        m = fit_logistic([rows[i] for i in train_idx], features)
        human += [nm.probability(m, rows[i]["values"]) for i in val_idx if rows[i]["label"] == "human"]
    final["thresholds"] = {name: human_quantile(human, fpr) for name, fpr in fprs.items()}
    return final


def fit_logistic(rows, features):
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    raw = np.array([[r["values"].get(f) for f in features] for r in rows], dtype=float)  # None 变成 nan
    mean = np.nanmean(raw, axis=0)
    X = np.where(np.isnan(raw), mean, raw)
    scale = X.std(axis=0)
    scale[scale == 0] = 1
    y = np.array([r["label"] == "ai" for r in rows])
    clf = LogisticRegression(C=1.0, max_iter=5000).fit((X - mean) / scale, y)
    return {
        "features": features, "mean": mean.tolist(), "scale": scale.tolist(),
        "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0]),
    }


def human_quantile(probs, fpr):
    """阈值：让大约 fpr 比例的人写样本超过它。"""
    import numpy as np
    return float(np.quantile(probs, 1 - fpr))


def rate(items, pred):
    items = list(items)
    return sum(1 for x in items if pred(x)) / len(items) if items else float("nan")


def auc(pos, neg):
    from sklearn.metrics import roc_auc_score
    return roc_auc_score([1] * len(pos) + [0] * len(neg), list(pos) + list(neg))


def pct(x):
    return "—" if x != x else f"{x * 100:.1f}%"


VARIANT_LABELS = {"bino": "Binoculars + GPT-2 + 规则", "full": "GPT-2 + 规则", "rules": "仅规则（网页链接版）"}


def cmd_run(*flags):
    import statistics

    import model as nm
    import textfeatures

    raid = read_jsonl(DATA / "raid.jsonl")
    bench = read_jsonl(DATA / "bench2026.jsonl")
    for d in raid:
        d["split"] = split_of(d["group"])
    for d in bench:
        d["split"] = "bench"
    docs = raid + bench
    print(f"共 {len(docs)} 篇，开始语言模型打分（有缓存）…", file=sys.stderr)
    scores = lm_scores(docs, use_bino="--no-bino" not in flags)
    has_bino = all("bino" in scores[d["id"]]["overall"] for d in docs)
    variants = ("bino", "full", "rules") if has_bino else ("full", "rules")
    best = variants[0]

    train = [d for d in raid if d["split"] == "train"]
    phrases, phrase_rows, kept_old, n_train, df = learn_phrases(train)
    print(f"套话表共 {len(phrases)} 个（数据学出 {len(phrase_rows)} 个）", file=sys.stderr)

    for d in docs:
        d["rule"] = textfeatures.analyze(d["text"], phrases)
        d["lm"] = scores[d["id"]]
        d["values"] = nm.doc_values(d["rule"], d["lm"]["overall"])

    model = {
        "version": 2,
        "trained_on": "RAID（ACL 2024）论文摘要、书籍概要、新闻：人写 vs GPT-4、ChatGPT、Llama-2、Mistral、Cohere、MPT",
        "phrases": phrases,
        "min_words": MIN_WORDS,
        "doc": {},
        "sentence": {},
    }
    for variant in variants:
        m = fit_with_thresholds(train, nm.DOC_FEATURES[variant], [d["group"] for d in train],
                                {"likely": LIKELY_FPR, "possible": POSSIBLE_FPR})
        m["min_words"] = MIN_WORDS
        model["doc"][variant] = m
        for d in docs:
            d.setdefault("prob", {})[variant] = nm.probability(m, d["values"])

    # 逐句特征：句子的标签就是所在文章的标签
    def sentence_rows(subset):
        out = []
        for d in subset:
            for s, lm_s in zip(d["rule"]["sentence_details"], d["lm"]["sentences"]):
                if s["words"] >= 3:
                    out.append({"label": d["label"], "doc": d, "s": s, "lm": lm_s,
                                "values": nm.sentence_values(s, lm_s)})
        return out

    train_sents = sentence_rows(train)
    for variant in variants:
        m = fit_with_thresholds(train_sents, nm.SENTENCE_FEATURES[variant], [r["doc"]["group"] for r in train_sents],
                                {"high": SENT_HIGH_FPR, "mid": SENT_MID_FPR})
        m["fpr_high"], m["fpr_mid"] = SENT_HIGH_FPR, SENT_MID_FPR
        model["sentence"][variant] = m

    feature_defs = [
        ("bino", "Binoculars 分数", lambda d: d["lm"]["overall"].get("bino")),
        ("ppl", "困惑度（GPT-2）", lambda d: d["lm"]["overall"]["ppl"]),
        ("sent_ppl_std", "句困惑度波动", lambda d: d["lm"]["overall"]["sent_ppl_std"]),
        ("top10", "Top-10 占比", lambda d: d["lm"]["overall"]["top10"]),
        ("burst", "突发性（句长 CV）", lambda d: d["rule"]["burst"]),
        ("mattr", "词汇多样性（MATTR）", lambda d: d["rule"]["mattr"]),
        ("avg_word_len", "平均词长", lambda d: d["rule"]["avg_word_len"]),
        ("phrases_per_1k", "套话 / 千词（数据学出的套话表）", lambda d: d["rule"]["phrases_per_1k"]),
        ("old_phrases", "套话 / 千词（旧版手写套话表）", lambda d: old_phrase_rate(d["text"])),
        ("commas_per_sentence", "逗号 / 句", lambda d: d["rule"]["commas_per_sentence"]),
        ("mean_len", "平均句长", lambda d: d["rule"]["mean_len"]),
        ("para_cv", "段落长度 CV", lambda d: d["rule"]["para_cv"]),
    ]
    if not has_bino:
        feature_defs = feature_defs[1:]

    # 每项指标在训练集人写 / AI 文本里的中位数，网页用来解释判断
    model["feature_stats"] = {}
    for key, _, f in feature_defs:
        if key == "old_phrases":
            continue
        stats = {}
        for label in ("human", "ai"):
            values = [f(d) for d in train if d["label"] == label and f(d) is not None]
            stats[label] = round(statistics.median(values), 4)
        model["feature_stats"][key] = stats

    # ---------- 评测 ----------
    test = [d for d in raid if d["split"] == "test"]
    t_h = [d for d in test if d["label"] == "human"]
    t_ai = [d for d in test if d["label"] == "ai"]
    lines = ["# Nuts 准确率评测", "",
             f"训练集：RAID {len(train)} 篇（人写 {n_train['human']}，AI {n_train['ai']}）。"
             f"测试集：RAID 另外 {len(test)} 篇（人写 {len(t_h)}，AI {len(t_ai)}），"
             "按原始文章分组划分，同一标题的人写和 AI 文本不会同时出现在训练集和测试集。",
             "另有 2026 基准 700 篇只用于测试，从不参与训练。", ""]

    lines += ["## 单项指标的区分能力（RAID 测试集 AUROC）", "",
              "AUROC 是随机抽一篇 AI 文本和一篇人写文本，指标能把它们排对顺序的概率。"
              "0.5 等于瞎猜，1.0 是完美区分。", "",
              "| 指标 | AUROC | 方向 | 人写中位数 | AI 中位数 |", "|---|---|---|---|---|"]
    model["feature_auc"] = {}
    for key, name, f in feature_defs:
        # 缺失值（比如只有一段时的段落长度 CV）不参与，否则会被当成 0 而扭曲方向
        a = auc([f(d) for d in t_ai if f(d) is not None], [f(d) for d in t_h if f(d) is not None])
        model["feature_auc"][key] = {"auc": round(max(a, 1 - a), 3), "higher_is_ai": a >= 0.5}
        st = model["feature_stats"].get(key)
        medians = f"{st['human']:.3g} | {st['ai']:.3g}" if st else "— | —"
        lines.append(f"| {name} | {max(a, 1 - a):.3f} | {'越高越像 AI' if a >= 0.5 else '越低越像 AI'} | {medians} |")

    lines += ["", "## 综合模型（整篇）", "",
              f"阈值用训练集上 5 折交叉验证的预测来定：“很可能是 AI”只让 {LIKELY_FPR:.0%} 的人写文本越线，"
              f"“可能有 AI 成分”让 {POSSIBLE_FPR:.0%} 越线。下面是在测试数据上的实际表现。", "",
              "| 引擎 | AUROC | 很可能：误判率 | 很可能：检出率 | 可能：误判率 | 可能：检出率 |",
              "|---|---|---|---|---|---|"]
    bench_ai = [d for d in bench if d["label"] == "ai"]
    esl = [d for d in bench if d["domain"] == "human_pmc_ccby_nonanglophone"]
    wiki = [d for d in bench if d["domain"] == "human_wikipedia_pre2022"]
    summary = {}
    for variant in variants:
        th = model["doc"][variant]["thresholds"]
        hit = lambda d, line: d["prob"][variant] >= th[line]
        row = {
            "auc": auc([d["prob"][variant] for d in t_ai], [d["prob"][variant] for d in t_h]),
            "likely_fpr": rate(t_h, lambda d: hit(d, "likely")),
            "likely_tpr": rate(t_ai, lambda d: hit(d, "likely")),
            "possible_fpr": rate(t_h, lambda d: hit(d, "possible")),
            "possible_tpr": rate(t_ai, lambda d: hit(d, "possible")),
            "bench_ai_possible_tpr": rate(bench_ai, lambda d: hit(d, "possible")),
            "esl_possible_fpr": rate(esl, lambda d: hit(d, "possible")),
            "wiki_possible_fpr": rate(wiki, lambda d: hit(d, "possible")),
        }
        summary[variant] = row
        lines.append(f"| {VARIANT_LABELS[variant]} | {row['auc']:.3f} | {pct(row['likely_fpr'])} | "
                     f"{pct(row['likely_tpr'])} | {pct(row['possible_fpr'])} | {pct(row['possible_tpr'])} |")

    th = model["doc"][best]["thresholds"]
    lines += ["", f"### 按 AI 模型的检出率（{VARIANT_LABELS[best]}，RAID 测试集）", "",
              "| 模型 | 篇数 | 很可能 | 可能 |", "|---|---|---|---|"]
    for name in RAID_AI_MODELS:
        sub = [d for d in t_ai if d["model"] == name]
        lines.append(f"| {name} | {len(sub)} | {pct(rate(sub, lambda d: d['prob'][best] >= th['likely']))} | "
                     f"{pct(rate(sub, lambda d: d['prob'][best] >= th['possible']))} |")

    lines += ["", f"### 按领域的误判率（{VARIANT_LABELS[best]}，RAID 测试集人写文本）", "",
              "| 领域 | 篇数 | 很可能 | 可能 |", "|---|---|---|---|"]
    for name in RAID_DOMAINS:
        sub = [d for d in t_h if d["domain"] == name]
        lines.append(f"| {name} | {len(sub)} | {pct(rate(sub, lambda d: d['prob'][best] >= th['likely']))} | "
                     f"{pct(rate(sub, lambda d: d['prob'][best] >= th['possible']))} |")

    lines += ["", "## 2026 基准（新模型、非母语作者）", "",
              "这部分完全没参与训练，用来看模型换了数据还靠不靠谱。人写的部分看误判率，AI 部分看检出率。"
              "表里是按“可能有 AI 成分”这条线算的。", "",
              "| 子集 | 篇数 | 平均词数 | " + " | ".join(VARIANT_LABELS[v] for v in variants) + " |",
              "|---|---|---|" + "---|" * len(variants)]
    bench_groups = defaultdict(list)
    for d in bench:
        key = d["model"] if d["label"] == "ai" else d["domain"]
        bench_groups[(d["label"], key)].append(d)
    for (label, key), sub in sorted(bench_groups.items()):
        cells = [pct(rate(sub, lambda d: d["prob"][v] >= model["doc"][v]["thresholds"]["possible"])) for v in variants]
        lines.append(f"| {'AI · ' if label == 'ai' else '人写 · '}{key} | {len(sub)} | "
                     f"{statistics.mean(d['rule']['words'] for d in sub):.0f} | " + " | ".join(cells) + " |")

    # 逐句：新模型 vs 旧版拍脑袋的阈值
    test_sents = sentence_rows(test)
    s_h = [r for r in test_sents if r["label"] == "human"]
    s_ai = [r for r in test_sents if r["label"] == "ai"]
    lines += ["", "## 逐句检查（RAID 测试集）", "",
              "句子的标签按所在文章算。AI 文章里也有很普通的句子，所以逐句检出率天然比整篇低。", "",
              "| 方法 | 人写句子被标“很像 AI” | AI 句子被标“很像 AI” | 人写句子被标（任一级） | AI 句子被标（任一级） |",
              "|---|---|---|---|---|"]
    for variant in variants:
        m = model["sentence"][variant]
        lv = lambda r: nm.sentence_level(m, nm.probability(m, r["values"]))
        lines.append(f"| {VARIANT_LABELS[variant]} | {pct(rate(s_h, lambda r: lv(r) == 2))} | "
                     f"{pct(rate(s_ai, lambda r: lv(r) == 2))} | {pct(rate(s_h, lambda r: lv(r) >= 1))} | "
                     f"{pct(rate(s_ai, lambda r: lv(r) >= 1))} |")
    lines.append(f"| 旧版阈值（困惑度 < 20 等） | {pct(rate(s_h, lambda r: old_level(r) == 2))} | "
                 f"{pct(rate(s_ai, lambda r: old_level(r) == 2))} | {pct(rate(s_h, lambda r: old_level(r) >= 1))} | "
                 f"{pct(rate(s_ai, lambda r: old_level(r) >= 1))} |")

    lines += ["", "## 套话表", "",
              f"只用训练集统计，只保留在三个领域里都偏向 AI 的短语，共 {len(phrase_rows)} 个。"
              "AI 篇数 / 人写篇数是含有这个短语的文章数（训练集 AI "
              f"{n_train['ai']} 篇、人写 {n_train['human']} 篇）。", "",
              "| 短语 | AI 篇数 | 人写篇数 |", "|---|---|---|"]
    for _, gram, a, h in phrase_rows:
        lines.append(f"| {gram} | {a} | {h} |")
    lines += ["", "旧版手写套话表在训练集里的情况。数据没有反驳的（人写文本里没出现过，或者 AI 文本里至少多一倍）保留，"
              "其余删掉：", "", "| 短语 | AI 篇数 | 人写篇数 | 结果 |", "|---|---|---|---|"]
    for p in OLD_PHRASES:
        key = " ".join(textfeatures.words(p))
        lines.append(f"| {p} | {df['ai'].get(key, 0)} | {df['human'].get(key, 0)} | "
                     f"{'保留' if key in kept_old else '删掉'} |")

    model["evaluation"] = {v: {k: round(x, 4) for k, x in row.items()} for v, row in summary.items()}
    with open(ROOT / "model.json", "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=1)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("\n已写出 model.json 和 reports/evaluation.md", file=sys.stderr)


def old_phrase_rate(text):
    lower = text.lower()
    words = len(text.split())
    return sum(lower.count(p) for p in OLD_PHRASES) * 1000 / max(words, 1)


def old_level(r):
    """旧版网页里的逐句分级规则，用来和新模型对比。"""
    hits = sum(1 for p in OLD_PHRASES if p in _sentence_text(r).lower())
    ppl = r["lm"]["ppl"] if r["lm"] and r["lm"]["tokens"] >= 8 else None
    level = 2 if hits >= 2 else 1 if hits else 0
    if ppl is not None and (ppl < 20 or (ppl < 30 and hits)):
        level = 2
    elif ppl is not None and ppl < 25:
        level = max(level, 1)
    return level


def _sentence_text(r):
    import textfeatures
    norm = textfeatures.normalize(r["doc"]["text"])
    return norm[r["s"]["start"]:r["s"]["end"]]


if __name__ == "__main__":
    commands = {"fetch": cmd_fetch, "run": cmd_run}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(__doc__)
        sys.exit(1)
    commands[sys.argv[1]](*sys.argv[2:])
