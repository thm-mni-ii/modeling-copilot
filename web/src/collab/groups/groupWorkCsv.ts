/** A person from the CSV; row is the line in the file, the header is 1. */
export interface CsvPerson {
  row: number
  username: string
  name: string
}

/** A group of the CSV, which becomes a room. */
export interface CsvGroup {
  name: string
  /** The case study numbers of its members; each becomes a model in the room. */
  caseStudies: string[]
  members: CsvPerson[]
}

/** A row that goes into no group, and why; login name and group as in the file. */
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

/** The columns of the participant list from Moodle; the import needs the first three. */
const COLUMNS = { username: 'Anmeldename', group: 'Gruppen', caseStudy: 'Fallstudie', firstName: 'Vorname', lastName: 'Nachname' } as const
const REQUIRED = ['username', 'group', 'caseStudy'] as const

/** Moodle writes UTF-8, a CSV saved in Excel Windows-1252; a BOM is dropped on decoding. */
export const decodeCsv = (buffer: ArrayBuffer) => {
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(buffer)
  } catch {
    return new TextDecoder('windows-1252').decode(buffer)
  }
}

/** The separator most frequent in the header: tab, semicolon or comma. */
const delimiterOf = (text: string) => {
  const header = text.split(/\r?\n/, 1)[0] ?? ''
  return ['\t', ';', ','].reduce((best, candidate) => (header.split(candidate).length > header.split(best).length ? candidate : best))
}

/** Splits the text into rows and cells; quoted cells may hold separators and line breaks. */
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

/** The numbers of a cell, whether "1", "F1" or "Fallstudie 1", without leading zeros; several separated by comma or semicolon. */
const caseStudiesOf = (cell: string) =>
  cell
    .split(/[,;]/)
    .map((part) => part.match(/\d+/)?.[0])
    .filter((number): number is string => Boolean(number))
    .map((number) => String(Number(number)))

/** Reads the participant list: Anmeldename becomes the person, Gruppen the room, Fallstudie the task. */
export const parseGroupWorkCsv = (text: string): GroupWorkCsv => {
  const [header = [], ...rows] = rowsOf(text, delimiterOf(text))
  const titles = header.map((title) => title.trim())
  const column = Object.fromEntries(Object.entries(COLUMNS).map(([key, title]) => [key, titles.indexOf(title)])) as Record<keyof typeof COLUMNS, number>
  const missing = REQUIRED.filter((key) => column[key] < 0).map((key) => `"${COLUMNS[key]}"`)
  if (missing.length) throw new Error(`The CSV has no column ${missing.join(', ')}.`)

  const groups = new Map<string, CsvGroup>()
  const skipped: CsvSkipped[] = []
  // Per login name the row it first appears in.
  const seen = new Map<string, number>()
  rows.forEach((cells, index) => {
    const row = index + 2
    const value = (key: keyof typeof COLUMNS) => (column[key] < 0 ? '' : cells[column[key]]?.trim() ?? '')
    if (cells.every((cell) => !cell.trim())) return
    const username = value('username')
    const group = value('group')
    const name = `${value('firstName')} ${value('lastName')}`.trim()
    const first = seen.get(username)
    // Moodle separates several groups of a person with commas; which one is meant, the tutor decides in Moodle.
    const reason = !username ? 'No login name' : first ? `Listed twice, first in row ${first}` : !group ? 'No group' : group.includes(',') ? 'In several groups' : null
    if (reason) {
      skipped.push({ row, name, username, group, reason })
      return
    }
    seen.set(username, row)
    const entry = groups.get(group) ?? { name: group, caseStudies: [], members: [] }
    groups.set(group, entry)
    // Mostly one number per person; the group works on the case studies of all its members.
    for (const caseStudy of caseStudiesOf(value('caseStudy'))) if (!entry.caseStudies.includes(caseStudy)) entry.caseStudies.push(caseStudy)
    entry.members.push({ row, username, name: name || username })
  })

  const sorted = [...groups.values()].sort((a, b) => naturally(a.name, b.name))
  for (const group of sorted) group.caseStudies.sort(naturally)
  return { groups: sorted, caseStudies: [...new Set(sorted.flatMap((group) => group.caseStudies))].sort(naturally), skipped, people: seen.size }
}
