<template>
  <v-container class="d-flex justify-center align-center join-view">
    <div v-if="error" class="text-center">
      <p class="mb-4">{{ error }}</p>
      <v-btn color="primary" variant="flat" @click="router.replace('/')">Back to the Copilot</v-btn>
    </div>
    <div v-else class="text-center">
      <v-progress-circular indeterminate color="primary" />
      <p class="mt-4">Joining the shared model…</p>
    </div>
  </v-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { joinShare } from './shareModel'

const route = useRoute()
const router = useRouter()
const error = ref('')

// The sign-in came before, in the router guard; a refusal such as a closed link is shown here, the model opens otherwise.
onMounted(async () => {
  try {
    await joinShare(router, String(route.params.roomId))
  } catch (cause) {
    error.value = (cause as Error).message
  }
})
</script>

<style scoped>
.join-view {
  min-height: 60vh;
}
</style>
