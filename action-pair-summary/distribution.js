(() => {
  'use strict'

  const cosineBands = [
    {label: '0.50–<0.60', max: 0.60},
    {label: '0.60–<0.70', max: 0.70},
    {label: '0.70–1.00', max: Infinity},
  ]
  const gapLabels = ['<10°', '10–<30°', '≥30°']
  const binSize = 10
  const binCount = 9
  const percent = (count, total) => total ? Math.round(count * 100 / total) + '%' : ''

  function node(tag, className, text) {
    const element = document.createElement(tag)
    if (className) element.className = className
    if (text !== undefined) element.textContent = text
    return element
  }

  function summarize(pairs, getGap) {
    const bands = cosineBands.map(band => ({label: band.label, counts: [0, 0, 0], total: 0}))
    const histogram = Array(binCount).fill(0)
    const gaps = []
    for (const pair of pairs) {
      const gap = getGap(pair)
      if (!Number.isFinite(gap)) continue
      const band = bands[cosineBands.findIndex(entry => pair.score < entry.max)]
      const category = gap < 10 ? 0 : gap < 30 ? 1 : 2
      band.counts[category]++
      band.total++
      histogram[Math.min(binCount - 1, Math.floor(gap / binSize))]++
      gaps.push(gap)
    }
    gaps.sort((a, b) => a - b)
    const midpoint = Math.floor(gaps.length / 2)
    const median = gaps.length % 2 ? gaps[midpoint] : (gaps[midpoint - 1] + gaps[midpoint]) / 2
    return {bands, histogram, sampleSize: gaps.length, median, maximum: gaps.at(-1)}
  }

  function histogramFigure(summary, defaultView) {
    const {histogram, sampleSize, median, maximum} = summary
    const figure = node('figure', 'gap-histogram')
    const heading = node('h2', '', 'Distribution of angle gaps')
    const scale = node('div', 'gap-histogram-y', 'Pair count')
    const graph = node('div', 'gap-histogram-plot')
    const axis = node('div', 'gap-histogram-x')
    graph.setAttribute('role', 'img')
    graph.setAttribute('aria-label', histogram.map((count, index) => {
      const start = index * binSize
      const end = start + binSize
      const range = index === binCount - 1 ? start + ' through ' + end : start + ' to under ' + end
      return range + ' degrees: ' + count + (count === 1 ? ' pair' : ' pairs')
    }).join('. '))
    axis.setAttribute('aria-hidden', 'true')

    const maxCount = Math.max(...histogram)
    const roughStep = maxCount / 4
    const magnitude = 10 ** Math.floor(Math.log10(Math.max(1, roughStep)))
    const step = [1, 2, 2.5, 5, 10].map(number => Math.ceil(number * magnitude))
      .find(number => number >= roughStep)
    const upper = Math.ceil(maxCount / step) * step
    for (let tick = 0; tick <= upper; tick += step) {
      const line = node('div', 'gap-histogram-tick')
      line.style.bottom = 100 * tick / upper + '%'
      line.appendChild(node('span', '', String(tick)))
      graph.appendChild(line)
    }

    const bars = node('div', 'gap-histogram-bars')
    for (const [index, count] of histogram.entries()) {
      const bar = node('div', 'gap-histogram-bar gap-range-' + (index === 0 ? '0' : index <= 2 ? '1' : '2'))
      bar.style.height = 100 * count / upper + '%'
      if (count) bar.appendChild(node('span', '', String(count)))
      bars.appendChild(bar)
    }
    graph.appendChild(bars)
    for (let index = 0; index <= binCount; index++) {
      const label = node('span', '', String(index * binSize))
      label.style.left = 100 * index / binCount + '%'
      axis.appendChild(label)
    }
    const caption = node('figcaption', 'gap-distribution-note')
    caption.textContent = histogram[0] + ' of ' + sampleSize + ' plotted pairs (' +
      percent(histogram[0], sampleSize) + ') have a gap below 10°. Median ' +
      median.toFixed(1) + '° · largest ' + maximum.toFixed(1) + '°.'
    if (defaultView) caption.append(' Gaps cluster near zero with a long right tail.')
    figure.append(heading, scale, graph, axis, node('div', 'gap-histogram-label', 'Angle change gap (°)'), caption)
    return figure
  }

  function downloadBands(summary, matchedCount) {
    const headers = [
      'Cosine band', 'Filtered pair count', 'Filtered pairs with measured gaps', 'Pairs in band',
      'Gap below 10 deg count', 'Gap below 10 deg percent', 'Gap 10 to below 30 deg count',
      'Gap 10 to below 30 deg percent', 'Gap at least 30 deg count', 'Gap at least 30 deg percent',
    ]
    const rows = summary.bands.map(band => [
      band.label, matchedCount, summary.sampleSize, band.total,
      ...band.counts.flatMap(count => [count, band.total ? (count * 100 / band.total).toFixed(2) : '']),
    ])
    const csv = [headers, ...rows].map(row => row.join(',')).join('\r\n')
    const href = URL.createObjectURL(new Blob(['\ufeff', csv], {type: 'text/csv;charset=utf-8'}))
    const link = node('a')
    link.href = href
    link.download = 'multicam-angle-gap-summary.csv'
    link.click()
    setTimeout(() => URL.revokeObjectURL(href), 1000)
  }

  function groupedTable(summary, matchedCount) {
    const panel = node('section', 'gap-band-panel')
    const title = node('h2', '', 'Angle gaps by cosine band')
    const table = node('table', 'gap-band-table')
    table.createCaption().className = 'screen-reader-only'
    table.caption.textContent = 'Counts and shares of pairs by cosine band and angle gap'
    const heading = table.createTHead().insertRow()
    for (const [index, text] of ['Cosine band', 'Pairs', ...gapLabels].entries()) {
      const cell = node('th', index < 2 ? '' : 'gap-range-' + (index - 2), text)
      cell.scope = 'col'
      heading.appendChild(cell)
    }
    const body = table.createTBody()
    for (const band of summary.bands) {
      const row = body.insertRow()
      const label = node('th', '', band.label)
      label.scope = 'row'
      row.appendChild(label)
      row.insertCell().textContent = band.total
      for (const count of band.counts) {
        const cell = row.insertCell()
        if (band.total) cell.append(node('span', 'gap-cell-count', String(count)), ' ',
          node('span', 'gap-cell-percent', '(' + percent(count, band.total) + ')'))
        else cell.textContent = '—'
      }
    }
    const notes = node('p', 'gap-distribution-note',
      'Shares are calculated within each cosine band for the plotted pairs. Percentages are rounded to whole numbers.')
    const download = node('button', 'gap-summary-download', 'Download grouped CSV')
    download.type = 'button'
    download.addEventListener('click', () => downloadBands(summary, matchedCount))
    panel.append(title, table)
    const highest = summary.bands.at(-1)
    if (highest.total) {
      const [small, , large] = highest.counts
      const pairs = highest.total === 1 ? ' plotted pair' : ' plotted pairs'
      const finding = 'For cosine 0.70 and above (' + highest.total + pairs + '), ' +
        small + ' (' + percent(small, highest.total) + ') are below 10° and ' +
        large + ' (' + percent(large, highest.total) + ') are at least 30°.'
      panel.appendChild(node('p', 'gap-band-finding', finding))
    }
    panel.append(notes, download)
    return panel
  }

  window.renderAngleGapDistribution = function renderAngleGapDistribution(container, pairs, getGap, defaultView) {
    const summary = summarize(pairs, getGap)
    container.hidden = summary.sampleSize === 0
    if (!summary.sampleSize) {
      container.replaceChildren()
      return summary
    }
    const section = node('div', 'gap-distribution')
    section.append(histogramFigure(summary, defaultView), groupedTable(summary, pairs.length))
    container.replaceChildren(section)
    return summary
  }
})()
