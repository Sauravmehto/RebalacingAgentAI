const MAX_HEADLINES = 20

/**
 * News-aware full pipeline: custom scenario + optional picks from /latest-news articles.
 */
export default function RebalanceModule({
  csvPath,
  loading,
  news,
  scenarioPrompt,
  onScenarioPromptChange,
  selectedHeadlines,
  onToggleHeadline,
  onClearScenario,
  onRun,
}) {
  const articles = news?.articles ?? []

  function toggle(title) {
    if (!title?.trim()) return
    const t = title.trim()
    onToggleHeadline(t)
  }

  return (
    <section className="card p-6 animate-fade-in">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-1 h-5 bg-cyan-500 rounded-full" />
        <h2 className="text-base font-semibold text-white">Rebalance Portfolio</h2>
      </div>
      <p className="text-sm text-gray-500 mb-4">
        Re-run the full AI pipeline (prices, trends, sentiment, scoring, recommendations).
        Add a scenario and/or pick headlines to bias sector sentiment and rebalancing decisions.
      </p>

      <label className="block text-xs font-medium text-gray-400 mb-2">Custom scenario / prompt</label>
      <textarea
        value={scenarioPrompt}
        onChange={e => onScenarioPromptChange(e.target.value)}
        placeholder='e.g. "Iran conflict", "Fed pivot", "market crash risk"'
        rows={3}
        className="w-full input-field mb-4 font-sans resize-y min-h-[80px]"
        disabled={loading}
      />

      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-gray-400">Select from latest news (optional)</span>
        <button
          type="button"
          onClick={onClearScenario}
          className="text-xs text-cyan-500 hover:text-cyan-400 disabled:opacity-40"
          disabled={loading || (!scenarioPrompt?.trim() && selectedHeadlines.length === 0)}
        >
          Clear prompt & selection
        </button>
      </div>

      <div className="max-h-56 overflow-y-auto rounded-lg border border-gray-800 bg-gray-900/50 p-3 space-y-2 mb-4">
        {articles.length === 0 && (
          <p className="text-xs text-gray-600">No articles yet — run an analysis first or refresh news.</p>
        )}
        {articles.slice(0, 40).map((a, i) => {
          const title = (a.title || '').trim()
          if (!title) return null
          const checked = selectedHeadlines.includes(title)
          return (
            <label
              key={`${i}-${title.slice(0, 40)}`}
              className={`flex items-start gap-2 p-2 rounded-lg cursor-pointer transition-colors ${
                checked ? 'bg-cyan-500/10 border border-cyan-500/30' : 'hover:bg-gray-800/60 border border-transparent'
              }`}
            >
              <input
                type="checkbox"
                className="mt-1 rounded border-gray-600"
                checked={checked}
                onChange={() => toggle(title)}
                disabled={loading || (!checked && selectedHeadlines.length >= MAX_HEADLINES)}
              />
              <span className="text-xs text-gray-300 leading-snug">
                <span className="text-cyan-500/80 font-mono text-[10px]">{a.ticker || '—'}</span>
                {' · '}
                {title}
                {a.source && <span className="text-gray-600 block mt-0.5">{a.source}</span>}
              </span>
            </label>
          )
        })}
      </div>
      <p className="text-xs text-gray-600 mb-4">
        Selected {selectedHeadlines.length}/{MAX_HEADLINES} headlines.
      </p>

      <button
        type="button"
        onClick={onRun}
        disabled={loading || !csvPath}
        className="btn-primary w-full sm:w-auto flex items-center justify-center gap-2"
      >
        {loading ? (
          <>
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Running pipeline…
          </>
        ) : (
          <>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Run full pipeline with context
          </>
        )}
      </button>
    </section>
  )
}
