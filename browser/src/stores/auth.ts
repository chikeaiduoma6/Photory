import { defineStore } from 'pinia'
import axios from 'axios'

type User = { id: number; username: string; email: string; is_admin?: boolean }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: (localStorage.getItem('user') &&
      JSON.parse(localStorage.getItem('user') as string)) as User | null,
  }),
  getters: {
    isAuthed: state => Boolean(state.token),
  },
  actions: {
    hydrate() {
      const token = localStorage.getItem('token')
      if (token) {
        this.token = token
        const rawUser = localStorage.getItem('user')
        this.user = rawUser ? (JSON.parse(rawUser) as User) : null
        axios.defaults.headers.common.Authorization = `Bearer ${token}`
      }
    },
    setAuth(token: string, user: User) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
      axios.defaults.headers.common.Authorization = `Bearer ${token}`
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      delete axios.defaults.headers.common.Authorization
    },
  },
})
