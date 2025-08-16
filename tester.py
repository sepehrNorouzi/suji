import requests
import time

services = {
    "Frontend HTTP": "http://localhost:51504/healthz",
    "Backend HTTP": "http://localhost:51505/healthz",
    "Query HTTP": "http://localhost:51503/healthz",
    "Synchronizer HTTP": "http://localhost:51506/healthz",
    "SwaggerUI": "http://localhost:51507",
}

print("Waiting for services to start...")
time.sleep(5)

print("\nChecking OpenMatch services health...")
for name, url in services.items():
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200 or response.status_code == 404:  # 404 is ok for swagger
            print(f"✅ {name}: Reachable")
        else:
            print(f"⚠️ {name}: Status {response.status_code}")
    except Exception as e:
        print(f"❌ {name}: {str(e)[:50]}")

# Test Redis
import redis
try:
    r = redis.Redis(host='localhost', port=6380)
    r.ping()
    print("✅ Redis: Connected")
except:
    print("❌ Redis: Connection failed")
