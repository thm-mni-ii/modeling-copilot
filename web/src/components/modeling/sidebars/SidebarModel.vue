<template>
  <div class="model-sidebar">
    <div class="model-section versions-section">
      <div class="section-title">Releases</div>
      <v-btn size="small" variant="tonal" block prepend-icon="mdi-tag-plus-outline" @click="releaseDialog = true">Release version</v-btn>
      <div class="versions-scroll">
        <ModelSnapshotList :entries="releaseVersions" empty-text="No releases." :show-branch="false" @preview="previewRestore($event.id)" />
      </div>
    </div>
    <v-divider />
    <div class="model-section history-section">
      <div class="d-flex align-center"><span class="section-title mb-0">History</span><v-spacer /><v-btn :icon="historyOpen ? 'mdi-chevron-up' : 'mdi-chevron-down'" size="x-small" variant="text" @click="historyOpen = !historyOpen" /></div>
      <div v-if="historyOpen" class="history-scroll mt-2">
        <ModelSnapshotList :entries="history" empty-text="No saved versions." :show-branch="false" @preview="previewRestore($event.id)" />
      </div>
    </div>
    <v-alert v-if="error" density="compact" type="error" variant="tonal" class="ma-2">{{ error }}</v-alert>
    <v-dialog v-model="releaseDialog" max-width="520"
      ><v-card
        ><v-card-title>Release version</v-card-title><v-card-text><v-text-field v-model="releaseName" label="Release name" /><v-textarea v-model="description" label="Description (optional)" /></v-card-text
        ><v-card-actions><v-spacer /><v-btn @click="releaseDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!releaseName.trim()" @click="saveRelease">Release</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="restoreDialog" max-width="1000"
      ><v-card
        ><v-card-title>Preview historical save</v-card-title
        ><v-card-text
          ><ModelSnapshotPreview :data="restoreData" />
          <p class="text-body-2 text-medium-emphasis mt-3 mb-0">Restoring keeps this historical save unchanged. Its model content and language selection become the current state and are stored as a new save after the latest version.</p></v-card-text
        ><v-card-actions><v-btn @click="restoreDialog = false">Cancel</v-btn><v-spacer /><v-btn color="primary" :disabled="!restoreVersionId" @click="confirmRestore">Restore as new save</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useGraphContext } from '@/composables/useGraphContext'
import modelService from '@/services/model/model.service'
import { exportModelAsXml, importModelFromXml } from '@/utils/modelPersistence'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import ModelSnapshotPreview from '@/components/modeling/versions/ModelSnapshotPreview.vue'
import ModelSnapshotList from '@/components/modeling/versions/ModelSnapshotList.vue'
import type { JsonObject } from '@/services/api/types/common'
import type { ModelVersionInfo } from '@/services/api/types/model'

const workspace = useModelWorkspaceStore()
const { graph } = useGraphContext()
const releaseDialog = ref(false)
const releaseName = ref('')
const description = ref('')
const history = ref<ModelVersionInfo[]>([])
const historyOpen = ref(false)
const error = ref<string | null>(null)
const restoreDialog = ref(false)
const restoreVersionId = ref<string | null>(null)
const restoreData = ref<JsonObject | null>(null)
const snapshotName = computed(() => workspace.model?.name ?? workspace.data.name)
const releaseVersions = computed(() => history.value.filter((entry) => entry.kind === 'release'))
const capture = () => {
  if (graph.value) workspace.setData({ format: 'maxgraph-xml', version: 1, xml: exportModelAsXml(graph.value, false), name: snapshotName.value })
}
const loadHistory = async () => {
  if (workspace.model) history.value = (await modelService.listVersions(workspace.model.id, 0, 100)).data.items
}
const saveRelease = async () => {
  try {
    error.value = null
    capture()
    await workspace.save('release', releaseName.value, description.value)
    releaseDialog.value = false
    releaseName.value = ''
    description.value = ''
    await loadHistory()
  } catch {
    error.value = 'Unable to release this version.'
  }
}
const previewRestore = async (versionId: string) => {
  if (!workspace.model) return
  try {
    error.value = null
    const snapshot = (await modelService.getVersion(workspace.model.id, versionId)).data
    restoreVersionId.value = versionId
    restoreData.value = snapshot.data
    restoreDialog.value = true
  } catch {
    error.value = 'Unable to load this save preview.'
  }
}
const confirmRestore = async () => {
  if (!restoreVersionId.value) return
  try {
    error.value = null
    await workspace.restoreVersion(restoreVersionId.value)
    if (graph.value && typeof workspace.data.xml === 'string') importModelFromXml(graph.value, workspace.data.xml)
    await workspace.save()
    restoreDialog.value = false
    restoreVersionId.value = null
    await loadHistory()
  } catch {
    error.value = 'Unable to restore this version.'
  }
}
onMounted(() => void loadHistory())
watch(
  () => workspace.model?.id,
  () => void loadHistory()
)
</script>

<style scoped>
.model-sidebar {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  background: #fff;
}
.model-section {
  padding: 12px;
  flex-shrink: 0;
}
.field-label,
.section-title {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.78);
  margin-bottom: 7px;
}
.empty-state {
  font-size: 11px;
  color: rgba(var(--v-theme-on-surface), 0.55);
}
.versions-section,
.history-section {
  display: flex;
  flex-direction: column;
}
.history-scroll {
  min-height: 200px;
  max-height: 200px;
  overflow-y: auto;
}
.versions-scroll {
  margin-top: 10px;
  max-height: 152px;
  overflow-y: auto;
}
.history-scroll::-webkit-scrollbar,
.versions-scroll::-webkit-scrollbar,
.model-sidebar::-webkit-scrollbar {
  width: 5px;
}
</style>
