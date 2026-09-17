<template>
  <v-container class="py-8" max-width="1200">
    <div class="d-flex align-center mb-6 ga-3">
      <div>
        <h1 class="text-h4">Diagram Languages</h1>
        <p class="text-medium-emphasis mb-0">Languages, checkpoints, and releases.</p>
      </div>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-plus" @click="createNewLanguage">New Language</v-btn>
    </div>

    <v-tabs v-model="archiveTab" class="mb-3"><v-tab :value="false">Languages</v-tab><v-tab :value="true">Archive</v-tab></v-tabs>
    <v-text-field v-model="query" label="Search languages" density="compact" prepend-inner-icon="mdi-magnify" clearable class="mb-3" @update:model-value="searchLanguages" />
    <v-data-table-server v-model:items-per-page="itemsPerPage" v-model:expanded="expanded" :headers="headers" :items="languages" :items-length="totalLanguages" :loading="loading" item-value="id" show-expand hover no-data-text="No diagram languages available" loading-text="Loading diagram languages..." @click:row="toggleExpanded" @update:expanded="setExpanded" @update:options="loadLanguages">
      <template #[`item.name`]="{ item }">
        <div class="font-weight-medium">{{ asLanguage(item).name }}</div>
      </template>

      <template #[`item.ownerId`]="{ item }">{{ asLanguage(item).ownerId || 'System' }}</template>

      <template #[`item.latestSave`]="{ item }">
        <div v-if="asLanguage(item).versionNumber !== null">
          <div class="font-weight-medium">{{ asLanguage(item).latestReleaseName || `v${asLanguage(item).versionNumber}` }}</div>
          <div v-if="asLanguage(item).latestReleaseName" class="text-caption text-medium-emphasis">v{{ asLanguage(item).versionNumber }}</div>
        </div>
        <span v-else class="text-medium-emphasis">No saves</span>
      </template>

      <template #[`item.actions`]="{ item }">
        <div class="d-flex justify-end ga-1">
          <v-btn v-if="asLanguage(item).latestVersionId" size="small" color="primary" @click.stop="openInEditor(asLanguage(item))">Open</v-btn>
          <v-btn v-else size="small" color="primary" variant="tonal" @click.stop="createInitialVersion(asLanguage(item))">Create first save</v-btn>
          <v-btn v-if="asLanguage(item).latestVersionId" size="small" variant="text" prepend-icon="mdi-play" @click.stop="tryLanguage(asLanguage(item))">Try</v-btn>
          <v-menu>
            <template #activator="{ props }">
              <v-btn icon="mdi-dots-vertical" size="small" variant="text" v-bind="props" @click.stop />
            </template>
            <v-list density="compact">
              <v-list-item prepend-icon="mdi-pencil" title="Change details" @click="editLanguage(asLanguage(item))" />
              <v-list-item :prepend-icon="archiveTab ? 'mdi-archive-arrow-up-outline' : 'mdi-archive-outline'" :title="archiveTab ? 'Restore' : 'Archive'" @click="setArchived(asLanguage(item), !archiveTab)" />
            </v-list>
          </v-menu>
        </div>
      </template>

      <template #expanded-row="{ columns, item }">
        <tr>
          <td :colspan="columns.length" class="pa-4">
            <v-tabs v-model="expandedTabs[asLanguage(item).id]" density="compact">
              <v-tab value="versions">Releases</v-tab>
              <v-tab value="saves">All Saves</v-tab>
            </v-tabs>
            <v-window v-model="expandedTabs[asLanguage(item).id]" class="pt-2">
              <v-window-item value="versions">
                <LanguageVersionList :entries="releaseVersions(asLanguage(item).id)" :current-version-id="asLanguage(item).latestVersionId" :disable-current-action="false" action-label="Open" show-try show-fork empty-text="No releases yet." @restore="openVersion(asLanguage(item), $event)" @try="tryVersion(asLanguage(item), $event)" @fork="forkVersion(asLanguage(item), $event)" />
              </v-window-item>
              <v-window-item value="saves">
                <LanguageVersionList :entries="versions[asLanguage(item).id] ?? []" :current-version-id="asLanguage(item).latestVersionId" :disable-current-action="false" action-label="Open" show-try show-fork @restore="openVersion(asLanguage(item), $event)" @try="tryVersion(asLanguage(item), $event)" @fork="forkVersion(asLanguage(item), $event)" />
              </v-window-item>
            </v-window>
          </td>
        </tr>
      </template>
    </v-data-table-server>

    <DialogLanguageEditor v-model="showLanguageDialog" :language="selectedLanguage" @create="createLanguage" @update="updateLanguage" />
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import DialogLanguageEditor from '@/components/dialog/DialogLanguageEditor.vue'
import LanguageVersionList from '@/components/modeling/versions/LanguageVersionList.vue'
import { createEmptyDiagramLanguage } from '@/model/DiagramLanguage'
import languageService from '@/services/language/language.service'
import type { ApiId } from '@/services/api/types/common'
import type { CreateLanguage, LanguageOverview, LanguageVersionInfo, UpdateLanguage } from '@/services/api/types/language'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { notifyError } from '@/composables/useNotifications'

interface TableOptions {
  page: number
  itemsPerPage: number
}

const router = useRouter()
const workspace = useModelWorkspaceStore()
const languages = ref<LanguageOverview[]>([])
const versions = ref<Record<string, LanguageVersionInfo[]>>({})
const expandedTabs = ref<Record<string, 'versions' | 'saves'>>({})
const expanded = ref<string[]>([])
const totalLanguages = ref(0)
const itemsPerPage = ref(10)
const currentPage = ref(1)
const archiveTab = ref(false)
const query = ref('')
const loading = ref(false)
const showLanguageDialog = ref(false)
const selectedLanguage = ref<LanguageOverview | null>(null)

