"""
Quick smoke test for the /v1/extract endpoint (no audio needed).
Run: python test_extract.py
"""
import httpx, json

BASE = "http://localhost:8100"

# --- Faypass: recherche de trajet ---
faypass_schema = {
    "context": "Application de transport en commun au Sénégal",
    "fields": [
        {"name": "origin_city",      "type": "string",  "description": "Ville de départ",         "required": True},
        {"name": "destination_city", "type": "string",  "description": "Ville d'arrivée",          "required": True},
        {"name": "date",             "type": "date",    "description": "Date du voyage",            "required": False},
        {"name": "passenger_count",  "type": "integer", "description": "Nombre de passagers",       "required": False},
        {"name": "service_type",     "type": "enum",    "description": "Type de véhicule",          "required": False,
         "enum_values": ["bus", "minibus", "sept-place"]},
    ],
    "hints": ["Villes: Dakar, Thiès, Ziguinchor, Saint-Louis, Kaolack, Touba, Mbour, Tambacounda"],
}

# --- E-commerce: commande vocale ---
ecommerce_schema = {
    "context": "E-commerce platform, customer placing an order by voice",
    "fields": [
        {"name": "product",   "type": "string",  "description": "Product name or description", "required": True},
        {"name": "quantity",  "type": "integer", "description": "Quantity",                    "required": False},
        {"name": "color",     "type": "string",  "description": "Color preference",            "required": False},
        {"name": "size",      "type": "string",  "description": "Size (S/M/L/XL)",             "required": False},
    ],
}

tests = [
    ("Faypass FR", faypass_schema, "Je veux aller à Ziguinchor depuis Dakar demain matin pour deux personnes", "2026-05-04"),
    ("Faypass WO", faypass_schema, "Dakar Thiès yoon bi tey", "2026-05-04"),
    ("E-commerce", ecommerce_schema, "I'd like to order two blue t-shirts in size large", None),
]

for name, schema, text, today in tests:
    print(f"\n{'='*50}\n[{name}] Text: {text!r}")
    payload = {"text": text, "schema": schema}
    if today:
        payload["today"] = today
    r = httpx.post(f"{BASE}/v1/extract", json=payload, timeout=30)
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
