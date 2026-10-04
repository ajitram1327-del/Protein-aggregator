import requests

response = requests.get("https://openrouter.ai/api/v1/models")
if response.status_code == 200:
    models = response.json().get("data", [])
    free_models = [m["id"] for m in models if m["id"].endswith(":free")]
    print("Free models available:")
    for m in free_models:
        print(f" - {m}")
else:
    print("Failed to fetch models")
