<template>
  <v-dialog :model-value="shareDialog === 'ask'" width="440" persistent>
    <v-card title="Share this model" text="Others join through a link. You can change these settings later.">
      <v-card-text class="pt-0">
        <div class="share-section">Visitors</div>
        <v-switch v-for="setting in visitorSettings" :key="setting.key" v-model="options[setting.key]" color="primary" density="compact" :label="setting.label" :hint="setting.hint" persistent-hint />
        <div class="share-section">Share history</div>
        <v-item-group v-model="options.history" mandatory :class="{ 'share-history--busy': busy }">
          <v-item v-for="choice in historyChoices" :key="choice.value" v-slot="{ isSelected, toggle }" :value="choice.value">
            <v-card :variant="isSelected ? 'tonal' : 'outlined'" :color="isSelected ? 'primary' : undefined" class="share-history mb-2" role="radio" tabindex="0" :aria-checked="isSelected" @click="toggle" @keydown.enter.prevent="toggle" @keydown.space.prevent="toggle">
              <v-icon :icon="choice.icon" class="mr-3" />
              <div class="flex-grow-1">
                <div class="share-history__title">{{ choice.title }}</div>
                <div class="text-caption share-history__hint">{{ choice.hint }}</div>
              </div>
              <v-icon v-if="isSelected" icon="mdi-check" />
            </v-card>
          </v-item>
        </v-item-group>
        <div v-if="shareProgress && options.history !== 'none'" class="mt-3">
          <v-progress-linear :model-value="shareProgress.total ? (shareProgress.done / shareProgress.total) * 100 : 0" color="primary" height="4" />
          <div class="text-caption mt-1">Writing history · {{ shareProgress.done }} of {{ shareProgress.total }}</div>
        </div>
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-3">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="busy" @click="closeDialog">Cancel</v-btn>
        <v-btn color="primary" variant="text" :loading="busy" @click="share">Share</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog :model-value="shareDialog === 'link'" width="440" persistent>
    <v-card title="Your model is shared" text="Everyone who is signed in can join while you share.">
      <v-card-text class="pt-0">
        <ShareCopyCard :link="link" hint="Send it to the people you want to work with" />
        <div class="share-section">Visitors</div>
        <v-chip v-for="chip in summary" :key="chip.key" :prepend-icon="chip.icon" size="small" variant="flat" class="share-chip mr-1" :class="{ 'share-chip--open': chip.open }">{{ chip.text }}</v-chip>
        <div class="share-section">History</div>
        <v-chip :prepend-icon="chosenHistory.icon" size="small" variant="flat" class="share-chip share-chip--open">{{ chosenHistory.title }}</v-chip>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn color="primary" variant="text" @click="closeDialog">Done</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog :model-value="shareDialog === 'quit'" width="480" persistent>
    <v-card v-if="!confirmDiscard" title="Quit sharing" text="The room closes for everyone. Decide what happens to the current state first.">
      <v-card-text class="pt-0">
        <v-chip v-if="visitors" prepend-icon="mdi-account-multiple-outline" size="small" variant="flat" class="share-chip share-chip--warn mr-1">{{ visitors === 1 ? '1 visitor' : `${visitors} visitors` }} will be disconnected</v-chip>
        <v-chip prepend-icon="mdi-lock-outline" size="small" variant="flat" class="share-chip share-chip--open">Room is locked while you decide</v-chip>
        <div class="share-section">Current state</div>
        <v-item-group v-model="target" mandatory :class="{ 'share-history--busy': busy }">
          <v-item v-for="choice in leaveChoices" :key="choice.value" v-slot="{ isSelected, toggle }" :value="choice.value">
            <v-card :variant="isSelected ? 'tonal' : 'outlined'" :color="isSelected ? (choice.danger ? 'error' : 'primary') : undefined" class="share-history mb-2" :class="{ 'share-history--danger': choice.danger }" role="radio" tabindex="0" :aria-checked="isSelected" @click="toggle" @keydown.enter.prevent="toggle" @keydown.space.prevent="toggle">
              <v-icon :icon="choice.icon" class="mr-3" />
              <div class="flex-grow-1">
                <div class="share-history__title">{{ choice.title }}</div>
                <div class="text-caption share-history__hint">{{ choice.hint }}</div>
                <v-text-field v-if="isSelected && choice.value === 'model'" v-model="name" label="Name of the new model" density="compact" variant="outlined" hide-details class="mt-2" @click.stop @keydown.stop />
              </div>
              <v-icon v-if="isSelected" icon="mdi-check" />
            </v-card>
          </v-item>
        </v-item-group>
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-3">{{ error }} Nothing was closed, so you can try again.</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-btn variant="text" :disabled="busy" @click="cancelQuit">Keep sharing</v-btn>
        <v-spacer />
        <v-btn :color="target === 'discard' ? 'error' : 'primary'" variant="text" :loading="busy" @click="confirmQuit">{{ quitLabel }}</v-btn>
      </v-card-actions>
    </v-card>
    <v-card v-else title="Quit without saving?" text="The current state of the model is lost for everyone. Your own model stays as it was before you shared it.">
      <v-card-text v-if="error" class="pt-0">
        <v-alert type="error" variant="tonal" density="compact">{{ error }} Nothing was closed, so you can try again.</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-btn variant="text" :disabled="busy" @click="confirmDiscard = false">Back</v-btn>
        <v-spacer />
        <v-btn color="error" variant="text" :loading="busy" @click="quit">Quit without saving</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog :model-value="hostClosed || shareDialog === 'leave'" width="480" persistent>
    <v-card v-if="!confirmDiscard">
      <v-card-text class="text-center pb-0">
        <v-icon :icon="situation.icon" size="40" :class="`visitor-icon--${situation.tone}`" />
        <div class="text-h6 mt-1">{{ situation.title }}</div>
        <div class="mt-2">{{ situation.text }}</div>
        <div class="mt-3">
          <v-chip :prepend-icon="situation.chip.icon" size="small" variant="flat" class="share-chip mr-1" :class="situation.tone === 'ok' ? 'share-chip--open' : 'share-chip--warn'">{{ situation.chip.text }}</v-chip>
          <v-chip prepend-icon="mdi-pencil" size="small" variant="flat" class="share-chip share-chip--open">Edits so far are in your copy</v-chip>
        </div>
      </v-card-text>
      <v-card-text>
        <v-item-group v-model="visitorChoice" mandatory :class="{ 'share-history--busy': busy }">
          <v-item v-for="option in visitorChoices" :key="option.value" v-slot="{ isSelected, toggle }" :value="option.value">
            <v-card :variant="isSelected ? 'tonal' : 'outlined'" :color="isSelected ? (option.danger ? 'error' : 'primary') : undefined" class="share-history mb-2" :class="{ 'share-history--danger': option.danger }" role="radio" tabindex="0" :aria-checked="isSelected" @click="toggle" @keydown.enter.prevent="toggle" @keydown.space.prevent="toggle">
              <v-icon :icon="option.icon" class="mr-3" />
              <div class="flex-grow-1">
                <div class="share-history__title">{{ option.title }}</div>
                <div v-if="option.hint" class="text-caption share-history__hint">{{ option.hint }}</div>
                <v-text-field v-if="isSelected && option.value === 'keep'" v-model="name" label="Name of the model" density="compact" variant="outlined" hide-details class="mt-2" @click.stop @keydown.stop />
              </div>
              <v-icon v-if="isSelected" icon="mdi-check" />
            </v-card>
          </v-item>
        </v-item-group>
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-3">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-btn v-if="situation.canStay" variant="text" :disabled="busy" @click="closeDialog">Stay in the room</v-btn>
        <v-spacer />
        <v-btn :color="visitorChoice === 'drop' ? 'error' : 'primary'" variant="text" :loading="busy" @click="confirmLeave">{{ visitorChoice === 'drop' ? 'Leave without saving' : situation.confirm }}</v-btn>
      </v-card-actions>
    </v-card>
    <v-card v-else title="Leave without saving?" text="The current state of the model is lost for you.">
      <v-card-text v-if="error" class="pt-0">
        <v-alert type="error" variant="tonal" density="compact">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-btn variant="text" :disabled="busy" @click="confirmDiscard = false">Back</v-btn>
        <v-spacer />
        <v-btn color="error" variant="text" :loading="busy" @click="drop">Leave without saving</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import ShareCopyCard from './ShareCopyCard.vue'
