<template>
  <section v-for="group in groups" :key="group.title" class="mb-8">
    <h2 class="text-h6 mb-3">{{ group.title }}</h2>
    <p v-if="!group.items.length" class="text-medium-emphasis">{{ group.empty }}</p>
    <v-card v-for="course in group.items" :key="course.id" variant="outlined" class="mb-3">
      <v-card-title
        ><router-link :to="courseLink(course.id)" class="text-decoration-none">{{ course.name }}</router-link></v-card-title
      >
      <v-card-text>
        <p v-if="course.description" class="mb-3">{{ course.description }}</p>
        <p v-if="course.deadline" class="text-body-2">Submission deadline: {{ date(course.deadline) }}</p>
        <v-chip v-if="course.enrolled" size="small" class="mt-2" :color="course.submissionStatus === 'feedback_available' ? 'success' : undefined">{{ submissionStatus(course.submissionStatus ?? 'not_submitted') }}</v-chip>
        <p v-else-if="course.activeRunId && !course.canEnroll" class="text-body-2 text-medium-emphasis mt-2">Enrollment is closed.</p>
      </v-card-text>
      <v-card-actions>
        <v-btn v-if="course.canEnroll" :loading="busy" color="primary" variant="flat" @click="emit('enroll', course)">Join course</v-btn>
        <v-btn v-else :to="courseLink(course.id)" :variant="course.enrolled ? 'flat' : 'text'" :color="course.enrolled ? 'primary' : undefined">{{ course.enrolled ? 'Go to submission' : 'View course' }}</v-btn>
      </v-card-actions>
    </v-card>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { submissionStatus, type SubmissionCourse } from '@/services/api/types/submission'
const props = defineProps<{ courses: SubmissionCourse[]; busy: boolean }>()
const emit = defineEmits<{ enroll: [course: SubmissionCourse] }>()
const date = (value: string) => new Date(value).toLocaleString()
const courseLink = (id: string) => ({ name: 'Submissions', params: { assignmentId: id }, query: { view: 'participant' } })
const groups = computed(() => [
  { title: 'My courses', items: props.courses.filter((c) => c.enrolled), empty: 'You are not enrolled in a course yet.' },
  { title: 'Available courses', items: props.courses.filter((c) => !c.enrolled && c.activeRunId), empty: 'No other courses are currently available.' },
  ...(props.courses.some((c) => !c.activeRunId) ? [{ title: 'Previous courses', items: props.courses.filter((c) => !c.activeRunId), empty: '' }] : [])
])
</script>
