<template>
  <div class="sidebar-persistence">
    <SidebarPanelHeader v-if="showHeader" title="Import / Export" />
    <div class="persistence-navigation">
      <v-btn-toggle v-model="mode" mandatory density="compact" variant="outlined" color="primary" class="mode-switch" :disabled="busy" aria-label="Import or export">
        <v-btn value="export" :aria-pressed="mode === 'export'">Export</v-btn>
        <v-btn value="import" :aria-pressed="mode === 'import'">Import</v-btn>
      </v-btn-toggle>
    </div>

    <div class="persistence-actions">
      <template v-if="mode === 'export'">
        <v-btn block color="primary" size="small" prepend-icon="mdi-download" :loading="operation === 'export'" :disabled="!canExport" @click="downloadModel">{{ downloadLabel }}</v-btn>
      </template>
      <template v-else>
        <p v-if="selectedPackage" class="replacement-note">Replaces the current canvas. Required task languages stay assigned.</p>
        <v-btn block color="primary" size="small" prepend-icon="mdi-upload" :loading="operation === 'import'" :disabled="!canImport" @click="importModel">Import model</v-btn>
      </template>
    </div>

    <div class="persistence-content" :aria-busy="busy">
      <template v-if="mode === 'export'">
        <div class="field-group">
          <v-select v-model="format" label="Format" :items="formats" density="compact" variant="outlined" :disabled="!graph || busy" hide-details />
          <p class="sidebar-hint">{{ formatDescription }}</p>
        </div>

        <div v-if="format !== 'mcmodel'" class="field-group">
          <v-select v-model="resolution" :label="format === 'png' ? 'Resolution' : 'Output size'" :items="resolutions" density="compact" variant="outlined" :disabled="!graph || busy" hide-details />
          <v-text-field v-if="resolution === 'custom'" v-model.number="customWidth" type="number" label="Width (px)" min="1" step="1" density="compact" variant="outlined" :disabled="!graph || busy" :error="Boolean(imageResult.error)" hide-details />
          <p v-if="imageResult.size" class="output-dimensions" aria-live="polite">{{ imageResult.size.width }} × {{ imageResult.size.height }} px</p>
          <p v-if="imageResult.error" class="inline-message inline-message--error" role="alert">{{ imageResult.error }}</p>
        </div>

        <v-checkbox v-model="includeFeedback" label="Include feedback" density="compact" :disabled="!graph || busy" hide-details />
        <p v-if="format !== 'mcmodel'" class="sidebar-hint">Complete model on white, without editing controls.</p>
        <p v-if="!graph" class="sidebar-hint">Open a model to export it.</p>
        <p v-if="exportError" class="inline-message inline-message--error" role="alert">{{ exportError }}</p>
        <p v-if="exportComplete" class="inline-message inline-message--success" role="status">Download started.</p>
      </template>

      <template v-else>
        <div class="field-group">
          <p class="sidebar-description">Open an exported model with its modeling languages.</p>
          <input ref="fileInput" class="file-input" type="file" accept=".mcmodel" :disabled="busy || Boolean(importUnavailableReason)" @change="onFileSelected" />
          <v-btn block variant="outlined" size="small" prepend-icon="mdi-folder-open" :disabled="busy || Boolean(importUnavailableReason)" :loading="operation === 'check'" @click="fileInput?.click()">{{ selectedFileName ? 'Change file' : 'Choose file' }}</v-btn>
          <p class="sidebar-hint">.mcmodel · up to 20 MB</p>
          <p v-if="selectedFileName" class="selected-file">{{ selectedFileName }}</p>
        </div>

        <p v-if="operation === 'check'" class="sidebar-hint" role="status">Checking file and languages…</p>
        <template v-if="selectedPackage">
          <section class="language-check" aria-label="Required modeling languages">
            <div class="language-summary" :class="hasMissingLanguages ? 'language-summary--missing' : 'language-summary--ready'" role="status">
              <v-icon :icon="hasMissingLanguages ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline'" size="16" />
              <span>{{ hasMissingLanguages ? `${missingLanguageCount} ${missingLanguageCount === 1 ? 'language' : 'languages'} missing` : languageStatuses.length ? 'All languages available' : 'No languages required' }}</span>
            </div>
            <ul v-if="languageStatuses.length" class="language-list">
              <li v-for="status in languageStatuses" :key="`${status.language.languageId}:${status.language.versionId}`">
                <span class="language-name">{{ status.language.name }}</span>
                <span class="language-status" :class="{ 'language-status--missing': !status.available }">{{ status.available ? 'Available' : 'Missing' }}</span>
              </li>
            </ul>
          </section>
          <div v-if="hasMissingLanguages" class="field-group">
            <v-checkbox v-model="importMissingLanguages" label="Import missing languages" density="compact" :disabled="busy" hide-details />
            <p class="sidebar-hint">Adds copies to your language library. Existing definitions stay unchanged.</p>
          </div>
        </template>

        <p v-if="importUnavailableReason" class="sidebar-hint">{{ importUnavailableReason }}</p>
        <p v-if="importError" class="inline-message inline-message--error" role="alert">{{ importError }}</p>
        <p v-if="importComplete" class="inline-message inline-message--success" role="status">Model imported.</p>
      </template>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef, watch } from 'vue'
