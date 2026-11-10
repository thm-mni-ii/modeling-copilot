import type { InjectionKey, Ref } from 'vue'

export type FeedbackTemplateTarget =
  | { kind: 'connection' | 'quantity' | 'cycle' }
  | { kind: 'relation'; source: string; target: string }
  | { kind: 'route'; source: string; target: string; index: number }
  | { kind: 'limit'; index: number }

export interface FeedbackTemplateNavigation {
  syntaxTarget: Ref<FeedbackTemplateTarget | null>
  templateTarget: Ref<FeedbackTemplateTarget | null>
  openSyntax: (target: FeedbackTemplateTarget) => void
  openTemplates: (target: FeedbackTemplateTarget) => void
}

export const feedbackTemplateNavigationKey: InjectionKey<FeedbackTemplateNavigation> = Symbol('feedbackTemplateNavigation')

export const feedbackTargetId = (view: 'syntax' | 'template', target: FeedbackTemplateTarget): string => {
  switch (target.kind) {
    case 'relation':
      return `${view}-relation-${encodeURIComponent(JSON.stringify([target.source, target.target]))}`
    case 'route':
      return `${view}-route-${encodeURIComponent(JSON.stringify([target.source, target.target, target.index]))}`
    case 'limit':
      return `${view}-limit-${target.index}`
    default:
      return `${view}-${target.kind}`
  }
}