import { useCollabConnection } from '@/collab/connection/useCollabConnection'
import { currentShare, historyChoices, hostClosed, leaveAsVisitor, leaveChoices, leaveShare, pendingTarget, reopenShare, shareChoice as options, shareDialog, shareLink, shareModel, shareProgress, visitorCase, visitorChoices, visitorCases, visitorSettings, type LeaveTarget, type VisitorChoice } from './shareModel'

const router = useRouter()
const workspace = useModelWorkspaceStore()

const { people } = useCollabConnection()
// Who else is in the room, counted by the presence; the host is one of the people.
const visitors = computed(() => people.value.filter((person) => !person.self).length)
const target = ref<LeaveTarget>('version')
const visitorChoice = ref<VisitorChoice>('keep')
const situation = computed(() => visitorCases[visitorCase()])
const quitLabel = computed(() => (target.value === 'discard' ? 'Quit without saving' : error.value ? 'Try again' : 'Save and quit'))
const name = ref('')
const busy = ref(false)
const error = ref('')
const confirmDiscard = ref(false)

const closeDialog = () => {
  shareDialog.value = null
  pendingTarget.value = null
}

const link = computed(() => (currentShare.value ? shareLink(router, currentShare.value.roomId) : ''))

/** Runs one step of a dialog; a failure stays in the dialog, so the step can be tried again. */
const run = async (step: () => Promise<void>) => {
  busy.value = true
  error.value = ''
  try {
    await step()
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    busy.value = false
  }
}

