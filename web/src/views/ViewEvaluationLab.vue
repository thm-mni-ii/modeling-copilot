<template>
  <div class="lab-page">
    <header class="lab-header">
      <div class="lab-identity">
        <div class="lab-symbol"><v-icon icon="mdi-flask-outline" size="26" /></div>
        <div>
          <h1 class="text-h6 font-weight-bold">Evaluation Lab</h1>
          <p class="text-body-2 text-medium-emphasis mb-0">Matching decisions and workflow analysis</p>
        </div>
      </div>
      <v-chip v-if="replayRunning" color="info" size="small" variant="tonal" prepend-icon="mdi-progress-clock" @click="openActiveRun">Test run in progress</v-chip>
    </header>
    <div class="lab-layout">
      <aside class="lab-sidebar" :class="{ 'lab-sidebar--expanded': sidebarExpanded }" aria-label="Evaluation Lab navigation">
        <div class="lab-context-row">
          <button type="button" class="lab-context" :disabled="!tasks.length || saving" aria-label="Change task and release" @click="openContext">
            <v-icon icon="mdi-clipboard-text-outline" size="20" />
            <span class="lab-context-copy">
              <span class="lab-eyebrow">Task / Release</span>
              <strong>{{ task?.name ?? 'Choose a task' }}</strong>
              <span class="text-caption text-medium-emphasis">{{ release ? `Release ${release.versionNumber}` : 'No release selected' }}</span>
            </span>
            <v-icon icon="mdi-swap-horizontal" size="18" />
          </button>
          <v-btn class="lab-browse-button" variant="tonal" size="small" :prepend-icon="sidebarExpanded ? 'mdi-chevron-up' : 'mdi-menu'" :aria-expanded="sidebarExpanded" aria-controls="lab-context-navigation" @click="sidebarExpanded = !sidebarExpanded">Browse</v-btn>
        </div>
        <v-list nav density="compact" class="lab-workspaces" aria-label="Choose a workspace">
          <v-list-item :active="workspaceTab === 'glossary'" color="primary" prepend-icon="mdi-book-alphabet" title="Synonym glossary" subtitle="Terms and matching decisions" @click="chooseWorkspace('glossary')" />
          <v-list-item :active="workspaceTab === 'tests'" color="primary" prepend-icon="mdi-flask-outline" title="Test suite" subtitle="Cases and workflow analysis" @click="chooseWorkspace('tests')" />
          <v-list-item :active="workspaceTab === 'live'" color="primary" prepend-icon="mdi-pencil-ruler" title="Live test" subtitle="Edit, submit and inspect" @click="chooseWorkspace('live')" />
        </v-list>
        <div id="lab-context-navigation" class="lab-sidebar-content">
          <template v-if="workspaceTab === 'glossary'">
            <div class="lab-nav-heading"><h2>Sample solutions</h2><span>{{ solutions.length }}</span></div>
            <v-list nav density="compact" class="lab-nav-list" aria-label="Choose a sample solution">
              <v-list-item v-for="(_solution, index) in solutions" :key="_solution.versionId" :active="solutionIndex === index" :disabled="saving" color="primary" prepend-icon="mdi-vector-square" :title="`Solution ${index + 1}`" @click="selectSolution(index)" />
            </v-list>
            <div class="lab-nav-heading"><h2>Result sources</h2></div>
            <v-list nav density="compact" class="lab-nav-list" aria-label="Original evaluation results">
              <v-list-item :active="outcomeSource === 'original'" color="primary" prepend-icon="mdi-account-school-outline" title="Original evaluations" :subtitle="view ? `${view.signals.evaluated} submissions` : 'Learner results'" :disabled="loading" @click="selectOutcome('original')" />
            </v-list>
            <EvaluationRunList :runs="replays" :selected-id="outcomeSource" :disabled="loading" aria-label="Test run results in the glossary" @select="selectOutcome" />
            <p v-if="!loading && !replays.length" class="text-caption text-medium-emphasis px-4 pb-3">Test runs appear here after you start one in the test suite.</p>
          </template>
          <template v-else-if="workspaceTab === 'tests'">
            <div class="lab-nav-heading"><h2>Test runs</h2><span>{{ replays.length }} saved</span></div>
            <EvaluationRunList :runs="replays" :selected-id="replayId" :disabled="loading" @select="selectReplay" />
            <p v-if="!loading && !replays.length" class="text-caption text-medium-emphasis px-4 pb-3">Start a test run to compare saved submissions.</p>
          </template>
          <p v-else class="text-body-2 text-medium-emphasis px-4 py-3">Live test models belong to your account and this task release. Each evaluation saves the model state it analyzes.</p>
        </div>
        <p class="lab-retention text-caption text-medium-emphasis">Test runs: up to 3 per release, retained for 7 days.</p>
      </aside>
      <section class="lab-main" :aria-label="workspaceTab === 'glossary' ? 'Synonym glossary workspace' : workspaceTab === 'live' ? 'Live test workspace' : 'Test suite workspace'">
    <v-alert v-if="!loading && !tasks.length" type="info" variant="tonal" class="ma-3">No evaluable tasks. A task needs a release with a sample solution.</v-alert>
    <template v-else>
      <div v-if="error || (workspaceTab === 'glossary' && (view?.signals.unavailable || job?.state === 'running' || job?.failed))" class="px-3 pt-2 d-flex flex-column ga-2">
        <v-alert v-if="error" type="error" variant="tonal" density="compact" closable @click:close="error = ''">{{ error }}</v-alert>
        <v-alert v-if="workspaceTab === 'glossary' && view?.signals.unavailable" type="warning" variant="tonal" density="compact">The workflow service is unavailable. Saved glossary entries stay editable, suggestions may be out of date.</v-alert>
        <div v-if="workspaceTab === 'glossary' && job?.state === 'running'" role="status">
          <div class="text-caption">Calculating signals: {{ job.done + job.failed }} of {{ job.total }}. This continues while the view is open.</div>
          <v-progress-linear :model-value="100 * (job.done + job.failed) / Math.max(job.total, 1)" color="primary" />
        </div>
        <v-alert v-else-if="workspaceTab === 'glossary' && job?.failed" type="warning" variant="tonal" density="compact">{{ job.failed }} of {{ job.total }} submissions could not be calculated. They stay missing until you calculate them again.</v-alert>
      </div>
      <v-progress-linear v-if="loading" indeterminate />
      <section v-if="workspaceTab === 'glossary'" class="lab-workspace">
        <header class="workspace-heading">
          <div class="workspace-title">
            <h2 class="text-subtitle-1 font-weight-bold" tabindex="-1" data-workspace-heading>Synonym glossary</h2>
            <p class="text-caption text-medium-emphasis mb-0">Solution {{ solutionIndex + 1 }} / {{ glossaryResultLabel }}</p>
          </div>
          <template v-if="view">
            <v-chip size="small" variant="tonal" :color="outcomeSource === 'original' ? undefined : 'info'">{{ outcomeSource === 'original' ? `${view.signals.evaluated} submissions` : `${glossaryReplay?.items.length ?? 0} test cases` }}</v-chip>
            <v-btn v-if="outcomeSource === 'original'" size="small" variant="tonal" prepend-icon="mdi-calculator-variant-outline" :disabled="!view.signals.missing || jobRunning" :loading="starting" @click="recalculate('missing')">Calculate missing ({{ view.signals.missing }})</v-btn>
            <v-menu>
              <template #activator="{ props: menu }"><v-btn v-bind="menu" size="small" variant="text" icon="mdi-dots-vertical" aria-label="Glossary actions" /></template>
              <v-list density="compact">
                <v-list-item :disabled="jobRunning || !view.signals.evaluated" title="Recalculate all original signals" prepend-icon="mdi-refresh" @click="confirmAll = true" />
                <v-list-item :disabled="!importSources.length" title="Import from another release" prepend-icon="mdi-import" @click="openImport" />
                <v-list-item v-if="glossaryReplay" title="Analyze this test run" prepend-icon="mdi-flask-outline" @click="analyzeGlossaryRun" />
              </v-list>
            </v-menu>
          </template>
        </header>
      <div ref="splitContainer" class="glossary-layout pa-3" :style="{ '--model-width': `${modelWidth}%` }">
        <SubmissionReviewCanvas
          v-if="modelPackage" ref="canvas" class="glossary-canvas" :package="modelPackage" :marks="marks" :selected-cell-id="selectedId"
          show-feedback hide-feedback-toggle hide-view-controls aria-label="Read-only sample solution" @select="selectCell" @overlay="(_keys, cellId) => selectCell(cellId)"
        />
        <div v-if="modelPackage && view" class="split-handle" role="separator" tabindex="0" aria-label="Resize model and glossary" aria-orientation="vertical" :aria-valuenow="Math.round(modelWidth)" :aria-valuemin="15" :aria-valuemax="70" @pointerdown="startResize" @pointermove="resizePanels" @pointerup="stopResize" @pointercancel="stopResize" @lostpointercapture="resizing = false" @keydown="resizeWithKeyboard"><v-icon icon="mdi-drag-vertical" size="small" /></div>
        <aside v-if="view" class="glossary-panel" aria-label="Synonyms">
          <div class="d-flex align-center flex-wrap ga-2 px-3 py-2 border-b">
            <v-icon icon="mdi-source-branch" size="small" />
            <span class="text-body-2">{{ matchingSources.length }} additional sources</span>
            <v-chip size="x-small" variant="tonal" :color="matchingSources.length ? 'info' : undefined">{{ workloadLabel }}</v-chip>
            <v-tooltip :text="workloadNote"><template #activator="{ props: tip }"><v-icon v-bind="tip" icon="mdi-information-outline" size="small" aria-label="How comparison effort is estimated" /></template></v-tooltip>
            <v-btn size="x-small" variant="text" @click="tab = 'sources'">Manage sources</v-btn>
          </div>
          <v-tabs v-model="tab" density="compact" aria-label="Glossary section">
            <v-tab value="selected">Element</v-tab>
            <v-tab value="all">Terms ({{ reviewTerms.length }})</v-tab>
            <v-tab value="results">Results ({{ activeOutcomes.length }})</v-tab>
            <v-tab value="sources">Sources ({{ matchingSources.length }})</v-tab>
          </v-tabs>
          <v-divider />
          <v-window v-model="tab" class="panel-body">
            <v-window-item value="selected" class="pa-3">
              <p v-if="!selectedId" class="text-body-2 text-medium-emphasis">Select an element or connection in the model.</p>
              <v-alert v-else-if="!selectedElement" type="info" variant="tonal" density="compact">This item is not compared, so it has no synonyms.</v-alert>
              <template v-else>
                <div class="text-subtitle-2">{{ selectedPath || selectedElement.label }}</div>
                <div class="text-caption text-medium-emphasis mb-3">{{ selectedElement.targetKind }} · {{ selectedElement.type }}</div>
                <v-form class="d-flex flex-wrap align-start ga-2 mb-3" @submit.prevent="addTerm('accepted')">
                  <v-text-field v-model="newTerm" label="Add synonym" density="compact" maxlength="256" hide-details="auto" :error-messages="newTermError" class="flex-grow-1 term-field" />
                  <v-btn color="primary" type="submit" :disabled="!newTerm.trim() || saving">Accept</v-btn>
                  <v-btn variant="tonal" :disabled="!newTerm.trim() || saving" @click="addTerm('rejected')">Reject</v-btn>
                </v-form>
                <v-data-table :headers="headers" :items="rows" item-value="key" :items-per-page="-1" hide-default-footer disable-sort density="compact">
                  <template #item="{ item }">
                    <tr v-if="item.header" class="section-row">
                      <td :colspan="headers.length">
                        <v-btn v-if="item.section === 'ignored'" variant="text" size="small" :prepend-icon="showIgnored ? 'mdi-chevron-down' : 'mdi-chevron-right'" :aria-expanded="showIgnored" @click="showIgnored = !showIgnored">Ignored ({{ item.count }})</v-btn>
                        <strong v-else class="text-body-2">{{ item.title }} ({{ item.count }})</strong>
                      </td>
                    </tr>
                    <tr v-else>
                      <td>
                        <div>{{ item.term }}</div>
                        <v-chip v-if="item.entry?.matchingSource" size="x-small" prepend-icon="mdi-source-branch" variant="tonal">Matching source</v-chip>
                        <div v-if="item.suggestion && item.suggestion.variants.length > 1" class="text-caption text-medium-emphasis">Variants: {{ item.suggestion.variants.map((variant) => `${variant.text} (${variant.count})`).join(', ') }}</div>
                        <div v-if="item.suggestion" class="text-caption text-medium-emphasis">{{ item.suggestion.submissions }} {{ item.suggestion.submissions === 1 ? 'case' : 'cases' }}</div>
                      </td>
                      <td class="reason-cell"><GlossaryConditionGroups :comparisons="item.suggestion?.comparisons ?? comparisonsOf(item.entry)" :outcome="outcomeOf(item.suggestion ?? item.entry)" /></td>
                      <td><GlossaryDecisionActions :status="item.entry?.status" :matching-source="item.entry?.matchingSource" :disabled="saving" @decide="item.suggestion ? decide(item.suggestion, $event) : change(item.entry!, $event)" @source="setMatchingSource(item.entry!, !item.entry!.matchingSource)" @remove="change(item.entry!, null)" /></td>
                    </tr>
                  </template>
                  <template #no-data>No synonyms yet.</template>
                </v-data-table>
              </template>
            </v-window-item>

            <v-window-item value="all" class="pa-3">
              <div class="d-flex flex-wrap ga-2 mb-3">
                <v-text-field v-model.number="minPersons" type="number" min="0" label="Min Case" density="compact" hide-details class="filter-field" />
                <v-checkbox v-model="excludeStaff" label="Exclude moderator/admin submissions" density="compact" hide-details />
                <v-select v-model="typeFilter" :items="typeItems" label="Element type" density="compact" hide-details clearable class="filter-field-wide" />
              </div>
              <v-data-table v-model:sort-by="termSort" :headers="allHeaders" :items="filteredSuggestions" :item-value="suggestionKey" :items-per-page="25" density="compact">
                <template #item="{ item }">
                  <tr :class="{ 'selected-row': item.referenceElementId === selectedId }">
                    <td><v-btn variant="text" size="small" class="text-none px-1" @click="selectCell(item.referenceElementId)">{{ elementsById.get(item.referenceElementId)?.label }}</v-btn></td>
                    <td>{{ item.term }}<v-chip v-if="item.evidence?.hintAccepted" size="x-small" color="info" variant="tonal" label class="ms-1" title="Learners accepted this term from a hint; it still needs your decision.">accepted from hint ×{{ item.evidence.hintAccepted }}</v-chip></td><td>{{ item.submissions }} {{ item.submissions === 1 ? 'case' : 'cases' }}</td>
                    <td class="reason-cell"><GlossaryConditionGroups :comparisons="item.comparisons" :outcome="outcomeOf(item)" /></td>
                    <td><GlossaryDecisionActions :status="findEntry(item)?.status" :matching-source="findEntry(item)?.matchingSource" :disabled="saving" @decide="decide(item, $event)" @source="toggleSource(item)" @remove="removeTerm(item)" /></td>
                  </tr>
                </template>
                <template #no-data>{{ view.signals.collected ? 'No open suggestions.' : 'No suggestions yet. Calculate missing signals to analyze earlier submissions.' }}</template>
              </v-data-table>
            </v-window-item>
            <v-window-item value="results" class="pa-3">
              <p class="text-caption text-medium-emphasis mb-3">All recorded terms, including counted matches. Decisions apply to future evaluations.</p>
              <v-data-table :headers="outcomeHeaders" :items="activeOutcomes" :item-value="suggestionKey" :items-per-page="25" density="compact">
                <template #[`item.element`]="{ item }"><v-btn variant="text" size="small" class="text-none px-1" @click="selectCell(item.referenceElementId)">{{ elementsById.get(item.referenceElementId)?.label ?? item.referenceElementId }}</v-btn></template>
                <template #[`item.similarity`]="{ item }"><GlossaryConditionGroups :comparisons="item.comparisons" :outcome="item" /></template>
                <template #[`item.actions`]="{ item }"><GlossaryDecisionActions :status="entryOf(item)?.status" :matching-source="entryOf(item)?.matchingSource" :disabled="saving" @decide="decideTerm(item, $event)" @source="toggleSource(item)" @remove="removeTerm(item)" /></template>
                <template #no-data>No verified final results for these terms yet.</template>
              </v-data-table>
            </v-window-item>
            <v-window-item value="sources" class="pa-3">
              <p class="text-caption text-medium-emphasis mb-3">Enabled terms are compared alongside the original element names in future evaluations.</p>
              <v-data-table :headers="sourceHeaders" :items="matchingSources" item-value="id" :items-per-page="10" density="compact">
                <template #[`item.element`]="{ item }"><v-btn variant="text" size="small" class="text-none px-1" @click="selectCell(item.referenceElementId); tab = 'selected'">{{ elementsById.get(item.referenceElementId)?.label ?? item.referenceElementId }}</v-btn></template>
                <template #[`item.actions`]="{ item }"><v-btn size="small" variant="text" :disabled="saving" @click="setMatchingSource(item, false)">Disable source</v-btn></template>
                <template #no-data>No extra matching sources enabled. Select an accepted synonym to enable one explicitly.</template>
              </v-data-table>
            </v-window-item>
          </v-window>
        </aside>
      </div>
      </section>
    </template>

    <section v-show="workspaceTab === 'tests' && tasks.length" class="lab-workspace suite-workspace" aria-label="Workflow test suite">
        <v-alert v-if="replayError" type="error" variant="tonal" density="compact" class="ma-3 mb-0">{{ replayError }}<v-btn size="small" variant="text" @click="refreshReplays">Retry</v-btn></v-alert>
        <template v-if="selectedReplay">
          <header class="suite-run-header workspace-heading">
            <div class="d-flex flex-wrap align-center ga-2">
              <div class="flex-grow-1">
                <h2 class="text-subtitle-1 font-weight-bold" tabindex="-1" data-workspace-heading>Test suite</h2>
                <p class="text-caption text-medium-emphasis mb-0">Test run / {{ formatDate(selectedReplay.createdAt) }}</p>
              </div>
              <v-btn color="primary" size="small" prepend-icon="mdi-plus" :disabled="loading || replayRunning" @click="newRunOpen = true">New test run</v-btn>
              <v-chip :color="selectedReplay.state === 'running' ? 'info' : replayCounts.failed ? 'warning' : 'success'" size="small" variant="tonal">{{ selectedReplay.state === 'running' ? 'Running' : replayCounts.failed ? 'Completed with failures' : 'Completed' }}</v-chip>
              <v-btn variant="text" size="small" icon="mdi-refresh" aria-label="Refresh selected run" @click="replayError = ''; poll(true)" />
              <v-menu>
                <template #activator="{ props: menu }"><v-btn v-bind="menu" size="small" variant="text" icon="mdi-dots-vertical" aria-label="Test run actions" /></template>
                <v-list density="compact">
                  <v-list-item title="View run settings" prepend-icon="mdi-tune" @click="runSettingsOpen = true" />
                  <v-list-item title="Show term results in glossary" prepend-icon="mdi-book-alphabet" @click="showGlossaryResults" />
                  <v-list-item title="Delete test run" prepend-icon="mdi-delete-outline" base-color="error" :disabled="selectedReplay.state === 'running'" @click="deleteReplayId = selectedReplay.id" />
                </v-list>
              </v-menu>
            </div>
            <div class="d-flex flex-wrap align-center ga-4 text-caption mt-2" role="status">
              <span>{{ selectedReplay.items.length }} cases</span>
              <span>{{ replayCounts.done }} completed</span>
              <span v-if="replayCounts.running">{{ replayCounts.running }} running</span>
              <span v-if="replayCounts.pending">{{ replayCounts.pending }} queued</span>
              <span v-if="replayCounts.failed" class="text-error font-weight-medium">{{ replayCounts.failed }} failed</span>
            </div>
            <p v-if="selectedReplay.state === 'running'" class="text-caption text-medium-emphasis mt-2 mb-0">Keep the Lab open to process queued cases.</p>
            <v-progress-linear v-if="selectedReplay.state === 'running'" :model-value="100 * (replayCounts.done + replayCounts.failed) / Math.max(selectedReplay.items.length, 1)" class="mt-2" aria-label="Processed test cases" />
          </header>
          <v-alert v-if="selectedReplay.unavailable" type="warning" variant="tonal" density="compact" class="ma-3 mb-0">The workflow service is unavailable. Saved results remain available; execution resumes when it can be reached.</v-alert>

          <section v-if="!inspectionId" class="suite-cases pa-3" aria-label="Test cases in this run">
            <div class="d-flex flex-wrap align-center ga-3 mb-3">
              <h3 class="suite-cases-heading text-subtitle-2" tabindex="-1">Test cases</h3>
              <v-spacer />
              <v-select v-model="caseStatus" :items="caseStatusOptions" label="Status" density="compact" hide-details class="case-status-filter" />
            </div>
            <v-data-table v-model:page="casePage" v-model:sort-by="caseSort" :headers="replayHeaders" :items="filteredReplayItems" item-value="runId" :items-per-page="10" density="comfortable">
              <template #[`item.modelName`]="{ item }">
                <v-btn variant="text" class="case-name text-none px-0" :data-case-id="item.evaluationId" @click="openInspection(item.evaluationId)">{{ caseName(item.modelVersionId) }}</v-btn>
                <div class="text-caption text-medium-emphasis" :title="item.modelVersionId">Version {{ item.modelVersionId.slice(0, 8) }}</div>
              </template>
              <template #[`item.status`]="{ item }"><v-chip :color="caseStatusColor(item.status)" size="small" variant="tonal">{{ caseStatusLabel(item.status) }}</v-chip><div v-if="item.error" class="case-error text-caption text-error mt-1">{{ item.error }}</div></template>
              <template #[`item.beforePercent`]="{ item }">{{ percentText(item.beforePercent) }}</template>
              <template #[`item.afterPercent`]="{ item }">{{ percentText(item.afterPercent) }}</template>
              <template #[`item.delta`]="{ item }">{{ deltaText(item.beforePercent, item.afterPercent) }}</template>
              <template #[`item.actions`]="{ item }"><v-btn size="small" variant="tonal" append-icon="mdi-arrow-right" @click="openInspection(item.evaluationId)">Analyze</v-btn></template>
              <template #no-data>No cases with this status. Choose another status to see the other cases.</template>
            </v-data-table>
            <p class="text-caption text-medium-emphasis mt-2">Recognition shows the best result across all sample solutions. Changes are in percentage points.</p>
          </section>

          <template v-else>
            <div class="suite-case-navigation d-flex flex-wrap align-center ga-2 px-3 py-2 border-b">
              <v-btn variant="text" size="small" prepend-icon="mdi-arrow-left" @click="closeInspection">All test cases</v-btn>
              <v-spacer />
              <v-select :model-value="inspectionId" :items="inspectionOptions" label="Test case" density="compact" hide-details class="case-select" @update:model-value="openInspection" />
              <span class="text-caption text-medium-emphasis">{{ inspectionIndex + 1 }} / {{ selectedReplay.items.length }}</span>
              <v-btn icon="mdi-chevron-left" variant="text" size="small" aria-label="Previous test case" :disabled="inspectionIndex <= 0" @click="stepInspection(-1)" />
              <v-btn icon="mdi-chevron-right" variant="text" size="small" aria-label="Next test case" :disabled="inspectionIndex >= selectedReplay.items.length - 1" @click="stepInspection(1)" />
            </div>
            <section ref="inspectionContainer" tabindex="-1" class="suite-analysis" aria-label="Selected test case analysis">
              <v-progress-linear v-if="inspectionLoading" indeterminate aria-label="Loading run analysis" />
              <v-alert v-if="inspectionError" type="error" variant="tonal" density="compact" class="ma-3">{{ inspectionError }}<v-btn size="small" variant="text" @click="loadInspection()">Retry</v-btn></v-alert>
              <EvaluationRunAnalysis v-if="inspectionDetail" :key="`${replayId}:${inspectionId}`" v-model:model-width="testModelWidth" :detail="inspectionDetail" />
            </section>
          </template>
        </template>
        <div v-else class="suite-empty pa-6">
          <v-icon icon="mdi-flask-outline" size="40" color="medium-emphasis" />
          <h2 class="text-h6 mt-3" tabindex="-1" data-workspace-heading>Test the evaluation workflow</h2>
          <p class="text-body-2 text-medium-emphasis mt-2 mb-4">Choose saved submissions, run an evaluation and inspect each case alongside its model.</p>
          <v-btn color="primary" prepend-icon="mdi-plus" :disabled="loading || !solutionRef" @click="newRunOpen = true">New test run</v-btn>
        </div>
    </section>
    <EvaluationLiveTest v-if="liveOpened && taskId && releaseId" v-show="workspaceTab === 'live'" ref="liveTest" :task-id="taskId" :release-id="releaseId" :task-name="task?.name ?? 'Task'" />
      </section>
    </div>

    <v-dialog v-model="contextOpen" max-width="560" scrollable>
      <v-card title="Choose a task and release">
        <v-card-text>
          <v-alert v-if="contextError" type="error" variant="tonal" density="compact" class="mb-3">{{ contextError }}</v-alert>
          <p class="text-body-2 text-medium-emphasis mb-4">Glossary decisions and test runs belong to the selected release.</p>
          <v-autocomplete v-model="contextTaskId" :items="tasks" item-title="name" item-value="id" label="Task" density="comfortable" hide-details class="mb-4" />
          <v-select v-model="contextReleaseId" :items="contextReleaseItems" label="Release" density="comfortable" hide-details :disabled="!contextTaskId" />
        </v-card-text>
        <v-card-actions class="px-4 pb-4">
          <v-spacer /><v-btn @click="contextOpen = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :disabled="!contextReleaseItems.some(item => item.value === contextReleaseId)" @click="applyContext">Open workspace</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="newRunOpen" max-width="1100" scrollable :persistent="replayStarting">
      <v-card title="New test run">
        <v-card-text>
          <p class="text-body-2 mb-4">Select submissions for {{ task?.name }} · Release {{ release?.versionNumber }}. The run uses the current glossary and leaves learner results unchanged.</p>
          <v-alert v-if="replayError" type="error" variant="tonal" density="compact" class="mb-3">{{ replayError }}</v-alert>
          <div class="d-flex flex-wrap align-center ga-3 mb-3">
            <v-text-field v-model="candidateSearch" label="Find a submission" prepend-inner-icon="mdi-magnify" density="compact" hide-details clearable />
            <v-checkbox v-model="studentCasesOnly" label="Student submissions only" density="compact" hide-details :disabled="replayStarting" />
            <v-btn variant="text" size="small" :loading="candidatesLoading" :disabled="replayStarting" @click="loadCandidates">Refresh</v-btn>
          </div>
          <v-data-table v-model="selectedCases" :headers="candidateHeaders" :items="visibleCandidates" :search="candidateSearch ?? ''" item-value="evaluationId" :items-per-page="10" density="compact" :loading="candidatesLoading" :show-select="!replayStarting">
            <template #[`item.modelVersionId`]="{ item }"><span :title="item.modelVersionId">{{ item.modelVersionId.slice(0, 8) }}</span></template>
            <template #[`item.startedAt`]="{ item }">{{ formatDate(item.startedAt) }}</template>
            <template #[`item.state`]="{ item }">{{ caseStatusLabel(item.state) }}</template>
            <template #no-data>{{ candidates.length ? 'No submissions match these filters.' : 'No saved submissions yet. Cases appear after an evaluation has been requested, including failed attempts.' }}</template>
          </v-data-table>
          <div class="d-flex flex-wrap align-center ga-3 mt-3">
            <v-switch v-model="customThresholds" label="Customize similarity thresholds" density="compact" hide-details :disabled="replayStarting" />
            <span v-if="!customThresholds" class="text-caption text-medium-emphasis">Workflow defaults</span>
          </div>
          <div v-if="customThresholds" class="d-flex flex-wrap ga-3 mt-3">
            <v-text-field v-model.number="thresholds.spelling" type="number" min="0" max="1" step="0.01" label="Spelling (0–1)" density="compact" hide-details :disabled="replayStarting" class="threshold-field" />
            <v-text-field v-model.number="thresholds.meaning" type="number" min="0" max="1" step="0.01" label="Meaning (0–1)" density="compact" hide-details :disabled="replayStarting" class="threshold-field" />
            <v-text-field v-model.number="thresholds.meaningFloor" type="number" min="0" max="1" step="0.01" label="Meaning floor (0–meaning)" density="compact" hide-details :disabled="replayStarting" class="threshold-field" />
          </div>
          <v-alert v-if="!thresholdsValid" type="warning" variant="tonal" density="compact" class="mt-3">Use values between 0 and 1. The meaning floor must not exceed the meaning threshold.</v-alert>
          <v-alert v-if="selectedCases.length > 500" type="warning" variant="tonal" density="compact" class="mt-3">Select at most 500 cases per run.</v-alert>
          <v-alert v-if="replayRunning" type="info" variant="tonal" density="compact" class="mt-3">A test run is already active for this release. Your selection is kept until you can start another.</v-alert>
        </v-card-text>
        <v-card-actions class="px-4 py-3 border-t">
          <span class="text-body-2" role="status">{{ selectedCases.length }} cases selected</span>
          <v-spacer />
          <v-btn :disabled="replayStarting" @click="newRunOpen = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" :loading="replayStarting" :disabled="replayRunning || !thresholdsValid || !selectedCases.length || selectedCases.length > 500" @click="startReplay">Start test run</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="runSettingsOpen" max-width="560" scrollable>
      <v-card v-if="selectedReplay" title="Test run settings">
        <v-card-text>
          <dl class="run-settings">
            <dt>Workflow</dt><dd>{{ selectedReplay.workflowName }} {{ selectedReplay.workflowVersion }}</dd>
            <dt>Spelling threshold</dt><dd>{{ selectedReplay.textEvidence?.spelling ?? 'Workflow default' }}</dd>
            <dt>Meaning threshold</dt><dd>{{ selectedReplay.textEvidence?.meaning ?? 'Workflow default' }}</dd>
            <dt>Meaning floor</dt><dd>{{ selectedReplay.textEvidence?.meaningFloor ?? 'Workflow default' }}</dd>
            <dt>Expires</dt><dd>{{ formatDate(selectedReplay.expiresAt) }}</dd>
          </dl>
          <p class="text-caption text-medium-emphasis mt-4 mb-0">The glossary was frozen when this run started. Temporary workspace files are removed after execution; workflow logs and artifacts expire after 7 days.</p>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="runSettingsOpen = false">Close</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog :model-value="!!deleteReplayId" max-width="460" @update:model-value="!$event && (deleteReplayId = null)">
      <v-card title="Delete comparison?">
        <v-card-text>The saved comparison and its term results will be removed. Original evaluations and glossary decisions stay unchanged.</v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="deleteReplayId = null">Cancel</v-btn><v-btn color="error" :loading="replayDeleting" @click="deleteReplay">Delete</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="confirmAll" max-width="480">
      <v-card title="Recalculate all signals?">
        <v-card-text>All {{ view?.signals.evaluated }} evaluated submissions are processed again from their frozen snapshots. Results and learner feedback do not change.</v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="confirmAll = false">Cancel</v-btn><v-btn color="primary" @click="confirmAll = false; recalculate('all')">Recalculate all</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog :model-value="!!applying" max-width="520" @update:model-value="!$event && !saving && (applying = null)">
      <v-card v-if="applying" :title="`Accept ${applying.term}`">
        <v-card-text>
          <p class="text-caption">Same name, multiple positions:</p>
          <v-checkbox v-for="element in acceptanceTargets" :key="element.id" v-model="acceptanceSelection" :value="element.id" :label="canvas?.pathOf(element.id) || element.label" :disabled="saving" density="compact" hide-details />
        </v-card-text>
        <v-card-actions><v-btn :disabled="saving" @click="applying = null">Cancel</v-btn><v-spacer /><v-btn :disabled="saving" @click="applySameNamed(true)">Accept all</v-btn><v-btn color="primary" :loading="saving" :disabled="!acceptanceSelection.length || saving" @click="applySameNamed(false)">Accept selected</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="importOpen" max-width="480">
      <v-card title="Import decisions">
        <v-card-text>
          <v-select v-model="importFrom" :items="importSources" label="From release" density="compact" />
          <p class="text-body-2">Only entries whose element and label are unchanged are imported. The rest is listed afterwards.</p>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="importOpen = false">Cancel</v-btn><v-btn color="primary" :disabled="!importFrom" @click="runImport">Import</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-snackbar v-model="snackbar" :timeout="8000">
      {{ snackbarText }}
      <template #actions><v-btn v-if="undoChanges" variant="text" @click="undo">Undo</v-btn></template>
    </v-snackbar>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SubmissionReviewCanvas, { type ReviewCanvasMark } from '@/components/submissions/SubmissionReviewCanvas.vue'
