<template>
  <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" focusable="false" :class="`pirate-pose--${pose}`">
    <g v-if="pose === 'dash'" stroke="#fff4c5" stroke-width="4" stroke-linecap="round">
      <path d="M3 48h23M0 62h20M6 76h18" />
    </g>
    <ellipse v-if="pose !== 'peek' && pose !== 'dash'" cx="60" cy="111" rx="27" ry="4" fill="#446354" opacity=".18" />
    <g class="pirate-body">
      <path d="m45 89-4 17h15l5-16m3 0 3 16h15l-7-19" fill="#26485b" />
      <path d="M40 104h17v7H36c0-4 1-6 4-7m27 0h15l5 7H67" fill="#173747" />
      <path d="M43 68q17-9 34 0l7 25H36z" fill="#df6854" />
      <path d="m51 65 9 13 9-13-2 25H53z" fill="#fff0d0" />
      <path d="M39 87h42v7H39z" fill="#754c3a" />
      <rect x="56" y="86" width="10" height="9" rx="2" fill="#ffd576" />
      <rect x="59" y="88" width="4" height="5" rx="1" fill="#754c3a" />
      <g :transform="leftArm">
        <path d="m44 71-13 10" stroke="#df6854" stroke-width="12" stroke-linecap="round" />
        <path d="m31 81-5 5" stroke="#f3bd8b" stroke-width="10" stroke-linecap="round" />
        <circle cx="24" cy="87" r="6" fill="#ffd3a0" />
      </g>
      <g :transform="rightArm">
        <path d="m76 71 12 10" stroke="#df6854" stroke-width="12" stroke-linecap="round" />
        <path d="m88 81 6 4" stroke="#f3bd8b" stroke-width="10" stroke-linecap="round" />
        <circle cx="96" cy="86" r="6" fill="#ffd3a0" />
        <g v-if="pose === 'invite' || pose === 'joy'">
          <circle cx="101" cy="83" r="9" fill="#e8a43b" />
          <circle cx="101" cy="82" r="7" fill="#ffdc77" />
          <path d="M101 78v8" stroke="#bf8130" stroke-width="2" stroke-linecap="round" />
        </g>
      </g>
      <g class="pirate-head" :transform="pose === 'listen' || pose === 'peek' ? 'rotate(-9 60 62)' : undefined">
        <path d="M34 39q0-18 26-18t26 18v19q-3 19-26 19T34 58z" fill="#613f38" />
        <circle cx="34" cy="53" r="7" fill="#f3bd8b" />
        <circle cx="86" cy="53" r="7" fill="#f3bd8b" />
        <path d="M37 38q23-10 46 0v18q-2 17-23 17T37 56z" fill="#ffd3a0" />
        <path d="m36 43 48-7" stroke="#294653" stroke-width="3" />
        <path d="M41 45q8-5 17-1v7q-8 10-16 0z" fill="#203c4b" />
        <path v-if="pose === 'joy'" d="m68 49 5-4 5 4" stroke="#294653" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
        <ellipse v-else cx="73" cy="48" rx="3" :ry="pose === 'farewell' ? 2 : 4" fill="#203c4b" />
        <path d="m68 39 9-1" stroke="#613f38" stroke-width="2.5" stroke-linecap="round" />
        <ellipse cx="77" cy="57" rx="5" ry="2.5" fill="#ed957e" opacity=".6" />
        <path v-if="pose === 'joy'" d="M55 58h16q-8 15-16 0" fill="#7b4140" />
        <ellipse v-else-if="pose === 'peek'" cx="63" cy="61" rx="3" ry="4" fill="#7b4140" />
        <path v-else d="M57 60q6 5 12-1" stroke="#8f5044" stroke-width="2.5" stroke-linecap="round" />
        <path d="M87 55a5 5 0 1 1-3 9" stroke="#ffd576" stroke-width="3" />
        <path d="M28 34 35 14l13 4L60 7l13 11 13-4 8 20q-33 14-66 0" fill="#234d60" />
        <path d="m35 16 4 15q21 7 43 0l4-15-13 4L60 10 48 20z" fill="#32667a" />
        <path d="M29 34q31 12 64 0" stroke="#ffd576" stroke-width="4" stroke-linecap="round" />
        <path d="m60 18 3 5 5 1-4 4 1 5-5-2-5 2 1-5-4-4 5-1z" fill="#fff1cb" />
      </g>
      <path d="m52 70 8 7 8-7-8-3z" fill="#f28b68" />
      <path d="m61 76 9 2 6 10-12-5z" fill="#f28b68" />
    </g>
    <g v-if="pose === 'joy'" stroke="#ffd576" stroke-width="2.5" stroke-linecap="round">
      <path d="M16 34v10m-5-5h10m79-18v8m-4-4h8" />
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'
const props = withDefaults(defineProps<{ pose?: 'peek' | 'dash' | 'invite' | 'listen' | 'joy' | 'farewell' }>(), { pose: 'invite' })
const leftArm = computed(() => props.pose === 'peek' || props.pose === 'joy' ? 'rotate(125 44 71)' : props.pose === 'dash' ? 'rotate(-45 44 71)' : undefined)
const rightArm = computed(() => props.pose === 'peek' || props.pose === 'joy' ? 'rotate(-125 76 71)' : props.pose === 'invite' || props.pose === 'farewell' ? 'rotate(-90 76 71)' : undefined)
</script>
