import { useEffect, useMemo, useState } from 'react'
import { cohortMetricValues, contractTitle, displayStatus, packageMetrics } from './metrics'
import { filterAndSortRankings, rankingPage } from './rankings'
import type { RankingSort } from './rankings'
import type { AwardRanking, CheckResult, LanguageProfile, PackageSummary, ProfilesData, RankingData } from './types'

const PAGE_SIZE = 25

function ResultRow({ result }: { result: CheckResult }) {
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
        </div>
      </div>
    </details>
  )
}

function AwardPill({ ranking }: { ranking: AwardRanking }) {
  return <span className={`award award-${ranking.tier.toLowerCase()}`}>{ranking.tier}</span>
}

function LanguageAssessment({ profile }: { profile: LanguageProfile }) {
  const strengths = profile.metrics.filter((metric) => metric.interpretation === 'favourable')
  const watch = profile.metrics.filter((metric) => metric.interpretation === 'unfavourable')
  const provisional = profile.metrics.filter((metric) => metric.interpretation === 'provisional')
  const format = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1)
  const ordinal = (value: number) => {
    const rounded = Math.round(value)
    const mod100 = rounded % 100
    const suffix = mod100 >= 11 && mod100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[rounded % 10] ?? 'th'
    return `${rounded}${suffix}`
  }
  return <section className="language-profile">
    <div className="language-heading"><div><span className="language-chip">{profile.language}</span><strong>{profile.measured_count} comparable measurements</strong></div><small>Compared only with {profile.language} projects using the same configuration.</small></div>
    {(strengths.length > 0 || watch.length > 0) && <div className="signal-grid">
      <div className="signal strength"><span>Strengths</span>{strengths.map((metric) => <p key={metric.check_id}><strong>{metric.label}</strong><small>{format(metric.value)} {metric.unit} · favourable cohort quartile</small></p>)}</div>
      <div className="signal watch"><span>Watch areas</span>{watch.map((metric) => <p key={metric.check_id}><strong>{metric.label}</strong><small>{format(metric.value)} {metric.unit} · requires interpretation, not necessarily a defect</small></p>)}</div>
    </div>}
    {provisional.length > 0 && <p className="provisional-note">Provisional comparison: only {provisional[0].cohort_size} compatible {profile.language} projects are currently available. Raw positions are shown without strength/watch labels.</p>}
    <div className="profile-metrics">{profile.metrics.map((metric) => <div key={metric.check_id}><span>{metric.label}</span><strong>{format(metric.value)} <small>{metric.unit}</small></strong><em>{metric.percentile === null ? 'Baseline not yet available' : `${ordinal(metric.percentile)} observed-value percentile`} · n={metric.cohort_size}</em></div>)}</div>
    {profile.metrics.length === 0 && <p className="empty-profile">Analyzer results are not yet available for this reviewed language root.</p>}
  </section>
}

function ComparePanel({ ids, rankings, profiles, onRemove }: { ids: string[]; rankings: AwardRanking[]; profiles: ProfilesData | null; onRemove: (id: string) => void }) {
  if (!ids.length) return null
  const selected = ids.map((id) => rankings.find((row) => row.package_id === id)).filter(Boolean) as AwardRanking[]
  return <section className="compare-panel" id="compare"><div className="section-heading"><div><p className="eyebrow">Side-by-side</p><h2>Compare selected tools</h2></div><p>Code measurements appear only when language and analyzer configuration are comparable.</p></div>
    <div className="compare-grid">{selected.map((tool) => { const profile = profiles?.profiles.find((row) => row.package_id === tool.package_id); return <article key={tool.package_id}><button aria-label={`Remove ${tool.name}`} onClick={() => onRemove(tool.package_id)}>×</button><h3>{tool.name}</h3><strong>{tool.score}/100</strong><span>{tool.breakdown.contracts}/50 CLI · {tool.breakdown.repository}/30 repo · {tool.breakdown.recipe_test}/20 recipe</span><small>{profile?.languages.map((row) => row.language).join(' + ') || 'Source profile pending'}</small></article> })}</div>
  </section>
}

