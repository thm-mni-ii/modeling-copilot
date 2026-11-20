import { ref } from 'vue'
import type { PlatformPeriod } from '@/services/analytics'

// Module-level state: the platform tabs share one filter set and keep it while switching.
const period = ref<PlatformPeriod>('30d')
const includeStaff = ref(false)

export const usePlatformFilters = () => ({ period, includeStaff })
