import { createRouter, createWebHashHistory } from 'vue-router'
import { useBearerToken } from '@/composables/useBearerToken'
import authService from '@/services/auth/auth.service'
import { isEmbedded, requestFbsToken, startFbsBridge } from '@/services/auth/fbsBridge'
import { useUserStore } from '@/stores/userStore'

const router = createRouter({
  history: createWebHashHistory(),
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
      path: '/tasks',
      name: 'Tasks',
      component: () => import('../views/ViewTaskEditor.vue')
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

const nonAdminPages = ['Login', 'Home', 'Modeling', 'View404Page']

router.beforeEach(async (to, from, next) => {
  // Embedded in the Feedbacksystem, the token comes from the host.
  if (isEmbedded) await startFbsBridge()
  const publicPages = ['/login']
  const authRequired = !publicPages.includes(to.path)
  const { bearerToken, clearToken } = useBearerToken()
  const loggedIn = bearerToken.value

  const adminRequired = !nonAdminPages.includes(to.name as string)
  const userStore = useUserStore()

  const loginValid = await authService.validateToken().then(async (response) => {
    // An expired token of the host is renewed once before logging out.
    if (response.data !== true && isEmbedded && loggedIn && (await requestFbsToken())) response = await authService.validateToken()
    if (response.data === true) {
      return true
    } else {
      clearToken()
      userStore.reset()
      return false
    }
  })

  // trying to access a restricted page + not logged in
  // redirect to login page
  if ((authRequired && !loggedIn) || (authRequired && !loginValid)) {
    next('/login')
  } else if (adminRequired && (await userStore.ensureGlobalRole()) !== 'ADMIN') {
    next('/404')
  } else {
    next()
  }
})

export default router
