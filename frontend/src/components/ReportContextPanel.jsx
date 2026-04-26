/**
 * What “rebalancing” means here, execution timeline, macro list, and API warnings.
 */
export default function ReportContextPanel({
  warnings = [],
  executionTimeline = [],
  macroTriggers = [],
  costBasisSummary = null,
}) {
  return (
    <section className="card p-6 animate-fade-in space-y-6">
      <div className="flex items-center gap-2">
        <div className="w-1 h-5 bg-amber-500 rounded-full" />
        <h2 className="text-base font-semibold text-white font-display tracking-wide">
          Report context
        </h2>
      </div>

      {executionTimeline?.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">
            Indicative execution timeline
          </p>
          <ol className="space-y-3 border-l border-cyan-500/30 pl-4 ml-1">
            {executionTimeline.map((step, i) => (
              <li key={i} className="relative">
                <span className="absolute -left-[21px] top-1 w-2 h-2 rounded-full bg-cyan-500" />
                <p className="text-sm font-medium text-white">{step.phase}</p>
                <p className="text-xs text-cyan-400/90 font-mono mt-0.5">{step.date_range}</p>
                <p className="text-xs text-gray-400 mt-1">{step.description}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {macroTriggers?.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-3">
            Macro checklist (reference)
          </p>
          <ol className="space-y-2">
            {macroTriggers.map((t) => (
              <li
                key={t.id}
                className="flex gap-3 text-sm text-gray-300 border border-gray-800 rounded-lg p-3 bg-gray-900/30"
              >
                <span className="font-display text-lg text-cyan-400/90 w-6 flex-shrink-0">
                  {t.id}
                </span>
                <div>
                  <p className="font-medium text-white">{t.title}</p>
                  <p className="text-xs text-gray-500 mt-1">{t.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}
