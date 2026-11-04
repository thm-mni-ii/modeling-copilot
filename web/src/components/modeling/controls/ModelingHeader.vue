<template>
  <header class="modeling-header">
    <div class="modeling-header__main">
      <ModelingToolbarGroup title="Model" class="modeling-header__identity">
        <div class="modeling-header__identity-actions">
          <span class="modeling-header__name" :title="modelName">{{ modelName }}</span>
          <v-btn icon="mdi-pencil-outline" size="x-small" variant="text" aria-label="Change model name" @click="openRename" />
        </div>
      </ModelingToolbarGroup>

      <ModelingToolbarGroup title="Save" class="modeling-header__save-group">
        <v-btn-group size="small" density="compact" variant="outlined">
          <v-btn :icon="saveIcon" :color="saveColor" :loading="workspace.saving" :title="`${stateLabel} — Save model`" @click="saveCheckpoint" />
          <v-menu v-model="releaseMenu" :close-on-content-click="false" location="bottom start" :offset="8">
            <template #activator="{ props }">
              <v-btn v-bind="props" icon="mdi-tag-plus-outline" color="medium-gray" :disabled="!workspace.canRelease" :title="workspace.canRelease ? 'Release version' : 'Change the model before creating another release'" aria-label="Release version" @click="releaseName = ''" />
            </template>
            <v-card class="modeling-release" width="320" rounded="lg">
              <v-text-field v-model="releaseName" label="Release name (optional)" placeholder="Automatic release number" variant="outlined" density="compact" autofocus maxlength="256" hide-details :disabled="workspace.saving" @keydown.enter.prevent="saveRelease">
                <template #append-inner>
                  <v-btn icon="mdi-check" color="primary" size="small" variant="text" :loading="workspace.saving" :disabled="!workspace.canRelease" title="Create release" aria-label="Create release" @click="saveRelease" />
                </template>
              </v-text-field>
              <p class="text-caption text-medium-emphasis mt-2 mb-0">Enter or ✓ to release. Leave empty for V1, V2, …</p>
            </v-card>
          </v-menu>
          <v-btn icon="mdi-timeline-clock-outline" :color="workspace.pendingPatches.length ? 'warning' : 'medium-gray'" :disabled="!workspace.model" title="Version timeline" aria-label="Open version timeline" @click="timelineDialog = true" />
          <slot name="save-tools" />
        </v-btn-group>
      </ModelingToolbarGroup>

      <div class="modeling-header__tools">
        <slot name="controls" />
      </div>
    </div>
    <div class="modeling-header__right">
      <slot name="autonomy" />
      <slot name="sidebar-toggle" />
    </div>

    <v-dialog v-model="renameDialog" max-width="460">
      <v-card>
        <v-card-title>Change model name</v-card-title>
        <v-card-text>
          <v-text-field v-model="editedName" label="Model name" autofocus @keyup.enter="saveName" />
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="renameDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!editedName.trim()" @click="saveName">Save</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <ModelTimelineDialog v-model="timelineDialog" />
  </header>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useGraphContext } from '@/composables/useGraphContext'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { exportModelAsXml } from '@/utils/modelPersistence'
import ModelTimelineDialog from '@/components/modeling/versions/ModelTimelineDialog.vue'
import ModelingToolbarGroup from './ModelingToolbarGroup.vue'
import { notifyError } from '@/composables/useNotifications'

const workspace = useModelWorkspaceStore()
const { graph } = useGraphContext()
const modelName = computed(() => workspace.model?.name ?? workspace.data.name)
const renameDialog = ref(false)
const editedName = ref('')
const releaseMenu = ref(false)
const releaseName = ref('')
const timelineDialog = ref(false)
const effectiveSyncState = computed(() => workspace.syncState === 'synced' && workspace.taskEditDirty ? workspace.taskEditSyncState : workspace.syncState)
const stateLabel = computed(() => ({ synced: 'Saved', dirty: 'Unsaved changes', saving: 'Saving...', offline: 'Offline - saved locally', conflict: 'Conflict' })[effectiveSyncState.value])
const canSave = computed(() => (workspace.dirty || workspace.taskEditDirty) && !workspace.saving && workspace.syncState !== 'conflict')
const saveColor = computed(() => ({ synced: 'success', dirty: 'warning', saving: 'primary', offline: 'warning', conflict: 'error' })[effectiveSyncState.value])
const saveIcon = computed(() => (effectiveSyncState.value === 'dirty' ? 'mdi-content-save-alert' : 'mdi-content-save-outline'))

const saveCheckpoint = async () => {
  if (!canSave.value) return
  try {
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
    notifyError(workspace.taskEditError ?? 'Unable to save this model.')
  }
}

watch(() => workspace.model?.id, () => {
  releaseMenu.value = false
  releaseName.value = ''
})

const saveRelease = async () => {
  if (!workspace.canRelease) return
  try {
    if (graph.value) {
      workspace.setData({
        format: 'maxgraph-xml',
        version: 1,
        xml: exportModelAsXml(graph.value, false),
        name: modelName.value
      })
    }
    await workspace.release(releaseName.value)
    releaseMenu.value = false
  } catch {
    notifyError('Unable to release this version.')
  }
}

const openRename = () => {
  editedName.value = modelName.value
  renameDialog.value = true
}

const saveName = async () => {
  if (!editedName.value.trim() || !workspace.model) return
  try {
    await workspace.rename(editedName.value)
    renameDialog.value = false
  } catch {
    notifyError('Unable to change the model name.')
  }
}
</script>

<style scoped>
.modeling-header {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  min-height: 48px;
  padding: 4px 12px;
  background: #ffffff;
  border: 1px solid rgba(var(--v-theme-outline), 0.14);
  border-radius: 4px;
  flex-wrap: wrap;
}

.modeling-release {
  padding: 12px;
  border-top: 3px solid rgb(var(--v-theme-primary));
}

.modeling-header__main {
  display: contents;
}

.modeling-header__right {
  display: flex;
  align-items: center;
  align-self: flex-end;
  flex: 0 0 auto;
  flex-wrap: nowrap;
  gap: 8px;
  margin-left: auto;
  order: 99;
}

.modeling-header__right :deep(.canvas-mode-controls) {
  order: 0;
  margin-left: 0;
}

.modeling-header__right :deep(.v-btn-group) {
  height: 32px;
  border-radius: 4px;
}

.modeling-header__right :deep(.v-btn-group .v-btn) {
  min-width: 28px;
  width: 28px;
  height: 28px;
}

.modeling-header__right :deep(.v-btn-group .v-icon) {
  font-size: 20px;
}

.modeling-header__identity {
  min-width: 150px;
  max-width: min(30vw, 240px);
}

.modeling-header__identity :deep(.modeling-toolbar-group__content) {
  width: 100%;
}

.modeling-header__tools,
.modeling-header__tools :deep(.canvas-toolbar) {
  display: contents;
}

.modeling-header__name {
  flex: 1;
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
  width: 100%;
}

.modeling-header__identity-actions > .v-btn {
  flex-shrink: 0;
}
</style>
