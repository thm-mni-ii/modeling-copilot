<template>
  <div class="group-work">
    <div class="d-flex align-center flex-wrap ga-3 mb-4">
      <v-text-field v-model="search" placeholder="Search rooms, people or models" prepend-inner-icon="mdi-magnify" density="compact" hide-details clearable class="search" />
      <v-btn icon="mdi-information-outline" size="small" :variant="info ? 'tonal' : 'text'" :color="info ? 'primary' : undefined" aria-label="About group work" :aria-expanded="info" @click="info = !info" />
      <v-spacer />
      <v-btn color="primary" :variant="importing ? 'tonal' : 'flat'" :prepend-icon="importing ? 'mdi-close' : 'mdi-file-upload-outline'" @click="importing = !importing">{{ importing ? 'Close import' : 'Import CSV' }}</v-btn>
    </div>
    <!-- Was man über Gruppen, Räume und den Import wissen sollte; auf und zu wie die Infos von collab-kit oben rechts. -->
    <v-expand-transition>
      <v-sheet v-show="info" border rounded="lg" class="info pa-4 mb-6">
        <div class="info__grid">
          <div>
            <h4>Groups and rooms</h4>
            <p>Each group in the CSV becomes a group with its members and a room of the same name for its models. The group may see, comment on and edit everything in its room. You'll find both again under "Groups" and "Rooms".</p>
            <h4>Course name</h4>
            <p>Always enter one, such as "DBS WS 26". The same course and group name mean the same group. A new semester gets a new course name, and with it new groups.</p>
            <h4>Importing again</h4>
            <p>You can load the same or an updated CSV as often as you like. Only what's missing is added: new people and models for new tasks. Nobody is removed, and existing models stay as they are.</p>
          </div>
          <div>
            <h4>The CSV</h4>
            <p>The participant list exported from Moodle with the columns "Anmeldename", "Gruppen" and "Fallstudie". A case study number is matched to the task whose name starts with it, such as F1.</p>
            <h4>People not in the Feedbacksystem</h4>
            <p>Anyone who has never signed in to the Feedbacksystem can't be added yet. Ask them to sign in once, then import the CSV again.</p>
            <h4>Dashed names</h4>
            <p>The person hasn't opened the Modeling Copilot yet. Until then, their name comes from the CSV.</p>
            <h4>Removing people</h4>
            <p>The import never removes anyone. Do that by hand under "Groups".</p>
          </div>
        </div>
      </v-sheet>
    </v-expand-transition>
    <!-- Der Import bleibt offen, solange er gebraucht wird; seine Räume erscheinen danach sofort darunter. -->
    <v-expand-transition>
      <v-sheet v-show="importing" border rounded="lg" class="pa-4 mb-6"><GroupWorkImport :courses="overview?.courses ?? []" @created="created" /></v-sheet>
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
const info = ref(false)
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

.info {
  font-size: 13px;
  line-height: 1.55;
}

.info__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 4px 28px;
}

.info h4 {
  margin: 10px 0 2px;
  font-size: 13px;
  font-weight: 600;
}

.info__grid > div > h4:first-child {
  margin-top: 0;
}

.info p {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), 0.7);
}
</style>
