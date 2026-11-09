import languageService from '@/services/language/language.service'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import type { LanguageVersionReference } from '@/services/api/types/common'
import { languageReferenceKey } from './workspaceLanguageResolver'
import { canonicalJson, type ModelPackage, type PackagedLanguage } from '@/utils/modelPackage'

export interface PackageLanguageStatus {
  language: PackagedLanguage
  available: boolean
}

const isMissing = (error: unknown) => (error as { response?: { status?: number } }).response?.status === 404
const sameDefinition = (left: PackagedLanguage, data: DiagramLanguage, includes: LanguageVersionReference[]) =>
  canonicalJson(left.data) === canonicalJson(data) &&
  canonicalJson(left.includedLanguageVersions) === canonicalJson(includes)

export const inspectPackageLanguages = async (model: ModelPackage): Promise<PackageLanguageStatus[]> => Promise.all(model.languages.map(async (language) => {
  try {
    const [{ data: identity }, { data: version }] = await Promise.all([
      languageService.get(language.languageId),
      languageService.getVersion<DiagramLanguage>(language.languageId, language.versionId)
    ])
    if (identity.archivedAt) throw new Error(`Language "${language.name}" is archived. Restore it before importing this model.`)
    if (!sameDefinition(language, version.data, version.includedLanguageVersions)) throw new Error(`Language version conflict for "${language.name}". The package differs from the installed version.`)
    return { language, available: true }
  } catch (error) {
    if (isMissing(error)) return { language, available: false }
    throw error
  }
}))

/** Missing versions become owned copies; existing definitions are never overwritten. */
export const installPackageLanguages = async (model: ModelPackage, allowInstall: boolean): Promise<LanguageVersionReference[]> => {
  // Recheck at confirmation time, including server errors and changed availability.
  const statuses = await inspectPackageLanguages(model)
  if (!allowInstall && statuses.some((status) => !status.available)) throw new Error('Import the missing language versions before importing the model.')
  const byKey = new Map(statuses.map((status) => [languageReferenceKey(status.language), status]))
  const resolved = new Map<string, LanguageVersionReference>()
  const visit = async (reference: LanguageVersionReference): Promise<LanguageVersionReference> => {
    const key = languageReferenceKey(reference)
    const cached = resolved.get(key)
    if (cached) return cached
    const status = byKey.get(key)!
    const { language } = status
    const includes: LanguageVersionReference[] = []
    for (const dependency of language.includedLanguageVersions) includes.push(await visit(dependency))
    if (status.available) {
      if (canonicalJson(includes) !== canonicalJson(language.includedLanguageVersions)) throw new Error(`Installed language "${language.name}" has unavailable dependencies.`)
      const existing = { languageId: language.languageId, versionId: language.versionId }
      resolved.set(key, existing)
      return existing
    }
    // Reuse a previous imported copy with the same name, definition and dependencies.
    const expected = { ...language, includedLanguageVersions: includes }
    for (let skip = 0; ; skip += 100) {
      const { data: page } = await languageService.list(skip, 100, { q: language.name })
      for (const candidate of page.items.filter((item) => item.name === language.name)) {
        for (let versionSkip = 0; ; versionSkip += 100) {
          const { data: versions } = await languageService.listVersions(candidate.id, versionSkip, 100)
          for (const version of versions.items) {
            const { data: detail } = await languageService.getVersion<DiagramLanguage>(candidate.id, version.id)
            if (sameDefinition(expected, detail.data, detail.includedLanguageVersions)) {
              const match = { languageId: candidate.id, versionId: detail.id }
              resolved.set(key, match)
              return match
            }
          }
          if (!versions.items.length || versionSkip + versions.items.length >= versions.total) break
        }
      }
      if (!page.items.length || skip + page.items.length >= page.total) break
    }
    const { data: created } = await languageService.create({ name: language.name })
    const { data: version } = await languageService.createVersion<DiagramLanguage>(created.id, {
      baseVersionId: null, kind: 'release', releaseName: 'Imported model package',
      includedLanguageVersions: includes, data: language.data
    })
    const imported = { languageId: created.id, versionId: version.id }
    resolved.set(key, imported)
    return imported
  }
  const roots: LanguageVersionReference[] = []
  for (const reference of model.workspaceLanguages) roots.push(await visit(reference))
  return roots
}
