import type { Condition, PathStep } from '@/services/learningPaths'

export const conditionSummary = (condition: Condition, steps: PathStep[]): string => {
  const source = steps.find((step) => step.id === condition.stepId)?.title ?? 'a missing task'
  if (condition.type === 'completed') return `After “${source}” is completed`
  if (condition.type === 'score') return `At least ${condition.value ?? '…'}% on “${source}”`
  if (condition.type === 'at') return condition.at && Number.isFinite(Date.parse(condition.at)) ? `From ${new Date(condition.at).toLocaleString('en-GB', { timeZone: condition.timezone, timeZoneName: 'short' })}` : 'Choose an unlock date'
  return `${Number(((condition.seconds ?? 0) / 3600).toFixed(2))} hours after ${condition.stepId ? `“${source}” is completed` : 'the run starts'}`
}

export const availabilitySummary = (step: PathStep, steps: PathStep[]) => (step.unlock.conditions.length ? step.unlock.conditions.map((condition) => conditionSummary(condition, steps)).join(step.unlock.mode === 'all' ? ' AND ' : ' OR ') : 'Available immediately')

export const validatePathSteps = (steps: PathStep[]): Record<string, string[]> => {
  const errors: Record<string, string[]> = {}
  const add = (id: string, text: string) => {
    ;(errors[id] ??= []).push(text)
  }
  const ids = new Set(steps.map((step) => step.id))
  for (const step of steps) {
    if (!step.title.trim() || step.title.length > 256) add(step.id, 'Enter a step title of up to 256 characters.')
    if (!step.taskVersion.taskId || !step.taskVersion.versionId) add(step.id, 'Select a published task release.')
    if (step.unlock.conditions.length > 50) add(step.id, 'Use no more than 50 unlock conditions per step.')
    for (const condition of step.unlock.conditions) {
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
    steps
      .find((step) => step.id === id)
      ?.unlock.conditions.forEach((condition) => {
        if (condition.stepId && ids.has(condition.stepId)) visit(condition.stepId)
      })
    active.pop()
    visited.add(id)
  }
  steps.forEach((step) => visit(step.id))
  return Object.fromEntries(Object.entries(errors).map(([id, messages]) => [id, [...new Set(messages)]]))
}
