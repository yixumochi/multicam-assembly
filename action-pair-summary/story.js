(() => {
  'use strict'

  function element(tag, className, text) {
    const node = document.createElement(tag)
    if (className) node.className = className
    if (text !== undefined) node.textContent = text
    return node
  }

  function framePreview(filename, caseId, actionName) {
    const frame = element('figure', 'scatter-case-frame')
    const image = document.createElement('img')
    image.src = '../plates/click_rest/' + encodeURIComponent(filename)
    image.alt = actionName
    image.loading = 'lazy'
    image.decoding = 'async'
    frame.append(image, element('figcaption', '', caseId))
    return frame
  }

  function caseCard(pair, story, gap) {
    const link = element('a', 'scatter-case')
    link.dataset.tone = story.tone
    link.href = '../index.html#action-pair=' + pair.id

    const title = element('h3', 'scatter-case-title', story.heading)
    const stats = element('p', 'scatter-case-stats', pair.score.toFixed(3) + ' cosine · ' + gap.toFixed(1) + '° gap')
    const titleBlock = element('div')
    titleBlock.append(title, stats)
    const arrow = element('span', 'scatter-case-arrow', '→')
    arrow.setAttribute('aria-hidden', 'true')
    const header = element('div', 'scatter-case-header')
    header.append(titleBlock, arrow)

    const evidence = element('div', 'scatter-case-evidence')
    story.images.forEach((filename, index) => {
      evidence.appendChild(framePreview(filename, pair.cases[index], pair.names[index]))
    })
    const body = element('div', 'scatter-case-body')
    body.append(evidence, element('p', 'scatter-case-summary', story.summary))
    link.append(header, body)
    return link
  }

  window.renderScatterCases = function renderScatterCases(container, displayedPairs, details, getGap) {
    const shown = new Map(displayedPairs.map(pair => [pair.id, pair]))
    const cards = []
    for (const [id, story] of Object.entries(details)) {
      const pair = shown.get(id)
      if (!pair) continue
      const gap = getGap(pair)
      if (gap !== null) cards.push(caseCard(pair, story, gap))
    }
    container.hidden = cards.length === 0
    if (container.hidden) {
      container.replaceChildren()
      return
    }

    const heading = element('h2', 'scatter-cases-title', 'Case examples')
    heading.id = container.id + '-title'
    container.setAttribute('aria-labelledby', heading.id)
    const list = element('div', 'scatter-case-list')
    list.append(...cards)
    container.replaceChildren(heading, list)
  }
})()
