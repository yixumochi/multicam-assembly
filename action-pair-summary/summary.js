(() => {
  'use strict'

  const angleStages = ['Start → Middle', 'Middle → End']
  const bothStages = 'Both stages'
  const scopeFilter = document.querySelector('#scope')
  const caseFilter = document.querySelector('#case')
  const search = document.querySelector('#search')
  const status = document.querySelector('#status')
  const scrollHint = document.querySelector('.summary-scroll-hint')
  const grid = document.querySelector('.summary-grid')
  const results = document.querySelector('#results')
  const download = document.querySelector('#download')
  const sortButtons = [...document.querySelectorAll('[data-sort]')]
  const tabs = [...document.querySelectorAll('.summary-view-tabs [role="tab"]')]
  const scatter = document.querySelector('#pair-scatter')
  const scatterNotes = document.querySelector('#scatter-notes')
  let ready = false
  let activeView = 'table'
  let pairs = []
  let displayed = []
  let sortKey = 'score'
  let ascending = false

  function gap(pair) {
    const [a, b] = pair.stages.map(stage => stage.net)
    return a === null || b === null ? null : Number(Math.abs(Math.abs(a) - Math.abs(b)).toFixed(1))
  }

  function largest(stage) {
    if (stage.angles.includes(null)) return null
    const [first, second] = stage.angles.map(angle => Number(Math.abs(angle).toFixed(1)))
    if (first === second) return bothStages
    return angleStages[Number(second > first)]
  }

  function signed(value) {
    if (value === null) return '—'
    const degrees = Math.abs(value).toFixed(1)
    const sign = Number(degrees) === 0 ? '' : value > 0 ? '+' : '−'
    return sign + degrees + '°'
  }

  function node(tag, className, text) {
    const item = document.createElement(tag)
    if (className) item.className = className
    if (text !== undefined) item.textContent = text
    return item
  }

  function appendReadings(row, pair, readings) {
    const cell = row.insertCell()
    readings.forEach((reading, side) => {
      const line = node('span', 'summary-reading summary-side-' + (side === 0 ? 'a' : 'b'))
      line.append(node('span', 'summary-side-mark', pair.cases[side]),
        node('span', reading === '—' ? 'summary-empty' : '', reading))
      cell.appendChild(line)
    })
  }

  function showPair(pair) {
    const row = document.createElement('tr')
    const link = node('a', 'summary-pair')
    link.href = '../index.html#action-pair=' + pair.id
    row.dataset.href = link.href
    pair.names.forEach((name, side) => {
      const action = node('span', 'summary-action summary-side-' + (side === 0 ? 'a' : 'b'))
      action.append(node('span', 'summary-case', pair.cases[side]), node('span', '', name))
      link.appendChild(action)
    })
    row.insertCell().appendChild(link)
    const score = row.insertCell()
    score.className = 'summary-number'
    score.textContent = pair.score.toFixed(3)
    appendReadings(row, pair, pair.stages.map(stage => signed(stage.net)))
    appendReadings(row, pair, pair.stages.map(stage => largest(stage) ?? '—'))
    const difference = row.insertCell()
    const value = gap(pair)
    difference.className = value === null ? 'summary-empty' : 'summary-number'
    difference.textContent = value === null ? '—' : value.toFixed(1) + '°'
    return row
  }

  function comparePairs(a, b) {
    const first = sortKey === 'score' ? a.score : gap(a)
    const second = sortKey === 'score' ? b.score : gap(b)
    if (first === null) return second === null ? 0 : 1
    if (second === null) return -1
    return (ascending ? first - second : second - first) || b.score - a.score
  }

  function selectView(view) {
    activeView = view
    for (const tab of tabs) {
      const selected = tab.id === 'tab-' + view
      tab.setAttribute('aria-selected', String(selected))
      tab.tabIndex = selected ? 0 : -1
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected
    }
    if (ready) render()
  }

  function openView(tab) {
    const view = tab.id === 'tab-scatter' ? 'scatter' : 'table'
    const url = new URL(window.location.href)
    url.hash = view === 'scatter' ? 'scatter' : ''
    history.replaceState(history.state, '', url)
    selectView(view)
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => openView(tab))
    tab.addEventListener('keydown', event => {
      const next = {ArrowLeft: (index + tabs.length - 1) % tabs.length, ArrowRight: (index + 1) % tabs.length,
        Home: 0, End: tabs.length - 1}[event.key]
      if (next === undefined) return
      event.preventDefault()
      openView(tabs[next])
      tabs[next].focus()
    })
  })
  function viewFromHash() {
    selectView(window.location.hash === '#scatter' ? 'scatter' : 'table')
  }
  window.addEventListener('hashchange', viewFromHash)
  viewFromHash()

  function render() {
    const criteria = search.value.trim().toLowerCase().split(/\s+/).filter(Boolean)
    const drawingCase = caseFilter.value
    const scope = scopeFilter.value
    displayed = pairs.filter(pair => {
      if (scope !== 'all' && pair.shared !== (scope === 'same')) return false
      if (drawingCase && !pair.cases.includes(drawingCase)) return false
      const target = [...pair.cases, ...pair.names].join(' ').toLowerCase()
      return criteria.every(word => target.includes(word))
    }).sort(comparePairs)
    const count = displayed.length
    download.disabled = count === 0
    if (activeView === 'scatter') {
      renderScatter(count)
      return
    }
    status.textContent = count ? count + (count === 1 ? ' action pair' : ' action pairs') + ' · cosine ≥ 0.50' : 'No action pairs match these filters.'
    grid.hidden = count === 0
    scrollHint.hidden = count === 0
    results.replaceChildren(...displayed.map(showPair))
    sortButtons.forEach(button => {
      const header = button.closest('th')
      const active = button.dataset.sort === sortKey
      if (active) header.setAttribute('aria-sort', ascending ? 'ascending' : 'descending')
      else header.removeAttribute('aria-sort')
      button.lastElementChild.textContent = active ? (ascending ? '↑' : '↓') : '↕'
    })
  }

  function renderScatter(total) {
    const count = window.renderActionPairScatter(scatter, displayed, gap)
    scatterNotes.hidden = count === 0
    if (!total) {
      status.textContent = 'No action pairs match these filters.'
      return
    }
    status.textContent = count + ' of ' + total + (total === 1 ? ' pair plotted' : ' pairs plotted') +
      (count < total ? ' · ' + (total - count) + ' missing a start or end angle' : '')
  }

  const columns = [
    'Drawing case A', 'Action name A', 'Drawing case B', 'Action name B', 'Name cosine', 'Shares a case',
    'A start-to-end angle (deg)', 'B start-to-end angle (deg)', 'Angle change gap (deg)',
    'A largest angle stage', 'B largest angle stage',
    'A start-to-middle angle (deg)', 'A middle-to-end angle (deg)',
    'B start-to-middle angle (deg)', 'B middle-to-end angle (deg)',
    'A start-to-middle grip displacement (d/H)', 'A middle-to-end grip displacement (d/H)',
    'B start-to-middle grip displacement (d/H)', 'B middle-to-end grip displacement (d/H)',
  ]

  function round(value, digits) {
    return value === null ? '' : Number(value.toFixed(digits))
  }

  function csvRow(pair) {
    const [a, b] = pair.stages
    return [
      pair.cases[0], pair.names[0], pair.cases[1], pair.names[1], pair.score, pair.shared ? 'Yes' : 'No',
      round(a.net, 1), round(b.net, 1), gap(pair),
      largest(a), largest(b),
      ...pair.stages.flatMap(stage => stage.angles.map(angle => round(angle, 1))),
      ...pair.stages.flatMap(stage => stage.shifts.map(shift => round(shift, 2))),
    ]
  }

  function csvCell(value) {
    if (value === null) return ''
    if (typeof value === 'number') return String(value)
    // Preserve any formula-like label as text in spreadsheet applications.
    const literal = /^\s*[=+@-]/.test(value) ? "'" + value : value
    return '"' + literal.replaceAll('"', '""') + '"'
  }

  download.addEventListener('click', () => {
    const csv = [columns, ...displayed.map(csvRow)].map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n'
    const url = URL.createObjectURL(new Blob(['\ufeff', csv], {type: 'text/csv;charset=utf-8'}))
    const link = node('a')
    link.href = url
    link.download = 'multicam-action-pairs.csv'
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  })

  results.addEventListener('click', event => {
    const target = event.target.closest('tr[data-href]')
    if (!target || event.target.closest('a') || !window.getSelection()?.isCollapsed) return
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return
    window.location.assign(target.dataset.href)
  })

  fetch('data.json')
    .then(response => {
      if (!response.ok) throw new Error('Action pair data unavailable')
      return response.json()
    })
    .then(data => {
      pairs = data.rows.filter(row => row.score >= .5)
      ready = true
      const cases = [...new Set(pairs.flatMap(pair => pair.cases))].sort()
      cases.forEach(id => caseFilter.add(new Option(id, id)))
      search.addEventListener('input', render)
      caseFilter.addEventListener('change', render)
      scopeFilter.addEventListener('change', render)
      sortButtons.forEach(button => button.addEventListener('click', () => {
        if (button.dataset.sort === sortKey) ascending = !ascending
        else {
          sortKey = button.dataset.sort
          ascending = sortKey === 'gap'
        }
        render()
      }))
      render()
    })
    .catch(error => {
      console.error(error)
      status.textContent = 'Could not load the action pairs. Reload the page to try again.'
    })
})()
