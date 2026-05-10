<template>
  <div
    v-if="confirm.open"
    class="confirm-overlay"
    role="presentation"
    @click.self="confirm.cancel()"
  >
    <div
      class="confirm-dialog panel panel--light"
      role="alertdialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      :aria-describedby="messageId"
    >
      <div class="confirm-dialog__head">
        <h2 :id="titleId" class="h3">{{ confirm.title }}</h2>
        <p :id="messageId" class="muted">{{ confirm.message }}</p>
      </div>

      <div class="confirm-dialog__actions">
        <button class="btn" type="button" @click="confirm.cancel()">
          {{ confirm.cancelLabel }}
        </button>
        <button
          class="btn"
          :class="confirm.danger ? 'btn--danger' : 'btn--accent'"
          type="button"
          @click="confirm.accept()"
        >
          {{ confirm.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useConfirmStore } from '../store/confirm'

const confirm = useConfirmStore()
const titleId = 'confirm-dialog-title'
const messageId = 'confirm-dialog-message'
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 140;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(7, 16, 22, 0.32);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}

.confirm-dialog {
  width: min(100%, 460px);
  padding: 24px;
  border-radius: 24px;
  box-shadow: 0 24px 60px rgba(16, 55, 52, 0.18);
}

.confirm-dialog__head {
  display: grid;
  gap: 8px;
}

.confirm-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 20px;
}

@media (max-width: 640px) {
  .confirm-dialog__actions {
    flex-direction: column-reverse;
  }

  .confirm-dialog__actions > .btn {
    width: 100%;
  }
}
</style>
