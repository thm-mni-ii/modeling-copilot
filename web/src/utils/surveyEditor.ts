import type { SurveyQuestion } from '@/services/surveys'

export const questionTypes = [
  { title: 'Freitext', value: 'comment' },
  { title: 'Einfachauswahl', value: 'radiogroup' },
  { title: 'Mehrfachauswahl', value: 'checkbox' },
  { title: 'Bewertungsskala', value: 'rating' },
  { title: 'Likert-Skala', value: 'matrix' }
]
export const questionTypeLabel = (question: SurveyQuestion) => questionTypes.find((type) => type.value === question.type)?.title ?? question.type
export const titleRule = (value: string) => (!!value?.trim() && value.length <= 256) || 'Bitte einen Titel mit maximal 256 Zeichen eingeben.'
export const optionsRule = (value: string) => {
  const values = (value ?? '').split('\n')
  return (values.length <= 100 && values.every((v) => !!v.trim() && v.length <= 256) && new Set(values).size === values.length) || 'Bitte 1–100 eindeutige, nicht leere Einträge mit maximal 256 Zeichen eingeben.'
}
export const ratingRule = (question: SurveyQuestion) => {
  const min = question.rateMin ?? 1,
    max = question.rateMax ?? 5
  return (Number.isInteger(min) && Number.isInteger(max) && min >= 0 && max <= 100 && max > min) || 'Ganzzahlen: 0 ≤ Minimum < Maximum ≤ 100.'
}
export function questionIssues(question: SurveyQuestion): string[] {
  const errors: string[] = []
  const check = (result: true | string, prefix = '') => {
    if (result !== true) errors.push(prefix + result)
  }
  check(titleRule(question.title))
  if (['radiogroup', 'checkbox'].includes(question.type)) check(optionsRule(question.choices?.join('\n') ?? ''), 'Antwortoptionen: ')
  if (question.type === 'matrix') {
    check(optionsRule(question.rows?.join('\n') ?? ''), 'Aussagen: ')
    check(optionsRule(question.columns?.join('\n') ?? ''), 'Skalenoptionen: ')
  }
  if (question.type === 'rating') check(ratingRule(question))
  return errors
}
