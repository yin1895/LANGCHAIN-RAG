import time
import uuid
import urllib.request
import traceback
from jose import jwt

SECRET_KEY = 'your-secret-key'
ALGO = 'HS256'

payload = {
    'sub': 'yin',
    'is_admin': True,
    'iat': int(time.time()),
    'jti': str(uuid.uuid4()),
    'exp': int(time.time()) + 86400
}

token = jwt.encode(payload, SECRET_KEY, algorithm=ALGO)
print('generated token jti=', payload['jti'])

url = 'http://localhost:8000/api/admin/users'
req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        b = r.read().decode('utf-8')
        print('status', r.status)
        print('body:', b)
except Exception as e:
    print('request failed:', e)
    traceback.print_exc()
