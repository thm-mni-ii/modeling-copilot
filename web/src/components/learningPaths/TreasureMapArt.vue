<template>
  <svg viewBox="0 0 120 120" fill="none" aria-hidden="true" focusable="false">
    <g v-if="kind === 'chest'" stroke="#643d27" stroke-width="3" stroke-linejoin="round">
      <ellipse cx="60" cy="103" rx="43" ry="7" fill="#3d5140" opacity=".13" stroke="none" />
      <g :class="{ 'chest-lid--open': opened }" class="chest-lid">
        <path d="M20 63V47C20 18 100 18 100 47V63Z" fill="#b66b39" />
        <path d="M27 43Q60 27 93 43M21 52H99" stroke="#824924" />
        <path d="M33 32V63M87 32V63" stroke="#f5cf70" stroke-width="9" />
      </g>
      <path d="M20 60H100V95Q100 101 94 101H26Q20 101 20 95Z" fill="#a55b32" />
      <path d="M21 79H99M23 93H97" stroke="#7e4328" />
      <path d="M20 62H100" stroke="#f5cf70" stroke-width="7" />
      <path d="M33 65V99M87 65V99" stroke="#f5cf70" stroke-width="9" />
      <rect x="50" y="59" width="20" height="21" rx="4" fill="#ffdb79" />
      <path d="M60 67V73" stroke-width="4" />
      <g v-if="opened" stroke="#b98423" stroke-width="2">
        <circle cx="44" cy="46" r="10" fill="#ffdc75" />
        <circle cx="61" cy="39" r="11" fill="#ffe8a3" />
        <circle cx="78" cy="47" r="10" fill="#f9c957" />
        <path d="M44 41V51M61 33V45M78 42V52" />
        <path d="M22 20V30M17 25H27M97 14V24M92 19H102" stroke="#e6b746" />
      </g>
    </g>
    <g v-else-if="kind === 'pirate'" stroke="#403c35" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
      <ellipse cx="60" cy="111" rx="26" ry="5" fill="#315650" opacity=".15" stroke="none" />
      <path d="M48 87L46 105H57L61 89M66 88L69 105H80L75 85" fill="#414c5f" />
      <path d="M43 67Q60 57 78 67L82 88H40Z" fill="#b9423c" />
      <path d="M54 65L60 80L67 65" fill="#fff4d8" />
      <path d="M41 84H80" stroke="#65442e" stroke-width="5" />
      <path d="M43 71L33 84M77 71L87 81" stroke="#e6ac7a" stroke-width="9" />
      <circle cx="60" cy="46" r="23" fill="#efbd8d" />
      <path d="M40 43L83 35" stroke="#403c35" stroke-width="3" />
      <circle cx="51" cy="45" r="6" fill="#343b3f" />
      <circle cx="71" cy="44" r="2" fill="#343b3f" stroke="none" />
      <path d="M58 56Q64 61 70 55" />
      <path d="M29 33L37 13L49 18L60 6L73 18L85 13L94 33Q61 25 29 33Z" fill="#35464b" />
      <path d="M30 33Q60 42 94 33" stroke="#e9c46b" stroke-width="5" />
      <circle cx="61" cy="22" r="5" fill="#fff4d8" stroke="none" />
      <path d="M56 29L67 29" stroke="#fff4d8" stroke-width="2" />
      <path d="M82 50L86 60L80 63" stroke="#e9c46b" />
    </g>
    <g v-else-if="kind === 'palm'" stroke-linecap="round" stroke-linejoin="round">
      <path d="M65 106Q77 70 55 35" stroke="#a77945" stroke-width="10" />
      <path d="M61 86L70 89M62 69L69 71M58 52L64 54" stroke="#795834" stroke-width="3" />
      <path d="M56 36Q19 7 7 51Q34 35 56 36Z" fill="#36816a" />
      <path d="M55 35Q36 0 76 7Q64 16 55 35Z" fill="#469777" />
      <path d="M57 36Q95 3 113 46Q81 30 57 36Z" fill="#287560" />
      <path d="M56 36Q97 32 96 75Q77 46 56 36Z" fill="#469777" />
      <path d="M54 36Q28 31 23 74Q43 48 54 36Z" fill="#236d59" />
      <circle cx="55" cy="39" r="6" fill="#86603e" />
      <circle cx="66" cy="43" r="5" fill="#a77945" />
    </g>
    <g v-else-if="kind === 'mountain'" stroke="#6c7c7b" stroke-width="2" stroke-linejoin="round">
      <path d="M5 103L40 29L77 103Z" fill="#9caca3" />
      <path d="M35 103L78 10L117 103Z" fill="#758e87" />
      <path d="M78 10L62 45L75 39L83 49L92 41Z" fill="#f5f4e7" stroke="none" />
      <path d="M40 29L28 54L40 49L49 57L53 55Z" fill="#e7ece0" stroke="none" />
      <path d="M78 49L68 103H117L91 48L84 57Z" fill="#5b7872" stroke="none" opacity=".5" />
    </g>
    <g v-else-if="kind === 'rocks'" stroke="#7e8b7c" stroke-width="2" stroke-linejoin="round">
      <path d="M15 98L9 73L30 49L57 61L65 98Z" fill="#b9bca0" />
      <path d="M49 102L54 54L83 35L110 69L112 102Z" fill="#9ba88f" />
      <path d="M54 54L76 72L83 35M76 72L112 102" />
      <path d="M9 73L32 79L30 49M32 79L65 98" />
      <path d="M2 106H118" stroke="#78937a" stroke-width="5" />
    </g>
    <g v-else-if="kind === 'coin'">
      <circle cx="60" cy="60" r="44" fill="#e5aa37" />
      <circle cx="60" cy="56" r="40" fill="#ffdb78" stroke="#ae7d24" stroke-width="3" />
      <circle cx="60" cy="56" r="29" stroke="#edb94e" stroke-width="3" />
      <path d="M60 38L65 49L77 51L68 60L70 73L60 67L50 73L52 60L43 51L55 49Z" fill="#bc8424" />
    </g>
  </svg>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ kind: 'chest' | 'pirate' | 'palm' | 'mountain' | 'rocks' | 'coin'; opened?: boolean }>(), { opened: false })
</script>

<style scoped>
.chest-lid {
  transform-origin: 60px 60px;
  transition: transform 0.4s ease;
}
.chest-lid--open {
  transform: translateY(-14px) rotate(-8deg);
}
@media (prefers-reduced-motion: reduce) {
  .chest-lid {
    transition: none;
  }
}
</style>
