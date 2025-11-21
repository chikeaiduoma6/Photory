import { defineStore } from 'pinia'

type User = { id: number; username: string; email: string; is_admin?: boolean }

const defaultAdminUser: User = {
  id: 0,
  username: 'hyk',
  email: '3230103921@zju.edu.cn',
  is_admin: true,
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || 'dev-admin-token',
    user:
      (localStorage.getItem('user') &&
        JSON.parse(localStorage.getItem('user') as string)) ||
      defaultAdminUser,
  }),
  actions: {
    setAuth(token: string, user: User) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null as any
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
