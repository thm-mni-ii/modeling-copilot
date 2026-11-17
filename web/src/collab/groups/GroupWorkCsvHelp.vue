<template>
  <!-- Example file and rules of the import; the rules match parseGroupWorkCsv in groupWorkCsv.ts. -->
  <v-expansion-panels variant="accordion" class="mb-4">
    <v-expansion-panel title="CSV format">
      <v-expansion-panel-text>
        <p class="mb-2">One row per person. Moodle's participant export works as it is.</p>
        <ul class="ml-4 mb-3">
          <li><b>Required columns:</b> "Anmeldename", "Gruppen", "Fallstudie". The header must use exactly these names.</li>
          <li><b>Optional:</b> "Vorname" and "Nachname" are shown in the preview. Other columns are ignored.</li>
          <li><b>Separator:</b> semicolon, comma or tab, detected from the header.</li>
          <li><b>Groups:</b> the same course and group name is one room. A person in several groups (comma in "Gruppen") is skipped.</li>
          <li><b>Case study:</b> "1", "F1" and "Fallstudie 1" all mean case study 1. A group works on the case studies of all its members. Several numbers go in one cell, like "2, 3"; in a comma-separated file the cell needs quotes.</li>
          <li><b>Skipped rows:</b> empty login name, no group, or the same login name twice. These rows are listed after loading.</li>
        </ul>
        <v-btn variant="tonal" size="small" prepend-icon="mdi-eye-outline" @click="showExample = true">Show example CSV</v-btn>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
  <!-- The same example file as a table, as Excel shows it, and as text; the required columns are bold. -->
  <v-dialog v-model="showExample" max-width="760">
    <v-card title="Example CSV">
      <v-card-text>
        <p class="text-caption text-medium-emphasis mb-1">As a table, required columns in bold:</p>
        <v-table density="compact" class="mb-4 border">
          <thead>
            <tr>
              <th v-for="title in EXAMPLE_ROWS[0]" :key="title" :class="{ 'font-weight-bold': EXAMPLE_REQUIRED.includes(title) }">{{ title }}</th>
            </tr>
          </thead>
          <tbody>
            <!-- A person in several groups (comma in Gruppen) is skipped and grayed out here. -->
            <tr v-for="(cells, index) in EXAMPLE_ROWS.slice(1)" :key="index" :class="{ 'example-csv--skipped': cells[4].includes(',') }">
              <td v-for="(cell, column) in cells" :key="column">{{ cell }}</td>
            </tr>
          </tbody>
        </v-table>
        <ul class="ml-4 mb-4 text-body-2">
          <li>Alice and Bob form GW 01 with case study 1: "1" and "F1" are the same.</li>
          <li>GW 02 gets case studies 2 and 3, because Erika lists both.</li>
          <li>Tom is in two groups, so his row is skipped.</li>
        </ul>
        <p class="text-caption text-medium-emphasis mb-1">As text in the file:</p>
        <pre class="example-csv pa-3 rounded border">{{ EXAMPLE_CSV }}</pre>
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn @click="showExample = false">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'

/** An example in the format of the Moodle participant list; semicolons, so a German Excel splits the columns. */
const EXAMPLE_CSV = ['Vorname;Nachname;Anmeldename;E-Mail-Adresse;Gruppen;Fallstudie', 'Alice;Beispiel;alice;alice@example.org;GW 01;1', 'Bob;Beispiel;bob;bob@example.org;GW 01;F1', 'Max;Mustermann;max;max@example.org;GW 02;Fallstudie 2', 'Erika;Musterfrau;erika;erika@example.org;GW 02;2, 3', 'Tom;Test;tom;tom@example.org;GW 01, GW 02;1'].join('\n')
// The table in the dialog comes from the same text, so both stay the same.
const EXAMPLE_ROWS = EXAMPLE_CSV.split('\n').map((line) => line.split(';'))
const EXAMPLE_REQUIRED = ['Anmeldename', 'Gruppen', 'Fallstudie']
const showExample = ref(false)
</script>

<style scoped>
/* The file content as in an editor, long lines scroll instead of wrapping. */
.example-csv {
  font-family: monospace;
  font-size: 13px;
  overflow-x: auto;
  background: rgba(var(--v-theme-on-surface), 0.04);
}

.example-csv--skipped {
  text-decoration: line-through;
  opacity: 0.5;
}
</style>
