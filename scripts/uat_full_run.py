import os
import sys
import json
import httpx

TOKEN = "Yk0z1vjhgBqMKNNm0sLxyua8rZXC0TBsJQImRwi39qo"
BASE_URL = "http://127.0.0.1:8000"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

results = []

def record(test_name, success, details=""):
    results.append({"test": test_name, "success": success, "details": details})
    mark = "PASS" if success else "FAIL"
    print(f"[{mark}] {test_name}: {details}")

client = httpx.Client(timeout=10.0)

# 1. Health check
try:
    r = client.get(f"{BASE_URL}/api/health")
    if r.status_code == 200 and r.json().get("status") == "ok":
        record("Health Check", True, f"Status: {r.json().get('status')}")
    else:
        record("Health Check", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Health Check", False, str(e))

# 2. Details & Power Status
try:
    r = client.get(f"{BASE_URL}/api/power", headers=HEADERS)
    if r.status_code == 200:
        record("Power Status", True, f"State: {r.json().get('state')}")
    else:
        record("Power Status", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Power Status", False, str(e))

# 3. Create Product in Catalog
created_product_id = None
try:
    payload = {
        "name": "Roihan AI Growth Engine",
        "category": "software",
        "description": "Platform AI untuk optimasi pertumbuhan organik dan manajemen prospek B2B.",
        "features": ["Autonomous Technical SEO", "Lead Scoring", "Marketing Automation"],
        "claims": ["Meningkatkan efisiensi pemasaran tanpa manipulasi angka"]
    }
    r = client.post(f"{BASE_URL}/api/products", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        created_product_id = r.json().get("id")
        record("Create Product", True, f"Product ID: {created_product_id}")
    else:
        record("Create Product", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Create Product", False, str(e))

# 4. Create Lead in CRM
created_lead_id = None
try:
    import time
    ts = int(time.time())
    payload = {
        "company": {"name": f"PT Mega Pratama {ts}", "industry": "Financial Services", "size_band": "medium"},
        "contact": {"name": "Dewi Sartika", "title": "VP of Marketing", "email": f"dewi_{ts}@megapratama.id", "phone": "08123456789"},
        "source": {"source_type": "public_website", "url": "https://megapratama.id"}
    }
    r = client.post(f"{BASE_URL}/api/marketing/leads", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        created_lead_id = r.json().get("id")
        score = r.json().get("score")
        record("Create CRM Lead", True, f"Lead ID: {created_lead_id}, Score: {score}")
    else:
        record("Create CRM Lead", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Create CRM Lead", False, str(e))

# 5. Create SEO Campaign
created_campaign_id = None
try:
    payload = {
        "name": "Q4 2026 B2B Organic Expansion",
        "website_url": "https://roihan.id",
        "primary_keywords": ["software house jakarta", "b2b saas indonesia"],
        "objective": "organic_traffic",
        "target_value": 1500,
        "api_budget_idr": 500000,
        "autonomy": "read_only"
    }
    r = client.post(f"{BASE_URL}/api/marketing/seo/campaigns", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        created_campaign_id = r.json().get("id")
        record("Create SEO Campaign", True, f"Campaign ID: {created_campaign_id}, Status: {r.json().get('status')}")
    else:
        record("Create SEO Campaign", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Create SEO Campaign", False, str(e))

# 6. Add Keyword to Campaign
if created_campaign_id:
    try:
        payload = {"keyword": "autonomous marketing agents", "intent": "commercial"}
        r = client.post(f"{BASE_URL}/api/marketing/seo/campaigns/{created_campaign_id}/keywords", headers=HEADERS, json=payload)
        if r.status_code in (200, 201):
            record("Add Campaign Keyword", True, "Added keyword 'autonomous marketing agents'")
        else:
            record("Add Campaign Keyword", False, f"HTTP {r.status_code}: {r.text}")
    except Exception as e:
        record("Add Campaign Keyword", False, str(e))

# 7. Run SEO Audit
try:
    payload = {
        "url": "https://roihan.id/pricing",
        "html": "<html><head><title>Harga Layanan - Roihan AI Office</title><meta name='description' content='Daftar paket dan harga langganan Roihan AI Office.'><link rel='canonical' href='https://roihan.id/pricing'></head><body><h1>Paket Langganan</h1></body></html>"
    }
    r = client.post(f"{BASE_URL}/api/marketing/seo/tasks/audit", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        record("Run Technical SEO Audit", True, f"Task ID: {r.json().get('task_id')}")
    else:
        record("Run Technical SEO Audit", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Run Technical SEO Audit", False, str(e))

# 8. Create Content Brief
try:
    payload = {
        "topic": "Strategi SEO Modern Berbasis AI Tanpa Halusinasi",
        "material": "Roihan AI Office menggunakan data nyata dan sandbox terisolasi.",
        "keyword": "seo ai"
    }
    r = client.post(f"{BASE_URL}/api/marketing/seo/tasks/brief", headers=HEADERS, json=payload)
    if r.status_code in (200, 201):
        record("Create Content Brief", True, f"Task ID: {r.json().get('task_id')}")
    else:
        record("Create Content Brief", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Create Content Brief", False, str(e))

# 9. List Marketing Tasks & Approvals
try:
    r = client.get(f"{BASE_URL}/api/tasks", headers=HEADERS)
    if r.status_code == 200:
        tasks = r.json()
        record("List Tasks Queue", True, f"Total tasks in system: {len(tasks)}")
    else:
        record("List Tasks Queue", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("List Tasks Queue", False, str(e))

# 10. Dashboard Telemetry & Stats
try:
    r = client.get(f"{BASE_URL}/api/dashboard", headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        record("Dashboard Telemetry", True, f"Marketing leads: {data.get('marketing', {}).get('leads_total')}, AI Calls: {data.get('ai', {}).get('calls_24h')}")
    else:
        record("Dashboard Telemetry", False, f"HTTP {r.status_code}: {r.text}")
except Exception as e:
    record("Dashboard Telemetry", False, str(e))

summary = {
    "total": len(results),
    "passed": sum(1 for r in results if r["success"]),
    "failed": sum(1 for r in results if not r["success"]),
    "results": results
}
print("\n" + "="*50)
print(f"UAT SUMMARY: {summary['passed']}/{summary['total']} PASSED")
print("="*50)
with open("data/uat_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
