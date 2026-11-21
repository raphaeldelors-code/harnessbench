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
# keep these versions in sync with the pinned registry in bench/harnesses.py
# claude-code ships a native binary through its install script -> no --ignore-scripts here
npm i -g @anthropic-ai/claude-code@2.1.326
npm i -g --ignore-scripts @earendil-works/pi-coding-agent@1.5.2
npm i -g @deepseek-ai/dsh@0.2.2-rc.3
# other registry harnesses (opencode, codex, qwen-code, kimi-code, grok,
# openclaw) install the same way, pinned to their registry versions
echo HB_SETUP_DONE
