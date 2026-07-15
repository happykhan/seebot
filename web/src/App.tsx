import { useEffect, useMemo, useState } from 'react'
import { NavBar } from '@genomicx/ui'
import { useLocation } from 'react-router-dom'
import { loadPublishedDataset } from './dataset'
import type {
  ContractObservation, Dataset, ExemplarLabels, MetricPoint, ObservationStatus,
  ProjectSummary, SourceSnapshot,
} from './types'
import { activeLabelKeys, filterProjects, labelNames } from './projects'

const statusText: Record<ObservationStatus, string> = {
  PASS: 'Handled gracefully', FAIL: 'Did not handle gracefully', OBSERVED: 'Observed',
  NOT_OBSERVED: 'Not observed', NOT_APPLICABLE: 'Not applicable',
  UNTESTABLE: 'Could not assess', ERROR: 'Audit error', NOT_RUN: 'Not run',
  NOT_EXISTING: 'Project not yet present',
}

const metricDefinitions: Record<string, { label: string, unit: string }> = {
  days_since_last_commit: { label: 'Days since last non-bot commit', unit: 'days' },
  commits_last_12_months: { label: 'Commits in the previous 12 months', unit: 'commits' },
  active_months_last_12_months: { label: 'Active months in the previous 12 months', unit: 'months' },
  days_since_latest_release: { label: 'Days since latest release', unit: 'days' },
  production_lines: { label: 'Production source lines', unit: 'lines' },
  maximum_file_lines: { label: 'Longest production source file', unit: 'lines' },
  percent_files_over_500: { label: 'Production files over 500 lines', unit: '%' },
  function_length_p90: { label: '90th percentile function length', unit: 'lines' },
  complexity_p90: { label: '90th percentile cyclomatic complexity', unit: '' },
  duplication_percent: { label: 'Exact normalized duplication indicator', unit: '%' },
  documentation_coverage: { label: 'Function-associated documentation coverage', unit: '%' },
  dead_code_candidates: { label: 'Dead-code candidates', unit: 'candidates' },
  lint_findings_per_kloc: { label: 'Native linter findings', unit: 'per kLOC' },
  security_findings_per_kloc: { label: 'Native source-security findings', unit: 'per kLOC' },
  dependency_advisories: { label: 'Current dependency advisories', unit: 'advisories' },
}

const historyDefinitions = {
  physical_lines: { label: 'Production source lines', unit: 'lines' },
  maximum_file: { label: 'Longest production file', unit: 'lines' },
  complexity_p90: { label: 'Complexity p90', unit: '' },
  documentation: { label: 'Documentation coverage', unit: '%' },
  duplication: { label: 'Duplication indicator', unit: '%' },
}

function pretty(value: string | null): string {
  return value ? value.replaceAll('_', ' ') : 'Not classified'
}

function numeric(record: Record<string, unknown> | undefined, key: string): number | null {
  const value = record?.[key]
  return typeof value === 'number' ? value : null
}

function formatNumber(value: number | null | undefined, unit = ''): string {
  if (value == null) return 'Not available'
  const formatted = Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return unit ? `${formatted} ${unit}` : formatted
}

function StatusBadge({ status }: { status: ObservationStatus }) {
  return <span className={`status-badge status-${status.toLowerCase().replaceAll('_', '-')}`}>{statusText[status]}</span>
}

function LabelList({ labels }: { labels: ExemplarLabels }) {
  const active = activeLabelKeys(labels)
  if (active.length === 0) return <span className="quiet-label">No exemplar label</span>
  return <div className="label-list">{active.map((key) => <span key={key}>{labelNames[key]}</span>)}</div>
}

function LanguagePanel({ dataset }: { dataset: Dataset }) {
  const rows = Object.entries(dataset.aggregate.primary_language_counts).sort((a, b) => b[1] - a[1])
  const maximum = Math.max(...rows.map(([, count]) => count), 1)
  return <section className="section-block">
    <div className="section-heading"><div><p className="eyebrow">Language inventory</p><h2>Primary implementation language</h2></div><p>One project contributes once to this chart. Mixed-language components are retained in project reports and compatible analyzer groups.</p></div>
    <div className="language-bars">{rows.map(([language, count]) => <div key={language}><span>{language}</span><i><b style={{ width: `${count * 100 / maximum}%` }} /></i><strong>{count}</strong></div>)}</div>
  </section>
}

