<template>
  <v-container class="path-editor py-5" max-width="1440">
    <header class="editor-header">
      <div class="header-title">
        <router-link to="/learning-path-templates" class="overview-link"><v-icon size="16">mdi-arrow-left</v-icon> Learning path templates</router-link>
        <div class="path-title">
          <h1 class="path-name" :aria-label="draft.name || 'Untitled path'">
            <input ref="nameInput" v-model="draft.name" aria-label="Learning path name" :aria-invalid="attempted && !draft.name.trim()" :disabled="!ready" placeholder="Untitled path" maxlength="256" />
          </h1>
          <v-btn icon="mdi-pencil-outline" size="x-small" variant="text" aria-label="Rename learning path" title="Rename learning path" :disabled="!ready" @click="nameInput?.focus()" />
        </div>
        <v-textarea v-model="draft.description" class="path-description" aria-label="Path description" placeholder="Add a description…" variant="plain" density="compact" rows="3" hide-details maxlength="5000" :disabled="!ready" />
      </div>
      <div class="header-actions">
        <v-menu>
          <template #activator="{ props }">
            <v-chip v-bind="props" size="small" :color="visibilityAppearance[draft.visibility].color" variant="flat" :prepend-icon="visibilityAppearance[draft.visibility].icon" append-icon="mdi-chevron-down" :disabled="!ready" :aria-label="`Change visibility: ${pathVisibilityLabel(draft.visibility)}`">{{ pathVisibilityLabel(draft.visibility) }}</v-chip>
          </template>
          <v-list aria-label="Path visibility" max-width="360" density="compact">
            <v-list-item v-for="option in visibilityOptions" :key="option.value" :title="option.title" :subtitle="option.description" :base-color="option.color" :color="option.color" variant="tonal" :prepend-icon="option.icon" :active="draft.visibility === option.value" :append-icon="draft.visibility === option.value ? 'mdi-check' : undefined" lines="three" @click="draft.visibility = option.value" />
            <p class="text-caption text-medium-emphasis px-4 py-2">Applied when you save. Hiding a path preserves progress and answers.</p>
          </v-list>
        </v-menu>
        <v-btn size="small" variant="text" prepend-icon="mdi-eye-outline" :disabled="!draft.steps.length" @click="previewDialog = true">Preview</v-btn>
        <v-btn size="small" color="primary" variant="flat" prepend-icon="mdi-content-save-outline" :loading="busy" :disabled="loading || !ready || !dirty" @click="save()">Save</v-btn>
        <span class="save-state" role="status">{{ dirty ? 'Unsaved changes' : draft.id ? 'All changes saved' : 'Not saved yet' }}</span>
      </div>
    </header>
    <v-progress-linear v-if="loading" indeterminate class="mb-4" />
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}<v-btn v-if="!ready && !loading" variant="text" size="small" @click="load">Retry</v-btn></v-alert>

    <div class="editor-grid" :class="{ 'editor-grid--detail': showDetail }">
      <aside class="path-sidebar" aria-label="Path activities and features">
        <div class="sidebar-add" role="group" aria-label="Add activity">
          <v-btn size="small" color="primary" variant="tonal" prepend-icon="mdi-file-document-plus-outline" aria-label="Add task" :disabled="!ready || draft.steps.length >= 200" @click="openTaskPicker">Task</v-btn>
          <v-btn size="small" color="deep-purple" variant="tonal" prepend-icon="mdi-clipboard-plus-outline" aria-label="Add questionnaire" :disabled="!ready || draft.steps.length >= 200" @click="surveyPickerDialog = true">Questionnaire</v-btn>
        </div>
        <div class="path-features" role="group" aria-label="Lernpfad-Features">
          <button type="button" class="pulse-feature" :class="{ 'pulse-feature--selected': detailMode === 'pulse', 'pulse-feature--enabled': draft.pulseSurveys?.enabled, 'pulse-feature--error': attempted && pulseIssue }" :aria-pressed="detailMode === 'pulse'" aria-controls="path-detail-panel" :disabled="!ready" @click="selectPulseSettings">
            <v-icon size="18" :color="draft.pulseSurveys?.enabled ? 'success' : undefined">mdi-comment-question-outline</v-icon>
            <strong class="pulse-feature-name">Impuls-Fragen</strong>
            <span class="feature-state">{{ draft.pulseSurveys?.enabled ? 'Aktiv' : 'Inaktiv' }}</span>
          </button>
          <button type="button" class="pulse-feature" :class="{ 'pulse-feature--selected': detailMode === 'help', 'pulse-feature--enabled': draft.helpRequests?.enabled }" :aria-pressed="detailMode === 'help'" aria-controls="path-detail-panel" :disabled="!ready" @click="selectHelpSettings">
            <v-icon size="18" :color="draft.helpRequests?.enabled ? 'success' : undefined">mdi-lifebuoy</v-icon>
            <strong class="pulse-feature-name">Hilfe anfordern</strong>
            <span class="feature-state">{{ draft.helpRequests?.enabled ? 'Aktiv' : 'Inaktiv' }}</span>
          </button>
        </div>
        <div class="activity-scroll" role="region" aria-label="Path activities" tabindex="0">
          <v-alert v-if="orderNotice" type="info" variant="tonal" density="compact" closable class="ma-3 text-caption" @click:close="orderNotice = ''">{{ orderNotice }}</v-alert>
          <draggable v-model="draft.steps" item-key="id" handle=".step-handle" class="step-list" ghost-class="step-row--ghost" :animation="150" @end="onReorder">
            <template #item="{ element, index }">
              <div class="step-row" :class="{ 'step-row--survey': element.type === 'survey', 'step-row--active': detailMode === 'activity' && selectedId === element.id, 'step-row--error': issues[element.id]?.length }">
                <span class="step-handle" aria-hidden="true"><v-icon size="18">mdi-drag-vertical</v-icon></span>
                <button type="button" class="step-select" :aria-pressed="detailMode === 'activity' && selectedId === element.id" @click="selectStep(element.id)">
                  <span class="step-number">{{ index + 1 }}</span
                  ><span class="step-copy"
                    ><strong
                      ><v-icon size="15">{{ element.type === 'survey' ? 'mdi-clipboard-list-outline' : 'mdi-pencil-outline' }}</v-icon> {{ element.title || 'Untitled task' }}</strong
                    ><span>{{ availabilitySummary(element, draft.steps) }}</span
                    ><span v-if="element.challenge" class="step-challenge"
                      ><v-icon size="13" :color="element.challenge.color ?? undefined">{{ element.challenge.icon }}</v-icon> {{ element.challenge.title }}</span
                    ></span
                  >
                  <v-icon v-if="issues[element.id]?.length" color="error" size="18" :aria-label="`${issues[element.id].length} errors`">mdi-alert-circle-outline</v-icon>
                </button>
                <v-menu
                  ><template #activator="{ props }"><v-btn v-bind="props" icon="mdi-dots-vertical" size="x-small" variant="text" :aria-label="`Actions for step ${index + 1}`" /></template
                  ><v-list density="compact"
                    ><v-list-item title="Move up" prepend-icon="mdi-arrow-up" :disabled="index === 0" @click="move(index, -1)" /><v-list-item title="Move down" prepend-icon="mdi-arrow-down" :disabled="index === draft.steps.length - 1" @click="move(index, 1)" /><v-list-item title="Duplicate" prepend-icon="mdi-content-copy" @click="duplicate(element)" /><v-list-item
                      title="Remove"
                      prepend-icon="mdi-delete-outline"
                      @click="removeId = element.id" /></v-list
                ></v-menu>
              </div>
            </template>
          </draggable>
          <div v-if="!draft.steps.length" class="sidebar-empty">
            <v-icon size="34" class="mb-3">mdi-map-marker-path</v-icon>
            <p>Start with a few tasks.</p>
            <p class="text-caption mt-1">You can add more at any time.</p>
          </div>
        </div>
      </aside>

      <section id="path-detail-panel" ref="detailPanel" class="step-details" tabindex="0" :aria-label="detailMode === 'help' ? 'Hilfe konfigurieren' : detailMode === 'pulse' ? 'Impuls-Fragen konfigurieren' : 'Selected activity settings'">
        <template v-if="detailMode === 'help'">
          <v-btn class="mobile-back mb-3" variant="text" prepend-icon="mdi-arrow-left" @click="showDetail = false">Back to path</v-btn>
          <div class="detail-heading">
            <div>
              <p class="text-overline text-medium-emphasis">Lernpfad-Feature · Konfiguration</p>
              <h2 ref="detailHeading" tabindex="-1" class="text-h5"><v-icon color="primary" class="mr-2">mdi-lifebuoy</v-icon>Hilfe anfordern</h2>
            </div>
            <v-chip :color="draft.helpRequests?.enabled ? 'success' : undefined" size="small" variant="tonal">{{ draft.helpRequests?.enabled ? 'Aktiv' : 'Inaktiv' }}</v-chip>
          </div>
          <HelpRequestSettings v-model="draft.helpRequests" @validation="helpIssue = $event" />
        </template>
        <template v-else-if="detailMode === 'pulse'">
          <v-btn class="mobile-back mb-3" variant="text" prepend-icon="mdi-arrow-left" @click="showDetail = false">Back to path</v-btn>
          <div class="detail-heading">
            <div>
              <p class="text-overline text-medium-emphasis">Lernpfad-Feature · Konfiguration</p>
              <h2 ref="detailHeading" tabindex="-1" class="text-h5"><v-icon color="primary" class="mr-2">mdi-comment-question-outline</v-icon>Impuls-Fragen</h2>
            </div>
            <v-chip :color="draft.pulseSurveys?.enabled ? 'success' : undefined" size="small" variant="tonal">{{ draft.pulseSurveys?.enabled ? 'Aktiv' : 'Inaktiv' }}</v-chip>
          </div>
          <p class="text-body-2 text-medium-emphasis mt-4">Kurze, zufällig angebotene Fragen begleiten die Aufgabenbearbeitung. Sie gelten für den gesamten Lernpfad und können von Lernenden weggeklickt werden.</p>
          <PulseSurveySettings v-model="draft.pulseSurveys" :steps="draft.steps" :surveys="surveyList" :loading="loadingTasks" />
        </template>
        <template v-else-if="selected">
          <v-btn class="mobile-back mb-3" variant="text" prepend-icon="mdi-arrow-left" @click="showDetail = false">Back to path</v-btn>
          <div class="detail-heading">
            <div>
              <p class="text-overline text-medium-emphasis">STEP {{ selectedIndex + 1 }} OF {{ draft.steps.length }}</p>
              <h2 ref="detailHeading" tabindex="-1" class="text-h5">{{ selected.type === 'survey' ? 'Questionnaire settings' : 'Task settings' }}</h2>
            </div>
            <div><v-btn icon="mdi-content-copy" variant="text" aria-label="Duplicate selected task" @click="duplicate(selected)" /><v-btn icon="mdi-delete-outline" variant="text" aria-label="Remove selected task" @click="removeId = selected.id" /></div>
          </div>
          <v-alert v-if="issues[selected.id]?.length" type="error" variant="tonal" density="compact" class="mt-4"
            ><ul class="pl-4">
              <li v-for="issue in issues[selected.id]" :key="issue">{{ issue }}</li>
            </ul></v-alert
          >
          <div class="d-flex align-center ga-4 mt-5">
            <v-text-field v-model="selected.title" label="Step title" variant="outlined" class="flex-grow-1" maxlength="256" hide-details="auto" :error-messages="attempted && !selected.title.trim() ? 'A step title is required.' : []" /><v-switch v-if="selected.type === 'survey'" v-model="selected.required" label="Required" color="primary" hide-details class="flex-grow-0" />
          </div>
          <div v-if="selected.type !== 'survey'" class="task-source mt-3">
            <v-icon size="19">mdi-clipboard-text-outline</v-icon>
            <div>
              <strong>{{ taskName(selected) }}</strong
              ><span>{{ releaseLabel(selected) }}</span>
            </div>
            <v-spacer /><v-btn variant="text" size="small" :loading="loadingVersions === selected.taskVersion!.taskId" @click="openReleaseDialog">Change release</v-btn>
          </div>
          <template v-if="selected.type === 'survey'">
            <v-select :model-value="selected.surveyId" :items="surveyOptions" label="Published questionnaire" class="mt-4" @update:model-value="chooseSurvey" />
            <p class="text-caption">Uses the current published questionnaire. Optional questionnaires can be skipped.</p>
            <p class="text-body-2 mt-3">{{ availabilitySummary(selected, draft.steps) }}</p>
          </template>
          <v-expansion-panels v-model="activitySections" multiple variant="accordion" class="activity-sections mt-5">
            <v-expansion-panel v-if="selected.type !== 'survey'" value="evaluation">
              <v-expansion-panel-title><v-icon size="20" class="mr-2">mdi-check-decagram-outline</v-icon>Automatic evaluation</v-expansion-panel-title>
              <v-expansion-panel-text>
                <p class="text-caption text-medium-emphasis mb-3">Legt fest, welches Prüfergebnis zum Bestehen dieser Aufgabe erforderlich ist.</p>
                <v-progress-linear v-if="loadingEvaluationRelease" indeterminate color="info" class="mb-2" />
                <v-alert v-if="evaluationReleaseError" type="error" density="compact" variant="tonal" class="mb-2">{{ evaluationReleaseError }}<v-btn size="small" variant="text" @click="loadEvaluationRelease">Retry</v-btn></v-alert>
                <p v-else-if="!loadingEvaluationRelease && !selectedEvaluationAvailable" class="text-caption mb-2">Add a released sample solution to this task release to enable automatic evaluation.</p>
                <v-switch :model-value="selected.minimumScorePercent != null" :disabled="loadingEvaluationRelease || !selectedEvaluationAvailable && selected.minimumScorePercent == null" label="Require a minimum evaluation score to complete this task" color="primary" hide-details @update:model-value="Object.assign(selected, { minimumScorePercent: $event ? 50 : null, scoreScope: 'overall', categoryMinimums: [] })" />
                <template v-if="selected.minimumScorePercent != null">
                  <v-text-field :model-value="selected.minimumScorePercent" type="number" min="0" max="100" step="1" label="Minimum score" suffix="%" variant="outlined" class="mt-3" hide-details="auto" :rules="[percentRule]" @update:model-value="selected.minimumScorePercent = $event === '' ? Number.NaN : Number($event)" />
                  <v-radio-group :model-value="selected.scoreScope ?? 'overall'" class="mt-2" hide-details @update:model-value="selected.scoreScope = $event as ScoreScope">
                    <v-radio value="overall" label="Across all objects of the sample solution" />
                    <v-radio value="eachCategory" label="In every category (e.g. entities, attributes, relationships)" />
                  </v-radio-group>
                  <h4 class="text-body-2 font-weight-medium mt-3 mb-2">Category minimums</h4>
                  <div v-for="(row, index) in selected.categoryMinimums" :key="index" class="d-flex ga-2 align-center mb-2">
                    <v-combobox v-model="row.label" :items="categorySuggestions" label="Category" density="compact" variant="outlined" hide-details />
                    <v-text-field :model-value="row.minimumPercent" type="number" min="0" max="100" step="1" suffix="%" density="compact" variant="outlined" hide-details="auto" class="category-minimum" :rules="[percentRule]" :aria-label="`Minimum for ${row.label || 'category'}`" @update:model-value="row.minimumPercent = $event === '' ? Number.NaN : Number($event)" />
                    <v-btn icon="mdi-delete-outline" variant="text" size="small" aria-label="Remove category minimum" @click="selected.categoryMinimums!.splice(index, 1)" />
                  </div>
                  <v-btn variant="text" size="small" prepend-icon="mdi-plus" @click="(selected.categoryMinimums ??= []).push({ label: '', minimumPercent: selected.minimumScorePercent })">Add category minimum</v-btn>
                  <p class="text-caption mt-2">Completion evaluates the current model. {{ selected.scoreScope === 'eachCategory' ? 'Every category must reach the minimum score' : 'The share of recognized objects must reach the minimum score' }}; a category minimum replaces or adds the requirement for that category. Categories absent from the sample solution are ignored.</p>
                </template>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel v-if="selected.type !== 'survey'" value="feedback">
              <v-expansion-panel-title><v-icon size="20" class="mr-2">mdi-comment-check-outline</v-icon>Feedback settings</v-expansion-panel-title>
              <v-expansion-panel-text>
                <p class="text-caption text-medium-emphasis mb-3">Wie oft dürfen Lernende welche Hilfe für diese Station nutzen? Die Limits gelten pro persönlichem Durchlauf und zählen erfolgreich erzeugtes Feedback. Leer = unbegrenzt · 0 = deaktiviert.</p>
                <v-progress-linear v-if="loadingEvaluationRelease" indeterminate color="info" class="mb-2" />
                <v-alert v-if="evaluationReleaseError" type="error" density="compact" variant="tonal" class="mb-2">{{ evaluationReleaseError }}<v-btn size="small" variant="text" @click="loadEvaluationRelease">Retry</v-btn></v-alert>
                <section v-if="!loadingEvaluationRelease && selectedEvaluationAvailable" aria-label="Feedback usage for this task">
                  <p v-if="!draft.helpRequests?.enabled" class="text-caption text-medium-emphasis mb-3">Die Limits werden wirksam, sobald „Hilfe anfordern“ für den Lernpfad aktiviert ist.</p>
                  <div class="feedback-limits">
                    <div v-for="option in helpFeedbackOptions" :key="option.type" class="feedback-limit-row">
                      <v-icon size="24" color="primary-dark">{{ option.icon }}</v-icon>
                      <div class="feedback-limit-copy"><strong class="text-body-2">{{ option.title }}</strong><p class="text-caption text-medium-emphasis">{{ option.description }}</p></div>
                      <v-text-field :model-value="selectedHelpFeedback[option.limitKey]" label="Nutzungen" :aria-label="`${option.title}: Nutzungen pro Durchlauf`" placeholder="Unbegrenzt" persistent-placeholder clearable type="number" min="0" max="100" step="1" density="compact" variant="outlined" hide-details="auto" :rules="[feedbackLimitRule]" @update:model-value="updateHelpFeedback(option.limitKey, $event)" />
                    </div>
                  </div>
                </section>
                <template v-else-if="!loadingEvaluationRelease && !evaluationReleaseError">
                  <v-alert v-if="selected.helpFeedback" type="warning" variant="tonal" density="compact">Diese Aufgabenfreigabe unterstützt kein automatisches Feedback. Wähle eine Freigabe mit Musterlösung oder entferne die Feedback-Einstellungen.<v-btn size="small" variant="text" @click="selected.helpFeedback = null">Feedback-Einstellungen entfernen</v-btn></v-alert>
                  <p v-else class="text-caption text-medium-emphasis">Eine Aufgabenfreigabe mit Musterlösung ist erforderlich, um automatisches Feedback einzustellen.</p>
                </template>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel v-if="selected.type !== 'survey'" value="questionnaires">
              <v-expansion-panel-title><v-icon size="20" class="mr-2">mdi-clipboard-list-outline</v-icon>Task questionnaires</v-expansion-panel-title>
              <v-expansion-panel-text>
                <v-select v-model="selected.beforeSurveyId" :items="surveyOptions" label="Before task" clearable hide-details class="mb-3" />
                <v-select v-model="selected.afterSurveyId" :items="surveyOptions" label="After task" clearable hide-details />
                <p class="text-caption mt-2">Required in the modeling view before working on or completing this task. Uses the current published questionnaire.</p>
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel value="availability">
              <v-expansion-panel-title><v-icon size="20" class="mr-2">mdi-lock-open-outline</v-icon>Availability</v-expansion-panel-title>
              <v-expansion-panel-text>
                <LearningPathAvailability :key="selected.id" v-model="selected.unlock" :step="selected" :steps="draft.steps" />
              </v-expansion-panel-text>
            </v-expansion-panel>
            <v-expansion-panel v-if="selected.type !== 'survey'" value="challenge">
              <v-expansion-panel-title><v-icon size="20" class="mr-2">mdi-trophy-outline</v-icon>Challenge</v-expansion-panel-title>
              <v-expansion-panel-text><ChallengeConfigEditor :key="`challenge-${selected.id}`" v-model="selected.challenge" :show-errors="attempted" /></v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </template>
        <div v-else class="detail-empty">
          <v-icon size="52" color="primary">mdi-map-marker-path</v-icon>
          <h2 class="text-h5 mt-5">Build your learning journey</h2>
          <p class="text-medium-emphasis mt-3">Choose tasks, arrange the path, and add a learning goal.</p>
          <v-btn color="primary" class="mt-5" prepend-icon="mdi-plus" :disabled="!ready" @click="openTaskPicker">Add your first tasks</v-btn>
        </div>
      </section>
    </div>

    <LearningPathTaskPicker v-model="pickerDialog" :tasks="tasks" :steps="draft.steps" :loading="loadingTasks" @add="addTasks" />
    <LearningPathSurveyPicker v-model="surveyPickerDialog" :surveys="surveyList" :steps="draft.steps" :loading="loadingTasks" @add="addSurveys" />
    <v-dialog v-model="saveConfirmation" max-width="480">
      <v-card title="Save changes?">
        <v-card-text>Saved changes apply to all runs, including paths already in progress.</v-card-text>
        <v-card-actions><v-btn @click="saveConfirmation = false">Cancel</v-btn><v-spacer /><v-btn color="primary" :disabled="!dirty" @click="save(true)">Save changes</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="releaseDialog" max-width="560"
      ><v-card title="Change task release"
        ><v-card-text
          ><p class="text-body-2 mb-4">The selected release is fixed when a learner starts a new run. Existing runs keep their original releases.</p>
          <v-select v-model="pendingVersion" :items="selectedVersions.map((version) => ({ title: releaseVersionLabel(version), value: version.id }))" label="Task release" variant="outlined" :loading="Boolean(loadingVersions)" /><v-alert v-if="!selectedVersions.length && !loadingVersions" type="info" variant="tonal">No accessible releases found.</v-alert></v-card-text
        ><v-card-actions><v-btn @click="releaseDialog = false">Cancel</v-btn><v-spacer /><v-btn color="primary" :disabled="!pendingVersion || !selectedVersions.some((version) => version.id === pendingVersion)" @click="applyRelease">Use release</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog
      :model-value="Boolean(removeId)"
      max-width="560"
      @update:model-value="
        (value) => {
          if (!value) removeId = null
        }
      "
      ><v-card title="Remove this step?"
        ><v-card-text
          ><template v-if="dependents.length"
            ><p class="mb-3">Update these tasks first. Their rules still reference this step:</p>
            <v-list density="compact"><v-list-item v-for="step in dependents" :key="step.id" :title="step.title" append-icon="mdi-arrow-right" @click="editDependent(step.id)" /></v-list
          ></template>
          <p v-else>Existing runs keep this activity and their learner work.</p></v-card-text
        ><v-card-actions><v-btn @click="removeId = null">Cancel</v-btn><v-spacer /><v-btn color="error" :disabled="Boolean(dependents.length)" @click="confirmRemove">Remove step</v-btn></v-card-actions></v-card
      ></v-dialog
    >
    <v-dialog v-model="previewDialog" max-width="1100" scrollable
      ><v-card
        ><v-card-title class="d-flex align-center">{{ draft.name || 'Path preview' }}<v-spacer /><v-btn icon="mdi-close" variant="text" aria-label="Close path preview" @click="previewDialog = false" /></v-card-title
        ><v-card-text
          ><v-alert type="info" variant="tonal" density="compact" class="mb-4">Preview of a new learner’s run. Select an available chest or treasure map to edit its settings.</v-alert
          ><TreasurePathBoard
            :run="previewRun"
            busy=""
            @open="
              (step) => {
                previewDialog = false
                selectStep(step.id)
              }
            " /></v-card-text></v-card
    ></v-dialog>
  </v-container>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import draggable from 'vuedraggable'