// The name offered is that of the open model, taken when the dialog opens.
watch([() => shareDialog.value === 'quit' || shareDialog.value === 'leave', hostClosed], ([quitting, closed]) => {
  if (quitting || closed) name.value = workspace.data.name
  if (quitting) {
    target.value = 'version'
    visitorChoice.value = 'keep'
  }
  error.value = ''
  confirmDiscard.value = false
})

const share = () =>
  run(async () => {
    await shareModel(router, { ...options })
    shareDialog.value = 'link'
  })

// Was der Host im Dialog davor gewählt hat; der Dialog mit dem Link öffnet direkt nach dem Teilen.
const summary = computed(() =>
  visitorSettings.map(({ key, open, on, off }) => {
    const value = options[key]
    return { key, ...(value ? on : off), open: value === open }
  })
)
const chosenHistory = computed(() => historyChoices.find((choice) => choice.value === options.history) ?? historyChoices[0])

const quit = () =>
  run(async () => {
    if (target.value === 'model' && !name.value.trim()) throw new Error('Enter a name for the new model.')
    await leaveShare(router, target.value, target.value === 'model' ? name.value.trim() : undefined)
    shareDialog.value = null
  })

// Throwing the state away asks once more; the other ways save it and need no question.
const confirmQuit = () => (target.value === 'discard' ? (confirmDiscard.value = true) : void quit())

const cancelQuit = () =>
  run(async () => {
    await reopenShare()
    shareDialog.value = null
    pendingTarget.value = null
  })

const keep = () =>
  run(async () => {
    if (!name.value.trim()) throw new Error('Enter a name for the model.')
    // The state becomes an own model, which opens so the work goes on there; a place the guard stopped at does not take its place.
    pendingTarget.value = null
    await leaveAsVisitor(router, true, name.value.trim())
    shareDialog.value = null
  })

// Throwing the state away asks once more; keeping it needs no question.
const confirmLeave = () => (visitorChoice.value === 'drop' ? (confirmDiscard.value = true) : void keep())

const drop = () =>
  run(async () => {
    await leaveAsVisitor(router, false)
    shareDialog.value = null
  })
</script>

<style scoped>
.share-section {
  margin: 12px 0 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(var(--v-theme-on-surface), 0.55);
}

.share-history {
  display: flex;
  align-items: flex-start;
  padding: 10px 12px;
  cursor: pointer;
}

.share-history__title {
  font-size: 14px;
  font-weight: 500;
}

/* Auch gewählt bleibt die Schrift dunkel und die Karte hellgrün (rot bei "Do not save"), nur die Icons tragen die Farbe; grüne Schrift auf grünem Grund ist schlecht lesbar. */
.share-history__title,
.share-history :deep(.v-field) {
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.share-history__hint {
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.share-history :deep(.v-icon) {
  color: color-mix(in srgb, rgb(var(--v-theme-primary)) 75%, black);
}

.visitor-icon--ok {
  color: color-mix(in srgb, rgb(var(--v-theme-primary)) 75%, black);
}

.visitor-icon--warn {
  color: color-mix(in srgb, rgb(var(--v-theme-warning)) 70%, black);
}

.share-history--danger :deep(.v-icon) {
  color: color-mix(in srgb, rgb(var(--v-theme-error)) 75%, black);
}

/* Grün für das, was die Besucher dürfen, Grau für das, was eingeschränkt ist; Schrift dunkel, damit sie lesbar bleibt. */
.share-chip {
  background: rgba(var(--v-theme-on-surface), 0.08);
  color: rgba(var(--v-theme-on-surface), 0.7);
}

.share-chip--warn {
  background: rgba(var(--v-theme-warning), 0.2);
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.share-chip--open {
  background: rgba(var(--v-theme-primary), 0.18);
  color: rgba(var(--v-theme-on-surface), 0.87);
}

.share-chip--open :deep(.v-icon) {
  color: color-mix(in srgb, rgb(var(--v-theme-primary)) 75%, black);
}

.share-history--busy {
  pointer-events: none;
  opacity: 0.6;
}
</style>