import GlossaryConditionGroups from '@/components/submissions/GlossaryConditionGroups.vue'
import GlossaryDecisionActions from '@/components/submissions/GlossaryDecisionActions.vue'
import EvaluationRunAnalysis from '@/components/submissions/EvaluationRunAnalysis.vue'
import EvaluationRunList from '@/components/submissions/EvaluationRunList.vue'
import EvaluationLiveTest from '@/components/submissions/EvaluationLiveTest.vue'
import type { EvaluationDetail } from '@/services/api/types/evaluation'
import languageService from '@/services/language/language.service'
import taskService from '@/services/task/task.service'
import { synonymGlossary, type EntryStatus, type EvaluableTask, type GlossaryChange, type GlossaryElement, type GlossaryEntry, type GlossaryView, type RecalculateScope, type SolutionRef, type Suggestion, type ReplayBatch, type ReplayCandidate, type TermOutcome, type TextEvidence } from '@/services/synonymGlossary'
import type { DiagramLanguage } from '@/model/DiagramLanguage'
import type { LanguageVersionReference } from '@/services/api/types/common'
import type { ModelPackage, PackagedLanguage } from '@/utils/modelPackage'

type Section = 'suggested' | 'accepted' | 'rejected' | 'ignored'
interface Row { key: string; header?: boolean; section: Section; title?: string; count?: number; term?: string; status?: string; origin?: string; suggestion?: Suggestion; entry?: GlossaryEntry }

