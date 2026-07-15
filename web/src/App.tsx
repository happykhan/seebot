import { useEffect, useMemo, useState } from 'react'
import { contractTitle, displayStatus } from './metrics'
import { filterAndSortRankings, rankingPage } from './rankings'
import type { RankingSort } from './rankings'
import type { AwardRanking, CheckResult, LanguageProfile, PackageSummary, ProfilesData, RankingData } from './types'

const PAGE_SIZE = 25

const categoryInfo = {
  testing: { title: 'Tests', maximum: 25, description: 'Test suite, test configuration, and reusable test data found in the upstream codebase.' },
  automation: { title: 'Automation', maximum: 20, description: 'Continuous integration, dependency updates, and release automation are configured.' },
  documentation: { title: 'Documentation', maximum: 20, description: 'README, maintained documentation tree, and worked examples or tutorials.' },
  stewardship: { title: 'Project stewardship', maximum: 20, description: 'Licence, contribution, conduct, citation, issue, and change-management files.' },
  reproducibility: { title: 'Reproducibility', maximum: 15, description: 'Dependency manifests, lock files, and container or development-environment definitions.' },
} as const

type CategoryKey = keyof typeof categoryInfo

function repoObservation(results: CheckResult[]): Record<string, unknown> {
  return results.find((result) => result.check_id === 'REPO-PRACTICES-001')?.observed ?? {}
}

function bool(value: unknown): boolean { return value === true }
function num(value: unknown): number { return typeof value === 'number' ? value : 0 }

function AwardPill({ ranking }: { ranking: AwardRanking }) {
  return <span className={`award award-${ranking.tier.toLowerCase()}`}>{ranking.tier}</span>
}

function ResultRow({ result }: { result: CheckResult }) {
  const label = displayStatus(result)
  return <details className="result-row">
    <summary><span className={`status status-${label.toLowerCase()}`}>{label}</span><span><strong>{contractTitle(result.check_id)}</strong><small>{result.check_id}</small></span><span className="domain">{result.domain}</span><span className="chevron">+</span></summary>
    <div className="result-detail"><div><h4>Observed</h4><pre>{JSON.stringify(result.observed, null, 2)}</pre></div><div className="provenance"><h4>How it was measured</h4><dl><div><dt>Method</dt><dd>{result.method.replaceAll('_', ' ')}</dd></div><div><dt>Tool</dt><dd>{result.tool.name} {result.tool.version}</dd></div><div><dt>Duration</dt><dd>{result.duration_seconds.toFixed(2)} s</dd></div><div><dt>Command</dt><dd>{result.command?.join(' ') ?? 'Repository API observation'}</dd></div></dl></div></div>
  </details>
}

function CategoryBar({ category, value }: { category: CategoryKey; value: number }) {
  const info = categoryInfo[category]
  const percent = value * 100 / info.maximum
  return <div className="category-bar"><div><span>{info.title}</span><strong>{value}/{info.maximum}</strong></div><i><b style={{ width: `${percent}%` }} /></i></div>
}

function CohortSnapshot({ rankings, results }: { rankings: AwardRanking[]; results: CheckResult[] }) {
  const repositories = results.filter((result) => result.check_id === 'REPO-PRACTICES-001' && result.status === 'PASS')
  const count = (signal: string) => repositories.filter((result) => bool(result.observed[signal])).length
  const cards = [
    ['Tests found', count('test_path_present'), 'A test directory or test files were observed. This does not assess effectiveness.'],
    ['CI configured', count('ci_workflow_present'), 'At least one upstream CI workflow was observed. Current pass status is not inferred.'],
    ['Documentation tree', count('documentation_path_present'), 'A dedicated docs or documentation directory was observed.'],
    ['Dependency manifest', count('dependency_manifest_present'), 'A language or environment dependency manifest was observed.'],
  ] as const
  return <section className="snapshot" id="overview">
    <div className="section-heading"><div><p className="eyebrow">What the cohort shows</p><h2>Upstream engineering at a glance</h2></div><p>Direct file-based observations from each pinned upstream repository. Missing means “not observed”, not “the project is bad”.</p></div>
    <div className="snapshot-grid">{cards.map(([label, value, note]) => <article key={label}><strong>{value}<small>/{repositories.length || rankings.length}</small></strong><h3>{label}</h3><p>{note}</p></article>)}</div>
  </section>
}

