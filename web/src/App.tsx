import { useEffect, useMemo, useState } from 'react'
import { NavBar } from '@genomicx/ui'
import { useLocation } from 'react-router-dom'
import { AggregateTrend, compatibleMetricLanguages, DistributionPlot, formatNumber, numeric, quantile, selectMetricPoints, SoftwareTimeSeries } from './charts'
import { contractCatalogue, describeRule, historyDefinitions, metricDefinitions, practiceDescriptions, ruleDocumentationUrl, type HistoryMetric } from './catalogue'
import { loadPublishedDataset } from './dataset'
import { FindingsTable } from './FindingsTable'
import { filterSoftware, practiceAreas, projectAchievements, softwareHref, type PracticeArea, type SoftwareFilters } from './projects'
import { describeSeverity, summarizeRules } from './presentation'
import type { ContractObservation, Dataset, MetricPoint, ObservationStatus, ProbeObservation, ProjectSummary, SourceSnapshot } from './types'
import { InfoTip, SeebotIcon, SelectField } from './ui'

const statusText: Record<ObservationStatus, string> = {
  PASS: 'Handled gracefully', FAIL: 'Needs improvement', OBSERVED: 'Observed', NOT_OBSERVED: 'Not observed',
  NOT_APPLICABLE: 'Not applicable', UNTESTABLE: 'Could not assess', ERROR: 'Audit error', NOT_RUN: 'Not run',
  NOT_EXISTING: 'Software not yet present',
}

function pretty(value: string | null): string { return value ? value.replaceAll('_', ' ') : 'Not classified' }
function StatusBadge({ status }: { status: ObservationStatus }) { return <span className={`status-badge status-${status.toLowerCase().replaceAll('_', '-')}`}>{statusText[status]}</span> }

function AchievementList({ project, linked = false }: { project: ProjectSummary, linked?: boolean }) {
  const active = projectAchievements(project)
  if (!active.length) return null
  return <div className="achievement-list" aria-label="Best-practice areas">{active.map((key) => {
    const content = <><span aria-hidden="true">{practiceAreas[key].short}</span><InfoTip>{practiceAreas[key].description}</InfoTip></>
    return linked ? <a key={key} href={softwareHref({ exemplar: key })} aria-label={practiceAreas[key].description}>{content}</a> : <span key={key} aria-label={practiceAreas[key].description}>{content}</span>
  })}</div>
}

function Overview({ dataset }: { dataset: Dataset }) {
  const achievementCount = (area: PracticeArea) => dataset.projects.filter((project) => projectAchievements(project).includes(area)).length
  const cards = [
    { count: achievementCount('repository'), title: 'Repository', text: 'Software meeting the reviewed documentation, testing, continuous-integration and repository-maintenance practices.', href: softwareHref({ exemplar: 'repository' }) },
    { count: achievementCount('source'), title: 'Source', text: 'Software with a complete current source assessment across its identified implementation languages.', href: softwareHref({ exemplar: 'source' }) },
    { count: achievementCount('usage'), title: 'Usage', text: 'Software meeting every applicable check for help, execution, output and handling of problematic input.', href: softwareHref({ exemplar: 'usage' }) },
    { count: achievementCount('dependencies'), title: 'Dependencies', text: 'Software with resolved runtime dependencies scanned and no known vulnerability advisories returned.', href: softwareHref({ exemplar: 'dependencies' }) },
  ]
  return <>
    <section className="hero"><div><p className="eyebrow">Seebot</p><h1>A review of bioinformatics software practices</h1><p>Seebot reports on how bioinformatics tools are maintained, structured, documented and how their command-line interfaces behaved with valid and deliberately awkward input.</p><div className="hero-actions"><a href="#/explore">Explore the results</a><a href="#/software">Browse software</a></div></div></section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Examples</p><h2>Software with best practices</h2></div><p>Open a category to see the software that met all of its stated checks.</p></div>
      <div className="best-practice-grid">{cards.map((card) => <a href={card.href} key={card.title}><strong>{card.count}</strong><div><h3>{card.title}</h3><p>{card.text}</p></div><span>View software →</span></a>)}</div>
    </section>
    <RepositoryPracticePanel dataset={dataset} />
    <SourceHealthPanel dataset={dataset} />
    <RobustnessPanel dataset={dataset} />
    <DependencyHealthPanel dataset={dataset} />
  </>
}

function LanguagePanel({ dataset }: { dataset: Dataset }) {
  const rows = Object.entries(dataset.aggregate.primary_language_counts).sort((a, b) => b[1] - a[1])
  const maximum = Math.max(...rows.map(([, count]) => count), 1)
  return <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Languages</p><h2>Primary implementation language</h2></div><p>The principal language identified for each software package in the current assessment.</p></div>
    <div className="language-bars">{rows.map(([language, count]) => <a href={softwareHref({ language })} key={language}><span>{language}</span><i><b style={{ width: `${count * 100 / maximum}%` }} /></i><strong>{count}</strong></a>)}</div>
  </section>
}

