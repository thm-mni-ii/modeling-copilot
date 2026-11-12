"""Übernehme die fünf Laborverwaltungsmodelle unverändert in den Vergleich.

Die Sollwerte beschreiben Labelgleichwertigkeit in der gegebenen Aufgabe, keine
strukturelle 1:1-Zuordnung. Aliasgruppen wurden anhand der Modelle und der
Fallstudie festgelegt; gleiche IDs oder Ähnlichkeitsscores erzeugen keine Sollwerte.
"""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[3]
SOURCE = REPOSITORY / 'api/src/modeling_api/db/migrations/versions/v12_laboratory_management'
VARIANTS = {
    'spelling': 'Schreibweise',
    'typos_abbreviations': 'Tippfehler und Abkürzungen',
    'terms': 'Fachbegriffe',
    'languages': 'Sprachmix',
    'ambiguity': 'Abgrenzung und Mehrdeutigkeit',
}

# Explizite Erwartungen nur für diesen Datensatz, kein Wörterbuch für den Service.
# Zeilenumbrüche aus dem Modell bleiben in Eingabe und Sollwerttabelle erhalten.
ALIASES = {
    'Gebäude': ['Gebaeude', 'Building'],
    'GebäudeNr.': ['GebaeudeNr.', 'Building number'],
    'Bezeichnung': ['Bez.'],
    'Etage': ['Stockwerk', 'Etagge'],
    'EtagenNr.': ['Stockwerknummer', 'Etagen-Nummer'],
    'Laborraum': ['laborRaum', 'Laborrraum', 'Laboratory room'],
    'RaumNr.': ['Raumnummer', 'Room number'],
    'Größe': ['Groesse', 'Fläche'],
    'Geräte': ['Geräteart'],
    'GeräteNr.': ['Geräteartnummer'],
    'Labor\nausstattung': [],
    'Anzahl': ['Stückzahl', 'Quantity'],
    'Forschungs\nprojekt': [],
    'ProjektNr.': ['PROJEKTNR.', 'Projektnummer'],
    'Wissen\nschaftler': ['Forschende', 'Scientist'],
    'PersonalNr.': [],
    'Vorname': [],
    'Nachname': ['Familienname'],
    'E-Mail': [],
    'Projekt\nbeteiligung': [],
    'Beginn': ['Start'],
    'Ende': ['End', 'Schluss'],
    'Versuch': ['Ver\nsuch', 'Versuchh', 'Experiment'],
    'VersuchsNr.': ['Experimentnummer', 'Experiment number'],
    'Beschreibung': [],
    'Arbeitseinsatz': ['Arbeits-Einsatz'],
    'EinsatzNr.': [],
}
ENGLISH = {'Building', 'Building number', 'Laboratory room', 'Room number',
           'Quantity', 'Scientist', 'Start', 'End', 'Experiment', 'Experiment number'}


def read_labels(path, english_labels=()):
    """Extrahiere alle beschrifteten Zellen mit Original-IDs und Originaltext."""
    model = json.loads(path.read_text())['model']
    root = ET.fromstring(model['version']['data']['xml'])
    elements = [
        {'id': cell.get('id'), 'label': cell.get('value'),
         'language': 'en' if cell.get('value') in english_labels else 'de'}
        for cell in root.iter('Cell') if cell.get('value', '').strip()
    ]
    ids = [element['id'] for element in elements]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError(f'{path.name}: missing or duplicate IDs')
    return elements


def build():
    """Erzeuge vollständige 48×48-Fälle mit nachvollziehbaren Annotationen."""
    reference = read_labels(SOURCE / 'sample_solution.json')
    if {element['label'] for element in reference} != set(ALIASES):
        raise ValueError('Reference labels changed: review the annotation groups')
    cases = []
    for number, (variant, title) in enumerate(VARIANTS.items(), 101):
        student = read_labels(SOURCE / f'synonym_{variant}.json',
                              ENGLISH if variant == 'languages' else ())
        annotations = [
            ['correct' if element['label'] in {ref['label'], *ALIASES[ref['label']]}
             else 'incorrect' for element in student]
            for ref in reference
        ]
        # Diese IDs markieren lediglich geänderte Stellen für die Fehleranalyse.
        # Sie werden weder als Trainingsmerkmal noch zur Annotation verwendet.
        student_by_id = {element['id']: element['label'] for element in student}
        changed = [ref['id'] for ref in reference
                   if student_by_id.get(ref['id']) != ref['label']]
        reference_by_id = {ref['id']: ref['label'] for ref in reference}
        changed_student = [element['id'] for element in student
                           if reference_by_id.get(element['id']) != element['label']]
        cases.append({
            'id': 'laboratory-' + variant, 'case_number': number,
            'title': 'Laborverwaltung: ' + title, 'reference': reference,
            'student': student, 'annotations': annotations,
            'changed_reference_ids': changed,
            'changed_student_ids': changed_student,
            'note': 'Aufgabenbezogene vorläufige Labelannotation, keine unabhängige Prüfung.',
        })
    files = ['sample_solution.json', 'laboratory_management.json'] + [
        f'synonym_{variant}.json' for variant in VARIANTS]
    return {
        'version': 1,
        'purpose': 'Diagnostischer Vergleich der fünf konstruierten Laborverwaltungsmodelle.',
        'provenance': {
            'source_directory': str(SOURCE.relative_to(REPOSITORY)),
            'source_sha256': {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
                              for name in files},
            'synthetic': True,
        },
        'annotation_policy': {
            'status': 'provisional_task_specific', 'aliases': ALIASES,
            'positives': 'Gleiche oder explizit gleichwertige Labels; auch über verschiedene IDs.',
            'negatives': 'Alle übrigen Paare nach strenger Labelgleichwertigkeit.',
            'decisions': [
                'Die Fallstudie spricht von Gerätearten und Raumgröße in Quadratmetern: '
                'Geräte/Geräteart und Größe/Fläche gelten hier als gleichwertig.',
                'Nr. allein ist zu unspezifisch für RaumNr.; Büro ist kein Synonym für Laborraum.',
                'Geräteraum ist kein Gerätebegriff; Preis ist keine Anzahl.',
                'Beginn/Ende sind verschieden. Ende und Schluss sind gleichwertig, '
                'unabhängig davon, an welcher Modellposition das Label vorkommt.',
            ],
            'limits': 'Keine Graphkontextprüfung, keine automatische 1:1-Sollzuordnung. '
                      'Viele unveränderte Labels; Gesamtergebnisse können Änderungen verdecken. '
                      'Nicht als unabhängigen Test nach weiterer Optimierung verwenden.',
        },
        'cases': cases,
    }


def main():
    """Speichere den Datensatz für den unveränderten research.compare-Befehl."""
    path = HERE / 'laboratory-cases.json'
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    main()