function Leaderboard({ rankings, onSelect }: { rankings: AwardRanking[]; onSelect: (id: string) => void }) {
  return (
    <section className="leaderboard" id="rankings">
      <div className="section-heading">
        <div><p className="eyebrow">Engineering practice award</p><h2>Current ranking</h2></div>
        <p>Observable CLI contracts, repository signals, and recipe-test depth. Scientific validity is outside this award.</p>
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Rank</th><th>Tool</th><th>Award</th><th>Score</th><th>CLI</th><th>Repository</th><th>Recipe</th><th></th></tr></thead>
          <tbody>
            {rankings.slice(0, 10).map((ranking) => (
              <tr key={ranking.package_id}>
                <td className="rank">{ranking.rank ? `#${ranking.rank}` : '—'}</td>
                <td><strong>{ranking.name}</strong><small>{ranking.version}</small></td>
                <td><AwardPill ranking={ranking} /></td>
                <td><strong>{ranking.score}</strong><span className="score-bar"><i style={{ width: `${ranking.score}%` }} /></span></td>
                <td>{ranking.breakdown.contracts}/50</td>
                <td>{ranking.breakdown.repository}/30</td>
                <td>{ranking.breakdown.recipe_test}/20</td>
                <td><button className="text-button" onClick={() => onSelect(ranking.package_id)}>View</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="formula"><summary>How the award is calculated</summary><p><strong>50 points</strong> for five executable contracts; <strong>30 points</strong> for six repository-practice signals; <strong>20 points</strong> for recipe-test depth. Gold starts at 85, silver at 70, and bronze at 55. Static-analysis findings are shown comparatively and do not affect the score.</p></details>
    </section>
  )
}

function CohortSummary({ results, profiles }: { results: CheckResult[]; profiles: ProfilesData | null }) {
  const grouped = useMemo(() => {
    const byPackage = new Map<string, CheckResult[]>()
    results.forEach((result) => byPackage.set(result.package_id, [...(byPackage.get(result.package_id) ?? []), result]))
    const values = [...byPackage.values()].map(cohortMetricValues)
    if (!values.length) return []
    return values[0].map((definition, index) => {
      const sample = values.map((packageValues) => packageValues[index].value).sort((a, b) => a - b)
      const middle = Math.floor(sample.length / 2)
      const median = sample.length % 2 ? sample[middle] : (sample[middle - 1] + sample[middle]) / 2
      return { ...definition, minimum: sample[0], median, maximum: sample[sample.length - 1], count: sample.length }
    })
  }, [results])
  const languages = useMemo(() => {
    const rows = profiles?.profiles.flatMap((profile) => profile.languages.map((language) => ({ package_id: profile.package_id, ...language }))) ?? []
    return [...new Set(rows.map((row) => row.language))].sort().map((language) => {
      const matching = rows.filter((row) => row.language === language)
      return { language, packages: new Set(matching.map((row) => row.package_id)).size, measurements: matching.reduce((sum, row) => sum + row.measured_count, 0) }
    })
  }, [profiles])
  return (
    <section className="cohort-summary" id="metrics">
      <div className="section-heading">
        <div><p className="eyebrow">Cohort aggregation</p><h2>Codebase coverage and distributions</h2></div>
        <p>Every source language has its own profile and baseline. Analyzer errors and unavailable checks remain visible.</p>
      </div>
      <div className="language-summary">{languages.map((row) => <div key={row.language}><span>{row.language}</span><strong>{row.packages}</strong><small>projects · {row.measurements} comparable measurements</small></div>)}{languages.length === 0 && <p>Language profiles are awaiting the next normalized run.</p>}</div>
      {grouped.length > 0 && <><h3 className="subheading">Python pilot distributions</h3>
      <div className="distribution-grid">
        {grouped.map((metric) => (
          <div className="distribution" key={metric.key}>
            <span>{metric.label}</span><strong>{metric.median.toFixed(1)} <small>{metric.unit}</small></strong>
            <div className="range"><i style={{ left: '0%', right: '0%' }} /><b style={{ left: metric.maximum === metric.minimum ? '50%' : `${(metric.median - metric.minimum) * 100 / (metric.maximum - metric.minimum)}%` }} /></div>
            <small>{metric.minimum.toFixed(1)} min · {metric.median.toFixed(1)} median · {metric.maximum.toFixed(1)} max · n={metric.count}</small>
          </div>
        ))}
      </div>
      </>}
    </section>
  )
}

function ToolDirectory({ rankings, selected, compared, onSelect, onCompare }: { rankings: AwardRanking[]; selected: string; compared: string[]; onSelect: (id: string) => void; onCompare: (id: string) => void }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [sort, setSort] = useState<RankingSort>('score')
  const [language, setLanguage] = useState('all')
  const [page, setPage] = useState(1)
  const categories = useMemo(() => [...new Set(rankings.map((item) => item.category))].sort(), [rankings])
  const languages = useMemo(() => [...new Set(rankings.flatMap((item) => item.languages ?? []))].sort(), [rankings])
  const filtered = useMemo(() => filterAndSortRankings(rankings, query, category, sort).filter((item) => language === 'all' || item.languages?.includes(language)), [category, language, query, rankings, sort])
  const { currentPage, pages, items: visible } = rankingPage(filtered, page, PAGE_SIZE)
  const updateFilter = (action: () => void) => { action(); setPage(1) }
  return (
    <section className="directory" id="tools">
      <div className="section-heading"><div><p className="eyebrow">Tool directory</p><h2>Browse {rankings.length} reviewed tools</h2></div><p>Built for the full 200-tool cohort: search, filter, sort, then open one detailed profile.</p></div>
      <div className="directory-controls">
        <label>Search<input type="search" value={query} onChange={(event) => updateFilter(() => setQuery(event.target.value))} placeholder="Tool name or category" /></label>
        <label>Category<select value={category} onChange={(event) => updateFilter(() => setCategory(event.target.value))}><option value="all">All categories</option>{categories.map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label>
        <label>Sort by<select value={sort} onChange={(event) => updateFilter(() => setSort(event.target.value as RankingSort))}><option value="score">Award score</option><option value="name">Name</option><option value="contracts">CLI contracts</option><option value="repository">Repository signals</option><option value="recipe">Recipe depth</option></select></label>
        <label>Language<select value={language} onChange={(event) => updateFilter(() => setLanguage(event.target.value))}><option value="all">All languages</option>{languages.map((value) => <option key={value}>{value}</option>)}</select></label>
      </div>
      <div className="table-wrap">
        <table className="tool-table">
          <thead><tr><th>Tool</th><th>Category</th><th>Award</th><th>Score</th><th>CLI</th><th>Repo</th><th>Recipe</th><th></th></tr></thead>
          <tbody>{visible.map((ranking) => <tr className={selected === ranking.package_id ? 'selected' : ''} key={ranking.package_id}><td><strong>{ranking.name}</strong><small>{ranking.version} · {(ranking.languages ?? []).join(' + ') || 'source pending'}</small></td><td className="category">{ranking.category.replaceAll('_', ' ')}</td><td><AwardPill ranking={ranking} /></td><td>{ranking.score}/100</td><td>{ranking.breakdown.contracts}/50</td><td>{ranking.breakdown.repository}/30</td><td>{ranking.breakdown.recipe_test}/20</td><td><button className="text-button" onClick={() => onSelect(ranking.package_id)}>View</button><button disabled={compared.includes(ranking.package_id) || compared.length === 3} className="compare-button" onClick={() => onCompare(ranking.package_id)}>Compare</button></td></tr>)}</tbody>
        </table>
      </div>
      <div className="pagination"><span>{filtered.length} tools · page {currentPage} of {pages}</span><div><button disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Previous</button><button disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Next</button></div></div>
    </section>
  )
}

function PackageProfile({ pkg, ranking, results, profiles }: { pkg: PackageSummary; ranking?: AwardRanking; results: CheckResult[]; profiles: LanguageProfile[] }) {
  const [copied, setCopied] = useState(false)
  const metrics = packageMetrics(results)
  const contracts = results.filter((result) => result.result_kind === 'CONTRACT')
  const measurements = results.filter((result) => result.result_kind === 'MEASUREMENT')
  const passedContracts = contracts.filter((result) => result.status === 'PASS')
  const failedContracts = contracts.filter((result) => result.status === 'FAIL')
  const repoSignals = Object.values(metrics.repository).filter(Boolean).length
  const badgeUrl = `${window.location.origin}${import.meta.env.BASE_URL}badges/${pkg.name.toLowerCase()}.svg`
  const profileUrl = `${window.location.origin}${import.meta.env.BASE_URL}?tool=${encodeURIComponent(pkg.name)}#profile`
  const badgeMarkdown = `[![Seebot ${ranking?.tier ?? 'reviewed'} award](${badgeUrl})](${profileUrl})`
  const copyBadge = async () => { await navigator.clipboard.writeText(badgeMarkdown); setCopied(true) }
  return (
    <article className="package-profile" id="profile">
      <header className="package-heading">
        <div><p className="eyebrow">{pkg.category.replaceAll('_', ' ')}</p><h2>{pkg.name} <span>{pkg.version}</span></h2><p>{pkg.description}</p></div>
        <div className="identity-card"><span>Frozen Bioconda artifact</span><strong>{pkg.build}</strong><small>{pkg.subdir}</small><a href={pkg.upstream_url}>Upstream repository ↗</a></div>
      </header>
      {ranking && <section className="award-section"><div><p className="eyebrow">Provisional Seebot Engineering Practice Award</p><div className="award-score"><strong>{ranking.score}</strong><span>/100</span><AwardPill ranking={ranking} /></div><p>Rank {ranking.rank ? `#${ranking.rank}` : 'pending'} · pilot rubric; promotional badge copy unlocks after freeze</p></div><div className="badge-box"><img src={`${import.meta.env.BASE_URL}badges/${pkg.name.toLowerCase()}.svg`} alt={`Provisional Seebot ${ranking.tier} award: ${ranking.score} out of 100`} /><button disabled title="Badges remain provisional until the ten-tool rubric is frozen" onClick={copyBadge}>{copied ? 'Copied Markdown' : 'Badge provisional'}</button></div></section>}
      <section className="signal-overview"><div className="overview-signal strong-signal"><span>Observed strengths</span><h3>{passedContracts.length}/{contracts.length} executable contracts met</h3><p>{repoSignals}/6 repository-practice signals present. These observations describe visible practices, not scientific quality.</p></div><div className="overview-signal watch-signal"><span>Watch areas</span>{failedContracts.length > 0 ? <><h3>{failedContracts.length} executable contract{failedContracts.length === 1 ? '' : 's'} not met</h3><p>Open the recorded checks below for the exact command and outcome.</p></> : metrics.recipeDepth <= 1 ? <><h3>Recipe test depth is installation-level</h3><p>Bioconda confirms installation or command availability; Seebot's independent functional probe is reported separately.</p></> : <><h3>No behaviour-contract watch area observed</h3><p>Source comparisons remain provisional until each language cohort reaches ten compatible tools.</p></>}</div></section>
      <section className="contract-section"><div className="section-label"><span>Executable contracts</span><strong>{contracts.filter((result) => result.status === 'PASS').length}/{contracts.length} met</strong></div><div className="contract-grid">{contracts.map((result) => <div key={result.check_id}><span className={`status status-${displayStatus(result).toLowerCase()}`}>{displayStatus(result)}</span><strong>{contractTitle(result.check_id)}</strong></div>)}</div></section>
      <section className="assessment-section"><div className="section-label"><span>Codebase profile</span><small>Separate by language; never part of the award score</small></div>{profiles.map((profile) => <LanguageAssessment key={profile.language} profile={profile} />)}{profiles.length === 0 && <p className="empty-profile">Reviewed language roots exist, but no normalized source analysis is published yet.</p>}</section>
      <section className="facts-section"><div><h3>Repository snapshot</h3><div className="fact-list">{Object.entries(metrics.repository).map(([label, value]) => <span className={value ? 'present' : 'absent'} key={label}>{value ? '✓' : '–'} {label}</span>)}</div></div><div><h3>Recipe test</h3><strong className="depth">Level {metrics.recipeDepth}</strong><p>Installation-level checks only; independent functional behaviour is tested separately.</p></div><div><h3>Execution</h3><p>Package installation and executable probes run in a fresh native Pixi environment.</p></div></section>
      <section className="checks-section"><div className="section-label"><span>All recorded observations</span><small>{contracts.length} contracts · {measurements.length} measurements</small></div>{results.map((result) => <ResultRow key={result.check_id} result={result} />)}</section>
    </article>
  )
}

export default function App() {
  const [results, setResults] = useState<CheckResult[]>([])
  const [packages, setPackages] = useState<PackageSummary[]>([])
  const [rankingData, setRankingData] = useState<RankingData | null>(null)
  const [profiles, setProfiles] = useState<ProfilesData | null>(null)
  const [compared, setCompared] = useState<string[]>([])
  const [selected, setSelected] = useState('')
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    Promise.all([
      fetch(`${import.meta.env.BASE_URL}data/checks.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Checks returned ${response.status}`))),
      fetch(`${import.meta.env.BASE_URL}data/packages.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Packages returned ${response.status}`))),
      fetch(`${import.meta.env.BASE_URL}data/rankings.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Rankings returned ${response.status}`))),
      fetch(`${import.meta.env.BASE_URL}data/profiles.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Profiles returned ${response.status}`))),
    ] as const).then(([checkRows, packageRows, rankingRows, profileRows]: [CheckResult[], PackageSummary[], RankingData, ProfilesData]) => {
      setResults(checkRows); setPackages(packageRows); setRankingData(rankingRows); setProfiles(profileRows)
      const requested = new URLSearchParams(window.location.search).get('tool')
      setSelected(packageRows.find((pkg) => pkg.name === requested)?.package_id ?? packageRows[0]?.package_id ?? '')
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown data error'))
  }, [])
  const rankings = rankingData?.rankings ?? []
  const selectedPackage = packages.find((pkg) => pkg.package_id === selected)
  const selectedRanking = rankings.find((ranking) => ranking.package_id === selected)
  const selectedResults = useMemo(() => results.filter((result) => result.package_id === selected), [results, selected])
  const contracts = results.filter((result) => result.result_kind === 'CONTRACT')
  const measurements = results.filter((result) => result.result_kind === 'MEASUREMENT')
  const errors = results.filter((result) => result.status === 'ERROR').length
  const selectPackage = (id: string) => {
    setSelected(id)
    const pkg = packages.find((item) => item.package_id === id)
    if (pkg) window.history.replaceState({}, '', `${import.meta.env.BASE_URL}?tool=${encodeURIComponent(pkg.name)}#profile`)
    window.setTimeout(() => document.getElementById('profile')?.scrollIntoView({ behavior: 'smooth' }), 0)
  }
  return (
    <><header className="site-header"><a className="brand" href={import.meta.env.BASE_URL}><span>SB</span>Seebot</a><nav><a href="#rankings">Rankings</a><a href="#metrics">Metrics</a><a href="#tools">Tools</a><a href="https://github.com/happykhan/seebot">GitHub ↗</a></nav></header><main>
      <section className="overview"><div><p className="eyebrow">Bioconda software engineering audit</p><h1>Compare tools.<br />See the metrics.</h1><p className="lede">A transparent engineering-practice ranking alongside raw domain measurements. No claim of scientific correctness.</p></div><div className="overview-stats"><div><strong>{packages.length || '—'}</strong><span>reviewed packages</span></div><div><strong>{contracts.length ? `${contracts.filter((result) => result.status === 'PASS').length}/${contracts.length}` : '—'}</strong><span>contracts met</span></div><div><strong>{measurements.length || '—'}</strong><span>measurements completed</span></div><div><strong>{errors}</strong><span>audit errors</span></div></div></section>
      {error && <p className="load-error">Could not load the published dataset: {error}</p>}
      {rankingData && <><Leaderboard rankings={rankings} onSelect={selectPackage} /><CohortSummary results={results} profiles={profiles} /><ToolDirectory rankings={rankings} selected={selected} compared={compared} onSelect={selectPackage} onCompare={(id) => setCompared((current) => current.length < 3 && !current.includes(id) ? [...current, id] : current)} /><ComparePanel ids={compared} rankings={rankings} profiles={profiles} onRemove={(id) => setCompared((current) => current.filter((value) => value !== id))} /></>}
      {selectedPackage && <PackageProfile pkg={selectedPackage} ranking={selectedRanking} results={selectedResults} profiles={profiles?.profiles.find((row) => row.package_id === selected)?.languages ?? []} />}
      {!error && !selectedPackage && <p className="loading">Loading published pilot data…</p>}
    </main><footer><span>Seebot development pilot · award rubric {rankingData?.rubric_version ?? '—'}</span><span>{rankingData?.scope_note ?? 'Observations are not scientific validation.'}</span></footer></>
  )
}
