import { useState, useMemo } from 'react'
import { getDownloadCsvUrl } from '../services/api.js'
import { actionAnimationClass } from '../utils/actionAnimation.js'

// ── Action styling ────────────────────────────────────────────────────────────
const ACTION_STYLE = {
  'STRONG BUY':  'bg-green-500/25 text-green-300 border-green-500/40',
  'BUY':         'bg-green-500/15 text-green-400 border-green-600/30',
  'HOLD':        'bg-yellow-500/15 text-yellow-400 border-yellow-600/30',
  'REDUCE':      'bg-orange-500/15 text-orange-400 border-orange-600/30',
  'PARTIAL SELL':'bg-orange-500/20 text-orange-300 border-orange-500/40',
  'SELL':        'bg-red-500/15 text-red-400 border-red-600/30',
  'STRONG SELL': 'bg-red-500/25 text-red-300 border-red-500/40',
}

function ActionBadge({ action }) {
  const cls = ACTION_STYLE[action] ?? 'bg-gray-700 text-gray-300 border-gray-600'
  const motion = actionAnimationClass(action)
  return (
    <span className={`badge whitespace-nowrap font-bold rounded-full ${cls} ${motion}`}>
      {action}
    </span>
  )
}

function TrendIcon({ trend }) {
  if (trend === 'Uptrend')   return <span className="text-green-400 font-bold">↑</span>
  if (trend === 'Downtrend') return <span className="text-red-400 font-bold">↓</span>
  return <span className="text-gray-500">→</span>
}

function ConfidenceBadge({ confidence }) {
  const map = { HIGH: ['★★★', 'text-yellow-400'], MEDIUM: ['★★☆', 'text-yellow-500/70'], LOW: ['★☆☆', 'text-gray-600'] }
  const [stars, cls] = map[confidence] ?? ['★☆☆', 'text-gray-600']
  return <span className={`text-sm font-mono ${cls}`}>{stars}</span>
}

function ScoreBar({ score }) {
  const pct   = Math.min(100, Math.max(0, score))
  const color = pct >= 65 ? 'bg-green-500' : pct >= 40 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400 tabular-nums w-8">{score?.toFixed(0)}</span>
    </div>
  )
}

function ReturnCell({ value, estimated }) {
  if (value === undefined || value === null) return <span className="text-gray-600">—</span>
  const pos = value >= 0
  return (
    <span
      className={`tabular-nums font-medium ${pos ? 'text-green-400' : 'text-red-400'}`}
      title={estimated ? 'Return% may be reconstructed — add CSV buy price for trusted P&L' : undefined}
    >
      {estimated && <span className="text-amber-400/90 mr-0.5 select-none">~</span>}
      {pos ? '+' : ''}{value.toFixed(2)}%
    </span>
  )
}

function AllocationBadge({ status }) {
  const map = {
    Overweight:  'bg-red-500/15 text-red-400 border-red-600/30',
    Underweight: 'bg-blue-500/15 text-blue-400 border-blue-600/30',
    Neutral:     'bg-gray-700/50 text-gray-400 border-gray-600/30',
  }
  return <span className={`badge text-xs ${map[status] ?? map.Neutral}`}>{status}</span>
}

function SentimentBadge({ sentiment }) {
  const map = {
    'Strong Positive': 'text-green-400',
    'Positive':        'text-green-500',
    'Neutral':         'text-yellow-400',
    'Negative':        'text-red-400',
    'Strong Negative': 'text-red-500',
  }
  return <span className={`text-xs font-medium ${map[sentiment] ?? 'text-gray-400'}`}>{sentiment}</span>
}

// ── Main component ────────────────────────────────────────────────────────────
const SORT_KEYS = ['score', 'return_pct', 'current_price', 'symbol']

