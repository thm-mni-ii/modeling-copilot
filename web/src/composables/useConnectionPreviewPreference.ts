import { ref, watch } from 'vue'

const STORAGE_KEY = 'modeling-copilot.connection-preview.enabled'
const readPreference = () => {
  try { return localStorage.getItem(STORAGE_KEY) !== 'false' }
  catch { return true }
}
const enabled = ref(readPreference())
watch(enabled, (value) => {
  try { localStorage.setItem(STORAGE_KEY, String(value)) }
  catch { /* Keep the session preference when storage is unavailable. */ }
})

export const useConnectionPreviewPreference = () => enabled