function RepositoryPracticePanel({ dataset }: { dataset: Dataset }) {
  const total = dataset.summary.assessed_projects
  return <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Repository health</p><h2>Repository best practices</h2></div><p>Select a practice to see software where it was not found.</p></div>
    <div className="practice-grid">{Object.entries(dataset.aggregate.repository_practice_counts).map(([name, count]) => <a href={softwareHref({ practice: name, outcome: 'fail' })} key={name}><div><span><strong>{count}/{total}</strong>{name}<InfoTip>{practiceDescriptions[name] ?? 'A reviewed repository practice.'}</InfoTip></span><b>{total - count} not found →</b></div><i><em style={{ width: `${100 * count / total}%` }} /></i></a>)}</div>
  </section>
}

function SourceHealthPanel({ dataset }: { dataset: Dataset }) {
  const languages = Object.keys(dataset.aggregate.component_language_counts).sort()
  const [language, setLanguage] = useState(languages[0] ?? 'all')
  const keys = ['maximum_file_lines', 'function_length_p90', 'complexity_p90', 'documentation_coverage', 'duplication_percent', 'lint_findings_per_kloc']
  return <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Source health</p><h2>Source-code measurements by language</h2></div><SelectField label="Language" value={language} onChange={(event) => setLanguage(event.target.value)}>{languages.map((value) => <option key={value} value={value}>{value}</option>)}</SelectField></div>
    <div className="source-summary-grid">{keys.map((key) => {
      const definition = metricDefinitions[key]
      const values = (dataset.aggregate.metric_points[key] ?? []).filter((point) => point.language === language).map((point) => point.value)
      return <a href={`#/explore?metric=${key}&language=${encodeURIComponent(language)}#software-observations`} key={key}><span>{definition.shortLabel}<InfoTip>{definition.explanation}</InfoTip></span><strong>{values.length ? formatNumber(quantile(values, .5), definition.unit) : 'Not available'}</strong><small>{values.length ? `Median across ${values.length} ${language} observations` : `No ${language} observations`}</small><b>Explore distribution →</b></a>
    })}</div>
  </section>
}

function RobustnessPanel({ dataset }: { dataset: Dataset }) {
  const total = dataset.summary.assessed_projects
  return <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Command-line robustness</p><h2>Response to problematic user input</h2></div><p>These checks examine missing, malformed and incompatible input, as well as valid files containing no biological records. Software should return useful errors for unusable input and valid empty results when there are simply no records to process. Select a scenario to see software that did not meet the expected behaviour.</p></div>
    <div className="robustness-grid">{dataset.aggregate.robustness.map((row) => { const pass = row.statuses.PASS ?? 0; const fail = row.statuses.FAIL ?? 0; const na = row.statuses.NOT_APPLICABLE ?? 0; return <a href={softwareHref({ robustness: row.check_id, outcome: 'fail' })} key={row.check_id}><div><span><strong>{row.label}</strong><small>{pass} handled · {fail} needs improvement · {na} N/A</small></span><b>{fail} to review →</b></div><i><em className="segment-pass" style={{ width: `${100 * pass / total}%` }} /><em className="segment-fail" style={{ width: `${100 * fail / total}%` }} /><em className="segment-na" style={{ width: `${100 * na / total}%` }} /></i></a> })}</div>
  </section>
}

const dependencyCoverageText: Record<string, { label: string, description: string }> = {
  runtime_scanned: { label: 'Runtime dependencies scanned', description: 'Exact packages from the audited installation or a supported runtime lockfile were checked for known advisories.' },
  declared_unresolved: { label: 'Dependencies declared', description: 'Runtime dependencies were declared, but no exact installed or locked version could be matched to advisories.' },
  installed_inventory_only: { label: 'Installed environment recorded', description: 'The resolved Pixi environment was recorded, but its packages could not be mapped to an OSV-supported ecosystem.' },
  development_only: { label: 'Development files only', description: 'Supported files were found only under documentation, test, benchmark or development paths, so they are not treated as the software runtime dependency set.' },
  no_supported_input: { label: 'No dependency input found', description: 'No runtime declaration, installed ecosystem package or supported lockfile was available.' },
  audit_error: { label: 'Dependency scan incomplete', description: 'The dependency scan could not produce a usable observation.' },
}

function DependencyHealthPanel({ dataset }: { dataset: Dataset }) {
  const counts = dataset.aggregate.dependency_coverage_counts ?? {}
  return <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Dependencies</p><h2>Runtime dependency advisory coverage</h2></div><p>Seebot combines dependencies declared in the repository with exact package versions found in the isolated Pixi environment used to run each tool.</p></div>
    <div className="dependency-coverage-grid">{Object.entries(dependencyCoverageText).map(([key, text]) => <a href={softwareHref({ dependencyCoverage: key })} key={key}><strong>{counts[key] ?? 0}</strong><span>{text.label}<InfoTip>{text.description}</InfoTip></span><small>View software →</small></a>)}</div>
  </section>
}

