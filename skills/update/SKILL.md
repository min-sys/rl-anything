---
name: update
effort: low
description: |
  Update the rl-anything plugin to the latest version. Runs install.sh and prompts
  for Claude Code restart.
  Trigger: update, 更新, アップデート, install, インストール
disable-model-invocation: true
---

# /rl-anything:update — プラグインの更新

rl-anything プラグインを最新版に更新する。Claude 内から実行可能。

## Usage

```
/rl-anything:update
```

## 実行手順

### Step 1: install.sh を実行

```bash
bash <PLUGIN_DIR>/install.sh
```

結果を表示する（MUST）。

### Step 2: 再起動を案内

「Claude Code を再起動してください」とユーザーに伝える（MUST）。

## allowed-tools

Bash

## Tags

update, install, plugin
