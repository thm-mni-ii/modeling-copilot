import { inject, provide, type InjectionKey, type Ref } from 'vue'
import type { LanguageVersionReference } from '@/services/api/types/common'
import type { ModelPackage, PackagedLanguage } from '@/utils/modelPackage'
import type { CompletionGate } from '@/services/learningPaths'

export interface ModelFileContext {
  disabledReason: Ref<string>
  // Learning-path task: the model must not leave or be copied (no export, import or branch).
  learningPath: Ref<boolean>
  // Completion requirement of the learning-path task, so evaluations show the same result as the completion check.
  completionGate: Ref<CompletionGate | null>
  languages: Ref<PackagedLanguage[]>
  workspaceLanguages: Ref<LanguageVersionReference[]>
  importModel: (model: ModelPackage, languages: LanguageVersionReference[]) => Promise<void>
}

const key: InjectionKey<ModelFileContext> = Symbol('ModelFileContext')
export const provideModelFileContext = (context: ModelFileContext) => provide(key, context)
export const useModelFileContext = () => inject(key, null)
