import getpass
import json
import secrets
import sys

def main():
    print("=== Financial SaaS / Meta WhatsApp Local Configuration ===")
    print("Enter the requested Meta credentials. Secret values will not be echoed.")
    print()

    phone_id = input("Meta Phone Number ID: ").strip()
    if not phone_id:
        print("Error: Meta Phone Number ID cannot be empty.", file=sys.stderr)
        sys.exit(1)

    if phone_id.startswith("+"):
        print(
            "Error: Meta Phone Number ID must be a numeric ID from Meta App Dashboard, "
            "not an E.164 phone number (e.g. +62...).",
            file=sys.stderr,
        )
        sys.exit(1)

    if not phone_id.isdigit():
        print(
            "Error: Meta Phone Number ID must contain only digits (numeric ID).",
            file=sys.stderr,
        )
        sys.exit(1)

    api_token = getpass.getpass("Meta Access Token: ").strip()
    if not api_token:
        print("Error: Meta Access Token cannot be empty.", file=sys.stderr)
        sys.exit(1)

    app_secret = getpass.getpass("Meta App Secret: ").strip()
    if not app_secret:
        print("Error: Meta App Secret cannot be empty.", file=sys.stderr)
        sys.exit(1)

    adapter_token = secrets.token_urlsafe(32)
    tenant_token = secrets.token_urlsafe(32)
    org_id = "9670673b-c0fd-4ebe-87e4-a646358084ea"
    tenant_tokens_json = json.dumps({org_id: tenant_token})

    # Read existing .env
    env_path = ".env"
    existing_lines = []
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()
    except FileNotFoundError:
        pass

    keys_to_update = {
        "WHATSAPP_PROVIDER": "meta",
        "WHATSAPP_PHONE_NUMBER_ID": phone_id,
        "WHATSAPP_API_TOKEN": api_token,
        "WHATSAPP_WEBHOOK_APP_SECRET": app_secret,
        "WHATSAPP_ADAPTER_TOKEN": adapter_token,
        "WHATSAPP_TENANT_TOKENS": tenant_tokens_json,
    }

    new_lines = []
    handled_keys = set()

    for line in existing_lines:
        trimmed = line.strip()
        if trimmed and not trimmed.startswith("#") and "=" in trimmed:
            k = trimmed.split("=", 1)[0].strip()
            if k in keys_to_update:
                new_lines.append(f"{k}={keys_to_update[k]}\n")
                handled_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in keys_to_update.items():
        if k not in handled_keys:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{k}={v}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print()
    print("SUCCESS: backend/.env updated safely with local-only Meta configuration.")

if __name__ == "__main__":
    main()
