<template>
  <v-app>
    <HeaderMain v-if="showLayout" />

    <v-main>
      <FeedbacksystemLogin v-if="connectionBlocked" />
      <RouterView v-else />
    </v-main>

    <FooterMain v-if="showLayout" />
    <AppNotification />
  </v-app>
</template>

<script setup lang="ts">
import { RouterView, useRoute } from 'vue-router'
import { computed } from 'vue'
import { isEmbedded, fbsAuthenticated, fbsConnectionError } from '@/services/auth/fbsBridge'

import FeedbacksystemLogin from '@/components/auth/FeedbacksystemLogin.vue'

import FooterMain from '@/components/layout/FooterMain.vue'
import HeaderMain from '@/components/layout/HeaderMain.vue'
import AppNotification from '@/components/layout/AppNotification.vue'

const connectionBlocked = computed(() => isEmbedded && (!fbsAuthenticated.value || !!fbsConnectionError.value))
const route = useRoute()
// Mount authenticated navigation only after the route guard has accepted a page.
const showLayout = computed(() => !connectionBlocked.value && !!route.name && route.name !== 'Login')
</script>

<style scoped lang="scss"></style>