export default function PortfolioTable({ stocks }) {
  const [search,    setSearch]    = useState('')
  const [actionFilter, setAction] = useState('ALL')
  const [sectorFilter, setSector] = useState('ALL')
  const [sortKey,   setSortKey]   = useState('score')
  const [sortAsc,   setSortAsc]   = useState(false)

  const sectors = useMemo(() => {
    const set = new Set(stocks.map(s => s.sector).filter(Boolean))
    return ['ALL', ...Array.from(set).sort()]
  }, [stocks])

  const actions = ['ALL', 'STRONG BUY', 'BUY', 'HOLD', 'REDUCE', 'PARTIAL SELL', 'SELL', 'STRONG SELL']

  const filtered = useMemo(() => {
    let rows = [...stocks]
    if (search) {
      const q = search.toUpperCase()
      rows = rows.filter(s => s.symbol?.toUpperCase().includes(q) || s.sector?.toUpperCase().includes(q))
    }
    if (actionFilter !== 'ALL') rows = rows.filter(s => s.action === actionFilter)
    if (sectorFilter !== 'ALL') rows = rows.filter(s => s.sector === sectorFilter)

    rows.sort((a, b) => {
      const av = a[sortKey] ?? 0
      const bv = b[sortKey] ?? 0
      const cmp = typeof av === 'string' ? av.localeCompare(bv) : av - bv
      return sortAsc ? cmp : -cmp
    })
    return rows
  }, [stocks, search, actionFilter, sectorFilter, sortKey, sortAsc])

  function toggleSort(key) {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  function SortTh({ label, sortable, colKey, className = '' }) {
    const active = sortKey === colKey
    return (
      <th
        onClick={() => sortable && toggleSort(colKey)}
        className={`px-3 py-3 text-left text-xs font-semibold text-gray-400 uppercase tracking-wider
          whitespace-nowrap ${sortable ? 'cursor-pointer hover:text-gray-200 select-none' : ''} ${className}`}
      >
        <span className="flex items-center gap-1">
          {label}
          {sortable && (
            <span className={active ? 'text-cyan-400' : 'text-gray-700'}>
              {active ? (sortAsc ? '↑' : '↓') : '↕'}
            </span>
          )}
        </span>
      </th>
    )
  }

  return (
    <section className="card animate-fade-in">
      {/* Toolbar */}
      <div className="p-4 border-b border-gray-800 flex flex-wrap gap-3 items-center">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <div className="w-1 h-5 bg-cyan-500 rounded-full flex-shrink-0" />
          <h2 className="text-base font-semibold text-white flex-shrink-0">Portfolio Holdings</h2>
          <span className="text-xs text-gray-600 ml-1">({filtered.length} of {stocks.length})</span>
        </div>

        <div className="flex flex-wrap gap-2 items-center">
          {/* Search */}
          <input
            type="text"
            placeholder="Search ticker…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field w-36"
          />

          {/* Action filter */}
          <select
            value={actionFilter}
            onChange={e => setAction(e.target.value)}
            className="input-field"
          >
            {actions.map(a => <option key={a} value={a}>{a === 'ALL' ? 'All Actions' : a}</option>)}
          </select>

          {/* Sector filter */}
          <select
            value={sectorFilter}
            onChange={e => setSector(e.target.value)}
            className="input-field"
          >
            {sectors.map(s => <option key={s} value={s}>{s === 'ALL' ? 'All Sectors' : s}</option>)}
          </select>

          {/* CSV download */}
          <a
            href={getDownloadCsvUrl()}
            download="Nexus_AI_Portfolio_With_Live_Prices.csv"
            className="btn-secondary text-sm flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            CSV
          </a>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-900/80">
            <tr>
              <SortTh label="Ticker"     sortable colKey="symbol"       />
              <SortTh label="Sector"     sortable={false}               />
              <SortTh label="Buy $"      sortable={false}               />
              <SortTh label="Cur $"      sortable colKey="current_price"/>
              <SortTh label="Return"     sortable colKey="return_pct"   />
              <SortTh label="Sentiment"  sortable={false}               />
              <SortTh label="Trend"      sortable={false}               />
              <SortTh label="Allocation" sortable={false}               />
              <SortTh label="Score"      sortable colKey="score"        />
              <SortTh label="Confidence" sortable={false}               />
              <SortTh label="Action"     sortable={false}               />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {filtered.map((s, i) => (
              <tr key={s.symbol ?? i}
                  className={`hover:bg-gray-800/40 transition-colors group ${
                    s.priority_sell ? 'bg-red-950/25 ring-1 ring-inset ring-red-500/20' : ''
                  }`}>
                <td className="px-3 py-3 font-mono font-bold text-white">
                  {s.symbol}
                </td>
                <td className="px-3 py-3 text-gray-400 text-xs max-w-[120px] truncate">
                  {s.sector}
                </td>
                <td className="px-3 py-3 tabular-nums text-gray-400">
                  {s.buy_price ? `$${s.buy_price.toFixed(2)}` : '—'}
                </td>
                <td className="px-3 py-3 tabular-nums text-white font-medium">
                  {s.current_price ? `$${s.current_price.toFixed(2)}` : '—'}
                </td>
                <td className="px-3 py-3">
                  <ReturnCell value={s.return_pct} estimated={s.return_pct_is_estimated} />
                </td>
                <td className="px-3 py-3">
                  <SentimentBadge sentiment={s.sentiment} />
                </td>
                <td className="px-3 py-3">
                  <div className="flex items-center gap-1.5">
                    <TrendIcon trend={s.trend} />
                    <span className="text-xs text-gray-500">{s.trend}</span>
                  </div>
                </td>
                <td className="px-3 py-3">
                  <AllocationBadge status={s.allocation_status} />
                </td>
                <td className="px-3 py-3">
                  <ScoreBar score={s.score} />
                </td>
                <td className="px-3 py-3">
                  <ConfidenceBadge confidence={s.confidence} />
                </td>
                <td className="px-3 py-3">
                  <ActionBadge action={s.action} />
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={11} className="px-4 py-10 text-center text-gray-600 text-sm">
                  No holdings match the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
