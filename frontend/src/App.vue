<template>
  <div id="app">
    <nav class="navbar">
      <span class="brand">🏠 Chores &amp; Rewards</span>
      <div class="nav-links">
        <button :class="{ active: view === 'child' }" @click="view = 'child'">👦 Dítě</button>
        <button :class="{ active: view === 'parent' }" @click="view = 'parent'">👨 Rodič</button>
      </div>
    </nav>

    <main>
      <!-- Výběr dítěte (pouze v dětském pohledu) -->
      <div v-if="view === 'child'" class="child-selector card">
        <label class="selector-label">Kdo jsi?</label>
        <div class="selector-buttons">
          <button
            v-for="child in children"
            :key="child.id"
            class="btn child-btn"
            :class="{ active: selectedChild?.id === child.id }"
            @click="selectedChild = child"
          >
            {{ child.name }}
          </button>
          <span v-if="children.length === 0" class="muted">
            {{ loadingChildren ? 'Načítám…' : 'Žádné děti – přidej v rodičovském pohledu.' }}
          </span>
        </div>
      </div>

      <ChildView
        v-if="view === 'child' && selectedChild"
        :key="selectedChild.id"
        :childId="selectedChild.id"
        :childName="selectedChild.name"
      />
      <div v-else-if="view === 'child' && children.length > 0 && !selectedChild" class="card muted-center">
        👆 Vyber, kdo tu dnes pracuje.
      </div>

      <ParentView v-if="view === 'parent'" />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import ChildView from './views/ChildView.vue'
import ParentView from './views/ParentView.vue'
import { getChildrenPublic } from './api.js'

const view           = ref('child')
const children       = ref([])
const selectedChild  = ref(null)
const loadingChildren = ref(true)

onMounted(async () => {
  try {
    children.value = await getChildrenPublic()
    if (children.value.length === 1) {
      selectedChild.value = children.value[0]
    }
  } catch (e) {
    // Backend nedostupný při loadu – tiše ignoruj
  } finally {
    loadingChildren.value = false
  }
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', sans-serif; background: #f0f2f5; color: #333; }
#app { min-height: 100vh; }

.navbar {
  background: #1a1a2e;
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.brand { font-size: 1.4rem; font-weight: bold; }
.nav-links button {
  background: transparent;
  border: 2px solid #fff;
  color: white;
  padding: 0.4rem 1.2rem;
  border-radius: 20px;
  cursor: pointer;
  margin-left: 0.5rem;
  font-size: 1rem;
  transition: background 0.2s;
}
.nav-links button.active,
.nav-links button:hover {
  background: #e94560;
  border-color: #e94560;
}

main { max-width: 900px; margin: 2rem auto; padding: 0 1rem; }

.card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

h2 { margin-bottom: 1rem; color: #1a1a2e; }

.child-selector { display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; padding: 1rem 1.5rem; }
.selector-label { font-weight: 600; color: #1a1a2e; white-space: nowrap; }
.selector-buttons { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.child-btn {
  background: #f0f2f5;
  border: 2px solid transparent;
  color: #333;
  padding: 0.4rem 1.2rem;
  border-radius: 20px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
}
.child-btn.active,
.child-btn:hover {
  background: #e94560;
  color: white;
  border-color: #e94560;
}
.muted { color: #888; font-style: italic; }
.muted-center { text-align: center; color: #888; font-style: italic; }

.btn {
  padding: 0.5rem 1.2rem;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  transition: opacity 0.2s;
}
.btn:hover { opacity: 0.85; }
.btn-primary   { background: #e94560; color: white; }
.btn-success   { background: #28a745; color: white; }
.btn-danger    { background: #dc3545; color: white; }
.btn-secondary { background: #6c757d; color: white; }

.badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}
.badge-pending  { background: #fff3cd; color: #856404; }
.badge-approved { background: #d1e7dd; color: #0f5132; }
.badge-rejected { background: #f8d7da; color: #842029; }
.badge-settled  { background: #cfe2ff; color: #084298; }
</style>
