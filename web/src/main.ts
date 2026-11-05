import { createApp } from 'vue'
import { createPinia } from 'pinia'

// Components
import App from './App.vue'

// Composables
import router from './router'

// Plugins
import { registerPlugins } from './plugins'
import vuetify from './plugins/vuetify'

import { isEmbedded } from './services/auth/fbsBridge'
import { handOverFeedbacksystemRenewal, isFeedbacksystemCallback, resumeFeedbacksystemSession } from './services/auth/fbsOidc'

import '@maxgraph/core/css/common.css'

import { Client } from '@maxgraph/core'
import { registerCustomShapes } from './utils/shapeRegistry'
Client.setImageBasePath('/images/')
registerCustomShapes()

// The hidden frame of a token renewal only hands the response back to the page.
if (isEmbedded && isFeedbacksystemCallback()) {
  handOverFeedbacksystemRenewal()
} else {
  if (!isEmbedded) resumeFeedbacksystemSession()

  const pinia = createPinia()
  const app = createApp(App)
  registerPlugins()

  app.use(router)
  app.use(vuetify)
  app.use(pinia)
  app.mount('#app')
}
