#!/bin/bash
# setup_hb.sh — portable harness runtime for harnessbench at /opt/hb
# node22 tarball + npm-global harnesses; mountable read-only into ANY container.
set -euo pipefail
HB=/opt/hb
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
npm i -g --ignore-scripts @anthropic-ai/claude-code
npm i -g --ignore-scripts @earendil-works/pi-coding-agent
npm i -g @deepseek-ai/dsh
echo "=== versions ==="
claude --version 2>&1 | head -1
pi --version 2>&1 | head -1
dsh --version 2>&1 | head -1
echo HB_SETUP_DONE
