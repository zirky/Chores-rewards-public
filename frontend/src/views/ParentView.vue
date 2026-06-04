<template>
  <div>
    <!-- SETUP -->
    <div v-if="mode === 'setup'" class="card login-card">
      <h2>🔐 Nastav PIN rodiče</h2>
      <p class="muted">První spuštění – zvol PIN pro rodičovský přístup.</p>
      <div class="pin-form">
        <input v-model="loginPin" type="password" inputmode="numeric" placeholder="Nový PIN"
          class="pin-input" maxlength="8" @keyup.enter="doSetup" :disabled="loginLoading" />
        <button class="btn btn-primary" @click="doSetup" :disabled="loginLoading || !loginPin">
          {{ loginLoading ? 'Ukládám…' : 'Nastavit PIN' }}
        </button>
      </div>
      <p v-if="loginError" class="error-msg">{{ loginError }}</p>
    </div>

    <!-- LOGIN -->
    <div v-else-if="mode === 'login'" class="card login-card">
      <h2>🔓 Přihlášení rodiče</h2>
      <p class="muted">Zadej PIN pro přístup do rodičovského rozhraní.</p>
      <div class="pin-form">
        <input v-model="loginPin" type="password" inputmode="numeric" placeholder="PIN"
          class="pin-input" maxlength="8" @keyup.enter="doLogin" :disabled="loginLoading" />
        <button class="btn btn-primary" @click="doLogin" :disabled="loginLoading || !loginPin">
          {{ loginLoading ? 'Přihlašuji…' : 'Přihlásit' }}
        </button>
      </div>
      <p v-if="loginError" class="error-msg">{{ loginError }}</p>
    </div>

    <!-- HLAVNÍ ROZHRANÍ -->
    <template v-else-if="mode === 'app'">
      <div class="card rate-card">
        <span v-if="rate">⚡ BTC/CZK: {{ rate.rate_czk_per_btc.toLocaleString('cs-CZ') }}</span>
        <span v-else class="muted">Načítám kurz…</span>
        <button class="btn btn-ghost btn-sm logout-btn" @click="logout">🚪 Odhlásit</button>
      </div>

      <!-- SPRÁVA DĚTÍ -->
      <div class="card">
        <div class="section-header">
          <h2>👦 Správa dětí</h2>
          <button class="btn btn-primary btn-sm" @click="openChildForm(null)">+ Přidat dítě</button>
        </div>
        <div v-if="children.length === 0" class="empty">Zatím žádné děti. Přidej první dítě.</div>
        <div v-else class="table-scroll">
          <table class="table">
            <thead><tr><th>Jméno</th><th>Lightning adresa</th><th>Metoda</th><th>Stav</th><th></th></tr></thead>
            <tbody>
              <tr v-for="child in children" :key="child.id" :class="{ inactive: !child.active }">
                <td><strong>{{ child.name }}</strong></td>
                <td>
                  <span v-if="child.ln_address && child.ln_address !== 'string'" class="ln-addr">⚡ {{ child.ln_address }}</span>
                  <span v-else class="muted">nenastavena</span>
                </td>
                <td>
                  <span class="method-badge" :class="child.payout_method">
                    {{ child.payout_method === 'ln_address' ? '⚡ Přímá platba' : '📱 Voucher QR' }}
                  </span>
                </td>
                <td><span :class="child.active ? 'badge badge-paid' : 'badge badge-failed'">{{ child.active ? 'Aktivní' : 'Neaktivní' }}</span></td>
                <td class="actions">
                  <button class="btn btn-ghost btn-sm" @click="openChildForm(child)">✏️ Upravit</button>
                  <button v-if="child.active" class="btn btn-warning btn-sm" @click="deactivate(child)" title="Deaktivovat">⏸</button>
                  <button class="btn btn-danger btn-sm" @click="confirmDelete(child)" title="Trvale vymazat">🗑️</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Formulář dítě -->
      <div v-if="childForm.show" class="overlay" @click.self="childForm.show = false">
        <div class="modal">
          <h3>{{ childForm.id ? 'Upravit dítě' : 'Přidat dítě' }}</h3>
          <label class="form-label">Jméno</label>
          <input v-model="childForm.name" class="form-input" placeholder="např. Lukáš" />
          <label class="form-label">Metoda výplaty</label>
          <div class="radio-group">
            <label class="radio-option" :class="{ active: childForm.payout_method === 'ln_address' }">
              <input type="radio" v-model="childForm.payout_method" value="ln_address" />
              ⚡ Přímá platba na Lightning adresu
            </label>
            <label class="radio-option" :class="{ active: childForm.payout_method === 'voucher' }">
              <input type="radio" v-model="childForm.payout_method" value="voucher" />
              📱 LNURL-withdraw voucher (QR kód)
            </label>
          </div>
          <div v-if="childForm.payout_method === 'ln_address'">
            <label class="form-label">⚡ Lightning adresa</label>
            <input v-model="childForm.ln_address" class="form-input"
              placeholder="např. jmeno@bitlifi.com nebo +420XXXXXXXXX@bitlifi.com"
              :class="{ 'input-error': childForm.ln_address && !isValidLnAddress(childForm.ln_address) }" />
            <p v-if="childForm.ln_address && !isValidLnAddress(childForm.ln_address)" class="field-hint error">
              Musí mít formát <code>něco@doména.tld</code>
            </p>
            <p v-else class="field-hint">BitLifi: <code>+420XXXXXXXXX@bitlifi.com</code></p>
          </div>
          <div v-else>
            <p class="field-hint">📱 QR kód se zobrazí rodiči po výplatě.</p>
          </div>
          <p v-if="childForm.error" class="error-msg">{{ childForm.error }}</p>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="childForm.show = false">Zrušit</button>
            <button class="btn btn-primary" @click="saveChild"
              :disabled="!childForm.name || (childForm.payout_method === 'ln_address' && !isValidLnAddress(childForm.ln_address)) || childForm.saving">
              {{ childForm.saving ? 'Ukládám…' : (childForm.id ? 'Uložit změny' : 'Přidat') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Potvrzení smazání dítěte -->
      <div v-if="deleteModal.show" class="overlay" @click.self="deleteModal.show = false">
        <div class="modal modal-danger">
          <h3>🗑️ Trvale vymazat dítě?</h3>
          <p>Chystáš se trvale smazat <strong>{{ deleteModal.child?.name }}</strong> a všechna jeho data.</p>
          <p class="warning-text">⚠️ Tato akce je nevratná!</p>
          <p v-if="deleteModal.error" class="error-msg">{{ deleteModal.error }}</p>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="deleteModal.show = false">Zrušit</button>
            <button class="btn btn-danger" @click="doDelete" :disabled="deleteModal.deleting">
              {{ deleteModal.deleting ? 'Mažu…' : 'Ano, smazat' }}
            </button>
          </div>
        </div>
      </div>

      <!-- SPRÁVA ÚKOLŮ -->
      <div class="card">
        <div class="section-header">
          <h2>📋 Správa úkolů</h2>
          <button class="btn btn-primary btn-sm" @click="openTaskForm(null)">+ Přidat úkol</button>
        </div>
        <div v-if="allTasks.length === 0" class="empty">Zatím žádné úkoly.</div>
        <div v-else class="table-scroll">
          <table class="table">
            <thead><tr><th>Název</th><th>Odměna</th><th>Denní limit</th><th>Stav</th><th></th></tr></thead>
            <tbody>
              <tr v-for="task in allTasks" :key="task.id" :class="{ inactive: !task.active }">
                <td><strong>{{ task.title }}</strong></td>
                <td>{{ task.reward_czk }} CZK</td>
                <td>
                  <span class="limit-badge">
                    {{ task.daily_limit === 0 ? '∞ neomezeno' : task.daily_limit + '× za den' }}
                  </span>
                </td>
                <td><span :class="task.active ? 'badge badge-paid' : 'badge badge-failed'">{{ task.active ? 'Aktivní' : 'Neaktivní' }}</span></td>
                <td class="actions">
                  <button class="btn btn-ghost btn-sm" @click="openTaskForm(task)">✏️ Upravit</button>
                  <button class="btn btn-danger btn-sm" @click="removeTask(task)" title="Smazat/deaktivovat">🗑️</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Formulář úkol -->
      <div v-if="taskForm.show" class="overlay" @click.self="taskForm.show = false">
        <div class="modal">
          <h3>{{ taskForm.id ? 'Upravit úkol' : 'Přidat úkol' }}</h3>

          <label class="form-label">Název úkolu</label>
          <input v-model="taskForm.title" class="form-input" placeholder="např. Mytí nádobí" />

          <label class="form-label">Odměna (CZK)</label>
          <input v-model.number="taskForm.reward_czk" type="number" min="0.5" step="0.5" class="form-input" placeholder="5" />

          <label class="form-label">Denní limit splnění</label>
          <div class="limit-options">
            <button v-for="opt in limitOptions" :key="opt.value"
              class="btn btn-sm" :class="taskForm.daily_limit === opt.value ? 'btn-primary' : 'btn-ghost'"
              @click="taskForm.daily_limit = opt.value">
              {{ opt.label }}
            </button>
          </div>
          <p class="field-hint">
            {{ taskForm.daily_limit === 0 ? 'Dítě může splnit úkol libovolněkrát za den.' : `Dítě může splnit úkol max. ${taskForm.daily_limit}× za den.` }}
          </p>

          <div v-if="taskForm.id" style="margin-top: 0.5rem">
            <label class="form-label">Stav</label>
            <div class="radio-group">
              <label class="radio-option" :class="{ active: taskForm.active }">
                <input type="radio" v-model="taskForm.active" :value="true" /> Aktivní
              </label>
              <label class="radio-option" :class="{ active: !taskForm.active }">
                <input type="radio" v-model="taskForm.active" :value="false" /> Neaktivní
              </label>
            </div>
          </div>

          <p v-if="taskForm.error" class="error-msg">{{ taskForm.error }}</p>
          <div class="modal-actions">
            <button class="btn btn-ghost" @click="taskForm.show = false">Zrušit</button>
            <button class="btn btn-primary" @click="saveTask"
              :disabled="!taskForm.title || !taskForm.reward_czk || taskForm.saving">
              {{ taskForm.saving ? 'Ukládám…' : (taskForm.id ? 'Uložit změny' : 'Přidat úkol') }}
            </button>
          </div>
        </div>
      </div>

      <!-- Čeká na schválení -->
      <div class="card">
        <h2>⏳ Čeká na schválení ({{ pending.length }})</h2>
        <div v-if="pending.length === 0" class="empty">Vše schváleno ✓</div>
        <div v-else class="table-scroll table-scroll-sm">
          <table class="table">
            <thead><tr><th>Dítě</th><th>Úkol</th><th>Odměna</th><th>Akce</th></tr></thead>
            <tbody>
              <tr v-for="c in pending" :key="c.id">
                <td>{{ c.child_name || childName(c.child_id) }}</td>
                <td>{{ c.task_title }}</td>
                <td>{{ c.reward_czk }} CZK</td>
                <td class="actions">
                  <button class="btn btn-success" @click="approve(c)">✓ Schválit</button>
                  <button class="btn btn-danger"  @click="reject(c)">✕ Zamítnout</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Výplata -->
      <div class="card">
        <h2>💸 Výplata odměn</h2>
        <div v-if="activeChildren.length === 0" class="empty">Nejdřív přidej aktivní dítě.</div>
        <div v-for="child in activeChildren" :key="child.id" class="child-payout-row">
          <div class="child-info">
            <strong>{{ child.name }}</strong>
            <span class="muted" v-if="balances[child.id]">
              {{ balances[child.id].pending_count }} schválených
              &middot; {{ balances[child.id].total_sats }} sats
              &middot; {{ balances[child.id].total_czk }} CZK
            </span>
            <span class="muted" v-else>Načítám…</span>
            <span v-if="child.payout_method === 'ln_address' && child.ln_address && child.ln_address !== 'string'" class="addr">⚡ {{ child.ln_address }}</span>
            <span v-else class="addr voucher-label">📱 Voucher (QR kód)</span>
          </div>
          <button class="btn btn-primary"
            :disabled="!balances[child.id] || balances[child.id].pending_count === 0 || paying[child.id]"
            @click="startPay(child)">
            {{ paying[child.id] ? 'Odesílám…' : 'Vyplatit' }}
          </button>
        </div>
      </div>

      <!-- Historie výplat -->
      <div class="card" v-if="activeChildren.length > 0">
        <h2>📜 Historie výplat</h2>
        <div class="child-tabs" v-if="activeChildren.length > 1">
          <button v-for="child in activeChildren" :key="child.id"
            class="btn" :class="selectedChild?.id === child.id ? 'btn-primary' : 'btn-ghost'"
            @click="loadPayoutHistory(child)">{{ child.name }}</button>
        </div>
        <div v-if="payoutHistory.length === 0" class="empty">Zatím žádné výplaty.</div>
        <div v-else class="table-scroll">
          <table class="table">
            <thead><tr><th>Datum</th><th>Sats</th><th>CZK</th><th>Metoda</th><th>Stav</th><th></th></tr></thead>
            <tbody>
              <tr v-for="p in payoutHistory" :key="p.id">
                <td>{{ fmt(p.paid_at || p.created_at) }}</td>
                <td>{{ p.total_sats }}</td>
                <td>{{ p.total_czk }}</td>
                <td><span class="method-badge" :class="p.payout_method">{{ p.payout_method === 'ln_address' ? '⚡ LN' : '📱 QR' }}</span></td>
                <td><span :class="'badge badge-' + p.status">{{ statusLabel(p.status) }}</span></td>
                <td class="actions">
                  <button v-if="p.payout_method === 'ln_address'"
                    class="btn btn-ghost btn-sm" @click="checkStatus(p)" :disabled="checking[p.id]">↻</button>
                  <button v-if="p.payout_method === 'voucher'"
                    class="btn btn-ghost btn-sm" @click="showVoucherQr(p)" :disabled="loadingQr[p.id]">{{ loadingQr[p.id] ? '…' : 'QR' }}</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- PIN modal -->
      <PinModal v-if="modal.show" :title="modal.title" :message="modal.message"
        ref="pinModalRef" @confirm="onPinConfirm" @cancel="modal.show = false" />

      <!-- QR modal -->
      <div v-if="qrModal.show" class="overlay" @click.self="qrModal.show = false">
        <div class="qr-modal">
          <h3>📱 Voucher QR kód</h3>
          <p class="qr-hint">Dítě naskenuje QR kód svým Lightning peněženkou.</p>
          <img :src="'data:image/png;base64,' + qrModal.qr" alt="LNURL-withdraw QR" class="qr-img" width="260" height="260" />
          <p class="lnurl-str">{{ qrModal.lnurl }}</p>
          <button class="btn btn-primary" @click="qrModal.show = false">Zavřít</button>
        </div>
      </div>
    </template>

    <div v-if="toast.show" class="toast" :class="'toast-' + toast.type">{{ toast.msg }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive } from 'vue'
import PinModal from '../components/PinModal.vue'
import {
  getPending, approveCompletion, rejectCompletion,
  getChildren, getBalance, payChild,
  getPayoutHistory, getPayoutStatus, getVoucherQr,
  getRate, parentLogin, setupPin,
  createChild, updateChild, deactivateChild, deleteChild,
  getAllTasks, createTask, updateTask, deleteTask
} from '../api.js'

const mode         = ref('login')
const loginPin     = ref('')
const loginError   = ref('')
const loginLoading = ref(false)

onMounted(async () => {
  try {
    const r = await fetch('/api/auth/verify', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: '' })
    })
    const data = await r.json()
    if (data.detail?.includes('není nastaven')) mode.value = 'setup'
  } catch (e) {}
})

