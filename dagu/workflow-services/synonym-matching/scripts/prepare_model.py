"""Provision only the existing default model, without running a label comparison."""

from sentence_transformers import SentenceTransformer

from synonym_matching.methods.registry import MULTILINGUAL_PARAMETERS


if __name__ == "__main__":
    SentenceTransformer(
        MULTILINGUAL_PARAMETERS["model"],
        revision=MULTILINGUAL_PARAMETERS["revision"],
        device=MULTILINGUAL_PARAMETERS["device"],
    )
