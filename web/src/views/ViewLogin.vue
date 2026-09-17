<template>
  <v-container fluid class="login">
    <v-row justify="center" align="center" class="login__row">
      <v-col cols="12" md="8" lg="6" class="login__col">
        <v-card class="login__token-card" max-width="480">
          <v-card-title class="text-h6">Bearer Token</v-card-title>
          <v-card-text>
            <v-text-field v-model="bearerToken" label="Bearer Token" placeholder="Enter bearer token" :type="showToken ? 'text' : 'password'" :append-inner-icon="showToken ? 'mdi-eye-off' : 'mdi-eye'" density="comfortable" variant="outlined" hide-details="auto" @click:append-inner="showToken = !showToken" />
            <v-alert v-if="bearerToken && isChecking" type="info" variant="tonal" density="compact" class="mt-3"> Checking token... </v-alert>
            <pre v-if="isValid && claims" class="login__code mt-3"><code>{{ JSON.stringify(claims, null, 2) }}</code></pre>
          </v-card-text>
          <v-card-actions>
            <v-btn variant="text" :disabled="!bearerToken" @click="removeToken">Delete</v-btn>
            <v-spacer />
            <v-btn color="primary" :disabled="!isValid" @click="login">Login</v-btn>
          </v-card-actions>

          <v-expansion-panels variant="accordion">
            <v-expansion-panel title="How do I get a token?">
              <v-expansion-panel-text>
                <p class="mb-2">1. Start the feedback system locally:</p>
                <pre class="login__code"><code>git clone git@github.com:thm-mni-ii/feedbacksystem.git
cd feedbacksystem
docker compose up -d --build</code></pre>
                <p class="mb-2">
                  2. The feedback system is now available at
                  <a href="https://localhost" target="_blank" rel="noopener">https://localhost</a>.
                </p>
                <p class="mb-2">3. Log in with <br /><strong>Username:</strong> <code>admin</code> and <br /><strong>Password:</strong> <code>AWObcEyYi6SZaYKU9daTgKt</code></p>
                <p class="mb-0">4. In Chrome: right-click &rarr; "Inspect" &rarr; "Application" tab &rarr; "Local Storage" &rarr; copy the value of the <code>token</code> key.</p>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useBearerToken } from '@/composables/useBearerToken'
import { useUserStore } from '@/stores/userStore'
import authService from '@/services/auth/auth.service'
import type { TokenClaims } from '@/services/api/types/auth'
import { notifyError, notifySuccess } from '@/composables/useNotifications'

const router = useRouter()
const userStore = useUserStore()
const { bearerToken, persistToken, clearToken } = useBearerToken()
const showToken = ref(false)
const isChecking = ref(false)
const isValid = ref<boolean | null>(null)
const claims = ref<TokenClaims | null>(null)

let debounceTimer: ReturnType<typeof setTimeout> | undefined

const checkToken = async () => {
  isChecking.value = true
  try {
    const validation = await authService.validateToken()
    isValid.value = validation.data
    claims.value = isValid.value ? (await authService.getMe()).data : null
    if (isValid.value) notifySuccess('Token is valid.')
    else notifyError('Token is invalid.')
  } catch {
    isValid.value = false
    claims.value = null
    notifyError('Token is invalid.')
  }
  isChecking.value = false
}

onMounted(() => {
  if (bearerToken.value) {
    checkToken()
  }
})

// Persist and validate on every change, debounced to avoid a request per keystroke
watch(bearerToken, (value) => {
  persistToken()
  isValid.value = null
  claims.value = null
  userStore.reset()
  clearTimeout(debounceTimer)

  if (!value) return
  debounceTimer = setTimeout(checkToken, 400)
})

const removeToken = () => {
  clearToken()
  isValid.value = null
  claims.value = null
  userStore.reset()
}

const login = () => {
  router.push('/')
}
</script>

<style scoped lang="scss">
.login {
  min-height: 100vh;
}

.login__token-card {
  margin-left: auto;
  margin-right: auto;
}

.login__code {
  white-space: pre-wrap;
  word-break: break-word;
  background-color: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
  padding: 8px 12px;
  font-size: 0.85rem;
}
</style>
