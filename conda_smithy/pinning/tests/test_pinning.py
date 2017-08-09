from unittest import TestCase
from conda_smithy.pinning import replace_strings, get_replacements


class TestReplacements(TestCase):

    def test_basic_pins(self):
        pinnings = {'foo': {'build': '1.0', 'run': '1.0'}}
        sections = {'build': ['foo 1.0'], 'run': ['foo']}

        # do not update when already up-to-date
        build_repl = get_replacements(sections, 'build', pins=pinnings)
        self.assertEqual(len(build_repl), 0)

        # update to latest version
        run_repl = get_replacements(sections, 'run', pins=pinnings)
        self.assertEqual(run_repl, [('foo', 'foo 1.0')])

    def test_star_pin(self):
        pinnings = {'foo': {'build': '1.0'}}
        sections = {'build': ['foo *']}

        # star dependencies should not be pinned
        build_repl = get_replacements(sections, 'build', pins=pinnings)
        self.assertEqual(len(build_repl), 0)

    def test_partial_hits(self):
        text = (
            '- boost-cpp 1.63.*\n'
            '- boost'
        )
        replacements = [
            ('- boost', '- boost 1.63.*'),
        ]

        result = replace_strings(replacements, text)
        exp_result = (
            '- boost-cpp 1.63.*\n'
            '- boost 1.63.*'
        )
        self.assertEqual(result, exp_result)

    def test_selectors(self):
        text = (
            '- foo 1.*  # [linux]'
        )
        replacements = [
            ('- foo 1.*', '- foo 2.*'),
        ]

        result = replace_strings(replacements, text)
        exp_result = (
            '- foo 2.*  # [linux]'
        )
        self.assertEqual(result, exp_result)
