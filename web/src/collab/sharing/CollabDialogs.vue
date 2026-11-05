<template>
  <v-dialog :model-value="shareDialog === 'ask'" width="440" persistent>
    <v-card title="Share this model" text="Others join through a link. You can change these settings later.">
      <v-card-text class="pt-0">
        <div class="share-section">Visitors</div>
        <v-switch v-model="options.anonymous" color="primary" density="compact" label="Anonymous" hint="Others see a pseudonym instead of the name" persistent-hint />
        <v-switch v-model="options.edit" color="primary" density="compact" label="May edit" hint="Change the model together with you" persistent-hint />
        <v-switch v-model="options.comment" color="primary" density="compact" label="May comment" hint="Leave comments on elements" persistent-hint />
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
    <v-card title="Your model is shared" text="Send this link. Everyone who is signed in can join while you share.">
      <v-card-text class="pt-0">
        <v-text-field :model-value="link" readonly density="compact" variant="outlined" hide-details append-inner-icon="mdi-content-copy" @click:append-inner="copy" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="copy">Copy</v-btn>
        <v-btn color="primary" variant="text" @click="closeDialog">Done</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog :model-value="shareDialog === 'quit'" width="480" persistent>
    <v-card title="Quit sharing" text="Everyone working on this model can no longer continue. Save the current state first.">
      <v-card-text class="pt-0">
        <v-radio-group v-model="target" hide-details density="compact">
          <v-radio color="primary" value="version" label="New version of your model" />
          <v-radio color="primary" value="model" label="New model" />
        </v-radio-group>
        <v-text-field v-if="target === 'model'" v-model="name" label="Name of the new model" density="compact" variant="outlined" hide-details class="mt-2" />
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-3">{{ error }} Nothing was closed, so you can try again.</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" :disabled="busy" @click="cancelQuit">Cancel</v-btn>
        <v-btn color="primary" variant="text" :loading="busy" @click="quit">{{ error ? 'Try again' : 'Save and quit' }}</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>

  <v-dialog :model-value="hostClosed || shareDialog === 'leave'" width="480" persistent>
    <v-card v-if="!confirmDiscard" :title="hostClosed ? 'The host has left' : 'Leave sharing'" :text="hostClosed ? 'The room is closed. Do you want to keep the current state as a model of your own and continue privately?' : 'You leave the shared model. Do you want to keep the current state as a model of your own and continue privately?'">
      <v-card-text class="pt-0">
        <v-text-field v-model="name" label="Name of the model" density="compact" variant="outlined" hide-details />
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-3">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-btn v-if="!hostClosed" variant="text" :disabled="busy" @click="closeDialog">Cancel</v-btn>
        <v-btn variant="text" :disabled="busy" @click="confirmDiscard = true">Discard</v-btn>
        <v-spacer />
        <v-btn color="primary" variant="text" :loading="busy" @click="keep">Continue privately</v-btn>
      </v-card-actions>
    </v-card>
    <v-card v-else title="Discard the state?" text="The current state of the model is lost.">
      <v-card-actions>
        <v-btn variant="text" :disabled="busy" @click="confirmDiscard = false">Back</v-btn>
        <v-spacer />
        <v-btn color="error" variant="text" :loading="busy" @click="drop">Discard</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { notifyError, notifySuccess } from '@/composables/useNotifications'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import type { HistoryMode } from '@/collab/converters/model/modelHistory'
import { currentShare, hostClosed, leaveAsVisitor, leaveShare, pendingTarget, reopenShare, shareDialog, shareLink, shareModel, shareProgress, type LeaveTarget } from './shareModel'

const router = useRouter()
const workspace = useModelWorkspaceStore()

const historyChoices: { value: HistoryMode; icon: string; title: string; hint: string }[] = [
  { value: 'none', icon: 'mdi-camera-outline', title: 'Current state', hint: 'Only the model as it is now' },
  { value: 'versions', icon: 'mdi-source-branch', title: 'Versions', hint: 'Releases and checkpoints' },
  { value: 'steps', icon: 'mdi-history', title: 'Every change', hint: 'Versions and all changes between them' }
]
const options = reactive({ anonymous: false, edit: true, comment: true, task: true, history: 'none' as HistoryMode })
const target = ref<LeaveTarget>('version')
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
  error.value = ''
  confirmDiscard.value = false
})

const share = () =>
  run(async () => {
    await shareModel(router, { ...options })
    shareDialog.value = 'link'
  })

const copy = async () => {
  try {
    await navigator.clipboard.writeText(link.value)
    notifySuccess('Link copied')
    closeDialog()
  } catch {
    notifyError('The link could not be copied.')
  }
}

const quit = () =>
  run(async () => {
    if (target.value === 'model' && !name.value.trim()) throw new Error('Enter a name for the new model.')
    await leaveShare(router, target.value, target.value === 'model' ? name.value.trim() : undefined)
    shareDialog.value = null
  })

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

.share-history__hint {
  opacity: 0.75;
}

.share-history--busy {
  pointer-events: none;
  opacity: 0.6;
}
</style>