import ChallengeConfigEditor from '@/components/learningPaths/ChallengeConfigEditor.vue'
import LearningPathAvailability from '@/components/learningPaths/LearningPathAvailability.vue'
import LearningPathTaskPicker from '@/components/learningPaths/LearningPathTaskPicker.vue'
import PulseSurveySettings from '@/components/learningPaths/PulseSurveySettings.vue'
import HelpRequestSettings from '@/components/learningPaths/HelpRequestSettings.vue'
import LearningPathSurveyPicker from '@/components/learningPaths/LearningPathSurveyPicker.vue'
import TreasurePathBoard from '@/components/learningPaths/TreasurePathBoard.vue'
import paths, { pathVisibilityOptions, pathVisibilityLabel, defaultTaskHelpFeedbackConfig, helpFeedbackOptions, type PathRun, type PathStep, type PathTemplate, type PathVisibility, type ScoreScope, type TaskHelpFeedbackConfig } from '@/services/learningPaths'
import surveys, { type Survey } from '@/services/surveys'
import taskService from '@/services/task/task.service'
import languageService from '@/services/language/language.service'
import type { Task, TaskVersion, TaskVersionInfo } from '@/services/api/types/task'
import { availabilitySummary, conditionSummary, validatePathSteps, validatePulseConfig } from '@/utils/learningPathEditor'
import { releaseVersionLabel } from '@/utils/versions'

