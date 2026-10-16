<template>
  <v-btn v-if="mayManage" to="/collab" active-class="active" prepend-icon="mdi-account-group-outline">
    <span> Collab </span>
    <v-tooltip activator="parent" location="bottom"> Manage collaboration </v-tooltip>
  </v-btn>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useBearerToken } from '@/composables/useBearerToken'
import { mayManageAll } from './access'

const { bearerToken } = useBearerToken()
const mayManage = ref(false)

// The header stays from the login page on, so every new token asks again; only the answer to the latest counts.
watch(
  bearerToken,
  async (token) => {
    const may = await mayManageAll()
    if (token === bearerToken.value) mayManage.value = may
  },
  { immediate: true }
)
</script>
