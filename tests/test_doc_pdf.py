import os
import sys
import json

# Ensure project root is importable when running from tests/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from sdlc.config import ensure_generated_code_dir

client = app.test_client()

def main():
    # Clean previous outputs
    gen_dir = ensure_generated_code_dir()
    docs_dir = os.path.join(gen_dir, "docs")
    if os.path.isdir(docs_dir):
        for f in os.listdir(docs_dir):
            if f.endswith('.md') or f.endswith('.pdf'):
                try:
                    os.remove(os.path.join(docs_dir, f))
                except Exception:
                    pass

    payload = {
        "path": "docs/README.pdf",
        "plan": "### README\n**Audience:** Developers\n**Key Content:**\n- Overview\n- Installation\n",
        "fullDocument": ""
    }

    resp = client.post('/api/documentation/pdf', json=payload)
    print('POST status:', resp.status_code)
    try:
        print('POST json:', resp.get_json())
    except Exception:
        print('POST response text:', resp.data[:200])

    # Now try to GET the file
    get_resp = client.get('/api/documentation/pdf', query_string={'path': 'docs/README.pdf'})
    print('GET status:', get_resp.status_code)
    if get_resp.status_code == 200:
        # write to local file for inspection
        out_path = os.path.join('tests', 'out_README.pdf')
        with open(out_path, 'wb') as f:
            f.write(get_resp.data)
        print('Wrote PDF to', out_path)
    else:
        try:
            print('GET json:', get_resp.get_json())
        except Exception:
            print('GET response text:', get_resp.data[:200])

if __name__ == '__main__':
    main()
