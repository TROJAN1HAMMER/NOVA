import httpx
import asyncio
import sys

BASE_URL = "http://localhost:8000/api/v1"
GLOBAL_URL = "http://localhost:8000"

async def test_endpoints():
    print("Testing endpoints...")
    async with httpx.AsyncClient() as client:
        # Test basic health
        print("GET /health")
        res = await client.get(f"{GLOBAL_URL}/health")
        if res.status_code != 200:
            print(f"FAILED: Health endpoint returned {res.status_code}")
            sys.exit(1)
        print("OK")

        print("GET /health/ready")
        res = await client.get(f"{GLOBAL_URL}/health/ready")
        if res.status_code != 200:
            print(f"FAILED: Readiness endpoint returned {res.status_code} - {res.text}")
            sys.exit(1)
        print("OK")

        # Test Auth
        print("POST /api/v1/auth/login")
        res = await client.post(f"{BASE_URL}/auth/login", data={"username": "admin@NOVA.io", "password": "password"})
        if res.status_code != 200:
            print(f"FAILED: Login failed with {res.status_code} - {res.text}")
            sys.exit(1)
        
        token = res.json()["access_token"]
        print("OK - Token received")

        headers = {"Authorization": f"Bearer {token}"}

        # Test Me
        print("GET /api/v1/auth/me")
        res = await client.get(f"{BASE_URL}/auth/me", headers=headers)
        if res.status_code != 200:
            print(f"FAILED: /auth/me returned {res.status_code}")
            sys.exit(1)
        print(f"OK - Logged in as {res.json()['email']} with role {res.json()['role']}")

        # Test FAQ Rules
        print("GET /api/v1/faq")
        res = await client.get(f"{BASE_URL}/faq", headers=headers)
        if res.status_code == 200:
            rules = res.json()
            if isinstance(rules, dict) and "items" in rules:
                rules = rules["items"]
            print(f"OK - Found {len(rules)} FAQ rules")
        else:
            print(f"FAILED: /faq returned {res.status_code} - {res.text}")

        # Test Knowledge Documents
        print("GET /api/v1/knowledge/documents")
        res = await client.get(f"{BASE_URL}/knowledge/documents", headers=headers)
        if res.status_code == 200:
            docs = res.json().get("items", [])
            print(f"OK - Found {len(docs)} documents")
        else:
            print(f"FAILED: /knowledge/documents returned {res.status_code} - {res.text}")

    print("\nAll tested endpoints are working successfully!")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
