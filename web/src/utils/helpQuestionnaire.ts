import type { HelpBlueprint, HelpEditableQuestion, HelpQuestionEdit, HelpRequestConfig, HelpSurveyPhase } from '@/services/learningPaths'
import type { SurveyDefinition } from '@/services/surveys'

export const editableHelpQuestions: { name: HelpEditableQuestion; title: string }[] = [
  { name: 'stuck_duration', title: 'Dauer des Stillstands' },
  { name: 'support_need', title: 'Gewünschte Unterstützung' },
  { name: 'next_action', title: 'Hilfequelle wählen' }
]

export const helpQuestion = (blueprint: HelpBlueprint, config: HelpRequestConfig, name: HelpEditableQuestion): HelpQuestionEdit => config.questionEdits?.[name] ?? blueprint.questions[name]

export const helpPhaseDefinition = (blueprint: HelpBlueprint, config: HelpRequestConfig, phase: HelpSurveyPhase): SurveyDefinition => {
  if (phase === 'topic') return blueprint.topic
  const names: HelpEditableQuestion[] = phase === 'reflection' ? ['stuck_duration', 'support_need'] : ['next_action']
  return { elements: names.map(name => {
    const question = helpQuestion(blueprint, config, name)
    return { type: 'radiogroup', name, title: question.title, isRequired: true, choices: question.choices.map(c => c.id), choiceLabels: Object.fromEntries(question.choices.map(c => [c.id, c.text])) }
  }) }
}

export const helpQuestionIssue = (question: HelpQuestionEdit): string => {
  if (!question.title.trim() || question.title.length > 256) return 'Formuliere eine Frage mit höchstens 256 Zeichen.'
  if (question.choices.length < 2 || question.choices.length > 20) return 'Lege zwischen 2 und 20 Antwortoptionen an.'
  if (question.choices.some(c => !c.text.trim() || c.text.length > 256)) return 'Fülle alle Antwortoptionen aus (höchstens 256 Zeichen).'
  if (new Set(question.choices.map(c => c.text.trim().toLocaleLowerCase())).size !== question.choices.length) return 'Antwortoptionen dürfen nicht doppelt vorkommen.'
  return ''
}
