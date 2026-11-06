"""Bereite die drei Standardmodelle einmalig für spätere Offline-Aufrufe vor."""

from synonym_matching import MatchingEngine


def main():
    """Lade und prüfe beide Embedding-Pfade inklusive DE→EN-Übersetzung."""
    engine = MatchingEngine({
        'methods': ['multilingual', 'translated_embedding'],
    })
    engine.match(
        [{'id': 'r1', 'label': 'Kunde', 'language': 'de'}],
        [{'id': 's1', 'label': 'Customer', 'language': 'en'}],
    )
    print('Standardmodelle für Embeddings und Übersetzung sind verfügbar.')


if __name__ == '__main__':
    main()