async function doSetup() {
  if (!loginPin.value) return
  loginLoading.value = true; loginError.value = ''
  try { await setupPin(loginPin.value); showToast('PIN nastaven!', 'ok'); mode.value = 'login'; loginPin.value = '' }
  catch (e) { loginError.value = e.message }
  finally { loginLoading.value = false }
}

async function doLogin() {
  if (!loginPin.value) return
  loginLoading.value = true; loginError.value = ''
  try {
    await parentLogin(loginPin.value)
    mode.value = 'app'; loginPin.value = ''
    await loadAll()
    if (activeChildren.value.length > 0) await loadPayoutHistory(activeChildren.value[0])
  } catch (e) {
    if (e.message?.includes('není nastaven')) mode.value = 'setup'
    else loginError.value = e.message || 'Chybný PIN'
  } finally { loginLoading.value = false }
}

function logout() {
  window.__parentToken = null; mode.value = 'login'
  pending.value = []; children.value = []; payoutHistory.value = []; allTasks.value = []
  Object.keys(balances).forEach(k => delete balances[k])
}

// ── Data ──────────────────────────────────────────────────────────────────────
const pending       = ref([])
const children      = ref([])
const allTasks      = ref([])
const balances      = reactive({})
const paying        = reactive({})
const checking      = reactive({})
const loadingQr     = reactive({})
const rate          = ref(null)
const payoutHistory = ref([])
const selectedChild = ref(null)
const pinModalRef   = ref(null)
const modal         = ref({ show: false, title: '', message: '', action: null, target: null })
const qrModal       = ref({ show: false, qr: '', lnurl: '' })
const toast         = ref({ show: false, msg: '', type: 'ok' })
const childForm     = reactive({ show: false, id: null, name: '', payout_method: 'ln_address', ln_address: '', error: '', saving: false })
const deleteModal   = reactive({ show: false, child: null, deleting: false, error: '' })
const taskForm      = reactive({ show: false, id: null, title: '', reward_czk: 5, daily_limit: 1, active: true, error: '', saving: false })

