export const nextReleaseVersionNumber = (previous?: string | null) => {
  const major = Number.parseInt(previous?.split('.')[0] ?? '0', 10)
  return `${Number.isNaN(major) ? 1 : major + 1}.0`
}

export const releaseVersionLabel = (version: { versionNumber: string; releaseName?: string | null }) =>
  `v${version.versionNumber}${version.releaseName ? ` · ${version.releaseName}` : ''}`