const statuses: EntryStatus[] = ['accepted', 'rejected', 'ignored']
const headers = [{ title: 'Term', key: 'term' }, { title: 'Evidence', key: 'evidence', sortable: false }, { title: 'Actions', key: 'actions', sortable: false }]
const allHeaders = [{ title: 'Element', key: 'element', value: (item: { referenceElementId?: string }) => elementsById.value.get(item.referenceElementId ?? '')?.label ?? '' }, { title: 'Term', key: 'term' }, { title: 'Cases', key: 'submissions' }, { title: 'Evidence', key: 'evidence', sortable: false }, { title: 'Actions', key: 'actions', sortable: false }]
const outcomeHeaders = [{ title: 'Element', key: 'element', value: (item: { referenceElementId?: string }) => elementsById.value.get(item.referenceElementId ?? '')?.label ?? '' }, { title: 'Term', key: 'term' }, { title: 'Evidence', key: 'similarity', sortable: false }, { title: 'Actions', key: 'actions', sortable: false }]
const sourceHeaders = [{ title: 'Reference element', key: 'element', sortable: false }, { title: 'Additional source', key: 'term' }, { title: 'Actions', key: 'actions', sortable: false }]
const replayHeaders = [{ title: 'Submission', key: 'modelName' }, { title: 'Status', key: 'status' }, { title: 'Original', key: 'beforePercent' }, { title: 'Test run', key: 'afterPercent' }, { title: 'Change', key: 'delta', sortable: false }, { title: '', key: 'actions', sortable: false }]
const candidateHeaders = [{ title: 'Model', key: 'modelName' }, { title: 'Version', key: 'modelVersionId' }, { title: 'Last evaluation', key: 'startedAt' }, { title: 'Status', key: 'state' }]
const markImage = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"><circle cx="8" cy="8" r="7" fill="#f9a825" stroke="white" stroke-width="1.5"/></svg>')}`

