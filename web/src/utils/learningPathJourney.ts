import type { StepRun } from '@/services/learningPaths'

type Station = Pick<StepRun, 'id' | 'status'>

export function journeyDestination<T extends Station>(steps: T[], requestedId: string) {
  const index = steps.findIndex((step) => step.id === requestedId)
  const requested = steps[index]
  if (!requested) return null
  if (requested.status !== 'locked') return { target: requested, blocked: null }

  const reachable = (step: T) => step.status !== 'locked'
  const target = [...steps.slice(0, index)].reverse().find(reachable) ?? steps.find((step) => step.status === 'in_progress') ?? steps.find((step) => step.status === 'available') ?? steps.find(reachable) ?? null
  return { target, blocked: requested }
}
