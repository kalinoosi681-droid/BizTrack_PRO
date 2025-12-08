import requests
import json
from bs4 import BeautifulSoup

session = requests.Session()

# First, check what users exist and try logging in
print("Attempting to login with existing test user...")
login_response = session.post('http://localhost:5000/login', data={
    'email': 'test@example.com',
    'password': 'password123'
}, allow_redirects=True)

# Check if login was successful
if 'dashboard' in login_response.url or 'dashboard' in login_response.text:
    print("✅ Login successful!")
else:
    print("❌ Login failed, trying to register new user...")
    # Try registration
    reg_response = session.post('http://localhost:5000/register', data={
        'email': 'apitest@example.com',
        'password': 'testpass123',
        'confirm_password': 'testpass123'
    }, allow_redirects=True)
    
    if 'dashboard' in reg_response.url or 'dashboard' in reg_response.text:
        print("✅ Registration and auto-login successful!")
    else:
        print("❌ Registration failed")
        print(f"URL: {reg_response.url}")

# Get dashboard to extract CSRF
print("Getting CSRF token...")
response = session.get('http://localhost:5000/dashboard')

if response.status_code != 200:
    print(f"❌ Could not get dashboard (status {response.status_code})")
    print(f"Redirected to: {response.url}")
else:
    soup = BeautifulSoup(response.text, 'html.parser')
    csrf_input = soup.find('input', {'name': 'csrf_token'})
    csrf_token = csrf_input.get('value') if csrf_input else ''
    
    if csrf_token:
        print(f"✅ CSRF token found: {csrf_token[:20]}...")
    else:
        print("❌ No CSRF token found in dashboard")
    
    # Check cookies
    print(f"\n✅ Session cookies: {len(session.cookies)} cookies")
    for cookie in session.cookies:
        print(f"   - {cookie.name}")
    
    # Test API with proper headers
    headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf_token
    }
    
    print("\nTesting AI Chat API...")
    response = session.post(
        'http://localhost:5000/api/ai/chat',
        json={'query': 'List my products', 'stream': False},
        headers=headers,
        timeout=120,
        allow_redirects=False
    )
    
    print(f'Status: {response.status_code}')
    print(f'Content-Type: {response.headers.get("content-type")}')
    
    if response.status_code == 302:
        print(f'❌ Redirected to: {response.headers.get("Location")}')
    elif response.status_code == 200:
        print(f'Response length: {len(response.text)}')
        
        # Try to parse as JSON
        try:
            data = response.json()
            print(f'✅ Valid JSON response!')
            print(json.dumps(data, indent=2)[:1000])
        except:
            print(f'❌ Not valid JSON, first 500 chars:')
            print(response.text[:500])
    else:
        print(f'❌ Unexpected status code')
        print(response.text[:500])