const route = useRoute()
const router = useRouter()
const canvas = ref<InstanceType<typeof SubmissionReviewCanvas>>()
const splitContainer = ref<HTMLDivElement>()
const modelWidth = ref(35)
const testModelWidth = ref(35)
const resizing = ref(false)
const setModelWidth = (value: number) => { modelWidth.value = Math.min(70, Math.max(15, value)) }
const startResize = (event: PointerEvent) => {
  if (event.button !== 0) return
  event.preventDefault()
  resizing.value = true
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
const resizePanels = (event: PointerEvent) => {
  if (!resizing.value || !splitContainer.value) return
  const bounds = splitContainer.value.getBoundingClientRect()
  setModelWidth(100 * (event.clientX - bounds.left - 12) / (bounds.width - 24))
}
const stopResize = (event: PointerEvent) => {
  resizing.value = false
  const target = event.currentTarget as HTMLElement
  if (target.hasPointerCapture(event.pointerId)) target.releasePointerCapture(event.pointerId)
}
const resizeWithKeyboard = (event: KeyboardEvent) => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return
  event.preventDefault()
  setModelWidth(event.key === 'Home' ? 15 : event.key === 'End' ? 70 : modelWidth.value + (event.key === 'ArrowLeft' ? -2 : 2))
}
const tasks = ref<EvaluableTask[]>([])
const taskId = ref<string | null>(null)
const releaseId = ref<string | null>(null)
const contextOpen = ref(false)
const contextError = ref('')
const liveTest = ref<InstanceType<typeof EvaluationLiveTest>>()
const liveOpened = ref(route.query.tab === 'live')
const contextTaskId = ref<string | null>(null)
const contextReleaseId = ref<string | null>(null)
const sidebarExpanded = ref(false)
const solutionIndex = ref(0)
const view = ref<GlossaryView | null>(null)
const modelPackage = ref<ModelPackage | null>(null)
const selectedId = ref<string | null>(null)
const selectedPath = ref('')
const tab = ref('all')
const workspaceTab = ref<'glossary' | 'tests' | 'live'>(route.query.tab === 'live' ? 'live' : route.query.tab === 'tests' ? 'tests' : 'glossary')
const candidates = ref<ReplayCandidate[]>([])
const selectedCases = ref<string[]>([])
const candidateSearch = ref<string | null>('')
const studentCasesOnly = ref(true)
const candidatesLoading = ref(false)
const newRunOpen = ref(false)
const runSettingsOpen = ref(false)
const caseStatus = ref('all')
const casePage = ref(1)
const caseSort = ref<{ key: string; order?: boolean | 'asc' | 'desc' }[]>([])
const caseStatusOptions = [{ title: 'All cases', value: 'all' }, { title: 'Failed', value: 'failed' }, { title: 'Running', value: 'running' }, { title: 'Queued', value: 'pending' }, { title: 'Completed', value: 'done' }]
const visibleCandidates = computed(() => candidates.value.filter(item => !studentCasesOnly.value || !item.staff))
const inspectionId = ref<string | null>(null)
const inspectionContainer = ref<HTMLElement>()
const inspectionDetail = ref<EvaluationDetail | null>(null)
const inspectionLoading = ref(false)
const inspectionError = ref('')
const newTerm = ref('')
const newTermError = ref('')
const showIgnored = ref(false)
const minPersons = ref(0)
const termSort = ref<{ key: string; order?: boolean | 'asc' | 'desc' }[]>([{ key: 'submissions', order: 'desc' }])
const excludeStaff = ref(true)
const typeFilter = ref<string | null>(null)
const loading = ref(false)
const saving = ref(false)
const starting = ref(false)
const error = ref('')
const snackbar = ref(false)
const snackbarText = ref('')
const undoChanges = ref<GlossaryChange[] | null>(null)
const confirmAll = ref(false)
const applying = ref<Suggestion | null>(null)
const acceptanceSelection = ref<string[]>([])
const acceptanceTargets = computed(() => applying.value ? [elementsById.value.get(applying.value.referenceElementId)!, ...sameNamed(applying.value)].filter(Boolean) : [])
const importOpen = ref(false)
const importFrom = ref<string | null>(null)
const replays = ref<ReplayBatch[]>([])
const replayId = ref<string | null>(null)
const replayStarting = ref(false)
const replayDeleting = ref(false)
const replayError = ref('')
const deleteReplayId = ref<string | null>(null)
const outcomeSource = ref('original')
const customThresholds = ref(false)
const thresholds = ref<TextEvidence>({ spelling: 0.85, meaning: 0.85, meaningFloor: 0.7 })
let pollTimer: ReturnType<typeof setTimeout> | undefined
let loadToken = 0
let inspectionToken = 0

