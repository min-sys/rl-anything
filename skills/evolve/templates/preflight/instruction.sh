#!/bin/bash
# Preflight check: instruction category
# スキル指示の遵守確認チェック

# Root-cause: {root_cause}
# このスクリプトは指示違反を防ぐための事前確認を行います

if [ -z "${SKILL_DIR:-}" ]; then
  echo "WARNING: SKILL_DIR が設定されていません"
  exit 0
fi

SKILL_MD="${SKILL_DIR}/SKILL.md"
if [ ! -f "$SKILL_MD" ]; then
  echo "WARNING: SKILL.md が見つかりません: $SKILL_MD"
  exit 0
fi

# Critical Instructions セクションの存在確認
if grep -q "## Critical Instructions" "$SKILL_MD" 2>/dev/null; then
  echo "REMINDER: Critical Instructions セクションを確認してください"
  grep -A 20 "## Critical Instructions" "$SKILL_MD" | head -15
fi

echo "OK: 指示遵守の事前チェック完了"
exit 0
