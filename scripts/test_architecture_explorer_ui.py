"""Architecture explorer and readable flow regressions against local fixture APIs."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:5178')
    args = parser.parse_args()
    evidence = {'repository': 'claims-api', 'file': 'claims/service.py', 'lineStart': 24, 'snippet': 'def validate_claim(amount): return amount > 0'}
    specifications = [('web', 'Customer Portal', 'client', 'claims-web'), ('api', 'Claims API', 'api', 'claims-api'), ('auth', 'Identity Gateway', 'gateway', 'claims-api'), ('claims', 'Claims Service', 'service', 'claims-api'), ('policy', 'Policy Validation', 'service', 'claims-api'), ('db', 'Claims Database', 'database', 'claims-api'), ('provider', 'Payment Provider', 'external', 'claims-api'), ('job', 'Reconciliation Job', 'job', 'claims-api'), ('audit', 'Audit Log', 'database', 'claims-api')]
    nodes = [{'id': id, 'name': name, 'type': type, 'repository': repo, 'evidence': [evidence]} for id, name, type, repo in specifications]
    connections = [('web', 'api', 'submits claim'), ('api', 'auth', 'checks identity'), ('api', 'claims', 'requests processing'), ('claims', 'policy', 'validates policy'), ('claims', 'db', 'persists claim'), ('claims', 'provider', 'requests payment'), ('job', 'db', 'reads pending claims'), ('claims', 'audit', 'records outcome'), ('policy', 'db', 'reads policy data')]
    graph = {'nodes': nodes, 'edges': [{'source': source, 'target': target, 'relationship': label, 'evidence': [evidence]} for source, target, label in connections]}
    analysis = {'analysisId': 'explorer-test', 'name': 'Claims Platform', 'status': 'COMPLETED', 'repositories': [], 'createdAt': '2026-09-23', 'updatedAt': '2026-09-23', 'overview': {}, 'architecture': graph, 'flows': [{'id': 'submit', 'title': 'Submit a claim', 'description': 'The customer submits a claim for validation.', **graph}], 'businessRules': [], 'narratives': {'flows': '## Submit a claim\nA customer sends a claim for validation.'}}
    doc = {'type': 'application_flows', 'title': 'Application Flows', 'evidence': [evidence], 'content': '## Submit a claim\n\n### What starts it\nA customer submits a claim through the portal.\n\n### What happens\n1. The application checks the submitted claim.\n2. A valid claim is saved.\n\n### Result\nThe claim is available for processing.\n\n## Source Evidence\n- [E1] claims/service.py:24\n\n## Coverage Limitations\nPayment completion is not verified.'}
    state = {'saved': True, 'fail': False}
    writes, errors = [], []

    def respond(route):
        path = urlsplit(route.request.url).path
        data, status = {'success': True}, 200
        if path.endswith('/documentation'):
            if route.request.method == 'POST':
                writes.append(route.request.post_data_json)
            if state['fail']:
                status, data = 500, {'success': False, 'error': 'Fixture failure'}
            else:
                data['documents'] = [doc] if state['saved'] or route.request.method == 'POST' else []
        elif path.endswith('/recent'):
            data['analyses'] = [analysis]
        elif '/legacy-intelligence/explorer-test' in path:
            data['analysis'] = analysis
        elif path.endswith('/health'):
            data = {'status': 'UP'}
        elif path.endswith('/models'):
            data['models'] = []
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))

    output = Path(__file__).resolve().parents[1] / 'generated'
    output.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={'width': 1600, 'height': 1050}, device_scale_factor=1)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/api/**', respond)
        page.goto(args.url + '/#/legacy-intelligence/explorer-test/architecture')
        expect(page.locator('.ax-node')).to_have_count(9, timeout=30000)
        expect(page.locator('.react-flow__edge')).to_have_count(9)
        assert page.locator('iframe').count() == 0, 'The diagram must render without a remote iframe'
        page.wait_for_function("() => { const node = document.querySelector('.ax-node'), canvas = document.querySelector('.ax-canvas'), viewport = document.querySelector('.react-flow__viewport'); return node && canvas && viewport && viewport.style.transform !== 'translate(0px,0px) scale(1)' && node.getBoundingClientRect().top >= canvas.getBoundingClientRect().top; }")
        page.screenshot(path=str(output / 'architecture-explorer-desktop.png'), full_page=True)
        page.get_by_role('textbox', name='Find a component').fill('Claims Service')
        page.locator('.ax-search-results button').click()
        expect(page.locator('.ax-inspector h4')).to_have_text('Claims Service')
        evidence_panel = page.locator('.ax-inspector .li-evidence')
        assert not evidence_panel.evaluate('(el) => el.open')
        evidence_panel.locator('summary').click()
        expect(evidence_panel.locator('pre')).to_be_visible()
        page.get_by_role('button', name='Focus connections', exact=True).click()
        expect(page.locator('.ax-node')).to_have_count(6)
        page.get_by_role('button', name='Show full view', exact=True).click()
        expect(page.locator('.ax-node')).to_have_count(9)
        page.get_by_role('button', name='Clear selection').click()
        page.get_by_role('button', name='Left to right layout').click()
        expect(page.locator('.ax-node')).to_have_count(9)
        page.get_by_role('combobox', name='Filter by repository').select_option('claims-web')
        expect(page.locator('.ax-node')).to_have_count(1)
        page.get_by_role('button', name='Clear filters and selection').click()
        expect(page.locator('.ax-node')).to_have_count(9)
        with page.expect_download() as downloaded:
            page.get_by_role('button', name='draw.io', exact=True).click()
        xml_path = output / 'architecture-explorer.drawio'
        downloaded.value.save_as(xml_path)
        import xml.etree.ElementTree as ET
        xml = ET.parse(xml_path)
        assert len(xml.findall('.//mxCell[@vertex="1"]')) == 9
        assert len(xml.findall('.//mxCell[@edge="1"]')) == 9
        with page.expect_download() as downloaded:
            page.get_by_role('button', name='SVG', exact=True).click()
        svg_path = output / 'architecture-explorer.svg'
        downloaded.value.save_as(svg_path)
        ET.parse(svg_path)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(output / 'architecture-explorer-mobile.png'), full_page=True)
        page.set_viewport_size({'width': 1600, 'height': 1050})
        page.goto(args.url + '/#/legacy-intelligence/explorer-test/flows')
        expect(page.get_by_role('heading', name='What starts it', exact=True)).to_be_visible()
        expect(page.get_by_text('Payment completion is not verified.', exact=True)).to_be_visible()
        assert not writes, 'Existing flow documentation should be reused'
        assert page.locator('.ax-explorer').count() == 0, 'Collapsed flows must not load diagram workers'
        assert not page.locator('.li-document-sources').evaluate('(el) => el.open')
        assert not page.locator('.li-business-rules-document > .li-evidence').evaluate('(el) => el.open')
        page.screenshot(path=str(output / 'application-flows-readable.png'), full_page=True)
        page.get_by_text('Explore flow diagram (9 components)', exact=True).click()
        expect(page.locator('.ax-node')).to_have_count(9)
        state['saved'] = False
        page.reload()
        expect(page.get_by_role('heading', name='What starts it', exact=True)).to_be_visible()
        assert writes == [{'types': ['application_flows']}]
        state['fail'] = True
        page.reload()
        expect(page.get_by_role('alert')).to_contain_text('could not be loaded')
        expect(page.get_by_text('A customer sends a claim for validation.', exact=True)).to_be_visible()
        state['fail'] = False
        state['saved'] = True
        page.get_by_role('button', name='Retry explanation').click()
        expect(page.get_by_role('heading', name='What starts it', exact=True)).to_be_visible()
        assert not errors, errors
        browser.close()
    print('PASS: local worker rendering, search, selection, focus, filters, direction, exports, mobile, readable flows, lazy diagrams, collapsed evidence, authoring, fallback and retry.')


if __name__ == '__main__':
    main()