function RepositoryPracticePanel({ dataset }: { dataset: Dataset }) {
  const total = dataset.summary.assessed_projects
  return <section className="section-block">
    <div className="section-heading"><div><p className="eyebrow">Repository practice</p><h2>Observed across the current repositories</h2></div><p>Presence is recorded separately. It is not converted to a repository score.</p></div>
    <div className="practice-grid">{Object.entries(dataset.aggregate.repository_practice_counts).map(([name, count]) => <article key={name}><div><strong>{count}/{total}</strong><span>{name}</span></div><i><b style={{ width: `${100 * count / total}%` }} /></i></article>)}</div>
  </section>
}

function Overview({ dataset }: { dataset: Dataset }) {
  const cards = [
    ['Repository health', 'Activity, releases, verification CI, standard test patterns, documentation, licence and citation.'],
    ['Code health', 'Language-specific structural measurements and native analyzer findings from production source only.'],
    ['Usage health', 'A curated miniature run plus bounded probes for malformed and unexpected input.'],
  ]
  return <>
    <section className="hero">
      <div><p className="eyebrow">Scientific software observatory</p><h1>Evidence about code.<br /><em>Not a quality score.</em></h1><p>Seebot records how scientific tools are maintained, structured, documented and how their command-line interfaces behaved with valid and deliberately awkward input.</p></div>
      <aside><span>Canonical snapshot</span><strong>1 July 2026</strong><p>{dataset.summary.assessed_projects} fully curated project reports · source history from 2021 where the project existed</p></aside>
    </section>
    <section className="section-block">
      <div className="section-heading"><div><p className="eyebrow">Assessment model</p><h2>Three independent views of each project</h2></div><p>Measurements remain separate. Seebot does not collapse different practices, languages, or analyzer findings into one number.</p></div>
      <div className="pillar-grid">{cards.map(([title, description], index) => <article key={title}><span>0{index + 1}</span><h3>{title}</h3><p>{description}</p></article>)}</div>
    </section>
    <section className="section-block">
      <div className="section-heading"><div><p className="eyebrow">Factual recognition</p><h2>Labels require every stated condition</h2></div><p>Code-health values never qualify or disqualify a project. Labels reflect repository practices, executable behaviour, and assessment coverage.</p></div>
      <div className="summary-grid">
        <article><strong>{dataset.summary.labels.usage_exemplars}</strong><span>Usage exemplars</span></article>
        <article><strong>{dataset.summary.labels.repository_practice_exemplars}</strong><span>Repository-practice exemplars</span></article>
        <article><strong>{dataset.summary.labels.complete_assessments}</strong><span>Complete assessments</span></article>
        <article><strong>{dataset.summary.labels.practice_exemplars}</strong><span>Practice exemplars</span></article>
      </div>
    </section>
    <LanguagePanel dataset={dataset} />
    <RepositoryPracticePanel dataset={dataset} />
  </>
}

function quantile(values: number[], fraction: number): number {
  const ordered = [...values].sort((a, b) => a - b)
  if (ordered.length === 1) return ordered[0]
  const position = (ordered.length - 1) * fraction
  const lower = Math.floor(position)
  const remainder = position - lower
  return ordered[lower] + (ordered[lower + 1] - ordered[lower]) * remainder
}

function DistributionPlot({ points, label, unit }: { points: MetricPoint[], label: string, unit: string }) {
  if (points.length === 0) return <p className="empty-state">No compatible observations for this measurement.</p>
  const values = points.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const x = (value: number) => 50 + 800 * (value - min) / span
  const q1 = quantile(values, .25), median = quantile(values, .5), q3 = quantile(values, .75)
  return <div className="chart-card"><div className="chart-title"><strong>{label}</strong><span>n={points.length} · {points.length >= 10 ? 'box + project points' : 'project points'}</span></div><svg className="distribution-chart" viewBox="0 0 900 150" role="img" aria-label={`${label} distribution`}>
    <line x1="50" x2="850" y1="105" y2="105" className="axis" />
    {points.length >= 10 && <><line x1={x(min)} x2={x(max)} y1="68" y2="68" className="whisker" /><rect x={x(q1)} y="46" width={Math.max(x(q3) - x(q1), 2)} height="44" className="box" /><line x1={x(median)} x2={x(median)} y1="46" y2="90" className="median" /></>}
    {points.map((point, index) => <circle key={`${point.project_id}-${point.language ?? ''}-${point.analyzer ?? ''}`} cx={x(point.value)} cy={110 + (index % 3) * 7} r="5" className="project-dot"><title>{point.project_id}{point.language ? ` · ${point.language}` : ''}{point.analyzer ? ` · ${point.analyzer}` : ''}: {formatNumber(point.value, unit)}</title></circle>)}
    <text x="50" y="145">{formatNumber(min, unit)}</text><text x="850" y="145" textAnchor="end">{formatNumber(max, unit)}</text>
  </svg></div>
}

