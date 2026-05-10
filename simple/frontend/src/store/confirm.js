import { defineStore } from 'pinia'

function defaults() {
  return {
    open: false,
    title: 'Подтверждение',
    message: '',
    confirmLabel: 'Подтвердить',
    cancelLabel: 'Отмена',
    danger: false,
  }
}

export const useConfirmStore = defineStore('confirm', {
  state: () => ({
    ...defaults(),
    resolver: null,
  }),
  actions: {
    ask(options = {}) {
      this.open = true
      this.title = options.title || 'Подтверждение'
      this.message = options.message || ''
      this.confirmLabel = options.confirmLabel || 'Подтвердить'
      this.cancelLabel = options.cancelLabel || 'Отмена'
      this.danger = !!options.danger
      return new Promise((resolve) => {
        this.resolver = resolve
      })
    },
    accept() {
      if (typeof this.resolver === 'function') {
        this.resolver(true)
      }
      this.reset()
    },
    cancel() {
      if (typeof this.resolver === 'function') {
        this.resolver(false)
      }
      this.reset()
    },
    reset() {
      Object.assign(this, defaults(), { resolver: null })
    },
  },
})
