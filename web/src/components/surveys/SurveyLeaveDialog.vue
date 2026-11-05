<template>
  <v-dialog :model-value="modelValue" max-width="560" @update:model-value="!$event && $emit('resolve', false)">
    <v-card title="Fragebogeneditor verlassen?">
      <v-card-text>
        <v-alert v-if="dirty" type="warning" variant="tonal" class="mb-3">Ungespeicherte Änderungen gehen beim Verlassen verloren.</v-alert>
        <p v-if="unpublished">Dein letzter Checkpoint ist gespeichert, aber noch nicht veröffentlicht. {{ activeVersion ? `Teilnehmende erhalten weiterhin Release ${activeVersion}.` : 'Der Fragebogen ist noch nicht für Teilnehmende verfügbar.' }}</p>
        <p class="text-body-2 mt-3">Zum Veröffentlichen bleibe im Editor und wähle „Release“.</p>
      </v-card-text>
      <v-card-actions><v-btn @click="$emit('resolve', false)">Im Editor bleiben</v-btn><v-spacer /><v-btn color="primary" @click="$emit('resolve', true)">Editor verlassen</v-btn></v-card-actions>
    </v-card>
  </v-dialog>
</template>
<script setup lang="ts">
defineProps<{ modelValue: boolean; dirty: boolean; unpublished: boolean; activeVersion: number | null }>()
defineEmits<{ resolve: [leave: boolean] }>()
</script>