const limitOptions = [
  { value: 1, label: '1× za den' },
  { value: 2, label: '2× za den' },
  { value: 3, label: '3× za den' },
  { value: 5, label: '5× za den' },
  { value: 0, label: '∞ neomezeno' },
]

const activeChildren = computed(() => children.value.filter(c => c.active))

async function loadAll() {
  const [p, ch, r, tasks] = await Promise.all([
    getPending().catch(() => []),
    getChildren().catch(() => []),
    getRate().catch(() => null),
    getAllTasks().catch(() => [])
  ])
  pending.value = p; children.value = ch; allTasks.value = tasks
  if (r) rate.value = r
  for (const child of ch.filter(c => c.active)) {
    getBalance(child.id).then(b => { balances[child.id] = b }).catch(() => {})
  }
}

async function loadPayoutHistory(child) {
  selectedChild.value = child
  payoutHistory.value = await getPayoutHistory(child.id).catch(() => [])
}

// ── Správa dětí ──────────────────────────────────────────────────────────────
function isValidLnAddress(addr) { return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(addr) }

function openChildForm(child) {
  if (child) {
    childForm.id            = child.id
    childForm.name          = child.name
    childForm.payout_method = child.payout_method === 'voucher' ? 'voucher' : 'ln_address'
    childForm.ln_address    = (child.ln_address && child.ln_address !== 'string') ? child.ln_address : ''
  } else {
    childForm.id = null; childForm.name = ''; childForm.payout_method = 'ln_address'; childForm.ln_address = ''
  }
  childForm.error = ''; childForm.saving = false; childForm.show = true
}

