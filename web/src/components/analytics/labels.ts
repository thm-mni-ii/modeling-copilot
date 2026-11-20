const SUPPORT_KINDS: Record<string, string> = {
  'help.check': 'Check',
  'help.clarify': 'Clarify',
  'help.next_step': 'Next step',
  'help.example': 'Example',
  'help.solution': 'Solution',
  recognition: 'Recognition overview'
}
const HELP_STAGES: Record<string, string> = {
  topic: 'Problem area question', marking: 'Marking', reflection: 'Reflection questions',
  action: 'Help source question', completed: 'Completed', cancelled: 'Cancelled'
}

export const supportKindLabel = (kind: string | null) => kind ? SUPPORT_KINDS[kind] ?? kind : '—'
export const helpStageLabel = (stage: string | null) => stage ? HELP_STAGES[stage] ?? stage : '—'
export const percentText = (value: number | null) => value === null ? '—' : `${value}%`
export const durationText = (seconds: number | null) => {
  if (seconds === null) return '—'
  if (seconds < 60) return `${Math.round(seconds)} s`
  const minutes = Math.round(seconds / 60)
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}
