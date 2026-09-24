"""Browser checks for readable rules and evidence disclosure using offline API fixtures."""
import json
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect


def main():
    evidence = {"id": "E1", "repository": "claims", "file": "rules.py", "lineStart": 12, "snippet": "if amount <= 0: reject()"}
    analysis = {"analysisId": "rules-test", "name": "Claims", "status": "COMPLETED", "repositories": [],
                "createdAt": "2026-09-23", "updatedAt": "2026-09-23", "overview": {},
                "businessRules": [{"id": "BR1", "title": "Positive claim amount", "description": "The amount must be greater than zero.", "confidence": "HIGH", "evidence": [evidence]}],
                "narratives": {"businessRules": "## Claim validation\nClaims must have a positive amount."}}
    document = {"type": "business_rules", "title": "Business Rules", "evidence": [evidence], "content": "## Claim amounts\n\n**When it applies:** A customer submits a claim.\n\n**What the application does:** Rejects amounts of zero or less [E1].\n\n## Source Evidence\n\n- [E1] claims: rules.py:12\n\n## Coverage Limitations\n\nRuntime behavior needs confirmation."}
    mode = {"saved": True, "fail": False}
    generated = []
    errors = []

    def respond(route):
        path = urlsplit(route.request.url).path
        status, data = 200, {"success": True}
        if path.endswith('/documentation'):
            if route.request.method == 'POST':
                generated.append(route.request.post_data_json)
            if mode['fail']:
                status, data = 500, {"success": False, "error": "Fixture failure"}
            else:
                data['documents'] = [document] if mode['saved'] or route.request.method == 'POST' else []
        elif path.endswith('/recent'):
            data['analyses'] = [analysis]
        elif '/legacy-intelligence/rules-test' in path:
            data['analysis'] = analysis
        elif path.endswith('/health'):
            data = {"status": "UP"}
        elif path.endswith('/models'):
            data['models'] = []
        route.fulfill(status=status, content_type='application/json', body=json.dumps(data))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='msedge', headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/api/**', respond)
        page.goto('http://127.0.0.1:5178/#/legacy-intelligence/rules-test')
        page.get_by_role('button', name='Find Business Rules', exact=True).click()
        expect(page.get_by_text('When it applies:', exact=True)).to_be_visible()
        assert not generated, 'Saved documentation must be reused'
        sources = page.locator('.li-document-sources')
        snippets = page.locator('.li-business-rules-document > .li-evidence')
        assert not sources.evaluate('(el) => el.open')
        assert not snippets.evaluate('(el) => el.open')
        expect(page.get_by_text('Runtime behavior needs confirmation.', exact=True)).to_be_visible()
        sources.locator('summary').click()
        expect(sources.get_by_text('[E1] claims: rules.py:12', exact=True)).to_be_visible()
        sources.locator('summary').click()
        snippets.locator('summary').focus()
        page.keyboard.press('Enter')
        expect(snippets.locator('pre')).to_be_visible()
        snippets.locator('summary').click()
        expect(snippets.locator('pre')).not_to_be_visible()
        assert not page.locator('.li-rule-catalogue').evaluate('(el) => el.open')
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        mode['saved'] = False
        page.reload()
        expect(page.get_by_text('When it applies:', exact=True)).to_be_visible()
        assert generated == [{"types": ["business_rules"]}]
        mode['fail'] = True
        page.reload()
        expect(page.get_by_role('alert')).to_contain_text('could not be loaded')
        expect(page.get_by_text('Claims must have a positive amount.', exact=True)).to_be_visible()
        mode['fail'] = False
        mode['saved'] = True
        page.get_by_role('button', name='Retry explanation').click()
        expect(page.get_by_text('When it applies:', exact=True)).to_be_visible()
        assert not errors, errors
        browser.close()
    print('PASS: saved prose, generation, collapsed evidence, keyboard expansion, mobile layout, failure fallback and retry.')


if __name__ == '__main__':
    main()
