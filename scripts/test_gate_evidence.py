"""Regression checks for the opt-in overlay and workflow contract."""
import json
from pathlib import Path
import tempfile
import unittest
import yaml
from jsonschema import Draft202012Validator
from setup_repo import Overlay, render, apply_existing_overlay

ROOT = Path(__file__).resolve().parents[1]


class Contract(unittest.TestCase):
    def setUp(self):
        self.validator = Draft202012Validator(json.loads((ROOT / 'overlay.schema.json').read_text()))
        self.binding = dict(verify='verify-evidence', release='release-gate', documentation='docs/gating.md')

    def test_existing_overlay_unchanged(self):
        self.validator.validate({'schema': 1, 'gate': ['test']})
        self.assertNotIn('gate_evidence:', render(Overlay(name='fixture', target=Path('/tmp/fixture'))))

    def test_all_bindings_required_and_typos_rejected(self):
        self.validator.validate({'schema': 1, 'gate_evidence': self.binding})
        for key in self.binding:
            missing = dict(self.binding)
            del missing[key]
            self.assertTrue(list(self.validator.iter_errors({'schema': 1, 'gate_evidence': missing})))
        self.assertTrue(list(self.validator.iter_errors({'schema': 1, 'gate_evidence': dict(self.binding, typo='x')})))

    def test_renderer_preserves_opt_in(self):
        info = Overlay(name='fixture', target=Path('/tmp/fixture'))
        apply_existing_overlay(info, {'gate_evidence': self.binding})
        rendered = render(info)
        self.assertEqual(rendered.count("\ngate_evidence:"), 1)
        result = yaml.safe_load(rendered)
        self.assertEqual(result['gate_evidence'], self.binding)
        self.validator.validate(result)


if __name__ == '__main__':
    unittest.main()
