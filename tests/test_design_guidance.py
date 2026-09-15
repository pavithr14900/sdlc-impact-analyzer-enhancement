import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from sdlc.rag import knowledge_base as kb
from sdlc.rag.design_url import GuidanceParser, fetch_guidance


class DesignGuidanceTests(unittest.TestCase):
    def test_extracts_main_content_and_preserves_guidance_links(self):
        parser = GuidanceParser()
        parser.feed('<header>Cookie notice</header><nav><a href="/styles/colour">Colour</a></nav>'
                    '<main><h1>Typography</h1><p>Use 19px body text.</p><script>noise</script></main><footer>Copyright</footer>')
        self.assertIn('Use 19px body text.', parser.text)
        self.assertNotIn('Cookie', parser.text)
        self.assertNotIn('noise', parser.text)
        self.assertNotIn('Copyright', parser.text)
        self.assertIn('/styles/colour', parser.links)

    def test_follows_relevant_same_site_links(self):
        class Response:
            headers = {'Content-Type': 'text/html'}
            encoding = 'utf-8'

            def __init__(self, url):
                self.url = url

            def __enter__(self): return self
            def __exit__(self, *args): pass
            def raise_for_status(self): pass

            def iter_content(self, size):
                yield ('<main><p>' + 'Useful design guidance. ' * 8 + '</p>'
                       '<a href="/styles/colour">Colour</a><a href="https://other.test/spacing">External</a>'
                       '<a href="/privacy">Privacy</a></main>').encode()

        with patch('requests.Session') as session:
            client = session.return_value.__enter__.return_value
            client.get.side_effect = lambda url, **kwargs: Response(url)
            documents, warnings = fetch_guidance('https://example.test/styles/')
        self.assertEqual([source for source, _ in documents], ['https://example.test/styles/', 'https://example.test/styles/colour'])
        self.assertEqual(warnings, [])

    def test_replacing_import_removes_previous_guidance_and_summary_cites_sources(self):
        with patch.object(kb, '_save'), patch.object(kb, '_cache', []):
            kb.replace_category('engineering', [('coding', 'Keep this guidance')])
            kb.replace_category('design', [('old', 'Old purple theme')])
            kb.replace_category('design', [('https://example.test/colour', 'Use green buttons'), ('https://example.test/typeface', 'Use a sans-serif typeface')])
            summary = kb.category_summary('design')
            self.assertNotIn('purple', summary)
            self.assertIn('https://example.test/colour', summary)
            self.assertIn('sans-serif', summary)
            self.assertIn('Keep this guidance', kb.category_summary('engineering'))

    def test_prompt_schema_formats_and_includes_design_controls(self):
        # Inspect the actual prompt without initializing the cloud SDK.
        module = ast.parse((Path(__file__).resolve().parents[1] / 'sdlc/agents/prototype_agent.py').read_text())
        prompt = next(ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PROMPT' for t in node.targets))
        result = prompt.format(requirement='Example', analysis='', user_stories='', rules='', design_standards='Use green buttons')
        self.assertIn('"theme"', result)
        self.assertIn('"layout"', result)
        self.assertIn('Use green buttons', result)


if __name__ == '__main__':
    unittest.main()
