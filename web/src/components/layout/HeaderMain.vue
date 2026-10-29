<template>
  <v-app-bar :elevation="1" class="main-header">
    <v-app-bar-title class="brand-title">
      <RouterLink :to="{ name: 'Home' }" class="brand-link" aria-label="Modeling Copilot home">
        <IconFBS class="brand-icon" aria-hidden="true" />
      </RouterLink>
    </v-app-bar-title>

    <template #append>
      <nav aria-label="Main navigation" class="d-flex align-center ga-1 mr-2">
        <v-btn :to="{ name: 'Home' }" exact variant="text" icon="mdi-home-outline" aria-label="Home">
          <v-icon icon="mdi-home-outline" />
          <v-tooltip activator="parent" location="bottom">Home</v-tooltip>
        </v-btn>
        <v-menu location="bottom end" max-height="min(600px, 80vh)">
          <template #activator="{ props }">
            <v-btn v-bind="props" variant="tonal" prepend-icon="mdi-view-grid-outline" append-icon="mdi-chevron-down">Navigation</v-btn>
          </template>
          <v-list nav aria-label="Functions" class="navigation-menu">
            <v-list-subheader>Workspace</v-list-subheader>
            <v-list-item v-for="item in navigation.workspaceItems" :key="item.route" :to="{ name: item.route }" :prepend-icon="item.icon" :title="item.title" color="primary-dark" />
            <template v-if="navigation.isAdmin">
              <v-divider class="my-2" />
              <v-list-subheader>Administration</v-list-subheader>
              <v-list-item v-for="item in navigation.adminItems" :key="item.route" :to="{ name: item.route }" :prepend-icon="item.icon" :title="item.title" color="primary-dark" />
            </template>
            <v-divider class="my-2" />
            <v-list-item prepend-icon="mdi-logout" title="Logout" @click="logout" />
          </v-list>
        </v-menu>
      </nav>
    </template>
  </v-app-bar>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import IconFBS from '@/components/icons/IconFBS.vue'
import { useNavigationStore } from '@/stores/navigation'
import { useUserStore } from '@/stores/userStore'
import { useBearerToken } from '@/composables/useBearerToken'
import { isEmbedded } from '@/services/auth/fbsBridge'
import { forgetFeedbacksystemSession } from '@/services/auth/fbsOidc'

const router = useRouter()
const userStore = useUserStore()
const navigation = useNavigationStore()
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

<style scoped>
.brand-title {
  min-width: 0;
}

.brand-link {
  display: flex;
  align-items: center;
  width: fit-content;
  max-width: 100%;
}

.brand-link:focus-visible {
  outline: 2px solid rgb(var(--v-theme-primary-dark));
  outline-offset: 4px;
}

.brand-icon {
  display: block;
  width: 250px;
  max-width: 100%;
  height: auto;
  max-height: 36px;
}

.navigation-menu {
  min-width: 260px;
}
</style>
