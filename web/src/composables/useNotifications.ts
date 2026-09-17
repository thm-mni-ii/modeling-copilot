import { readonly, ref, shallowRef } from 'vue'

export type NotificationTone = 'error' | 'warning' | 'success'

export interface NotificationAction {
  label: string
  handler: () => void | Promise<void>
}

interface NotificationOptions {
  action?: NotificationAction
  timeout?: number
}

export interface AppNotification {
  id: number
  message: string
  tone: NotificationTone
  action?: NotificationAction
  timeout: number
}

const DEFAULT_TIMEOUTS: Record<NotificationTone, number> = {
  error: 8000,
  warning: 6000,
  success: 4500
}

const current = shallowRef<AppNotification | null>(null)
const visible = ref(false)
const queue: AppNotification[] = []
let nextId = 0
let transitionTimer: ReturnType<typeof setTimeout> | undefined

const activate = (notification: AppNotification) => {
  current.value = notification
  visible.value = true
}

const showNotification = (message: string, tone: NotificationTone, options: NotificationOptions = {}) => {
  const normalizedMessage = message.trim()
  if (!normalizedMessage) return

  const notification: AppNotification = {
    id: ++nextId,
    message: normalizedMessage,
    tone,
    action: options.action,
    timeout: options.timeout ?? DEFAULT_TIMEOUTS[tone]
  }

  if (current.value?.message === notification.message && current.value.tone === notification.tone) return
  if (queue.some((entry) => entry.message === notification.message && entry.tone === notification.tone)) return

  if (!current.value) activate(notification)
  else queue.push(notification)
}

const dismissNotification = () => {
  if (!current.value || !visible.value) return
  visible.value = false
  if (transitionTimer) clearTimeout(transitionTimer)
  transitionTimer = setTimeout(() => {
    current.value = null
    const next = queue.shift()
    if (next) activate(next)
  }, 200)
}

export const notifyError = (message: string, options?: NotificationOptions) => showNotification(message, 'error', options)
export const notifyWarning = (message: string, options?: NotificationOptions) => showNotification(message, 'warning', options)
export const notifySuccess = (message: string, options?: NotificationOptions) => showNotification(message, 'success', options)

export const useNotifications = () => ({
  current: readonly(current),
  visible: readonly(visible),
  dismissNotification
})
