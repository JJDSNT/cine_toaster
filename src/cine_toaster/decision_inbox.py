"""Read-only projection of real human requests, not another approval store."""
from urllib.parse import urlencode

from .creation import creation_view
from .project import load_production


def decision_inbox(root):
    creation = creation_view(root); production = load_production(root)
    current = (creation.get('inception_review') or {}).get('current') or {}
    items = []; agent_work = []
    if current.get('status') == 'awaiting_decision':
        proposal = current['proposal']; preview = current.get('handoff_preview') or {}
        target = preview.get('target') or {}
        url = '/app/creation.html#direction-review'
        if proposal.get('direction_plan') and target.get('scene'):
            url = '/app/preproduction.html?' + urlencode({'scene': target['scene']}) + '#direction-review'
        items.append({'id': current['id'], 'kind': 'direction', 'title': current['title'],
                      'question': proposal['question'], 'scope': proposal['scope'], 'why': proposal['why'],
                      'next_step': proposal['next_step'], 'url': url, 'target': preview.get('target'),
                      'evidence': current['materials'], 'actions': ['approve', 'request_changes']})
    elif current.get('status') == 'needs_reassessment':
        agent_work.append({'id': current['id'], 'state': 'needs_reassessment',
                           'instruction': 'Agent must refresh the proposal before a human can decide.',
                           'url': '/app/creation.html#direction-review'})
    from .intake import inbox_items
    items.extend(inbox_items(creation['intake']))
    for scene in production['scenes']:
        for identity, gate in (scene.get('gates') or {}).items():
            if gate.get('state') != 'waiting':
                continue
            items.append({'id': identity, 'kind': gate.get('kind', 'gate'), 'title': scene['title'],
                          'question': 'Review ' + gate.get('kind', 'production gate').replace('_', ' '),
                          'scope': scene['id'] + ' / ' + str(gate.get('subject', '')),
                          'why': 'The production has explicitly opened this human gate.',
                          'next_step': 'The existing workflow continues after its gate decision.',
                          'url': '/?' + urlencode({'scene': scene['id']}) + '#workflow',
                          'evidence': {'candidates': gate.get('candidates', [])}, 'actions': ['open_origin']})
    for handoff in creation.get('handoffs', []):
        agent_work.append({'id': handoff['id'], 'state': 'sources_changed' if handoff['stale'] else
                           'outputs_retained' if handoff['outputs'] else 'awaiting_agent_output',
                           'instruction': handoff['instruction'], 'decision': handoff['decision'],
                           'target': handoff['target'], 'outputs': handoff['outputs'],
                           'url': '/app/preproduction.html?' + urlencode({'scene': handoff['target']['scene']})})
    agent_work.extend(creation.get('sequence_work', {}).get('items', []))
    pending_agent = sum(item['state'] != 'outputs_retained' for item in agent_work)
    return {'project_id': production['id'], 'revision': creation['revision'], 'pending_count': len(items),
            'agent_work_count': pending_agent,
            'items': items, 'agent_work': agent_work,
            'coverage': 'Saved current direction requests, open interview questions and waiting scene/workflow gates. Warnings and informal choices are not invented gates.'}
