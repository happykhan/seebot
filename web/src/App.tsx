import { useEffect, useMemo, useState } from 'react'
import { NavBar } from '@genomicx/ui'
import { useLocation } from 'react-router-dom'
import { AggregateTrend, DistributionPlot, formatNumber, numeric, quantile, SoftwareTimeSeries } from './charts'
import { contractCatalogue, historyDefinitions, metricDefinitions, practiceDescriptions, type HistoryMetric } from './catalogue'
import { loadPublishedDataset } from './dataset'
import { FindingsTable } from './FindingsTable'
import { activeLabelKeys, filterSoftware, labelNames, softwareHref, type SoftwareFilters } from './projects'
import type { ContractObservation, Dataset, ExemplarLabels, MetricPoint, ObservationStatus, ProbeObservation, ProjectSummary, SourceSnapshot } from './types'
import { InfoTip, SeebotIcon, SelectField } from './ui'

const statusText: Record<ObservationStatus, string> = {
  PASS: 'Handled gracefully', FAIL: 'Needs improvement', OBSERVED: 'Observed', NOT_OBSERVED: 'Not observed',
  NOT_APPLICABLE: 'Not applicable', UNTESTABLE: 'Could not assess', ERROR: 'Audit error', NOT_RUN: 'Not run',
  NOT_EXISTING: 'Software not yet present',
}

function pretty(value: string | null): string { return value ? value.replaceAll('_', ' ') : 'Not classified' }
function StatusBadge({ status }: { status: ObservationStatus }) { return <span className={`status-badge status-${status.toLowerCase().replaceAll('_', '-')}`}>{statusText[status]}</span> }

function LabelList({ labels, linked = false }: { labels: ExemplarLabels, linked?: boolean }) {
  const active = activeLabelKeys(labels).filter((key) => key !== 'complete_assessment')
  if (!active.length) return null
  return <div className="label-list">{active.map((key) => linked
    ? <a key={key} href={softwareHref({ exemplar: key === 'usage_exemplar' ? 'usage' : key === 'repository_practice_exemplar' ? 'repository' : 'all' })}>{labelNames[key]}</a>
    : <span key={key}>{labelNames[key]}</span>)}</div>
}

function Overview({ dataset }: { dataset: Dataset }) {
  const cards = [
    { count: dataset.summary.labels.repository_practice_exemplars, title: 'Repository best practices', text: 'Software with current development activity and the reviewed documentation, testing and continuous-integration practices.', href: softwareHref({ exemplar: 'repository' }) },
    { count: dataset.summary.labels.usage_exemplars, title: 'Command-line best practices', text: 'Software that met every applicable check for help, execution, output and handling of problematic input.', href: softwareHref({ exemplar: 'usage' }) },
    { count: dataset.summary.labels.practice_exemplars, title: 'Best practices across all areas', text: 'Software meeting the repository and command-line criteria across the reviewed areas.', href: softwareHref({ exemplar: 'all' }) },
  ]
  return <>
    <section className="hero"><div><p className="eyebrow">Seebot</p><h1>A review of bioinformatics software practices</h1><p>Seebot reports on how bioinformatics tools are maintained, structured, documented and how their command-line interfaces behaved with valid and deliberately awkward input.</p><div className="hero-actions"><a href="#/explore">Explore the results</a><a href="#/projects">Browse software</a></div></div></section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Examples</p><h2>Software with best practices</h2></div><p>Open a category to see the software that met all of its stated checks.</p></div>
      <div className="best-practice-grid">{cards.map((card) => <a href={card.href} key={card.title}><strong>{card.count}</strong><div><h3>{card.title}</h3><p>{card.text}</p></div><span>View software →</span></a>)}</div>
    </section>
    <RepositoryPracticePanel dataset={dataset} />
    <SourceHealthPanel dataset={dataset} />
    <RobustnessPanel dataset={dataset} />
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
      return <a href={`#/explore?metric=${key}&language=${encodeURIComponent(language)}`} key={key}><span>{definition.shortLabel}<InfoTip>{definition.explanation}</InfoTip></span><strong>{values.length ? formatNumber(quantile(values, .5), definition.unit) : 'Not available'}</strong><small>{values.length ? `Median across ${values.length} ${language} observations` : `No ${language} observations`} →</small></a>
    })}</div>
  </section>
}

