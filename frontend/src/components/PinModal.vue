<template>
  <div class="modal-overlay" @click.self="$emit('cancel')">
    <div class="modal">
      <h3>{{ title }}</h3>
      <p v-if="message" class="modal-msg">{{ message }}</p>
      <input
        ref="pinInput"
        v-model="pin"
        type="password"
        inputmode="numeric"
        maxlength="8"
        placeholder="Zadej PIN..."
        @keyup.enter="confirm"
      />
      <p v-if="error" class="error">{{ error }}</p>
      <div class="modal-actions">
        <button class="btn btn-secondary" @click="$emit('cancel')">Zrusit</button>
        <button class="btn btn-primary" @click="confirm" :disabled="!pin">Potvrdit</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  title: { type: String, default: 'Zadani PIN' },
  message: { type: String, default: '' }
})
const emit = defineEmits(['confirm', 'cancel'])

const pin = ref('')
const error = ref('')
const pinInput = ref(null)

onMounted(() => pinInput.value?.focus())

function confirm() {
  if (!pin.value) return
  error.value = ''
  emit('confirm', pin.value)
}

defineExpose({ setError: (msg) => { error.value = msg } })
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 100;
}
.modal {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  width: 320px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2);
}
.modal h3 { margin-bottom: 0.75rem; color: #1a1a2e; }
.modal-msg { margin-bottom: 1rem; color: #555; font-size: 0.9rem; }
input {
  width: 100%;
  padding: 0.6rem 1rem;
  font-size: 1.2rem;
  letter-spacing: 0.3em;
  border: 2px solid #ddd;
  border-radius: 8px;
  margin-bottom: 0.5rem;
  text-align: center;
}
input:focus { outline: none; border-color: #e94560; }
.error { color: #dc3545; font-size: 0.85rem; margin-bottom: 0.5rem; }
.modal-actions {
  display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 1rem;
}
</style>
