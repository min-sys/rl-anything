# ADR-016: Skill Self-Evolution Pattern

Date: 2026-03-13
Status: Accepted

## Context

evolve パイプラインはスキル/ルールを「外から」改善するが、スキル自身が実行中に知見を蓄積する仕組みがなかった。aws-deploy と figma-to-code で手動適用した「自己進化パターン」（Pre-flight Check, pitfalls.md, Failure-triggered Learning, Pitfall Lifecycle, Stale Knowledge Guard）は実績がある（figma-to-code: 16 -> 44 pitfalls に成長）。

研究知見により以下の改善点が判明: 根本原因カテゴリ付与（AgentDebug）、成功パターンも蓄積（自己生成カリキュラム: 73% -> 89%改善）、品質ゲートの必要性（全部記録は記憶なしより悪い）、3層コンテキスト管理（MemOS/Letta: Hot/Warm/Cold）、回避回数ベース卒業。

## Decision

- **適性判定**: テレメトリ 3軸（実行頻度・失敗多様性・出力評価可能性）+ LLMキャッシュ 2軸（外部依存度・判断複雑さ）の5項目スコアリング（各1-3点、15点満点）。12-15点=適性高、8-11点=適性中、5-7点=適性低。LLM結果はスキルハッシュ付きでキャッシュ
- **変換パターン**: テンプレートベース挿入。Pre-flight Check、references/pitfalls.md、Failure-triggered Learning テーブル、Pitfall Lifecycle Management、Success Patterns 枠、根本原因カテゴリの6セクションを LLM がスキル文脈に合わせてカスタマイズして挿入
- **品質ゲート**: Candidate -> New の2段階昇格。初回エラーは Candidate（Pre-flight 対象外）、同一根本原因が2回目で New に昇格、ユーザー訂正は即 Active（ゲートスキップ）。根本原因の同一性は Jaccard 類似度 >= 0.5 で判定
- **3層コンテキスト管理**: pitfalls.md 内のセクション分離で実現（ファイル分割なし）。Hot（Active Top 5件, ~500 tokens, Pre-flight で読む）、Warm（New + 残り Active, エラー時のみ）、Cold（Candidate + Graduated, 明示的参照時のみ）
- **卒業判定**: 回避回数ベース。スキル実行頻度に応じた動的調整（高頻度: 10回、中: 5回、低: 3回）
- **evolve パイプライン統合**: Diagnose に skill_evolve_assessment()、Compile に evolve_skill_proposal() via FIX_DISPATCH、Housekeeping に pitfall_hygiene()、Report に自己進化ステータスサマリ
- **対象フィルタ**: classify_artifact_origin() で custom/global のみ。plugin/symlink/既に自己進化済みは除外
- **アンチパターン検出**: Noise Collector、Context Bloat、Band-Aid の評価時3パターン。2件以上該当で変換非推奨

## Alternatives Considered

- **全項目 LLM 判定**: コスト高・再現性低のため却下
- **全項目テレメトリのみ**: 外部依存度・判断複雑さはテレメトリで判定困難なため却下
- **即時記録（品質ゲートなし）**: 「全部記録は記憶なしより悪い」研究結果に反するため改善
- **3回以上で昇格**: 重要な問題の記録が遅れすぎるため却下
- **pitfalls を別ファイル分割（hot.md/warm.md/cold.md）**: ファイル数増加・管理コスト高のため却下
- **データベース管理**: オーバーエンジニアリングのため却下
- **時間ベース卒業（6ヶ月）**: 低頻度スキルでは永遠に卒業しないため、回避回数ベースに改善
- **固定回数卒業**: 高頻度スキルでは早すぎ低頻度では遅すぎるため、動的調整を採用
- **全文 LLM 生成**: 品質にばらつきがあるため、テンプレート+カスタマイズが安定

## Consequences

**良い影響:**
- スキルが実行中に自律的に知見を蓄積し、同じ失敗を繰り返さなくなる
- 品質ゲートにより低品質な pitfall の蓄積を防止（記憶なしよりも悪い状態を回避）
- 3層コンテキスト管理により Pre-flight のトークンコストを ~500 tokens に抑制
- 回避回数ベース卒業により、実績に基づいた pitfall の適切なライフサイクル管理が実現
- evolve パイプラインに自然統合され、独立した運用フローが不要

**悪い影響:**
- テンプレート挿入により SKILL.md が ~30行増加 + references/pitfalls.md が追加される
- 適性スコアの閾値（8/15）が不適切な可能性（evolve-fitness の accept/reject データで要調整）
- LLM キャッシュが陳腐化する可能性（スキルハッシュで変更検出し再計算で対応）
- Active pitfall 10件上限により、重要な知見が見えにくくなる可能性