async function saveChild() {
  childForm.error = ''; childForm.saving = true
  const payload = {
    name:          childForm.name.trim(),
    payout_method: childForm.payout_method,
    ln_address:    childForm.payout_method === 'ln_address' ? childForm.ln_address.trim() : null
  }
  try {
    if (childForm.id) { await updateChild(childForm.id, payload); showToast('Uloženo ✓', 'ok') }
    else              { await createChild(payload); showToast('Dítě přidáno ✓', 'ok') }
    childForm.show = false; await loadAll()
    if (activeChildren.value.length > 0 && !selectedChild.value) await loadPayoutHistory(activeChildren.value[0])
  } catch (e) { childForm.error = e.message }
  finally { childForm.saving = false }
}

async function deactivate(child) {
  if (!confirm(`Opravdu deaktivovat ${child.name}?`)) return
  try { await deactivateChild(child.id); showToast(`${child.name} deaktivován`, 'warn'); await loadAll() }
  catch (e) { showToast(e.message, 'err') }
}

function confirmDelete(child) {
  deleteModal.child = child; deleteModal.error = ''; deleteModal.deleting = false; deleteModal.show = true
}

async function doDelete() {
  deleteModal.deleting = true; deleteModal.error = ''
  try {
    await deleteChild(deleteModal.child.id)
    showToast(`${deleteModal.child.name} smazán`, 'warn')
    deleteModal.show = false; await loadAll()
  } catch (e) { deleteModal.error = e.message }
  finally { deleteModal.deleting = false }
}

