(() => {
  'use strict'

  const svgNamespace = 'http://www.w3.org/2000/svg'
  const layouts = new WeakMap()
  const minScore = 0.5
  const maxScore = 1
  const maxGap = 90
  const hitRadius = 8
  const badgeRadius = 10
  const badgeHitRadius = 13
  const badgeDirections = [0, -45, -90, -135, 180, 135, 90, 45]
    .map(angle => [Math.cos(angle * Math.PI / 180), Math.sin(angle * Math.PI / 180)])

  function svgElement(tag, attributes = {}, text) {
    const node = document.createElementNS(svgNamespace, tag)
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value)
    if (text !== undefined) node.textContent = text
    return node
  }

  function htmlElement(tag, className, text) {
    const node = document.createElement(tag)
    node.className = className
    if (text !== undefined) node.textContent = text
    return node
  }

  function labelPoint(pair, gap) {
    const actions = pair.names.map((name, side) => pair.cases[side] + ' · ' + name)
    const values = 'Similarity ' + pair.score.toFixed(3) + ' · Angle gap ' + gap.toFixed(1) + '°'
    const label = actions.join(' paired with ') + '. Name similarity ' + pair.score.toFixed(3) +
      '. Angle change gap ' + gap.toFixed(1) + ' degrees.'
    return {actions, values, label}
  }

  function addAnnotation(point, {tone, number}) {
    const {pair, link} = point
    const group = svgElement('g', {class: 'pair-scatter-annotation', 'aria-hidden': 'true'})
    const leader = svgElement('line', {class: 'pair-scatter-annotation-leader', x1: 0, y1: 0})
    const label = svgElement('g', {class: 'pair-scatter-annotation-label'})
    label.append(
      svgElement('circle', {class: 'pair-scatter-annotation-hit', r: badgeHitRadius}),
      svgElement('circle', {class: 'pair-scatter-annotation-badge', r: badgeRadius}),
      svgElement('text', {'text-anchor': 'middle', y: 4}, number)
    )
    group.append(leader, label)
    link.dataset.annotation = tone
    link.dataset.pairId = pair.id
    link.dataset.caseNumber = number
    link.setAttribute('aria-label', 'Pair ' + number + '. ' + point.info.label)
    link.appendChild(group)
    point.annotation = {leader, label}
  }

  function layoutAnnotations(points, {left, right, top, bottom, tickPositions}) {
    const placed = []
    const clamp = (value, min, max) => Math.max(min, Math.min(value, max))
    points.filter(point => point.annotation).forEach(point => {
      const {x, y, annotation} = point
      const margin = badgeHitRadius + 2
      const candidates = [23, 32, 45, 61].flatMap(distance =>
        badgeDirections.map(([dx, dy]) => [
          clamp(x + dx * distance, left + margin, right - margin),
          clamp(y + dy * distance, top + margin, bottom - margin),
        ])
      )
      // Use the left gutter when the lower-left cluster leaves no room inside the axes.
      const gutterX = badgeHitRadius + 2
      for (const offset of [-26, -40, -58, 24]) {
        const gutterY = clamp(y + offset, top + margin, bottom - margin)
        const leaderY = y + (gutterY - y) * ((left - 15 - x) / (gutterX - x))
        if (tickPositions.every(tick => Math.abs(tick - leaderY) > 9)) {
          candidates.push([gutterX, gutterY])
        }
      }
      let best
      for (const [centerX, centerY] of candidates) {
        const distance = Math.hypot(centerX - x, centerY - y)
        const covered = points.filter(dot =>
          (dot.x - centerX) ** 2 + (dot.y - centerY) ** 2 < (badgeHitRadius + 5) ** 2).length
        const overlaps = placed.some(badge =>
          (badge.x - centerX) ** 2 + (badge.y - centerY) ** 2 < (badgeHitRadius * 2 + 3) ** 2)
        const cost = distance + (centerX < left ? 14 : 0) + covered * 250 + (overlaps ? 5000 : 0)
        if (!best || cost < best.cost) best = {cost, x: centerX, y: centerY}
      }
      placed.push(best)
      annotation.label.setAttribute('transform', 'translate(' + (best.x - x) + ',' + (best.y - y) + ')')
      annotation.leader.setAttribute('x2', best.x - x)
      annotation.leader.setAttribute('y2', best.y - y)
    })
  }

  function nearestHitArea(point, points) {
    const corners = [-hitRadius, hitRadius]
    let polygon = [[corners[0], corners[0]], [corners[1], corners[0]],
      [corners[1], corners[1]], [corners[0], corners[1]]]
    for (const neighbor of points) {
      const dx = neighbor.x - point.x
      const dy = neighbor.y - point.y
      const radiusSquared = dx * dx + dy * dy
      if (radiusSquared === 0 || radiusSquared > 8 * hitRadius ** 2) continue
      // Keep the part of this target closer to its own dot than to its neighbor.
      const distance = ([x, y]) => x * dx + y * dy - radiusSquared / 2
      const clipped = []
      for (let index = 0; index < polygon.length; index++) {
        const from = polygon[index]
        const to = polygon[(index + 1) % polygon.length]
        const start = distance(from)
        const end = distance(to)
        if (start <= 0) clipped.push(from)
        if ((start < 0 && end > 0) || (start > 0 && end < 0)) {
          const t = start / (start - end)
          clipped.push([from[0] + (to[0] - from[0]) * t, from[1] + (to[1] - from[1]) * t])
        }
      }
      polygon = clipped
    }
    return polygon.map(vertex => vertex.join(',')).join(' ')
  }

  window.renderActionPairScatter = function renderActionPairScatter(container, pairs, getGap, examples = {}) {
    layouts.get(container)?.disconnect()
    layouts.delete(container)
    const points = pairs.map(pair => ({pair, gap: getGap(pair)}))
      .filter(point => Number.isFinite(point.gap))
      .sort((a, b) => a.pair.score - b.pair.score || a.gap - b.gap)
    if (!points.length) {
      container.replaceChildren()
      return 0
    }

    const annotations = new Map(Object.entries(examples).map(([id, example], index) =>
      [id, {tone: example.tone, number: index + 1}]))
    const title = htmlElement('h2', 'pair-scatter-title', 'Name similarity and turn-angle difference')
    const frame = htmlElement('div', 'pair-scatter-frame')
    const plot = svgElement('svg', {
      class: 'pair-scatter-svg',
      role: 'group',
      'aria-label': 'Action pair scatter plot. Use the arrow keys to move between pairs and Enter to open a pair.',
    })
    const grid = svgElement('g', {class: 'pair-scatter-grid', 'aria-hidden': 'true'})
    const marks = svgElement('g')
    const highlight = svgElement('circle', {r: 5, class: 'pair-scatter-highlight', 'aria-hidden': 'true'})
    highlight.setAttribute('visibility', 'hidden')
    const tooltip = htmlElement('div', 'pair-scatter-tooltip')
    tooltip.setAttribute('aria-hidden', 'true')
    tooltip.hidden = true
    plot.append(grid, marks, highlight)
    frame.append(plot, tooltip)
    const card = htmlElement('section', 'pair-scatter-card')
    card.append(title, frame)
    container.replaceChildren(card)

    let focusedPoint = null
    let hoveredPoint = null
    let activePoint = null
    let tabStop = null
    let frameWidth = 0
    let frameHeight = 0

    function positionTooltip(point) {
      const {offsetWidth, offsetHeight} = tooltip
      const left = Math.min(frameWidth - offsetWidth - 4, Math.max(4, point.x - offsetWidth / 2))
      const top = point.y - offsetHeight - 10
      const below = Math.min(frameHeight - offsetHeight - 4, point.y + 10)
      tooltip.style.left = left + 'px'
      tooltip.style.top = (top >= 0 ? top : below) + 'px'
      highlight.setAttribute('cx', point.x)
      highlight.setAttribute('cy', point.y)
      highlight.setAttribute('data-annotation', point.link.dataset.annotation || '')
    }

    function showPreview() {
      const point = hoveredPoint || focusedPoint
      if (activePoint === point) return
      activePoint = point
      tooltip.hidden = !point
      highlight.setAttribute('visibility', point ? 'visible' : 'hidden')
      if (!point) return
      tooltip.replaceChildren(...point.info.actions.map(action => htmlElement('div', 'pair-scatter-action', action)),
        htmlElement('div', 'pair-scatter-values', point.info.values))
      positionTooltip(point)
    }

    function setTabStop(point) {
      tabStop?.link.setAttribute('tabindex', '-1')
      tabStop = point
      tabStop.link.setAttribute('tabindex', '0')
    }

    const annotatedLinks = []
    points.forEach((point, index) => {
      const {pair} = point
      point.info = labelPoint(pair, point.gap)
      point.link = svgElement('a', {
        class: 'pair-scatter-point',
        href: '../index.html#action-pair=' + pair.id,
        tabindex: '-1',
        'aria-label': point.info.label,
      })
      point.hit = svgElement('polygon', {class: 'pair-scatter-hit', 'aria-hidden': 'true'})
      const dot = svgElement('circle', {r: 4, class: 'pair-scatter-dot', 'aria-hidden': 'true'})
      point.link.appendChild(point.hit)
      const annotation = annotations.get(pair.id)
      if (annotation) addAnnotation(point, annotation)
      point.link.appendChild(dot)
      point.link.addEventListener('pointerenter', event => {
        if (event.pointerType === 'touch') return
        hoveredPoint = point
        showPreview()
      })
      point.link.addEventListener('pointerleave', () => {
        if (hoveredPoint === point) hoveredPoint = null
        showPreview()
      })
      point.link.addEventListener('focus', () => {
        focusedPoint = point
        hoveredPoint = null
        setTabStop(point)
        showPreview()
      })
      point.link.addEventListener('blur', () => {
        if (focusedPoint === point) focusedPoint = null
        showPreview()
      })
      point.link.addEventListener('keydown', event => {
        let nextIndex
        switch (event.key) {
          case 'ArrowLeft':
          case 'ArrowUp': nextIndex = Math.max(0, index - 1); break
          case 'ArrowRight':
          case 'ArrowDown': nextIndex = Math.min(points.length - 1, index + 1); break
          case 'Home': nextIndex = 0; break
          case 'End': nextIndex = points.length - 1; break
          case 'Escape':
            hoveredPoint = null
            focusedPoint = null
            showPreview()
            return
          default: return
        }
        event.preventDefault()
        points[nextIndex].link.focus({preventScroll: true})
      })
      if (annotation) annotatedLinks.push(point.link)
      else marks.appendChild(point.link)
    })
    marks.append(...annotatedLinks)
    setTabStop(points[0])

    function layout() {
      const width = frame.clientWidth
      if (!width || width === frameWidth) return
      frameWidth = width
      frameHeight = Math.max(290, Math.min(430, Math.round(width * .44)))
      plot.setAttribute('viewBox', '0 0 ' + width + ' ' + frameHeight)
      const left = annotatedLinks.length ? 53 : 45
      const right = width - 16
      const top = 38
      const bottom = frameHeight - 52
      const xAt = value => left + (value - minScore) / (maxScore - minScore) * (right - left)
      const yAt = value => bottom - (value / maxGap) * (bottom - top)

      grid.replaceChildren(
        svgElement('text', {x: left, y: 18, class: 'pair-scatter-axis-title'}, 'Angle change gap (°)'),
        svgElement('text', {x: (left + right) / 2, y: frameHeight - 10, class: 'pair-scatter-axis-title', 'text-anchor': 'middle'},
          'Action-name similarity (cosine)')
      )
      const tickPositions = []
      for (let tick = 0; tick <= maxGap; tick += width < 460 ? 30 : 15) {
        const y = yAt(tick)
        tickPositions.push(y)
        grid.append(
          svgElement('line', {x1: left, x2: right, y1: y, y2: y, class: tick === 0 ? 'pair-scatter-baseline' : ''}),
          svgElement('text', {x: left - 9, y: y + 4, 'text-anchor': 'end'}, tick)
        )
      }
      const step = width < 620 ? 10 : 5
      for (let tick = 50; tick <= 100; tick += step) {
        const value = tick / 100
        const x = xAt(value)
        grid.append(
          svgElement('line', {x1: x, x2: x, y1: top, y2: bottom}),
          svgElement('text', {x, y: bottom + 21, 'text-anchor': 'middle'}, value.toFixed(2))
        )
      }
      points.forEach(point => {
        point.x = xAt(point.pair.score)
        point.y = yAt(point.gap)
        point.link.setAttribute('transform', 'translate(' + point.x + ',' + point.y + ')')
      })
      points.forEach(point => point.hit.setAttribute('points', nearestHitArea(point, points)))
      layoutAnnotations(points, {left, right, top, bottom, tickPositions})
      if (activePoint) positionTooltip(activePoint)
    }

    layout()
    const observer = new ResizeObserver(layout)
    observer.observe(frame)
    layouts.set(container, observer)
    return points.length
  }
})()
