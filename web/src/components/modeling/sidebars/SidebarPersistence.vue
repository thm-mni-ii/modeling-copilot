<template>
  <div class="sidebar-persistence">
    <div class="sidebar-section">
      <SidebarPanelHeader v-if="showHeader" title="Import / Export" />

      <div class="sidebar-section-body">
        <p class="sidebar-description">Export the current model as XML or load an XML file into the editor.</p>

        <div class="sidebar-action-buttons">
          <v-btn color="primary" variant="flat" size="small" prepend-icon="mdi-download" @click="openDialog('download')"> Download </v-btn>
          <v-btn color="secondary" variant="tonal" size="small" prepend-icon="mdi-upload" @click="openDialog('upload')"> Upload </v-btn>
        </div>

        <p v-if="!graph" class="sidebar-hint">A graph must be available for export or import.</p>
      </div>
    </div>

    <v-dialog v-model="isDialogOpen" max-width="520px" persistent>
      <v-card>
        <v-card-title class="text-h6">
          {{ dialogMode === 'download' ? 'Download Model' : 'Upload Model' }}
        </v-card-title>

        <v-card-text class="sidebar-dialog-body">
          <template v-if="dialogMode === 'download'">
            <p class="sidebar-description">Download the current model in the native maxGraph XML format.</p>
          </template>

          <template v-else>
            <p class="sidebar-description">Select a previously exported XML model file.</p>

            <input ref="fileInput" class="file-input" type="file" accept=".xml,application/xml,text/xml" @change="onFileSelected" />

            <div class="sidebar-action-buttons">
              <v-btn variant="tonal" size="small" prepend-icon="mdi-folder-open" @click="chooseFile"> Select File </v-btn>
              <span class="selected-file" :class="{ 'selected-file--empty': !selectedFileName }">
                {{ selectedFileName || 'No file selected yet' }}
              </span>
            </div>

            <p v-if="selectedFileName" class="sidebar-hint">Format: XML</p>
          </template>

          <p v-if="errorMessage" class="sidebar-error">{{ errorMessage }}</p>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="closeDialog">Cancel</v-btn>
          <v-btn v-if="dialogMode === 'download'" color="primary" :disabled="!graph" @click="downloadModel"> Download </v-btn>
          <v-btn v-else color="primary" :disabled="!graph || !selectedFile" @click="importModel"> Upload </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { exportModelAsXml, importModelFromXml, saveTextFile } from '@/utils/modelPersistence'
import { useGraphContext } from '@/composables/useGraphContext'
import SidebarPanelHeader from './SidebarPanelHeader.vue'

type DialogMode = 'download' | 'upload'

withDefaults(defineProps<{ showHeader?: boolean }>(), { showHeader: true })

const { graph } = useGraphContext()

const isDialogOpen = ref(false)
const dialogMode = ref<DialogMode>('download')
const selectedFile = ref<File | null>(null)
const selectedFileName = ref('')
const errorMessage = ref('')
const fileInput = ref<HTMLInputElement | null>(null)

const openDialog = (mode: DialogMode) => {
  dialogMode.value = mode
  errorMessage.value = ''
  selectedFile.value = null
  selectedFileName.value = ''
  if (fileInput.value) {
    fileInput.value.value = ''
  }
  isDialogOpen.value = true
}

const closeDialog = () => {
  isDialogOpen.value = false
}

const chooseFile = () => {
  if (fileInput.value) {
    fileInput.value.value = ''
  }
  fileInput.value?.click()
}

const downloadModel = () => {
  const currentGraph = graph.value
  if (!currentGraph) {
    errorMessage.value = 'No graph available.'
    return
  }

  try {
    saveTextFile(exportModelAsXml(currentGraph), 'model.xml', 'application/xml')
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Export failed.'
  }
}

const onFileSelected = async (event: Event) => {
  const target = event.target as HTMLInputElement | null
  const file = target?.files?.[0] ?? null

  if (!file) {
    return
  }

  selectedFile.value = file
  selectedFileName.value = file.name
  errorMessage.value = ''
}

const importModel = async () => {
  const currentGraph = graph.value
  const file = selectedFile.value

  if (!currentGraph || !file) {
    errorMessage.value = 'Select a file first.'
    return
  }

  try {
    const text = await file.text()
    importModelFromXml(currentGraph, text)

    // Nach dem Import: Handler-Zustände zurücksetzen und View neu aufbauen,
    // damit keine veralteten MouseMove-States oder CellStates verbleiben.
    const connectionHandler = currentGraph.getPlugin('ConnectionHandler') as { reset?: () => void } | null
    connectionHandler?.reset?.()
    currentGraph.clearSelection()
    currentGraph.refresh()
    currentGraph.view.validate()

    closeDialog()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Import failed.'
  }
}
</script>

<style scoped>
.sidebar-persistence {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-width: 0;
  overflow: hidden;
  background: #ffffff;
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.sidebar-section-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
}

.sidebar-description {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(var(--v-theme-on-surface), 0.78);
}

.sidebar-hint {
  margin: 0;
  font-size: 11px;
  line-height: 1.4;
  color: rgba(var(--v-theme-on-surface), 0.56);
}

.sidebar-error {
  margin: 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(var(--v-theme-error), 0.08);
  color: rgba(var(--v-theme-error), 0.95);
  font-size: 12px;
}

.sidebar-action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.format-toggle {
  width: fit-content;
}

.selected-file {
  font-size: 12px;
  color: rgba(var(--v-theme-on-surface), 0.7);
  word-break: break-word;
}

.selected-file--empty {
  color: rgba(var(--v-theme-on-surface), 0.45);
}

.file-input {
  display: none;
}

.sidebar-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