function Leaderboard({ rankings, onSelect }: { rankings: AwardRanking[]; onSelect: (id: string) => void }) {
  return <section className="leaderboard" id="rankings">
    <div className="section-heading"><div><p className="eyebrow">Upstream engineering practice award</p><h2>Which projects expose the strongest practices?</h2></div><p>The award scores five observable upstream categories. Runtime behaviour and static-analysis findings are reported separately.</p></div>
    <div className="table-wrap"><table><thead><tr><th>Rank</th><th>Tool</th><th>Award</th><th>Total</th><th>Tests</th><th>Automation</th><th>Docs</th><th></th></tr></thead><tbody>{rankings.slice(0, 10).map((ranking) => <tr key={ranking.package_id}><td className="rank">{ranking.rank ? `#${ranking.rank}` : '—'}</td><td><strong>{ranking.name}</strong><small>{ranking.version} · {(ranking.languages ?? []).join(' + ')}</small></td><td><AwardPill ranking={ranking} /></td><td><strong>{ranking.score}/100</strong><span className="score-bar"><i style={{ width: `${ranking.score}%` }} /></span></td><td>{ranking.breakdown.testing}/25</td><td>{ranking.breakdown.automation}/20</td><td>{ranking.breakdown.documentation}/20</td><td><button className="text-button" onClick={() => onSelect(ranking.package_id)}>Open report</button></td></tr>)}</tbody></table></div>
    <details className="formula"><summary>What is and is not scored</summary><div className="formula-grid">{(Object.entries(categoryInfo) as [CategoryKey, typeof categoryInfo[CategoryKey]][]).map(([key, info]) => <p key={key}><strong>{info.maximum} points · {info.title}</strong>{info.description}</p>)}</div><p>File presence is a conservative, reproducible signal. It does not establish test quality, documentation accuracy, active maintenance, security, or scientific validity.</p></details>
  </section>
}