const route = useRoute(),
  router = useRouter()
const draft = ref<PathTemplate>({ id: '', name: '', description: '', visibility: 'hidden', published: false, archived: false, revision: 0, updatedAt: null, steps: [] })
const visibilityAppearance: Record<PathVisibility, { color: string; icon: string }> = {
  published: { color: 'success', icon: 'mdi-earth' },
  unlisted: { color: 'deep-purple', icon: 'mdi-link-variant' },
  hidden: { color: 'medium-gray', icon: 'mdi-eye-off-outline' }
}
const visibilityOptions = pathVisibilityOptions.map((option) => ({ ...option, value: option.value as PathVisibility, ...visibilityAppearance[option.value as PathVisibility] }))
const tasks = ref<Task[]>([]),
  versions = ref<Record<string, TaskVersionInfo[]>>({})
const detailMode = ref<'activity' | 'pulse' | 'help'>('activity')
const selectedId = ref<string | null>(null),
  selected = computed(() => detailMode.value === 'activity' ? draft.value.steps.find((step) => step.id === selectedId.value) ?? null : null)
const selectedIndex = computed(() => draft.value.steps.findIndex((step) => step.id === selectedId.value))
const activitySections = ref(['evaluation', 'feedback'])
const selectedHelpFeedback = computed(() => ({ ...defaultTaskHelpFeedbackConfig(), ...selected.value?.helpFeedback }))
const feedbackLimitRule = (value: unknown) => value == null || value === '' || (Number.isInteger(Number(value)) && Number(value) >= 0 && Number(value) <= 100) || 'Enter a whole number between 0 and 100, or leave empty for unlimited.'
const updateHelpFeedback = (key: keyof TaskHelpFeedbackConfig, value: string | number | null) => {
  if (selected.value) selected.value.helpFeedback = { ...selectedHelpFeedback.value, [key]: value === '' || value == null ? null : Number(value) }
}
const evaluationRelease = ref<TaskVersion | null>(null)
const loadingEvaluationRelease = ref(false)
const evaluationReleaseError = ref('')
const selectedEvaluationAvailable = computed(() => Boolean(evaluationRelease.value?.data.sampleSolutions.length))
const categorySuggestions = ref<string[]>([])
const percentRule = (value: unknown) => (value !== '' && Number.isFinite(Number(value)) && Number(value) >= 0 && Number(value) <= 100) || 'Enter a percentage between 0 and 100.'
let evaluationReleaseGeneration = 0
const loadEvaluationRelease = async () => {
  const reference = selected.value?.taskVersion
  const generation = ++evaluationReleaseGeneration
  evaluationRelease.value = null
  evaluationReleaseError.value = ''
  loadingEvaluationRelease.value = Boolean(reference)
  if (!reference) return
  try {
    const result = (await taskService.getVersion(reference.taskId, reference.versionId)).data
    if (generation !== evaluationReleaseGeneration) return
    evaluationRelease.value = result
    // Category suggestions are the comparison groups of the task languages; missing languages just yield none.
    const languages = await Promise.all(result.workspaceLanguages.map((language) => languageService.getVersion<{ evaluation?: { comparisonGroups?: { name: string }[] } }>(language.languageId, language.versionId).then((response) => response.data.data, () => null)))
    if (generation === evaluationReleaseGeneration) categorySuggestions.value = [...new Set(languages.flatMap((data) => data?.evaluation?.comparisonGroups?.map((group) => group.name) ?? []))]
  } catch (error) {
    if (generation === evaluationReleaseGeneration) evaluationReleaseError.value = message(error)
  } finally {
    if (generation === evaluationReleaseGeneration) loadingEvaluationRelease.value = false
  }
}
watch(() => [selected.value?.taskVersion?.taskId, selected.value?.taskVersion?.versionId], loadEvaluationRelease)
const busy = ref(false),
  loading = ref(true),
  loadingTasks = ref(true),
  ready = ref(false),
  error = ref(''),
  saved = ref(''),
  attempted = ref(false)
