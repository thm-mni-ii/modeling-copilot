"""Genau das gewählte Embedding samt gepinnter Architektur vorbereiten."""

import argparse

from synonym_matching.methods import MODELS, SentenceEmbedding


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', choices=MODELS, default='jina_de')
    args = parser.parse_args()
    backend = SentenceEmbedding(args.model)
    backend.load(allow_download=True)
    print(backend.metadata())


if __name__ == '__main__':
    main()