const task = computed(() => tasks.value.find((item) => item.id === taskId.value) ?? null)
const release = computed(() => task.value?.releases.find((item) => item.id === releaseId.value) ?? null)
const contextReleaseItems = computed(() => tasks.value.find(item => item.id === contextTaskId.value)?.releases.map(item => ({ title: `Release ${item.versionNumber}`, value: item.id })) ?? [])
const solutions = computed(() => release.value?.sampleSolutions ?? [])
const solutionRef = computed<SolutionRef | null>(() => {
  const solution = solutions.value[solutionIndex.value]
  return solution && taskId.value && releaseId.value ? { taskId: taskId.value, versionId: releaseId.value, modelId: solution.modelId, modelVersionId: solution.versionId } : null
})
const job = computed(() => view.value?.signals.job ?? null)
const jobRunning = computed(() => job.value?.state === 'running')
const replayRunning = computed(() => replays.value.some(item => item.state === 'running'))
const selectedReplay = computed(() => replays.value.find(item => item.id === replayId.value) ?? null)
const replayCounts = computed(() => {
  const counts = { pending: 0, running: 0, done: 0, failed: 0 }
  for (const item of selectedReplay.value?.items ?? []) counts[item.status]++
  return counts
})
const candidatesByVersion = computed(() => new Map(candidates.value.map(item => [item.modelVersionId, item])))
const caseName = (versionId: string) => candidatesByVersion.value.get(versionId)?.modelName ?? 'Saved submission'
const caseStatusLabel = (status: string) => ({ pending: 'Queued', queued: 'Queued', running: 'Running', done: 'Completed', succeeded: 'Completed', failed: 'Failed', cancelled: 'Cancelled', unknown: 'Status unknown' }[status] ?? status)
const caseStatusColor = (status: string) => ({ done: 'success', succeeded: 'success', running: 'info', failed: 'error', cancelled: 'warning' }[status])
const filteredReplayItems = computed(() => (selectedReplay.value?.items ?? [])
  .filter(item => caseStatus.value === 'all' || item.status === caseStatus.value)
  .map(item => ({ ...item, modelName: caseName(item.modelVersionId) })))