const showDetail = ref(false),
  nameInput = ref<HTMLInputElement | null>(null),
  detailPanel = ref<HTMLElement | null>(null),
  detailHeading = ref<HTMLElement | null>(null),
  orderNotice = ref('')
const openTaskPicker = () => {
  pickerDialog.value = true
}
const surveyList = ref<Survey[]>([])
const surveyOptions = computed(() => surveyList.value.filter((item) => item.activeReleaseId).map((item) => ({ title: item.title, value: item.id })))
const surveyPickerDialog = ref(false)
const addSurveys = (ids: string[]) => {
  if (draft.value.steps.length + ids.length > 200) {
    error.value = 'A path can contain up to 200 activities.'
    return
  }
  let first: string | null = null
  for (const id of ids) {
    const survey = surveyList.value.find((item) => item.id === id)
    if (!survey?.activeReleaseId) continue
    const step: PathStep = { id: crypto.randomUUID(), type: 'survey', title: survey.title, taskVersion: null, surveyId: id, required: true, unlock: { mode: 'sequence', conditions: [] }, challenge: null }
    draft.value.steps.push(step)
    first ??= step.id
  }
  surveyPickerDialog.value = false
  if (first) void selectStep(first)
}
const chooseSurvey = (id: string) => {
  if (!selected.value) return
  selected.value.surveyId = id
}
const pickerDialog = ref(false),
  saveConfirmation = ref(false),
  releaseDialog = ref(false),
  previewDialog = ref(false),
  removeId = ref<string | null>(null)
