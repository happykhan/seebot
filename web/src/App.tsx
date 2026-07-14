import { useEffect, useMemo, useState } from 'react'
import type { CheckResult, Status } from './types'

const statuses: Status[] = [
  'PASS',
  'FAIL',
  'PARTIAL',
  'NOT_APPLICABLE',
  'UNTESTABLE',
  'ERROR',
  'NOT_RUN',
]

function shortPackage(packageId: string): string {
  return packageId.split('__')[0]
}

function ResultRow({ result }: { result: CheckResult }) {
  return (
    <details className="result-row">
      <summary>
        <span className={`status status-${result.status.toLowerCase()}`}>{result.status}</span>
        <span className="package-name">{shortPackage(result.package_id)}</span>
        <span className="check-id">{result.check_id}</span>
        <span className="domain">{result.domain}</span>
        <span className="chevron" aria-hidden="true">⌄</span>
      </summary>
      <div className="result-detail">
        <div>
          <p className="detail-label">Observed</p>
          <pre>{JSON.stringify(result.observed, null, 2)}</pre>
        </div>
        <div>
          <p className="detail-label">Expected</p>
          <pre>{JSON.stringify(result.expected, null, 2)}</pre>
        </div>
        <dl>
          <div><dt>Command</dt><dd>{result.command?.join(' ') ?? 'Not applicable'}</dd></div>
          <div><dt>Method</dt><dd>{result.method.replaceAll('_', ' ')}</dd></div>
          <div><dt>Duration</dt><dd>{result.duration_seconds.toFixed(3)} s</dd></div>
          <div><dt>Run</dt><dd>{result.run_id}</dd></div>
          <div><dt>Evidence</dt><dd>{result.evidence.metadata}</dd></div>
        </dl>
        {result.notes && <p className="note">{result.notes}</p>}
      </div>
    </details>
  )
}

export default function App() {
  const [results, setResults] = useState<CheckResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<Status | 'ALL'>('ALL')
  const [domain, setDomain] = useState('ALL')

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/checks.json`)
      .then((response) => {
        if (!response.ok) throw new Error(`Results request returned ${response.status}`)
        return response.json() as Promise<CheckResult[]>
      })
      .then(setResults)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown error'))
      .finally(() => setLoading(false))
  }, [])

  const domains = useMemo(
    () => Array.from(new Set(results.map((result) => result.domain))).sort(),
    [results],
  )
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return results.filter((result) => {
      const matchesQuery = !needle || `${result.package_id} ${result.check_id}`.toLowerCase().includes(needle)
      return matchesQuery && (status === 'ALL' || result.status === status) && (domain === 'ALL' || result.domain === domain)
    })
  }, [domain, query, results, status])
  const counts = useMemo(
    () => Object.fromEntries(statuses.map((value) => [value, results.filter((item) => item.status === value).length])),
    [results],
  ) as Record<Status, number>
  const packages = new Set(results.map((result) => result.package_id)).size

  return (
    <>
      <header className="site-header">
        <a className="brand" href={import.meta.env.BASE_URL} aria-label="SeeCode home">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          SeeCode
        </a>
        <nav aria-label="Primary navigation">
          <a href="#results">Results</a>
          <a href="https://github.com/happykhan/seecode/tree/main/docs/protocol.md">Protocol</a>
          <a href="https://github.com/happykhan/seecode">Repository ↗</a>
        </nav>
      </header>

      <main>
        <section className="hero">
          <div className="eyebrow"><span /> Reproducible Bioconda software audit</div>
          <h1>Engineering evidence,<br /><em>without the league table.</em></h1>
          <p className="hero-copy">SeeCode publishes observable, evidence-backed results for widely downloaded Bioconda tools. Domains stay separate. Audit errors stay separate from software failures.</p>
          <div className="hero-meta">
            <div><strong>{packages}</strong><span>packages in this dataset</span></div>
            <div><strong>{results.length}</strong><span>individual checks</span></div>
            <div><strong>v0.1</strong><span>pilot protocol</span></div>
          </div>
        </section>

        <section className="principle-strip" aria-label="Core principles">
          <span>Raw observations</span><span>Immutable evidence</span><span>Explicit unknowns</span><span>No composite score</span>
        </section>

        <section className="results-section" id="results">
          <div className="section-heading">
            <div><p className="kicker">Pilot results explorer</p><h2>Inspect every check.</h2></div>
            <p>Open a row to see the declared expectation, observed value, exact command, and evidence location.</p>
          </div>

          <div className="status-grid">
            {statuses.map((value) => (
              <button className={status === value ? 'active' : ''} onClick={() => setStatus(status === value ? 'ALL' : value)} key={value}>
                <span className={`dot dot-${value.toLowerCase()}`} />
                <strong>{counts[value]}</strong>
                <span>{value.replaceAll('_', ' ')}</span>
              </button>
            ))}
          </div>

          <div className="filters">
            <label><span className="sr-only">Search checks</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search package or check ID…" /></label>
            <select value={domain} onChange={(event) => setDomain(event.target.value)} aria-label="Filter by domain">
              <option value="ALL">All domains</option>
              {domains.map((value) => <option key={value}>{value}</option>)}
            </select>
            {(query || status !== 'ALL' || domain !== 'ALL') && <button className="clear" onClick={() => { setQuery(''); setStatus('ALL'); setDomain('ALL') }}>Clear filters</button>}
            <span className="result-count">{filtered.length} / {results.length} checks</span>
          </div>

          <div className="results-list">
            <div className="result-header"><span>Status</span><span>Package</span><span>Check</span><span>Domain</span></div>
            {loading && <p className="empty">Loading results…</p>}
            {error && <p className="empty error">Could not load results: {error}</p>}
            {!loading && !error && filtered.map((result) => <ResultRow key={`${result.package_id}-${result.check_id}`} result={result} />)}
            {!loading && !error && filtered.length === 0 && <p className="empty">No checks match these filters.</p>}
          </div>
        </section>

        <section className="method-note">
          <p className="kicker">How to read this site</p>
          <h2>An <code>ERROR</code> is ours,<br />not the package’s.</h2>
          <p>If SeeCode cannot start or supervise an audit, the outcome is <code>ERROR</code> and is excluded from package-failure counts. <code>UNTESTABLE</code> and <code>NOT_APPLICABLE</code> remain visible rather than disappearing from denominators.</p>
          <a href="https://github.com/happykhan/seecode/blob/main/docs/protocol.md">Read the full protocol →</a>
        </section>
      </main>

      <footer><span>SeeCode · open methods, inspectable evidence</span><span>Code: MIT · Data and docs: CC BY 4.0</span></footer>
    </>
  )
}

