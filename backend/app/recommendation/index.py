"""Immutable per-catalog lexical/embedding index; one embedding query per request."""

from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass(frozen=True)
class Evidence:
    word: np.ndarray
    char: np.ndarray
    semantic: np.ndarray | None

    @property
    def lexical(self):
        return 0.45 * self.word + 0.55 * self.char


class SearchIndex:
    def __init__(self, materials, semantic=None):
        self.materials = materials
        self.semantic = semantic
        self.documents = [" ".join([m.title, m.title, m.description, *m.topics, *m.tags]) for m in materials]
        self.word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.word_matrix = self.char_matrix = None
        if materials:
            try:
                self.word_matrix = self.word.fit_transform(self.documents)
            except ValueError:
                pass
            try:
                self.char_matrix = self.char.fit_transform(self.documents)
            except ValueError:
                pass
        self.semantic_matrix = semantic.encode(self.documents) if semantic and materials else None

    def search(self, query, baseline=False):
        count = len(self.materials)
        word = (
            (self.word_matrix @ self.word.transform([query]).T).toarray().ravel()
            if self.word_matrix is not None
            else np.zeros(count)
        )
        char = (
            (self.char_matrix @ self.char.transform([query]).T).toarray().ravel()
            if self.char_matrix is not None
            else np.zeros(count)
        )
        semantic = (
            (self.semantic_matrix @ self.semantic.encode([query], query=True).T).ravel()
            if self.semantic_matrix is not None and not baseline
            else None
        )
        return Evidence(word, char, semantic)
