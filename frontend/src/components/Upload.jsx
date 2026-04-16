import { useState, useRef, useCallback } from 'react'

const STEPS = [
  'Uploading CSV…',
  'Fetching live prices…',
  'Analysing 7d & 30d trends…',
  'Fetching sector news…',
  'Classifying sentiment (Claude)…',
  'Checking allocation targets…',
  'Scoring holdings…',
  'Generating recommendations…',
  'Writing AI explanations…',
]

function useStepCycle(active) {
  const [step, setStep] = useState(0)
  const ref = useRef(null)

  if (active && !ref.current) {
    ref.current = setInterval(() => {
      setStep(s => (s + 1) % STEPS.length)
    }, 4500)
  }
  if (!active && ref.current) {
    clearInterval(ref.current)
    ref.current = null
    // reset on next tick so it starts fresh next time
    setTimeout(() => setStep(0), 100)
  }

  return STEPS[step]
}

export default function Upload({ onUpload, onAnalyze, loading, csvPath }) {
  const [dragging, setDragging] = useState(false)
  const [file, setFile]         = useState(null)
  const inputRef                = useRef(null)
  const stepLabel               = useStepCycle(loading)

  const handleFile = useCallback((f) => {
    if (!f) return
    setFile(f)
    onUpload(f)
  }, [onUpload])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files?.[0]
    if (f?.name.endsWith('.csv')) handleFile(f)
  }, [handleFile])

  return (
    <section className="card p-6 animate-fade-in">
      <div className="flex items-center gap-2 mb-5">
        <div className="w-1 h-5 bg-cyan-500 rounded-full" />
        <h2 className="text-base font-semibold text-white">Upload Portfolio</h2>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
          transition-all duration-200 group
          ${dragging
            ? 'border-cyan-500 bg-cyan-500/10'
            : 'border-gray-700 hover:border-gray-600 hover:bg-gray-800/50'
          }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={e => handleFile(e.target.files?.[0])}
        />

        <div className="flex flex-col items-center gap-3">
          <div className={`w-12 h-12 rounded-full flex items-center justify-center transition-colors
            ${dragging ? 'bg-cyan-500/20' : 'bg-gray-800 group-hover:bg-gray-700'}`}>
            <svg className={`w-6 h-6 ${dragging ? 'text-cyan-400' : 'text-gray-500'}`}
                 fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          </div>

          {file ? (
            <div>
              <p className="text-sm font-medium text-cyan-400">{file.name}</p>
              <p className="text-xs text-gray-500 mt-1">
                {(file.size / 1024).toFixed(1)} KB · Click to change
              </p>
            </div>
          ) : (
            <div>
              <p className="text-sm font-medium text-gray-300">
                Drop your CSV here or <span className="text-cyan-400">click to browse</span>
              </p>
              <p className="text-xs text-gray-600 mt-1">
                Supported: Ticker, Quantity, Buy Price, Purchase Date, Sector
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="mt-4 p-4 bg-cyan-500/5 border border-cyan-500/20 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <svg className="w-5 h-5 text-cyan-400 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10"
                        stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-cyan-400 truncate">{stepLabel}</p>
              <p className="text-xs text-gray-500 mt-0.5">This may take 2–5 minutes</p>
            </div>
          </div>
          {/* Progress dots */}
          <div className="flex gap-1 mt-3">
            {STEPS.map((_, i) => (
              <div key={i} className={`h-1 flex-1 rounded-full transition-all duration-500 ${
                i <= STEPS.indexOf(stepLabel) ? 'bg-cyan-500' : 'bg-gray-800'
              }`} />
            ))}
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-3 mt-5">
        <button
          onClick={() => file && onAnalyze()}
          disabled={!csvPath || loading}
          className="btn-primary flex-1 flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10"
                        stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              Analyzing…
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                      d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              Analyze Portfolio
            </>
          )}
        </button>
      </div>
    </section>
  )
}
