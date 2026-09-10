<template>
  <header class="modeling-header">
    <ModelingToolbarGroup title="Model" class="modeling-header__identity">
      <div class="modeling-header__identity-actions">
        <span class="modeling-header__name" :title="modelName">{{ modelName }}</span>
        <v-btn icon="mdi-pencil-outline" size="x-small" variant="text" aria-label="Change model name" @click="openRename" />
      </div>
    </ModelingToolbarGroup>

    <ModelingToolbarGroup title="Save" class="modeling-header__save-group">
      <v-btn-group size="small" density="compact" variant="outlined">
        <v-btn :icon="saveIcon" :color="saveColor" :loading="workspace.syncState === 'saving'" :title="`${stateLabel} — Save model`" @click="saveCheckpoint" />
        <v-btn icon="mdi-tag-plus-outline" color="medium-gray" title="Release version" @click="openRelease" />
        <slot name="save-tools" />
      </v-btn-group>
    </ModelingToolbarGroup>

    <div class="modeling-header__tools">
      <slot name="controls" />
    </div>
    <div class="modeling-header__spacer" />
    <div class="modeling-header__autonomy"><slot name="autonomy" /></div>
    <div class="modeling-header__sidebar-toggle"><slot name="sidebar-toggle" /></div>

    <v-alert v-if="saveError" density="compact" type="error" variant="tonal" class="modeling-header__error">{{ saveError }}</v-alert>

    <v-dialog v-model="renameDialog" max-width="460">
      <v-card>
        <v-card-title>Change model name</v-card-title>
        <v-card-text>
          <v-text-field v-model="editedName" label="Model name" autofocus @keyup.enter="saveName" />
          <v-alert v-if="renameError" density="compact" type="error" variant="tonal">{{ renameError }}</v-alert>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="renameDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!editedName.trim()" @click="saveName">Save</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="releaseDialog" max-width="520">
      <v-card>
        <v-card-title>Release version</v-card-title>
        <v-card-text>
          <v-text-field v-model="releaseName" label="Release name" autofocus @keyup.enter="saveRelease" />
          <v-textarea v-model="releaseDescription" label="Description (optional)" />
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="releaseDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!releaseName.trim()" @click="saveRelease">Release</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </header>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGraphContext } from '@/composables/useGraphContext'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { exportModelAsXml } from '@/utils/modelPersistence'
import ModelingToolbarGroup from './ModelingToolbarGroup.vue'

const workspace = useModelWorkspaceStore()
const { graph } = useGraphContext()
const modelName = computed(() => workspace.model?.name ?? workspace.data.name)
const renameDialog = ref(false)
const editedName = ref('')
const renameError = ref<string | null>(null)
const saveError = ref<string | null>(null)
const releaseDialog = ref(false)
const releaseName = ref('')
const releaseDescription = ref('')
const stateLabel = computed(() => ({ synced: 'Saved', dirty: 'Unsaved changes', saving: 'Saving...', offline: 'Offline - saved locally', conflict: 'Conflict' })[workspace.syncState])
const canSave = computed(() => workspace.dirty && workspace.syncState !== 'saving' && workspace.syncState !== 'conflict')
const saveColor = computed(() => ({ synced: 'success', dirty: 'warning', saving: 'primary', offline: 'warning', conflict: 'error' })[workspace.syncState])
const saveIcon = computed(() => (workspace.syncState === 'dirty' ? 'mdi-content-save-alert' : 'mdi-content-save-outline'))

const saveCheckpoint = async () => {
  if (!canSave.value) return
  try {
    saveError.value = null
    if (graph.value) {
      workspace.setData({
        format: 'maxgraph-xml',
        version: 1,
        xml: exportModelAsXml(graph.value, false),
        name: modelName.value
      })
    }
    await workspace.save()
  } catch {
    saveError.value = 'Unable to save this model.'
  }
}

const openRelease = () => {
  releaseName.value = ''
  releaseDescription.value = ''
  releaseDialog.value = true
}

const saveRelease = async () => {
  if (!releaseName.value.trim()) return
  try {
    saveError.value = null
    if (graph.value) {
      workspace.setData({
        format: 'maxgraph-xml',
        version: 1,
        xml: exportModelAsXml(graph.value, false),
        name: modelName.value
      })
    }
    await workspace.save('release', releaseName.value, releaseDescription.value)
    releaseDialog.value = false
  } catch {
    saveError.value = 'Unable to release this version.'
  }
}

const openRename = () => {
  editedName.value = modelName.value
  renameError.value = null
  renameDialog.value = true
}

const saveName = async () => {
  if (!editedName.value.trim() || !workspace.model) return
  try {
    renameError.value = null
    await workspace.rename(editedName.value)
    renameDialog.value = false
  } catch {
    renameError.value = 'Unable to change the model name.'
  }
}
</script>

<style scoped>
.modeling-header {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 48px;
  padding: 8px 12px;
  background: #ffffff;
  border: 1px solid rgba(var(--v-theme-outline), 0.14);
  border-radius: 4px;
  flex-wrap: wrap;
}

.modeling-header__identity {
  min-width: 150px;
  max-width: min(30vw, 320px);
}

.modeling-header__tools,
.modeling-header__sidebar-toggle,
.modeling-header__autonomy {
  display: flex;
  align-items: center;
}

.modeling-header__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.9);
}

.modeling-header__identity-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  min-width: 0;
}

.modeling-header__spacer { flex: 1; }

.modeling-header__error { width: 100%; }

@media (max-width: 900px) {
  .modeling-header__spacer { display: none; }
  .modeling-header__autonomy { margin-left: auto; }
}
</style>
