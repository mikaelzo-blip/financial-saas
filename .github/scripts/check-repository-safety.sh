#!/usr/bin/env bash
set -euo pipefail

failure=0

tracked_env_files=()
sensitive_files=()
while IFS= read -r tracked_path; do
  if [[ "$tracked_path" =~ (^|/)\.env($|\.) ]] && [[ ! "$tracked_path" =~ (^|/)\.env\.example$ ]]; then
    tracked_env_files+=("$tracked_path")
  fi
  if [[ "$tracked_path" =~ (\.pem|\.key|\.p12|\.pfx|id_rsa|credentials\.json|secrets?\.(json|ya?ml))$ ]]; then
    sensitive_files+=("$tracked_path")
  fi
done < <(git ls-files)

if ((${#tracked_env_files[@]})); then
  echo "::error::Tracked environment files are forbidden:"
  printf '  %s\n' "${tracked_env_files[@]}"
  failure=1
fi

if ((${#sensitive_files[@]})); then
  echo "::error::Tracked credential or private-key files are forbidden:"
  printf '  %s\n' "${sensitive_files[@]}"
  failure=1
fi

secret_patterns=(
  '-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'
  'AKIA[0-9A-Z]{16}'
  'ASIA[0-9A-Z]{16}'
  'gh[pousr]_[A-Za-z0-9_]{36,255}'
  'glpat-[A-Za-z0-9_-]{20,}'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
  'sk_live_[A-Za-z0-9]{16,}'
  'AIza[0-9A-Za-z_-]{35}'
)
for pattern in "${secret_patterns[@]}"; do
  if git grep -IEn -- "$pattern" -- . ':(exclude).github/scripts/check-repository-safety.sh'; then
    echo "::error::A tracked file matches an obvious secret signature."
    failure=1
  fi
done

for ignored_path in .env backend/.env frontend/.env private-key.pem; do
  if ! git check-ignore -q "$ignored_path"; then
    echo "::error::$ignored_path is not protected by repository ignore rules."
    failure=1
  fi
done

if ((failure)); then
  exit 1
fi

echo "Repository safety checks passed: no tracked environment files, credential files, private keys, or obvious live-token signatures."