import { InternalEvent, type ConnectionHandler } from '@maxgraph/core'
import { saveTextFile } from '@/utils/modelPersistence'
import { MAX_PACKAGE_BYTES, packageModelXml, parseModelPackage, type ModelPackage } from '@/utils/modelPackage'
import { exportModelImage, getModelImageSize } from '@/utils/modelImageExport'
import { inspectPackageLanguages, installPackageLanguages, type PackageLanguageStatus } from '@/services/model/modelPackage.service'
import { useGraphContext } from '@/composables/useGraphContext'
import { useModelFileContext } from '@/composables/useModelFileContext'
import SidebarPanelHeader from './SidebarPanelHeader.vue'

withDefaults(defineProps<{ showHeader?: boolean }>(), { showHeader: true })
const { graph } = useGraphContext()
const files = useModelFileContext()
const mode = ref<'export' | 'import'>('export')
const operation = ref<'export' | 'check' | 'import' | null>(null)
const busy = computed(() => operation.value !== null)
const format = ref<'mcmodel' | 'png' | 'svg'>(files ? 'mcmodel' : 'png')
const formats = computed(() => [
  ...(files ? [{ title: 'Model (.mcmodel)', value: 'mcmodel' }] : []),
  { title: 'PNG image', value: 'png' }, { title: 'SVG image', value: 'svg' }
])
const formatDescription = computed(() => ({
  mcmodel: 'Editable model, including its modeling languages.',
  png: 'Image for documents and submissions.',
  svg: 'Vector graphic. Scales without quality loss.'
}[format.value]))
const downloadLabel = computed(() => format.value === 'mcmodel' ? 'Download model' : `Download ${format.value.toUpperCase()}`)
const includeFeedback = ref(false)
const resolution = ref<number | 'custom'>(2)
const customWidth = ref(1920)
const resolutions = [{ title: 'Original (1×)', value: 1 }, { title: 'Large (2×)', value: 2 }, { title: 'Extra large (4×)', value: 4 }, { title: 'Custom width', value: 'custom' }]
const imageOptions = computed(() => ({ includeFeedback: includeFeedback.value, scale: typeof resolution.value === 'number' ? resolution.value : 1, ...(resolution.value === 'custom' ? { width: customWidth.value } : {}) }))
const imageRevision = ref(0)
watch(graph, (currentGraph, _previous, onCleanup) => {
  if (!currentGraph) return
  const refreshSize = () => { imageRevision.value++ }
  currentGraph.getDataModel().addListener(InternalEvent.CHANGE, refreshSize)
  onCleanup(() => currentGraph.getDataModel().removeListener(refreshSize))
}, { immediate: true })
const imageResult = computed(() => {
  void imageRevision.value
  if (!graph.value || mode.value !== 'export' || format.value === 'mcmodel') return { size: null, error: '' }
  if (resolution.value === 'custom' && (!Number.isInteger(customWidth.value) || customWidth.value <= 0)) return { size: null, error: 'Enter a positive whole number for the width.' }
  try {
    const size = getModelImageSize(graph.value, imageOptions.value)
    const tooLarge = format.value === 'png' && (size.width > 16384 || size.height > 16384 || size.width * size.height > 64_000_000)
    return { size, error: tooLarge ? 'Reduce the resolution: PNG supports up to 16,384 px per side and 64 megapixels.' : '' }
  } catch (cause) { return { size: null, error: cause instanceof Error ? cause.message : 'The image size could not be calculated.' } }
})
const selectedFileName = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const selectedPackage = shallowRef<ModelPackage | null>(null)
const languageStatuses = shallowRef<PackageLanguageStatus[]>([])
const importMissingLanguages = ref(false)
const exportError = ref('')
const importError = ref('')
const exportComplete = ref(false)
const importComplete = ref(false)
const importUnavailableReason = computed(() => files ? files.disabledReason.value : 'Open a model workspace to import a file.')
const missingLanguageCount = computed(() => languageStatuses.value.filter((status) => !status.available).length)
const hasMissingLanguages = computed(() => missingLanguageCount.value > 0)
const canImport = computed(() => !!graph.value && !!files && !files.disabledReason.value && !!selectedPackage.value && !busy.value && (!hasMissingLanguages.value || importMissingLanguages.value))
const canExport = computed(() => !!graph.value && !busy.value && (format.value === 'mcmodel' ? !!files : !!imageResult.value.size && !imageResult.value.error))

watch([format, resolution, customWidth, includeFeedback], () => {
  exportError.value = ''
  exportComplete.value = false
})

