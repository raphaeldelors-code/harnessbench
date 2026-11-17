#!/bin/bash
# setup_hb_configs.sh — per-harness config homes for harnessbench
set -euo pipefail
HB=/home/rapha/hb
H=$HB/homes
mkdir -p "$H/pi/.pi/agent" "$H/dsh/.dsh/profiles/headless" "$H/claude" "$H/opencode/.config/opencode"
chmod -R u+w "$H"

# --- pi: custom OpenAI-completions provider "rig"
cat > "$H/pi/.pi/agent/models.json" <<EOF
{
  "providers": {
    "rig": {
      "baseUrl": "http://127.0.0.1:8080/v1",
      "api": "openai-completions",
      "apiKey": "***",
      "models": [
        { "id": "strata_iq3s", "contextWindow": 131072, "maxTokens": 8192 }
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
        baseURL: http://127.0.0.1:8080/v1
        models:
          - id: strata_iq3s
- id: agent-default-model
  config:
    provider: rig
    model: strata_iq3s
EOF

# --- claude-code: skip onboarding; llama-swap speaks /v1/messages natively
python3 - <<'EOF'
import json, os
p = "/home/rapha/hb/homes/claude/.claude.json"
d = {}
if os.path.exists(p): d = json.load(open(p))
d["hasCompletedOnboarding"] = True
d["theme"] = "dark"
d.setdefault("autoUpdates", False)
json.dump(d, open(p, "w"), indent=1)
EOF

# --- opencode: reuse the rig opencode.json (llamaswap provider, V2 schema)
cp /home/rapha/opencode/config/opencode.json "$H/opencode/.config/opencode/opencode.json"

# --- opencode V2 binary out of the container image into the portable runtime
if [ ! -x "$HB/bin/opencode" ]; then
  mkdir -p "$HB/bin"
  cid=$(docker create opencode-rig:latest)
  path=$(docker exec "$cid" true 2>/dev/null; docker inspect --format '{{.Config.Entrypoint}}' "$cid" | awk '{print $1}')
  [ -n "$path" ] || path=$(docker run --rm --entrypoint sh opencode-rig:latest -c 'command -v opencode')
  docker cp "$cid:$path" "$HB/bin/opencode"
  docker rm "$cid" >/dev/null
  chmod +x "$HB/bin/opencode"
  file "$HB/bin/opencode" | head -1
fi
ln -sf "$HB/bin/opencode" "$HB/npm/bin/opencode" 2>/dev/null || true
echo CONFIGS_DONE
