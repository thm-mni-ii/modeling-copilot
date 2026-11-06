from research.compare import configurations, load_config
from research.rank_results import describe_pipeline


def test_character_token_description_expands_steps_methods_and_group_weights():
    specs = list(configurations(load_config())[0].values())
    spec = next(s for s in specs if s['name'] == 'character_token_ensemble')
    text = describe_pipeline({**spec, 'preprocessing': ['normalize', 'lowercase', 'split_compounds']})
    assert text.startswith('normalize_lowercase_split_compounds - ')
    for method in ['Levenshtein', 'Jaro-Winkler', 'Zeichen-Trigramme',
                   'Token-Jaccard', 'Token-Sort-Ratio']:
        assert method in text
    assert text.count('50%') == 2
    assert 'character_token_ensemble' not in text


def test_weighted_hybrid_describes_separate_preprocessing_and_all_configurations_names():
    specs = list(configurations(load_config())[0].values())
    for spec in specs:
        text = describe_pipeline({**spec, 'preprocessing': []})
        assert 'Unbekannt' not in text
        if spec.get('chain_based'):
            assert ' → ' in text
        else:
            assert text.startswith('ohne_Preprocessing - ')
    weighted = next(s for s in specs if s['name'] == 'string_multi_25_75')
    text = describe_pipeline({**weighted, 'preprocessing': ['normalize', 'lowercase', 'stem']})
    assert '25% Mittel(' in text
    assert '75% Multilinguales Embedding' in text
    assert 'Sprach-/Lexikonpfade: normalize' in text


def test_chain_description_shows_translation_step_and_weights():
    specs = configurations(load_config())[0]
    mix = specs['25% normalize+stem → levenshtein + 75% normalize → multilingual']
    assert describe_pipeline(mix) == ('25% normalize+stem → Levenshtein + '
                                      '75% normalize → Multilinguales Embedding')
    single = specs['normalize+translate → fasttext_en_matching']
    assert describe_pipeline(single).startswith('normalize+DE→EN → FastText (EN) → Greedy')
