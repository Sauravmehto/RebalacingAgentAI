import { useEffect, useRef, useState } from 'react'
import { actionAnimationClass } from '../utils/actionAnimation.js'

function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0)
  const prev = useRef(0)
  useEffect(() => {
    if (target === undefined || target === null) return
    const start = prev.current
    const diff  = target - start
    const fps   = 60
    const frames = Math.round((duration / 1000) * fps)
    let i = 0
    const id = setInterval(() => {
      i++
      const progress = i / frames
      const ease = 1 - Math.pow(1 - progress, 3)
      setValue(start + diff * ease)
      if (i >= frames) { clearInterval(id); prev.current = target }
    }, 1000 / fps)
    return () => clearInterval(id)
  }, [target, duration])
  return value
}

function fmt(n, decimals = 2) {
  if (n === undefined || n === null) return '—'
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function sentimentColor(s) {
  if (!s) return 'text-gray-400'
  const l = s.toLowerCase()
  if (l.includes('strong positive')) return 'text-green-400'
  if (l.includes('positive'))        return 'text-green-400'
  if (l.includes('strong negative')) return 'text-red-500'
  if (l.includes('negative'))        return 'text-red-400'
  return 'text-yellow-400'
}

function riskColor(r) {
  if (!r) return 'text-gray-400'
  if (r === 'Low')    return 'text-green-400'
  if (r === 'Medium') return 'text-yellow-400'
  return 'text-red-400'
}

function StatCard({ label, value, subtext, icon, accent, animValue }) {
  return (
    <div className="card p-5 flex flex-col gap-3 animate-slide-up hover:border-gray-700 transition-colors">
      <div className="flex items-start justify-between">
        <span className="text-xs text-gray-500 font-medium uppercase tracking-wider">{label}</span>
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${accent ?? 'bg-gray-800'}`}>
          {icon}
        </div>
      </div>
      <div>
        <div className="text-2xl font-bold text-white leading-tight">{value}</div>
        {subtext && <div className="text-xs text-gray-500 mt-1">{subtext}</div>}
      </div>
    </div>
  )
}

export default function SummaryCards({ summary, marketSentiment }) {
  const invested = useCountUp(summary?.total_invested)
  const current  = useCountUp(summary?.current_value)
  const ret      = useCountUp(summary?.portfolio_return_pct)
  const cf       = summary?.capital_flows

  if (!summary) return null

  const retPositive = (summary.portfolio_return_pct ?? 0) >= 0

  const cards = [
    {
      label: 'Total Invested',
      value: `$${fmt(invested, 0)}`,
      subtext: `${summary.holdings_count} holdings`,
      accent: 'bg-blue-500/20',
      icon: (
        <svg className="w-4 h-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
        </svg>
      ),
    },
    {
      label: 'Current Value',
      value: `$${fmt(current, 0)}`,
      subtext: `vs $${fmt(summary.total_invested, 0)} invested`,
      accent: 'bg-cyan-500/20',
      icon: (
        <svg className="w-4 h-4 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
    {
      label: 'Portfolio Return',
      value: (
        <span className={retPositive ? 'text-green-400' : 'text-red-400'}>
          {retPositive ? '+' : ''}{fmt(ret)}%
        </span>
      ),
      subtext: retPositive ? 'Gain' : 'Loss',
      accent: retPositive ? 'bg-green-500/20' : 'bg-red-500/20',
      icon: (
        <svg className={`w-4 h-4 ${retPositive ? 'text-green-400' : 'text-red-400'}`}
             fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d={retPositive
                  ? "M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                  : "M13 17h8m0 0V9m0 8l-8-8-4 4-6-6"} />
        </svg>
      ),
    },
    {
      label: 'Market Sentiment',
      value: <span className={sentimentColor(marketSentiment)}>{marketSentiment ?? '—'}</span>,
      subtext: 'Overall market mood',
      accent: 'bg-purple-500/20',
      icon: (
        <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z" />
        </svg>
      ),
    },
    {
      label: 'Portfolio Risk',
      value: <span className={riskColor(summary.risk_level)}>{summary.risk_level ?? '—'}</span>,
      subtext: 'Based on sentiment & drawdowns',
      accent: 'bg-orange-500/20',
      icon: (
        <svg className="w-4 h-4 text-orange-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      ),
    },
    {
      label: 'Recommended Cash',
      value: `${summary.cash_allocation_pct ?? 10}%`,
      subtext: 'Suggested cash reserve',
      accent: 'bg-teal-500/20',
      icon: (
        <svg className="w-4 h-4 text-teal-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
    },
  ]

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-4">
        {cards.map(c => (
          <StatCard key={c.label} {...c} />
        ))}
      </div>

      {cf && (
        <div className="card p-5 border border-gray-800">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-1 h-4 bg-amber-500 rounded-full" />
            <h3 className="text-sm font-semibold text-white">Indicative capital flows</h3>
          </div>
          <p className="text-xs text-gray-600 mb-4">
            Heuristic only — not execution advice. {cf.assumptions}
          </p>
          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            <div>
              <p className="text-xs text-gray-500 uppercase">Est. sell proceeds</p>
              <p className="text-xl font-bold text-red-400 tabular-nums">
                ${fmt(cf.estimated_sell_proceeds_usd, 0)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase">Est. buy deployment</p>
              <p className="text-xl font-bold text-green-400 tabular-nums">
                ${fmt(cf.estimated_buy_deployment_usd, 0)}
              </p>
            </div>
          </div>
          {(cf.sell_candidates?.length > 0) && (
            <div>
              <p className="text-xs text-gray-500 uppercase mb-2">Suggested sales (priority)</p>
              <ul className="space-y-1.5 max-h-40 overflow-y-auto">
                {cf.sell_candidates.slice(0, 8).map((s) => (
                  <li
                    key={s.ticker}
                    className="flex justify-between gap-2 text-xs bg-red-500/5 border border-red-500/10 rounded px-2 py-1.5"
                  >
                    <span className="font-mono font-bold text-white">{s.ticker}</span>
                    <span
                      className={`text-orange-400 inline-block rounded px-1 ${actionAnimationClass(s.action)}`}
                    >
                      {s.action}
                    </span>
                    <span className="text-gray-400 tabular-nums">${fmt(s.estimated_trim_usd, 0)}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