function Explorer({ dataset }: { dataset: Dataset }) {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const initialMetric = params.get('metric') ?? 'days_since_last_commit'
  const [metric, setMetric] = useState(dataset.aggregate.metric_points[initialMetric]?.length ? initialMetric : 'days_since_last_commit')
  const [metricLanguage, setMetricLanguage] = useState(params.get('language') ?? 'all')
  const [historyMetric, setHistoryMetric] = useState<HistoryMetric>('physical_lines')
  const [historyLanguage, setHistoryLanguage] = useState('all')
  const definition = metricDefinitions[metric]
  const languages = Object.keys(dataset.aggregate.component_language_counts).sort()
  const metricPoints = dataset.aggregate.metric_points[metric] ?? []
  const metricLanguages = compatibleMetricLanguages(metricPoints)
  const points = selectMetricPoints(metricPoints, metricLanguage)
  useEffect(() => {
    if (metricLanguage !== 'all' && !metricLanguages.includes(metricLanguage)) setMetricLanguage('all')
  }, [metric, metricLanguage, metricLanguages.join('|')])
  return <>
    <section className="page-intro"><p className="eyebrow">Explore</p><h1>Patterns across bioinformatics software</h1><p>Compare repository practices, source-code measurements, command-line behaviour and automated code-review findings across the assessed software.</p></section>
    <LanguagePanel dataset={dataset} />
    <section className="section-block" id="software-observations"><div className="section-heading"><div><p className="eyebrow">Distributions</p><h2>Software observations</h2></div><div className="select-row"><SelectField label="Measurement" value={metric} onChange={(event) => setMetric(event.target.value)}>{Object.entries(metricDefinitions).filter(([key]) => dataset.aggregate.metric_points[key]?.length).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</SelectField>{metricLanguages.length > 0 && <SelectField label="Language" value={metricLanguage} onChange={(event) => setMetricLanguage(event.target.value)}><option value="all">All compatible observations</option>{metricLanguages.map((value) => <option key={value} value={value}>{value}</option>)}</SelectField>}</div></div>
      <p className="section-description">{definition.explanation} Hover over the box to see its boundaries, or over a point to identify the software and its value.</p><DistributionPlot points={points} label={definition.label} unit={definition.unit} software={dataset.projects} />
    </section>
    <DependencyHealthPanel dataset={dataset} />
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Change over time</p><h2>Source-code trends</h2></div><div className="select-row"><SelectField label="Measurement" value={historyMetric} onChange={(event) => setHistoryMetric(event.target.value as HistoryMetric)}>{Object.entries(historyDefinitions).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</SelectField><SelectField label="Language" value={historyLanguage} onChange={(event) => setHistoryLanguage(event.target.value)}><option value="all">All primary languages</option>{languages.map((value) => <option key={value} value={value}>{value}</option>)}</SelectField></div></div>
      <p className="section-description">The line shows the median and the shaded band shows the middle 50% of software available at each annual snapshot. This aggregate remains readable as the collection grows; individual histories appear in each software report.</p><AggregateTrend dataset={dataset} metric={historyMetric} language={historyLanguage} />
    </section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Automated code review</p><h2>Static-analysis findings</h2></div><p>Browse the findings reported by language-specific linters and security analyzers. The information icon beside each rule explains what it identifies.</p></div><FindingsTable rows={dataset.aggregate.native_rules} /></section>
  </>
}

function ProjectDirectory({ projects }: { projects: ProjectSummary[] }) {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const fixed: SoftwareFilters = { tag: params.get('tag') ?? undefined, exemplar: params.get('exemplar') ?? undefined, practice: params.get('practice') ?? undefined, robustness: params.get('robustness') ?? undefined, dependencyCoverage: params.get('dependencyCoverage') ?? undefined, outcome: params.get('outcome') ?? undefined }
  const [query, setQuery] = useState(params.get('query') ?? '')
  const [language, setLanguage] = useState(params.get('language') ?? 'all')
  const [category, setCategory] = useState(params.get('category') ?? 'all')
  const languages = [...new Set(projects.flatMap((project) => project.languages))].sort()
  const categories = [...new Set(projects.map((project) => project.category).filter(Boolean) as string[])].sort()
  const visible = useMemo(() => filterSoftware(projects, { ...fixed, query, language, category }), [category, language, location.search, projects, query])
  const filterLabel = fixed.tag ? `Tagged “${fixed.tag}”` : fixed.practice ? `${fixed.outcome === 'pass' ? 'Present' : 'Not found'}: ${fixed.practice}` : fixed.robustness ? `${contractCatalogue[fixed.robustness]?.label ?? fixed.robustness}: needs improvement` : fixed.dependencyCoverage ? dependencyCoverageText[fixed.dependencyCoverage]?.label ?? pretty(fixed.dependencyCoverage) : fixed.exemplar ? `${pretty(fixed.exemplar)} best practices` : null
  return <>
    <section className="page-intro"><p className="eyebrow">Software directory</p><h1>Find a bioinformatics software report</h1><p>Search by name or browse by language, category and the assessment filters linked throughout Seebot.</p></section>
    <section className="directory">{filterLabel && <div className="active-filter"><span>Current filter</span><strong>{filterLabel}</strong><a href="#/software">Clear filter ×</a></div>}
      <div className="directory-controls"><label className="search-field"><span>Search</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Software, format or category" /></label><SelectField label="Language" value={language} onChange={(event) => setLanguage(event.target.value)}><option value="all">All languages</option>{languages.map((value) => <option key={value}>{value}</option>)}</SelectField><SelectField label="Category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((value) => <option key={value} value={value}>{pretty(value)}</option>)}</SelectField></div>
      <div className="project-list">{visible.sort((a, b) => a.name.localeCompare(b.name)).map((project) => <a href={`#/software/${project.id}?back=${encodeURIComponent(location.pathname + location.search)}`} key={project.id}><div><strong>{project.name}</strong><p>{project.description}</p><small>{pretty(project.category)} · {project.languages.join(' + ')}</small></div><AchievementList project={project} /><b>→</b></a>)}</div><p className="result-count">{visible.length} software report{visible.length === 1 ? '' : 's'}</p>
    </section>
  </>
}

function failureExplanation(probe: ProbeObservation): string {
  if (probe.status === 'PASS') return 'The observed behaviour met the expectation for this check.'
  const exit = probe.observed.exit_code
  const diagnostic = probe.observed.diagnostic_class
  const timedOut = probe.observed.timed_out
  if (timedOut === true) return 'The command did not finish within the assessment time limit.'
  if (exit === 0) return 'The command returned exit code 0, so the problematic input was accepted instead of reported as an error.'
  if (diagnostic == null || diagnostic === 'NONE') return 'The command failed without a useful diagnostic on standard error.'
  if (probe.observed.internal_crash_marker === true) return 'The output contained an internal exception or crash marker.'
  if (probe.observed.inappropriate_side_effect === true) return 'The command created output that could be mistaken for a successful result.'
  return probe.notes ?? 'The observed behaviour did not meet one or more expectations for this check.'
}

function ContractTable({ contracts }: { contracts: ContractObservation[] }) {
  if (!contracts.length) return <p className="empty-state">No installed command-line assessment has been published for this software yet.</p>
  return <div className="contract-list">{contracts.map((contract) => {
    const entry = contractCatalogue[contract.check_id] ?? { label: contract.label, explanation: 'A reviewed command-line behaviour.', expectation: 'Return a clear and appropriate result.' }
    return <details key={contract.check_id}><summary><div><span><strong>{entry.label}</strong><code>{contract.check_id}</code></span><small>{entry.explanation}</small></div><span className="summary-result"><StatusBadge status={contract.status} /><b aria-hidden="true">⌄</b></span></summary><div className="contract-body"><p className="expectation"><strong>Expected:</strong> {entry.expectation}</p><div className="probe-list">{contract.probes.map((probe) => <article key={probe.probe_id}><div className="probe-heading"><StatusBadge status={probe.status} /><code>{probe.command?.join(' ') ?? probe.probe_id}</code></div><p className={probe.status === 'PASS' ? 'finding-pass' : 'finding-fail'}>{failureExplanation(probe)}</p><dl><div><dt>Exit code</dt><dd>{String(probe.observed.exit_code ?? 'N/A')}</dd></div><div><dt>Diagnostic</dt><dd>{String(probe.observed.diagnostic_class ?? 'N/A')}</dd></div><div><dt>Timed out</dt><dd>{String(probe.observed.timed_out ?? false)}</dd></div></dl>{(probe.output?.stderr || probe.output?.stdout) && <div className="command-output">{probe.output.stderr && <div><strong>Standard error</strong><pre>{probe.output.stderr}</pre></div>}{probe.output.stdout && <div><strong>Standard output</strong><pre>{probe.output.stdout}</pre></div>}</div>}</article>)}</div></div></details>
  })}</div>
}

function comparison(dataset: Dataset, point: MetricPoint | undefined, key: string, language?: string) {
  if (!point) return null
  const definition = metricDefinitions[key]
  const peers = (dataset.aggregate.metric_points[key] ?? []).filter((candidate) => !language || candidate.language === language)
  if (peers.length < 2 || definition.direction === 'neutral') return { percentile: 50, text: `${peers.length} comparable observation${peers.length === 1 ? '' : 's'}` }
  const favourable = peers.filter((candidate) => definition.direction === 'higher' ? candidate.value <= point.value : candidate.value >= point.value).length
  const percentile = Math.round(100 * favourable / peers.length)
  return { percentile, text: `${percentile}th percentile among ${peers.length}${language ? ` ${language}` : ''} observations` }
}

function ComparisonCard({ label, value, explanation, comparison: result }: { label: string, value: string, explanation: string, comparison: ReturnType<typeof comparison> }) {
  const className = !result ? '' : result.percentile >= 67 ? 'comparison-high' : result.percentile <= 33 ? 'comparison-low' : 'comparison-mid'
  return <article className={`comparison-card ${className}`} style={result ? { '--comparison': `${result.percentile}%` } as React.CSSProperties : undefined}><span>{label}<InfoTip>{explanation}</InfoTip></span><strong>{value}</strong>{result && <small>{result.text}</small>}</article>
}

function SourceCards({ snapshots, project, dataset }: { snapshots: SourceSnapshot[], project: ProjectSummary, dataset: Dataset }) {
  const definitions: { key: string, field: [keyof SourceSnapshot['metrics'], string] }[] = [
    { key: 'production_lines', field: ['inventory', 'physical_lines'] }, { key: 'maximum_file_lines', field: ['files', 'maximum'] },
    { key: 'percent_files_over_500', field: ['files', 'percent_over_500'] }, { key: 'function_length_p90', field: ['functions', 'length_percentile_90'] },
    { key: 'complexity_p90', field: ['complexity', 'percentile_90'] }, { key: 'documentation_coverage', field: ['documentation', 'coverage_percent'] },
    { key: 'duplication_percent', field: ['duplication', 'duplicated_line_percent'] },
  ]
  if (!snapshots.length) return <p className="empty-state">No current source-code assessment has been published for this software yet.</p>
  return <div className="source-components">{snapshots.map((snapshot) => <article key={snapshot.language}><header><strong>{snapshot.language}</strong><StatusBadge status={snapshot.status} /></header><div className="metric-grid">{definitions.map(({ key, field }) => {
    const definition = metricDefinitions[key]
    let value = numeric(snapshot.metrics[field[0]], field[1]); if (key === 'documentation_coverage' && value != null) value = Math.min(100, value)
    const point = value == null ? undefined : { project_id: project.id, language: snapshot.language, value }
    return <ComparisonCard key={key} label={definition.shortLabel} value={formatNumber(value, definition.unit)} explanation={definition.explanation} comparison={comparison(dataset, point, key, snapshot.language)} />
  })}</div>{snapshot.native_findings.map((finding, index) => {
    const analyzer = finding.analyzer ?? 'not applicable'
    const summary = summarizeRules(finding.rules)
    return <details className="finding-summary" key={`${finding.kind}-${finding.analyzer}-${index}`}><summary><span>{finding.kind === 'lint' ? 'Code-review findings' : 'Security findings'} · {analyzer}</span><strong>{finding.status === 'OBSERVED' ? formatNumber(finding.finding_count ?? 0) : statusText[finding.status]} <b aria-hidden="true">⌄</b></strong></summary>{summary.visible.length > 0 && <div className="finding-rule-list">{summary.visible.map((rule) => {
      const url = ruleDocumentationUrl(analyzer, rule.rule)
      const label = <code>{rule.rule}</code>
      return <div key={rule.rule}><div><strong>{url ? <a href={url}>{label}</a> : label}</strong><span>{describeRule(analyzer, rule.rule)}</span></div><b>{formatNumber(rule.count)}</b></div>
    })}{summary.hiddenTypeCount > 0 && <p>{formatNumber(summary.hiddenFindingCount)} other findings across {summary.hiddenTypeCount} rule type{summary.hiddenTypeCount === 1 ? '' : 's'}.</p>}</div>}</details>
  })}</article>)}</div>
}

function ProjectReport({ project, dataset }: { project: ProjectSummary, dataset: Dataset }) {
  const location = useLocation()
  const [historyMetric, setHistoryMetric] = useState<HistoryMetric>('physical_lines')
  const currentSource = project.source_snapshots.filter((row) => row.snapshot_date === dataset.snapshot_date)
  const dependency = project.dependency_advisories.observed
  const advisories = dependency.runtime_advisories
  const declaredDependencies = Array.isArray(dependency.declared_dependencies) ? dependency.declared_dependencies as Record<string, unknown>[] : []
  const runtimeDeclarations = declaredDependencies.filter((row) => row.role === 'runtime')
  const back = new URLSearchParams(location.search).get('back') ?? '/software'
  const activityCards = [
    ['days_since_last_commit', numeric(project.repository.activity, 'days_since_last_non_bot_commit'), 'days ago'],
    ['commits_last_12_months', numeric(project.repository.activity, 'commits_last_12_months'), ''],
    ['active_months_last_12_months', numeric(project.repository.activity, 'active_months_last_12_months'), 'of 12'],
    ['days_since_latest_release', numeric(project.repository.releases, 'days_since_latest_release'), 'days ago'],
  ] as const
  return <article className="project-report"><a className="back-link" href={`#${back}`}>← Back to search</a>
    <header><div><p className="eyebrow"><a href={softwareHref({ category: project.category ?? undefined })}>{pretty(project.category)}</a></p><h1>{project.name}</h1><p>{project.description}</p><div className="tag-row">{project.languages.map((language) => <a href={softwareHref({ language })} key={language}>{language}</a>)}{project.tags.map((tag) => <a href={softwareHref({ tag })} key={tag}>{pretty(tag)}</a>)}</div></div><aside><span>Software report</span><AchievementList project={project} linked /><small>Reviewed commit {project.repository.snapshot_commit.slice(0, 12)}</small><a href={project.repository.url}>Open GitHub repository ↗</a></aside></header>
    <section className="report-facts"><div><span>Reviewed executable</span><strong>{project.primary_executable ?? 'Not identified'}</strong></div><div><span>Installed software</span><strong>{project.installation.artifact} {project.installation.version}</strong></div><div><span>Assessment environment</span><strong>{dataset.methodology.canonical_platform}</strong></div></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Repository health</p><h2>Maintenance and repository practices</h2></div><p>Current activity, releases, documentation, standard test structure and continuous integration.</p></div><div className="repo-layout"><div className="practice-checks">{Object.entries(project.repository.practices).map(([name, present]) => <a href={softwareHref({ practice: name, outcome: present ? 'pass' : 'fail' })} key={name}><span className={present ? 'present' : 'absent'}>{present ? '✓' : '—'}</span><strong>{name}</strong><InfoTip>{practiceDescriptions[name]}</InfoTip></a>)}</div><div className="activity-cards">{activityCards.map(([key, value, unit]) => { const definition = metricDefinitions[key]; const point = value == null ? undefined : { project_id: project.id, value }; return <ComparisonCard key={key} label={definition.shortLabel} value={formatNumber(value, unit)} explanation={definition.explanation} comparison={comparison(dataset, point, key)} /> })}</div></div></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Usage health</p><h2>Installed command-line behaviour</h2></div><p>The reviewed executable is asked for help and version information, run with a small representative dataset, and challenged with missing, empty, malformed and incompatible input. The expected response is a clear exit status and useful message, with valid output only when the command succeeds.</p></div><ContractTable contracts={project.contracts} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Source health</p><h2>Current source-code measurements</h2></div><p>Structural measurements and language-specific analyzer results for the software’s implementation. Each information icon defines the measurement; percentile bands compare it with software assessed in the same language.</p></div><SourceCards snapshots={currentSource} project={project} dataset={dataset} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Source history</p><h2>Source-code metrics over time</h2></div><SelectField label="Measurement" value={historyMetric} onChange={(event) => setHistoryMetric(event.target.value as HistoryMetric)}>{Object.entries(historyDefinitions).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</SelectField></div><p className="section-description">Annual values use the source present on 1 July. Seebot’s historical observation window begins in 2021; it does not indicate when the software was first created. Years marked “not yet present” have an explicit repository observation to that effect. “p90” is the value at or below which 90% of detected functions fall.</p><SoftwareTimeSeries project={project} metric={historyMetric} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Dependencies</p><h2>Runtime dependency vulnerabilities</h2></div><span className="dependency-coverage-status">{dependencyCoverageText[String(dependency.coverage_status)]?.label ?? 'Dependency scan incomplete'}</span></div><p className="section-description">{String(dependency.scanner_profile ?? 'The dependency assessment combines repository metadata and the audited installation environment.')}. Exact versions are checked when the project supplies a supported lockfile or the installed package exposes ecosystem metadata.</p>
      {runtimeDeclarations.length > 0 && <p className="dependency-source"><strong>Declared runtime dependencies:</strong> {runtimeDeclarations.map((row) => String(row.raw ?? row.name)).join(', ')}</p>}
      {Number(dependency.conda_package_count ?? 0) > 0 && <p className="dependency-source"><strong>Audited Pixi environment:</strong> {String(dependency.conda_package_count)} resolved Conda packages; {String(dependency.ecosystem_package_count ?? 0)} exact PyPI, Maven or npm packages checked by OSV.</p>}
      {Array.isArray(dependency.runtime_sources) && dependency.runtime_sources.length > 0 && <p className="dependency-source"><strong>Runtime input:</strong> {dependency.runtime_sources.join(', ')}</p>}
      {Array.isArray(dependency.development_sources) && dependency.development_sources.length > 0 && <p className="dependency-source"><strong>Development-only inputs found:</strong> {dependency.development_sources.join(', ')}</p>}
      {Array.isArray(advisories) && advisories.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Advisory</th><th>Ecosystem</th><th>Dependency</th><th>Version</th><th>Source</th><th>Impact characteristics</th></tr></thead><tbody>{(advisories as Record<string, unknown>[]).map((row) => <tr key={`${row.advisory_id}-${row.dependency}-${row.source}`}><td><code>{String(row.advisory_id)}</code></td><td>{String(row.ecosystem)}</td><td>{String(row.dependency)}</td><td>{String(row.resolved_version)}</td><td>{String(row.source ?? 'Runtime input')}</td><td className="severity-description">{Array.isArray(row.native_severity) && row.native_severity.length ? row.native_severity.map((value) => { const description = describeSeverity(String(value)); return <div key={String(value)}><span>{description.summary}</span>{description.vector && <details><summary>Show CVSS vector</summary><code>{description.vector}</code></details>}</div> }) : 'Unspecified'}</td></tr>)}</tbody></table></div> : dependency.coverage_status === 'runtime_scanned' ? <p className="empty-state">No known vulnerability advisories were returned for the resolved runtime dependencies.</p> : <p className="empty-state">{dependencyCoverageText[String(dependency.coverage_status)]?.description ?? String(dependency.reason ?? 'The dependency assessment did not produce a runtime observation.')}</p>}
    </section>
  </article>
}

function Methods({ dataset }: { dataset: Dataset }) {
  return <section className="methods-page"><p className="eyebrow">Methods</p><h1>How Seebot reviews bioinformatics software</h1><p className="methods-lead">Seebot measures practical software-engineering characteristics that affect whether bioinformatics software can be found, understood, maintained and used reliably. The assessment combines repository metadata, source-code analysis, controlled command-line exercises and dependency-advisory checks.</p>
    <div className="method-section"><h2>Study set and observation dates</h2><p>A discovery survey considered {dataset.methodology.candidate_survey_size} download-ranked package names and identified {dataset.methodology.eligible_cli_projects_found} eligible command-line tools. Each current report refers to a named repository commit and installed release reviewed on 1 July 2026. Source history begins in 2021 and uses the commit present on 1 July of each year. A missing historical point therefore means either that the software was not yet present or that the measurement could not be made; it does not identify the software’s date of origin.</p></div>
    <div className="method-section"><h2>Repository</h2><p>Repository observations describe the information and maintenance signals available to users and contributors. Seebot records days since the latest non-bot commit and published release, non-bot commits and active months during the preceding year, and whether the repository is explicitly archived. It also records a README, installation instructions, a worked usage example, licence and citation guidance, conventional unit-test files or framework configuration, and continuous integration that performs verification.</p></div>
    <div className="method-section"><h2>Source</h2><p>Source is analysed separately for each implementation language. The production-source selection excludes test fixtures, documentation, examples, generated output and vendored code. Measurements include physical lines, the longest file, the proportion of files above 500 lines, function-length and cyclomatic-complexity 90th percentiles, documented functions, repeated exact six-line blocks and language-specific static-analysis findings. Analyzer rules retain their native identifiers because their meaning and severity depend on the analyzer and language; the website provides a plain-language description alongside each identifier.</p></div>
    <div className="method-section"><h2>Usage</h2><p>Curated commands exercise the installed interface with small shared biological fixtures or a software-specific fixture where necessary. The review asks for help and version information, performs a representative miniature run, and observes the use of standard output and standard error. Robustness probes supply no arguments, missing files, zero-byte files, malformed data, a valid file of the wrong biological format, unknown options, invalid values and unwritable output locations. A separate no-data probe supplies a valid format containing zero biological records and checks that successful output remains structurally valid with zero records. For each probe Seebot records the command, exit status, standard streams, timeout and any output created.</p></div>
    <div className="method-section"><h2>Dependencies</h2><p>Dependency assessment combines repository and installation evidence. Seebot records Python dependencies declared in <code>pyproject.toml</code>, separating runtime, optional, build and development requirements. <a href="https://google.github.io/osv-scanner/supported-languages-and-lockfiles/">OSV-Scanner’s ecosystem-specific parsers</a> inspect supported repository lockfiles and manifests. Seebot also inventories the exact disposable Pixi environment used for executable checks and sends installed PyPI, Maven and npm names and versions to OSV-Scanner. The full resolved Conda package inventory is retained even when a package cannot be mapped to an OSV ecosystem. Perl projects with a <code>cpanfile</code> or <code>cpanfile.snapshot</code> are checked with <a href="https://metacpan.org/pod/cpan-audit">CPAN Audit</a>. Documentation, test and benchmark dependencies remain separate from runtime results.</p></div>
    <div className="method-section"><h2>Scope of the observations</h2><p>The repository, source, usage and dependency observations answer different practical questions about the reviewed software. The small executable runs establish interface behaviour and output structure for the chosen examples. Scientific accuracy, performance on representative research datasets, usability studies and long-term sustainability require additional study designs.</p></div>
  </section>
}

const guidanceSections: { area: PracticeArea, introduction: string, items: string[] }[] = [
  { area: 'repository', introduction: 'Help users understand, cite, install and contribute to the software before they run it.', items: ['State the software’s purpose and intended users near the start of the README.', 'Provide installation instructions that have been checked in a clean environment.', 'Include at least one representative command with its expected input and output.', 'State the software licence in a standard licence file.', 'Provide a citation file, publication reference or explicit citation instructions.', 'Keep unit tests in conventional locations and run them in continuous integration.', 'Run a verification workflow for supported platforms and language versions.', 'Publish named releases and maintain a concise record of user-visible changes.'] },
  { area: 'source', introduction: 'Keep the implementation understandable enough to review, test and change safely.', items: ['Separate production source from tests, fixtures, generated files and vendored code.', 'Keep modules and files focused; review unusually long files for mixed responsibilities.', 'Keep functions focused; review the longest and most complex functions first.', 'Document public functions, data structures and non-obvious scientific assumptions.', 'Run language-appropriate formatting, linting and static security analysis in CI.', 'Explain or fix recurring analyzer findings rather than suppressing them globally.', 'Reduce repeated source blocks when a shared function would express the intent clearly.', 'Review source measurements over time to identify sustained growth in complexity.'] },
  { area: 'usage', introduction: 'Make normal operation predictable and errors useful to people and automated workflows.', items: ['Provide useful -h or --help output with required inputs and a representative example.', 'Provide a version option that identifies the installed software release.', 'Use standard output for results and standard error for progress and diagnostics.', 'Return a non-zero exit code when the requested operation cannot be completed.', 'Run a small valid example and check the structure of every expected output.', 'Test missing paths, zero-byte input and syntactically malformed input.', 'Test valid FASTA, FASTQ, SAM, VCF or other inputs containing zero records and verify that the resulting output is also valid and empty.', 'Test a valid biological file of the wrong format and explain the incompatibility.', 'Test unknown options, invalid parameter values and unwritable output locations.'] },
  { area: 'dependencies', introduction: 'Make runtime requirements visible and keep known vulnerable versions out of releases.', items: ['Declare direct runtime dependencies in a standard machine-readable manifest.', 'Commit the ecosystem’s resolved lockfile when that is normal practice for an application.', 'Keep development, documentation and test requirements separate from runtime requirements.', 'Run the ecosystem-appropriate vulnerability check in continuous integration.', 'Review each advisory in the context of the resolved version and reachable functionality.', 'Update or replace affected dependencies and record any justified temporary exception.', 'Remove dependencies that are no longer used by production code.', 'Document external databases, reference data and network services required at runtime.'] },
]

function Guidance() {
  const [checked, setChecked] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('seebot-guidance-checklist') ?? '[]') as string[] } catch { return [] }
  })
  useEffect(() => { localStorage.setItem('seebot-guidance-checklist', JSON.stringify(checked)) }, [checked])
  const total = guidanceSections.reduce((sum, section) => sum + section.items.length, 0)
  const toggle = (id: string) => setChecked((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id])
  return <section className="methods-page guidance-page"><p className="eyebrow">Guidance</p><h1>Assess your own bioinformatics software</h1><p className="methods-lead">Use this practical checklist to review your project across repository, source, usage and dependency practices. Tick each item as you verify it; progress is saved in this browser.</p>
    <div className="checklist-progress"><div><strong>{checked.length} of {total}</strong><span>items reviewed</span></div><i><span style={{ width: `${100 * checked.length / total}%` }} /></i><button type="button" onClick={() => setChecked([])} disabled={!checked.length}>Reset checklist</button></div>
    <div className="guidance-checklist">{guidanceSections.map((section, sectionIndex) => { const complete = section.items.filter((_, itemIndex) => checked.includes(`${section.area}-${itemIndex}`)).length; return <article key={section.area}><header><span>0{sectionIndex + 1}</span><div><h2>{practiceAreas[section.area].label}</h2><p>{section.introduction}</p></div><strong>{complete}/{section.items.length}</strong></header><div>{section.items.map((item, itemIndex) => { const id = `${section.area}-${itemIndex}`; return <label className={checked.includes(id) ? 'checked' : ''} key={id}><input type="checkbox" checked={checked.includes(id)} onChange={() => toggle(id)} /><span aria-hidden="true">✓</span><em>{item}</em></label> })}</div></article> })}</div>
    <div className="guidance-note"><h2>Continue the assessment</h2><p>Engineering practice should be considered alongside scientific validation, performance and scalability, accessibility, privacy and data governance, interoperability, user support and long-term stewardship.</p></div>
  </section>
}

