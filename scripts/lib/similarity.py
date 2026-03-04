#!/usr/bin/env python3
"""共通類似度エンジン。

TF-IDF ベクトル化とコサイン類似度計算を提供する。
reorganize / audit / prune / enrich など複数モジュールから利用される Single Source of Truth。
"""
import re
import sys
from typing import Dict, List, Set


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


def compute_pairwise_similarity(
    paths: Dict[str, str], threshold: float = 0.80
) -> List[Dict[str, object]]:
    """ファイル群のペアワイズ コサイン類似度を計算し、閾値以上のペアを返す。

    Args:
        paths: {skill_name: file_path} の辞書
        threshold: 類似度の閾値（デフォルト 0.80）

    Returns:
        [{"path_a": str, "path_b": str, "similarity": float}, ...]
        sklearn 未インストール時は空リスト。
    """
    if len(paths) < 2:
        return []

    # ファイル読み込み
    skill_texts: dict = {}
    path_map: dict = {}  # skill_name -> file_path
    for name, file_path in paths.items():
        try:
            with open(file_path, encoding="utf-8") as f:
                skill_texts[name] = f.read()
            path_map[name] = file_path
        except OSError:
            print(f"Warning: failed to read {file_path}, skipping", file=sys.stderr)

    if len(skill_texts) < 2:
        return []

    # TF-IDF 行列を構築
    matrix, _feature_names, skill_names = build_tfidf_matrix(skill_texts)
    if matrix is None:
        return []

    # ペアワイズ コサイン類似度を計算
    try:
        from scipy.spatial.distance import cosine as cosine_distance
    except ImportError:
        return []

    results: List[Dict[str, object]] = []
    n = len(skill_names)
    for i in range(n):
        for j in range(i + 1, n):
            vec_a = matrix[i].toarray().flatten()
            vec_b = matrix[j].toarray().flatten()
            similarity = 1.0 - cosine_distance(vec_a, vec_b)
            if similarity >= threshold:
                results.append({
                    "path_a": path_map[skill_names[i]],
                    "path_b": path_map[skill_names[j]],
                    "similarity": round(similarity, 4),
                })

    return results


# --- Jaccard 類似度 ---


def tokenize(text: str) -> Set[str]:
    """テキストを空白・句読点で分割し、小文字トークンの集合を返す。"""
    return set(re.split(r"[\s\W_]+", text.lower())) - {""}


def jaccard_coefficient(set_a: Set[str], set_b: Set[str]) -> float:
    """Jaccard 類似度係数を計算する。

    両方が空集合の場合は 0.0 を返す。
    """
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)
