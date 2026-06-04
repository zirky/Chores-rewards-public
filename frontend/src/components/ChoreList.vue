<template>
  <ul class="chore-list">
    <li v-for="task in tasks" :key="task.id" class="chore-item">
      <div class="chore-info">
        <span class="chore-name">{{ task.title || task.name }}</span>
        <span class="chore-reward">⚡ {{ task.reward_czk }} CZK</span>
      </div>
      <button
        class="btn btn-primary"
        :disabled="submitted.has(task.id) || loading === task.id"
        @click="submit(task.id)"
      >
        <span v-if="loading === task.id">Odesílám…</span>
        <span v-else-if="submitted.has(task.id)">Odesláno ✓</span>
        <span v-else>Hotovo!</span>
      </button>
    </li>
  </ul>
</template>

<script setup>
import { ref } from 'vue'
import { submitCompletion } from '../api.js'

const props = defineProps({
  tasks:   { type: Array,  default: () => [] },
  childId: { type: Number, required: true }
})
const emit = defineEmits(['submitted'])

const submitted = ref(new Set())
const loading   = ref(null)   // task.id právě odesílaného úkolu

async function submit(taskId) {
  if (loading.value || submitted.value.has(taskId)) return
  loading.value = taskId
  try {
    await submitCompletion(props.childId, taskId)
    submitted.value = new Set([...submitted.value, taskId])
    emit('submitted')
  } catch (e) {
    alert('Chyba při odesílání: ' + e.message)
  } finally {
    loading.value = null
  }
}
</script>

<style scoped>
.chore-list { list-style: none; }
.chore-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.85rem 0;
  border-bottom: 1px solid #eee;
}
.chore-item:last-child { border-bottom: none; }
.chore-info { display: flex; flex-direction: column; gap: 0.2rem; }
.chore-name   { font-weight: 600; font-size: 1rem; }
.chore-reward { color: #e94560; font-size: 0.85rem; }
.btn {
  padding: 0.45rem 1.1rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 600;
  transition: opacity 0.2s;
  min-width: 96px;
}
.btn:hover:not(:disabled) { opacity: 0.85; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: #e94560; color: white; }
</style>
