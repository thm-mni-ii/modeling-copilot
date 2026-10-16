<template>
  <v-container fluid class="pa-3 collab-view">
    <div class="d-flex align-center mb-3 ga-2">
      <div>
        <h1 class="text-h5">Collaboration</h1>
        <p class="text-medium-emphasis mb-0">Rooms, groups and who may work where in collab-kit.</p>
      </div>
      <v-spacer />
      <v-btn v-if="mayManage" prepend-icon="mdi-plus" color="primary" @click="panel?.openCreate()">{{ tab === 'rooms' ? 'New room' : 'New group' }}</v-btn>
    </div>

    <v-progress-linear v-if="mayManage === null" indeterminate />
    <template v-else-if="mayManage">
      <v-tabs v-model="tab" class="mb-3"><v-tab value="rooms">Rooms</v-tab><v-tab value="groups">Groups</v-tab></v-tabs>
      <CollabRoomsPanel v-if="tab === 'rooms'" ref="panel" />
      <CollabGroupsPanel v-else ref="panel" />
    </template>
    <v-card v-else class="collab-view__denied d-flex align-center justify-center" variant="outlined">
      <div class="text-center text-medium-emphasis">
        <v-icon size="48">mdi-lock-outline</v-icon>
        <div class="mt-2">Managing rooms and groups takes the right manage everywhere in collab-kit.</div>
      </div>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { mayManageAll } from './access'
import CollabGroupsPanel from './CollabGroupsPanel.vue'
import CollabRoomsPanel from './CollabRoomsPanel.vue'
import { useCollabDirectory } from './useCollabDirectory'

const tab = ref<'rooms' | 'groups'>('rooms')
const panel = ref<{ openCreate: () => void } | null>(null)
const mayManage = ref<boolean | null>(null)
const { load } = useCollabDirectory()

// The route is open to everyone, so collab-kit decides here, as it does for every change.
onMounted(async () => {
  mayManage.value = await mayManageAll()
  if (mayManage.value) await load()
})
</script>

<style scoped>
.collab-view {
  height: calc(100vh - var(--v-layout-top, 0px));
  display: flex;
  flex-direction: column;
}

.collab-view__denied {
  flex: 1;
}
</style>
