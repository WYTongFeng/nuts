import unittest
from unittest.mock import patch

import rewrite_quality as quality
import rewriting


class QualityTest(unittest.TestCase):
    def test_numbers_dates_and_citations_are_preserved(self):
        source = 'The API served 1,200 users in 2024, with 12.5% growth (Smith, 2023) [1, 2].'
        result = quality.check(source, source.replace('served', 'supported'), ['API'], 'natural')
        self.assertTrue(result['passed'])

    def test_changed_or_added_numbers_fail(self):
        source = 'Revenue rose by 12.5% in 2024.'
        for output in ['Revenue rose by 20% in 2024.', source + ' It reached 500 people.']:
            self.assertFalse(quality.check(source, output, [], 'natural')['passed'])

    def test_missing_citations_and_quotes_fail(self):
        source = 'The report states "No evidence of harm" (Smith, 2024).'
        self.assertFalse(quality.check(source, 'The report states there is no evidence of harm in 2024.', [], 'natural')['passed'])

    def test_large_omission_fails(self):
        source = 'A useful system records events and processes requests while maintaining detailed audit records.'
        self.assertFalse(quality.check(source, 'A useful system.', [], 'natural')['passed'])

    def test_homoglyphs_and_invisible_characters_fail(self):
        for output in ['The A\u200bPI works correctly.', 'The \u0410PI works correctly.']:
            self.assertFalse(quality.check('The API works correctly.', output, [], 'natural')['passed'])

    def test_missing_terms_and_identical_output(self):
        source = 'The Java API works correctly.'
        self.assertFalse(quality.check(source, 'The interface works correctly.', ['Java', 'API'], 'natural')['passed'])
        self.assertTrue(quality.check(source, source, ['API'], 'natural')['warnings'])

    def test_short_text_is_unknown_not_zero(self):
        self.assertIsNone(quality.local_score('A short sentence.')['score'])

    def test_review_failure_cannot_be_eligible(self):
        with patch.object(rewriting, 'status', return_value={'models':['local']}), patch.object(rewriting, 'chat', side_effect=['The API works correctly.', ValueError('bad review')]):
            result = rewriting.rewrite('The API functions correctly.', 'natural', 'local', ['API'], audit=True)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['review']['status'], 'unavailable')

    def test_semantic_discrepancy_blocks_recommendation(self):
        review = '{"meaning_preserved":false,"added_claims":[],"missing_claims":["Lost negation"],"changed_claims":[]}'
        with patch.object(rewriting, 'status', return_value={'models':['local']}), patch.object(rewriting, 'chat', side_effect=['The API always works correctly.', review]):
            result = rewriting.rewrite('The API does not work correctly.', 'natural', 'local', ['API'], audit=True)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['review']['status'], 'flagged')

    def test_structured_review_required(self):
        for raw in ['not json', '{"meaning_preserved":"yes"}', '{"meaning_preserved":true,"added_claims":[1],"missing_claims":[],"changed_claims":[]}']:
            with patch.object(rewriting, 'chat', return_value=raw):
                self.assertEqual(rewriting.review('source', 'output', 'local')['status'], 'unavailable')

    def test_successful_review_and_prompt_variants(self):
        passed = '{"meaning_preserved":true,"added_claims":[],"missing_claims":[],"changed_claims":[]}'
        with patch.object(rewriting, 'status', return_value={'models':['local']}), patch.object(rewriting, 'chat', side_effect=['The API works correctly.', passed]) as chat:
            result = rewriting.rewrite('The API functions correctly.', 'formal', 'local', ['API'], attempt=1, strength='deep', voice='My sample.', audit=True)
            prompt = chat.call_args_list[0].args[1]
        self.assertTrue(result['eligible'])
        self.assertEqual(result['strategy'], '重组句式')
        self.assertIn('My sample.', prompt[1]['content'])
        self.assertIn('Preserve uncertainty', prompt[0]['content'])


if __name__ == '__main__':
    unittest.main()
