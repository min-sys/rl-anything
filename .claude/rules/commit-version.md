# コミット時のバージョン管理（PJ固有）
bump 時は `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` plugins[0].version + CHANGELOG.md を同期更新する。main マージ後に `claude plugin tag --push` で `rl-anything--v<version>` タグを作成。