function RobustnessPanel({ dataset }: { dataset: Dataset }) {
  const total = dataset.summary.assessed_projects
  return <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Awkward input</p><h2>Observed outcome by robustness scenario</h2></div><p>A pass means non-zero exit, a diagnostic on standard error, no internal crash marker, and no inappropriate side effect. Acceptance or an internal exception fails that contract.</p></div><div className="robustness-grid">{dataset.aggregate.robustness.map((row) => {
    const pass = row.statuses.PASS ?? 0, fail = row.statuses.FAIL ?? 0, na = row.statuses.NOT_APPLICABLE ?? 0
    return <article key={row.check_id}><div><strong>{row.label}</strong><span>{pass} handled · {fail} did not · {na} N/A</span></div><i><b className="segment-pass" style={{ width: `${100 * pass / total}%` }} /><b className="segment-fail" style={{ width: `${100 * fail / total}%` }} /><b className="segment-na" style={{ width: `${100 * na / total}%` }} /></i></article>
  })}</div></section>
}

function historyValue(snapshot: SourceSnapshot, metric: keyof typeof historyDefinitions): number | null {
  if (metric === 'physical_lines') return numeric(snapshot.metrics.inventory, 'physical_lines')
  if (metric === 'maximum_file') return numeric(snapshot.metrics.files, 'maximum')
  if (metric === 'complexity_p90') return numeric(snapshot.metrics.complexity, 'percentile_90')
  if (metric === 'documentation') return numeric(snapshot.metrics.documentation, 'coverage_percent')
  return numeric(snapshot.metrics.duplication, 'duplicated_line_percent')
}

const lineColors = ['#147d64', '#ca6245', '#4968b0', '#a36b16', '#7f4ca5', '#477d28', '#a34472', '#33788d', '#765f3b', '#58606b']

function TimeSeries({ projects, metric, aiContext, compact = false }: { projects: ProjectSummary[], metric: keyof typeof historyDefinitions, aiContext: Dataset['methodology']['ai_context'], compact?: boolean }) {
  const series = projects.map((project) => ({
    project,
    points: project.source_snapshots
      .filter((row) => row.language === project.primary_language)
      .map((row) => ({ year: Number(row.snapshot_date.slice(0, 4)), value: historyValue(row, metric) }))
      .filter((row): row is { year: number, value: number } => row.value != null),
  })).filter((row) => row.points.length)
  const values = series.flatMap((row) => row.points.map((point) => point.value))
  if (!values.length) return <p className="empty-state">No historical observations for this measurement.</p>
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1
  const x = (year: number) => 70 + (year - 2021) * 152
  const y = (value: number) => 250 - 190 * (value - min) / span
  return <div className="chart-card"><svg className={`time-chart ${compact ? 'compact' : ''}`} viewBox="0 0 900 300" role="img" aria-label={`${historyDefinitions[metric].label} over time`}>
    {[2021, 2022, 2023, 2024, 2025, 2026].map((year) => <g key={year}><line x1={x(year)} x2={x(year)} y1="45" y2="255" className="grid-line" /><text x={x(year)} y="280" textAnchor="middle">{year}</text></g>)}
    {!compact && aiContext.map((event) => { const date = new Date(`${event.date}T00:00:00Z`); const position = x(date.getUTCFullYear() + date.getUTCMonth() / 12); return <g key={event.date}><line x1={position} x2={position} y1="35" y2="255" className="ai-marker" /><title>{event.label} · contextual marker only</title></g> })}
    {series.map((row, index) => <g key={row.project.id}><polyline points={row.points.map((point) => `${x(point.year)},${y(point.value)}`).join(' ')} style={{ stroke: lineColors[index % lineColors.length] }} className="series-line" />{row.points.map((point) => <circle key={point.year} cx={x(point.year)} cy={y(point.value)} r="4" style={{ fill: lineColors[index % lineColors.length] }}><title>{row.project.name} · {point.year}: {formatNumber(point.value, historyDefinitions[metric].unit)}</title></circle>)}</g>)}
    <text x="70" y="28">{formatNumber(max, historyDefinitions[metric].unit)}</text><text x="70" y="248">{formatNumber(min, historyDefinitions[metric].unit)}</text>
  </svg>{!compact && <div className="chart-legend">{series.map((row, index) => <span key={row.project.id}><i style={{ background: lineColors[index % lineColors.length] }} />{row.project.name}</span>)}</div>}</div>
}

