<template>
  <div class="group-work">
    <div class="d-flex align-center flex-wrap ga-3 mb-4">
      <v-text-field v-model="search" placeholder="Search rooms, people or models" prepend-inner-icon="mdi-magnify" density="compact" hide-details clearable class="search" />
      <v-spacer />
      <v-btn color="primary" :variant="importing ? 'tonal' : 'flat'" :prepend-icon="importing ? 'mdi-close' : 'mdi-file-upload-outline'" @click="importing = !importing">{{ importing ? 'Close import' : 'Import CSV' }}</v-btn>
    </div>
    <!-- Der Import bleibt offen, solange er gebraucht wird; seine Räume erscheinen danach sofort darunter. -->
    <v-expand-transition>
      <v-sheet v-show="importing" border rounded="lg" class="pa-4 mb-6"><GroupWorkImport @created="created" /></v-sheet>
    </v-expand-transition>
    <GroupModels ref="overview" imported :search="search ?? ''" />
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef } from 'vue'
import GroupModels from './GroupModels.vue'
import GroupWorkImport from './GroupWorkImport.vue'

/** Meldet, dass Räume angelegt wurden, damit auch <ck-management> neu lädt. */
const emit = defineEmits<{ created: [] }>()

const search = ref<string | null>('')
const importing = ref(false)
const overview = shallowRef<InstanceType<typeof GroupModels>>()

const created = () => {
  void overview.value?.reload()
  emit('created')
}
</script>

<style scoped>
.search {
  max-width: 320px;
}
</style>
