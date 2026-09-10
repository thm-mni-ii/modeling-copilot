<template>
  <v-card>
    <v-card-title class="d-flex align-center justify-space-between py-2">
      <span class="text-h6">{{ title }}</span>
      <v-btn v-if="showAddButton" color="primary" variant="tonal" size="small" prepend-icon="mdi-plus" @click="$emit('add')">
        {{ addButtonText }}
      </v-btn>
    </v-card-title>

    <v-divider />

    <v-list density="compact">
      <v-list-item v-for="(item, index) in items" :key="index" :active="selectedIndex === index" class="cursor-pointer" @click="$emit('select', index)">
        <template v-if="showPrependIcon" #prepend>
          <v-icon :color="getItemColor(item)" size="small">
            {{ getItemIcon(item) }}
          </v-icon>
        </template>

        <v-list-item-title>{{ getItemTitle(item) }}</v-list-item-title>
        <v-list-item-subtitle>{{ getItemSubtitle(item) }}</v-list-item-subtitle>

        <template #append>
          <v-btn v-if="showDeleteButton" icon="mdi-delete" variant="text" size="small" color="error" @click.stop="$emit('delete', index)" />
        </template>
      </v-list-item>
    </v-list>

    <v-card-text v-if="items.length === 0" class="text-center text-medium-emphasis">
      {{ emptyText }}
    </v-card-text>
  </v-card>
</template>

<script setup lang="ts">
interface EntityItem {
  type: string
  [key: string]: any
}

interface Props {
  title: string
  addButtonText: string
  items: EntityItem[]
  selectedIndex?: number
  emptyText: string
  titleField?: string
  subtitleField?: string
  iconField?: string
  colorField?: string
  iconMap?: Record<string, string>
  colorMap?: Record<string, string>
  showAddButton?: boolean
  showDeleteButton?: boolean
  showPrependIcon?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  selectedIndex: -1,
  titleField: 'label',
  subtitleField: 'type',
  iconField: 'type',
  colorField: 'type',
  iconMap: () => ({}),
  colorMap: () => ({}),
  showAddButton: true,
  showDeleteButton: true,
  showPrependIcon: true
})

defineEmits<{
  add: []
  select: [type: number]
  delete: [type: number]
}>()

const getItemTitle = (item: EntityItem) => {
  return item[props.titleField]
}

const getItemSubtitle = (item: EntityItem) => {
  return item[props.subtitleField] ?? ''
}

const getItemIcon = (item: EntityItem) => {
  const iconValue = item[props.iconField]
  if (typeof iconValue === 'string' && iconValue.length > 0) {
    if (props.iconMap[iconValue]) {
      return props.iconMap[iconValue]
    }
    if (iconValue.startsWith('mdi-')) {
      return iconValue
    }
  }
  return 'mdi-circle-outline'
}

const getItemColor = (item: EntityItem) => {
  const colorValue = item[props.colorField]
  if (typeof colorValue === 'string' && colorValue.length > 0) {
    if (props.colorMap[colorValue]) {
      return props.colorMap[colorValue]
    }
    return colorValue
  }

  return 'grey'
}
</script>