// ── Správa úkolů ──────────────────────────────────────────────────────────────
function openTaskForm(task) {
  if (task) {
    taskForm.id          = task.id
    taskForm.title       = task.title
    taskForm.reward_czk  = task.reward_czk
    taskForm.daily_limit = task.daily_limit ?? 1
    taskForm.active      = task.active
  } else {
    taskForm.id = null; taskForm.title = ''; taskForm.reward_czk = 5; taskForm.daily_limit = 1; taskForm.active = true
  }
  taskForm.error = ''; taskForm.saving = false; taskForm.show = true
}

async function saveTask() {
  taskForm.error = ''; taskForm.saving = true
  const payload = {
    title:       taskForm.title.trim(),
    reward_czk:  taskForm.reward_czk,
    daily_limit: taskForm.daily_limit,
    ...(taskForm.id ? { active: taskForm.active } : {})
  }
  try {
    if (taskForm.id) { await updateTask(taskForm.id, payload); showToast('Úkol upraven ✓', 'ok') }
    else             { await createTask(payload); showToast('Úkol přidán ✓', 'ok') }
    taskForm.show = false; await loadAll()
  } catch (e) { taskForm.error = e.message }
  finally { taskForm.saving = false }
}

async function removeTask(task) {
  if (!confirm(`Smazat úkol "${task.title}"?`)) return
  try {
    const res = await deleteTask(task.id)
    const msg = typeof res === 'object' ? res.detail : res
    showToast(msg || 'Smazáno', 'warn')
    await loadAll()
  } catch (e) { showToast(e.message, 'err') }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function childName(id) { return children.value.find(c => c.id === id)?.name || `#${id}` }
function fmt(dt) { return dt ? new Date(dt).toLocaleDateString('cs-CZ', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '–' }
function statusLabel(s) { return { open: 'Otevřeno', paid: 'Zaplaceno', failed: 'Chyba' }[s] || s }

async function approve(c) {
  try { await approveCompletion(c.id); showToast('Schváleno ✓', 'ok'); await loadAll() }
  catch (e) { showToast(e.message, 'err') }
}
async function reject(c) {
  try { await rejectCompletion(c.id); showToast('Zamítnuto', 'warn'); await loadAll() }
  catch (e) { showToast(e.message, 'err') }
}

function startPay(child) {
  const bal  = balances[child.id]
  const dest = (child.payout_method === 'ln_address' && child.ln_address && child.ln_address !== 'string')
    ? `Lightning adresu ${child.ln_address}` : 'LNURL-withdraw voucher (QR kód)'
  modal.value = { show: true, action: 'pay', target: child,
    title: `Výplata – ${child.name}`,
    message: `Odeslat ${bal.total_sats} sats (${bal.total_czk} CZK) na ${dest}?` }
}

async function onPinConfirm(pin) {
  const { action, target } = modal.value
  try {
    await parentLogin(pin)
    if (action === 'pay') {
      paying[target.id] = true
      const result = await payChild(target.id)
      paying[target.id] = false
      if (result.payout_method === 'voucher') await _fetchAndShowQr(result.id)
      else showToast(`Odesláno ⚡ ${result.total_sats} sats`, 'ok')
      await loadPayoutHistory(target)
    }
    modal.value.show = false; await loadAll()
  } catch (e) {
    paying[modal.value.target?.id] = false
    pinModalRef.value?.setError(e.message)
  }
}

async function checkStatus(payout) {
  checking[payout.id] = true
  try {
    const res = await getPayoutStatus(payout.id)
    if (res.lnbits_confirmed === true) showToast('✓ LNbits potvrzuje platbu', 'ok')
    else if (res.lnbits_confirmed === false) showToast('⚠️ Nezaplaceno', 'warn')
    else showToast('LNbits nedostupné', 'warn')
  } catch (e) { showToast(e.message, 'err') }
  finally { checking[payout.id] = false }
}

async function showVoucherQr(payout) {
  loadingQr[payout.id] = true
  try { await _fetchAndShowQr(payout.id) }
  catch (e) { showToast(e.message, 'err') }
  finally { loadingQr[payout.id] = false }
}

async function _fetchAndShowQr(payoutId) {
  const data = await getVoucherQr(payoutId)
  qrModal.value = { show: true, qr: data.qr_png_base64, lnurl: data.lnurl }
}

function showToast(msg, type = 'ok') {
  toast.value = { show: true, msg, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}
</script>

<style scoped>
.login-card { max-width: 400px; margin: 3rem auto; text-align: center; }
.login-card h2 { margin-bottom: 0.5rem; }
.pin-form { display: flex; gap: 0.75rem; margin-top: 1.25rem; justify-content: center; }
.pin-input { padding: 0.5rem 1rem; border: 2px solid #ddd; border-radius: 8px; font-size: 1.1rem; width: 140px; text-align: center; letter-spacing: 0.2em; }
.pin-input:focus { outline: none; border-color: #e94560; }
.error-msg { color: #e94560; margin-top: 0.5rem; font-size: 0.9rem; }
.warning-text { color: #b07a00; font-weight: 600; }
.rate-card { background: #1a1a2e; color: #ccc; font-size: 0.9rem; padding: 0.7rem 1.5rem; border-radius: 12px; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; }
.logout-btn { font-size: 0.8rem; padding: 0.25rem 0.75rem; }
.section-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
.section-header h2 { margin: 0; }
.muted { color: #888; font-style: italic; }
.empty { color: #888; font-style: italic; padding: 1rem 0; }
.inactive td { opacity: 0.45; }
.ln-addr { font-size: 0.85rem; color: #016e5b; font-weight: 500; }
.addr { font-size: 0.8rem; color: #666; }
.voucher-label { color: #b07a00; }
/* ── Scrollovatelné tabulky ─────────────────────────────────── */
.table-scroll { max-height: 320px; overflow-y: auto; border-radius: 8px; border: 1px solid #f0f0f0; }
.table-scroll-sm { max-height: 240px; }
.table-scroll thead th { position: sticky; top: 0; background: #fff; z-index: 1; box-shadow: 0 1px 0 #eee; }
/* ─────────────────────────────────────────────────────────────── */
.table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
.table th { text-align: left; padding: 0.5rem; border-bottom: 2px solid #eee; }
.table td { padding: 0.5rem; border-bottom: 1px solid #f0f0f0; vertical-align: middle; }
.actions { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.child-payout-row { display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid #f0f0f0; }
.child-payout-row:last-child { border-bottom: none; }
.child-info { display: flex; flex-direction: column; gap: 0.2rem; }
.child-tabs { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,.55); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 16px; padding: 2rem; width: 90%; max-width: 440px; display: flex; flex-direction: column; gap: 0.75rem; max-height: 90vh; overflow-y: auto; }
.modal-danger { border: 2px solid #e74c3c; }
.modal-danger h3 { color: #e74c3c; }
.form-label { font-size: 0.85rem; font-weight: 600; color: #444; margin-bottom: 0; }
.form-input { padding: 0.5rem 0.75rem; border: 2px solid #ddd; border-radius: 8px; font-size: 1rem; width: 100%; }
.form-input:focus { outline: none; border-color: #e94560; }
.form-input.input-error { border-color: #e74c3c; }
.radio-group { display: flex; flex-direction: column; gap: 0.4rem; }
.radio-option { display: flex; align-items: center; gap: 0.5rem; padding: 0.6rem 0.9rem; border: 2px solid #eee; border-radius: 8px; cursor: pointer; font-size: 0.95rem; transition: border-color .15s; }
.radio-option.active { border-color: #e94560; background: #fff5f7; }
.radio-option input[type=radio] { accent-color: #e94560; }
.field-hint { font-size: 0.8rem; color: #888; margin: 0; }
.field-hint.error { color: #e74c3c; }
.field-hint code { background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 4px; font-size: 0.8rem; }
.modal-actions { display: flex; justify-content: flex-end; gap: 0.5rem; margin-top: 0.5rem; }
.limit-options { display: flex; gap: 0.4rem; flex-wrap: wrap; }
.limit-badge { font-size: 0.8rem; padding: 0.15rem 0.6rem; border-radius: 9999px; background: #e8f4fd; color: #1a6a9a; font-weight: 500; }
.btn { padding: 0.4rem 1rem; border-radius: 8px; font-size: 0.9rem; cursor: pointer; border: none; font-weight: 600; }
.btn-sm { padding: 0.25rem 0.6rem; font-size: 0.8rem; }
.btn-primary { background: #e94560; color: #fff; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-success { background: #2ecc71; color: #fff; }
.btn-danger { background: #e74c3c; color: #fff; }
.btn-danger:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-warning { background: #f39c12; color: #fff; }
.btn-ghost { background: #f0f0f0; color: #333; }
.badge { padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.8rem; }
.badge-paid { background: #d4edda; color: #155724; }
.badge-open { background: #fff3cd; color: #856404; }
.badge-failed { background: #f8d7da; color: #721c24; }
.method-badge { font-size: 0.8rem; padding: 0.15rem 0.5rem; border-radius: 6px; background: #f0f0f0; }
.method-badge.voucher { background: #fff3cd; color: #856404; }
.method-badge.ln_address { background: #d4edda; color: #155724; }
.qr-modal { background: #fff; border-radius: 16px; padding: 2rem; display: flex; flex-direction: column; align-items: center; gap: 1rem; max-width: 320px; width: 90%; }
.qr-modal h3 { margin: 0; font-size: 1.2rem; }
.qr-hint { font-size: 0.85rem; color: #666; text-align: center; margin: 0; }
.qr-img { border-radius: 8px; border: 1px solid #eee; }
.lnurl-str { font-size: 0.65rem; color: #aaa; word-break: break-all; text-align: center; max-width: 280px; }
.toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.6rem 1.4rem; border-radius: 9999px; font-size: 0.9rem; font-weight: 500; z-index: 200; animation: fadein .2s ease; }
.toast-ok { background: #d4edda; color: #155724; }
.toast-warn { background: #fff3cd; color: #856404; }
.toast-err { background: #f8d7da; color: #721c24; }
@keyframes fadein { from { opacity: 0; transform: translateX(-50%) translateY(8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }
</style>
