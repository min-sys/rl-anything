---
name: version
effort: low
description: |
  Display the installed rl-anything version, commit hash, scope, and update timestamp.
  Trigger: version, バージョン, info, 情報, status, ステータス
---

# /rl-anything:version — バージョン確認

インストール済み rl-anything のバージョンとコミットハッシュを表示する。

## Usage

```
/rl-anything:version
```

## 実行手順

### Step 1: plugin.json を読み取り

```bash
cat <PLUGIN_DIR>/.claude-plugin/plugin.json
```

### Step 2: installed_plugins.json から詳細を取得

```bash
python3 -c "
import json
from pathlib import Path

f = Path.home() / '.claude/plugins/installed_plugins.json'
if f.exists():
    d = json.load(open(f))
    for k, v in d.get('plugins', {}).items():
        if 'rl-anything' in k:
            p = v[0]
            print(f\"Key: {k}\")
            print(f\"Version: {p.get('version', '?')}\")
            print(f\"Commit: {p.get('gitCommitSha', '?')[:12]}\")
            print(f\"Scope: {p.get('scope', '?')}\")
            print(f\"Updated: {p.get('lastUpdated', '?')}\")
            print(f\"Path: {p.get('installPath', '?')}\")
"
```

結果をユーザーに表示する（MUST）。

## allowed-tools

Bash, Read

## Tags

version, info, status