function Explorer({ dataset }: { dataset: Dataset }) {
  const [metric, setMetric] = useState('days_since_last_commit')
  const [historyMetric, setHistoryMetric] = useState<keyof typeof historyDefinitions>('physical_lines')
  const [ruleKind, setRuleKind] = useState<'lint' | 'security'>('lint')
  const rules = dataset.aggregate.native_rules.filter((row) => row.kind === ruleKind).sort((a, b) => b.count - a.count).slice(0, 30)
  const definition = metricDefinitions[metric]
  return <>
    <section className="page-intro"><p className="eyebrow">Dataset explorer</p><h1>Explore compatible measurements, not synthetic grades.</h1><p>Every project point remains visible. Analyzer-derived values retain their language, analyzer, rule, and denominator.</p></section>
    <LanguagePanel dataset={dataset} />
    <RepositoryPracticePanel dataset={dataset} />
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Current distributions</p><h2>Project-level observations</h2></div><label className="inline-select">Measurement<select value={metric} onChange={(event) => setMetric(event.target.value)}>{Object.entries(metricDefinitions).filter(([key]) => dataset.aggregate.metric_points[key]?.length).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label></div><DistributionPlot points={dataset.aggregate.metric_points[metric] ?? []} label={definition.label} unit={definition.unit} /></section>
    <RobustnessPanel dataset={dataset} />
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Source history</p><h2>Changes at each 1 July snapshot</h2></div><label className="inline-select">Measurement<select value={historyMetric} onChange={(event) => setHistoryMetric(event.target.value as keyof typeof historyDefinitions)}>{Object.entries(historyDefinitions).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label></div><p className="context-note">Thin vertical markers show three public AI-tooling milestones as context only. They do not imply attribution or causality.</p><TimeSeries projects={dataset.projects} metric={historyMetric} aiContext={dataset.methodology.ai_context} /><div className="source-links">{dataset.methodology.ai_context.map((event) => <a href={event.url} key={event.date}>{event.date} · {event.label} ↗</a>)}</div></section>
    <section className="section-block"><div className="section-heading"><div><p className="eyebrow">Native findings</p><h2>Most frequent tool-native rules</h2></div><label className="inline-select">Finding type<select value={ruleKind} onChange={(event) => setRuleKind(event.target.value as 'lint' | 'security')}><option value="lint">Linter</option><option value="security">Source security</option></select></label></div><div className="data-table-wrap"><table className="data-table"><thead><tr><th>Language</th><th>Analyzer</th><th>Native rule</th><th>Native severity</th><th>Projects</th><th>Findings</th></tr></thead><tbody>{rules.map((rule) => <tr key={`${rule.kind}-${rule.language}-${rule.analyzer}-${rule.rule}`}><td>{rule.language}</td><td>{rule.analyzer}</td><td><code>{rule.rule}</code></td><td>{rule.native_severity ?? 'Unspecified'}</td><td>{rule.project_count}</td><td>{rule.count}</td></tr>)}</tbody></table></div><p className="context-note">Rules are never remapped into broad cross-language categories.</p></section>
  </>
}

function ProjectDirectory({ projects }: { projects: ProjectSummary[] }) {
  const [query, setQuery] = useState('')
  const [language, setLanguage] = useState('all')
  const [category, setCategory] = useState('all')
  const languages = [...new Set(projects.flatMap((project) => project.languages))].sort()
  const categories = [...new Set(projects.map((project) => project.category).filter(Boolean) as string[])].sort()
  const visible = useMemo(() => filterProjects(projects, query, language, category), [category, language, projects, query])
  return <>
    <section className="page-intro"><p className="eyebrow">Project directory</p><h1>Find a scientific software report.</h1><p>Projects are listed alphabetically. There is no score-based ordering.</p></section>
    <section className="directory"><div className="directory-controls"><label>Search<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Project, format, or category" /></label><label>Language<select value={language} onChange={(event) => setLanguage(event.target.value)}><option value="all">All languages</option>{languages.map((value) => <option key={value}>{value}</option>)}</select></label><label>Category<select value={category} onChange={(event) => setCategory(event.target.value)}><option value="all">All categories</option>{categories.map((value) => <option key={value}>{pretty(value)}</option>)}</select></label></div>
      <div className="project-list">{visible.sort((a, b) => a.name.localeCompare(b.name)).map((project) => <a href={`#/projects/${project.id}`} key={project.id}><div><strong>{project.name}</strong><p>{project.description}</p><small>{pretty(project.category)} · {project.languages.join(' + ')}</small></div><div><span className="assessment-state">Report published</span><LabelList labels={project.labels} /></div><b>→</b></a>)}</div><p className="result-count">{visible.length} project{visible.length === 1 ? '' : 's'}</p>
    </section>
  </>
}

function ContractTable({ contracts }: { contracts: ContractObservation[] }) {
  return <div className="contract-list">{contracts.map((contract) => <details key={contract.check_id}><summary><div><code>{contract.check_id}</code><strong>{contract.label}</strong></div><StatusBadge status={contract.status} /></summary><div className="probe-list">{contract.probes.map((probe) => <article key={probe.probe_id}><div><StatusBadge status={probe.status} /><code>{probe.command?.join(' ') ?? probe.probe_id}</code></div>{probe.notes && <p>{probe.notes}</p>}<dl><div><dt>Exit</dt><dd>{String(probe.observed.exit_code ?? 'N/A')}</dd></div><div><dt>Diagnostic</dt><dd>{String(probe.observed.diagnostic_class ?? 'N/A')}</dd></div><div><dt>Timed out</dt><dd>{String(probe.observed.timed_out ?? false)}</dd></div></dl></article>)}</div></details>)}</div>
}

function SourceCards({ snapshots }: { snapshots: SourceSnapshot[] }) {
  return <div className="source-components">{snapshots.map((snapshot) => {
    const inventory = snapshot.metrics.inventory, files = snapshot.metrics.files, functions = snapshot.metrics.functions, complexity = snapshot.metrics.complexity, documentation = snapshot.metrics.documentation, duplication = snapshot.metrics.duplication
    return <article key={snapshot.language}><header><strong>{snapshot.language}</strong><StatusBadge status={snapshot.status} /></header><div className="metric-grid"><div><span>Production lines</span><strong>{formatNumber(numeric(inventory, 'physical_lines'))}</strong></div><div><span>Production files</span><strong>{formatNumber(numeric(inventory, 'files'))}</strong></div><div><span>Longest file</span><strong>{formatNumber(numeric(files, 'maximum'), 'lines')}</strong></div><div><span>Files over 500 lines</span><strong>{formatNumber(numeric(files, 'percent_over_500'), '%')}</strong></div><div><span>Function length p90</span><strong>{formatNumber(numeric(functions, 'length_percentile_90'), 'lines')}</strong></div><div><span>Complexity p90</span><strong>{formatNumber(numeric(complexity, 'percentile_90'))}</strong></div><div><span>Documentation</span><strong>{formatNumber(numeric(documentation, 'coverage_percent'), '%')}</strong></div><div><span>Duplication indicator</span><strong>{formatNumber(numeric(duplication, 'duplicated_line_percent'), '%')}</strong></div></div>{snapshot.native_findings.map((finding, index) => <div className="finding-summary" key={`${finding.kind}-${finding.analyzer}-${index}`}><span>{finding.kind} · {finding.analyzer ?? 'not applicable'}</span><strong>{finding.status === 'OBSERVED' ? formatNumber(finding.finding_count ?? 0) : statusText[finding.status]}</strong></div>)}</article>
  })}</div>
}

function ProjectReport({ project, dataset }: { project: ProjectSummary, dataset: Dataset }) {
  const [historyMetric, setHistoryMetric] = useState<keyof typeof historyDefinitions>('physical_lines')
  const currentSource = project.source_snapshots.filter((row) => row.snapshot_date === dataset.snapshot_date)
  const advisories = project.dependency_advisories.observed.advisories
  return <article className="project-report">
    <header><div><p className="eyebrow">{pretty(project.category)}</p><h1>{project.name}</h1><p>{project.description}</p><div className="tag-row">{project.languages.map((language) => <span key={language}>{language}</span>)}{project.tags.map((tag) => <span key={tag}>{pretty(tag)}</span>)}</div></div><aside><span>Report published</span><LabelList labels={project.labels} /><small>Snapshot 1 July 2026 · {project.repository.snapshot_commit.slice(0, 12)}</small><a href={project.repository.url}>Open GitHub repository ↗</a></aside></header>
    <section className="report-facts"><div><span>Audited executable</span><strong>{project.primary_executable ?? 'Not identified'}</strong></div><div><span>Installed artifact</span><strong>{project.installation.artifact} {project.installation.version}</strong></div><div><span>Canonical runtime</span><strong>{dataset.methodology.canonical_platform}</strong></div></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Repository health</p><h2>Current repository observations</h2></div><p>Commit and release recency are descriptive. Only explicit archived status affects inclusion.</p></div><div className="repo-layout"><div className="practice-checks">{Object.entries(project.repository.practices).map(([name, present]) => <div key={name}><span className={present ? 'present' : 'absent'}>{present ? '✓' : '—'}</span><strong>{name}</strong></div>)}</div><div className="activity-cards"><article><span>Last non-bot commit</span><strong>{formatNumber(numeric(project.repository.activity, 'days_since_last_non_bot_commit'), 'days ago')}</strong></article><article><span>Commits in 12 months</span><strong>{formatNumber(numeric(project.repository.activity, 'commits_last_12_months'))}</strong></article><article><span>Active months</span><strong>{formatNumber(numeric(project.repository.activity, 'active_months_last_12_months'), '/ 12')}</strong></article><article><span>Latest release</span><strong>{formatNumber(numeric(project.repository.releases, 'days_since_latest_release'), 'days ago')}</strong></article></div></div><p className="context-note">Recognized standard tests: {String(project.repository.standard_tests.recognised_test_count ?? 0)} files ({(project.repository.standard_tests.frameworks as string[] | undefined)?.join(', ') || 'no framework recognized'}). Upstream tests were detected but never executed.</p></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Usage health</p><h2>Installed-interface behaviour</h2></div><p>A miniature valid run checks execution and output structure, not scientific correctness.</p></div><ContractTable contracts={project.contracts} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Code health</p><h2>Current production source</h2></div><p>Tests, documentation, examples, data, generated output, and vendored source are excluded from every denominator.</p></div><SourceCards snapshots={currentSource} /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Source history</p><h2>Measurements at each 1 July snapshot</h2></div><label className="inline-select">Measurement<select value={historyMetric} onChange={(event) => setHistoryMetric(event.target.value as keyof typeof historyDefinitions)}>{Object.entries(historyDefinitions).map(([key, value]) => <option key={key} value={key}>{value.label}</option>)}</select></label></div><TimeSeries projects={[project]} metric={historyMetric} aiContext={[]} compact /></section>
    <section className="report-section"><div className="section-heading"><div><p className="eyebrow">Dependency advisories</p><h2>Current supported dependency manifests</h2></div><StatusBadge status={project.dependency_advisories.status} /></div>{Array.isArray(advisories) && advisories.length ? <div className="data-table-wrap"><table className="data-table"><thead><tr><th>Advisory</th><th>Ecosystem</th><th>Dependency</th><th>Version</th><th>Native severity</th></tr></thead><tbody>{(advisories as Record<string, unknown>[]).map((row) => <tr key={`${row.advisory_id}-${row.dependency}`}><td><code>{String(row.advisory_id)}</code></td><td>{String(row.ecosystem)}</td><td>{String(row.dependency)}</td><td>{String(row.resolved_version)}</td><td>{Array.isArray(row.native_severity) ? row.native_severity.join(', ') : 'Unspecified'}</td></tr>)}</tbody></table></div> : <p className="empty-state">{String(project.dependency_advisories.observed.reason ?? 'No known advisories were returned for the supported dependency data.')}</p>}</section>
  </article>
}

function Methods({ dataset }: { dataset: Dataset }) {
  return <section className="methods-page"><p className="eyebrow">Scope and methods</p><h1>Every claim is tied to a command, commit, fixture, and denominator.</h1><div className="methods-grid"><article><h2>Candidate discovery</h2><p>{dataset.methodology.candidate_survey_size} official download-ranked package names were surveyed as a discovery route only. {dataset.methodology.eligible_cli_projects_found} had explicit eligible CLI evidence; the first 200 were reached by rank {dataset.methodology.first_200_eligible_reached_at_rank}. Packaging is not an assessment metric.</p></article><article><h2>Current snapshot</h2><p>The canonical repository snapshot is the default-branch commit at or before 1 July 2026. Repository, dependency, and executable observations apply only to it.</p></article><article><h2>Historical source</h2><p>Source-derived measurements use commits at or before 1 July from 2021 onward, with one frozen analyzer configuration. Missing pre-existence years remain explicit.</p></article><article><h2>No upstream tests</h2><p>Seebot detects recognized standard test patterns and whether verification CI appears to invoke them. It never executes upstream test suites, and test source is excluded from code metrics.</p></article><article><h2>Bounded behaviour</h2><p>Usage probes run without network in an isolated Linux x86-64 environment with two CPUs, 8 GB memory, bounded storage, process count, and timeouts.</p></article><article><h2>Native findings</h2><p>Linter and security rules remain native to their analyzer. Different tools and languages are not merged into one finding category.</p></article><article><h2>No quality score</h2><p>Measurements remain separate. Exemplar labels depend on observable practices, graceful behaviour, and complete evidence—not arbitrary code thresholds.</p></article><article><h2>Interpretation limit</h2><p>A valid miniature run establishes neither scientific correctness nor fitness for a particular analysis. Historical AI markers are contextual dates, never causal claims.</p></article></div></section>
}

function About() {
  return <section className="methods-page"><p className="eyebrow">About Seebot</p><h1>A transparent observatory for scientific software engineering.</h1><div className="methods-grid"><article><h2>What it records</h2><p>Reproducible observations about repositories, production source, command-line interfaces, and deliberately awkward input.</p></article><article><h2>What it does not claim</h2><p>It does not judge scientific validity, rank projects, or turn unrelated engineering measurements into an overall quality score.</p></article><article><h2>Rerunnable by design</h2><p>Project manifests, shared fixtures, selectors, pinned environments, and evidence rules live with the code. A single project or check family can be regenerated.</p></article><article><h2>Factual exemplars</h2><p>Labels identify projects that meet every applicable stated condition. They are not prizes, grades, or editorial judgements.</p></article></div></section>
}

export default function App() {
  const location = useLocation()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { loadPublishedDataset().then(setDataset).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : 'Unknown data error')) }, [])
  const parts = location.pathname.split('/').filter(Boolean)
  const view = parts[0] || 'overview'
  const project = view === 'projects' && parts[1] ? dataset?.projects.find((item) => item.id === parts[1]) : undefined
  return <><NavBar appName="SEEBOT" appSubtitle="Scientific software observatory" version="1.0.0" githubUrl="https://github.com/happykhan/seebot" actions={<><a className="seebot-nav-link" href="#/">Overview</a><a className="seebot-nav-link" href="#/explore">Explore</a><a className="seebot-nav-link" href="#/projects">Projects</a><a className="seebot-nav-link" href="#/methods">Methods</a></>} mobileActions={<><a className="gx-nav-dropdown-link" href="#/">Overview</a><a className="gx-nav-dropdown-link" href="#/explore">Explore</a><a className="gx-nav-dropdown-link" href="#/projects">Projects</a><a className="gx-nav-dropdown-link" href="#/methods">Methods</a></>} /><main>
    {error && <p className="load-error">Could not load the published dataset: {error}</p>}
    {!error && !dataset && <p className="loading">Loading software observations…</p>}
    {dataset && view === 'overview' && <Overview dataset={dataset} />}
    {dataset && view === 'explore' && <Explorer dataset={dataset} />}
    {dataset && view === 'projects' && !parts[1] && <ProjectDirectory projects={dataset.projects} />}
    {dataset && view === 'projects' && project && <ProjectReport project={project} dataset={dataset} />}
    {dataset && view === 'projects' && parts[1] && !project && <p className="load-error">Project not found.</p>}
    {dataset && view === 'methods' && <Methods dataset={dataset} />}
    {view === 'about' && <About />}
  </main><footer className="site-footer"><span>Seebot · canonical snapshot 1 July 2026</span><span>Observable engineering evidence, not scientific validation or a quality score.</span></footer></>
}
