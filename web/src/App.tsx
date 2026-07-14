import { useEffect, useMemo, useState } from 'react'
import { contractTitle, displayStatus, packageMetrics } from './metrics'
import type { CheckResult, PackageSummary } from './types'

function ResultRow({ result, artifactUrl }: { result: CheckResult; artifactUrl: string }) {
  const label = displayStatus(result)
  return (
    <details className="result-row">
      <summary>
        <span className={`status status-${label.toLowerCase()}`}>{label}</span>
        <span><strong>{contractTitle(result.check_id)}</strong><small>{result.check_id}</small></span>
        <span className="domain">{result.domain}</span>
        <span className="chevron" aria-hidden="true">+</span>
      </summary>
      <div className="result-detail">
        <div><h4>Observed</h4><pre>{JSON.stringify(result.observed, null, 2)}</pre></div>
        <div className="provenance">
          <h4>Provenance</h4>
          <dl>
            <div><dt>Method</dt><dd>{result.method.replaceAll('_', ' ')}</dd></div>
            <div><dt>Tool</dt><dd>{result.tool.name} {result.tool.version}</dd></div>
            <div><dt>Duration</dt><dd>{result.duration_seconds.toFixed(2)} s</dd></div>
            <div><dt>Run</dt><dd>{result.run_id}</dd></div>
            <div><dt>Command</dt><dd>{result.command?.join(' ') ?? 'Not applicable'}</dd></div>
          </dl>
          <a className="evidence-link" href={artifactUrl}>Download raw evidence ↗</a>
        </div>
      </div>
    </details>
  )
}

function PackageProfile({ pkg, results }: { pkg: PackageSummary; results: CheckResult[] }) {
  const metrics = packageMetrics(results)
  const contracts = results.filter((result) => result.result_kind === 'CONTRACT')
  const measurements = results.filter((result) => result.result_kind === 'MEASUREMENT')
  return (
    <article className="package-profile">
      <header className="package-heading">
        <div>
          <p className="eyebrow">{pkg.category.replaceAll('_', ' ')}</p>
          <h2>{pkg.name} <span>{pkg.version}</span></h2>
          <p>{pkg.description}</p>
        </div>
        <div className="identity-card">
          <span>Frozen Bioconda artifact</span>
          <strong>{pkg.build}</strong>
          <small>{pkg.subdir}</small>
          <a href={pkg.upstream_url}>Upstream repository ↗</a>
        </div>
      </header>

      <section className="contract-section">
        <div className="section-label"><span>Executable contracts</span><strong>{contracts.filter((r) => r.status === 'PASS').length}/{contracts.length} met</strong></div>
        <div className="contract-grid">
          {contracts.map((result) => <div key={result.check_id}><span className={`status status-${displayStatus(result).toLowerCase()}`}>{displayStatus(result)}</span><strong>{contractTitle(result.check_id)}</strong></div>)}
        </div>
      </section>

      <section className="measurement-section">
        <div className="section-label"><span>Source observations</span><small>Measurements, not pass/fail judgements</small></div>
        <div className="metric-grid">
          {metrics.map((metric) => <div className="metric-card" key={metric.label}><strong>{metric.value}</strong><span>{metric.label}</span><small>{metric.note}</small></div>)}
        </div>
      </section>

      <section className="facts-section">
        <div><h3>Repository snapshot</h3><div className="fact-list">{Object.entries(metrics.repository).map(([label, value]) => <span className={value ? 'present' : 'absent'} key={label}>{value ? '✓' : '–'} {label}</span>)}</div></div>
        <div><h3>Recipe test</h3><strong className="depth">Level {metrics.recipeDepth}</strong><p>Installation-level checks only; independent functional behaviour is tested separately.</p></div>
        <div><h3>Execution</h3><p>Native Pixi environment. Exact solved package build and lock hash are retained in evidence.</p><a className="evidence-link" href={pkg.artifact_url}>Download evidence archive ↗</a></div>
      </section>

      <section className="checks-section">
        <div className="section-label"><span>All recorded observations</span><small>{contracts.length} contracts · {measurements.length} measurements</small></div>
        {results.map((result) => <ResultRow artifactUrl={pkg.artifact_url} key={result.check_id} result={result} />)}
      </section>
    </article>
  )
}

export default function App() {
  const [results, setResults] = useState<CheckResult[]>([])
  const [packages, setPackages] = useState<PackageSummary[]>([])
  const [selected, setSelected] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      fetch(`${import.meta.env.BASE_URL}data/checks.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Checks returned ${response.status}`))),
      fetch(`${import.meta.env.BASE_URL}data/packages.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Packages returned ${response.status}`))),
    ] as const)
      .then(([checkRows, packageRows]: [CheckResult[], PackageSummary[]]) => {
        setResults(checkRows)
        setPackages(packageRows)
        setSelected(packageRows[0]?.package_id ?? '')
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown data error'))
  }, [])

  const selectedPackage = packages.find((pkg) => pkg.package_id === selected)
  const selectedResults = useMemo(() => results.filter((result) => result.package_id === selected), [results, selected])
  const contracts = results.filter((result) => result.result_kind === 'CONTRACT')
  const measurements = results.filter((result) => result.result_kind === 'MEASUREMENT')
  const errors = results.filter((result) => result.status === 'ERROR').length

  return (
    <>
      <header className="site-header"><a className="brand" href={import.meta.env.BASE_URL}><span>SB</span>Seebot</a><nav><a href="#packages">Packages</a><a href="https://github.com/happykhan/seebot/blob/main/docs/protocol.md">Protocol</a><a href="https://github.com/happykhan/seebot">GitHub ↗</a></nav></header>
      <main>
        <section className="overview">
          <div><p className="eyebrow">Three-package development pilot</p><h1>Bioconda tools,<br />observed in the open.</h1><p className="lede">Executable contracts and source measurements are reported separately. No composite score, no hidden failures, and no claim of scientific correctness.</p></div>
          <div className="overview-stats"><div><strong>{packages.length || '—'}</strong><span>reviewed packages</span></div><div><strong>{contracts.length ? `${contracts.filter((r) => r.status === 'PASS').length}/${contracts.length}` : '—'}</strong><span>contracts met</span></div><div><strong>{measurements.length || '—'}</strong><span>measurements completed</span></div><div><strong>{errors}</strong><span>audit errors</span></div></div>
        </section>

        {error && <p className="load-error">Could not load the published dataset: {error}</p>}
        <section className="package-picker" id="packages" aria-label="Select package">
          {packages.map((pkg) => <button className={selected === pkg.package_id ? 'active' : ''} key={pkg.package_id} onClick={() => setSelected(pkg.package_id)}><span>{pkg.name}</span><small>{pkg.version} · {pkg.category.replaceAll('_', ' ')}</small></button>)}
        </section>
        {selectedPackage && <PackageProfile pkg={selectedPackage} results={selectedResults} />}
        {!error && !selectedPackage && <p className="loading">Loading published pilot data…</p>}
      </main>
      <footer><span>Seebot development pilot · protocol v0.1</span><span>Observations are not quality scores.</span></footer>
    </>
  )
}
