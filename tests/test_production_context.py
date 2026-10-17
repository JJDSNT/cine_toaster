"""Production agents get canonical work structure, not a developer's chat memory."""
from __future__ import annotations

import copy
import json
import unittest

from cine_toaster.agents.reads import overview, read
from cine_toaster.errors import ResourceNotFoundError, ValidationError
from cine_toaster.production_context import WORK_POLICY, work_structure


def film():
    ids = ['1-01', '1-02', '1-02A', '1-02B', '1-02C', '1-03', '1-04', '3-01', 'unplaced']
    return {'id': 'a-film', 'title': 'A film',
            'scenes': [{'id': identity, 'shots': [{'id': 'P1'}]} for identity in ids],
            'sequences': [{'id': 'first', 'label': 'First movement', 'scene_ids': ids[:7]},
                          {'id': 'later', 'scene_ids': ['3-01']}]}


class Runtime:
    def __init__(self, production):
        self.value = production

    def production(self):
        return copy.deepcopy(self.value)


class ProductionContextTests(unittest.TestCase):
    def test_exact_membership_preserves_subdivisions_order_and_review_unit(self):
        value = work_structure(film(), scene='1-02B')
        self.assertEqual(value['review_unit'], 'sequence')
        self.assertEqual(value['scene_sequences'], ['first'])
        self.assertEqual(value['sequences'][0]['scene_ids'],
                         ['1-01', '1-02', '1-02A', '1-02B', '1-02C', '1-03', '1-04'])
        self.assertEqual(value['sequences'][0]['shot_count'], 7)
        self.assertEqual(value['unassigned_scene_ids'], ['unplaced'])

    def test_missing_members_are_not_silently_removed(self):
        production = film()
        production['sequences'][0]['scene_ids'].insert(1, 'missing')
        value = work_structure(production)['sequences'][0]
        self.assertEqual(value['missing_scene_ids'], ['missing'])
        self.assertEqual(value['scene_ids'][1], 'missing')

    def test_scope_is_selected_by_canonical_id_not_label_or_numeric_range(self):
        value = work_structure(film(), sequence='first')
        self.assertEqual(len(value['sequences']), 1)
        with self.assertRaises(ResourceNotFoundError):
            work_structure(film(), sequence='First movement')
        with self.assertRaises(ResourceNotFoundError):
            work_structure(film(), scene='1-02D')
        with self.assertRaises(ValidationError):
            work_structure(film(), sequence='first', scene='3-01')

    def test_ungrouped_imported_film_does_not_get_an_invented_sequence(self):
        production = film()
        production['sequences'] = []
        value = work_structure(production, scene='1-01')
        self.assertEqual(value['sequences'], [])
        self.assertEqual(value['scene_sequences'], [])
        self.assertEqual(len(value['unassigned_scene_ids']), 9)

    def test_ambiguous_parent_is_not_silently_chosen(self):
        production = film()
        production['sequences'][1]['scene_ids'].append('1-01')
        self.assertEqual(work_structure(production, scene='1-01')['scene_sequences'], ['first', 'later'])

    def test_film_identity_and_membership_are_reread_not_cached_across_projects(self):
        runtime = Runtime(film())
        first = json.loads(read(runtime, 'work_structure', {'sequence': 'first'}))
        runtime.value = {'id': 'other', 'title': 'Other', 'scenes': [], 'sequences': []}
        second = json.loads(read(runtime, 'work_structure', {}))
        self.assertEqual((first['project_id'], second['project_id']), ('a-film', 'other'))
        self.assertEqual(second['sequences'], [])
        self.assertNotIn('1-02B', json.dumps(second))

    def test_explicit_read_keeps_whole_parent_sequence_when_scene_is_focused(self):
        value = json.loads(read(Runtime(film()), 'work_structure', {'sequence': 'first', 'scene': '1-02B'}))
        self.assertEqual(value['focused_scene'], '1-02B')
        self.assertEqual(len(value['sequences'][0]['scene_ids']), 7)
        self.assertIn('readiness', value['policy'])
        self.assertNotIn('approved', value)

    def test_unknown_read_scope_is_a_visible_failure_not_an_empty_pass(self):
        self.assertIn('The read failed:', read(Runtime(film()), 'work_structure', {'sequence': 'invented'}))

    def test_overview_cannot_truncate_away_the_work_contract_or_last_sequence(self):
        production = film()
        production['scenes'][0]['title'] = 'Large scene detail ' * 500
        text = overview(production)
        self.assertIn(WORK_POLICY, text)
        self.assertIn('"id": "later"', text)
        self.assertIn('1-02C', text)
        self.assertIn('cut short', text)

    def test_context_does_not_mutate_film_or_synthesize_production_decisions(self):
        production = film()
        original = copy.deepcopy(production)
        value = work_structure(production)
        value['sequences'][0]['scene_ids'].append('not-canonical')
        self.assertEqual(production, original)
        self.assertNotIn('readiness', value)
        self.assertNotIn('gates', value)


if __name__ == '__main__':
    unittest.main()
