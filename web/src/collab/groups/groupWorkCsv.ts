/** Eine Person aus der CSV; row ist die Zeile in der Datei, die Kopfzeile ist 1. */
export interface CsvPerson {
  row: number
  username: string
  name: string
}

/** Eine Gruppe der CSV, aus der ein Raum wird. */
export interface CsvGroup {
  name: string
  /** Die Nummern der Fallstudien ihrer Mitglieder; jede wird ein Modell im Raum. */
  caseStudies: string[]
  members: CsvPerson[]
}

/** Eine Zeile, die nicht in eine Gruppe kommt, und warum; Anmeldename und Gruppe wie in der Datei. */
export interface CsvSkipped {
  row: number
  name: string
  username: string
  group: string
  reason: string
}

export interface GroupWorkCsv {
  groups: CsvGroup[]
  caseStudies: string[]
  skipped: CsvSkipped[]
  people: number
}

/** Die Spalten der Teilnehmerliste aus Moodle; die drei ersten braucht der Import. */
const COLUMNS = { username: 'Anmeldename', group: 'Gruppen', caseStudy: 'Fallstudie', firstName: 'Vorname', lastName: 'Nachname' } as const
const REQUIRED = ['username', 'group', 'caseStudy'] as const

/** Moodle schreibt UTF-8, ein in Excel gespeichertes CSV Windows-1252; ein BOM fällt beim Dekodieren weg. */
export const decodeCsv = (buffer: ArrayBuffer) => {
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(buffer)
  } catch {
    return new TextDecoder('windows-1252').decode(buffer)
  }
}

/** Das Trennzeichen, das in der Kopfzeile am häufigsten vorkommt: Tab, Semikolon oder Komma. */
const delimiterOf = (text: string) => {
  const header = text.split(/\r?\n/, 1)[0] ?? ''
  return ['\t', ';', ','].reduce((best, candidate) => (header.split(candidate).length > header.split(best).length ? candidate : best))
}

/** Zerlegt den Text in Zeilen und Zellen; Zellen in Anführungszeichen dürfen Trennzeichen und Umbrüche enthalten. */
const rowsOf = (text: string, delimiter: string) => {
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let index = 0; index < text.length; index++) {
    const char = text[index]
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        cell += '"'
        index++
      } else if (char === '"') quoted = false
      else cell += char
    } else if (char === '"') quoted = true
    else if (char === delimiter) {
      row.push(cell)
      cell = ''
    } else if (char === '\n' || char === '\r') {
      if (char === '\r' && text[index + 1] === '\n') index++
      rows.push([...row, cell])
      row = []
      cell = ''
    } else cell += char
  }
  if (cell || row.length) rows.push([...row, cell])
  return rows
}

const naturally = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true })

/** Die Nummern einer Zelle, ob „1“, „F1“ oder „Fallstudie 1“, ohne führende Nullen; mehrere getrennt durch Komma oder Semikolon. */
const caseStudiesOf = (cell: string) =>
  cell
    .split(/[,;]/)
    .map((part) => part.match(/\d+/)?.[0])
    .filter((number): number is string => Boolean(number))
    .map((number) => String(Number(number)))

/** Liest die Teilnehmerliste: Anmeldename wird die Person, Gruppen der Raum, Fallstudie die Aufgabe. */
export const parseGroupWorkCsv = (text: string): GroupWorkCsv => {
  const [header = [], ...rows] = rowsOf(text, delimiterOf(text))
  const titles = header.map((title) => title.trim())
  const column = Object.fromEntries(Object.entries(COLUMNS).map(([key, title]) => [key, titles.indexOf(title)])) as Record<keyof typeof COLUMNS, number>
  const missing = REQUIRED.filter((key) => column[key] < 0).map((key) => `"${COLUMNS[key]}"`)
  if (missing.length) throw new Error(`The CSV has no column ${missing.join(', ')}.`)

  const groups = new Map<string, CsvGroup>()
  const skipped: CsvSkipped[] = []
  // Je Anmeldename die Zeile, in der er zuerst steht.
  const seen = new Map<string, number>()
  rows.forEach((cells, index) => {
    const row = index + 2
    const value = (key: keyof typeof COLUMNS) => (column[key] < 0 ? '' : cells[column[key]]?.trim() ?? '')
    if (cells.every((cell) => !cell.trim())) return
    const username = value('username')
    const group = value('group')
    const name = `${value('firstName')} ${value('lastName')}`.trim()
    const first = seen.get(username)
    // Moodle trennt mehrere Gruppen einer Person mit Komma; welche gemeint ist, entscheidet der Tutor in Moodle.
    const reason = !username ? 'No login name' : first ? `Listed twice, first in row ${first}` : !group ? 'No group' : group.includes(',') ? 'In several groups' : null
    if (reason) {
      skipped.push({ row, name, username, group, reason })
      return
    }
    seen.set(username, row)
    const entry = groups.get(group) ?? { name: group, caseStudies: [], members: [] }
    groups.set(group, entry)
    // Meist eine Nummer je Person; die Gruppe bearbeitet die Fallstudien all ihrer Mitglieder.
    for (const caseStudy of caseStudiesOf(value('caseStudy'))) if (!entry.caseStudies.includes(caseStudy)) entry.caseStudies.push(caseStudy)
    entry.members.push({ row, username, name: name || username })
  })

  const sorted = [...groups.values()].sort((a, b) => naturally(a.name, b.name))
  for (const group of sorted) group.caseStudies.sort(naturally)
  return { groups: sorted, caseStudies: [...new Set(sorted.flatMap((group) => group.caseStudies))].sort(naturally), skipped, people: seen.size }
}
