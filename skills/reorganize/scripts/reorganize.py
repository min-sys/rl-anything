#!/usr/bin/env python3
"""Reorganize フェーズ。

TF-IDF + 階層クラスタリングでスキルを内容類似度に基づきクラスタリングし、
マージ候補・分割候補を提案する。直接の変更は行わない。
"""
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_plugin_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_plugin_root / "skills" / "audit" / "scripts"))

from audit import (
    DATA_DIR,
    classify_artifact_origin,
    find_artifacts,
)

DEFAULT_REORGANIZE_THRESHOLD = 0.7
SPLIT_LINE_THRESHOLD = 300


def load_reorganize_threshold() -> float:
    """evolve-state.json から reorganize_threshold を読み込む。未設定時はデフォルト 0.7。"""
    state_file = DATA_DIR / "evolve-state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            return float(state.get("reorganize_threshold", DEFAULT_REORGANIZE_THRESHOLD))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return DEFAULT_REORGANIZE_THRESHOLD


def build_tfidf_matrix(skill_texts: dict) -> tuple:
    """スキルテキストから TF-IDF 行列を構築する。

    Args:
        skill_texts: {skill_name: text_content} の辞書

    Returns:
        (tfidf_matrix, feature_names, skill_names) のタプル。
        sklearn がインストールされていない場合は (None, None, None)。
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError:
        return None, None, None

    skill_names = list(skill_texts.keys())
    texts = [skill_texts[name] for name in skill_names]

    vectorizer = TfidfVectorizer(max_features=200, stop_words='english')
    matrix = vectorizer.fit_transform(texts)
    return matrix, vectorizer.get_feature_names_out(), skill_names


def cluster_skills(tfidf_matrix, threshold: float = 0.7) -> list:
    """TF-IDF 行列を使って階層クラスタリングを実行する。

    Args:
        tfidf_matrix: TF-IDF 行列（scipy sparse matrix）
        threshold: コサイン距離の閾値（これ以下の距離のスキルが同一クラスタ）

    Returns:
        クラスタラベルのリスト（各スキルに対応）
    """
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist

    distances = pdist(tfidf_matrix.toarray(), metric='cosine')
    Z = linkage(distances, method='average')
    labels = fcluster(Z, t=threshold, criterion='distance')
    return labels.tolist()


def detect_split_candidates(artifacts: Dict[str, List[Path]]) -> List[Dict[str, Any]]:
    """SKILL.md が 300 行を超えるスキルを分割候補として検出する。"""
    candidates = []
    for path in artifacts.get("skills", []):
        origin = classify_artifact_origin(path)
        if origin == "plugin":
            continue
        try:
            line_count = path.read_text(encoding="utf-8").count("\n") + 1
        except OSError:
            continue
        if line_count > SPLIT_LINE_THRESHOLD:
            skill_name = path.parent.name
            candidates.append({
                "skill_name": skill_name,
                "line_count": line_count,
                "threshold": SPLIT_LINE_THRESHOLD,
            })
    return candidates


def extract_centroid_keywords(
    cluster_skills_texts: List[str],
    feature_names,
    tfidf_matrix,
    cluster_indices: List[int],
) -> List[str]:
    """クラスタに属するスキルの TF-IDF ベクトルから上位5キーワードを抽出する。

    Args:
        cluster_skills_texts: クラスタ内のスキルテキストのリスト（未使用、互換性のため保持）
        feature_names: TF-IDF の特徴名（語彙）
        tfidf_matrix: 全体の TF-IDF 行列
        cluster_indices: クラスタに属するスキルのインデックスリスト

    Returns:
        上位5キーワードのリスト
    """
    import numpy as np

    # クラスタ内スキルの TF-IDF ベクトルの平均を計算
    cluster_matrix = tfidf_matrix[cluster_indices].toarray()
    centroid = np.mean(cluster_matrix, axis=0)

    # 上位5キーワードを抽出
    top_indices = centroid.argsort()[::-1][:5]
    return [feature_names[i] for i in top_indices]


def run_reorganize(project_dir: str = None) -> dict:
    """Reorganize を実行してクラスタリング結果を返す。

    Returns:
        クラスタリング結果の辞書。スキル数が不足の場合やライブラリ未インストール時は
        skipped=True で理由を返す。
    """
    proj = Path(project_dir) if project_dir else Path.cwd()
    artifacts = find_artifacts(proj)

    # プラグイン由来スキルを除外してテキストを収集
    skill_texts: Dict[str, str] = {}
    for path in artifacts.get("skills", []):
        origin = classify_artifact_origin(path)
        if origin == "plugin":
            continue
        skill_name = path.parent.name
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        skill_texts[skill_name] = text

    # スキル数が少なすぎる場合はスキップ
    if len(skill_texts) < 5:
        return {
            "skipped": True,
            "reason": "insufficient_skills",
            "count": len(skill_texts),
        }

    # scipy/sklearn のインポートチェック
    try:
        import scipy  # noqa: F401
        import sklearn  # noqa: F401
    except ImportError:
        print(
            "Reorganize: scipy/scikit-learn が未インストールです。"
            "pip install scipy scikit-learn でインストールしてください。",
            file=sys.stderr,
        )
        return {
            "skipped": True,
            "reason": "scipy_not_available",
        }

    # TF-IDF 行列を構築
    tfidf_matrix, feature_names, skill_names = build_tfidf_matrix(skill_texts)
    if tfidf_matrix is None:
        return {
            "skipped": True,
            "reason": "scipy_not_available",
        }

    # 閾値を読み込み
    threshold = load_reorganize_threshold()

    # クラスタリング
    labels = cluster_skills(tfidf_matrix, threshold=threshold)

    # クラスタごとにスキルをグループ化
    cluster_map: Dict[int, List[int]] = {}
    for idx, label in enumerate(labels):
        cluster_map.setdefault(label, []).append(idx)

    # クラスタ情報を構築
    clusters = []
    merge_groups = []

    for cluster_id, indices in sorted(cluster_map.items()):
        cluster_skill_names = [skill_names[i] for i in indices]
        keywords = extract_centroid_keywords(
            [skill_texts[skill_names[i]] for i in indices],
            feature_names,
            tfidf_matrix,
            indices,
        )

        clusters.append({
            "cluster_id": cluster_id,
            "skills": cluster_skill_names,
            "centroid_keywords": keywords,
        })

        # 2つ以上のスキルがあるクラスタはマージ候補
        if len(indices) >= 2:
            # クラスタ内ペアの平均類似度を計算
            from scipy.spatial.distance import cosine as cosine_dist

            total_sim = 0.0
            pair_count = 0
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    vec_a = tfidf_matrix[indices[i]].toarray().flatten()
                    vec_b = tfidf_matrix[indices[j]].toarray().flatten()
                    sim = 1.0 - cosine_dist(vec_a, vec_b)
                    total_sim += sim
                    pair_count += 1

            avg_similarity = total_sim / pair_count if pair_count > 0 else 0.0

            merge_groups.append({
                "skills": cluster_skill_names,
                "reason": "high content similarity",
                "similarity_score": round(avg_similarity, 4),
            })

    # 分割候補
    split_candidates = detect_split_candidates(artifacts)

    return {
        "skipped": False,
        "clusters": clusters,
        "merge_groups": merge_groups,
        "split_candidates": split_candidates,
        "total_clusters": len(clusters),
        "total_merge_groups": len(merge_groups),
        "total_split_candidates": len(split_candidates),
    }


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_reorganize(project)
    print(json.dumps(result, ensure_ascii=False, indent=2))
