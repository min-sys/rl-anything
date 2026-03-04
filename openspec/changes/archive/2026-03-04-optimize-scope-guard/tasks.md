## 1. Scope 判定ロジック

- [x] 1.1 optimize.py に `detect_scope(target_path: Path) -> str` 関数を追加。`~/.claude/skills/` 配下なら `"global"`、それ以外は `"project"` を返す
- [x] 1.2 GeneticOptimizer の `__init__` で scope を判定し `self.scope` に保持する
- [x] 1.3 実行開始時に scope が `global` の場合「汎用評価モードで最適化します」メッセージを表示する

## 2. 汎用評価モード（cwd 切替）

- [x] 2.1 `claude -p` を呼び出す `subprocess.run` に `cwd` パラメータを追加。scope が `global` の場合は `Path.home()` を設定する
- [x] 2.2 対象箇所: `mutate()`, `crossover()`, `_llm_evaluate()`, `_execution_evaluate()`, `pairwise_compare()` の5メソッド
- [x] 2.3 ワークフローヒントの読み込みが `cwd` 変更後も正常に動作することを確認する

## 3. SKILL.md 更新

- [x] 3.1 SKILL.md のターゲット選択セクションに scope ラベル（`[global]` / `[project]`）の表示指示を追加する

## 4. テスト

- [x] 4.1 `detect_scope()` のユニットテスト（global / project / plugin パス）
- [x] 4.2 `cwd` パラメータが scope に応じて正しく設定されることを確認するテスト
- [x] 4.3 既存テストが全てパスすることを確認（73 passed）
