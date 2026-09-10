<template>
  <v-container class="py-8" max-width="1200">
    <div class="d-flex align-center mb-6 ga-3">
      <div>
        <h1 class="text-h4">My Models</h1>
        <p class="text-medium-emphasis mb-0">Models, checkpoints, and releases.</p>
      </div>
      <v-spacer /><v-btn color="primary" prepend-icon="mdi-plus" :loading="creating" @click="createModel">New Model</v-btn>
    </div>
    <v-tabs v-model="archiveTab" class="mb-3"><v-tab :value="false">My Models</v-tab><v-tab :value="true">Archive</v-tab></v-tabs>
    <v-text-field v-model="query" label="Search models" density="compact" prepend-inner-icon="mdi-magnify" clearable class="mb-3" @update:model-value="searchModels" />
    <v-alert v-if="error" type="error" class="mb-3">{{ error }}</v-alert>
    <v-data-table-server v-model:items-per-page="itemsPerPage" v-model:expanded="expanded" :headers="headers" :items="models" :items-length="total" :loading="loading" item-value="id" show-expand hover @click:row="toggleExpanded" @update:options="loadModels" @update:expanded="setExpanded">
      <template #[`item.updatedAt`]="{ item }">{{ formattedDate(asModel(item).updatedAt) }}</template>
      <template #[`item.actions`]="{ item }"
        ><v-btn size="small" color="primary" @click.stop="openModel(asModel(item).id)">Open</v-btn><v-btn size="small" variant="text" @click.stop="openRename(asModel(item))">Change name</v-btn><v-btn size="small" variant="text" @click.stop="setArchived(asModel(item), !archiveTab)">{{ archiveTab ? 'Restore' : 'Archive' }}</v-btn></template
      >
      <template #expanded-row="{ columns, item }"
        ><tr>
          <td :colspan="columns.length" class="pa-4">
            <v-tabs v-model="expandedTabs[asModel(item).id]" density="compact"><v-tab value="versions">Releases</v-tab><v-tab value="saves">All Saves</v-tab></v-tabs
            ><v-window v-model="expandedTabs[asModel(item).id]" class="pt-2"
              ><v-window-item value="versions"><ModelSnapshotList :entries="releaseVersions(asModel(item).id)" empty-text="No releases yet." @preview="openPreview(asModel(item), $event)" @branch="branch(asModel(item), $event)" /></v-window-item
              ><v-window-item value="saves"><ModelSnapshotList :entries="versions[asModel(item).id] ?? []" @preview="openPreview(asModel(item), $event)" @branch="branch(asModel(item), $event)" /></v-window-item
            ></v-window>
          </td></tr
      ></template>
    </v-data-table-server>

    <v-dialog v-model="renameDialog" max-width="520"
      ><v-card
        ><v-card-title>Change model name</v-card-title><v-card-text><v-text-field v-model="editedName" label="Model name" autofocus /></v-card-text><v-card-actions><v-spacer /><v-btn @click="renameDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!editedName.trim()" @click="saveName">Change name</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="previewDialog" max-width="1000"
      ><v-card
        ><v-card-title class="d-flex align-center">Preview · {{ previewTitle }}<v-spacer /><v-btn icon="mdi-chevron-left" :disabled="previewIndex <= 0" @click="movePreview(-1)" /><v-btn icon="mdi-chevron-right" :disabled="previewIndex >= previewEntries.length - 1" @click="movePreview(1)" /></v-card-title
        ><v-card-subtitle v-if="previewEntries[previewIndex]">{{ snapshotLabel(previewEntries[previewIndex]) }}</v-card-subtitle
        ><v-card-text><ModelSnapshotPreview :data="previewData" :height="600" /></v-card-text><v-card-actions><v-spacer /><v-btn @click="previewDialog = false">Close</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ModelSnapshotPreview from '@/components/modeling/versions/ModelSnapshotPreview.vue'
import ModelSnapshotList from '@/components/modeling/versions/ModelSnapshotList.vue'
import modelService from '@/services/model/model.service'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { JsonObject } from '@/services/api/types/common'
import type { Model, ModelSortField, ModelVersionInfo, SortOrder } from '@/services/api/types/model'

interface ModelTableOptions {
  page: number
  itemsPerPage: number
  sortBy: Array<{ key: ModelSortField; order: SortOrder }>
}

