import { computed, ref, watch } from 'vue'

export function useBulkSelection(itemsRef, getId = (item) => item.id) {
  const selectedIds = ref([])

  const selectedSet = computed(() => new Set(selectedIds.value))
  const selectedCount = computed(() => selectedIds.value.length)
  const allOnPageSelected = computed(() => {
    const items = itemsRef.value || []
    return items.length > 0 && items.every((item) => selectedSet.value.has(getId(item)))
  })

  function pruneSelection() {
    const allowedIds = new Set((itemsRef.value || []).map((item) => getId(item)))
    selectedIds.value = selectedIds.value.filter((id) => allowedIds.has(id))
  }

  function isSelected(item) {
    return selectedSet.value.has(getId(item))
  }

  function toggleSelection(item, checked) {
    const id = getId(item)
    if (checked) {
      if (!selectedSet.value.has(id)) {
        selectedIds.value = [...selectedIds.value, id]
      }
      return
    }
    selectedIds.value = selectedIds.value.filter((value) => value !== id)
  }

  function togglePageSelection(checked) {
    if (!checked) {
      selectedIds.value = []
      return
    }
    selectedIds.value = (itemsRef.value || []).map((item) => getId(item))
  }

  function clearSelection() {
    selectedIds.value = []
  }

  watch(itemsRef, pruneSelection, { deep: true })

  return {
    selectedIds,
    selectedCount,
    allOnPageSelected,
    isSelected,
    toggleSelection,
    togglePageSelection,
    clearSelection,
  }
}
