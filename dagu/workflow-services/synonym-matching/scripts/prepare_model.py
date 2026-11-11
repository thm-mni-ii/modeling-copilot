"""Provision only the existing default model, without running a label comparison."""

from sentence_transformers import SentenceTransformer

from synonym_matching.config import MODEL_NAME, MODEL_REVISION


if __name__ == "__main__":
    SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")