function RobustnessPanel({ dataset }: { dataset: Dataset }) {
  const total = dataset.summary.assessed_projects
  return <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Command-line robustness</p><h2>Response to problematic user input</h2></div><p>These checks examine whether software identifies missing, empty, malformed or incompatible input and returns a useful error without crashing or creating misleading output. Select a scenario to see software that did not meet the expected behaviour.</p></div>
    <div className="robustness-grid">{dataset.aggregate.robustness.map((row) => { const pass = row.statuses.PASS ?? 0; const fail = row.statuses.FAIL ?? 0; const na = row.statuses.NOT_APPLICABLE ?? 0; return <a href={softwareHref({ robustness: row.check_id, outcome: 'fail' })} key={row.check_id}><div><span><strong>{row.label}</strong><small>{pass} handled · {fail} needs improvement · {na} N/A</small></span><b>{fail} to review →</b></div><i><em className="segment-pass" style={{ width: `${100 * pass / total}%` }} /><em className="segment-fail" style={{ width: `${100 * fail / total}%` }} /><em className="segment-na" style={{ width: `${100 * na / total}%` }} /></i></a> })}</div>
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
  const points = (dataset.aggregate.metric_points[metric] ?? []).filter((point) => metricLanguage === 'all' || point.language === metricLanguage)
  return <>
    <section className="page-intro"><p className="eyebrow">Explore</p><h1>Patterns across bioinformatics software</h1><p>Compare repository practices, source-code measurements, command-line behaviour and automated code-review findings across the assessed software.</p></section>
    <LanguagePanel dataset={dataset} />
    <section className="section-block" id="software-observations"><div className="section-heading"><div><p className="eyebrow">Distributions</p><h2>Software observations</h2></div><div className="select-row"><SelectField label="Measurement" value={metric} onChange={(event) => setMetric(event.target.value)}>{Object.entries(metricDefinitions).filter(([key]) => dataset.aggregate.metric_points[key]?.length).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</SelectField><SelectField label="Language" value={metricLanguage} onChange={(event) => setMetricLanguage(event.target.value)}><option value="all">All compatible observations</option>{languages.map((value) => <option key={value} value={value}>{value}</option>)}</SelectField></div></div>
      <p className="section-description">{definition.explanation} Hover over the box to see its boundaries, or over a point to identify the software and its value.</p><DistributionPlot points={points} label={definition.label} unit={definition.unit} software={dataset.projects} />
    </section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Change over time</p><h2>Source-code trends</h2></div><div className="select-row"><SelectField label="Measurement" value={historyMetric} onChange={(event) => setHistoryMetric(event.target.value as HistoryMetric)}>{Object.entries(historyDefinitions).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</SelectField><SelectField label="Language" value={historyLanguage} onChange={(event) => setHistoryLanguage(event.target.value)}><option value="all">All primary languages</option>{languages.map((value) => <option key={value} value={value}>{value}</option>)}</SelectField></div></div>
      <p className="section-description">The line shows the median and the shaded band shows the middle 50% of software available at each annual snapshot. This aggregate remains readable as the collection grows; individual histories appear in each software report.</p><AggregateTrend dataset={dataset} metric={historyMetric} language={historyLanguage} />
    </section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Automated code review</p><h2>Static-analysis findings</h2></div><p>Browse the findings reported by language-specific linters and security analyzers. The information icon beside each rule explains what it identifies.</p></div><FindingsTable rows={dataset.aggregate.native_rules} /></section>
  </>
}

function ProjectDirectory({ projects }: { projects: ProjectSummary[] }) {
  const location = useLocation()
  const params = new URLSearchParams(location.search)
  const fixed: SoftwareFilters = { tag: params.get('tag') ?? undefined, exemplar: params.get('exemplar') ?? undefined, practice: params.get('practice') ?? undefined, robustness: params.get('robustness') ?? undefined, outcome: params.get('outcome') ?? undefined }
  const [query, setQuery] = useState(params.get('query') ?? '')
  const [language, setLanguage] = useState(params.get('language') ?? 'all')
  const [category, setCategory] = useState(params.get('category') ?? 'all')
  const languages = [...new Set(projects.flatMap((project) => project.languages))].sort()
  const categories = [...new Set(projects.map((project) => project.category).filter(Boolean) as string[])].sort()
  const visible = useMemo(() => filterSoftware(projects, { ...fixed, query, language, category }), [category, language, location.search, projects, query])
  const filterLabel = fixed.tag ? `Tagged “${fixed.tag}”` : fixed.practice ? `${fixed.outcome === 'pass' ? 'Present' : 'Not found'}: ${fixed.practice}` : fixed.robustness ? `${contractCatalogue[fixed.robustness]?.label ?? fixed.robustness}: needs improvement` : fixed.exemplar ? `${fixed.exemplar === 'all' ? 'All-area' : pretty(fixed.exemplar)} best practices` : null
  return <>
    <section className="page-intro"><p className="eyebrow">Software directory</p><h1>Find a bioinformatics software report</h1><p>Search by name or browse by language, category and the assessment filters linked throughout Seebot.</p></section>
    <section className="directory">{filterLabel && <div className="active-filter"><span>Current filter</span><strong>{filterLabel}</strong><a href="#/projects">Clear filter ×</a></div>}
      <div className="directory-controls"><label className="search-field"><span>Search</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Software, format or category" /></label><SelectField label="Language" value={language} onChange={(event) => setLanguage(event.target.value)}><option value="all">All languages</option>{languages.map((value) => <option key={value}>{value}</option>)}</SelectField><SelectField label="Category" value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((value) => <option key={value} value={value}>{pretty(value)}</option>)}</SelectField></div>
      <div className="project-list">{visible.sort((a, b) => a.name.localeCompare(b.name)).map((project) => <a href={`#/projects/${project.id}?back=${encodeURIComponent(location.pathname + location.search)}`} key={project.id}><div><strong>{project.name}</strong><p>{project.description}</p><small>{pretty(project.category)} · {project.languages.join(' + ')}</small></div><LabelList labels={project.labels} /><b>→</b></a>)}</div><p className="result-count">{visible.length} software report{visible.length === 1 ? '' : 's'}</p>
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
  return <div className="source-components">{snapshots.map((snapshot) => <article key={snapshot.language}><header><strong>{snapshot.language}</strong><StatusBadge status={snapshot.status} /></header><div className="metric-grid">{definitions.map(({ key, field }) => {
    const definition = metricDefinitions[key]
    let value = numeric(snapshot.metrics[field[0]], field[1]); if (key === 'documentation_coverage' && value != null) value = Math.min(100, value)
    const point = value == null ? undefined : { project_id: project.id, language: snapshot.language, value }
    return <ComparisonCard key={key} label={definition.shortLabel} value={formatNumber(value, definition.unit)} explanation={definition.explanation} comparison={comparison(dataset, point, key, snapshot.language)} />
  })}</div>{snapshot.native_findings.map((finding, index) => <div className="finding-summary" key={`${finding.kind}-${finding.analyzer}-${index}`}><span>{finding.kind === 'lint' ? 'Code-review findings' : 'Security findings'} · {finding.analyzer ?? 'not applicable'}</span><strong>{finding.status === 'OBSERVED' ? formatNumber(finding.finding_count ?? 0) : statusText[finding.status]}</strong></div>)}</article>)}</div>
}

function ProjectReport({ project, dataset }: { project: ProjectSummary, dataset: Dataset }) {
  const location = useLocation()
  const [historyMetric, setHistoryMetric] = useState<HistoryMetric>('physical_lines')
  const currentSource = project.source_snapshots.filter((row) => row.snapshot_date === dataset.snapshot_date)
  const advisories = project.dependency_advisories.observed.advisories
  const back = new URLSearchParams(location.search).get('back') ?? '/projects'
  const activityCards = [
    ['days_since_last_commit', numeric(project.repository.activity, 'days_since_last_non_bot_commit'), 'days ago'],
    ['commits_last_12_months', numeric(project.repository.activity, 'commits_last_12_months'), ''],
    ['active_months_last_12_months', numeric(project.repository.activity, 'active_months_last_12_months'), 'of 12'],
    ['days_since_latest_release', numeric(project.repository.releases, 'days_since_latest_release'), 'days ago'],
  ] as const
  return <article className="project-report"><a className="back-link" href={`#${back}`}>← Back to search</a>
    <header><div><p className="eyebrow"><a href={softwareHref({ category: project.category ?? undefined })}>{pretty(project.category)}</a></p><h1>{project.name}</h1><p>{project.description}</p><div className="tag-row">{project.languages.map((language) => <a href={softwareHref({ language })} key={language}>{language}</a>)}{project.tags.map((tag) => <a href={softwareHref({ tag })} key={tag}>{pretty(tag)}</a>)}</div></div><aside><span>Software report</span><LabelList labels={project.labels} linked /><small>Reviewed commit {project.repository.snapshot_commit.slice(0, 12)}</small><a href={project.repository.url}>Open GitHub repository ↗</a></aside></header>
    <section className="report-facts"><div><span>Reviewed executable</span><strong>{project.primary_executable ?? 'Not identified'}</strong></div><div><span>Installed software</span><strong>{project.installation.artifact} {project.installation.version}</strong></div><div><span>Assessment environment</span><strong>{dataset.methodology.canonical_platform}</strong></div></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Repository health</p><h2>Maintenance and repository practices</h2></div><p>Current activity, releases, documentation, standard test structure and continuous integration.</p></div><div className="repo-layout"><div className="practice-checks">{Object.entries(project.repository.practices).map(([name, present]) => <a href={softwareHref({ practice: name, outcome: present ? 'pass' : 'fail' })} key={name}><span className={present ? 'present' : 'absent'}>{present ? '✓' : '—'}</span><strong>{name}</strong><InfoTip>{practiceDescriptions[name]}</InfoTip></a>)}</div><div className="activity-cards">{activityCards.map(([key, value, unit]) => { const definition = metricDefinitions[key]; const point = value == null ? undefined : { project_id: project.id, value }; return <ComparisonCard key={key} label={definition.shortLabel} value={formatNumber(value, unit)} explanation={definition.explanation} comparison={comparison(dataset, point, key)} /> })}</div></div></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Usage health</p><h2>Installed command-line behaviour</h2></div><p>The reviewed executable is asked for help and version information, run with a small representative dataset, and challenged with missing, empty, malformed and incompatible input. The expected response is a clear exit status and useful message, with valid output only when the command succeeds.</p></div><ContractTable contracts={project.contracts} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Source health</p><h2>Current source-code measurements</h2></div><p>Structural measurements and language-specific analyzer results for the software’s implementation. Each information icon defines the measurement; percentile bands compare it with software assessed in the same language.</p></div><SourceCards snapshots={currentSource} project={project} dataset={dataset} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Source history</p><h2>Source-code metrics over time</h2></div><SelectField label="Measurement" value={historyMetric} onChange={(event) => setHistoryMetric(event.target.value as HistoryMetric)}>{Object.entries(historyDefinitions).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</SelectField></div><p className="section-description">Annual values use the source present on 1 July. “p90” describes the value below which 90% of detected functions fall, showing the longer or more complex end of the distribution.</p><SoftwareTimeSeries project={project} metric={historyMetric} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Dependencies</p><h2>Known dependency vulnerabilities</h2></div><StatusBadge status={project.dependency_advisories.status} /></div><p className="section-description">OSV-Scanner checks <a href="https://google.github.io/osv-scanner/supported-languages-and-lockfiles/">supported dependency manifests and lockfiles</a> against published vulnerability advisories. An unavailable result means the repository did not contain a supported manifest for this scan; for example, current source scanning does not cover Perl/CPAN manifests.</p>{Array.isArray(advisories) && advisories.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Advisory</th><th>Ecosystem</th><th>Dependency</th><th>Version</th><th>Severity</th></tr></thead><tbody>{(advisories as Record<string, unknown>[]).map((row) => <tr key={`${row.advisory_id}-${row.dependency}`}><td><code>{String(row.advisory_id)}</code></td><td>{String(row.ecosystem)}</td><td>{String(row.dependency)}</td><td>{String(row.resolved_version)}</td><td>{Array.isArray(row.native_severity) ? row.native_severity.join(', ') : 'Unspecified'}</td></tr>)}</tbody></table></div> : <p className="empty-state">{String(project.dependency_advisories.observed.reason ?? 'No known advisories were returned for the supported dependency data found in this repository.')}</p>}</section>
  </article>
}

function Methods({ dataset }: { dataset: Dataset }) {
  return <section className="methods-page"><p className="eyebrow">Methods</p><h1>How Seebot reviews bioinformatics software</h1><p className="methods-lead">Seebot measures practical software-engineering characteristics that affect whether bioinformatics software can be found, understood, maintained and used reliably. The assessment combines repository metadata, source-code analysis, controlled command-line exercises and dependency-advisory checks.</p>
    <div className="method-section"><h2>Study set and review dates</h2><p>A discovery survey considered {dataset.methodology.candidate_survey_size} download-ranked package names and identified {dataset.methodology.eligible_cli_projects_found} eligible command-line tools. Current observations use the reviewed repository commit and installed software release. Source history uses the commit present on 1 July in each year from 2021 to 2026 where the software existed.</p></div>
    <div className="method-section"><h2>Repository health</h2><p>Repository observations describe maintenance activity and information available to users and contributors.</p><div className="method-details"><article><h3>Activity and releases</h3><p>Days since the latest non-bot commit and release, number of non-bot commits in the preceding 12 months, and number of active months in that period.</p></article><article><h3>Documentation and citation</h3><p>Presence of a README, installation instructions, a usage example, licence and citation guidance.</p></article><article><h3>Testing and automation</h3><p>Presence of conventional unit-test files or framework configuration, and whether continuous integration contains a verification workflow.</p></article></div></div>
    <div className="method-section"><h2>Source health</h2><p>Production source is measured separately for each implementation language using a fixed analyzer configuration.</p><div className="method-details"><article><h3>Size and structure</h3><p>Source lines and files, longest file, share of files over 500 lines, function-length p90 and cyclomatic-complexity p90.</p></article><article><h3>Documentation and repetition</h3><p>Share of detected functions with associated documentation, and the share of normalized lines in repeated exact six-line blocks.</p></article><article><h3>Automated review</h3><p>Language-specific linter, maintainability and source-security findings, including the analyzer’s own rule and severity labels.</p></article></div></div>
    <div className="method-section"><h2>Usage health</h2><p>Curated commands exercise the installed interface using small shared fixtures or a software-specific fixture when required. Checks cover help and version output, a valid miniature run, standard streams, no arguments, missing files, empty files, malformed data, the wrong biological format, invalid options and values, and unwritable output. Exit status, standard output, standard error, timeout and unintended output files are recorded.</p></div>
    <div className="method-section"><h2>Dependency health</h2><p>OSV-Scanner inspects <a href="https://google.github.io/osv-scanner/supported-languages-and-lockfiles/">supported dependency manifests and lockfiles</a> and queries published vulnerability records. Coverage depends on the ecosystems and file formats supported by the scanner, so an unsupported or absent manifest is reported as unavailable.</p></div>
    <div className="method-section"><h2>Interpretation</h2><p>The results describe the repository, source and executable observed at the stated review points. Small example runs assess interface behaviour and output structure; domain-specific validation of scientific algorithms requires separate benchmark data and expert analysis.</p></div>
  </section>
}

function Guidance() {
  return <section className="methods-page"><p className="eyebrow">Guidance</p><h1>Practical guidance for bioinformatics software</h1><p className="methods-lead">Good scientific software should be understandable before installation, predictable when used correctly, informative when something goes wrong, and maintainable as methods and computing environments change.</p>
    <div className="guidance-grid"><article><span>01</span><h2>Repository</h2><ul><li>Explain the purpose, installation and a representative command in the README.</li><li>State the licence and give a stable citation route.</li><li>Keep conventional unit tests and run verification in continuous integration.</li><li>Publish releases and record meaningful changes.</li></ul></article><article><span>02</span><h2>Source</h2><ul><li>Keep files and functions focused enough to review and test.</li><li>Document public functions and non-obvious decisions.</li><li>Run language-appropriate linters and security analysis, then review findings in context.</li><li>Watch complexity, repetition and unusually large files as the codebase grows.</li></ul></article><article><span>03</span><h2>Usage</h2><ul><li>Provide useful <code>-h</code>/<code>--help</code> and version output.</li><li>Use standard output for results and standard error for diagnostics.</li><li>Return non-zero exit codes for errors and describe how users can correct them.</li><li>Test empty, missing, malformed and incompatible input as well as a valid example.</li></ul></article><article><span>04</span><h2>Dependencies</h2><ul><li>Declare direct dependencies and versions in standard machine-readable files.</li><li>Review vulnerability advisories and update affected dependencies.</li><li>Remove dependencies that are no longer required.</li><li>Document external databases, reference data and services needed at runtime.</li></ul></article></div>
    <div className="method-section"><h2>Further areas</h2><p>Engineering practice is one part of trustworthy scientific software. Software teams should also consider scientific validation against reference results, performance and scalability, accessibility, privacy and data governance, interoperability, user support, and long-term stewardship.</p></div>
  </section>
}

export default function App() {
  const location = useLocation()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { loadPublishedDataset().then(setDataset).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown data error')) }, [])
  const parts = location.pathname.split('/').filter(Boolean)
  const view = parts[0] || 'overview'
  const project = view === 'projects' && parts[1] ? dataset?.projects.find((item) => item.id === parts[1]) : undefined
  const nav = <><a className="seebot-nav-link" href="#/">Overview</a><a className="seebot-nav-link" href="#/explore">Explore</a><a className="seebot-nav-link" href="#/projects">Software</a><a className="seebot-nav-link" href="#/methods">Methods</a><a className="seebot-nav-link" href="#/guidance">Guidance</a></>
  const mobileNav = <><a className="gx-nav-dropdown-link" href="#/">Overview</a><a className="gx-nav-dropdown-link" href="#/explore">Explore</a><a className="gx-nav-dropdown-link" href="#/projects">Software</a><a className="gx-nav-dropdown-link" href="#/methods">Methods</a><a className="gx-nav-dropdown-link" href="#/guidance">Guidance</a></>
  return <><NavBar appName="SEEBOT" appSubtitle="Bioinformatics software practices" version="1.0.0" icon={<SeebotIcon />} githubUrl="https://github.com/happykhan/seebot" actions={nav} mobileActions={mobileNav} /><main>
    {error && <p className="load-error">Could not load the published dataset: {error}</p>}{!error && !dataset && <p className="loading">Loading software observations…</p>}
    {dataset && view === 'overview' && <Overview dataset={dataset} />}{dataset && view === 'explore' && <Explorer dataset={dataset} />}
    {dataset && view === 'projects' && !parts[1] && <ProjectDirectory projects={dataset.projects} />}{dataset && view === 'projects' && project && <ProjectReport project={project} dataset={dataset} />}
    {dataset && view === 'projects' && parts[1] && !project && <p className="load-error">Software report not found.</p>}{dataset && view === 'methods' && <Methods dataset={dataset} />}
    {(view === 'guidance' || view === 'about') && <Guidance />}
  </main><footer className="site-footer"><span>Seebot</span><nav><a href="#/methods">Methods</a><a href="#/guidance">Guidance</a><a href="https://github.com/happykhan/seebot">Source code</a></nav></footer></>
}
