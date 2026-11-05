<template>
  <v-container class="home-page py-8 py-md-12" max-width="1200">
    <header class="home-heading mb-8">
      <span class="text-overline text-medium-emphasis">Modeling Copilot</span>
      <h1 class="text-h4 font-weight-bold mt-1">Your workspace</h1>
      <p class="text-body-1 text-medium-emphasis mt-3 mb-0">Create a model, continue learning, or pick up where you left off.</p>
    </header>

    <section aria-labelledby="workspace-title">
      <h2 id="workspace-title" class="text-h6 mb-4">Get started</h2>
      <div class="tile-grid">
        <v-card v-for="item in navigation.workspaceItems" :key="item.route" :to="{ name: item.route }" variant="outlined" rounded="lg" class="feature-tile">
          <div class="tile-icon"><v-icon :icon="item.icon" size="28" /></div>
          <h3 class="text-h6 mt-5 mb-2">{{ item.title }}</h3>
          <p class="text-body-2 text-medium-emphasis mb-5">{{ item.description }}</p>
          <div class="tile-action text-body-2 font-weight-medium">Open {{ item.title }}<v-icon icon="mdi-arrow-right" size="20" aria-hidden="true" /></div>
        </v-card>
      </div>
    </section>

    <section v-if="navigation.isAdmin" aria-labelledby="admin-title" class="admin-section mt-10 pt-8">
      <div class="d-flex align-center flex-wrap ga-3 mb-2">
        <h2 id="admin-title" class="text-h6">Administration</h2>
        <v-chip size="small" prepend-icon="mdi-shield-account-outline" variant="tonal">Admin</v-chip>
      </div>
      <p class="text-body-2 text-medium-emphasis mb-5">Manage the content and tools available in Modeling Copilot.</p>
      <div class="tile-grid tile-grid--admin">
        <v-card v-for="item in navigation.adminItems" :key="item.route" :to="{ name: item.route }" variant="outlined" rounded="lg" class="feature-tile">
          <div class="tile-icon tile-icon--admin"><v-icon :icon="item.icon" size="26" /></div>
          <h3 class="text-h6 mt-5 mb-2">{{ item.title }}</h3>
          <p class="text-body-2 text-medium-emphasis mb-5">{{ item.description }}</p>
          <div class="tile-action text-body-2 font-weight-medium">Manage<v-icon icon="mdi-arrow-right" size="20" aria-hidden="true" /></div>
        </v-card>
      </div>
    </section>
  </v-container>
</template>

<script setup lang="ts">
import { useNavigationStore } from '@/stores/navigation'

const navigation = useNavigationStore()
</script>

<style scoped>
.home-page {
  padding-inline: clamp(16px, 4vw, 40px);
}

.tile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.tile-grid--admin {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.feature-tile {
  display: flex;
  flex-direction: column;
  padding: 24px;
  border-color: rgba(var(--v-theme-dark-gray), 0.18);
  text-decoration: none;
}

.feature-tile:focus-visible {
  outline: 3px solid rgb(var(--v-theme-primary-dark));
  outline-offset: 3px;
}

.tile-icon {
  display: grid;
  place-items: center;
  align-self: flex-start;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  color: rgb(var(--v-theme-primary-dark));
  background: rgba(var(--v-theme-primary), 0.12);
}

.tile-icon--admin {
  color: rgb(var(--v-theme-dark-gray));
  background: rgba(var(--v-theme-dark-gray), 0.07);
}

.tile-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: auto;
  color: rgb(var(--v-theme-primary-dark));
}

.admin-section {
  border-top: 1px solid rgba(var(--v-theme-dark-gray), 0.14);
}

@media (max-width: 959px) {
  .tile-grid--admin {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 599px) {
  .tile-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }
}
</style>
