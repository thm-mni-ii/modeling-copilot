<template>
  <v-container max-width="1100" class="py-8">
    <div class="d-flex align-center ga-3 mb-5">
      <h1 class="text-h4">{{ admin ? 'Learning path templates' : run ? run.name : 'Learning path runs' }}</h1>
      <v-spacer /><v-btn v-if="admin" color="primary" to="/learning-path-templates/edit">New template</v-btn><v-btn v-if="run" to="/learning-path-runs">All runs</v-btn><v-btn :loading="loading" @click="load">Refresh</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
    <v-progress-linear v-if="loading" indeterminate />
    <template v-if="run">
      <p class="mb-4">{{ run.description }}</p>
      <TreasurePathBoard :key="run.id" :run="run" :busy="busy" @open="open" @complete="complete" />
    </template>
    <template v-else>
      <template v-if="!admin"
        ><h2 class="text-h6 mb-3">My runs</h2>
        <v-card v-for="item in runs" :key="item.id" variant="outlined" class="mb-3 pa-4"
          ><div class="d-flex align-center ga-3">
            <strong>{{ item.name }}</strong
            ><v-spacer /><span>{{ item.completed }}/{{ item.total }}</span
            ><v-btn :to="`/learning-path-runs/${item.id}`">Continue</v-btn>
          </div>
          <v-progress-linear :model-value="item.progress" color="success" rounded
        /></v-card>
        <p v-if="!runs.length && !loading" class="mb-6 text-medium-emphasis">You have not started a run yet.</p>
        <h2 class="text-h6 mt-6 mb-3">Available learning path templates</h2></template
      >
      <v-card v-for="item in templates" :key="item.id" variant="outlined" class="mb-3 pa-4"
        ><div class="d-flex align-center flex-wrap ga-3">
          <strong>{{ item.name }}</strong
          ><v-chip v-if="admin" size="small">{{ item.archived ? 'Archived' : item.published ? 'Published' : 'Draft' }}</v-chip
          ><v-spacer /><v-btn v-if="admin" :to="`/learning-path-templates/${item.id}/edit`">Edit</v-btn><v-btn v-if="item.published && !item.archived" color="primary" :disabled="!!busy" :loading="busy === item.id" @click="start(item.id)">{{ runs.some((r) => r.templateId === item.id) ? 'Open run' : 'Start run' }}</v-btn>
        </div>
        <p class="my-2">{{ item.description }}</p>
        <span class="text-caption">{{ item.steps.length }} tasks</span></v-card
      >
      <v-alert v-if="!templates.length && !loading" type="info" variant="tonal">No learning path templates available.</v-alert>
    </template>
    <v-dialog
      :model-value="Boolean(challengeStep)"
      max-width="560"
      :persistent="Boolean(busy)"
      aria-labelledby="challenge-start-title"
      @update:model-value="
        (value) => {
          if (!value && !busy) challengeStep = null
        }
      "
    >
      <v-card v-if="challengeStep?.challenge">
        <v-card-title id="challenge-start-title">Before you start</v-card-title>
        <v-card-subtitle class="text-wrap">{{ challengeStep.title }}</v-card-subtitle>
        <v-card-text
          ><v-alert v-if="error" type="error" class="mb-3">{{ error }}</v-alert
          ><ChallengeDetails :config="challengeStep.challenge" />
          <p v-if="challengeStep.challenge.type === 'time'" class="text-body-2 mt-3">The countdown begins when you select “Start task”.</p></v-card-text
        >
        <v-card-actions><v-btn :disabled="Boolean(busy)" @click="challengeStep = null">Cancel</v-btn><v-spacer /><v-btn color="primary" :loading="Boolean(busy)" @click="confirmChallenge">Start task</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TreasurePathBoard from '@/components/learningPaths/TreasurePathBoard.vue'
import ChallengeDetails from '@/components/learningPaths/ChallengeDetails.vue'
import type { ChallengeConfig } from '@/services/challenges'
import paths, { type PathRun, type PathTemplate, type StepRun } from '@/services/learningPaths'
const route = useRoute(),
  router = useRouter()
const admin = computed(() => route.name === 'LearningPathTemplates')
const templates = ref<PathTemplate[]>([]),
  runs = ref<PathRun[]>([]),
  run = ref<PathRun | null>(null)
const loading = ref(false),
  busy = ref(''),
  error = ref('')
const message = (e: unknown) => (e as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The learning path could not be loaded.'
const challengeStep = ref<StepRun | null>(null)
let generation = 0
const load = async () => {
  const current = ++generation
  loading.value = true
  error.value = ''
  try {
    if (route.params.id) {
      const result = (await paths.run(String(route.params.id))).data
      if (current === generation) run.value = result
    } else {
      run.value = null
      const allTemplates: PathTemplate[] = [],
        allRuns: PathRun[] = []
      for (let skip = 0; ; ) {
        const page = (await paths.templates(skip)).data
        allTemplates.push(...page.items)
        skip += page.items.length
        if (skip >= page.total || !page.items.length) break
      }
      if (!admin.value)
        for (let skip = 0; ; ) {
          const page = (await paths.runs(skip)).data
          allRuns.push(...page.items)
          skip += page.items.length
          if (skip >= page.total || !page.items.length) break
        }
      if (current === generation) {
        templates.value = admin.value ? allTemplates : allTemplates.filter((t) => t.published && !t.archived)
        runs.value = allRuns
      }
    }
  } catch (e) {
    if (current === generation) error.value = message(e)
  } finally {
    if (current === generation) loading.value = false
  }
}
const start = async (id: string) => {
  busy.value = id
  try {
    const result = (await paths.start(id)).data
    await router.push(`/learning-path-runs/${result.id}`)
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = ''
  }
}
const open = async (step: StepRun) => {
  if (busy.value || step.status === 'locked') return
  error.value = ''
  if (!step.modelId && step.challenge) {
    challengeStep.value = JSON.parse(JSON.stringify(step))
    return
  }
  await openModel(step)
}
const confirmChallenge = async () => {
  if (!challengeStep.value || busy.value) return
  await openModel(challengeStep.value, challengeStep.value.challenge ?? null)
}
const openModel = async (step: StepRun, acknowledgedChallenge: ChallengeConfig | null = null) => {
  if (!run.value) return
  busy.value = step.id
  try {
    const result = (await paths.startStep(run.value.id, step.id, acknowledgedChallenge)).data
    challengeStep.value = null
    await router.push(`/modeling/${result.modelId}`)
  } catch (e) {
    if ((e as { response?: { status?: number } }).response?.status === 409) {
      challengeStep.value = null
      await load()
    }
    error.value = message(e)
  } finally {
    busy.value = ''
  }
}
const complete = async (step: StepRun) => {
  if (!run.value) return
  busy.value = step.id
  try {
    run.value = (await paths.complete(run.value.id, step.id)).data
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = ''
  }
}
watch(
  () => route.fullPath,
  () => {
    challengeStep.value = null
    void load()
  },
  { immediate: true }
)
// Time-based unlocks are re-evaluated by the server while this view is open.
const timer = setInterval(() => {
  if (run.value && !loading.value && !busy.value) void load()
}, 30000)
onUnmounted(() => {
  clearInterval(timer)
  generation++
})
</script>