const headers = [
  { title: 'Language', key: 'name', sortable: true },
  { title: 'Owner', key: 'ownerId', sortable: true },
  { title: 'Latest save', key: 'latestSave', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false, align: 'end' as const }
]

const asLanguage = (item: LanguageOverview | { raw: LanguageOverview }) => ('raw' in item ? item.raw : item)
const versionLabel = (entry: LanguageVersionInfo) => (entry.kind === 'release' && entry.releaseName ? `${entry.releaseName} · v${entry.versionNumber}` : `v${entry.versionNumber}`)
const releaseVersions = (languageId: ApiId) => (versions.value[languageId] ?? []).filter((entry) => entry.kind === 'release')

const loadLanguages = async (options?: TableOptions) => {
  if (options) {
    currentPage.value = options.page
    itemsPerPage.value = options.itemsPerPage
  }
  const limit = itemsPerPage.value === -1 ? 100 : itemsPerPage.value
  loading.value = true
  try {
    const response = await languageService.list((currentPage.value - 1) * limit, limit, { q: query.value || undefined, archived: archiveTab.value })
    languages.value = response.data.items
    totalLanguages.value = response.data.total
  } catch {
    notifyError('Diagram languages could not be loaded.')
  } finally {
    loading.value = false
  }
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
const searchLanguages = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void loadLanguages({ page: 1, itemsPerPage: itemsPerPage.value }), 250)
}

const loadVersions = async (languageId: ApiId, force = false) => {
  if (!force && versions.value[languageId]) return
  try {
    versions.value[languageId] = (await languageService.listVersions(languageId, 0, 100)).data.items
    expandedTabs.value[languageId] ??= 'versions'
  } catch {
    notifyError('The version history could not be loaded.')
  }
}

const expandedId = (entry: unknown) => (typeof entry === 'string' ? entry : (entry as { value?: string }).value)
const setExpanded = (entries: unknown[]) => {
  const id = expandedId(entries[entries.length - 1])
  expanded.value = id ? [id] : []
  if (id) void loadVersions(id)
}
const toggleExpanded = (_event: MouseEvent, { item }: { item: LanguageOverview }) => setExpanded(expanded.value[0] === item.id ? [] : [item.id])

const createNewLanguage = () => {
  selectedLanguage.value = null
  showLanguageDialog.value = true
}
const editLanguage = (language: LanguageOverview) => {
  selectedLanguage.value = language
  showLanguageDialog.value = true
}
const openInEditor = (language: Pick<LanguageOverview, 'id'>) => router.push(`/diagramLanguageEditor/${language.id}`)
const openVersion = (language: LanguageOverview, version: LanguageVersionInfo) => router.push({ name: 'DiagramLanguageEditor', params: { id: language.id }, query: version.id === language.latestVersionId ? {} : { restore: version.id } })

const tryVersion = async (language: Pick<LanguageOverview, 'id' | 'name'>, version: Pick<LanguageVersionInfo, 'id'>) => {
  try {
    await workspace.startNew(`Test: ${language.name}`, [{ languageId: language.id, versionId: version.id, source: 'additional' }])
    await router.push({ name: 'Modeling' })
  } catch {
    notifyError('The language version could not be opened for testing.')
  }
}
const tryLanguage = async (language: LanguageOverview) => {
  if (!language.latestVersionId) return
  await tryVersion(language, { id: language.latestVersionId })
}

const forkVersion = async (language: LanguageOverview, version: LanguageVersionInfo) => {
  try {
    const fork = (
      await languageService.create({
        name: `${language.name} – ${versionLabel(version)}`,
        parent: { languageId: language.id, versionId: version.id }
      })
    ).data
    await router.push(`/diagramLanguageEditor/${fork.id}`)
  } catch {
    notifyError('The language version could not be used as a new language.')
  }
}

const createInitialVersion = async (language: LanguageOverview) => {
  try {
    await languageService.createVersion(language.id, {
      baseVersionId: null,
      kind: 'release',
      releaseName: 'Initial release',
      includedLanguageVersions: [],
      data: createEmptyDiagramLanguage()
    })
    await router.push(`/diagramLanguageEditor/${language.id}`)
  } catch {
    notifyError('The first language save could not be created.')
  }
}

const createLanguage = async (data: CreateLanguage) => {
  try {
    const language = (await languageService.create(data)).data
    if (!language.latestVersionId) {
      await languageService.createVersion(language.id, {
        baseVersionId: null,
        kind: 'release',
        releaseName: 'Initial release',
        includedLanguageVersions: [],
        data: createEmptyDiagramLanguage()
      })
    }
    await router.push(`/diagramLanguageEditor/${language.id}`)
  } catch {
    notifyError('The language could not be created.')
  }
}

const updateLanguage = async (languageId: ApiId, data: UpdateLanguage) => {
  try {
    await languageService.update(languageId, data)
    await loadLanguages({ page: 1, itemsPerPage: itemsPerPage.value })
  } catch {
    notifyError('The language details could not be changed.')
  }
}

const setArchived = async (language: LanguageOverview, archived: boolean) => {
  try {
    await languageService.update(language.id, { archived })
    expanded.value = []
    await loadLanguages({ page: 1, itemsPerPage: itemsPerPage.value })
  } catch {
    notifyError(archived ? 'The language could not be archived.' : 'The language could not be restored.')
  }
}

watch(archiveTab, () => {
  expanded.value = []
  void loadLanguages({ page: 1, itemsPerPage: itemsPerPage.value })
})
</script>
