import { inject, provide, type InjectionKey, type Ref } from 'vue'
import type { LanguageVersionReference } from '@/services/api/types/common'
import type { ModelPackage, PackagedLanguage } from '@/utils/modelPackage'

export interface ModelFileContext {
  disabledReason: Ref<string>
  languages: Ref<PackagedLanguage[]>
  workspaceLanguages: Ref<LanguageVersionReference[]>
  importModel: (model: ModelPackage, languages: LanguageVersionReference[]) => Promise<void>
}

const key: InjectionKey<ModelFileContext> = Symbol('ModelFileContext')
export const provideModelFileContext = (context: ModelFileContext) => provide(key, context)
export const useModelFileContext = () => inject(key, null)