export default function App() {
  const location = useLocation()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { loadPublishedDataset().then(setDataset).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown data error')) }, [])
  const parts = location.pathname.split('/').filter(Boolean)
  const view = parts[0] || 'overview'
  const softwareView = view === 'software' || view === 'projects'
  const project = softwareView && parts[1] ? dataset?.projects.find((item) => item.id === parts[1]) : undefined
  const nav = <><a className="seebot-nav-link" href="#/">Overview</a><a className="seebot-nav-link" href="#/explore">Explore</a><a className="seebot-nav-link" href="#/software">Software</a><a className="seebot-nav-link" href="#/methods">Methods</a><a className="seebot-nav-link" href="#/guidance">Guidance</a></>
  const mobileNav = <><a className="gx-nav-dropdown-link" href="#/">Overview</a><a className="gx-nav-dropdown-link" href="#/explore">Explore</a><a className="gx-nav-dropdown-link" href="#/software">Software</a><a className="gx-nav-dropdown-link" href="#/methods">Methods</a><a className="gx-nav-dropdown-link" href="#/guidance">Guidance</a></>
  return <><NavBar appName="SEEBOT" appSubtitle="Bioinformatics software practices" version="1.0.0" icon={<SeebotIcon />} githubUrl="https://github.com/happykhan/seebot" actions={nav} mobileActions={mobileNav} /><main>
    {error && <p className="load-error">Could not load the published dataset: {error}</p>}{!error && !dataset && <p className="loading">Loading software observations…</p>}
    {dataset && view === 'overview' && <Overview dataset={dataset} />}{dataset && view === 'explore' && <Explorer dataset={dataset} />}
    {dataset && softwareView && !parts[1] && <ProjectDirectory projects={dataset.projects} />}{dataset && softwareView && project && <ProjectReport project={project} dataset={dataset} />}
    {dataset && softwareView && parts[1] && !project && <p className="load-error">Software report not found.</p>}{dataset && view === 'methods' && <Methods dataset={dataset} />}
    {(view === 'guidance' || view === 'about') && <Guidance />}
  </main><footer className="site-footer"><span>Seebot</span><nav><a href="#/methods">Methods</a><a href="#/guidance">Guidance</a><a href="https://github.com/happykhan/seebot">Source code</a></nav></footer></>
}
