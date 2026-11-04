<template>
  <v-dialog :model-value="shareDialog === 'ask'" width="440" persistent>
    <v-card title="Share this model" text="Others join through a link. You decide what they may do; you can change it later.">
      <v-card-text class="pt-0">
        <v-switch v-model="options.anonymous" color="primary" density="compact" hide-details label="Visitors anonymous" />
        <v-switch v-model="options.edit" color="primary" density="compact" hide-details label="Visitors may edit" />
        <v-switch v-model="options.comment" color="primary" density="compact" hide-details label="Visitors may comment" />
        <v-switch v-if="workspace.taskReference" v-model="options.task" color="primary" density="compact" hide-details label="Share the task" />
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
        <v-btn variant="text" @click="copy">{{ copied ? 'Copied' : 'Copy' }}</v-btn>
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

  <v-dialog :model-value="hostClosed" width="480" persistent>
    <v-card v-if="!confirmDiscard" title="The host has left" text="The room is closed. Do you want to keep the current state as a model of your own?">
      <v-card-text class="pt-0">
        <v-text-field v-model="name" label="Name of the model" density="compact" variant="outlined" hide-details />
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mt-3">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions>
        <v-btn variant="text" :disabled="busy" @click="confirmDiscard = true">Discard</v-btn>
        <v-spacer />
        <v-btn color="primary" variant="text" :loading="busy" @click="keep">Save as model</v-btn>
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
import { notifyError } from '@/composables/useNotifications'
import { useModelWorkspaceStore } from '@/stores/modelWorkspace'
import { currentShare, hostClosed, leaveAsVisitor, leaveShare, reopenShare, shareDialog, shareLink, shareModel, type LeaveTarget } from './shareModel'

const router = useRouter()
const workspace = useModelWorkspaceStore()

const options = reactive({ anonymous: false, edit: true, comment: true, task: true })
const target = ref<LeaveTarget>('version')
const name = ref('')
const busy = ref(false)
const error = ref('')
const copied = ref(false)
const confirmDiscard = ref(false)

const closeDialog = () => (shareDialog.value = null)

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
watch([() => shareDialog.value === 'quit', hostClosed], ([quitting, closed]) => {
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
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
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
  })

const keep = () =>
  run(async () => {
    if (!name.value.trim()) throw new Error('Enter a name for the model.')
    await leaveAsVisitor(router, true, name.value.trim())
  })

const drop = () => run(() => leaveAsVisitor(router, false))
</script>
