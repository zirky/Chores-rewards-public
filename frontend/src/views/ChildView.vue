<template>
  <div>
    <!-- Hlavička s jménem dítěte -->
    <div class="card child-header">
      <h2>👋 Ahoj, {{ childName }}!</h2>
      <p class="subtitle">Splň úkoly a vydělávej saty ⚡</p>
    </div>

    <!-- Moje úkoly -->
    <div class="card">
      <h2>📝 Moje úkoly</h2>
      <div v-if="loading" class="skeleton-list">
        <div v-for="i in 3" :key="i" class="skeleton-row"></div>
      </div>
      <div v-else-if="tasks.length === 0" class="empty-state">
        <span class="empty-icon">📭</span>
        <p>Rodič zatím nepřidal žádné úkoly.</p>
      </div>
      <ChoreList
        v-else
        :tasks="tasks"
        :childId="childId"
        @submitted="loadHistory"
      />
    </div>

    <!-- Statistiky -->
    <div class="card stats">
      <h2>⚡ Mé saty</h2>
      <div class="stat-row">
        <div class="stat">
          <span class="stat-value">{{ pendingCount }}</span>
          <span class="stat-label">Čeká na schválení</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ approvedSats }}</span>
          <span class="stat-label">Sats ke proplacení</span>
        </div>
        <div class="stat">
          <span class="stat-value">{{ approvedCzk }} Kč</span>
          <span class="stat-label">Schváleno (nevyplaceno)</span>
        </div>
        <div class="stat">
          <span class="stat-value settled">{{ settledSats }}</span>
          <span class="stat-label">Celkem vyplaceno (sats)</span>
        </div>
      </div>
    </div>

    <!-- Historie -->
    <div class="card">
      <h2>📊 Můj postup</h2>
      <div v-if="historyLoading" class="muted">Načítám…</div>
      <div v-else-if="history.length === 0" class="empty-state">
        <span class="empty-icon">🗒️</span>
        <p>Zatím žádné záznamy. Splň první úkol!</p>
      </div>
      <div v-else class="table-scroll">
        <table class="table">
          <thead>
            <tr><th>Úkol</th><th>Stav</th><th>Odměna</th><th>Datum</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in history" :key="c.id">
              <td>{{ c.task_title }}</td>
              <td><span :class="'badge badge-' + c.status">{{ statusLabel(c.status) }}</span></td>
              <td>{{ c.reward_czk ? c.reward_czk + ' Kč' : '–' }}</td>
              <td>{{ fmt(c.submitted_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ChoreList from '../components/ChoreList.vue'
import { getTasks, getHistory } from '../api.js'

const props = defineProps({
  childId:   { type: Number, required: true },
  childName: { type: String, default: 'tebe' }
})

const tasks          = ref([])
const history        = ref([])
const loading        = ref(true)
const historyLoading = ref(false)

onMounted(async () => {
  await Promise.all([loadTasks(), loadHistory()])
  loading.value = false
})

async function loadTasks() {
  try { tasks.value = await getTasks() } catch {}
}

async function loadHistory() {
  historyLoading.value = true
  try { history.value = await getHistory(props.childId) } catch {}
  finally { historyLoading.value = false }
}

function fmt(dt) {
  return dt ? new Date(dt).toLocaleDateString('cs-CZ') : '–'
}

function statusLabel(s) {
  return {
    submitted: 'Čeká',
    approved:  'Schváleno',
    rejected:  'Zamítnuto',
    settled:   'Vyplaceno'
  }[s] || s
}

const pendingCount = computed(() =>
  history.value.filter(c => c.status === 'submitted').length
)
const approvedSats = computed(() =>
  history.value.filter(c => c.status === 'approved').reduce((s, c) => s + (c.reward_sats || 0), 0)
)
const approvedCzk = computed(() =>
  history.value.filter(c => c.status === 'approved').reduce((s, c) => s + (c.reward_czk || 0), 0).toFixed(2)
)
const settledSats = computed(() =>
  history.value.filter(c => c.status === 'settled').reduce((s, c) => s + (c.reward_sats || 0), 0)
)
</script>

<style scoped>
.child-header h2   { font-size: 1.6rem; margin-bottom: 0.25rem; }
.child-header .subtitle { color: #888; font-size: 0.95rem; }
.muted { color: #888; font-style: italic; padding: 1rem 0; }
.empty-state { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2rem 0; color: #888; }
.empty-icon  { font-size: 2.5rem; }
/* scrollovatelná tabulka */
.table-scroll { max-height: 320px; overflow-y: auto; border-radius: 8px; border: 1px solid #f0f0f0; }
.table-scroll thead th { position: sticky; top: 0; background: #fff; z-index: 1; box-shadow: 0 1px 0 #eee; }
.table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
.table th { text-align: left; padding: 0.5rem; border-bottom: 2px solid #eee; }
.table td { padding: 0.5rem; border-bottom: 1px solid #f0f0f0; }
/* stats */
.stats .stat-row { display: flex; gap: 1.5rem; margin-top: 0.5rem; flex-wrap: wrap; }
.stat { display: flex; flex-direction: column; gap: 0.15rem; min-width: 100px; }
.stat-value  { font-size: 1.8rem; font-weight: 700; color: #e94560; }
.stat-value.settled { color: #0d6efd; }
.stat-label  { font-size: 0.78rem; color: #888; text-transform: uppercase; letter-spacing: 0.03em; }
/* skeleton loader */
.skeleton-list { display: flex; flex-direction: column; gap: 0.75rem; padding: 0.5rem 0; }
.skeleton-row  {
  height: 2.5rem;
  border-radius: 8px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}
@keyframes shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position:  200% 0; }
}
/* badges */
.badge { padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.8rem; font-weight: 600; }
.badge-submitted { background: #fff3cd; color: #856404; }
.badge-approved  { background: #d4edda; color: #155724; }
.badge-rejected  { background: #f8d7da; color: #721c24; }
.badge-settled   { background: #cce5ff; color: #004085; }
</style>
