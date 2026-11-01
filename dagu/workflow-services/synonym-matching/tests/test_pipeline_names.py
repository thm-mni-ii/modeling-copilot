from research.compare import configurations
from research.rank_results import describe_pipeline


def test_character_token_description_expands_steps_methods_and_group_weights():
    specs = list(configurations(True, True, {'lowercase': ['normalize', 'lowercase']}).values())
    spec = next(s for s in specs if s['name'] == 'character_token_ensemble')
    text = describe_pipeline({**spec, 'preprocessing': ['normalize', 'lowercase', 'split_compounds']})
    assert text.startswith('normalize_lowercase_split_compounds - ')
    for method in ['Levenshtein', 'Jaro-Winkler', 'Zeichen-Trigramme',
                   'Token-Jaccard', 'Token-Sort-Ratio']:
        assert method in text
    assert text.count('50%') == 2
    assert 'character_token_ensemble' not in text


def test_weighted_hybrid_describes_separate_preprocessing_and_all_configurations_names():
    specs = list(configurations(True, True, {'lowercase': ['normalize', 'lowercase']}).values())
    for spec in specs:
        text = describe_pipeline({**spec, 'preprocessing': []})
        assert text.startswith('ohne_Preprocessing - ')
        assert 'Unbekannt' not in text
    weighted = next(s for s in specs if s['name'] == 'string_multi_25_75')
    text = describe_pipeline({**weighted, 'preprocessing': ['normalize', 'lowercase', 'stem']})
    assert '25% Mittel(' in text
    assert '75% Multilinguales Embedding' in text
    assert 'Sprach-/Lexikonpfade: normalize' in text