const router = useRouter()
const workspace = useModelWorkspaceStore()
const models = ref<Model[]>([])
const versions = ref<Record<string, ModelVersionInfo[]>>({})
const expandedTabs = ref<Record<string, 'versions' | 'saves'>>({})
const expanded = ref<string[]>([])
const total = ref(0)
const itemsPerPage = ref(10)
const page = ref(1)
const sortBy = ref<ModelTableOptions['sortBy']>([{ key: 'updatedAt', order: 'desc' }])
const query = ref('')
const archiveTab = ref(false)
const creating = ref(false)
const renameDialog = ref(false)
const selectedModel = ref<Model | null>(null)
const editedName = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const previewDialog = ref(false)
const previewData = ref<JsonObject | null>(null)
const previewEntries = ref<ModelVersionInfo[]>([])
const previewModel = ref<Model | null>(null)
const previewIndex = ref(0)
const headers = [
  { title: 'Model', key: 'name', sortable: true },
  { title: 'Last updated', key: 'updatedAt', sortable: true },
  { title: 'Actions', key: 'actions', sortable: false }
]
const formattedDate = (value: string) => new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
const asModel = (item: Model | { raw: Model }) => ('raw' in item ? item.raw : item)
const previewTitle = computed(() => previewModel.value?.name ?? '')
const releaseVersions = (modelId: string) => (versions.value[modelId] ?? []).filter((entry) => entry.kind === 'release')

const loadModels = async (options?: ModelTableOptions) => {
  if (options) {
    page.value = options.page
    itemsPerPage.value = options.itemsPerPage
    sortBy.value = options.sortBy.length ? options.sortBy : [{ key: 'updatedAt', order: 'desc' }]
  }
  const limit = itemsPerPage.value === -1 ? 100 : itemsPerPage.value
  loading.value = true
  error.value = null
  try {
    const sort = sortBy.value[0]
    const result = await modelService.list((page.value - 1) * limit, limit, { q: query.value || undefined, archived: archiveTab.value, sort: sort.key, order: sort.order })
    models.value = result.data.items
    total.value = result.data.total
  } catch {
    error.value = 'Models could not be loaded.'
  } finally {
    loading.value = false
  }
}
let searchTimer: ReturnType<typeof setTimeout> | undefined
const searchModels = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void loadModels({ page: 1, itemsPerPage: itemsPerPage.value, sortBy: sortBy.value }), 250)
}
const loadVersions = async (modelId: string) => {
  if (versions.value[modelId]) return
  versions.value[modelId] = (await modelService.listVersions(modelId, 0, 100)).data.items
  expandedTabs.value[modelId] = 'versions'
}
const expandedId = (entry: unknown) => (typeof entry === 'string' ? entry : (entry as { value?: string }).value)
const setExpanded = (entries: unknown[]) => {
  const id = expandedId(entries[entries.length - 1])
  expanded.value = id ? [id] : []
  if (id) void loadVersions(id)
}
const toggleExpanded = (_event: MouseEvent, { item }: { item: Model }) => {
  const id = item.id
  setExpanded(expanded.value[0] === id ? [] : [id])
}
const createModel = async () => {
  creating.value = true
  error.value = null
  try {
    await workspace.startNew('Untitled model', [])
    await workspace.save()
    await router.push(`/modeling/${workspace.model!.id}`)
  } catch {
    error.value = 'The initial model save could not be created.'
  } finally {
    creating.value = false
  }
}
const openModel = (id: string) => router.push(`/modeling/${id}`)
const setArchived = async (item: Model, archived: boolean) => {
  try {
    error.value = null
    await modelService.update(item.id, { archived })
    expanded.value = []
    await loadModels()
  } catch {
    error.value = archived ? 'The model could not be archived.' : 'The model could not be restored.'
  }
}
const openRename = (model: Model) => {
  selectedModel.value = model
  editedName.value = model.name
  renameDialog.value = true
}
const saveName = async () => {
  if (!selectedModel.value) return
  try {
    error.value = null
    await modelService.update(selectedModel.value.id, { name: editedName.value.trim() })
    renameDialog.value = false
    await loadModels()
  } catch {
    error.value = 'The model name could not be changed.'
  }
}
const openPreview = async (model: Model, entry: ModelVersionInfo) => {
  previewModel.value = model
  previewEntries.value = versions.value[model.id] ?? []
  previewIndex.value = previewEntries.value.findIndex((item) => item.id === entry.id)
  previewDialog.value = true
  await loadPreview()
}
const loadPreview = async () => {
  const entry = previewEntries.value[previewIndex.value]
  if (!entry || !previewModel.value) return
  previewData.value = (await modelService.getVersion(previewModel.value.id, entry.id)).data.data
}
const movePreview = async (change: number) => {
  previewIndex.value += change
  await loadPreview()
}
const branch = async (model: Model, entry: ModelVersionInfo) => {
  try {
    await workspace.branchVersion(model.id, entry.id, `${model.name} – ${snapshotLabel(entry)}`)
    await workspace.save()
    await router.push(`/modeling/${workspace.model!.id}`)
  } catch {
    error.value = 'The save could not be continued as a new model.'
  }
}
const snapshotLabel = (entry: ModelVersionInfo) => (entry.kind === 'release' && entry.releaseName ? `${entry.releaseName} · v${entry.versionNumber}` : `v${entry.versionNumber}`)
watch(archiveTab, () => void loadModels({ page: 1, itemsPerPage: itemsPerPage.value, sortBy: sortBy.value }))
onMounted(() => {
  void loadModels()
})
</script>
