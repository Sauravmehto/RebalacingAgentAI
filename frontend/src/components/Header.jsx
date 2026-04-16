import { useState, useEffect } from 'react'

function ReturnBadge({ value }) {
  if (value === undefined || value === null) return null
  const positive = value >= 0
  return (
    <span className={`badge text-sm px-3 py-1 ${
      positive
        ? 'bg-green-500/20 text-green-400 border-green-500/40'
        : 'bg-red-500/20 text-red-400 border-red-500/40'
    }`}>
      {positive ? '▲' : '▼'} {Math.abs(value).toFixed(2)}%
    </span>
  )
}

function SentimentDot({ sentiment }) {
  const map = {
    'Strong Positive': 'bg-green-400',
    'Positive':        'bg-green-500',
    'Neutral':         'bg-yellow-400',
    'Negative':        'bg-red-400',
    'Strong Negative': 'bg-red-600',
  }
  return (
    <span className="flex items-center gap-1.5 text-sm text-gray-400">
      <span className={`w-2 h-2 rounded-full ${map[sentiment] ?? 'bg-gray-500'}`} />
      {sentiment ?? 'Unknown'}
    </span>
  )
}

export default function Header({ portfolioReturn, marketSentiment }) {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 60_000)
    return () => clearInterval(id)
  }, [])

  return (
    <header className="sticky top-0 z-30 bg-gray-950/90 backdrop-blur-sm border-b border-gray-800">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between gap-4">
        {/* Logo + title */}
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex-shrink-0 w-9 h-9 bg-cyan-500/20 rounded-lg border border-cyan-500/40 flex items-center justify-center">
            <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5 text-cyan-400">
              <path d="M3 14L7 8l4 6 3-4 4 6" stroke="currentColor" strokeWidth="1.8"
                    strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div className="min-w-0">
            <h1 className="text-lg font-bold text-white leading-tight truncate">
              Nexus AI <span className="text-cyan-400">v2</span>
            </h1>
            <p className="text-xs text-gray-500 truncate hidden sm:block">
              Intelligent Portfolio Manager
            </p>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {marketSentiment && <SentimentDot sentiment={marketSentiment} />}
          {portfolioReturn !== undefined && <ReturnBadge value={portfolioReturn} />}
          <div className="hidden md:block text-xs text-gray-600 border-l border-gray-800 pl-3">
            {time.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
            &nbsp;
            {time.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    </header>
  )
}
