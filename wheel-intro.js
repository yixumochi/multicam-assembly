(() => {
  'use strict'

  const explorer = document.querySelector('#explorer-body')
  const dialog = document.querySelector('#wheel-intro')
  const replay = explorer?.querySelector('[data-wheel-intro-replay]')
  const closeButton = dialog?.querySelector('[data-wheel-intro-close]')
  if (!explorer || !replay || !closeButton || typeof dialog.showModal !== 'function') return

  const closeLabel = closeButton.querySelector('[data-wheel-intro-close-label]')
  const status = dialog.querySelector('[data-wheel-intro-status]')
  const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
  const storageKey = 'multicam-wheel-intro-seen'
  const timers = []
  let seen = false
  let mode = null
  let awaitingVisibility = false

  try {
    seen = window.sessionStorage.getItem(storageKey) === '1'
  } catch {
    // The in-memory flag still covers navigation within this document.
  }

  function markSeen() {
    seen = true
    try {
      window.sessionStorage.setItem(storageKey, '1')
    } catch {
      // Storage may be unavailable in private or embedded contexts.
    }
  }

  function onWheel() {
    return location.hash === '#action-connections' && !explorer.hidden && explorer.getClientRects().length > 0
  }

  function pairIsOpen() {
    return Boolean(document.querySelector('#pair-pop:not([hidden])'))
  }

  function setStep(step) {
    dialog.dataset.step = step
    if (!status) return
    const caption = dialog.querySelector('[data-wheel-intro-step="' + step + '"]')
    const title = caption?.querySelector('strong')?.textContent
    const description = caption?.querySelector('p')?.textContent
    status.textContent = title && description ? 'Step ' + step + ' of 3. ' + title + '. ' + description : ''
  }

  function clearTimers() {
    timers.splice(0).forEach(id => window.clearTimeout(id))
  }

  function showStatic() {
    clearTimers()
    dialog.dataset.static = 'true'
    if (closeLabel) closeLabel.textContent = 'Show the wheel'
    if (status) status.textContent = ''
  }

  function finish(restoreFocus = true) {
    clearTimers()
    if (!dialog.open) return
    mode = null
    dialog.close()
    if (restoreFocus && !document.hidden && onWheel() && !pairIsOpen()) replay.focus({preventScroll: true})
  }

  function open(nextMode) {
    if (dialog.open || !onWheel() || pairIsOpen() || document.querySelector('dialog[open]')) return
    const staticPlayback = preference.matches
    if (staticPlayback && nextMode === 'auto') return

    mode = nextMode
    delete dialog.dataset.static
    if (closeLabel) closeLabel.textContent = 'Skip intro'
    dialog.dataset.step = '1'
    if (status) status.textContent = ''
    dialog.showModal()
    markSeen()
    if (staticPlayback) {
      showStatic()
      return
    }

    setStep('1')
    timers.push(
      window.setTimeout(() => setStep('2'), 1500),
      window.setTimeout(() => setStep('3'), 3100),
      window.setTimeout(finish, 4800)
    )
  }

  function syncWheelIntro() {
    awaitingVisibility = false
    if (!onWheel() || pairIsOpen()) {
      finish(false)
      return
    }
    if (seen || preference.matches) return
    if (document.hidden) awaitingVisibility = true
    else open('auto')
  }

  replay.hidden = false
  replay.addEventListener('click', () => open('replay'))
  closeButton.addEventListener('click', () => finish())
  dialog.addEventListener('cancel', event => {
    event.preventDefault()
    finish()
  })
  dialog.addEventListener('close', () => {
    if (!dialog.open) clearTimers()
  })
  preference.addEventListener?.('change', () => {
    if (!preference.matches || !dialog.open) return
    if (mode === 'replay') showStatic()
    else finish()
  })
  window.addEventListener('hashchange', syncWheelIntro)
  document.addEventListener('visibilitychange', () => {
    if (awaitingVisibility && !document.hidden) syncWheelIntro()
  })
  window.syncWheelIntro = syncWheelIntro
  syncWheelIntro()
})()
