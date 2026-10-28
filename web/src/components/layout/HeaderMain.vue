<template>
  <v-app-bar :elevation="1">
    <v-app-bar-title>
      <router-link to="/">
        <IconFBS class="icon" />
      </router-link>
    </v-app-bar-title>

    <template #append>
      <v-btn to="/" active-class="active" prepend-icon="mdi-folder-outline">
        <span> Models </span>
        <v-tooltip activator="parent" location="bottom"> My models </v-tooltip>
      </v-btn>
      <v-btn to="/diagramLanguages" active-class="active" prepend-icon="mdi-view-list">
        <span> Languages </span>
        <v-tooltip activator="parent" location="bottom"> Diagram Language Overview </v-tooltip>
      </v-btn>
      <v-btn to="/diagramLanguageEditor" active-class="active" prepend-icon="mdi-application-edit">
        <span> Editor </span>
        <v-tooltip activator="parent" location="bottom"> Diagram Language Editor </v-tooltip>
      </v-btn>
      <v-btn v-if="isAdmin" to="/tasks" active-class="active" prepend-icon="mdi-clipboard-text-outline">
        <span> Tasks </span>
        <v-tooltip activator="parent" location="bottom"> Create and manage tasks </v-tooltip>
      </v-btn>
      <v-btn to="/learning-path-runs" prepend-icon="mdi-map-marker-path">Learning paths</v-btn>
      <v-btn v-if="isAdmin" to="/learning-path-templates" prepend-icon="mdi-map-plus">Path templates</v-btn>
      <CollabNavButton />
      <v-btn v-if="isAdmin" to="/surveys" prepend-icon="mdi-form-select">Fragebögen</v-btn>
      <v-btn prepend-icon="mdi-logout" @click="logout">
        <span> Logout </span>
        <v-tooltip activator="parent" location="bottom"> Logout </v-tooltip>
      </v-btn>
    </template>
  </v-app-bar>
</template>

<script setup lang="ts">
import IconFBS from '@/components/icons/IconFBS.vue'
import CollabNavButton from '@/collab/rooms/CollabNavButton.vue'

import { computed, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/userStore'
import { useBearerToken } from '@/composables/useBearerToken'
import { isEmbedded } from '@/services/auth/fbsBridge'
import { forgetFeedbacksystemSession } from '@/services/auth/fbsOidc'

const router = useRouter()
const userStore = useUserStore()
const isAdmin = computed(() => userStore.globalRole === 'ADMIN')
onMounted(() => void userStore.ensureGlobalRole())

const logout = () => {
  if (!isEmbedded) {
    useBearerToken().clearToken()
    forgetFeedbacksystemSession()
    userStore.reset()
  }
  router.push('/login')
}
</script>

<style scoped lang="scss">
.icon {
  display: block;
  height: 36px;
  width: 250px;
  margin-right: 20px;
}
</style>
