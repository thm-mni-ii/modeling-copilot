<template>
  <v-container fluid class="pa-0">
    <v-card class="editor-header mx-2 mt-2 mb-1" variant="outlined">
      <div class="editor-toolbar">
        <v-btn icon="mdi-arrow-left" size="small" variant="text" aria-label="Back to diagram languages" @click="goToOverview" />
        <div class="editor-title">
          <div class="d-flex align-center ga-2">
            <span class="font-weight-medium text-truncate">{{ store.language?.name || 'Diagram Language' }}</span>
            <v-chip v-if="store.currentVersion" size="x-small" variant="tonal">v{{ store.currentVersion.versionNumber }}</v-chip>
          </div>
          <div class="text-caption" :class="statusColor">{{ saveStatus }}</div>
        </div>

        <v-spacer />
        <v-btn size="small" variant="text" prepend-icon="mdi-history" :disabled="!store.language" @click="openHistory">History</v-btn>
        <v-btn color="primary" size="small" prepend-icon="mdi-content-save" :loading="store.saving" :disabled="!store.isDirty || store.saving" @click="saveCheckpoint">Save</v-btn>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-bookmark-plus-outline" :disabled="!store.currentVersion || store.saving" @click="openReleaseDialog">Release version</v-btn>
      </div>

      <v-divider />
      <v-tabs v-model="activeEditor" density="compact" color="primary" class="editor-tabs">
        <v-tab value="elements" prepend-icon="mdi-shape">Elements</v-tab>
        <v-tab value="connections" prepend-icon="mdi-connection">Connections</v-tab>
        <v-tab value="syntax" prepend-icon="mdi-code-braces">Syntax</v-tab>
        <v-tab value="feedback" prepend-icon="mdi-comment-check">Feedback</v-tab>
        <v-tab value="settings" prepend-icon="mdi-cog">Settings</v-tab>
      </v-tabs>

      <v-alert v-if="store.error" type="error" variant="tonal" density="compact" class="mx-3 mb-2">{{ store.error }}</v-alert>
      <v-progress-linear v-if="store.loading" indeterminate />
    </v-card>

    <div class="editor-content">
      <div v-show="activeEditor === 'elements'" class="editor-panel"><ElementEditor /></div>
      <div v-show="activeEditor === 'connections'" class="editor-panel"><ConnectionEditor /></div>
      <div v-show="activeEditor === 'syntax'" class="editor-panel"><SyntaxEditor /></div>
      <div v-show="activeEditor === 'feedback'" class="editor-panel"><FeedbackEditor /></div>
      <div v-show="activeEditor === 'settings'" class="editor-panel"><GlobalSettingsEditor /></div>
    </div>
  </v-container>

  <v-dialog v-model="releaseDialog" max-width="520">
    <v-card>
      <v-card-title>Release version</v-card-title>
      <v-card-text>
        <v-text-field v-model="releaseName" label="Release name" variant="outlined" autofocus maxlength="256" counter class="mb-2" @keyup.enter="saveRelease" />
        <v-textarea v-model="versionDescription" label="Description (optional)" variant="outlined" rows="3" maxlength="2000" counter />
        <p class="text-caption text-medium-emphasis mb-0">Releases advance the major version. Checkpoints remain available under All Saves.</p>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="releaseDialog = false">Cancel</v-btn>
        <v-btn color="primary" :loading="store.saving" :disabled="!releaseName.trim() || store.saving" @click="saveRelease">Release</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog v-model="historyDialog" max-width="760">
    <v-card>
      <v-card-title class="d-flex align-center">
        Version history
        <v-spacer />
        <v-btn icon="mdi-refresh" size="small" variant="text" :loading="historyLoading" aria-label="Refresh history" @click="loadHistory(true)" />
      </v-card-title>
      <v-tabs v-model="historyTab" density="compact" class="px-4">
        <v-tab value="versions">Releases</v-tab>
        <v-tab value="saves">All Saves</v-tab>
      </v-tabs>
      <v-card-text class="pt-2">
        <v-progress-linear v-if="historyLoading" indeterminate class="mb-2" />
        <v-alert v-if="historyError" type="error" variant="tonal" density="compact" class="mb-2">{{ historyError }}</v-alert>
        <v-window v-model="historyTab">
          <v-window-item value="versions">
            <LanguageVersionList :entries="releaseVersions" :current-version-id="store.currentVersion?.id" empty-text="No releases yet." @restore="restoreVersion" />
          </v-window-item>
          <v-window-item value="saves">
            <LanguageVersionList :entries="versions" :current-version-id="store.currentVersion?.id" @restore="restoreVersion" />
          </v-window-item>
        </v-window>
      </v-card-text>
      <v-card-actions><v-spacer /><v-btn @click="historyDialog = false">Close</v-btn></v-card-actions>
    </v-card>
  </v-dialog>

  <DialogConfirm ref="confirmDialog" />
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import ConnectionEditor from '@/components/modeling/editors/ConnectionEditor.vue'
import DialogConfirm from '@/components/dialog/DialogConfirm.vue'
import ElementEditor from '@/components/modeling/editors/ElementEditor.vue'
import FeedbackEditor from '@/components/modeling/editors/FeedbackEditor.vue'
import GlobalSettingsEditor from '@/components/modeling/editors/GlobalSettingsEditor.vue'
import LanguageVersionList from '@/components/modeling/versions/LanguageVersionList.vue'
import SyntaxEditor from '@/components/modeling/editors/SyntaxEditor.vue'
import { useDiagramLanguages } from '@/composables/useDiagramLanguages'
import languageService from '@/services/language/language.service'
import type { LanguageVersionInfo } from '@/services/api/types/language'