const pendingVersion = ref<string | null>(null),
  loadingVersions = ref('')
const dirty = computed(() => ready.value && saved.value !== JSON.stringify(draft.value))
const pulseIssue = computed(() => validatePulseConfig(draft.value.pulseSurveys, draft.value.steps))
const helpIssue = ref('')
const issues = computed(() => {
  if (!attempted.value) return {}
  const result = validatePathSteps(draft.value.steps)
  if (selected.value?.helpFeedback && !loadingEvaluationRelease.value && !evaluationReleaseError.value && !selectedEvaluationAvailable.value) {
    ;(result[selected.value.id] ??= []).push('Automatic feedback requires a released sample solution. Change the release or remove the feedback settings.')
  }
  if (selected.value?.minimumScorePercent != null && !loadingEvaluationRelease.value && !evaluationReleaseError.value && !selectedEvaluationAvailable.value) {
    ;(result[selected.value.id] ??= []).push('A minimum score requires a released sample solution in the selected task release.')
  }
  if (draft.value.visibility === 'published' && !loadingTasks.value) {
    for (const step of draft.value.steps) {
      const task = tasks.value.find((task) => task.id === step.taskVersion?.taskId)
      if (step.type !== 'survey' && (!task || task.archivedAt)) {
        ;(result[step.id] ??= []).push('Select an active source task before publishing this path.')
      }
    }
  }
  return result
})
const dependents = computed(() => draft.value.steps.filter((step) => step.id !== removeId.value && step.unlock.conditions.some((condition) => condition.stepId === removeId.value)))
const selectedVersions = computed(() => (selected.value?.taskVersion ? versions.value[selected.value.taskVersion.taskId] ?? [] : []))
const message = (e: unknown) => (e as { response?: { data?: { message?: string } } }).response?.data?.message ?? 'The action could not be completed.'
const taskName = (step: PathStep) => tasks.value.find((task) => task.id === step.taskVersion?.taskId)?.name ?? step.title
const releaseLabel = (step: PathStep) => {
  const version = versions.value[step.taskVersion?.taskId ?? '']?.find((version) => version.id === step.taskVersion?.versionId)
  return version ? releaseVersionLabel(version) : tasks.value.find((task) => task.id === step.taskVersion?.taskId)?.latestReleaseId === step.taskVersion?.versionId ? 'Latest release' : 'Saved release'
}
const selectStep = async (id: string) => {
  detailMode.value = 'activity'
  selectedId.value = id
  showDetail.value = true
  await nextTick()
  detailPanel.value?.scrollTo({ top: 0 })
  detailHeading.value?.focus({ preventScroll: true })
}
const selectPulseSettings = async () => {
  detailMode.value = 'pulse'
  showDetail.value = true
  await nextTick()
  detailPanel.value?.scrollTo({ top: 0 })
  detailHeading.value?.focus({ preventScroll: true })
}
const selectHelpSettings = async () => {
  detailMode.value = 'help'
  showDetail.value = true
  await nextTick()
  detailPanel.value?.scrollTo({ top: 0 })
  detailHeading.value?.focus({ preventScroll: true })
}
const addTasks = (ids: string[]) => {
  if (draft.value.steps.length + ids.length > 200) {
    error.value = 'A path can contain up to 200 activities.'
    return
  }
  let first: string | null = null
  for (const id of ids) {
    const task = tasks.value.find((task) => task.id === id)
    if (!task?.latestReleaseId) continue
    const step: PathStep = { id: crypto.randomUUID(), title: task.name, taskVersion: { taskId: id, versionId: task.latestReleaseId }, unlock: { mode: 'sequence', conditions: [] }, challenge: null }
    draft.value.steps.push(step)
    first ??= step.id
  }
  pickerDialog.value = false
  if (first) void selectStep(first)
}
const onReorder = () => {
  orderNotice.value = 'Display order changed. Existing prerequisite links were kept.'
}
const move = (index: number, delta: number) => {
  const [step] = draft.value.steps.splice(index, 1)
  draft.value.steps.splice(index + delta, 0, step)
  onReorder()
}
const duplicate = (source: PathStep) => {
  if (draft.value.steps.length >= 200) {
    error.value = 'A path can contain up to 200 activities.'
    return
  }
  const step: PathStep = { ...JSON.parse(JSON.stringify(source)), id: crypto.randomUUID(), title: `${source.title.slice(0, 249)} (copy)`, unlock: { mode: 'sequence', conditions: [] } }
  draft.value.steps.splice(draft.value.steps.findIndex((item) => item.id === source.id) + 1, 0, step)
  orderNotice.value = 'Task duplicated. The copy becomes available after the original task is completed.'
  void selectStep(step.id)
}
const editDependent = (id: string) => {
  removeId.value = null
  void selectStep(id)
}
const confirmRemove = () => {
  if (!removeId.value || dependents.value.length) return
  const index = draft.value.steps.findIndex((step) => step.id === removeId.value)
  if (index < 0) return
  const wasSelected = detailMode.value === 'activity' && selectedId.value === removeId.value
  draft.value.steps.splice(index, 1)
  removeId.value = null
  if (wasSelected) {
    selectedId.value = draft.value.steps[Math.min(index, draft.value.steps.length - 1)]?.id ?? null
    if (!selectedId.value) showDetail.value = false
  }
}
const pendingLoads = new Map<string, Promise<void>>()
const loadVersions = async (taskId: string) => {
  if (versions.value[taskId]) return
  if (pendingLoads.has(taskId)) return pendingLoads.get(taskId)
  const request = (async () => {
    loadingVersions.value = taskId
    try {
      const result: TaskVersionInfo[] = []
      for (let skip = 0; ; ) {
        const page = (await taskService.listVersions(taskId, skip, 100)).data
        result.push(...page.items.filter((version) => version.kind === 'release'))
        skip += page.items.length
        if (skip >= page.total || !page.items.length) break
      }
      versions.value[taskId] = result
    } catch (e) {
      error.value = message(e)
    } finally {
      pendingLoads.delete(taskId)
      if (loadingVersions.value === taskId) loadingVersions.value = ''
    }
  })()
  pendingLoads.set(taskId, request)
  return request
}
const openReleaseDialog = async () => {
  if (!selected.value) return
  pendingVersion.value = selected.value.taskVersion!.versionId
  releaseDialog.value = true
  await loadVersions(selected.value.taskVersion!.taskId)
}
const applyRelease = () => {
  if (selected.value && pendingVersion.value && selectedVersions.value.some((version) => version.id === pendingVersion.value)) selected.value.taskVersion!.versionId = pendingVersion.value
  releaseDialog.value = false
}
watch(
  () => selected.value?.taskVersion?.taskId,
  (id) => {
    if (id) void loadVersions(id)
  }
)
const save = async (confirmed = false) => {
  if (busy.value || !ready.value || !dirty.value) return
  saveConfirmation.value = false
  attempted.value = true
  error.value = ''
  if (!draft.value.name.trim()) {
    error.value = 'Give your learning path a title.'
    nameInput.value?.focus()
    return
  }
  if (draft.value.visibility === 'published' && !draft.value.steps.length) {
    error.value = 'Add at least one activity before publishing.'
    openTaskPicker()
    return
  }
  const pulseError = pulseIssue.value
  if (pulseError) {
    error.value = pulseError
    await selectPulseSettings()
    return
  }
  const invalid = Object.keys(issues.value)[0]
  if (draft.value.helpRequests?.enabled && helpIssue.value) {
    error.value = helpIssue.value
    await selectHelpSettings()
    return
  }
  if (invalid) {
    error.value = 'Review the highlighted task settings before saving.'
    activitySections.value = ['evaluation', 'feedback', 'questionnaires', 'availability', 'challenge']
    await selectStep(invalid)
    return
  }
  if (draft.value.id && !confirmed) {
    saveConfirmation.value = true
    return
  }
  busy.value = true
  try {
    // Keep edits made during the request; the returned revision is still needed for the next save.
    const submitted = JSON.stringify(draft.value)
    const result = (await paths.save(JSON.parse(submitted))).data
    if (JSON.stringify(draft.value) === submitted) draft.value = result
    else {
      draft.value.id = result.id
      draft.value.revision = result.revision
      draft.value.updatedAt = result.updatedAt
    }
    saved.value = JSON.stringify(result)
    await router.replace(`/learning-path-templates/${result.id}/edit`)
  } catch (e) {
    error.value = message(e)
  } finally {
    busy.value = false
  }
}
const previewRun = computed<PathRun>(() => ({
  id: 'template-preview',
  templateRevision: draft.value.revision,
  templateId: draft.value.id,
  name: draft.value.name,
  description: draft.value.description,
  completed: 0,
  total: draft.value.steps.length,
  progress: 0,
  steps: draft.value.steps.map((step, index) => {
    if (step.unlock.mode === 'sequence') {
      const waiting = draft.value.steps.slice(0, index).some((item) => item.type !== 'survey' || item.required !== false)
      return { ...step, modelId: null, status: waiting ? 'locked' : 'available', availableAt: null, reasons: waiting ? ['After all previous required activities are completed'] : [] }
    }
    const satisfied = step.unlock.conditions.map((condition) => (condition.type === 'at' ? Boolean(condition.at && Date.parse(condition.at) <= Date.now()) : condition.type === 'after' && !condition.stepId && condition.seconds === 0))
    const available = !satisfied.length || (step.unlock.mode === 'all' ? satisfied.every(Boolean) : satisfied.some(Boolean))
    return { ...step, modelId: null, status: available ? 'available' : 'locked', availableAt: null, reasons: step.unlock.conditions.map((condition) => conditionSummary(condition, draft.value.steps)) }
  })
}))
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    if (route.params.id) draft.value = (await paths.template(String(route.params.id))).data
    saved.value = JSON.stringify(draft.value)
    ready.value = true
    selectedId.value = draft.value.steps[0]?.id ?? null
  } catch (e) {
    error.value = message(e)
  } finally {
    loading.value = false
  }
  loadingTasks.value = true
  try {
    const result: Task[] = []
    for (let skip = 0; ; ) {
      const page = (await taskService.list(skip, 100)).data
      result.push(...page.items)
      skip += page.items.length
      if (skip >= page.total || !page.items.length) break
    }
    tasks.value = result
    const questionnaires: Survey[] = []
    for (let skip = 0; ; ) {
      const page = (await surveys.list(skip)).data
      questionnaires.push(...page.items)
      skip += page.items.length
      if (skip >= page.total || !page.items.length) break
    }
    surveyList.value = questionnaires
  } catch (e) {
    error.value = message(e)
  } finally {
    loadingTasks.value = false
  }
}
const beforeUnload = (event: BeforeUnloadEvent) => {
  if (dirty.value) {
    event.preventDefault()
    event.returnValue = ''
  }
}
onBeforeRouteLeave(() => !dirty.value || window.confirm('Discard unsaved changes?'))
onMounted(() => {
  void load()
  window.addEventListener('beforeunload', beforeUnload)
})
onUnmounted(() => window.removeEventListener('beforeunload', beforeUnload))
</script>

