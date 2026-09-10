<template>
  <div class="library-sidebar">
    <div class="library-actions">
      <v-btn size="small" block variant="tonal" prepend-icon="mdi-bookshelf" @click="openDialog">Manage Languages ({{ workspace.languages.length }})</v-btn>
    </div>

    <v-dialog v-model="dialog" max-width="760">
      <v-card>
        <v-card-title>Model languages</v-card-title>
        <v-card-subtitle>Add, remove, reorder, or switch language releases.</v-card-subtitle>
        <v-card-text>
          <v-progress-linear v-if="loading" indeterminate class="mb-3" />
          <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-3">{{ error }}</v-alert>
          <div v-if="workspace.languages.length" class="language-list mb-4">
            <div v-for="(reference, index) in workspace.languages" :key="reference.languageId" class="language-row">
              <div class="language-name text-truncate">{{ languageName(reference.languageId) }}</div>
              <v-select :model-value="reference.versionId" :items="releaseOptions(reference.languageId, reference.versionId)" item-title="title" item-value="value" label="Release" density="compact" hide-details :loading="loadingVersions.has(reference.languageId)" @update:model-value="changeRelease(reference.languageId, $event)" />
              <div class="d-flex">
                <v-btn icon="mdi-arrow-up" size="x-small" variant="text" :disabled="index === 0" aria-label="Move language up" @click="workspace.moveLanguage(reference.languageId, -1)" />
                <v-btn icon="mdi-arrow-down" size="x-small" variant="text" :disabled="index === workspace.languages.length - 1" aria-label="Move language down" @click="workspace.moveLanguage(reference.languageId, 1)" />
                <v-btn icon="mdi-close" size="x-small" variant="text" color="error" aria-label="Remove language" @click="removeLanguage(reference.languageId)" />
              </div>
            </div>
          </div>
          <div v-else class="text-body-2 text-medium-emphasis mb-4">No language has been added yet.</div>
          <v-divider class="mb-4" />
          <div class="add-row">
            <v-select v-model="newLanguageId" :items="availableLanguages" item-title="name" item-value="id" label="Add language" density="compact" hide-details @update:model-value="selectNewLanguage" />
            <v-select v-model="newVersionId" :items="newReleaseOptions" item-title="title" item-value="value" label="Release" density="compact" hide-details :disabled="!newLanguageId" />
            <v-btn color="primary" :disabled="!newLanguageId || !newVersionId" @click="addLanguage">Add</v-btn>
          </div>
          <p class="text-caption text-medium-emphasis mt-4 mb-0">Compatibility checks and migrations for release changes will be added separately.</p>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="dialog = false">Done</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import languageService from '@/services/language/language.service'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { ApiId } from '@/services/api/types/common'
import type { LanguageOverview, LanguageVersionInfo } from '@/services/api/types/language'

const workspace = useModelWorkspaceStore()
const dialog = ref(false)
const loading = ref(false)
const error = ref<string | null>(null)
const catalog = ref<LanguageOverview[]>([])
const versions = ref<Record<string, LanguageVersionInfo[]>>({})
const loadingVersions = ref(new Set<ApiId>())
const newLanguageId = ref<ApiId | null>(null)
const newVersionId = ref<ApiId | null>(null)

const availableLanguages = computed(() => catalog.value.filter((language) => !workspace.languages.some((reference) => reference.languageId === language.id)))
const versionLabel = (version: LanguageVersionInfo) => `${version.releaseName || 'Release'} · v${version.versionNumber}`
const releaseOptions = (languageId: ApiId, selectedVersionId?: ApiId) => (versions.value[languageId] ?? []).filter((version) => version.kind === 'release' || version.id === selectedVersionId).map((version) => ({ title: version.kind === 'release' ? versionLabel(version) : `Checkpoint · v${version.versionNumber}`, value: version.id }))
const newReleaseOptions = computed(() => (newLanguageId.value ? releaseOptions(newLanguageId.value) : []))
const languageName = (languageId: ApiId) => catalog.value.find((language) => language.id === languageId)?.name ?? workspace.editorLanguages.find((language) => language.id === languageId)?.name ?? 'Unknown language'

const loadVersions = async (languageId: ApiId) => {
  if (versions.value[languageId]) return
  loadingVersions.value = new Set(loadingVersions.value).add(languageId)
  try {
    versions.value[languageId] = (await languageService.listVersions(languageId, 0, 100)).data.items
  } finally {
    const next = new Set(loadingVersions.value)
    next.delete(languageId)
    loadingVersions.value = next
  }
}

const openDialog = async () => {
  dialog.value = true
  loading.value = true
  error.value = null
  try {
    catalog.value = (await languageService.list(0, 100, { archived: false })).data.items
    await Promise.all(workspace.languages.map((reference) => loadVersions(reference.languageId)))
  } catch {
    error.value = 'The language catalog could not be loaded.'
  } finally {
    loading.value = false
  }
}

const selectNewLanguage = async (languageId: ApiId | null) => {
  newVersionId.value = null
  if (!languageId) return
  try {
    await loadVersions(languageId)
    newVersionId.value = releaseOptions(languageId)[0]?.value ?? null
  } catch {
    error.value = 'The releases could not be loaded.'
  }
}

const addLanguage = async () => {
  if (!newLanguageId.value || !newVersionId.value) return
  try {
    error.value = null
    await workspace.addLanguage(newLanguageId.value, newVersionId.value)
    newLanguageId.value = null
    newVersionId.value = null
  } catch {
    error.value = 'The language could not be added.'
  }
}

const changeRelease = async (languageId: ApiId, versionId: ApiId | null) => {
  if (!versionId) return
  try {
    error.value = null
    await workspace.changeLanguageVersion(languageId, versionId)
  } catch {
    error.value = 'The language release could not be changed.'
  }
}

const removeLanguage = async (languageId: ApiId) => {
  try {
    error.value = null
    await workspace.removeLanguage(languageId)
  } catch {
    error.value = 'The language could not be removed.'
  }
}
</script>

<style scoped>
.library-sidebar {
  padding: 8px;
}
.library-actions {
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.14);
}
.language-list {
  display: grid;
  gap: 8px;
}
.language-row {
  display: grid;
  grid-template-columns: minmax(120px, 0.7fr) minmax(220px, 1fr) auto;
  gap: 8px;
  align-items: center;
}
.add-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(220px, 1fr) auto;
  gap: 8px;
  align-items: center;
}
@media (max-width: 700px) {
  .language-row,
  .add-row {
    grid-template-columns: 1fr;
  }
}
</style>
