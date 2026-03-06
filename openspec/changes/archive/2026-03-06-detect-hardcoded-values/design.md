## Context

audit の `collect_issues()` は行数超過・陳腐化参照・肥大化警告・重複を検出するが、skill/rule ファイル内の環境固有ハードコード値は検出対象外。実際に channel-routing スキルで `slack_app_id` のリテラル値が原因で bot 無反応事故が発生した（Issue #9）。

既存パターン:
- `scripts/lib/` に共通モジュールを配置（`agent_classifier.py`, `skill_triggers.py`, `line_limit.py` 等）
- `audit.py` の `collect_issues()` で各検出関数を呼び出し、統一フォーマットの issue リストを返す
- remediation パイプライン（`remediation.py`）が `collect_issues()` の結果を分類・修正提案

## Goals / Non-Goals

**Goals:**
- skill/rule ファイル内の環境固有ハードコード値を正規表現ベースで検出する
- false positive を実用的なレベルに抑える（許容パターンのホワイトリスト）
- `collect_issues()` および audit レポートに統合する

**Non-Goals:**
- LLM を使った高精度なセマンティック判定（コストが高すぎる）
- コード内（`.py` 等）のハードコード値検出（対象は skill/rule の `.md` ファイルのみ）
- 自動修正（検出 + 警告まで。修正は remediation の既存フローに委ねる）

## Decisions

### D1. 検出ロジックを `scripts/lib/hardcoded_detector.py` に配置

**理由**: 既存パターンに準拠（`scripts/lib/` に共通モジュール配置）。audit と discover の両方から利用可能にする。

**代替案**: audit.py に直接実装 → discover からの再利用が困難なため却下。

### D2. 正規表現 + ヒューリスティクスによる検出

検出パターン（優先度順）:
1. **AWS ARN**: `arn:aws:[a-z0-9-]+:[a-z0-9-]*:\d{12}:.*`
2. **Slack App/Bot/Channel ID**: `[ABCUW][A-Z0-9]{10,}` （コマンド引数やコード例内）
3. **URL（localhost 以外）**: `https?://[a-z0-9-]+\.(slack|amazonaws|github)\.com/\S+` に具体的なパス/ID を含むもの
4. **API キー風文字列**: `(xoxb-|xapp-|sk-|AKIA)[A-Za-z0-9-]+`
5. **数値 ID（12桁以上）**: コマンド例内の長い数値リテラル

**false positive 回避**:
- プレースホルダパターン (`${VAR}`, `<PLACEHOLDER>`, `YOUR_*`) は除外
- ダミー値パターン (`A0123456789`, `xxx`, `example.com`) は除外
- frontmatter / コメント行内のサンプル注記は除外
- コードブロック内で変数代入の右辺（`=` の後）は検出対象、コマンドテンプレート内は文脈判定
- バージョン番号（セマンティックバージョニング形式）は除外
- 算術式（演算子を含む数値式）は除外

**検討した代替アプローチ**:

| アプローチ | 概要 | 採用しない理由 |
|------------|------|----------------|
| エントロピー分析（TruffleHog 方式） | 文字列のシャノンエントロピーを計算し、高エントロピー = シークレット候補として検出 | Markdown ファイル内の自然言語テキストとの混在でエントロピー閾値の調整が困難。API キーは既にプレフィックスで検出可能であり、コスト対効果が低い |
| tree-sitter AST 解析 | Markdown を AST にパースし、構文ノード単位で値を分析 | Markdown の AST はコードブロック内の言語までは解析しない。パターンマッチが主要な検出手段である以上、AST の付加価値が限定的。依存ライブラリ追加のコストに見合わない |

### D3. collect_issues() に `hardcoded_value` タイプで統合

**理由**: remediation パイプラインが既に `collect_issues()` の出力を処理するため、新タイプを追加するだけで自動連携する。

issue フォーマット:
```python
{
    "type": "hardcoded_value",
    "file": "path/to/SKILL.md",
    "detail": {
        "line": 42,
        "matched": "A04XXXXXXXX",
        "pattern_type": "slack_id",
        "context": "surrounding line text",
        "confidence_score": 0.65,
    },
    "source": "detect_hardcoded_values",
}
```

### D4. remediation 分類は `proposable`

ハードコード値の自動修正は危険（何に置換すべきか不明）なため、`proposable`（修正提案）として分類。ユーザーに「このリテラルをプレースホルダに置換すべきか」を確認する。

### D5. インライン抑制コメント `<!-- rl-allow: hardcoded -->`

意図的にハードコード値を記載するケース（ドキュメントの具体例、固定の定数等）に対応するため、行単位の抑制コメントを導入する。

**仕様**:
- `<!-- rl-allow: hardcoded -->` を含む行は検出対象から除外する
- 抑制はその行にのみ適用される（ブロック単位の抑制は導入しない）
- 既存の `rl-allow` 命名パターンに沿った設計

**実装方針**: `detect_hardcoded_values()` 内で行ごとの走査時に抑制コメントの存在をチェックし、該当行をスキップする。

### D6. confidence_score の定義

pattern_type ごとにデフォルトの confidence_score を割り当てる:

| pattern_type | confidence_score | 根拠 |
|-------------|-----------------|------|
| api_key | 0.85 | プレフィックスが明確で false positive が少ない |
| aws_arn | 0.75 | フォーマットが厳密だが、ドキュメント例も多い |
| slack_id | 0.65 | 形式が他の ID と重複する可能性がある |
| service_url | 0.55 | URL は正当なドキュメント参照の場合がある |
| numeric_id | 0.45 | 最も false positive リスクが高い |

impact_scope は全 pattern_type で `"file"` とする（影響範囲はファイル単位）。

### D7. パターン拡張インターフェース

`detect_hardcoded_values()` に `extra_patterns` / `extra_allowlist` パラメータを追加し、呼び出し元がプロジェクト固有のパターンを注入可能にする。

```python
def detect_hardcoded_values(
    file_path: str,
    extra_patterns: list[dict] | None = None,
    extra_allowlist: list[str] | None = None,
) -> list[dict]:
    """
    extra_patterns: [{"name": str, "regex": str, "confidence": float}]
    extra_allowlist: ["regex_pattern", ...]
    """
```

これにより audit 以外のコンテキスト（discover 等）からも拡張利用が可能になる。

## Risks / Trade-offs

- **[false positive]** → 許容パターンのホワイトリストで対応。初回リリース後にユーザーフィードバックで調整
- **[false negative]** → 既知パターンのみ検出。未知のサービス ID は漏れる → パターン追加で段階的に改善
- **[パフォーマンス]** → skill/rule ファイルは数十〜数百個程度、正規表現マッチは十分高速 → リスク低

## Future Work

- **エントロピーベース検出 (v2)**: TruffleHog 方式のシャノンエントロピー分析を補助的に導入し、未知のシークレット形式をカバーする。Markdown 特有のノイズ対策として、コードブロック内のみにスコープを限定する設計を検討
- **ベースライン機構 (detect-secrets 方式)**: 既知の false positive を `.hardcoded-baseline.json` にホワイトリスト登録し、CI/audit で差分のみを検出する仕組み。チーム開発でのノイズ削減に有効