function ToolDirectory({ rankings, selected, onSelect }: { rankings: AwardRanking[]; selected: string; onSelect: (id: string) => void }) {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [sort, setSort] = useState<RankingSort>('score')
  const [language, setLanguage] = useState('all')
  const [page, setPage] = useState(1)
  const categories = useMemo(() => [...new Set(rankings.map((item) => item.category))].sort(), [rankings])
  const languages = useMemo(() => [...new Set(rankings.flatMap((item) => item.languages ?? []))].sort(), [rankings])
  const filtered = useMemo(() => filterAndSortRankings(rankings, query, category, sort).filter((item) => language === 'all' || item.languages?.includes(language)), [category, language, query, rankings, sort])
  const { currentPage, pages, items } = rankingPage(filtered, page, PAGE_SIZE)
  const change = (action: () => void) => { action(); setPage(1) }
  return <section className="directory" id="tools">
    <div className="section-heading"><div><p className="eyebrow">Project directory</p><h2>Find an upstream report</h2></div><p>Search and filter will remain usable when the cohort grows to 200 tools. Each row opens one complete project report.</p></div>
    <div className="directory-controls"><label>Search<input type="search" value={query} onChange={(event) => change(() => setQuery(event.target.value))} placeholder="Tool name or category" /></label><label>Category<select value={category} onChange={(event) => change(() => setCategory(event.target.value))}><option value="all">All categories</option>{categories.map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label><label>Language<select value={language} onChange={(event) => change(() => setLanguage(event.target.value))}><option value="all">All languages</option>{languages.map((value) => <option key={value}>{value}</option>)}</select></label><label>Sort<select value={sort} onChange={(event) => change(() => setSort(event.target.value as RankingSort))}><option value="score">Overall award</option><option value="testing">Tests</option><option value="automation">Automation</option><option value="documentation">Documentation</option><option value="name">Name</option></select></label></div>
    <div className="tool-cards">{items.map((ranking) => <button className={selected === ranking.package_id ? 'selected' : ''} key={ranking.package_id} onClick={() => onSelect(ranking.package_id)}><span><strong>{ranking.name}</strong><small>{ranking.category.replaceAll('_', ' ')} · {ranking.version}</small></span><span className="tool-test-state"><em className={ranking.breakdown.testing >= 15 ? 'yes' : 'no'}>{ranking.breakdown.testing >= 15 ? 'Tests found' : 'Tests not observed'}</em><small>{ranking.breakdown.testing}/25 testing</small></span><span className="tool-score"><strong>{ranking.score}</strong><small>/100</small></span><span>→</span></button>)}</div>
    <div className="pagination"><span>{filtered.length} tools · page {currentPage} of {pages}</span><div><button disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>Previous</button><button disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>Next</button></div></div>
  </section>
}

function LanguageAssessment({ profile }: { profile: LanguageProfile }) {
  const strengths = profile.metrics.filter((metric) => metric.interpretation === 'favourable')
  const watch = profile.metrics.filter((metric) => metric.interpretation === 'unfavourable')
  const format = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1)
  const ordinal = (value: number) => { const rounded = Math.round(value); const mod100 = rounded % 100; const suffix = mod100 >= 11 && mod100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[rounded % 10] ?? 'th'; return `${rounded}${suffix}` }
  return <section className="language-profile"><div className="language-heading"><div><span className="language-chip">{profile.language}</span><strong>Static-analysis observations</strong></div><small>Compared only with compatible {profile.language} projects; no points awarded.</small></div>{(strengths.length > 0 || watch.length > 0) && <div className="signal-grid"><div className="signal strength"><span>Favourable signals</span>{strengths.map((metric) => <p key={metric.check_id}><strong>{metric.label}</strong><small>{format(metric.value)} {metric.unit}</small></p>)}</div><div className="signal watch"><span>Review signals</span>{watch.map((metric) => <p key={metric.check_id}><strong>{metric.label}</strong><small>{format(metric.value)} {metric.unit} · not necessarily a defect</small></p>)}</div></div>}<div className="profile-metrics">{profile.metrics.map((metric) => <div key={metric.check_id}><span>{metric.label}</span><strong>{format(metric.value)} <small>{metric.unit}</small></strong><em>{metric.percentile === null ? 'Cohort baseline pending' : `${ordinal(metric.percentile)} observed-value percentile`} · n={metric.cohort_size}</em></div>)}</div>{profile.metrics.length === 0 && <p className="empty-profile">No normalized analyzer measurements are available for this language yet.</p>}</section>
}

function PracticeReport({ ranking, repository }: { ranking: AwardRanking; repository: Record<string, unknown> }) {
  const cards: { key: CategoryKey; facts: [string, boolean][] }[] = [
    { key: 'testing', facts: [['Test suite', bool(repository.test_path_present)], ['Test configuration', bool(repository.test_config_present)], ['Test data', bool(repository.test_data_present)]] },
    { key: 'automation', facts: [['Continuous integration', bool(repository.ci_workflow_present)], ['Dependency updates', bool(repository.dependency_automation_present)], ['Release automation', bool(repository.release_automation_present)]] },
    { key: 'documentation', facts: [['README', bool(repository.readme_present)], ['Documentation tree', bool(repository.documentation_path_present)], ['Examples or tutorials', bool(repository.examples_present)]] },
    { key: 'stewardship', facts: [['Licence', bool(repository.licence_file_present)], ['Contribution guide', bool(repository.contribution_guide_present)], ['Code of conduct', bool(repository.code_of_conduct_present)], ['Issue templates', bool(repository.issue_templates_present)], ['Citation metadata', bool(repository.citation_metadata_present)], ['Changelog', bool(repository.changelog_present)]] },
    { key: 'reproducibility', facts: [['Dependency manifest', bool(repository.dependency_manifest_present)], ['Lock file', bool(repository.lockfile_present)], ['Container or dev environment', bool(repository.container_spec_present)]] },
  ]
  return <section className="practice-report"><div className="section-label"><span>Upstream practice report</span><small>Observed at commit {(repository.observed_commit as string)?.slice(0, 10) || 'unknown'}</small></div><div className="practice-grid">{cards.map(({ key, facts }) => { const info = categoryInfo[key]; const score = ranking.breakdown[key]; const present = facts.filter(([, value]) => value).length; return <article key={key}><header><div><h3>{info.title}</h3><p>{info.description}</p></div><strong>{score}<small>/{info.maximum}</small></strong></header><div className="fact-list">{facts.map(([label, value]) => <span className={value ? 'present' : 'absent'} key={label}>{value ? '✓' : '–'} {label}</span>)}</div><footer><span>{present}/{facts.length} signals observed</span><i><b style={{ width: `${score * 100 / info.maximum}%` }} /></i></footer></article> })}</div></section>
}

