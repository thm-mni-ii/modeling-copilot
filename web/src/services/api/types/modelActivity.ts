export interface ModelActivityInteraction {
  id: string
  createdAt: string
  type: 'tab_hidden' | 'tab_visible' | 'focus_lost' | 'focus_gained' | 'idle' | 'active'
}

export interface SaveModelActivitySession {
  createdAt: string
  endedAt: string | null
  interactions: ModelActivityInteraction[]
}
