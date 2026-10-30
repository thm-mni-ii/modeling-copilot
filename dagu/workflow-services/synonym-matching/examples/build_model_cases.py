"""Rebuild synthetic examples from the repository's Order Management graph."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
SOURCE = (
    HERE.parents[3] / 'api/src/modeling_api/db/initial_data'
    / 'order_management_sample_solution.json'
)


def labels(texts, prefix):
    """Erzeuge eindeutige IDs und ergänze die Sprache der Beispieldaten."""
    return [dict(id=f'{prefix}{i}', label=t if isinstance(t, str) else t[0],
                 language='de' if isinstance(t, str) else t[1]) for i, t in enumerate(texts)]


def build():
    """Extrahiere Original-Labels und erstelle synthetische Fälle mit Erwartungen."""
    original = json.loads(SOURCE.read_text())
    root = ET.fromstring(original['model']['version']['data']['xml'])
    cells = [c for c in root.iter('Cell') if c.get('value')]
    refs = [dict(id=c.get('id'), label=c.get('value'), language='en') for c in cells]
    changed = ['Kunde', 'Kundennummer', 'Bestelungen', 'Best.-Nr.', 'Bestellposition',
               'Menge', 'Artikel', 'Produktnummer', 'Verkaufbar']
    students = []
    for reference, text in zip(refs, changed, strict=True):
        students.append({'id': reference['id'], 'label': text, 'language': 'de'})
    cases = []

    def add(number, title, left, right, positives=(), note='', contexts=None):
        """Füge einen Kandidatensatz mit vollständigen Paarannotationen hinzu."""
        r = labels(left, 'r') if not left or not isinstance(left[0], dict) else left
        s = labels(right, 's') if not right or not isinstance(right[0], dict) else right
        positive = set(positives)
        cases.append(dict(id=f'case-{number:02d}', case_number=number, title=title,
                          reference=r, student=s,
                          annotations=[['correct' if (i, j) in positive else 'incorrect'
                                        for j in range(len(s))] for i in range(len(r))],
                          note=note, contexts=contexts or {}))

    pairs = [
        ('Identisch', 'Kunde', 'Kunde'), ('Groß-/Kleinschreibung', 'Kunde', 'kunde'),
        ('Tippfehler', 'Bestellung', 'Bestelung'), ('Zeichenvertauschung', 'Kunde', 'Knude'),
        ('Flexion', 'Bestellung', 'Bestellungen'), ('Abkürzung', 'Bestellnummer', 'Best.-Nr.'),
        ('Kompositum', 'Kundendaten', 'Daten des Kunden'),
        ('Wortreihenfolge und Nominalisierung', 'Kunde registrieren', 'Registrierung Kunde'),
        ('Synonym', 'Kunde', 'Abnehmer'), ('Übersetzung', 'Kunde', ('Customer', 'en')),
        ('Spanisch', 'Rechnung', ('Factura', 'es')),
        ('Paraphrase', 'Bestellung aufgeben', 'Auftrag erteilen'),
        ('Fachterminologie', 'Entität', ('Entity', 'en')),
        ('Ausdrucksform', 'Zahlung durchführen', 'bezahlen'),
        ('Verwandte Rollen', 'Kunde', 'Lieferant'), ('Antonym', 'aktiv', 'inaktiv'),
        ('Ober-/Unterbegriff', 'Fahrzeug', 'Auto'),
        ('Ähnliche Schreibweise', 'Bestellung', 'Bestätigung'),
        ('Gleiche Domäne', 'Rechnung', 'Zahlung'), ('Mehrdeutigkeit', 'Bank', 'Bank')]
    for n, (title, a, b) in enumerate(pairs, 1):
        note = 'Synthetische fachliche Erwartung; keine unabhängig validierte Annotation.'
        contexts = None
        if n == 12:
            note += ' Hier als gleichwertiger Bestellvorgang angenommen; domänenabhängig.'
        if n == 20:
            note = (
                'Referenz: Geldinstitut; Schülerlabel: Sitzmöbel. '
                'Ohne Kontext nicht unterscheidbar.'
            )
            contexts = {'r0': 'Geldinstitut', 's0': 'Sitzmöbel'}
        add(n, title, [a], [b], [(0, 0)] if n <= 14 else [], note, contexts)
    add(21, 'Graph: eindeutige 1:1-Zuordnung', refs, students,
        [(i, i) for i in range(len(refs))],
        'Original-IDs bleiben pro Modell erhalten; Schülerlabels synthetisch verändert.')
    add(22, 'Mehrsprachig und umgeordnet', ['Kunde', 'Rechnung', 'Produkt'],
        [('Product', 'en'), ('Factura', 'es'), ('Customer', 'en')], [(0, 2), (1, 1), (2, 0)])
    add(23, 'Konkurrierende Kandidaten', ['Kunde', 'Bestellung'],
        ['Lieferant', ('Customer', 'en'), 'Kund', 'Bestätigung', 'Bestelung'],
        [(0, 1), (0, 2), (1, 4)])
    add(24, 'Fehlende Entsprechung', ['Kunde', 'Rechnung'], ['Lieferant', 'Zahlung'])
    add(25, 'Unterschiedliche Mengengrößen', ['Kunde', 'Produkt'],
        ['Lieferant', 'Artikel', 'Kunde', 'Zahlung'], [(0, 2), (1, 1)])
    add(26, 'Doppelte Labels mit unterschiedlichen IDs', ['Kunde', 'Kunde'],
        ['Kunde', 'Kunde', 'Lieferant'], [(0, 0), (0, 1), (1, 0), (1, 1)],
        'Alle gleichbedeutenden Labels sind gültig; keine willkürliche 1:1-ID-Zuordnung.')
    add(27, 'Fachlich falsche Konkurrenten', ['Rechnung', 'Fahrzeug'],
        ['Zahlung', 'Auto', ('Invoice', 'en'), ('Vehicle', 'en')], [(0, 2), (1, 3)])
    # Separate subcases keep zero-dimensional matrix shapes explicit.
    for suffix, left, right, positive in [
        ('both-empty', [], [], []), ('reference-empty', [], ['Kunde'], []),
        ('student-empty', ['Kunde'], [], []),
        ('empty-labels', ['', '  ', 'Kunde'], ['', 'Kunde'], [(2, 1)]),
        ('special-characters', ['Änderung', 'Preis (€)', 'Kunde & Co.'],
         ['A\u0308nderung', 'Preis (€)', 'Kunde & Co.'], [(0, 0), (1, 1), (2, 2)])]:
        add(28, 'Randfall: ' + suffix, left, right, positive)
        cases[-1]['id'] += '-' + suffix
    # Zusätzliche Kontrastmengen: jeweils korrekter und plausibel falscher Kandidat.
    hard_cases = [
        ('Negation', ['Zahlung erhalten'], ['Zahlung nicht erhalten', 'Zahlung erhalten']),
        ('Antonym als Konkurrent', ['aktiv'], ['inaktiv', 'aktiv']),
        ('Vertauschte Rollen', ['Kunde bezahlt Lieferant'],
         ['Lieferant bezahlt Kunde', 'Kunde bezahlt Lieferant']),
        ('Statusunterschied', ['Bestellung bestätigt'],
         ['Bestellung storniert', 'Bestellung bestätigt']),
        ('Fachlicher Oberbegriff', ['Fahrzeug'], ['Auto', 'Fahrzeug']),
        ('Kompositum mit anderer Rolle', ['Rechnungsadresse'],
         ['Lieferadresse', 'Rechnungsadresse']),
    ]
    for number, (title, left, right) in enumerate(hard_cases, 29):
        add(number, title, left, right, [(0, 1)])
        cases[-1]['hard_negative'] = True
    return original, dict(
        version=1, provenance={'source': str(SOURCE.relative_to(HERE.parents[3])),
                              'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                              'synthetic': True},
        purpose=('Fixed-threshold diagnostic cases, '
                 'not training or an independent quality benchmark.'),
        cases=cases), dict(step='synonym_matching', input=dict(
            referenceModel={'elements': refs}, studentModel={'elements': students}, threshold=0.5))


def main():
    """Schreibe die reproduzierbaren JSON-Beispiele in diesen Ordner."""
    _, cases, payload = build()
    for name, data in [('model-cases.json', cases), ('order-management-input.json', payload)]:
        (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
