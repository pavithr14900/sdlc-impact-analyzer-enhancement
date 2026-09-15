import os, json, requests
url = 'http://localhost:5000/api/analyze/step'
payload = {
    'requirement': 'Build a customer management application to track customers, email, and status.',
    'stage': 'prototype',
    'context': {'requirement_analysis': 'analysis text', 'user_stories': 'user stories text'}
}
resp = requests.post(url, json=payload)
print(resp.status_code)
print(resp.text)
