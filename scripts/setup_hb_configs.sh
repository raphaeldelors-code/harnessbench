#!/bin/bash
# setup_hb_configs.sh — seed per-harness config homes for harnessbench.
# Everything machine-specific comes from env vars; defaults match a local
# llama-swap on :8080. Idempotent.
set -euo pipefail
HB="${HB_RUNTIME_DIR:-$HOME/.harnessbench/runtime}"
BACKEND="${HB_BACKEND_URL:-http://127.0.0.1:8080}"
MODEL="${HB_MODEL:-strata_iq3s}"
H=$HB/homes
mkdir -p "$H/pi/.pi/agent" "$H/dsh/.dsh/profiles/headless" "$H/claude" "$H/opencode/.config/opencode"
chmod -R u+w "$H"

# --- pi: custom OpenAI-completions provider "rig"
cat > "$H/pi/.pi/agent/models.json" <<EOF
{
  "providers": {
    "rig": {
      "baseUrl": "$BACKEND/v1",
      "api": "openai-completions",
      "apiKey": "***",
      "models": [
        { "id": "$MODEL", "contextWindow": 131072, "maxTokens": 8192 }
      ]
    }
  }
}
EOF

# --- dsh: custom provider + default model in the headless profile patch
cat > "$H/dsh/.dsh/profiles/headless/cordis.patch.yml" <<EOF
- id: llm-pi-ai
  config:
    providers:
      rig:
        apiKeyEnv: OPENAI_API_KEY
        api: openai-completions
        baseURL: $BACKEND/v1
        models:
          - id: $MODEL
- id: agent-default-model
  config:
    provider: rig
    model: $MODEL
EOF

# --- claude-code: skip onboarding (llama-swap speaks /v1/messages natively)
python3 - "$H/claude/.claude.json" <<'EOF'
import json, os, sys
p = sys.argv[1]
d = json.load(open(p)) if os.path.exists(p) else {}
d["hasCompletedOnboarding"] = True
d["theme"] = "dark"
d.setdefault("autoUpdates", False)
json.dump(d, open(p, "w"), indent=1)
EOF

# --- opencode: llamaswap provider config (V2 schema)
cat > "$H/opencode/.config/opencode/opencode.json" <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "provider": {
    "llamaswap": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "llama-swap",
      "options": { "baseURL": "$BACKEND/v1", "apiKey": "***" },
      "models": { "$MODEL": { "limit": { "context": 131072, "output": 8192 } } }
    }
  }
}
EOF
echo CONFIGS_DONE
