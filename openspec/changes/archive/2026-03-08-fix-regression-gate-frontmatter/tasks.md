Closes: #20

## 1. 実装

- [x] 1.1 `run()` 内で `self.original_content` を設定し、`_regression_gate()` で `self.original_content` を参照して frontmatter 保持チェックを実装
- [x] 1.2 `optimize()` 内の `_regression_gate()` 呼び出しはシグネチャ変更不要（インスタンス変数参照）
- [x] 1.3 `_format_gate_reason()` に `frontmatter_lost` → 日本語メッセージのマッピング追加

## 2. Spec 反映

- [x] 2.1 `openspec/specs/regression-gate/spec.md` に frontmatter 保持シナリオを追加

## 3. テスト

- [x] 3.1 frontmatter 付き → 保持の合格テスト
- [x] 3.2 frontmatter 付き → 消失の不合格テスト（reason = `frontmatter_lost`）
- [x] 3.3 frontmatter なし → チェックスキップのテスト
- [x] 3.4 既存テストが pass することを確認
- [x] 3.5 `_format_gate_reason("frontmatter_lost")` のテスト