function PackageProfile({ pkg, ranking, results, profiles }: { pkg: PackageSummary; ranking?: AwardRanking; results: CheckResult[]; profiles: LanguageProfile[] }) {
  const repository = repoObservation(results)
  const publishedResults = results.filter((result) => result.check_id !== 'RECIPE-TEST-DEPTH-001')
  const contracts = publishedResults.filter((result) => result.result_kind === 'CONTRACT')
  const testsFound = bool(repository.test_path_present)
  return <article className="package-profile" id="profile">
    <header className="package-heading"><div><p className="eyebrow">{pkg.category.replaceAll('_', ' ')}</p><h2>{pkg.name} <span>{pkg.version}</span></h2><p>{pkg.description}</p><div className="profile-links"><a href={pkg.upstream_url}>Open upstream repository ↗</a><span>Bioconda {pkg.build} · {pkg.subdir}</span></div></div>{ranking && <div className="profile-score"><AwardPill ranking={ranking} /><strong>{ranking.score}<small>/100</small></strong><span>Upstream practice score</span><small>Provisional pilot rubric</small></div>}</header>
    <section className={`test-answer ${testsFound ? 'tests-yes' : 'tests-no'}`}><span className="test-icon">{testsFound ? '✓' : '?'}</span><div><p className="eyebrow">Does the upstream codebase have tests?</p><h3>{testsFound ? `Yes — ${num(repository.test_file_count)} test-path files observed` : 'No test suite was observed'}</h3><p>{testsFound ? 'Seebot found test files or a test directory in the pinned upstream tree. This confirms presence only; coverage and effectiveness are separate questions.' : 'The pinned tree did not expose a conventional test path. Non-standard or external tests may still exist.'}</p></div></section>
    {ranking && <PracticeReport ranking={ranking} repository={repository} />}
    <section className="codebase-facts"><div className="section-label"><span>Codebase snapshot</span><small>Pinned upstream repository</small></div><div className="codebase-stat-grid"><div><strong>{num(repository.file_count).toLocaleString()}</strong><span>repository files</span></div><div><strong>{num(repository.source_file_count).toLocaleString()}</strong><span>recognized source files</span></div><div><strong>{num(repository.ci_workflow_count)}</strong><span>CI workflow files</span></div><div><strong>{Object.keys((repository.language_file_counts as Record<string, number>) ?? {}).join(' + ') || (pkg.languages ?? []).join(' + ') || '—'}</strong><span>observed source languages</span></div></div></section>
    <section className="runtime-section"><div className="section-label"><span>Installed tool behaviour</span><small>Independent Pixi environment · not part of the upstream award</small></div><div className="contract-grid">{contracts.map((result) => <div key={result.check_id}><span className={`status status-${displayStatus(result).toLowerCase()}`}>{displayStatus(result)}</span><strong>{contractTitle(result.check_id)}</strong></div>)}</div></section>
    <section className="assessment-section"><div className="section-label"><span>Code health signals</span><small>Language-specific static analysis · not a quality score</small></div>{profiles.map((profile) => <LanguageAssessment key={profile.language} profile={profile} />)}{profiles.length === 0 && <p className="empty-profile">No normalized source-analysis profile is published yet.</p>}</section>
    <section className="checks-section"><div className="section-label"><span>Recorded observations</span><small>{publishedResults.length} checks across upstream, source, and runtime domains</small></div>{publishedResults.map((result) => <ResultRow key={result.check_id} result={result} />)}</section>
  </article>
}

