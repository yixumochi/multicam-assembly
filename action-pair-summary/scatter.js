(() => {
  'use strict'

  const svgNamespace = 'http://www.w3.org/2000/svg'
  const layouts = new WeakMap()
  const minScore = 0.5
  const maxScore = 1
  const maxGap = 90
  const hitRadius = 8
  const annotationTones = new Map([
    ['69:72', 'small-gap'],
    ['217:221', 'large-gap'],
  ])
  const annotationWidth = 146
  const annotationHeight = 39

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

  function addAnnotation(point, tone) {
    const {pair, gap, link} = point
    const group = svgElement('g', {class: 'pair-scatter-annotation', 'aria-hidden': 'true'})
    const leader = svgElement('line', {class: 'pair-scatter-annotation-leader', x1: 0, y1: 0})
    const label = svgElement('g', {class: 'pair-scatter-annotation-label'})
    label.append(
      svgElement('rect', {class: 'pair-scatter-annotation-box', width: annotationWidth, height: annotationHeight, rx: 5}),
      svgElement('line', {class: 'pair-scatter-annotation-stripe', x1: 5, y1: 7, x2: 5, y2: annotationHeight - 7}),
      svgElement('text', {class: 'pair-scatter-annotation-title', x: 13, y: 16}, pair.cases.join(' × ')),
      svgElement('text', {x: 13, y: 30}, pair.score.toFixed(3) + ' cosine · ' + gap.toFixed(1) + '° gap')
    )
    group.append(leader, label)
    link.dataset.annotation = tone
    link.appendChild(group)
    point.annotation = {leader, label}
  }

  function layoutAnnotations(points, left, right, top, bottom) {
    const placed = []
    const clamp = (value, min, max) => Math.max(min, Math.min(value, max))
    points.filter(point => point.annotation).forEach(point => {
      const {x, y, annotation} = point
      const offset = 14
      const leftChoices = [x + offset, x - annotationWidth - offset, x - annotationWidth / 2, right - annotationWidth]
      const topChoices = [y - annotationHeight / 2, y + offset, y - annotationHeight - offset,
        y + offset + 25, y - annotationHeight - offset - 25]
      let best
      for (const proposedX of leftChoices) {
        for (const proposedY of topChoices) {
          const boxX = clamp(proposedX, left + 3, right - annotationWidth - 3)
          const boxY = clamp(proposedY, top + 3, bottom - annotationHeight - 3)
          const endX = clamp(x, boxX, boxX + annotationWidth)
          const endY = clamp(y, boxY, boxY + annotationHeight)
          // Prefer short leaders while keeping labels away from dots and other labels.
          const covered = points.filter(dot =>
            dot.x >= boxX - hitRadius && dot.x <= boxX + annotationWidth + hitRadius &&
            dot.y >= boxY - hitRadius && dot.y <= boxY + annotationHeight + hitRadius).length
          const overlaps = placed.some(box =>
            Math.abs(box.x - boxX) < annotationWidth + 6 && Math.abs(box.y - boxY) < annotationHeight + 6)
          const cost = Math.abs(endX - x) + Math.abs(endY - y) + covered * 1000 + (overlaps ? 5000 : 0)
          if (!best || cost < best.cost) best = {cost, x: boxX, y: boxY, endX, endY}
        }
      }
      placed.push(best)
      annotation.label.setAttribute('transform', 'translate(' + (best.x - x) + ',' + (best.y - y) + ')')
      annotation.leader.setAttribute('x2', best.endX - x)
      annotation.leader.setAttribute('y2', best.endY - y)
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

  window.renderActionPairScatter = function renderActionPairScatter(container, pairs, getGap) {
    layouts.get(container)?.disconnect()
    layouts.delete(container)
    const points = pairs.map(pair => ({pair, gap: getGap(pair)}))
      .filter(point => Number.isFinite(point.gap))
      .sort((a, b) => a.pair.score - b.pair.score || a.gap - b.gap)
    if (!points.length) {
      container.replaceChildren()
      return 0
    }

    const title = htmlElement('h2', 'pair-scatter-title', 'Name similarity vs. angle change gap')
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
      const tone = annotationTones.get(pair.id)
      if (tone) addAnnotation(point, tone)
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
      marks.appendChild(point.link)
    })
    setTabStop(points[0])

    function layout() {
      const width = frame.clientWidth
      if (!width || width === frameWidth) return
      frameWidth = width
      frameHeight = Math.max(290, Math.min(430, Math.round(width * .44)))
      plot.setAttribute('viewBox', '0 0 ' + width + ' ' + frameHeight)
      const left = 45
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
      for (let tick = 0; tick <= maxGap; tick += width < 460 ? 30 : 15) {
        const y = yAt(tick)
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
      layoutAnnotations(points, left, right, top, bottom)
      if (activePoint) positionTooltip(activePoint)
    }

    layout()
    const observer = new ResizeObserver(layout)
    observer.observe(frame)
    layouts.set(container, observer)
    return points.length
  }
})()
