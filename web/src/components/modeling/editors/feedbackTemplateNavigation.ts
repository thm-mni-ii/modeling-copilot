import type { InjectionKey, Ref } from 'vue'

export type FeedbackTemplateTarget = { kind: 'connection' | 'quantity' | 'cycle' | 'containment' }

export interface FeedbackTemplateNavigation {
  templateTarget: Ref<FeedbackTemplateTarget | null>
  openSyntax: (target: FeedbackTemplateTarget) => void
  openTemplates: (target: FeedbackTemplateTarget) => void
}

export const feedbackTemplateNavigationKey: InjectionKey<FeedbackTemplateNavigation> = Symbol('feedbackTemplateNavigation')

export const feedbackTargetId = (view: 'syntax' | 'template', target: FeedbackTemplateTarget): string => `${view}-${target.kind}`
