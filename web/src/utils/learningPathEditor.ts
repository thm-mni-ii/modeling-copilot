import type { Condition, PathStep, PulseSurveyConfig } from '@/services/learningPaths'

export const validatePulseConfig = (config: PulseSurveyConfig | undefined, steps: PathStep[]): string => {
  if (!config) return ''
  if (config.enabled && !config.surveyIds.length) return 'Wähle mindestens einen veröffentlichten Fragebogen für Impulse.'
  if (config.surveyIds.length > 100) return 'Der Pool darf höchstens 100 Fragebögen enthalten.'
  const ranges: [number | null, number, number, boolean][] = [
    [config.minGapSeconds, 1, 86400, false], [config.maxGapSeconds, 1, 86400, true],
    [config.maxPerSession, 1, 100, false], [config.maxPerTask, 1, 1000, true],
    [config.minActiveSeconds, 0, 86400, false]
  ]
  if (ranges.some(([value, min, max, nullable]) => !(nullable && value === null) && (value === null || !Number.isInteger(value) || value < min || value > max))) return 'Prüfe die ganzzahligen Werte und ihre zulässigen Bereiche.'
  if (config.maxGapSeconds !== null && config.maxGapSeconds < config.minGapSeconds) return 'Der Maximalabstand muss mindestens dem Mindestabstand entsprechen.'
  if (config.excludeStepIds.some((id) => !steps.some((step) => step.id === id && step.type !== 'survey'))) return 'Die Impuls-Ausnahmen müssen auf bestehende Tasks verweisen.'
  return ''
}

export const conditionSummary = (condition: Condition, steps: PathStep[]): string => {
  const source = steps.find((step) => step.id === condition.stepId)?.title ?? 'a missing task'
  if (condition.type === 'completed') return `After “${source}” is completed`
  if (condition.type === 'score') return `At least ${condition.value ?? '…'}% on “${source}”`
  if (condition.type === 'at') return condition.at && Number.isFinite(Date.parse(condition.at)) ? `From ${new Date(condition.at).toLocaleString('en-GB', { timeZone: condition.timezone, timeZoneName: 'short' })}` : 'Choose an unlock date'
  return `${Number(((condition.seconds ?? 0) / 3600).toFixed(2))} hours after ${condition.stepId ? `“${source}” is completed` : 'the run starts'}`
}

export const availabilitySummary = (step: PathStep, steps: PathStep[]) => {
  const availability = step.unlock.mode === 'sequence' ? 'After all previous required activities are completed' : step.unlock.conditions.length ? step.unlock.conditions.map((condition) => conditionSummary(condition, steps)).join(step.unlock.mode === 'all' ? ' AND ' : ' OR ') : 'Available immediately'
  const dependents = steps.filter((item) => item.unlock.conditions.some((condition) => condition.stepId === step.id))
  return availability + (dependents.length ? ` · Required for ${dependents.map((item) => item.title).join(', ')}` : '')
}

export const validatePathSteps = (steps: PathStep[]): Record<string, string[]> => {
  const errors: Record<string, string[]> = {}
  const add = (id: string, text: string) => {
    ;(errors[id] ??= []).push(text)
  }
  const ids = new Set(steps.map((step) => step.id))
  for (const step of steps) {
    if (!step.title.trim() || step.title.length > 256) add(step.id, 'Enter a step title of up to 256 characters.')
    if (step.type !== 'survey' && (!step.taskVersion?.taskId || !step.taskVersion?.versionId)) add(step.id, 'Select a published task release.')
    if (step.type === 'survey' && !step.surveyId) add(step.id, 'Select a published questionnaire release.')
    for (const condition of step.unlock.conditions) {
      const source = steps.find((item) => item.id === condition.stepId)
      if (source?.type === 'survey' && source.required === false) add(step.id, 'Optional questionnaires cannot be prerequisites.')
      if (source?.type === 'survey' && condition.type === 'score') add(step.id, 'Questionnaires do not have scores.')
    }
    if (step.unlock.conditions.length > 50) add(step.id, 'Use no more than 50 unlock conditions per step.')
    for (const condition of step.unlock.conditions) {
      if (condition.type === 'score') add(step.id, 'Score conditions are not available yet.')
      if (['completed', 'score'].includes(condition.type) && !condition.stepId) add(step.id, 'Choose a prerequisite task.')
      if (condition.stepId && (!ids.has(condition.stepId) || condition.stepId === step.id)) add(step.id, 'A prerequisite must reference another existing step.')
      if (condition.type === 'score' && (condition.value === null || !Number.isFinite(condition.value) || condition.value < 0 || condition.value > 100)) add(step.id, 'Enter a minimum score between 0 and 100.')
      if (condition.type === 'at' && (!condition.at || !Number.isFinite(Date.parse(condition.at)))) add(step.id, 'Choose a valid unlock date and time.')
      if (condition.type === 'after' && (condition.seconds === null || !Number.isInteger(condition.seconds) || condition.seconds < 0 || condition.seconds > 315360000)) add(step.id, 'Enter a valid non-negative delay (up to ten years).')
    }
    const challenge = step.challenge
    if (challenge) {
      if (!challenge.title.trim() || challenge.title.length > 256) add(step.id, 'Enter a challenge title of up to 256 characters.')
      if (!challenge.description.trim() || challenge.description.length > 3000) add(step.id, 'Enter a challenge introduction of up to 3,000 characters.')
      if (!/^mdi-[a-z0-9-]{1,80}$/.test(challenge.icon)) add(step.id, 'Choose a valid challenge icon.')
      if (challenge.color && !/^#[0-9a-fA-F]{6}$/.test(challenge.color)) add(step.id, 'Choose a valid challenge color.')
      if (challenge.type === 'time' && (!Number.isInteger(challenge.durationSeconds) || (challenge.durationSeconds ?? 0) < 1 || (challenge.durationSeconds ?? 0) > 86400)) add(step.id, 'Enter a time budget between one second and 24 hours.')
      if (challenge.type === 'help_budget' && (!Number.isInteger(challenge.helpBudget) || challenge.helpBudget === null || challenge.helpBudget < 0 || challenge.helpBudget > 1000)) add(step.id, 'Enter a whole-number help budget between 0 and 1,000.')
    }
  }
  // Report every member of a dependency cycle, including errors in hidden details.
  const visited = new Set<string>(),
    active: string[] = []
  const visit = (id: string) => {
    const cycle = active.indexOf(id)
    if (cycle >= 0) {
      active.slice(cycle).forEach((member) => add(member, 'Unlock rules contain a circular dependency.'))
      return
    }
    if (visited.has(id)) return
    active.push(id)
    const index = steps.findIndex((step) => step.id === id)
    const current = steps[index]
    // A sequential step implicitly waits for every earlier required step.
    if (current?.unlock.mode === 'sequence')
      steps
        .slice(0, index)
        .filter((item) => item.type !== 'survey' || item.required !== false)
        .forEach((item) => visit(item.id))
    current?.unlock.conditions.forEach((condition) => {
      if (condition.stepId && ids.has(condition.stepId)) visit(condition.stepId)
    })
    active.pop()
    visited.add(id)
  }
  steps.forEach((step) => visit(step.id))
  return Object.fromEntries(Object.entries(errors).map(([id, messages]) => [id, [...new Set(messages)]]))
}
