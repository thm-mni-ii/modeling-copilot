import { createRouter, createWebHashHistory } from 'vue-router'
import { useBearerToken } from '@/composables/useBearerToken'
import authService from '@/services/auth/auth.service'
import { isEmbedded, requestFbsToken, startFbsBridge, fbsAuthenticated, fbsConnectionError, fbsTargetPath, fbsConnecting } from '@/services/auth/fbsBridge'
import { useUserStore } from '@/stores/userStore'
import { isFeedbacksystemCallback, completeFeedbacksystemSignIn, renewFeedbacksystemToken } from '@/services/auth/fbsOidc'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/ViewLogin.vue')
    },
    {
      path: '/',
      name: 'Home',
      component: () => import('../views/ViewHome.vue')
    },
    {
      path: '/modeling/:modelId?',
      name: 'Modeling',
      component: () => import('../views/ViewModeling.vue'),
      props: true
    },
    {
      path: '/diagramLanguageEditor/:id?',
      name: 'DiagramLanguageEditor',
      component: () => import('../views/ViewDiagramLanguageEditor.vue')
    },
    {
      path: '/diagramLanguages',
      name: 'DiagramLanguages',
      component: () => import('../views/ViewDiagramLanguageOverview.vue')
    },
    {
      path: '/learning-path-templates/:id?/edit',
      name: 'LearningPathEditor',
      component: () => import('../views/ViewLearningPathEditor.vue')
    },
    {
      path: '/learning-path-templates',
      name: 'LearningPathTemplates',
      component: () => import('../views/ViewLearningPaths.vue')
    },
    {
      path: '/learning-path-runs/:id?',
      name: 'LearningPathRuns',
      component: () => import('../views/ViewLearningPaths.vue')
    },
    {
      path: '/surveys/:id?/edit',
      name: 'SurveyEditor',
      component: () => import('../views/ViewSurveyEditor.vue')
    },
    {
      path: '/surveys',
      name: 'Surveys',
      component: () => import('../views/ViewSurveys.vue')
    },
    {
      path: '/tasks',
      name: 'Tasks',
      component: () => import('../views/ViewTaskEditor.vue')
    },
    {
      path: '/collab',
      name: 'Collab',
      component: () => import('@/collab/rooms/ViewCollab.vue')
    },
    {
      path: '/404',
      name: 'View404Page',
      component: () => import('../views/View404Page.vue')
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/404'
    }
  ]
})

const nonAdminPages = ['LearningPathRuns', 'Login', 'Home', 'Modeling', 'View404Page', 'Collab']

router.beforeEach(async (to) => {
  if (!isEmbedded && isFeedbacksystemCallback()) {
    const target = await completeFeedbacksystemSignIn()
    useUserStore().reset()
    return target
  }
  const publicPages = ['/login']
  const authRequired = !publicPages.includes(to.path)
  const { bearerToken, clearToken } = useBearerToken()
  const adminRequired = !nonAdminPages.includes(to.name as string)
  const userStore = useUserStore()

  if (isEmbedded) {
    fbsTargetPath.value = to.path === '/login' ? '/' : to.fullPath
    if (!(await startFbsBridge())) {
      fbsAuthenticated.value = false
      clearToken()
      userStore.reset()
      return false
    }
    fbsConnecting.value = true
  }

  let loginValid = false
  try {
    if (bearerToken.value) {
      loginValid = (await authService.validateToken()).data === true
      if (!loginValid && (await (isEmbedded ? requestFbsToken() : renewFeedbacksystemToken()))) {
        loginValid = (await authService.validateToken()).data === true
      }
    }
    if (isEmbedded && !loginValid) {
      fbsConnectionError.value = 'The sign-in token received from the Feedbacksystem was rejected. Please sign in to the Feedbacksystem again and retry.'
    }
  } catch {
    if (isEmbedded) fbsConnectionError.value = 'Your sign-in could not be verified. Please check the connection to the Modeling Copilot API and try again.'
  } finally {
    if (isEmbedded) {
      fbsConnecting.value = false
      fbsAuthenticated.value = loginValid
    }
  }

  if (!loginValid) {
    clearToken()
    userStore.reset()
    if (isEmbedded) return false
    if (authRequired) return { path: '/login', query: { returnTo: to.fullPath } }
  }
  if (isEmbedded && to.path === '/login') return '/'
  if (adminRequired && (await userStore.ensureGlobalRole()) !== 'ADMIN') return '/404'
  return true
})

export default router
