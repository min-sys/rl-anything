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

## Note: Claude Code v2.1.81+ の自動更新

`claude plugin install` 経由でインストールした場合（ref-tracked install）、
CC v2.1.81+ ではロード時に自動で最新版が取得されるため、明示的な `/update` は不要。

`install.sh` 経由でインストールした場合は、引き続き以下の手順で更新する。

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