<style scoped>
.feedback-limits {
  display: grid;
  gap: 12px;
}
.feedback-limit-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.1);
}
.feedback-limit-copy {
  flex: 1;
  min-width: 160px;
}
.feedback-limit-row :deep(.v-input) {
  flex: 0 0 150px;
}
.activity-sections :deep(.v-expansion-panel-text__wrapper) {
  padding-top: 12px;
}
.editor-header {
  position: sticky;
  top: var(--v-layout-top, 64px);
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 0 12px;
  margin-bottom: 16px;
  background: rgb(var(--v-theme-background));
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.1);
}
.header-title {
  min-width: 0;
  flex: 1;
}
.overview-link {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: rgb(var(--v-theme-on-surface), 0.65);
  text-decoration: none;
  font-size: 0.78rem;
}
.path-title {
  display: flex;
  align-items: center;
  gap: 4px;
}
.path-name {
  flex: 1;
  min-width: 0;
  font-size: 1.4rem;
  line-height: 1.5;
}
.path-name input {
  width: 100%;
  color: inherit;
  text-overflow: ellipsis;
  font-weight: 650;
  border-bottom: 1px solid transparent;
}
.path-name input:hover:enabled {
  border-bottom-color: rgb(var(--v-theme-on-surface), 0.25);
}
.path-name input:focus-visible {
  outline: none;
  border-bottom-color: rgb(var(--v-theme-primary));
}
.path-name input[aria-invalid='true'] {
  border-bottom-color: rgb(var(--v-theme-error));
}
.path-description :deep(.v-field__input) {
  padding-top: 2px;
  min-height: 84px;
  max-height: min(280px, 35dvh);
  resize: vertical;
  overflow-y: auto;
  font-size: 0.8rem;
  line-height: 1.5;
}
.path-description :deep(.v-field) {
  --v-field-padding-top: 0px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.2);
}
.path-description :deep(.v-field--focused) {
  border-bottom-color: rgb(var(--v-theme-primary));
}
.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  flex-shrink: 0;
  gap: 8px;
}
.save-state {
  flex-basis: 100%;
  text-align: right;
  font-size: 0.72rem;
  opacity: 0.65;
}
.editor-grid {
  display: grid;
  grid-template-columns: minmax(270px, 340px) minmax(0, 1fr);
  align-items: start;
  gap: 24px;
}
.path-sidebar {
  border: 1px solid rgb(var(--v-theme-on-surface), 0.13);
  border-radius: 16px;
  overflow: hidden;
  background: rgb(var(--v-theme-surface));
}
.path-features {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.1);
  background: rgb(var(--v-theme-on-surface), 0.025);
}
.pulse-feature {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 7px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  text-align: left;
  background: transparent;
}
.pulse-feature:hover:enabled {
  border-color: rgb(var(--v-theme-on-surface), 0.45);
}
.pulse-feature--enabled {
  border-color: rgb(var(--v-theme-success), 0.45);
  background: rgb(var(--v-theme-success), 0.08);
}
.pulse-feature--selected {
  outline: 2px solid rgb(var(--v-theme-on-surface), 0.45);
  outline-offset: 2px;
}
.pulse-feature--error {
  border-color: rgb(var(--v-theme-error));
}
.pulse-feature:focus-visible {
  outline: 2px solid rgb(var(--v-theme-on-surface));
  outline-offset: 3px;
}
.pulse-feature:disabled {
  opacity: 0.5;
}
.pulse-feature-name {
  flex: 1;
  min-width: 0;
  font-size: 0.8rem;
  font-weight: 500;
}
.feature-state {
  flex-shrink: 0;
  font-size: 0.65rem;
  color: rgb(var(--v-theme-on-surface), 0.65);
}
.step-list {
  min-height: 12px;
}
.step-row {
  --activity-color: var(--v-theme-primary);
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 12px 8px 12px 4px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.07);
  border-left: 3px solid transparent;
  background: rgb(var(--activity-color), 0.06);
}
.step-row--survey {
  --activity-color: 103, 58, 183;
}
.step-row--active {
  background: rgb(var(--activity-color), 0.12);
  border-left-color: rgb(var(--activity-color));
}
.step-row--error {
  border-left-color: rgb(var(--v-theme-error));
}
.step-row--ghost {
  opacity: 0.4;
}
.step-handle {
  color: rgb(var(--v-theme-on-surface), 0.35);
  cursor: grab;
}
.step-select {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  min-width: 0;
  flex: 1;
  text-align: left;
  border-radius: 6px;
  padding: 3px 1px;
}
.step-select:focus-visible {
  outline: 2px solid rgb(var(--activity-color));
  outline-offset: 3px;
}
.step-number {
  display: grid;
  place-items: center;
  flex-shrink: 0;
  width: 25px;
  height: 25px;
  border-radius: 8px;
  background: rgb(var(--activity-color), 0.12);
  font-size: 0.75rem;
  font-weight: 700;
}
.step-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.step-copy strong {
  font-size: 0.82rem;
  overflow-wrap: anywhere;
}
.step-copy > span {
  font-size: 0.69rem;
  opacity: 0.7;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 225px;
}
.step-copy .step-challenge {
  color: rgb(var(--v-theme-on-surface));
  opacity: 0.85;
}
.sidebar-add {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px;
  border-bottom: 1px solid rgb(var(--v-theme-on-surface), 0.1);
}
.sidebar-empty {
  padding: 30px 18px;
  text-align: center;
  color: rgb(var(--v-theme-on-surface), 0.6);
}
.step-details {
  min-width: 0;
  padding: 24px 28px 32px;
  border: 1px solid rgb(var(--v-theme-on-surface), 0.13);
  border-radius: 16px;
  background: rgb(var(--v-theme-surface));
}
.activity-scroll:focus-visible,
.step-details:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: -3px;
}
.detail-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.detail-heading h2:focus {
  outline: none;
}
.task-source {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgb(var(--v-theme-on-surface), 0.035);
}
.task-source strong,
.task-source span {
  display: block;
  font-size: 0.75rem;
  overflow-wrap: anywhere;
}
.task-source span {
  opacity: 0.6;
  font-size: 0.7rem;
  margin-top: 2px;
}
.detail-empty {
  min-height: 440px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 30px;
}
.mobile-back {
  display: none;
}
@media (min-width: 761px) and (min-height: 600px) {
  .path-editor {
    display: flex;
    flex-direction: column;
    height: calc(100dvh - var(--v-layout-top, 0px) - var(--v-layout-bottom, 0px));
  }
  .path-editor > :not(.editor-grid) {
    flex-shrink: 0;
  }
  .editor-header {
    position: static;
  }
  .editor-grid {
    flex: 1;
    min-height: 0;
    grid-template-rows: minmax(0, 1fr);
    align-items: stretch;
  }
  .path-sidebar {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  .path-features,
  .sidebar-add {
    flex-shrink: 0;
  }
  .activity-scroll {
    flex: 1;
    min-height: 0;
  }
  .activity-scroll,
  .step-details {
    overflow-y: auto;
    overscroll-behavior-y: contain;
    scrollbar-gutter: stable;
  }
}
@media (max-width: 1000px) {
  .editor-header {
    flex-wrap: wrap;
    position: static;
  }
  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }
  .save-state {
    flex-basis: auto;
    margin-left: auto;
  }
  .header-title {
    flex-basis: 100%;
  }
  .editor-grid {
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 16px;
  }
  .step-details {
    padding: 20px;
  }
}
@media (max-width: 760px) {
  .editor-grid {
    display: block;
  }
  .step-details {
    display: none;
  }
  .editor-grid--detail .path-sidebar {
    display: none;
  }
  .editor-grid--detail .step-details {
    display: block;
  }
  .mobile-back {
    display: inline-flex;
  }
  .step-copy > span {
    max-width: 65vw;
  }
  .header-actions {
    gap: 4px;
  }
  .save-state {
    text-align: left;
  }
  .task-source {
    flex-wrap: wrap;
  }
}

.category-minimum {
  flex: 0 0 110px;
}
</style>
