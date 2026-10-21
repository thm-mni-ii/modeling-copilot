<template>
  <v-container class="feedbacksystem-login">
    <v-card class="feedbacksystem-login__card pa-4 pa-sm-6" max-width="560" rounded="lg">
      <v-card-title class="text-h5 text-wrap">Sign in to Modeling Copilot</v-card-title>
      <v-card-text class="pt-2">
        <p class="mb-6">Use your Feedbacksystem account to access your models.</p>
        <div aria-live="polite" :aria-busy="busy">
          <template v-if="busy">
            <v-progress-linear indeterminate class="mb-3" aria-label="Signing in" />
            <p>{{ isEmbedded ? 'Connecting to your Feedbacksystem session…' : 'Redirecting to the Feedbacksystem…' }}</p>
          </template>
          <v-alert v-else-if="error" type="error" variant="tonal">{{ error }}</v-alert>
        </div>
        <v-btn v-if="!isEmbedded || error" class="mt-5" color="primary" variant="flat" size="large" block :loading="busy" :disabled="busy" @click="connect">
          {{ error ? 'Try again' : 'Sign in with Feedbacksystem' }}
        </v-btn>
        <p v-if="!isEmbedded" class="text-body-2 text-medium-emphasis mt-3">You will return here after signing in.</p>
      </v-card-text>

      <v-divider class="my-2" />
      <v-expansion-panels variant="accordion" elevation="0">
        <v-expansion-panel title="How to connect to the Feedbacksystem">
          <v-expansion-panel-text>
            <ol class="pl-5">
              <li>Click “Sign in with Feedbacksystem” and sign in with your account.</li>
              <li>After sign-in, you will return to the page you wanted to open.</li>
            </ol>
            <p class="mt-3">When you open the Copilot inside the Feedbacksystem, your session is connected automatically.</p>
            <p class="mt-3">If the connection fails, check that you can open the Feedbacksystem below, sign in there, and try again.</p>
            <a v-if="feedbacksystemUrl" class="feedbacksystem-login__url d-inline-block mt-2" :href="feedbacksystemUrl" target="_blank" rel="noopener noreferrer">{{ feedbacksystemUrl }}</a>

            <template v-if="isDevelopment">
              <h2 class="text-subtitle-2 mt-5 mb-2">Local setup</h2>
              <p>Start the Feedbacksystem, the Copilot frontend and its API. In the Feedbacksystem application management, register the Copilot with these settings:</p>
              <dl class="feedbacksystem-login__settings mt-3">
                <dt>Provider / client ID</dt>
                <dd>{{ providerId }}</dd>
                <dt>Entry URL</dt>
                <dd>{{ entryUrl }}</dd>
                <dt>Mode</dt>
                <dd>IFRAME or EXTERNAL</dd>
                <dt>OIDC</dt>
                <dd>Enabled · PUBLIC client · no secret</dd>
                <dt>Redirect URI</dt>
                <dd>{{ fbsRedirectUri }}</dd>
                <dt>Scopes</dt>
                <dd>openid, profile, email</dd>
              </dl>
              <p class="mt-3">Keep the application active and use the Feedbacksystem address shown above for both sign-in modes.</p>
            </template>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isEmbedded, fbsConnectionError, fbsConnecting, fbsTargetPath } from '@/services/auth/fbsBridge'
import { fbsRedirectUri, signInWithFeedbacksystem, standaloneSignInError, standaloneSigningIn } from '@/services/auth/fbsOidc'

const router = useRouter()
const route = useRoute()
const retrying = ref(false)
const feedbacksystemUrl = import.meta.env.VITE_FBS_HOST_ORIGIN
const providerId = import.meta.env.VITE_FBS_PROVIDER_ID
const isDevelopment = import.meta.env.DEV
const entryUrl = new URL(import.meta.env.BASE_URL, window.location.origin).href
const error = computed(() => (isEmbedded ? fbsConnectionError.value : standaloneSignInError.value))
const busy = computed(() => (isEmbedded ? retrying.value || fbsConnecting.value || !fbsConnectionError.value : standaloneSigningIn.value))

const connect = () => (isEmbedded ? retryConnection() : signInWithFeedbacksystem(route.query.returnTo))

const retryConnection = async () => {
  retrying.value = true
  try {
    const { path, query, hash } = router.resolve(fbsTargetPath.value)
    await router.replace({ path, query, hash, force: true })
  } finally {
    retrying.value = false
  }
}
</script>

<style scoped lang="scss">
.feedbacksystem-login {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding-block: 32px;

  &__card {
    width: 100%;
  }

  &__url,
  &__settings dd {
    overflow-wrap: anywhere;
  }

  &__settings {
    display: grid;
    gap: 4px;

    dt {
      font-weight: 600;
    }

    dd {
      margin: 0 0 8px;
    }
  }
}
</style>
