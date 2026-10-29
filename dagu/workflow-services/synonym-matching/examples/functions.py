"""Run from the service directory: PYTHONPATH=src python examples/functions.py."""
from synonym_matching.preprocessing import apply_pipeline, normalize, lowercase
from synonym_matching.methods import levenshtein, jaro_winkler
from synonym_matching.combiners import mean

steps = [normalize, lowercase]
methods = [levenshtein, jaro_winkler]

reference = [apply_pipeline(label, steps) for label in [' Kunde ', 'Lieferant']]
student = [apply_pipeline(label, steps) for label in ['KUND', 'Supplier']]
scores = {method.__name__: method(reference, student) for method in methods}

for name, matrix in scores.items():
    print(name, matrix.tolist())
print('mean', mean(scores).tolist())