const route = useRoute()
const router = useRouter()
const store = useDiagramLanguages()
const confirmDialog = ref<InstanceType<typeof DialogConfirm>>()
const activeEditor = ref<'elements' | 'connections' | 'syntax' | 'feedback' | 'settings'>('elements')
const releaseDialog = ref(false)
const releaseName = ref('')
const versionDescription = ref('')
const historyDialog = ref(false)
const historyTab = ref<'versions' | 'saves'>('versions')
const historyLoading = ref(false)
const historyError = ref<string | null>(null)
const versions = ref<LanguageVersionInfo[]>([])

const versionLabel = (entry: LanguageVersionInfo) => (entry.kind === 'release' && entry.releaseName ? `${entry.releaseName} · v${entry.versionNumber}` : `v${entry.versionNumber}`)
const releaseVersions = computed(() => versions.value.filter((entry) => entry.kind === 'release'))
const saveStatus = computed(() => {
  if (store.loading) return 'Loading…'
  if (store.restoredFromVersion) return `Restored from ${versionLabel(store.restoredFromVersion)} · save to apply`
  if (store.isDirty) return 'Unsaved changes'
  return store.currentVersion ? 'All changes saved' : 'No version loaded'
})
const statusColor = computed(() => (store.isDirty ? 'text-warning' : 'text-medium-emphasis'))

const loadHistory = async (force = false) => {
  if (!store.language || (!force && versions.value.length)) return
  historyLoading.value = true
  historyError.value = null
  try {
    versions.value = (await languageService.listVersions(store.language.id, 0, 100)).data.items
  } catch {
    historyError.value = 'The version history could not be loaded.'
  } finally {
    historyLoading.value = false
  }
}

const loadLanguageFromRoute = async () => {
  const languageId = route.params.id as string | undefined
  if (!languageId) return
  try {
    await store.loadLanguage(languageId)
    const restoreId = typeof route.query.restore === 'string' ? route.query.restore : null
    if (restoreId && restoreId !== store.currentVersion?.id) await store.restoreVersion(restoreId)
    versions.value = []
  } catch (error) {
    console.error('Failed to load diagram language:', error)
  }
}

const save = async (kind: 'checkpoint' | 'release', name?: string, description?: string) => {
  try {
    await store.saveCurrentLanguage(kind, name, description)
    if (route.query.restore) await router.replace({ query: { ...route.query, restore: undefined } })
    await loadHistory(true)
    return true
  } catch (error) {
    console.error('Failed to save diagram language:', error)
    return false
  }
}

const saveCheckpoint = () => save('checkpoint')
const openReleaseDialog = () => {
  releaseName.value = ''
  versionDescription.value = ''
  releaseDialog.value = true
}
const saveRelease = async () => {
  if (!releaseName.value.trim()) return
  if (await save('release', releaseName.value, versionDescription.value)) releaseDialog.value = false
}
const openHistory = async () => {
  historyDialog.value = true
  await loadHistory()
}

const confirmUnsavedChanges = async () => {
  if (!store.isDirty) return true
  const choice = await confirmDialog.value?.openUnsavedChangesDialog()
  if (choice === 'discard') {
    await store.discardCurrentChanges()
    return true
  }
  if (choice === 'save') return save('checkpoint')
  return false
}

const restoreVersion = async (entry: LanguageVersionInfo) => {
  if (!(await confirmUnsavedChanges())) return
  try {
    await store.restoreVersion(entry.id)
    historyDialog.value = false
  } catch (error) {
    console.error('Failed to restore diagram language version:', error)
  }
}

const warnBeforeUnload = (event: BeforeUnloadEvent) => {
  if (!store.isDirty) return
  event.preventDefault()
  event.returnValue = ''
}
const goToOverview = () => router.push({ name: 'DiagramLanguages' })

onMounted(() => {
  window.addEventListener('beforeunload', warnBeforeUnload)
  void loadLanguageFromRoute()
})
onBeforeUnmount(() => window.removeEventListener('beforeunload', warnBeforeUnload))
watch(
  () => route.params.id,
  () => void loadLanguageFromRoute()
)
onBeforeRouteLeave(confirmUnsavedChanges)
onBeforeRouteUpdate(confirmUnsavedChanges)
</script>

<style scoped>
.editor-header {
  overflow: hidden;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 54px;
  padding: 6px 10px;
}

.editor-title {
  min-width: 150px;
  max-width: 320px;
  line-height: 1.2;
}

.editor-tabs {
  min-height: 38px;
}

.editor-content {
  margin: 0 8px;
}

.editor-panel {
  height: calc(100vh - 180px);
  display: flex;
  flex-direction: column;
  min-height: 0;
}

@media (max-width: 900px) {
  .editor-toolbar {
    flex-wrap: wrap;
  }

  .editor-title {
    max-width: calc(100% - 48px);
  }
}
</style>
