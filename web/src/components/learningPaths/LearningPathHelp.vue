<template>
  <section class="learning-path-help" aria-label="Hilfe beim Modellieren">
    <button type="button" class="help-sign" :disabled="disabled || busy" :aria-busy="busy" @click="emit('request')">
      <svg class="help-sign-art" viewBox="0 0 220 70" fill="none" aria-hidden="true" focusable="false">
        <!-- Short rope loops and a brass-edged wooden sign. -->
        <path d="M38 2v12M182 2v12" stroke="#62472e" stroke-width="5" stroke-linecap="round" />
        <path d="M38 2v12M182 2v12" stroke="#c7a772" stroke-width="2" stroke-dasharray="2 3" />
        <path d="M21 11h178l12 9v32l-12 10H21L9 52V20z" fill="#493023" stroke="#493023" stroke-width="2" />
        <path d="M21 11h178l12 9v32l-12 10H21L9 52V20z" fill="#b28a4d" />
        <path d="m22 15 176 0 9 7v28l-10 8H23l-10-8V22z" fill="#765035" stroke="#e2bd76" stroke-opacity=".55" />
        <path d="M26 20h168l7 5v22l-8 7H27l-8-7V25z" fill="#543a2a" stroke="#4a3022" stroke-width="2" />
        <path d="M22 36h176M30 25h32m96 0h29M28 47h20m117 1h24" stroke="#aa7b47" stroke-opacity=".24" stroke-linecap="round" />
        <path d="m14 51 10 7h173l10-8" stroke="#563a27" stroke-width="2" />
        <g fill="#d2bb8b" stroke="#6b5036" stroke-width="1.5">
          <circle cx="23" cy="24" r="2.5" /><circle cx="197" cy="24" r="2.5" />
          <circle cx="23" cy="48" r="2.5" /><circle cx="197" cy="48" r="2.5" />
        </g>
      </svg>
      <span class="help-sign-label">
        <v-progress-circular v-if="busy" indeterminate size="13" width="2" aria-hidden="true" />
        <span>Ich brauche Hilfe</span>
      </span>
    </button>
    <p v-if="busy" class="help-status" role="status">Dein Modellstand wird gespeichert …</p>
  </section>
</template>

<script setup lang="ts">
defineProps<{ busy: boolean; disabled: boolean }>()
const emit = defineEmits<{ request: [] }>()
</script>

<style scoped>
.learning-path-help {
  width: 200px;
  max-width: 100%;
}
.help-sign {
  position: relative;
  display: block;
  width: 100%;
  aspect-ratio: 22 / 7;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  filter: drop-shadow(0 2px 2px rgb(50 33 20 / 18%));
  transition: filter 150ms ease, transform 150ms ease;
}
.help-sign-art { display: block; width: 100%; height: 100%; }
.help-sign-label {
  position: absolute;
  inset: 20% 10% 13%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  color: #ffe0a0;
  font-family: Georgia, 'Times New Roman', serif;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  text-shadow: 0 1px 1px #281b14;
}
.help-sign:hover:not(:disabled) {
  filter: brightness(1.08) drop-shadow(0 3px 3px rgb(50 33 20 / 22%));
  transform: translateY(-1px);
}
.help-sign:active:not(:disabled) { transform: translateY(1px); }
.help-sign:focus-visible { outline: 2px solid #926b32; outline-offset: 3px; }
.help-sign:disabled { cursor: default; opacity: 0.65; }
.help-sign[aria-busy='true'] { cursor: progress; }
.help-status {
  margin: 4px 0 0;
  padding: 7px 9px;
  border: 1px solid #dbc9a5;
  border-radius: 6px;
  background: #fff8e9;
  color: #604b30;
  font-size: 11px;
  line-height: 1.45;
}
@media (prefers-reduced-motion: reduce) {
  .help-sign { transition: none; }
}
</style>
