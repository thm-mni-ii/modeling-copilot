export type AutonomyMode = 'free' | 'informative' | 'validating' | 'preventive'

export interface AutonomyModeDefinition {
  value: AutonomyMode
  title: string
  description: string
  icon: string
  color: 'primary' | 'info' | 'warning' | 'error'
}

export const AUTONOMY_MODES: AutonomyModeDefinition[] = [
  {
    value: 'free',
    title: 'Free Editing',
    description: 'Edit freely; feedback is available on demand.',
    icon: 'mdi-pencil-outline',
    color: 'primary'
  },
  {
    value: 'informative',
    title: 'Informative Feedback',
    description: 'Highlights rule violations while you keep editing.',
    icon: 'mdi-information-outline',
    color: 'info'
  },
  {
    value: 'validating',
    title: 'Validating Feedback',
    description: 'Reports rule violations immediately after an action.',
    icon: 'mdi-alert-circle-outline',
    color: 'warning'
  },
  {
    value: 'preventive',
    title: 'Preventive Feedback',
    description: 'Blocks invalid actions before they are applied.',
    icon: 'mdi-shield-lock-outline',
    color: 'error'
  }
]
