import { createRouter, createWebHashHistory } from 'vue-router'
import { useBearerToken } from '@/composables/useBearerToken'
import authService from '@/services/auth/auth.service'
import { isEmbedded, requestFbsToken, startFbsBridge, fbsAuthenticated, fbsConnectionError, fbsTargetPath, fbsConnecting } from '@/services/auth/fbsBridge'
import { useUserStore } from '@/stores/userStore'
import learningPaths from '@/services/learningPaths'
import { isFeedbacksystemCallback, completeFeedbacksystemSignIn, renewFeedbacksystemToken } from '@/services/auth/fbsOidc'

const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/submissions/:assignmentId?',
      name: 'Submissions',
      component: () => import('../views/ViewSubmissions.vue')
    },
    {
      path: '/submission-runs/:runId',
      name: 'SubmissionRun',
      component: () => import('../views/ViewSubmissionRun.vue')
    },
    {
      path: '/submission-feedback/:submissionId',
      name: 'SubmissionReview',
      component: () => import('../views/ViewSubmissionReview.vue')
    },
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
      path: '/models',
      name: 'Models',
      component: () => import('../views/ViewModels.vue')
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
      path: '/learning-path-progress',
      redirect: '/analytics/learning-paths'
    },
    {
      path: '/analytics',
      component: () => import('../views/analytics/ViewAnalytics.vue'),
      meta: { staff: true },
      children: [
        { path: '', name: 'Analytics', redirect: { name: 'AnalyticsPlatformOverview' } },
        {
          path: 'platform',
          component: () => import('../views/analytics/ViewAnalyticsPlatform.vue'),
          children: [
            { path: '', redirect: { name: 'AnalyticsPlatformOverview' } },
            { path: 'overview', name: 'AnalyticsPlatformOverview', component: () => import('../views/analytics/ViewAnalyticsPlatformOverview.vue') },
            { path: 'tasks', name: 'AnalyticsPlatformTasks', component: () => import('../views/analytics/ViewAnalyticsPlatformTasks.vue') },
            { path: 'people', name: 'AnalyticsPlatformPeople', component: () => import('../views/analytics/ViewAnalyticsPlatformPeople.vue') }
          ]
        },
        { path: 'tours', name: 'AnalyticsTours', component: () => import('../views/analytics/ViewAnalyticsTours.vue') },
        { path: 'tours/:tourId', name: 'AnalyticsTour', component: () => import('../views/analytics/ViewAnalyticsTour.vue'), props: true },
        { path: 'learning-paths', name: 'AnalyticsLearningPaths', component: () => import('../views/analytics/ViewAnalyticsLearningPaths.vue') },
        { path: 'learning-paths/:templateId', name: 'AnalyticsLearningPath', component: () => import('../views/analytics/ViewAnalyticsLearningPath.vue'), props: true },
        { path: 'surveys', name: 'AnalyticsSurveys', component: () => import('../views/analytics/ViewAnalyticsSurveys.vue') },
        { path: 'surveys/:surveyId', name: 'AnalyticsSurvey', component: () => import('../views/analytics/ViewAnalyticsSurvey.vue'), props: true }
      ]
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
      path: '/synonym-glossary/:taskId?',
      name: 'SynonymGlossary',
      component: () => import('../views/ViewSynonymGlossary.vue')
    },
    {
      path: '/collab',
      name: 'Collab',
      component: () => import('@/collab/rooms/ViewCollab.vue')
    },
    {
      path: '/modeling/share/:roomId',
      name: 'Join',
      component: () => import('@/collab/sharing/ViewJoin.vue')
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

// Everything outside this list requires ADMIN, including direct URL navigation.
const nonAdminPages = ['Submissions', 'SubmissionRun', 'SubmissionReview', 'LearningPathRuns', 'Login', 'Home', 'Models', 'Modeling', 'Join', 'View404Page']

router.beforeEach(async (to) => {
  if (!isEmbedded && isFeedbacksystemCallback()) {
    const target = await completeFeedbacksystemSignIn()
    useUserStore().reset()
    return target
  }
  const publicPages = ['/login']
  const authRequired = !publicPages.includes(to.path)
  const { bearerToken, clearToken } = useBearerToken()
  const staffPage = to.matched.some((record) => record.meta.staff)
  const adminRequired = !staffPage && !nonAdminPages.includes(to.name as string)
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
  if (staffPage) {
    try {
      if (!(await learningPaths.progressAccess()).data.canView) return '/404'
    } catch {
      return '/404'
    }
  }
  if (adminRequired && (await userStore.ensureGlobalRole()) !== 'ADMIN') return '/404'
  return true
})

export default router
