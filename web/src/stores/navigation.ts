import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useUserStore } from '@/stores/userStore'
import { useBearerToken } from '@/composables/useBearerToken'
import { mayManageAll } from '@/collab/rooms/access'

interface NavigationItem {
  title: string
  description: string
  icon: string
  route: string
}

const workspaceItems: NavigationItem[] = [
  { title: 'My Models', description: 'Create models, continue your work, and manage saved versions.', icon: 'mdi-folder-outline', route: 'Models' },
  { title: 'Learning paths', description: 'Explore learning paths and continue your activities.', icon: 'mdi-map-marker-path', route: 'LearningPathRuns' }
]

const administrationItems: NavigationItem[] = [
  { title: 'Diagram languages', description: 'Create, edit, and publish diagram languages.', icon: 'mdi-shape-outline', route: 'DiagramLanguages' },
  { title: 'Tasks', description: 'Create and manage modeling tasks and their releases.', icon: 'mdi-clipboard-text-outline', route: 'Tasks' },
  { title: 'Path templates', description: 'Build and publish learning paths with tasks and surveys.', icon: 'mdi-map-plus', route: 'LearningPathTemplates' },
  { title: 'Surveys', description: 'Create, edit, and publish questionnaires.', icon: 'mdi-form-select', route: 'Surveys' },
  { title: 'Collaboration', description: 'Manage collaboration rooms, groups, and shared models.', icon: 'mdi-account-group-outline', route: 'Collab' }
]

// Both the home tiles and the navigation menu use the same visibility rules.
export const useNavigationStore = defineStore('navigation', () => {
  const userStore = useUserStore()
  const { bearerToken } = useBearerToken()
  const isAdmin = computed(() => userStore.globalRole === 'ADMIN')
  const canManageCollaboration = ref(false)

  watch(
    [bearerToken, isAdmin],
    async ([token, admin], _previous, onCleanup) => {
      let cancelled = false
      onCleanup(() => {
        cancelled = true
      })
      canManageCollaboration.value = false
      if (!token || !admin) return
      const allowed = await mayManageAll()
      if (!cancelled) canManageCollaboration.value = allowed
    },
    { immediate: true }
  )

  const adminItems = computed(() => (isAdmin.value ? administrationItems.filter((item) => item.route !== 'Collab' || canManageCollaboration.value) : []))

  return { workspaceItems, adminItems, isAdmin }
})