const downloadModel = async () => {
  if (!graph.value || !canExport.value) return
  operation.value = 'export'
  exportError.value = ''
  exportComplete.value = false
  try {
    if (format.value === 'mcmodel' && files) {
      const model: ModelPackage = {
        format: 'modeling-copilot-model', version: 1,
        model: { xml: packageModelXml(graph.value, includeFeedback.value) },
        workspaceLanguages: files.workspaceLanguages.value,
        languages: files.languages.value
      }
      const text = JSON.stringify(model, null, 2)
      parseModelPackage(text)
      saveTextFile(text, 'model.mcmodel', 'application/vnd.modeling-copilot.model+json')
    } else if (format.value !== 'mcmodel') {
      await exportModelImage(graph.value, format.value, imageOptions.value)
    }
    exportComplete.value = true
  } catch (cause) {
    exportError.value = cause instanceof Error ? cause.message : 'Export failed.'
  } finally { operation.value = null }
}

const onFileSelected = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || busy.value || importUnavailableReason.value) return
  operation.value = 'check'
  importError.value = ''
  importComplete.value = false
  selectedFileName.value = file.name
  selectedPackage.value = null
  languageStatuses.value = []
  importMissingLanguages.value = false
  try {
    if (!file.name.toLowerCase().endsWith('.mcmodel')) throw new Error('Only .mcmodel packages can be imported. XML and images are not supported.')
    if (file.size > MAX_PACKAGE_BYTES) throw new Error('The model package exceeds 20 MB.')
    const model = parseModelPackage(await file.text())
    languageStatuses.value = await inspectPackageLanguages(model)
    selectedPackage.value = model
  } catch (cause) {
    importError.value = cause instanceof Error ? cause.message : 'The file could not be checked.'
  } finally {
    input.value = ''
    operation.value = null
  }
}

const importModel = async () => {
  if (!canImport.value || !selectedPackage.value || !files) return
  operation.value = 'import'
  importError.value = ''
  try {
    const references = await installPackageLanguages(selectedPackage.value, importMissingLanguages.value)
    await files.importModel(selectedPackage.value, references)
    graph.value?.getPlugin<ConnectionHandler>('ConnectionHandler')?.reset()
    graph.value?.clearSelection()
    selectedPackage.value = null
    selectedFileName.value = ''
    languageStatuses.value = []
    importMissingLanguages.value = false
    importComplete.value = true
  } catch (cause) {
    importError.value = cause instanceof Error ? cause.message : 'Import failed.'
  } finally { operation.value = null }
}
</script>

<style scoped>
.sidebar-persistence { display: flex; flex-direction: column; height: 100%; min-height: 0; min-width: 0; overflow: hidden; }
.persistence-navigation { padding: 12px 10px 0; flex-shrink: 0; }
.mode-switch { display: flex; width: 100%; }
.mode-switch > .v-btn { flex: 1; min-width: 0; padding-inline: 8px; font-size: 11px; }
.persistence-content { display: flex; flex: 1; flex-direction: column; gap: 16px; min-height: 0; overflow-y: auto; padding: 16px 10px; scrollbar-width: thin; }
.field-group { display: flex; flex-direction: column; gap: 8px; }
.sidebar-description, .sidebar-hint, .inline-message, .replacement-note, .selected-file { margin: 0; line-height: 1.5; overflow-wrap: anywhere; }
.sidebar-description, .selected-file, .inline-message { font-size: 12px; }
.sidebar-hint, .replacement-note { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.65); }
.selected-file { font-weight: 600; }
.output-dimensions { margin: 0; font-size: 12px; font-weight: 600; font-variant-numeric: tabular-nums; }
.language-check { display: flex; flex-direction: column; gap: 10px; }
.language-summary { display: flex; align-items: flex-start; gap: 6px; font-size: 12px; line-height: 1.4; }
.language-summary .v-icon { flex-shrink: 0; margin-top: 1px; }
.language-summary--ready, .inline-message--success { color: rgb(var(--v-theme-success)); }
.language-summary--missing { color: rgb(var(--v-theme-warning)); }
.language-list { list-style: none; padding: 0; margin: 0; }
.language-list li { display: flex; flex-direction: column; gap: 2px; padding: 8px 0; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.1); }
.language-name { font-size: 12px; font-weight: 500; overflow-wrap: anywhere; }
.language-status { font-size: 11px; color: rgba(var(--v-theme-on-surface), 0.65); }
.language-status--missing { color: rgb(var(--v-theme-warning)); }
.inline-message--error { color: rgb(var(--v-theme-error)); }
.persistence-actions { display: flex; flex-direction: column; gap: 10px; flex-shrink: 0; padding: 12px 10px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1); background: rgb(var(--v-theme-surface)); }
.persistence-actions > .v-btn, .field-group > .v-btn { min-height: 36px; height: auto; padding-block: 8px; }
.replacement-note { border-left: 2px solid rgb(var(--v-theme-warning)); padding-left: 8px; }
.sidebar-persistence :deep(.v-label) { font-size: 12px; }
.sidebar-persistence :deep(.v-selection-control .v-label) { white-space: normal; opacity: 1; }
.sidebar-persistence :deep(.v-select__selection-text) { font-size: 12px; }
.sidebar-persistence :deep(.v-btn__content) { white-space: normal; }
.file-input { display: none; }
</style>
