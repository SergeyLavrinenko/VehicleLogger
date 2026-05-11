import { ref, computed } from 'vue'

const STORAGE_TOKEN = 'vl.token'
const STORAGE_USER  = 'vl.user'
const STORAGE_EXP   = 'vl.expiresAt'

const token     = ref(localStorage.getItem(STORAGE_TOKEN))
const userJson  = localStorage.getItem(STORAGE_USER)
const user      = ref(userJson ? JSON.parse(userJson) : null)
const expiresAt = ref(localStorage.getItem(STORAGE_EXP))

const isAuthed = computed(() => {
  if (!token.value || !expiresAt.value) return false
  return new Date(expiresAt.value).getTime() > Date.now()
})
const isAdmin = computed(() => user.value?.role === 'admin')

function setSession({ token: t, user: u, expiresAt: exp }) {
  token.value     = t
  user.value      = u
  expiresAt.value = exp
  localStorage.setItem(STORAGE_TOKEN, t)
  localStorage.setItem(STORAGE_USER, JSON.stringify(u))
  localStorage.setItem(STORAGE_EXP, exp)
}

function clearSession() {
  token.value = null
  user.value = null
  expiresAt.value = null
  localStorage.removeItem(STORAGE_TOKEN)
  localStorage.removeItem(STORAGE_USER)
  localStorage.removeItem(STORAGE_EXP)
}

export function useAuth() {
  return { token, user, expiresAt, isAuthed, isAdmin, setSession, clearSession }
}