export default function App() {
  const [results, setResults] = useState<CheckResult[]>([])
  const [packages, setPackages] = useState<PackageSummary[]>([])
  const [rankingData, setRankingData] = useState<RankingData | null>(null)
  const [profiles, setProfiles] = useState<ProfilesData | null>(null)
  const [selected, setSelected] = useState('')
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { Promise.all([
    fetch(`${import.meta.env.BASE_URL}data/checks.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Checks returned ${response.status}`))),
    fetch(`${import.meta.env.BASE_URL}data/packages.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Packages returned ${response.status}`))),
    fetch(`${import.meta.env.BASE_URL}data/rankings.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Rankings returned ${response.status}`))),
    fetch(`${import.meta.env.BASE_URL}data/profiles.json`).then((response) => response.ok ? response.json() : Promise.reject(new Error(`Profiles returned ${response.status}`))),
  ] as const).then(([checkRows, packageRows, rankingRows, profileRows]: [CheckResult[], PackageSummary[], RankingData, ProfilesData]) => { setResults(checkRows); setPackages(packageRows); setRankingData(rankingRows); setProfiles(profileRows); const requested = new URLSearchParams(window.location.search).get('tool'); setSelected(packageRows.find((pkg) => pkg.name === requested)?.package_id ?? packageRows[0]?.package_id ?? '') }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown data error')) }, [])
  const rankings = rankingData?.rankings ?? []
  const selectedPackage = packages.find((pkg) => pkg.package_id === selected)
  const selectedRanking = rankings.find((ranking) => ranking.package_id === selected)
  const selectedResults = useMemo(() => results.filter((result) => result.package_id === selected), [results, selected])
  const selectPackage = (id: string) => { setSelected(id); const pkg = packages.find((item) => item.package_id === id); if (pkg) window.history.replaceState({}, '', `${import.meta.env.BASE_URL}?tool=${encodeURIComponent(pkg.name)}#profile`); window.setTimeout(() => document.getElementById('profile')?.scrollIntoView({ behavior: 'smooth' }), 0) }
  return <><header className="site-header"><a className="brand" href={import.meta.env.BASE_URL}><span>SB</span>Seebot</a><nav><a href="#overview">Overview</a><a href="#rankings">Awards</a><a href="#tools">Projects</a><a href="https://github.com/happykhan/seebot">Method & code ↗</a></nav></header><main>
    <section className="hero"><div><p className="eyebrow">Bioconda upstream software audit</p><h1>What is strong?<br /><em>What needs attention?</em></h1><p>Seebot turns observable upstream engineering practices into readable project reports: tests, automation, documentation, stewardship, reproducibility, code signals, and installed behaviour.</p></div><aside><span>Current pilot</span><strong>{packages.length || '—'}<small>/10</small></strong><p>tools published before the rubric and cohort are frozen</p></aside></section>
    {error && <p className="load-error">Could not load the published dataset: {error}</p>}
    {rankingData && <><CohortSnapshot rankings={rankings} results={results} /><Leaderboard rankings={rankings} onSelect={selectPackage} /><ToolDirectory rankings={rankings} selected={selected} onSelect={selectPackage} /></>}
    {selectedPackage && <PackageProfile pkg={selectedPackage} ranking={selectedRanking} results={selectedResults} profiles={profiles?.profiles.find((row) => row.package_id === selected)?.languages ?? []} />}
    {!error && !selectedPackage && <p className="loading">Loading published pilot data…</p>}
  </main><footer className="site-footer"><span>Seebot development pilot · rubric {rankingData?.rubric_version ?? '—'}</span><span>{rankingData?.scope_note ?? 'Observations are not scientific validation.'}</span></footer></>
}
