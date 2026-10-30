<template>
  <div>
    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <v-switch v-model="localStyle.bendable" color="primary" density="compact" class="mb-3" label="Adjustable Control Points" hint="Allows control points to be moved manually." persistent-hint @update:model-value="emit('update')" />
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <v-switch v-model="connectableValue" color="primary" density="compact" class="mb-3" label="Connectable Line" hint="Allows this line to connect to other lines." persistent-hint @update:model-value="emit('update')" />
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <v-switch v-model="allowLooseEndsValue" color="primary" density="compact" class="mb-3" label="Allow Loose Ends" hint="Allows an end of this line to stay unconnected." persistent-hint @update:model-value="emit('update')" />
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <v-switch v-model="localStyle.pointerEvents" color="primary" density="compact" class="mb-3" label="Pointer Events Enabled" hint="Controls whether the Connection receives mouse events." persistent-hint @update:model-value="emit('update')" />
    </FieldWithIndicator>

    <FieldWithIndicator :config="{ minComplexity: 'dev' }">
      <v-slider v-model.number="localStyle.opacity" :min="0" :max="100" :step="1" label="Overall Opacity" class="mb-3" hint="Overall Connection opacity (0–100%)." persistent-hint thumb-label @update:model-value="emit('update')">
        <template #append>
          <span class="text-caption">{{ localStyle.opacity ?? 100 }}%</span>
        </template>
      </v-slider>
    </FieldWithIndicator>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DiagramConnection } from '@/model/DiagramLanguage'
import type { VisibilityContext } from '../config/fieldVisibility'
import FieldWithIndicator from './FieldWithIndicator.vue'

interface Props {
  connection: DiagramConnection
  visibilityContext: VisibilityContext
}

const props = defineProps<Props>()
const emit = defineEmits<{ update: [] }>()

const localStyle = computed(() => props.connection.style as Record<string, any>)

const connectableValue = computed({
  get: () => props.connection.connectable ?? true,
  set: (value: boolean) => {
    // eslint-disable-next-line vue/no-mutating-props
    props.connection.connectable = value
  }
})

const allowLooseEndsValue = computed({
  get: () => props.connection.allowLooseEnds ?? true,
  set: (value: boolean) => {
    // eslint-disable-next-line vue/no-mutating-props
    props.connection.allowLooseEnds = value
  }
})
</script>
