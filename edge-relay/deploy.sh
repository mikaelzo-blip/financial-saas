#!/usr/bin/env bash
set -euo pipefail

echo "=== Financial SaaS Edge Relay Deployment ==="

if ! command -v npx &> /dev/null; then
    echo "Error: npx is required to deploy Cloudflare Worker."
    exit 1
fi

echo "1. Validating Worker files..."
if [ ! -f "wrangler.toml" ] || [ ! -f "schema.sql" ]; then
    echo "Error: Run deploy script inside the edge-relay directory."
    exit 1
fi

echo "2. Checking Cloudflare authentication..."
npx wrangler whoami || {
    echo "Please log in to Cloudflare first via 'npx wrangler login'."
    exit 1
}

echo "3. Deploying Cloudflare Worker..."
npx wrangler deploy

echo "Deployment complete! Edge relay is active."
