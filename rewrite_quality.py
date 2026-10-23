"""Conservative, explainable checks. Passing these does not prove semantic fidelity."""
import re
from collections import Counter

import model as detector
import textfeatures

NUMBER = re.compile(r'(?<![\w])[-+]?\d+(?:[,\.]\d+)*(?:\s?%|\b)')
CITATION = re.compile(r'\[[\d,;\s\-–]+\]|\([^()\n]{0,100}\b(?:19|20)\d{2}[a-z]?[^()\n]{0,40}\)')
QUOTE = re.compile(r'"([^"\n]{4,})"|“([^”\n]{4,})”')


def preserved_tokens(pattern, text):
    return Counter(m.group(0) for m in pattern.finditer(text))


def check(source, output, terms, style):
    missing = [term for term in dict.fromkeys(terms) if term and term in source and term not in output]
    issues = []
    if missing:
        issues.append('遗漏指定术语：' + '、'.join(missing))
    for title, pattern in [('数字', NUMBER), ('引用', CITATION), ('直接引语', QUOTE)]:
        before, after = preserved_tokens(pattern, source), preserved_tokens(pattern, output)
        lost = list((before - after).elements())
        added = list((after - before).elements())
        if lost:
            issues.append(f'{title}缺失或发生变化：' + '、'.join(lost[:10]))
        if added:
            issues.append(f'新增或重复{title}：' + '、'.join(added[:10]))
    before_words, after_words = len(textfeatures.words(source)), len(textfeatures.words(output))
    ratio = after_words / max(before_words, 1)
    if ratio < (0.55 if style == 'concise' else 0.7) or ratio > 1.4:
        issues.append('篇幅变化较大，可能遗漏信息或增添内容。')
    if re.search(r'[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]', output):
        issues.append('结果含不可见控制字符。')
    if any('\u0400' <= c <= '\u04ff' for c in output) and not any('\u0400' <= c <= '\u04ff' for c in source):
        issues.append('结果新增西里尔字母，可能存在异形字替换。')
    if not output.strip():
        issues.append('结果为空。')
    warnings = []
    if source.strip() == output.strip():
        warnings.append('结果与原文相同。')
    return {'passed': not issues, 'issues': issues, 'warnings': warnings,
            'missing_terms': missing, 'word_ratio': round(ratio, 3)}


def local_score(text):
    """Same rule model for both sides; never mix engines or infer third-party scores."""
    config = detector.load()
    rule = textfeatures.analyze(text, config['phrases'])
    if rule['words'] < config['min_words']:
        return {'score': None, 'engine': 'rules', 'reason': '少于 80 词，不评分'}
    probability = detector.probability(config['doc']['rules'], detector.doc_values(rule))
    return {'score': round(probability * 100, 3), 'engine': 'rules', 'reason': '仅 Nuts 规则模型，不能预测外部平台'}
