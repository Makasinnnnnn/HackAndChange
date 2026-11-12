"""Optional local ONNX E5 encoder. Loads files only, never calls inference APIs."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path

import numpy as np

MODEL_ID = "Xenova/multilingual-e5-small"
MODEL_REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"


class SemanticEncoder:
    def __init__(self, directory: Path):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if manifest["revision"] != MODEL_REVISION:
            raise ValueError("Unrecognized semantic model revision")
        for relative in ["onnx/model_quantized.onnx", "tokenizer.json"]:
            with (directory / relative).open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != manifest["sha256"][relative]:
                    raise ValueError("Semantic model checksum mismatch")
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>"), pad_token="<pad>")
        self.tokenizer.enable_truncation(max_length=512)
        options = ort.SessionOptions()
        options.intra_op_num_threads = max(1, min(4, int(os.getenv("ORT_THREADS", "2"))))
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(directory / "onnx/model_quantized.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.input_names = {i.name for i in self.session.get_inputs()}
        self.lock = threading.Lock()
        self.model_id = MODEL_ID

    def encode(self, texts: list[str], query=False) -> np.ndarray:
        vectors = []
        for start in range(0, len(texts), 16):
            with self.lock:
                tokens = self.tokenizer.encode_batch(
                    [("query: " if query else "passage: ") + t for t in texts[start : start + 16]]
                )
                inputs = {
                    "input_ids": np.array([t.ids for t in tokens], dtype=np.int64),
                    "attention_mask": np.array([t.attention_mask for t in tokens], dtype=np.int64),
                    "token_type_ids": np.array([t.type_ids for t in tokens], dtype=np.int64),
                }
                hidden = self.session.run(None, {k: v for k, v in inputs.items() if k in self.input_names})[0]
            mask = inputs["attention_mask"][..., None]
            pooled = (hidden * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
            vectors.append(pooled / np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12))
        return np.concatenate(vectors).astype(np.float32)


def optional_encoder():
    directory = os.getenv("SEMANTIC_MODEL_DIR")
    if not directory:
        return None, "not_enabled"
    try:
        return SemanticEncoder(Path(directory)), None
    except Exception:
        # No private paths or model internals in the public fallback reason.
        return None, "local_model_unavailable"
