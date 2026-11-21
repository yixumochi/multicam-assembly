(() => {
  const guides = document.querySelectorAll('.wheel-guide')
  if (!guides.length || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const timeouts = new WeakMap()

  function play(guide) {
    clearTimeout(timeouts.get(guide))
    guide.classList.remove('is-playing')
    void guide.offsetWidth
    guide.classList.add('is-playing')
    timeouts.set(guide, setTimeout(() => guide.classList.remove('is-playing'), 4800))
  }

  const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
    entries.forEach(({target, intersectionRatio}) => {
      if (intersectionRatio < .35) return
      observer.unobserve(target)
      play(target)
    })
  }, {threshold: .35}) : null

  guides.forEach(guide => {
    const replay = guide.querySelector('.wheel-guide-replay')
    replay.hidden = false
    replay.addEventListener('click', () => play(guide))
    if (observer) observer.observe(guide)
    else play(guide)
  })
})()
