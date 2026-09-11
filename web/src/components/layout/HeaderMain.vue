<template>
  <v-app-bar :elevation="1">
    <v-app-bar-title>
      <router-link to="/">
        <IconFBS class="icon" />
      </router-link>
    </v-app-bar-title>

    <template #append>
      <v-btn to="/" active-class="active" prepend-icon="mdi-folder-outline">
        <span> Modelle </span>
        <v-tooltip activator="parent" location="bottom"> Meine Modelle </v-tooltip>
      </v-btn>
      <v-btn to="/diagramLanguages" active-class="active" prepend-icon="mdi-view-list">
        <span> Languages </span>
        <v-tooltip activator="parent" location="bottom"> Diagram Language Overview </v-tooltip>
      </v-btn>
      <v-btn to="/diagramLanguageEditor" active-class="active" prepend-icon="mdi-application-edit">
        <span> Editor </span>
        <v-tooltip activator="parent" location="bottom"> Diagram Language Editor </v-tooltip>
      </v-btn>
      <v-btn to="/tasks" active-class="active" prepend-icon="mdi-clipboard-text-outline">
        <span> Tasks </span>
        <v-tooltip activator="parent" location="bottom"> Create and manage tasks </v-tooltip>
      </v-btn>
      <v-btn prepend-icon="mdi-logout" @click="logout">
        <span> Logout </span>
        <v-tooltip activator="parent" location="bottom"> Logout </v-tooltip>
      </v-btn>
    </template>
  </v-app-bar>
</template>

<script setup lang="ts">
import IconFBS from '@/components/icons/IconFBS.vue'

import { RouterLink, useRouter } from 'vue-router'

const router = useRouter()

const logout = () => {
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
