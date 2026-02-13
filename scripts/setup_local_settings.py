#!/usr/bin/env python3
"""
Generate local.settings.json from parent .env for local development.
Run from project root: python scripts/setup_local_settings.py
"""
import json
import os

def load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def main():
    env = load_env()
    settings = {
        "IsEncrypted": False,
        "Values": {
            "AzureWebJobsStorage": "UseDevelopmentStorage=true",
            "FUNCTIONS_WORKER_RUNTIME": "python",
            "BOOKEO_API_KEY": env.get("BOOKEO_API_KEY", ""),
            "BOOKEO_SECRET_KEY": env.get("BOOKEO_SECRET_KEY", ""),
            "AZURE_SQL_SERVER": env.get("AZURE_SQL_SERVER", ""),
            "AZURE_SQL_DATABASE": env.get("AZURE_SQL_DATABASE", ""),
            "AZURE_SQL_USER": env.get("AZURE_SQL_USER", ""),
            "AZURE_SQL_PASSWORD": env.get("AZURE_SQL_PASSWORD", ""),
            "BOOKEO_WEBHOOK_URL": env.get("BOOKEO_WEBHOOK_URL", ""),
        },
    }
    out_path = os.path.join(os.path.dirname(__file__), "..", "local.settings.json")
    with open(out_path, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"Created {out_path} from .env")

if __name__ == "__main__":
    main()
