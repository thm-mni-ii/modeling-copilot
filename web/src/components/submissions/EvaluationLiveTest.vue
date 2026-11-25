<template>
  <section class="live-test" aria-label="Live workflow test">
    <header class="live-toolbar">
      <div class="live-title"><h2 class="text-subtitle-1 font-weight-bold" tabindex="-1" data-workspace-heading>Live test</h2><p class="text-caption text-medium-emphasis mb-0">Edit your own test model and evaluate each saved change.</p></div>
      <v-select :model-value="modelId" :items="models" item-title="name" item-value="id" label="Test model" density="compact" hide-details class="model-select" :disabled="busy" @update:model-value="openModel" />
      <v-btn variant="tonal" prepend-icon="mdi-plus" :disabled="busy" @click="createModel">New model</v-btn>
      <v-btn variant="text" :disabled="!modelId || !editor?.ready || busy" @click="parametersOpen = true">Parameters</v-btn>
      <v-btn color="primary" prepend-icon="mdi-play" :disabled="!modelId || !editor?.ready || busy" :loading="busy" @click="evaluate()">Evaluate model</v-btn>
    </header>
    <v-alert v-if="error" type="error" variant="tonal" density="compact" class="ma-3">{{ error }}</v-alert>
    <ViewModeling v-if="modelId" :key="modelId" ref="editor" :model-id="modelId" evaluation-lab class="live-editor" style="height: 0" />
    <div v-else class="live-empty pa-6"><v-icon icon="mdi-pencil-ruler" size="40" /><h3 class="text-h6 mt-3">Try a model of your own</h3><p class="text-body-2 text-medium-emphasis mt-2 mb-4">Create a test model for this release, add or rename elements, then evaluate it as often as needed.</p><v-btn color="primary" :loading="busy" @click="createModel">Create test model</v-btn></div>
    <DialogEvaluationParameters v-model="parametersOpen" :busy="busy" @confirm="evaluate" />
  </section>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import ViewModeling from '@/views/ViewModeling.vue'
import DialogEvaluationParameters from '@/components/dialog/DialogEvaluationParameters.vue'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import modelService from '@/services/model/model.service'
import taskService from '@/services/task/task.service'
import type { Model } from '@/services/api/types/model'
import type { EvaluationParameters } from '@/services/api/types/evaluation'

const props = defineProps<{ taskId: string; releaseId: string; taskName: string }>()
const workspace = useModelWorkspaceStore()
const editor = ref<InstanceType<typeof ViewModeling>>()
const models = ref<Model[]>([])
const modelId = ref<string | null>(null)
const busy = ref(false)
const error = ref('')
const parametersOpen = ref(false)
let loadToken = 0
const message = (cause: unknown) => (cause as { response?: { data?: { message?: string } }; message?: string }).response?.data?.message ?? (cause as Error).message ?? 'The action could not be completed.'
const saveChanges = async () => {
  if (busy.value) throw new Error('Wait until the live test has finished loading or saving.')
  await editor.value?.saveChanges()
}
const openModel = async (id: string) => {
  if (id === modelId.value) return
  try { await saveChanges(); modelId.value = id; error.value = '' }
  catch (cause) { error.value = message(cause) }
}
const createModel = async () => {
  const previousId = modelId.value
  try {
    await saveChanges()
    busy.value = true
    error.value = ''
    const release = (await taskService.getVersion(props.taskId, props.releaseId)).data
    modelId.value = null
    await nextTick()
    await workspace.startNew(`Live test / ${props.taskName.slice(0, 160)} / ${new Date().toLocaleString()}`, release.workspaceLanguages, { taskId: props.taskId, versionId: props.releaseId })
    await workspace.updatePreferences({ ...workspace.preferences, evaluationLab: true })
    await workspace.save('checkpoint')
    const created = workspace.model!
    // Keep the saved model reachable even if tagging it fails.
    models.value = [created, ...models.value]
    modelId.value = created.id
  } catch (cause) { error.value = message(cause); modelId.value ??= previousId }
  finally { busy.value = false }
}
const evaluate = async (parameters: EvaluationParameters = {}) => {
  if (busy.value || !editor.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await editor.value.evaluate(parameters)
    if (result) parametersOpen.value = false
  } catch (cause) { error.value = message(cause) }
  finally { busy.value = false }
}
watch(() => `${props.taskId}:${props.releaseId}`, async () => {
  const token = ++loadToken
  modelId.value = null
  models.value = []
  parametersOpen.value = false
  busy.value = true
  error.value = ''
  try {
    let skip = 0, total = 0
    const entries: Model[] = []
    do {
      const { data } = await modelService.list(skip, 100, { taskBound: true, linked: false })
      if (token !== loadToken) return
      entries.push(...data.items.filter(model => model.taskVersion?.taskId === props.taskId && model.taskVersion.versionId === props.releaseId && model.preferences.evaluationLab === true))
      skip += data.items.length
      total = data.total
      if (!data.items.length) break
    } while (skip < total)
    models.value = entries
    modelId.value = entries[0]?.id ?? null
  } catch (cause) { if (token === loadToken) error.value = message(cause) }
  finally { if (token === loadToken) busy.value = false }
}, { immediate: true })
onBeforeUnmount(() => { loadToken++ })
defineExpose({ saveChanges })
</script>

<style scoped>
.live-test { display: flex; flex-direction: column; flex: 1; min-height: 0; overflow: hidden; }
.live-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 12px 16px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
.live-title { flex: 1 1 200px; }
.model-select { flex: 0 1 280px; min-width: 180px; }
.live-editor { flex: 1; min-height: 0; height: auto; }
.live-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; text-align: center; }
.live-empty p { max-width: 480px; }
</style>
