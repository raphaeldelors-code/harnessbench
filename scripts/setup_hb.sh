#!/bin/bash
# setup_hb.sh — portable harness runtime for harnessbench.
# node22 tarball + npm-global harness CLIs; the whole dir is mountable
# read-only into ANY eval container (bench.config.RUNTIME_DIR -> /opt/hb).
set -euo pipefail
HB="${HB_RUNTIME_DIR:-$HOME/.harnessbench/runtime}"
mkdir -p "$HB"
cd "$HB"

if [ ! -x "$HB/node/bin/node" ]; then
  curl -fsSLo node.tar.xz https://nodejs.org/dist/v22.21.1/node-v22.21.1-linux-x64.tar.xz
  mkdir -p node
  tar -xJf node.tar.xz -C node --strip-components=1
  rm -f node.tar.xz
fi
export PATH="$HB/node/bin:$PATH"
echo "node $(node --version) npm $(npm --version)"

HB_NPM=$HB/npm
export NPM_CONFIG_PREFIX=$HB_NPM
mkdir -p $HB_NPM
export PATH="$HB_NPM/bin:$PATH"
npm config set prefix $HB_NPM
# keep versions in sync with the pinned registry in bench/harnesses.py
npm i -g --ignore-scripts @anthropic-ai/claude-code
npm i -g --ignore-scripts @earendil-works/pi-coding-agent
npm i -g @deepseek-ai/dsh
# other registry harnesses (opencode, codex, qwen-code, kimi-code, grok,
# openclaw) install the same way, pinned to their registry versions
echo HB_SETUP_DONE
