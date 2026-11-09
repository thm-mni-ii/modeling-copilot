<template>
  <div v-if="run">
    <v-alert v-if="error" type="error" class="mb-3">{{ error }}</v-alert>
    <v-alert v-if="notice" type="info" class="mb-3" role="status">{{ notice }}</v-alert>
    <SubmissionLearnerPanel v-if="view === 'participant'" :run="run" :rows="rows" :busy="busy" :total="total" :page="page" @enroll="enroll" @submit="openSubmit" @page="changePage" />
    <SubmissionManagementPanel v-else :run="run" :rows="filtered" :busy="busy" :total="total" :page="page" :filter="filter" :history="history" :selected="selected" @configure="editRun" @filter="filter = $event" @history="changeHistory" @select="selected = $event" @release="prepareRelease" @page="changePage" />
    <v-dialog v-model="editDialog" max-width="760" :persistent="busy"
      ><v-card title="Run configuration"
        ><v-card-text
          ><SubmissionRunForm :data="runForm" :directory-run-id="run.id" /><v-alert v-if="dialogError" type="error">{{ dialogError }}</v-alert></v-card-text
        ><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="editDialog = false">Cancel</v-btn><v-btn color="primary" :loading="busy" :disabled="!runForm.name.trim()" @click="saveRun">Save run version</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="submitDialog" max-width="650" :persistent="busy"
      ><v-card title="Submit your model"
        ><v-card-text>
          <v-alert type="info" variant="tonal" class="mb-4">Your editable model stays separate. This submission cannot be replaced after reviewing starts.</v-alert>
          <v-btn-toggle v-model="source" mandatory class="mb-4"><v-btn value="saved">Saved model</v-btn><v-btn value="file">Upload .mcmodel</v-btn></v-btn-toggle>
          <template v-if="source === 'saved'">
            <v-autocomplete v-model="modelId" v-model:search="modelSearch" :items="models" item-title="name" item-value="id" label="My model" no-filter @update:model-value="chooseModel" />
            <v-select v-model="versionId" :items="versions" item-value="id" :item-title="(version) => version.releaseName || `Saved version ${version.versionNumber}`" label="Saved version to submit" />
          </template>
          <template v-else
            ><input type="file" accept=".mcmodel" aria-label="Model package" @change="chooseFile" />
            <p class="text-caption mt-2">Native model package including modeling languages · maximum 12 MB</p>
            <p v-if="upload">Model package checked.</p></template
          >
          <v-sheet v-if="source === 'saved' ? Boolean(versionId) : Boolean(upload)" class="pa-3 mt-3" rounded border>
            <p class="text-subtitle-2">You are submitting: {{ selectedModelName }}</p>
            <p v-if="selectedSavedAt" class="text-body-2">Saved on {{ new Date(selectedSavedAt).toLocaleString() }}</p>
            <p class="text-body-2 mt-2">This submits the selected copy. Later edits to your working model will not change it.</p>
            <p v-if="ownSubmission" class="text-body-2 mt-2">Your current submission will be replaced. Its earlier copy remains available.</p>
          </v-sheet>
          <v-alert v-if="dialogError" type="error" class="mt-3">{{ dialogError }}</v-alert> </v-card-text
        ><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="submitDialog = false">Cancel</v-btn><v-btn color="primary" :loading="busy" :disabled="source === 'saved' ? !versionId : !upload" @click="submitModel">Submit this model</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="releaseDialog" max-width="600" :persistent="busy"
      ><v-card title="Publish feedback"
        ><v-card-text
          >{{ releaseRequests.length }} review(s) ready to publish will become visible to the students. Draft reviews remain private.<v-alert v-if="dialogError" type="error" class="mt-3">{{ dialogError }}</v-alert></v-card-text
        ><v-card-actions><v-spacer /><v-btn :disabled="busy" @click="releaseDialog = false">Cancel</v-btn><v-btn color="primary" :disabled="!releaseRequests.length" :loading="busy" @click="release">Publish feedback</v-btn></v-card-actions></v-card
      ></v-dialog
    >
  </div>
  <v-container v-else
    ><v-progress-linear v-if="busy" indeterminate /><v-alert v-if="error" type="error">{{ error }}</v-alert></v-container
  >
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { submissions, submissionError } from '@/services/submissions'
import { type PublicationRequest, type RunData, type SubmissionRow, type SubmissionRun, type SubmissionView } from '@/services/api/types/submission'
import { useUserStore } from '@/stores/userStore'
import SubmissionRunForm from '@/components/submissions/SubmissionRunForm.vue'
import modelService from '@/services/model/model.service'
import type { Model, ModelVersionInfo } from '@/services/api/types/model'
import { parseModelPackage, type ModelPackage } from '@/utils/modelPackage'
import SubmissionLearnerPanel from './SubmissionLearnerPanel.vue'
import SubmissionManagementPanel from './SubmissionManagementPanel.vue'
const props = defineProps<{ runId: string; view: SubmissionView }>()
const emit = defineEmits<{ enrolled: [] }>()
const user = useUserStore()
const run = ref<SubmissionRun | null>(null)
const rows = ref<SubmissionRow[]>([])
const page = ref(1)
const total = ref(0)
const history = ref(props.view === 'participant')
const filter = ref('all')
const selected = ref<string[]>([])
const busy = ref(false)
const error = ref('')
const notice = ref('')
const dialogError = ref('')
const editDialog = ref(false)
const submitDialog = ref(false)
const releaseDialog = ref(false)
const releaseRequests = ref<PublicationRequest[]>([])
const runForm = ref<RunData>({ name: '', deadline: new Date().toISOString(), state: 'open', participation: 'all', participantIds: [], grants: [] })
const source = ref('saved')
const models = ref<Model[]>([])
const modelId = ref<string | null>(null)
const modelSearch = ref('')
const versionId = ref<string | null>(null)
const versions = ref<ModelVersionInfo[]>([])
const upload = ref<ModelPackage | null>(null)
const uploadName = ref('')
const selectedModelName = computed(() => (source.value === 'saved' ? models.value.find((model) => model.id === modelId.value)?.name ?? 'Selected model' : uploadName.value))
const selectedSavedAt = computed(() => (source.value === 'saved' ? versions.value.find((version) => version.id === versionId.value)?.createdAt : null))
const filtered = computed(() => rows.value.filter((row) => filter.value === 'all' || row.status === filter.value))
const ownSubmission = computed(() => rows.value.find((row) => row.ownerId === user.userId && row.current))
const loadRows = async () => {
  if (!run.value) return
  try {
    const result = (await submissions.listSubmissions(run.value.id, (page.value - 1) * 100, history.value, props.view)).data
    rows.value = result.items
    total.value = result.total
    selected.value = []
  } catch (cause) {
    error.value = submissionError(cause)
  }
}
const reloadList = () => {
  page.value = 1
  return loadRows()
}
const load = async () => {
  busy.value = true
  error.value = ''
  try {
    await user.ensureGlobalRole()
    run.value = (await submissions.run(props.runId, props.view)).data
    await loadRows()
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const editRun = () => {
  if (!run.value) return
  runForm.value = JSON.parse(JSON.stringify(run.value.data))
  dialogError.value = ''
  editDialog.value = true
}
const saveRun = async () => {
  if (!run.value) return
  busy.value = true
  dialogError.value = ''
  try {
    run.value = (await submissions.saveRun(run.value.id, { ...runForm.value, baseRevision: run.value.revision })).data
    editDialog.value = false
    await loadRows()
  } catch (cause) {
    dialogError.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const openSubmit = async () => {
  dialogError.value = ''
  upload.value = null
  uploadName.value = ''
  submitDialog.value = true
  try {
    models.value = (await modelService.list(0, 100, { q: modelSearch.value })).data.items.filter((m) => m.ownerId === user.userId)
  } catch (cause) {
    dialogError.value = submissionError(cause)
  }
}
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(modelSearch, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(async () => {
    if (submitDialog.value) {
      try {
        models.value = (await modelService.list(0, 100, { q: modelSearch.value })).data.items.filter((m) => m.ownerId === user.userId)
      } catch (cause) {
        dialogError.value = submissionError(cause)
      }
    }
  }, 250)
})
onBeforeUnmount(() => clearTimeout(searchTimer))
const chooseModel = async () => {
  versionId.value = null
  versions.value = []
  const model = models.value.find((m) => m.id === modelId.value)
  if (!model) return
  try {
    versions.value = (await modelService.listVersions(model, 0, 100)).data.items
    versionId.value = versions.value[0]?.id ?? null
  } catch (cause) {
    dialogError.value = submissionError(cause)
  }
}
const chooseFile = async (event: Event) => {
  upload.value = null
  uploadName.value = ''
  dialogError.value = ''
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  try {
    if (file.size > 12 * 1024 * 1024) throw new Error('Submission packages are limited to 12 MB.')
    upload.value = parseModelPackage(await file.text())
    uploadName.value =
      file.name
        .replace(/\.mcmodel$/i, '')
        .trim()
        .slice(0, 256) || 'Uploaded model'
  } catch (cause) {
    dialogError.value = submissionError(cause)
  }
}
const submitModel = async () => {
  if (!run.value) return
  busy.value = true
  dialogError.value = ''
  try {
    await submissions.submit(run.value.id, { ...(source.value === 'saved' ? { modelId: modelId.value!, versionId: versionId.value! } : { package: upload.value!, modelName: uploadName.value }), baseSubmissionId: ownSubmission.value?.id ?? null })
    submitDialog.value = false
    notice.value = 'Your model was submitted successfully. You can view the submitted copy below. Feedback will appear once published.'
    await loadRows()
  } catch (cause) {
    dialogError.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const prepareRelease = async (all: boolean) => {
  if (!run.value) return
  busy.value = true
  error.value = ''
  dialogError.value = ''
  try {
    const candidates = all ? ([] as SubmissionRow[]) : rows.value.filter((row) => selected.value.includes(row.id))
    if (all) {
      for (let skip = 0; ; skip += 100) {
        const result = (await submissions.listSubmissions(run.value.id, skip, false, props.view)).data
        candidates.push(...result.items)
        if (skip + 100 >= result.total) break
      }
    }
    releaseRequests.value = candidates.filter((row) => row.current && (user.globalRole === 'ADMIN' || row.ownerId !== user.userId)).flatMap((row) => row.reviews.filter((r) => r.status === 'complete').map((r) => ({ submissionId: row.id, reviewId: r.id, revision: r.revision })))
    releaseDialog.value = true
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const release = async () => {
  if (!run.value) return
  busy.value = true
  dialogError.value = ''
  try {
    let published = 0
    const failed: string[] = []
    for (let i = 0; i < releaseRequests.value.length; i += 100) {
      const result = (await submissions.publish(run.value.id, releaseRequests.value.slice(i, i + 100))).data
      for (const item of result.items) {
        if (item.published) published++
        else failed.push(item.message)
      }
    }
    notice.value = `${published} review(s) published.${failed.length ? ` ${failed.length} skipped: ${[...new Set(failed)].join(' ')}` : ''}`
    releaseDialog.value = false
    await loadRows()
  } catch (cause) {
    dialogError.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
const changePage = (value: number) => {
  page.value = value
  return loadRows()
}
const changeHistory = (value: boolean) => {
  history.value = value
  return reloadList()
}
const enroll = async () => {
  if (!run.value) return
  busy.value = true
  error.value = ''
  try {
    await submissions.enroll(run.value.id)
    await load()
    emit('enrolled')
  } catch (cause) {
    error.value = submissionError(cause)
  } finally {
    busy.value = false
  }
}
watch([() => props.runId, () => props.view], load, { immediate: true })
</script>
