export type ChallengeType = 'solo' | 'time' | 'help_budget'

export interface ChallengeConfig {
  type: ChallengeType
  title: string
  description: string
  icon: string
  color: string | null
  durationSeconds: number | null
  helpBudget: number | null
}

export interface ChallengeAttempt {
  config: ChallengeConfig
  startedAt: string
  endsAt: string | null
  stoppedAt: string | null
}

export const challengeTypes = [
  { title: 'Solo Challenge', value: 'solo' },
  { title: 'Time Challenge', value: 'time' },
  { title: 'Help Budget Challenge', value: 'help_budget' }
]

export const createChallenge = (type: ChallengeType): ChallengeConfig => ({
  type,
  title: challengeTypes.find((item) => item.value === type)!.title,
  description:
    type === 'solo'
      ? 'Start by modeling independently and see how far you can get without support. You can ask for help whenever you need it.'
      : type === 'time'
      ? 'Try to get as far as you can within the time budget. You can keep working after time runs out. The timer continues when you switch tabs or close the editor.'
      : 'Try to stay within the suggested budget of internal hints. Decide deliberately when support would help. Additional help remains available.',
  icon: type === 'solo' ? 'mdi-account-outline' : type === 'time' ? 'mdi-timer-outline' : 'mdi-lightbulb-outline',
  color: null,
  durationSeconds: type === 'time' ? 900 : null,
  helpBudget: type === 'help_budget' ? 3 : null
})

export const challengeGoal = (config: ChallengeConfig): string => (config.type === 'solo' ? 'Start by modeling without support' : config.type === 'time' ? `Time budget: ${Number(((config.durationSeconds ?? 0) / 60).toFixed(2))} minutes` : `Target budget: ${config.helpBudget} internal hints`)
