/* Nuts 核心计算（网页用）：textfeatures.py 和 model.py 的逐行对照版。
   改这里要同步改 Python 那边，tests/test_consistency.py 会对比两边算出的结果。 */
(function (root) {
  "use strict";

  // 句号后面紧跟这些词时不算句子结束
  const ABBREVIATIONS = new Set([
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "e.g", "i.e", "cf", "fig", "figs",
    "no", "vol", "pp", "al", "approx", "inc", "ltd", "u.s", "u.k",
  ]);
  const TERMINAL = ".!?:;\"')]”";
  const MATTR_WINDOW = 50;
  const MIN_SENTENCE_WORDS = 3; // 少于 3 个词的片段（标题、编号）不参与句长统计
  const MIN_SENTENCE_TOKENS = 5; // 句子太短时困惑度不稳定，当作缺失

  const SENTENCE_END = /[.!?]+["')\]”]*(?=\s|$)/g;
  const WORD_BEFORE = /([A-Za-z][A-Za-z.]*)$/;

  const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
  const pstdev = (a) => { const m = mean(a); return Math.sqrt(mean(a.map((x) => (x - m) ** 2))); };
  const splitCount = (s) => s.trim().split(/\s+/).filter(Boolean).length;

  // 统一引号和换行，结果和原文长度相同（位置可以直接对回原文）
  function normalize(text) {
    text = text.replace(/\r/g, " ").replace(/[‘’]/g, "'");
    const pieces = text.split(/(\n[ \t]*\n\s*)/);
    for (let i = 0; i < pieces.length; i += 2) {
      const lines = pieces[i].split("\n");
      const candidates = lines.slice(0, -1).filter((line) => line.trim());
      if (!candidates.length) continue;
      const paragraphLike = candidates.filter((line) => TERMINAL.includes(line.trimEnd().slice(-1)) || splitCount(line) <= 5).length;
      if (paragraphLike / candidates.length < 0.5) pieces[i] = pieces[i].replace(/\n/g, " ");
    }
    return pieces.join("");
  }

  // normalize() 之后，剩下的换行都是段落分隔
  function paragraphs(norm) {
    return norm.split(/\s*\n\s*/).filter((p) => p.trim());
  }

  // 切句，返回每句的 [起点, 终点]，已去掉首尾空白；段落分隔也算句子边界
  function sentenceSpans(norm) {
    const cuts = new Set([0, norm.length]);
    for (const m of norm.matchAll(SENTENCE_END)) {
      const g = m[0];
      if (g[0] === "." && g.split(".").length === 2) {
        const before = norm.slice(Math.max(0, m.index - 20), m.index).match(WORD_BEFORE);
        if (before && (ABBREVIATIONS.has(before[1].toLowerCase()) || /^[A-Z]$/.test(before[1]))) continue;
      }
      cuts.add(m.index + g.length);
    }
    for (const m of norm.matchAll(/\n/g)) cuts.add(m.index);
    const sorted = [...cuts].sort((a, b) => a - b);
    const spans = [];
    for (let i = 0; i + 1 < sorted.length; i++) {
      const seg = norm.slice(sorted[i], sorted[i + 1]);
      if (seg.trim()) spans.push([sorted[i] + seg.length - seg.trimStart().length, sorted[i + 1] - (seg.length - seg.trimEnd().length)]);
    }
    return spans;
  }

  // 英文单词（小写）和位置，去掉词两头的撇号
  function wordsWithPos(text) {
    const out = [];
    for (const m of text.toLowerCase().matchAll(/[a-z']+/g)) {
      const word = m[0].replace(/^'+|'+$/g, "");
      if (word) {
        const start = m.index + m[0].length - m[0].replace(/^'+/, "").length;
        out.push([word, start, start + word.length]);
      }
    }
    return out;
  }

  const words = (text) => wordsWithPos(text).map((w) => w[0]);

  // 滑动窗口的词汇多样性（MATTR）
  function mattr(tokens, window = MATTR_WINDOW) {
    if (!tokens.length) return null;
    if (tokens.length <= window) return new Set(tokens).size / tokens.length;
    const counts = new Map();
    for (const t of tokens.slice(0, window)) counts.set(t, (counts.get(t) || 0) + 1);
    let unique = counts.size;
    let total = unique;
    for (let i = window; i < tokens.length; i++) {
      const old = tokens[i - window], next = tokens[i];
      counts.set(old, counts.get(old) - 1);
      if (counts.get(old) === 0) unique -= 1;
      if (!counts.get(next)) unique += 1;
      counts.set(next, (counts.get(next) || 0) + 1);
      total += unique;
    }
    return total / (tokens.length - window + 1) / window;
  }

  // 句子里每个套话出现的位置：[套话, 第几个词起, 第几个词止]
  function phraseHits(sentenceWords, phrases) {
    const hits = [];
    for (const phrase of phrases) {
      const parts = phrase.split(" ");
      const n = parts.length;
      let i = 0;
      while (i + n <= sentenceWords.length) {
        if (parts.every((p, k) => sentenceWords[i + k] === p)) {
          hits.push([phrase, i, i + n]);
          i += n;
        } else {
          i += 1;
        }
      }
    }
    return hits;
  }

  function analyze(text, phrases) {
    const norm = normalize(text);
    const sentences = sentenceSpans(norm).map(([start, end]) => {
      const wp = wordsWithPos(norm.slice(start, end));
      const ws = wp.map((w) => w[0]);
      return {
        start, end, words: ws.length,
        avg_word_len: ws.length ? mean(ws.map((w) => w.length)) : 0,
        commas: (norm.slice(start, end).match(/,/g) || []).length,
        hits: phraseHits(ws, phrases).map(([p, a, b]) => [p, start + wp[a][1], start + wp[b - 1][2]]),
      };
    });

    const allWords = words(norm);
    const lengths = sentences.filter((s) => s.words >= MIN_SENTENCE_WORDS).map((s) => s.words);
    const meanLen = lengths.length ? mean(lengths) : 0;
    const paraLens = paragraphs(norm).map((p) => words(p).length).filter((n) => n);
    const nHits = sentences.reduce((sum, s) => sum + s.hits.length, 0);
    const counted = sentences.filter((s) => s.words).length;

    return {
      words: allWords.length,
      sentences: counted,
      mean_len: meanLen,
      burst: lengths.length > 1 ? pstdev(lengths) / meanLen : 0,
      mattr: mattr(allWords),
      avg_word_len: allWords.length ? mean(allWords.map((w) => w.length)) : 0,
      phrases_per_1k: nHits * 1000 / Math.max(allWords.length, 1),
      commas_per_sentence: (norm.match(/,/g) || []).length / Math.max(counted, 1),
      para_cv: paraLens.length > 1 ? pstdev(paraLens) / mean(paraLens) : null,
      sentence_details: sentences,
    };
  }

  // ---------- 综合模型（与 model.py 相同） ----------

  function docValues(rule, lm) {
    const v = {
      burst: rule.burst,
      mattr: rule.mattr,
      avg_word_len: rule.avg_word_len,
      log_phrases: Math.log1p(rule.phrases_per_1k),
      commas_per_sentence: rule.commas_per_sentence,
      mean_len: rule.mean_len,
    };
    if (lm) {
      v.log_ppl = Math.log(lm.ppl);
      v.log_sent_ppl_std = lm.sent_ppl_std === null ? null : Math.log1p(lm.sent_ppl_std);
      v.top10 = lm.top10;
      v.bino = lm.bino === undefined ? null : lm.bino;
    }
    return v;
  }

  // 按拿到的语言模型分数挑最好的引擎（与 model.engine 相同）
  function engine(m, lm) {
    if (lm && lm.bino !== undefined && lm.bino !== null && m.doc.bino) return "bino";
    return lm ? "full" : "rules";
  }

  function sentenceValues(sentence, lmSentence) {
    const v = {
      log_hits: Math.log1p(sentence.hits.length),
      log_words: Math.log1p(sentence.words),
      avg_word_len: sentence.avg_word_len,
      commas: sentence.commas,
      log_ppl: null,
      top10: null,
      bino: null,
    };
    if (lmSentence && lmSentence.tokens >= MIN_SENTENCE_TOKENS) {
      v.log_ppl = Math.log(lmSentence.ppl);
      v.top10 = lmSentence.top10;
      v.bino = lmSentence.bino === undefined ? null : lmSentence.bino;
    }
    return v;
  }

  // 逻辑回归：按训练集均值、标准差标准化，缺失的特征当作均值
  function probability(m, values) {
    let z = m.intercept;
    m.features.forEach((name, i) => {
      const x = values[name];
      z += m.coef[i] * (((x === null || x === undefined ? m.mean[i] : x) - m.mean[i]) / m.scale[i]);
    });
    return z >= 0 ? 1 / (1 + Math.exp(-z)) : Math.exp(z) / (1 + Math.exp(z));
  }

  function docVerdict(m, prob, wordCount) {
    if (wordCount < m.min_words) return "too_short";
    return prob >= m.thresholds.likely ? "likely" : prob >= m.thresholds.possible ? "possible" : "unlikely";
  }

  function sentenceLevel(m, prob) {
    return prob >= m.thresholds.high ? 2 : prob >= m.thresholds.mid ? 1 : 0;
  }

  const api = {
    normalize, paragraphs, sentenceSpans, wordsWithPos, words, mattr, phraseHits, analyze,
    docValues, sentenceValues, engine, probability, docVerdict, sentenceLevel,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.NutsCore = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
