<template>
  <v-container max-width="1100" class="py-8">
    <v-btn v-if="run" variant="text" prepend-icon="mdi-arrow-left" to="/learning-path-runs" class="mb-3">My learning paths</v-btn>
    <div class="d-flex align-start flex-wrap ga-3 mb-5">
      <div class="path-heading">
        <h1 class="text-h4">{{ admin ? 'Learning path templates' : run ? run.name : 'My learning paths' }}</h1>
        <p v-if="!admin && !run" class="text-body-1 text-medium-emphasis mt-2">Pick up where you left off or explore a new learning path.</p>
      </div>
      <v-btn v-if="admin" color="primary" to="/learning-path-templates/edit">New template</v-btn><v-btn variant="text" prepend-icon="mdi-refresh" :loading="loading" @click="load">Refresh</v-btn>
    </div>
    <v-alert v-if="error" type="error" class="mb-4">{{ error }}</v-alert>
    <v-progress-linear v-if="loading" indeterminate />
    <template v-if="run">
      <p class="mb-4">{{ run.description }}</p>
      <TreasurePathBoard :key="run.id" :run="run" :busy="busy" :expanded-id="surveyStep?.id" @open="open" @complete="complete">
        <template #activity="{ step }">
          <h3 class="text-h6 mb-3">{{ step.title }}</h3>
          <SurveyRenderer :key="`${step.id}:${step.surveyId}`" ref="surveyRenderer" :survey-id="step.surveyId!" :activity="{ runId: run.id, stepId: step.id }" @completed="surveyCompleted" />
          <div class="d-flex flex-wrap ga-2 mt-3"><v-btn :disabled="surveyRenderer?.saving" :loading="busy === step.id" @click="laterSurvey">Später</v-btn><v-btn v-if="step.required === false" :disabled="surveyRenderer?.saving" :loading="busy === step.id" @click="skipSurvey">Überspringen</v-btn></div>
        </template>
      </TreasurePathBoard>
    </template>
    <template v-else>
      <template v-if="!admin">
        <section aria-labelledby="started-paths-title" class="mb-8">
          <h2 id="started-paths-title" class="text-h6 mb-3">
            Your learning paths <span class="text-body-2 text-medium-emphasis">({{ runs.length }})</span>
          </h2>
          <v-card v-for="item in orderedRuns" :key="item.id" variant="outlined" class="path-card mb-3 pa-5">
            <div class="path-card-content">
              <div class="path-card-main">
                <v-chip :color="isFinished(item) ? 'success' : 'primary'" size="small" variant="tonal" class="mb-2">{{ isFinished(item) ? 'Finished' : 'In progress' }}</v-chip>
                <h3 class="text-h6">{{ item.name }}</h3>
                <p v-if="item.description" class="text-body-2 text-medium-emphasis mt-1">{{ item.description }}</p>
                <div class="d-flex align-center flex-wrap ga-2 mt-4 mb-2 text-body-2">
                  <span>{{ item.completed }} of {{ item.total }} completed</span>
                  <span v-if="item.skipped" class="text-medium-emphasis">· {{ item.skipped }} skipped</span>
                  <v-spacer /><strong>{{ item.progress }}%</strong>
                </div>
                <v-progress-linear :model-value="item.progress" color="success" rounded height="6" :aria-label="`Progress for ${item.name}`" />
              </div>
              <v-btn :to="`/learning-path-runs/${item.id}`" :color="isFinished(item) ? undefined : 'primary'" :variant="isFinished(item) ? 'outlined' : 'flat'" append-icon="mdi-arrow-right">{{ isFinished(item) ? 'View path' : 'Continue' }}</v-btn>
            </div>
          </v-card>
          <div v-if="!runs.length && !loading" class="path-empty pa-6">
            <v-icon color="primary" size="28" class="mb-2">mdi-map-marker-path</v-icon>
            <p class="font-weight-medium">Your journey starts here</p>
            <p class="text-body-2 text-medium-emphasis mt-1">Choose a learning path below to start your first activity.</p>
          </div>
        </section>
        <h2 class="text-h6 mb-1">Explore new learning paths</h2>
        <p class="text-body-2 text-medium-emphasis mb-4">Choose a path to discover its activities and get started.</p>
      </template>
      <v-card v-for="item in visibleTemplates" :key="item.id" variant="outlined" class="path-card mb-3 pa-5"
        ><div class="d-flex align-center flex-wrap ga-3">
          <h3 class="text-h6">{{ item.name }}</h3>
          <v-chip v-if="admin" size="small">{{ item.archived ? 'Archived' : item.published ? 'Published' : 'Draft' }}</v-chip>
          <v-spacer /><v-btn v-if="admin" :to="`/learning-path-templates/${item.id}/edit`">Edit</v-btn><v-btn v-if="item.published && !item.archived" color="primary" :disabled="!!busy" :loading="busy === item.id" @click="start(item.id)">{{ admin ? 'Start run' : 'Start learning path' }}</v-btn>
        </div>
        <p class="my-2">{{ item.description }}</p>
        <span class="text-caption text-medium-emphasis"><v-icon size="16" class="mr-1">mdi-format-list-checks</v-icon>{{ item.steps.length }} activities</span></v-card
      >
      <v-alert v-if="!visibleTemplates.length && !loading" type="info" variant="tonal">{{ admin ? 'No learning path templates available.' : runs.length ? 'You have explored all available learning paths. Continue one of your paths above.' : 'No learning paths available yet. Check back soon.' }}</v-alert>
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
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import SurveyRenderer from '@/components/surveys/SurveyRenderer.vue'
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
const isFinished = (item: PathRun) => item.total > 0 && (item.finished ?? item.completed + (item.skipped ?? 0) === item.total)
const orderedRuns = computed(() => [...runs.value].sort((a, b) => Number(isFinished(a)) - Number(isFinished(b))))
const visibleTemplates = computed(() => (admin.value ? templates.value : templates.value.filter((item) => !runs.value.some((started) => started.templateId === item.id))))
const loading = ref(false),
  busy = ref(''),
  error = ref('')
