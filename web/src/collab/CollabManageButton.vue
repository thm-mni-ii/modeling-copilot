<template>
  <v-btn v-if="canManage" variant="tonal" size="small" prepend-icon="mdi-cog-outline" @click="open = true">Manage</v-btn>
  <CollabManageDialog v-if="canManage" v-model="open" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getRights } from './collabApi'
import CollabManageDialog from './CollabManageDialog.vue'

const canManage = ref(false)
const open = ref(false)

// Rooms and groups lie in nothing, so creating them takes manage everywhere; without it there is nothing to manage.
onMounted(async () => {
  try {
    canManage.value = (await getRights()).data.includes('manage')
  } catch {
    canManage.value = false
  }
})
</script>
