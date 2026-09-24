"""Browser regression checks against Vite; all API responses are local fixtures."""
import argparse
import copy
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:5175')
    args = parser.parse_args()
    evidence = {'id': 'E1', 'repository': 'claims', 'file': 'services.py', 'symbol': 'submit_claim', 'lineStart': 10, 'lineEnd': 12, 'snippet': 'def submit_claim():\n    return save_claim()', 'evidenceType': 'CODE'}
    graph = {'nodes': [{'id': 'service', 'name': 'ClaimsService', 'type': 'service', 'evidence': [evidence]}, {'id': 'db', 'name': 'claims', 'type': 'database', 'evidence': [evidence]}], 'edges': [{'source': 'service', 'target': 'db', 'relationship': 'calls', 'evidence': [evidence]}]}
    template = {'status': 'COMPLETED', 'repositories': [{'type': 'local', 'path': 'C:/fixtures/claims'}], 'createdAt': '2026-09-23T00:00:00Z', 'updatedAt': '2026-09-23T00:00:00Z', 'progress': {'step': 8, 'totalSteps': 8, 'percent': 100, 'message': 'Complete'}, 'overview': {'repositories': 1, 'services': 1, 'classes': 2, 'apis': 2, 'databaseTables': 1, 'externalIntegrations': None, 'scheduledJobs': None}, 'architecture': graph, 'flows': [{'id': 'flow', 'title': 'Submit claim', **graph}], 'businessRules': [{'id': 'BR-001', 'title': 'Positive amount', 'description': 'Amounts must be positive.', 'confidence': 'LOW', 'evidence': [evidence]}], 'limitations': ['Bounded fixture analysis.']}
    analyses = {f'saved-{i}': {**copy.deepcopy(template), 'analysisId': f'saved-{i}', 'name': f'claims-service-{i}'} for i in range(18)}
    deleted, starts, errors = [], [], []
    fail_delete = {'enabled': False}

    def respond(route):
        path = urlsplit(route.request.url).path
        method = route.request.method
        status, data = 200, {'success': True}
        if path.endswith('/health'):
            data = {'status': 'UP'}
        elif path.endswith('/models'):
            data.update(models=[{'id': 'amazon.nova-lite-v1:0', 'label': 'Amazon Nova Lite v1'}])
        elif path.endswith('/model'):
            data.update(model_id='amazon.nova-lite-v1:0')
        elif '/legacy-intelligence/recent' in path:
            data.update(analyses=list(analyses.values()))
        elif path.endswith('/legacy-intelligence/analyze'):
            starts.append(route.request.post_data_json)
            data.update(analysis=analyses['saved-1'])
            status = 202
        elif path.endswith('/legacy-intelligence/chat'):
            data.update(answer='ClaimsService submits the claim [E1].', evidence=[evidence])
        elif path.endswith('/documentation'):
            data.update(documents=[{'type': 'application_overview', 'title': 'Application Overview', 'content': 'Claims service documentation [E1].', 'evidence': [evidence]}])
        elif '/legacy-intelligence/' in path:
            key = path.split('/legacy-intelligence/')[1]
            if method == 'DELETE' and fail_delete['enabled']:
                status, data = 500, {'success': False, 'error': 'Deletion temporarily unavailable.'}
            elif method == 'DELETE' and key in analyses:
                del analyses[key]
                deleted.append(key)
                data.update(analysisId=key)
            elif key in analyses:
                data.update(analysis=analyses[key])
            else:
                status, data = 404, {'success': False, 'error': 'Analysis not found.'}
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data), headers={'Access-Control-Allow-Origin': '*'})

    output = Path(__file__).resolve().parents[1] / 'generated'
    output.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1366, 'height': 768})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/api/**', respond)
        page.goto(args.url + '/#/legacy-intelligence')
        expect(page.locator('.li-recent-row')).to_have_count(18)
        layout = page.evaluate('''() => {
          const main = document.querySelector('.main-content');
          const list = document.querySelector('.li-recent-list');
          const heading = document.querySelector('.topbar h1');
          return {aligned: getComputedStyle(heading).textAlign, main: [main.scrollHeight, main.clientHeight],
            document: [document.documentElement.scrollHeight, innerHeight], sidebar: [document.querySelector('.sidebar').scrollHeight, document.querySelector('.sidebar').clientHeight],
            list: [list.scrollHeight, list.clientHeight], headingX: heading.getBoundingClientRect().left,
            breadcrumbX: document.querySelector('.breadcrumb').getBoundingClientRect().left};
        }''')
        print(json.dumps(layout), flush=True)
        assert layout['aligned'] == 'left'
        assert abs(layout['headingX'] - layout['breadcrumbX']) < 2
        for area in ('main', 'document', 'sidebar'):
            assert layout[area][0] <= layout[area][1] + 1, (area, layout[area])
        assert layout['list'][0] > layout['list'][1]
        def shell_geometry():
            return page.evaluate('''() => ['.brand', '.new-build-btn', '.sidebar-capabilities', '.engine-card', '.topbar', '.topbar h1', '.topbar-actions'].map(selector => {
                const r = document.querySelector(selector).getBoundingClientRect();
                return {selector, x: r.x, y: r.y, height: r.height};
            })''')
        baseline = shell_geometry()
        def assert_stable_shell():
            actual = shell_geometry()
            for expected, current in zip(baseline, actual):
                for dimension in ('x', 'y', 'height'):
                    assert abs(expected[dimension] - current[dimension]) < 1, (expected, current)
        page.screenshot(path=str(output / 'legacy-home-1366.png'), full_page=True)
        page.get_by_role('button', name='Multiple Repositories', exact=True).click()
        page.get_by_role('button', name='Add repository', exact=True).click()
        expect(page.locator('.li-repository-row')).to_have_count(3)
        page.get_by_role('button', name='Remove repository 3').click()
        expect(page.locator('.li-repository-row')).to_have_count(2)
        page.get_by_role('button', name='Local Folder', exact=True).click()
        expect(page.get_by_role('textbox', name='Local repository folder')).to_be_visible()
        field = page.get_by_role('textbox', name='Local repository folder')
        before_focus = field.bounding_box()
        field.click()
        assert field.bounding_box() == before_focus
        assert field.evaluate('(el) => getComputedStyle(el).outlineStyle') == 'none'
        assert field.evaluate('(el) => getComputedStyle(el.parentElement).boxShadow') != 'none'
        page.screenshot(path=str(output / 'legacy-path-focus.png'), full_page=True)
        # Opening history reads a saved snapshot; it never starts analysis.
        page.locator('.li-recent-item').first.click()
        expect(page.get_by_role('button', name='Generate Documentation', exact=True)).to_be_enabled()
        assert_stable_shell()
        assert not starts
        page.get_by_role('button', name='Generate Documentation', exact=True).click()
        expect(page.locator('.li-document-options input')).to_have_count(12)
        page.get_by_role('button', name='Generate Documentation', exact=True).click()
        expect(page.locator('.li-evidence')).to_have_count(1)
        page.locator('.li-evidence summary').click()
        expect(page.get_by_text('services.py', exact=False)).to_be_visible()
        page.get_by_role('button', name='Back to overview').click()
        page.get_by_role('button', name='Ask the Codebase', exact=True).click()
        page.get_by_role('textbox', name='Ask a question about your codebase').fill('How is a claim submitted?')
        page.get_by_role('button', name='Send question').click()
        expect(page.locator('.li-chat-message')).to_have_count(1)
        page.get_by_role('button', name='Back to overview').click()
        page.get_by_role('button', name='Delete analysis claims-service-0', exact=True).click()
        expect(page).to_have_url(args.url + '/#/legacy-intelligence')
        expect(page.locator('.li-recent-row')).to_have_count(17)
        assert deleted == ['saved-0']
        fail_delete['enabled'] = True
        page.get_by_role('button', name='Delete analysis claims-service-1', exact=True).click()
        expect(page.get_by_role('alert')).to_contain_text('Deletion temporarily unavailable')
        expect(page.locator('.li-recent-row')).to_have_count(17)
        fail_delete['enabled'] = False
        page.get_by_role('button', name='Delete analysis claims-service-1', exact=True).click()
        expect(page.locator('.li-recent-row')).to_have_count(16)
        page.get_by_role('button', name='View all', exact=False).click()
        expect(page.locator('.li-recent-full')).to_be_visible()
        page.locator('.sidebar-capabilities button').filter(has_text='Application Builder').click()
        expect(page.get_by_role('textbox', name='Business Requirement')).to_be_visible()
        assert_stable_shell()
        expect(page.locator('.sidebar').get_by_role('button', name='History')).to_have_count(0)
        page.get_by_role('button', name='Build history', exact=True).click()
        expect(page.get_by_role('dialog', name='Requirement history')).to_be_visible()
        page.get_by_role('button', name='Close history').click()
        page.screenshot(path=str(output / 'builder-shell.png'), full_page=True)
        page.locator('.sidebar-capabilities button').filter(has_text='Change Impact').click()
        expect(page.get_by_role('textbox', name='Change description')).to_be_visible()
        expect(page.get_by_label('Workspace capabilities')).to_have_count(0)
        assert_stable_shell()
        page.screenshot(path=str(output / 'impact-shell.png'), full_page=True)
        page.goto(args.url + '/#/legacy-intelligence')
        # A taller desktop keeps the same no-scroll initial state.
        page.set_viewport_size({'width': 1920, 'height': 1080})
        expect(page.locator('.li-recent-row')).to_have_count(16)
        assert page.locator('.main-content').evaluate('(el) => el.scrollHeight <= el.clientHeight + 1')
        page.screenshot(path=str(output / 'legacy-home-1920.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(page.locator('.li-recent-row')).to_have_count(16)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(output / 'legacy-home-mobile.png'), full_page=True)
        analyses.clear()
        page.reload()
        expect(page.get_by_text('Your analyzed repositories will appear here.', exact=False)).to_be_visible()
        assert not errors, errors
        browser.close()
    print('PASS: stable shared shell, left-aligned headers, desktop scrolling, mobile layout, path focus, saved results, deletion/errors, docs/chat evidence, integrated History, Change Impact badges removed.')


if __name__ == '__main__':
    main()