const inspectionOptions = computed(() => (selectedReplay.value?.items ?? []).map(item => ({
  title: `${caseName(item.modelVersionId)} / ${item.modelVersionId.slice(0, 8)} / ${caseStatusLabel(item.status)}`, value: item.evaluationId
})))
const inspectionIndex = computed(() => selectedReplay.value?.items.findIndex(item => item.evaluationId === inspectionId.value) ?? -1)
const deltaText = (before: number | null, after: number | null) => before == null || after == null ? 'Not available' : `${after > before ? '+' : ''}${(after - before).toFixed(1)} pp`
const formatDate = (date: string) => new Date(date).toLocaleString()
const glossaryReplay = computed(() => replays.value.find(item => item.id === outcomeSource.value) ?? null)
const glossaryResultLabel = computed(() => glossaryReplay.value ? `Test run ${formatDate(glossaryReplay.value.createdAt)}` : 'Original evaluations')
const openContext = () => {
  contextError.value = ''
  contextTaskId.value = taskId.value
  contextReleaseId.value = releaseId.value
  contextOpen.value = true
}
const focusWorkspace = async () => {
  await nextTick()
  document.querySelector<HTMLElement>('.lab-main [data-workspace-heading]')?.focus({ preventScroll: true })
}
const applyContext = async () => {
  if (!contextTaskId.value || !contextReleaseItems.value.some(item => item.value === contextReleaseId.value)) return
  try { await liveTest.value?.saveChanges() }
  catch (cause) { contextError.value = (cause as Error).message; return }
  taskId.value = contextTaskId.value
  releaseId.value = contextReleaseId.value
  contextOpen.value = false
  sidebarExpanded.value = false
}
const chooseWorkspace = (workspace: 'glossary' | 'tests' | 'live') => {
  if (workspace === 'live') liveOpened.value = true
  workspaceTab.value = workspace
  sidebarExpanded.value = false
  void focusWorkspace()
}
const selectSolution = (index: number) => {
  solutionIndex.value = index
  sidebarExpanded.value = false
  void focusWorkspace()
}
const selectOutcome = (id: string) => {
  outcomeSource.value = id
  sidebarExpanded.value = false
  void focusWorkspace()
}
const selectReplay = (id: string) => {
  replayId.value = id
  sidebarExpanded.value = false
  void focusWorkspace()
}
const showGlossaryResults = () => {
  if (!selectedReplay.value) return
  outcomeSource.value = selectedReplay.value.id
  tab.value = 'results'
  chooseWorkspace('glossary')
}
const analyzeGlossaryRun = () => {
  if (!glossaryReplay.value) return
  replayId.value = glossaryReplay.value.id
  chooseWorkspace('tests')
}
const openActiveRun = () => {
  const running = replays.value.find(item => item.state === 'running')
  if (running) replayId.value = running.id
  chooseWorkspace('tests')
}
const activeOutcomes = computed(() => outcomeSource.value === 'original' ? view.value?.outcomes ?? [] : replays.value.find(item => item.id === outcomeSource.value)?.outcomes ?? [])
const outcomeOf = (item?: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => item ? activeOutcomes.value.find(outcome => outcome.referenceElementId === item.referenceElementId && outcome.termKey === item.termKey) : undefined
const thresholdsValid = computed(() => !customThresholds.value || (Object.values(thresholds.value).every(value => typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1) && thresholds.value.meaningFloor <= thresholds.value.meaning))
const percentText = (value: number | null) => value == null ? 'Unknown' : `${value.toFixed(1)}%`
const elementsById = computed(() => new Map((view.value?.elements ?? []).map((element) => [element.id, element])))
const selectedElement = computed(() => (selectedId.value ? elementsById.value.get(selectedId.value) ?? null : null))
const matchingSources = computed(() => (view.value?.entries ?? []).filter(item => item.status === 'accepted' && item.matchingSource))
const workloadLabel = computed(() => {
  const work = view.value?.matchingWorkload
  if (!work) return 'Effort estimate unavailable'
  const unit = work.basis === 'text_pairs' ? 'comparisons' : 'reference texts'
  const percent = work.percent == null ? '' : ` (+${work.percent.toLocaleString(undefined, { maximumFractionDigits: 1 })}%)`
  return `${work.baseline.toLocaleString()} + ${work.additional.toLocaleString()} = ${work.total.toLocaleString()} ${unit}${percent}`
})
const workloadNote = computed(() => {
  const work = view.value?.matchingWorkload
  return work?.basis === 'text_pairs'
    ? `Baseline + ${work.additional.toLocaleString()} extra text comparisons, based on ${work.covered} of ${work.evaluated} evaluated submissions. Comparison counts, not a runtime forecast.`
    : 'No saved comparison inventory available. This estimate counts original element names plus additional source texts; actual effort depends on submission size.'
})
const marks = computed<ReviewCanvasMark[]>(() => {
  const counts = new Map<string, number>()
  for (const item of view.value?.suggestions ?? []) if (!findEntry(item)) counts.set(item.referenceElementId, (counts.get(item.referenceElementId) ?? 0) + 1)
  return [...counts].map(([cellId, count]) => ({
    key: cellId, cellId, state: 'hint' as const,
    config: { image: { src: markImage, width: 16, height: 16 }, tooltip: `${count} open suggestion${count === 1 ? '' : 's'}`, align: 'right' as const, verticalAlign: 'top' as const, cursor: 'pointer' }
  }))
})
const rows = computed<Row[]>(() => {
  if (!selectedId.value || !view.value) return []
  const suggestions = view.value.suggestions.filter((item) => item.referenceElementId === selectedId.value && !findEntry(item))
  const entries = view.value.entries.filter((item) => item.referenceElementId === selectedId.value)
  const result: Row[] = []
  const section = (name: Section, title: string, items: Row[], open = true) => {
    if (!items.length) return
    result.push({ key: `header:${name}`, header: true, section: name, title, count: items.length })
    if (open) result.push(...items)
  }
  section('suggested', 'Suggested', suggestions.map((item) => ({ key: `s:${item.termKey}`, section: 'suggested', term: item.term, status: 'suggested', suggestion: item })))
  for (const status of statuses) {
    const title = { accepted: 'Accepted', rejected: 'Rejected', ignored: 'Ignored' }[status]
    section(status, title, entries.filter((item) => item.status === status).map((item) => ({ key: `e:${item.id}`, section: status, term: item.term, status, origin: item.origin, entry: item })), status !== 'ignored' || showIgnored.value)
  }
  return result
})
const typeItems = computed(() => [...new Set((view.value?.suggestions ?? []).map((item) => elementsById.value.get(item.referenceElementId)?.type).filter((type): type is string => !!type))].sort())
const reviewTerms = computed<Suggestion[]>(() => {
  const terms = new Map((view.value?.suggestions ?? []).map(item => [suggestionKey(item), item]))
  for (const entry of view.value?.entries ?? []) {
    if (terms.has(suggestionKey(entry))) continue
    const outcome = outcomeOf(entry)
    terms.set(suggestionKey(entry), { ...entry, variants: [], persons: 0,
      submissions: new Set(outcome?.occurrences.map(item => item.modelVersionId) ?? []).size,
      evidence: { contextUnique: 0, contextBest: 0, textOnly: 0, recognized: outcome?.counts.counted ?? 0 },
      alsoSuggestedFor: [], comparisons: outcome?.comparisons ?? [] })
  }
  return [...terms.values()]
})
const filteredSuggestions = computed(() => reviewTerms.value.filter((item) =>
  item.submissions >= (minPersons.value || 0)
  && (!typeFilter.value || elementsById.value.get(item.referenceElementId)?.type === typeFilter.value)))
const importSources = computed(() => {
  const current = solutions.value[solutionIndex.value]
  if (!current || !task.value) return []
  const seen = new Set<string>([current.versionId])
  return task.value.releases.flatMap((item) => item.sampleSolutions.filter((solution) => solution.modelId === current.modelId && !seen.has(solution.versionId) && seen.add(solution.versionId))
    .map((solution) => ({ title: `Release ${item.versionNumber}`, value: solution.versionId })))
})

const suggestionKey = (item: Pick<Suggestion, 'referenceElementId' | 'termKey'>) => `${item.referenceElementId}:${item.termKey}`
const comparisonsOf = (item?: Pick<Suggestion, 'referenceElementId' | 'termKey'>) => item ? reviewTerms.value.find(term => suggestionKey(term) === suggestionKey(item))?.comparisons : undefined
const entryOf = (item: TermOutcome) => view.value?.entries.find(entry => entry.referenceElementId === item.referenceElementId && entry.termKey === item.termKey)
const decideTerm = (item: TermOutcome, status: EntryStatus) => {
  const term = reviewTerms.value.find(term => suggestionKey(term) === suggestionKey(item))
  if (term) return decide(term, status)
  const entry = entryOf(item)
  return entry ? change(entry, status) : save([{ referenceElementId: item.referenceElementId, term: item.term, status }], `“${item.term}” ${status}.`, [{ referenceElementId: item.referenceElementId, term: item.term, status: null }])
}
const sameNamed = (item: Suggestion): GlossaryElement[] => {
  const own = elementsById.value.get(item.referenceElementId)
  if (!own || !view.value) return []
  const decided = new Set(view.value.entries.map((entry) => `${entry.referenceElementId}:${entry.termKey}`))
  return view.value.elements.filter((element) => element.id !== own.id && element.label === own.label && element.targetKind === own.targetKind && !decided.has(`${element.id}:${item.termKey}`))
}
const message = (cause: unknown, fallback: string) => (cause as { response?: { data?: { message?: string } } }).response?.data?.message ?? fallback
const notify = (text: string, undoable: GlossaryChange[] | null = null) => {
  snackbarText.value = text
  undoChanges.value = undoable
  snackbar.value = true
}

const loadPackage = async (ref: SolutionRef): Promise<ModelPackage> => {
  const { data: solution } = await taskService.getSampleSolution(ref.taskId, ref.versionId, ref.modelId, ref.modelVersionId)
  const languages = new Map<string, PackagedLanguage>()
  const pending: LanguageVersionReference[] = [...solution.workspaceLanguages]
  while (pending.length) {
    const reference = pending.pop()!
    const key = `${reference.languageId}:${reference.versionId}`
    if (languages.has(key)) continue
    const { data: version } = await languageService.getVersion<DiagramLanguage>(reference.languageId, reference.versionId)
    const included = version.includedLanguageVersions ?? []
    languages.set(key, { languageId: reference.languageId, versionId: reference.versionId, name: '', data: version.data, includedLanguageVersions: included })
    pending.push(...included)
  }
  return { format: 'modeling-copilot-model', version: 1, model: { xml: String(solution.data.xml) }, workspaceLanguages: solution.workspaceLanguages, languages: [...languages.values()] }
}
const schedulePoll = () => {
  clearTimeout(pollTimer)
  if (jobRunning.value || replayRunning.value) pollTimer = setTimeout(poll, 3000)
}
const poll = async (refreshInspection = false) => {
  const current = solutionRef.value
  if (!current || !view.value) return
  try {
    if (jobRunning.value) {
      const { data } = await synonymGlossary.status(current.taskId, current.versionId)
      if (solutionRef.value !== current || !view.value) return
      const finished = data.job?.state !== 'running'
      const grew = data.collected !== view.value.signals.collected
      view.value = { ...view.value, signals: data }
      if (finished || grew) {
        const refreshed = await synonymGlossary.solution(current, false, excludeStaff.value)
        if (solutionRef.value !== current) return
        view.value = refreshed.data
      }
    }
    const running = replays.value.find(item => item.state === 'running')
    if (running) {
      const { data } = await synonymGlossary.replay(current, running.id)
      if (solutionRef.value !== current) return
      replays.value = replays.value.map(item => item.id === data.id ? data : item)
    }
    if (workspaceTab.value === 'tests' && inspectionId.value && (refreshInspection || !inspectionDetail.value || !['succeeded', 'failed', 'cancelled'].includes(inspectionDetail.value.state))) await loadInspection(true)
  } catch {
    replayError.value = 'Live updates could not be loaded. Refresh the saved run to retry.'
    return
  }
  schedulePoll()
}
const load = async () => {
  const current = solutionRef.value
  const wantedOutcome = outcomeSource.value
  const wantedReplay = replayId.value
  const token = ++loadToken
  clearTimeout(pollTimer)
  selectedId.value = null
  selectedPath.value = ''
  view.value = null
  modelPackage.value = null
  replays.value = []
  candidates.value = []
  candidatesLoading.value = false
  newRunOpen.value = false
  runSettingsOpen.value = false
  selectedCases.value = []
  inspectionId.value = null
  replayId.value = null
  outcomeSource.value = 'original'
  replayError.value = ''
  if (!current) return
  loading.value = true
  error.value = ''
  try {
    const [glossary, model] = await Promise.all([synonymGlossary.solution(current, false, excludeStaff.value), loadPackage(current)])
    if (token !== loadToken) return
    view.value = glossary.data
    modelPackage.value = model
    try {
      const { data } = await synonymGlossary.replays(current)
      if (token !== loadToken) return
      replays.value = data
      replayId.value = data.some(item => item.id === wantedReplay) ? wantedReplay : data[0]?.id ?? null
      outcomeSource.value = data.some(item => item.id === wantedOutcome) ? wantedOutcome : 'original'
    } catch (cause) {
      if (token === loadToken) replayError.value = message(cause, 'Saved comparisons could not be loaded.')
    }
    schedulePoll()
    if (workspaceTab.value === 'tests') await loadCandidates()
  } catch (cause) {
    if (token === loadToken) error.value = message(cause, 'The glossary could not be loaded.')
  } finally {
    if (token === loadToken) loading.value = false
  }
}
const reload = async () => {
  if (solutionRef.value) view.value = (await synonymGlossary.solution(solutionRef.value, false, excludeStaff.value)).data
}
const save = async (changes: GlossaryChange[], text: string, undoable: GlossaryChange[] | null) => {
  if (!solutionRef.value || !view.value) return false
  saving.value = true
  try {
    view.value = (await synonymGlossary.save(solutionRef.value, view.value.revision, changes)).data
    await reload()
    notify(text, undoable)
    return true
  } catch (cause) {
    const status = (cause as { response?: { status?: number } }).response?.status
    if (status === 409) {
      await reload().catch(() => undefined)
      error.value = 'Another administrator changed this glossary. The latest state is shown, please check and repeat your decision.'
    } else if (status === 422 && tab.value === 'selected' && newTerm.value) {
      newTermError.value = message(cause, 'This term cannot be saved.')
    } else {
      error.value = message(cause, 'The decision could not be saved.')
    }
    return false
  } finally {
    saving.value = false
  }
}
const setMatchingSource = async (entry: GlossaryEntry, enabled: boolean) => {
  const current = solutionRef.value
  if (!current || !view.value || saving.value) return
  saving.value = true
  try {
    const { data } = await synonymGlossary.setMatchingSource(current, entry.id, view.value.revision, enabled)
    if (solutionRef.value !== current) return
    view.value = data
    await reload()
    notify(enabled ? 'Matching source enabled.' : 'Matching source disabled.')
  } catch (cause) {
    if (solutionRef.value !== current) return
    if ((cause as { response?: { status?: number } }).response?.status === 409) {
      await reload().catch(() => undefined)
      error.value = 'The glossary changed. The latest state is shown; please repeat your change.'
    } else error.value = message(cause, 'The matching source could not be changed.')
  } finally {
    saving.value = false
  }
}
const findEntry = (item: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => view.value?.entries.find(entry => entry.referenceElementId === item.referenceElementId && entry.termKey === item.termKey)
const toggleSource = (item: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => {
  const entry = findEntry(item)
  if (entry) return setMatchingSource(entry, !entry.matchingSource)
}
const removeTerm = (item: Pick<TermOutcome, 'referenceElementId' | 'termKey'>) => {
  const entry = findEntry(item)
  if (entry) return change(entry, null)
}
const decide = (item: Suggestion, status: EntryStatus) => {
  if (status === 'accepted' && sameNamed(item).length) {
    acceptanceSelection.value = [item.referenceElementId]
    applying.value = item
    return
  }
  const entry = findEntry(item)
  return entry ? change(entry, status) : save([{ referenceElementId: item.referenceElementId, term: item.term, status }], `Term ${status}.`, [{ referenceElementId: item.referenceElementId, term: item.term, status: null }])
}
const change = (entry: GlossaryEntry, status: EntryStatus | null) =>
  save([{ referenceElementId: entry.referenceElementId, term: entry.term, status }], status ? `“${entry.term}” ${status}.` : `“${entry.term}” removed.`, [{ referenceElementId: entry.referenceElementId, term: entry.term, status: entry.status }])
const addTerm = async (status: EntryStatus) => {
  const term = newTerm.value.trim()
  if (!term || !selectedId.value) return
  newTermError.value = ''
  const change = { referenceElementId: selectedId.value, term }
  if (await save([{ ...change, status }], `“${term}” ${status}.`, [{ ...change, status: null }])) newTerm.value = ''
}
const applySameNamed = async (all: boolean) => {
  const item = applying.value
  if (!item || saving.value) return
  const targets = all ? acceptanceTargets.value.map(element => element.id) : [...acceptanceSelection.value]
  if (!targets.length) return
  const saved = await save(targets.map((referenceElementId) => ({ referenceElementId, term: item.term, status: 'accepted' })), `“${item.term}” accepted for ${targets.length} elements.`,
    targets.map((referenceElementId) => ({ referenceElementId, term: item.term, status: null })))
  if (saved) applying.value = null
}
const undo = async () => {
  const changes = undoChanges.value
  snackbar.value = false
  if (changes) await save(changes, 'Decision undone.', null)
}
const selectCell = (cellId: string, path?: string) => {
  selectedId.value = cellId
  tab.value = 'selected'
  selectedPath.value = path ?? canvas.value?.pathOf(cellId) ?? ''
  newTermError.value = ''
}
const recalculate = async (scope: RecalculateScope) => {
  if (!taskId.value || !releaseId.value || !view.value) return
  starting.value = true
  try {
    view.value = { ...view.value, signals: (await synonymGlossary.recalculate(taskId.value, releaseId.value, scope)).data }
    schedulePoll()
  } catch (cause) {
    error.value = message(cause, 'The calculation could not be started.')
  } finally {
    starting.value = false
  }
}
const startReplay = async () => {
  const current = solutionRef.value
  if (!current || !thresholdsValid.value || !selectedCases.value.length || selectedCases.value.length > 500) return
  replayStarting.value = true
  replayError.value = ''
  try {
    const { data } = await synonymGlossary.startReplay(current, customThresholds.value ? { ...thresholds.value } : null, [...selectedCases.value])
    if (solutionRef.value !== current) return
    replays.value = [data, ...replays.value.filter(item => item.id !== data.id)].slice(0, 3)
    replayId.value = data.id
    inspectionId.value = null
    newRunOpen.value = false
    schedulePoll()
    const saved = await synonymGlossary.replays(current)
    if (solutionRef.value !== current) return
    replays.value = saved.data
    schedulePoll()
  } catch (cause) {
    if (solutionRef.value === current) replayError.value = message(cause, 'The comparison could not be started.')
  } finally {
    replayStarting.value = false
  }
}
const loadCandidates = async () => {
  const current = solutionRef.value
  if (!current) return
  candidatesLoading.value = true
  try {
    const { data } = await synonymGlossary.candidates(current)
    if (solutionRef.value !== current) return
    candidates.value = data
    selectedCases.value = selectedCases.value.filter(id => visibleCandidates.value.some(item => item.evaluationId === id))
  } catch (cause) {
    if (solutionRef.value === current) replayError.value = message(cause, 'Saved submissions could not be loaded.')
  } finally {
    if (solutionRef.value === current) candidatesLoading.value = false
  }
}
const refreshReplays = async () => {
  const current = solutionRef.value
  if (!current) return
  replayError.value = ''
  try {
    const { data } = await synonymGlossary.replays(current)
    if (solutionRef.value !== current) return
    replays.value = data
    if (!data.some(item => item.id === replayId.value)) replayId.value = data[0]?.id ?? null
    if (outcomeSource.value !== 'original' && !data.some(item => item.id === outcomeSource.value)) outcomeSource.value = 'original'
    await poll(true)
  } catch (cause) {
    if (solutionRef.value === current) replayError.value = message(cause, 'Saved test runs could not be loaded.')
  }
}
const loadInspection = async (background = false) => {
  const current = solutionRef.value, batchId = replayId.value, evaluationId = inspectionId.value
  const token = ++inspectionToken
  if (!current || !batchId || !evaluationId) return
  if (!background) inspectionLoading.value = true
  try {
    const { data } = await synonymGlossary.inspectReplay(current, batchId, evaluationId)
    if (token !== inspectionToken) return
    inspectionDetail.value = data
    inspectionError.value = ''
  } catch (cause) {
    if (token === inspectionToken) inspectionError.value = message(cause, 'Run analysis could not be loaded.')
  } finally {
    if (token === inspectionToken) inspectionLoading.value = false
  }
}
const openInspection = async (id: string) => {
  inspectionId.value = id
  await nextTick()
  inspectionContainer.value?.focus({ preventScroll: true })
}
const closeInspection = async () => {
  const previousId = inspectionId.value
  inspectionId.value = null
  await nextTick()
  const target = previousId && document.querySelector<HTMLElement>(`.suite-cases [data-case-id="${CSS.escape(previousId)}"]`)
  ;(target || document.querySelector<HTMLElement>('.suite-cases-heading'))?.focus({ preventScroll: true })
}
const stepInspection = (direction: number) => {
  const next = selectedReplay.value?.items[inspectionIndex.value + direction]
  if (next) void openInspection(next.evaluationId)
}
const deleteReplay = async () => {
  const current = solutionRef.value
  const id = deleteReplayId.value
  if (!current || !id) return
  replayDeleting.value = true
  try {
    await synonymGlossary.deleteReplay(current, id)
    if (solutionRef.value !== current) return
    replays.value = replays.value.filter(item => item.id !== id)
    if (outcomeSource.value === id) outcomeSource.value = 'original'
    if (replayId.value === id) replayId.value = replays.value[0]?.id ?? null
    deleteReplayId.value = null
  } catch (cause) {
    replayError.value = message(cause, 'The comparison could not be deleted.')
    deleteReplayId.value = null
  } finally {
    replayDeleting.value = false
  }
}
const openImport = () => {
  importFrom.value = importSources.value[0]?.value ?? null
  importOpen.value = true
}
const runImport = async () => {
  if (!solutionRef.value || !view.value || !importFrom.value) return
  importOpen.value = false
  try {
    const { data } = await synonymGlossary.importEntries(solutionRef.value, importFrom.value, view.value.revision)
    view.value = data.glossary
    await reload()
    notify(`${data.imported} entries imported.${data.skipped.length ? ` Not imported: ${data.skipped.join(', ')}` : ''}`)
  } catch (cause) {
    error.value = message(cause, 'The entries could not be imported.')
    await reload().catch(() => undefined)
  }
}

watch(taskId, (id) => {
  if (!task.value?.releases.some(item => item.id === releaseId.value)) releaseId.value = task.value?.releases[0]?.id ?? null
  if (id && route.params.taskId !== id) router.replace({ name: 'EvaluationLab', params: { taskId: id }, query: route.query })
})
watch(contextTaskId, () => {
  if (!contextReleaseItems.value.some(item => item.value === contextReleaseId.value)) contextReleaseId.value = contextReleaseItems.value[0]?.value ?? null
})
watch(workspaceTab, value => {
  router.replace({ name: 'EvaluationLab', params: taskId.value ? { taskId: taskId.value } : {}, query: { ...route.query, tab: value === 'glossary' ? undefined : value } })
  if (value === 'tests' && !candidates.value.length) void loadCandidates()
})
watch(studentCasesOnly, () => { selectedCases.value = selectedCases.value.filter(id => visibleCandidates.value.some(item => item.evaluationId === id)) })
watch(newRunOpen, (open) => {
  if (open) {
    replayError.value = ''
    void loadCandidates()
  }
})
watch([replayId, inspectionId, solutionRef], () => {
  inspectionToken++
  inspectionDetail.value = null
  inspectionError.value = ''
  inspectionLoading.value = false
  void loadInspection()
})
watch(replayId, () => {
  inspectionId.value = null
  caseStatus.value = 'all'
  casePage.value = 1
  caseSort.value = []
  runSettingsOpen.value = false
})
watch(releaseId, () => { solutionIndex.value = 0 })
watch(solutionRef, load)
watch(excludeStaff, load)
onMounted(async () => {
  loading.value = true
  try {
    tasks.value = (await synonymGlossary.tasks()).data
    const wanted = String(route.params.taskId ?? '')
    taskId.value = tasks.value.some((item) => item.id === wanted) ? wanted : tasks.value[0]?.id ?? null
  } catch (cause) {
    error.value = message(cause, 'The tasks could not be loaded.')
  } finally {
    loading.value = false
  }
})
onBeforeUnmount(() => {
  loadToken++
  inspectionToken++
  clearTimeout(pollTimer)
})
</script>

<style scoped>
.lab-page { display: flex; flex-direction: column; height: calc(100dvh - var(--v-layout-top, 0px) - var(--v-layout-bottom, 0px)); min-height: 0; overflow: hidden; }
.lab-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px 16px; flex-shrink: 0; padding: 16px 20px; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
.lab-identity { display: flex; align-items: center; gap: 12px; min-width: 0; }
.lab-symbol { display: grid; place-items: center; flex: 0 0 44px; height: 44px; color: rgb(var(--v-theme-primary-dark)); background: rgba(var(--v-theme-primary), 0.12); border-radius: 12px; }
.lab-layout { display: flex; flex: 1; min-height: 0; }
.lab-sidebar { display: flex; flex-direction: column; flex: 0 0 264px; min-height: 0; border-right: 1px solid rgba(var(--v-theme-on-surface), 0.12); background: rgba(var(--v-theme-primary), 0.025); }
.lab-context-row { padding: 12px; }
.lab-context { display: flex; align-items: center; gap: 10px; width: 100%; padding: 12px; color: rgb(var(--v-theme-on-surface)); text-align: left; border: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 10px; background: rgb(var(--v-theme-surface)); }
.lab-context:hover:not(:disabled) { background: rgba(var(--v-theme-primary), 0.06); border-color: rgba(var(--v-theme-primary), 0.45); }
.lab-context:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 2px; }
.lab-context:disabled { opacity: 0.6; }
.lab-context-copy { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }
.lab-context-copy strong { font-size: 14px; line-height: 1.4; overflow-wrap: anywhere; }
.lab-eyebrow { font-size: 10px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: rgba(var(--v-theme-on-surface), 0.6); }
.lab-browse-button { display: none; }
.lab-workspaces { flex-shrink: 0; padding: 0 8px 12px; background: transparent; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.lab-workspaces :deep(.v-list-item) { min-height: 54px; }
.lab-workspaces :deep(.v-list-item__spacer), .lab-nav-list :deep(.v-list-item__spacer) { width: 12px; }
.lab-sidebar-content { flex: 1; min-height: 0; overflow: auto; padding-block: 8px; }
.lab-nav-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 16px 8px; }
.lab-nav-heading h2 { font-size: 12px; font-weight: 600; }
.lab-nav-heading span { font-size: 12px; color: rgba(var(--v-theme-on-surface), 0.6); }
.lab-nav-list { background: transparent; padding: 0 8px 8px; }
.lab-retention { flex-shrink: 0; padding: 12px 16px; margin: 0; border-top: 1px solid rgba(var(--v-theme-on-surface), 0.08); }
.lab-main { display: flex; flex-direction: column; flex: 1; min-width: 0; min-height: 0; overflow: hidden; }
.lab-workspace { display: flex; flex-direction: column; flex: 1; min-width: 0; min-height: 0; overflow: hidden; }
.workspace-heading { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; padding: 16px; flex-shrink: 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
.workspace-title { flex: 1; min-width: 180px; }
.workspace-heading h2:focus-visible { outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: 3px; }
.suite-run-header { display: block; }
.suite-run-header, .suite-case-navigation { flex-shrink: 0; }
.suite-cases { flex: 1; min-height: 0; overflow: auto; }
.case-status-filter { flex: 0 1 180px; min-width: 140px; }
.case-select { flex: 0 1 360px; min-width: 180px; }
.case-name { max-width: 320px; height: auto; min-height: 32px; text-align: left; }
.case-name :deep(.v-btn__content) { white-space: normal; justify-content: flex-start; overflow-wrap: anywhere; }
.case-error { max-width: 300px; overflow-wrap: anywhere; }
.suite-analysis { display: flex; flex-direction: column; flex: 1; min-height: 0; outline-offset: -2px; }
.suite-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; text-align: center; }
.suite-empty p { max-width: 440px; }
.threshold-field { flex: 1 1 180px; }
.run-settings { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px 20px; font-size: 14px; }
.run-settings dt { color: rgba(var(--v-theme-on-surface), 0.7); }
.run-settings dd { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 900px) {
  .lab-header { padding: 12px 16px; }
  .lab-layout { flex-direction: column; }
  .lab-sidebar { flex: 0 0 auto; border-right: 0; border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.12); }
  .lab-context-row { display: flex; align-items: center; gap: 8px; padding: 8px 12px; }
  .lab-context { flex: 1; min-width: 0; padding: 8px 10px; }
  .lab-eyebrow { display: none; }
  .lab-browse-button { display: inline-flex; }
  .lab-workspaces { display: flex; gap: 8px; padding: 0 8px 8px; border-bottom: 0; }
  .lab-workspaces :deep(.v-list-item) { flex: 1; min-width: 0; min-height: 40px; }
  .lab-workspaces :deep(.v-list-item-subtitle) { display: none; }
  .lab-workspaces :deep(.v-list-item-title) { white-space: normal; font-size: 12px; line-height: 1.3; }
  .lab-sidebar-content { display: none; flex: 0 0 auto; max-height: 32dvh; }
  .lab-sidebar--expanded .lab-sidebar-content { display: block; }
  .lab-retention { display: none; }
  .workspace-heading { padding: 12px; }
  .case-select { flex: 1 1 200px; }
}
@media (max-width: 500px) {
  .lab-header .lab-identity p { display: none; }
  .lab-symbol { flex-basis: 36px; height: 36px; border-radius: 10px; }
}
.glossary-layout { display: grid; grid-template-columns: minmax(0, var(--model-width)) 12px minmax(0, 1fr); gap: 0; flex: 1; min-height: 0; align-items: stretch; overflow: hidden; }
.glossary-canvas { min-height: 0; height: 100%; }
.glossary-canvas :deep(.review-graph) { min-height: 0; }
.glossary-panel { display: flex; flex-direction: column; border: 1px solid rgba(var(--v-theme-on-surface), 0.12); border-radius: 8px; min-width: 0; min-height: 0; overflow: hidden; }
.glossary-panel > :not(.panel-body) { flex-shrink: 0; }
.panel-body { flex: 1; min-height: 0; overflow-x: auto; overflow-y: auto; scrollbar-gutter: stable; }
.panel-body :deep(.v-window__container) { height: auto; }
.panel-body :deep(.v-table__wrapper) { overflow: visible; }
.panel-body::-webkit-scrollbar { width: 12px; height: 12px; }
.panel-body::-webkit-scrollbar-track { background: rgba(var(--v-theme-on-surface), 0.05); }
.panel-body::-webkit-scrollbar-thumb { background: rgba(var(--v-theme-on-surface), 0.35); border: 2px solid rgb(var(--v-theme-surface)); border-radius: 6px; }
.reason-cell { min-width: 200px; max-width: 340px; padding-block: 8px !important; }
.row-actions { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; min-width: 85px; padding-block: 6px; }
.row-actions :deep(.v-btn__content) { white-space: normal; overflow: visible; text-overflow: clip; }
.row-actions > .v-btn { height: auto; min-height: 24px; max-width: 140px; }
.split-handle { cursor: col-resize; touch-action: none; user-select: none; align-self: stretch; display: flex; align-items: center; justify-content: center; color: rgb(var(--v-theme-on-surface)); background: rgba(var(--v-theme-on-surface), 0.06); border-radius: 4px; }
.split-handle:hover, .split-handle:focus-visible { background: rgba(var(--v-theme-primary), 0.2); outline: 2px solid rgb(var(--v-theme-primary)); outline-offset: -2px; }
.term-field { min-width: 200px; }
.filter-field { flex: 0 1 120px; }
.filter-field-wide { flex: 1 1 170px; }
.section-row td { background: rgba(var(--v-theme-on-surface), 0.04); }
.selected-row td { background: rgba(var(--v-theme-primary), 0.08); }
@media (max-width: 1200px) {
  .glossary-layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(100px, 30%) minmax(0, 1fr); gap: 12px; }
  .split-handle { display: none; }
}
</style>
