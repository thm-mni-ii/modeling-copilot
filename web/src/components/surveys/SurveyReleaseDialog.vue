<template>
  <v-dialog :model-value="modelValue" max-width="600" :persistent="busy" @update:model-value="$emit('update:modelValue', $event)">
    <v-card title="Release veröffentlichen und aktivieren?">
      <v-card-text>
        <p>{{ targetLabel }} wird für alle neu gestarteten Beantwortungen verwendet. {{ activeVersion ? `Der bisher aktive Release ${activeVersion} wird dadurch ersetzt.` : 'Damit wird der Fragebogen erstmals veröffentlicht.' }}</p>
        <v-alert v-if="saveFirst" type="info" variant="tonal" class="mt-4">Der aktuelle Stand wird zuerst als Checkpoint gespeichert und anschließend veröffentlicht.</v-alert>
        <p class="text-body-2 mt-4">Bereits gestartete und abgeschlossene Beantwortungen behalten ihre ursprüngliche Version.</p>
        <v-alert type="warning" variant="tonal" class="mt-4">Ein Release kann nicht wieder zum Checkpoint werden. Zum Rückgängigmachen kannst du einen früheren Release aktivieren. Beim Aktivieren einer historischen Version bleibt der aktuelle Entwurf erhalten.</v-alert>
        <v-alert v-if="error" type="error" class="mt-4">{{ error }}</v-alert>
      </v-card-text>
      <v-card-actions
        ><v-btn :disabled="busy" @click="$emit('update:modelValue', false)">Abbrechen</v-btn><v-spacer /><v-btn color="primary" :loading="busy" @click="$emit('confirm')">{{ saveFirst ? 'Speichern & veröffentlichen' : 'Release aktivieren' }}</v-btn></v-card-actions
      >
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
defineProps<{ modelValue: boolean; targetLabel: string; activeVersion: number | null; saveFirst: boolean; busy: boolean; error: string }>()
defineEmits<{ 'update:modelValue': [value: boolean]; confirm: [] }>()
</script>
