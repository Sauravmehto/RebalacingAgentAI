import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
} from 'recharts'

const PALETTE = [
  '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899',
  '#f97316', '#eab308', '#22c55e', '#14b8a6',
  '#f43f5e', '#a78bfa',
]

function sentimentColor(s) {
  if (!s) return 'text-gray-400'
  const l = s.toLowerCase()
  if (l.includes('strong positive')) return 'text-green-400'
  if (l.includes('positive'))        return 'text-green-400'
  if (l.includes('strong negative')) return 'text-red-500'
  if (l.includes('negative'))        return 'text-red-400'
  return 'text-yellow-400'
}

function allocationStatusColor(status) {
  if (status === 'Overweight')  return 'text-red-400 bg-red-500/10 border-red-500/30'
  if (status === 'Underweight') return 'text-blue-400 bg-blue-500/10 border-blue-500/30'
  return 'text-gray-400 bg-gray-700/30 border-gray-600/30'
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">{d.name}</p>
      <p className="text-cyan-400">Allocation: {d.value?.toFixed(1)}%</p>
    </div>
  )
}

function BarTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 shadow-xl text-xs">
      <p className="font-semibold text-white mb-1">{label}</p>
      {payload.map(p => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {p.value?.toFixed(1)}%
        </p>
      ))}
    </div>
  )
}

export default function SectorBreakdown({ sectorBreakdown, currentAllocation, targetAllocation }) {
  if (!sectorBreakdown || Object.keys(sectorBreakdown).length === 0) return null

  const sectors = Object.entries(sectorBreakdown)

  // Pie chart data
  const pieData = sectors.map(([name, info], i) => ({
    name,
    value: info.allocation_pct ?? 0,
    color: PALETTE[i % PALETTE.length],
  }))

  // Bar chart data — current vs target
  const barData = sectors.map(([name, info]) => {
    const shortName = name.length > 14 ? name.slice(0, 12) + '…' : name
    const target    = targetAllocation?.[name] ?? targetAllocation?.Others ?? 20
    return {
      name:    shortName,
      current: parseFloat((info.allocation_pct ?? 0).toFixed(1)),
      target:  parseFloat(target.toFixed(1)),
    }
  })

  // Allocation status per sector
  function getStatus(name, current) {
    const target = targetAllocation?.[name] ?? targetAllocation?.Others ?? 20
    const diff   = current - target
    if (diff > 5)  return 'Overweight'
    if (diff < -5) return 'Underweight'
    return 'Neutral'
  }

  return (
    <section className="card p-6 animate-fade-in">
      <div className="flex items-center gap-2 mb-6">
        <div className="w-1 h-5 bg-cyan-500 rounded-full" />
        <h2 className="text-base font-semibold text-white">Sector Breakdown</h2>
      </div>

      <div className="grid lg:grid-cols-2 gap-8">
        {/* Pie chart */}
        <div>
          <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-4 font-medium">
            Current Allocation
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={65}
                outerRadius={100}
                paddingAngle={2}
                dataKey="value"
              >
                {pieData.map((entry, i) => (
                  <Cell key={entry.name} fill={entry.color} stroke="transparent" />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend
                formatter={(value) => (
                  <span className="text-xs text-gray-400">{value}</span>
                )}
                iconSize={8}
                wrapperStyle={{ fontSize: '11px' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Bar chart — current vs target */}
        <div>
          <h3 className="text-xs text-gray-500 uppercase tracking-wider mb-4 font-medium">
            Current vs Target Allocation
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={barData} layout="vertical" barSize={10} barGap={2}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" horizontal={false} />
              <XAxis
                type="number"
                domain={[0, 'auto']}
                tick={{ fill: '#6b7280', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={v => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={90}
                tick={{ fill: '#9ca3af', fontSize: 11 }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip content={<BarTooltip />} />
              <Bar dataKey="current" name="Current" fill="#06b6d4" radius={[0, 4, 4, 0]} />
              <Bar dataKey="target"  name="Target"  fill="#374151" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Sector cards grid */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {sectors.map(([name, info], i) => {
          const status  = getStatus(name, info.allocation_pct ?? 0)
          const statusCls = allocationStatusColor(status)
          const retPos  = (info.avg_return_pct ?? 0) >= 0
          return (
            <div key={name}
                 className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4
                            hover:border-gray-600 transition-colors">
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-3 h-3 rounded-full flex-shrink-0"
                       style={{ backgroundColor: PALETTE[i % PALETTE.length] }} />
                  <span className="text-sm font-semibold text-white truncate">{name}</span>
                </div>
                <span className={`badge text-xs flex-shrink-0 border ${statusCls}`}>
                  {status}
                </span>
              </div>

              {(() => {
                const tgt = targetAllocation?.[name] ?? targetAllocation?.Others ?? 20
                const cur = info.allocation_pct ?? 0
                const delta = cur - tgt
                const arrow = delta > 0.5 ? '↑' : delta < -0.5 ? '↓' : '→'
                const arrowCls =
                  delta > 0.5 ? 'text-red-400' : delta < -0.5 ? 'text-blue-400' : 'text-gray-500'
                return (
                  <p className="text-xs text-gray-500 mb-3 flex flex-wrap items-center gap-1.5">
                    <span className="tabular-nums text-white font-medium">{cur.toFixed(1)}%</span>
                    <span className={`font-bold ${arrowCls}`} title="Current vs target allocation">{arrow}</span>
                    <span className="text-gray-500">target</span>
                    <span className="tabular-nums text-gray-400">{tgt.toFixed(0)}%</span>
                    <span
                      className={`tabular-nums ${
                        delta > 0.1 ? 'text-red-300/90' : delta < -0.1 ? 'text-blue-300/90' : 'text-gray-600'
                      }`}
                    >
                      (Δ {delta >= 0 ? '+' : ''}{delta.toFixed(1)}%)
                    </span>
                  </p>
                )
              })()}

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <p className="text-gray-600 mb-0.5">Allocation</p>
                  <p className="text-white font-medium tabular-nums">
                    {(info.allocation_pct ?? 0).toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-gray-600 mb-0.5">Value</p>
                  <p className="text-white font-medium tabular-nums">
                    ${(info.current_value ?? 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                  </p>
                </div>
                <div>
                  <p className="text-gray-600 mb-0.5">Avg Return</p>
                  <p className={`font-medium tabular-nums ${retPos ? 'text-green-400' : 'text-red-400'}`}>
                    {retPos ? '+' : ''}{(info.avg_return_pct ?? 0).toFixed(2)}%
                  </p>
                </div>
                <div>
                  <p className="text-gray-600 mb-0.5">Sentiment</p>
                  <p className={`font-medium ${sentimentColor(info.sentiment)}`}>
                    {info.sentiment ?? '—'}
                  </p>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