const message = (e: unknown) => (e as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The learning path could not be loaded.'
const surveyStep = ref<StepRun | null>(null)
const surveyRenderer = ref<InstanceType<typeof SurveyRenderer> | null>(null)
const laterSurvey = async () => {
  if (!surveyStep.value || busy.value || surveyRenderer.value?.saving) return false
  busy.value = surveyStep.value.id
  try {
    if ((await surveyRenderer.value?.saveDraft()) === false) return false
    surveyStep.value = null
    await load()
    return true
  } finally {
    busy.value = ''
  }
}
const surveyCompleted = async () => {
  surveyStep.value = null
  await load()
}
const skipSurvey = async () => {
  if (!run.value || !surveyStep.value || busy.value) return
  busy.value = surveyStep.value.id
  try {
    if ((await surveyRenderer.value?.saveDraft()) === false) return
    const session = surveyRenderer.value?.getSessionReference()
    if (!session?.sessionId) return
    await paths.skipSurvey(run.value.id, surveyStep.value.id, session.revision, session.sessionId)
    try {
      localStorage.removeItem(session.draftKey)
    } catch {
      /* Server state is authoritative. */
    }
    surveyStep.value = null
    await load()
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = ''
  }
}
onBeforeRouteLeave(async () => {
  if (surveyStep.value) return await laterSurvey()
})
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
  if (surveyStep.value && !(await laterSurvey())) return
  error.value = ''
  if (step.type === 'survey') {
    if (!['completed', 'skipped'].includes(step.status)) surveyStep.value = step
    return
  }
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
  if (step.beforeSurveyId || step.afterSurveyId) {
    if (step.modelId) await router.push({ path: `/modeling/${step.modelId}`, query: { complete: '1' } })
    return
  }
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
    surveyStep.value = null
    void load()
  },
  { immediate: true }
)
// Reload only when a known time-based unlock is due in the visible view.
const timer = setInterval(() => {
  if (document.visibilityState !== 'visible' || !run.value || loading.value || busy.value) return
  const now = Date.now()
  if (run.value.steps.some((step) => step.status === 'locked' && step.availableAt && Date.parse(step.availableAt) <= now)) void load()
}, 30000)
onUnmounted(() => {
  clearInterval(timer)
  generation++
})
</script>

<style scoped>
.path-heading,
.path-card-main {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
}
.path-card {
  border-color: rgba(var(--v-theme-on-surface), 0.14);
  border-radius: 16px;
}
.path-card-content {
  display: flex;
  align-items: center;
  gap: 32px;
}
.path-empty {
  border: 1px dashed rgba(var(--v-theme-on-surface), 0.2);
  border-radius: 16px;
  text-align: center;
}
@media (max-width: 600px) {
  .path-card-content {
    align-items: stretch;
    flex-direction: column;
    gap: 20px;
  }
}
</style>
