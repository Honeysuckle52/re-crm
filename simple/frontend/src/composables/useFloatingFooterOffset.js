import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const DEFAULT_FOOTER_SELECTOR = '.footer, .app-footer, footer'

export function useFloatingFooterOffset(options = {}) {
  const {
    baseGap = 20,
    footerSelector = DEFAULT_FOOTER_SELECTOR,
  } = options

  const footerOverlap = ref(0)
  let footerEl = null
  let intersectionObserver = null
  let resizeObserver = null

  function measureFooter() {
    if (!footerEl) {
      footerOverlap.value = 0
      return
    }

    const rect = footerEl.getBoundingClientRect()
    const viewport = window.innerHeight || document.documentElement.clientHeight
    const overlap = Math.max(0, viewport - rect.top)
    footerOverlap.value = Math.min(overlap, rect.height)
  }

  function attachFooterObservers() {
    footerEl = document.querySelector(footerSelector)
    if (!footerEl) {
      footerOverlap.value = 0
      return
    }

    measureFooter()

    if ('IntersectionObserver' in window) {
      intersectionObserver = new IntersectionObserver(measureFooter, {
        threshold: [0, 0.01, 0.1, 0.25, 0.5, 0.75, 1],
      })
      intersectionObserver.observe(footerEl)
    }

    if ('ResizeObserver' in window) {
      resizeObserver = new ResizeObserver(measureFooter)
      resizeObserver.observe(footerEl)
    }

    window.addEventListener('scroll', measureFooter, { passive: true })
    window.addEventListener('resize', measureFooter)
  }

  function detachFooterObservers() {
    if (intersectionObserver) {
      intersectionObserver.disconnect()
      intersectionObserver = null
    }

    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }

    window.removeEventListener('scroll', measureFooter)
    window.removeEventListener('resize', measureFooter)

    footerEl = null
    footerOverlap.value = 0
  }

  onMounted(() => {
    window.requestAnimationFrame(attachFooterObservers)
  })

  onBeforeUnmount(() => {
    detachFooterObservers()
  })

  const floatStyle = computed(() => ({
    bottom: `${baseGap + footerOverlap.value}px`,
  }))

  return {
    floatStyle,
    footerOverlap,
    measureFooter,
  }
}
