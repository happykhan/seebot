import { useState } from 'react'
import type { Dataset, MetricPoint, ProjectSummary, SourceSnapshot } from './types'
import { historyDefinitions, type HistoryMetric } from './catalogue'

export function numeric(record: Record<string, unknown> | undefined, key: string): number | null {
  const value = record?.[key]
  return typeof value === 'number' ? value : null
}

export function formatNumber(value: number | null | undefined, unit = ''): string {
  if (value == null) return 'Not available'
  const formatted = Number.isInteger(value)
    ? value.toLocaleString()
    : value.toLocaleString(undefined, { maximumFractionDigits: 2 })
  return unit ? `${formatted} ${unit}` : formatted
}

export function quantile(values: number[], fraction: number): number {
  const ordered = [...values].sort((a, b) => a - b)
  if (ordered.length === 1) return ordered[0]
  const position = (ordered.length - 1) * fraction
  const lower = Math.floor(position)
  const remainder = position - lower
  return ordered[lower] + (ordered[lower + 1] - ordered[lower]) * remainder
}

export function compatibleMetricLanguages(points: MetricPoint[]): string[] {
  return [...new Set(points.map((point) => point.language).filter((value): value is string => Boolean(value)))].sort()
}

export function selectMetricPoints(points: MetricPoint[], language: string): MetricPoint[] {
  const compatible = compatibleMetricLanguages(points)
  if (language === 'all' || !compatible.includes(language)) return points
  return points.filter((point) => point.language === language)
}

function historyValue(snapshot: SourceSnapshot, metric: HistoryMetric): number | null {
  if (metric === 'physical_lines') return numeric(snapshot.metrics.inventory, 'physical_lines')
  if (metric === 'maximum_file') return numeric(snapshot.metrics.files, 'maximum')
  if (metric === 'complexity_p90') return numeric(snapshot.metrics.complexity, 'percentile_90')
  if (metric === 'documentation') {
    const value = numeric(snapshot.metrics.documentation, 'coverage_percent')
    return value == null ? null : Math.min(100, value)
  }
  return numeric(snapshot.metrics.duplication, 'duplicated_line_percent')
}

interface DistributionPlotProps {
  points: MetricPoint[]
  label: string
  unit: string
  software: ProjectSummary[]
}

export function DistributionPlot({ points, label, unit, software }: DistributionPlotProps) {
  const [hovered, setHovered] = useState<string | null>(null)
  if (points.length === 0) return <p className="empty-state">No observations are available for this measurement.</p>
  const values = points.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const x = (value: number) => 64 + 772 * (value - min) / span
  const q1 = quantile(values, 0.25)
  const median = quantile(values, 0.5)
  const q3 = quantile(values, 0.75)
  const softwareNames = new Map(software.map((item) => [item.id, item.name]))
  const ticks = Array.from({ length: 6 }, (_, index) => min + span * index / 5)
  const summary = `Minimum ${formatNumber(min, unit)}; Q1 ${formatNumber(q1, unit)}; median ${formatNumber(median, unit)}; Q3 ${formatNumber(q3, unit)}; maximum ${formatNumber(max, unit)}`
  return <div className="chart-card">
    <div className="chart-title"><strong>{label}</strong><span>{points.length} software · hover for values · select a point for its report</span></div>
    <svg className="distribution-chart" viewBox="0 0 900 190" role="img" aria-label={`${label} distribution`}>
      {ticks.map((tick, index) => <g key={index}>
        <line x1={x(tick)} x2={x(tick)} y1="32" y2="145" className="grid-line" />
        <text x={x(tick)} y="174" textAnchor="middle">{formatNumber(tick, unit)}</text>
      </g>)}
      <line x1="64" x2="836" y1="145" y2="145" className="axis" />
      {points.length >= 10 && <g className="box-plot" tabIndex={0} onMouseEnter={() => setHovered(summary)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(summary)} onBlur={() => setHovered(null)}>
        <title>{summary}</title>
        <line x1={x(min)} x2={x(max)} y1="75" y2="75" className="whisker" />
        <line x1={x(min)} x2={x(min)} y1="63" y2="87" className="whisker" />
        <line x1={x(max)} x2={x(max)} y1="63" y2="87" className="whisker" />
        <rect x={x(q1)} y="50" width={Math.max(x(q3) - x(q1), 2)} height="50" className="box" />
        <line x1={x(median)} x2={x(median)} y1="50" y2="100" className="median" />
      </g>}
      {points.map((point, index) => { const detail = `${softwareNames.get(point.project_id) ?? point.project_id}${point.language ? ` · ${point.language}` : ''}${point.analyzer ? ` · ${point.analyzer}` : ''}: ${formatNumber(point.value, unit)}`; return <a href={`#/software/${point.project_id}`} key={`${point.project_id}-${point.language ?? ''}-${point.analyzer ?? ''}-${index}`} onMouseEnter={() => setHovered(detail)} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(detail)} onBlur={() => setHovered(null)}>
        <circle cx={x(point.value)} cy={126 + (index % 3) * 7} r="6" className="project-dot">
          <title>{detail}</title>
        </circle>
      </a>})}
    </svg>
    <p className={`chart-hover ${hovered ? 'visible' : ''}`}>{hovered ?? 'Move over the box plot or a software point to see its value.'}</p>
    {points.length >= 10 && <p className="chart-summary">{summary}</p>}
  </div>
}

function seriesForSoftware(project: ProjectSummary, metric: HistoryMetric, language?: string) {
  const selectedLanguage = language ?? project.primary_language
  return project.source_snapshots
    .filter((row) => row.language === selectedLanguage)
    .map((row) => ({ year: Number(row.snapshot_date.slice(0, 4)), value: historyValue(row, metric) }))
    .filter((row): row is { year: number, value: number } => row.value != null)
}

export function SoftwareTimeSeries({ project, metric }: { project: ProjectSummary, metric: HistoryMetric }) {
  const definition = historyDefinitions[metric]
  const points = seriesForSoftware(project, metric)
  if (!points.length) return <p className="empty-state">No historical observations are available for this measurement.</p>
  const values = points.map((point) => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const x = (year: number) => 70 + (year - 2021) * 152
  const y = (value: number) => 245 - 175 * (value - min) / span
  const yTicks = Array.from({ length: 5 }, (_, index) => min + span * index / 4)
  const availability = [2021, 2022, 2023, 2024, 2025, 2026].map((year) => {
    const snapshot = project.source_snapshots.find((row) => row.language === project.primary_language && Number(row.snapshot_date.slice(0, 4)) === year)
    return { year, status: snapshot?.status ?? 'NOT_RUN' }
  })
  return <div className="chart-card">
    <svg className="time-chart compact" viewBox="0 0 900 300" role="img" aria-label={`${definition.label} over time for ${project.name}`}>
      {yTicks.map((tick, index) => <g key={index}><line x1="70" x2="830" y1={y(tick)} y2={y(tick)} className="grid-line" /><text x="62" y={y(tick) + 3} textAnchor="end">{formatNumber(tick, definition.unit)}</text></g>)}
      {[2021, 2022, 2023, 2024, 2025, 2026].map((year) => <g key={year}><line x1={x(year)} x2={x(year)} y1="55" y2="250" className="grid-line" /><text x={x(year)} y="278" textAnchor="middle">{year}</text></g>)}
      <polyline points={points.map((point) => `${x(point.year)},${y(point.value)}`).join(' ')} className="series-line single-series" />
      {points.map((point) => <circle key={point.year} cx={x(point.year)} cy={y(point.value)} r="5" className="history-dot"><title>{project.name} · {point.year}: {formatNumber(point.value, definition.unit)}</title></circle>)}
    </svg>
    <div className="history-availability" aria-label="Annual source availability">{availability.map((row) => <span className={`history-${row.status.toLowerCase().replaceAll('_', '-')}`} key={row.year}><b>{row.year}</b>{row.status === 'NOT_EXISTING' ? 'Not yet present' : row.status === 'NOT_RUN' ? 'No observation' : 'Source observed'}</span>)}</div>
    <p className="chart-summary">The selected measurement changed from {formatNumber(points[0].value, definition.unit)} in {points[0].year} to {formatNumber(points.at(-1)?.value, definition.unit)} in {points.at(-1)?.year}.</p>
  </div>
}

export function AggregateTrend({ dataset, metric, language }: { dataset: Dataset, metric: HistoryMetric, language: string }) {
  const definition = historyDefinitions[metric]
  const years = [2021, 2022, 2023, 2024, 2025, 2026]
  const summaries = years.map((year) => {
    const values = dataset.projects.flatMap((project) => {
      const selected = language === 'all' ? project.primary_language : language
      const point = seriesForSoftware(project, metric, selected).find((row) => row.year === year)
      return point ? [point.value] : []
    })
    return values.length ? { year, n: values.length, q1: quantile(values, 0.25), median: quantile(values, 0.5), q3: quantile(values, 0.75) } : null
  }).filter((row): row is { year: number, n: number, q1: number, median: number, q3: number } => row != null)
  if (!summaries.length) return <p className="empty-state">No historical observations are available for this language and measurement.</p>
  const allValues = summaries.flatMap((row) => [row.q1, row.median, row.q3])
  const min = Math.min(...allValues)
  const max = Math.max(...allValues)
  const span = max - min || 1
  const x = (year: number) => 75 + (year - 2021) * 150
  const y = (value: number) => 245 - 175 * (value - min) / span
  const yTicks = Array.from({ length: 5 }, (_, index) => min + span * index / 4)
  const band = [...summaries.map((row) => `${x(row.year)},${y(row.q3)}`), ...[...summaries].reverse().map((row) => `${x(row.year)},${y(row.q1)}`)].join(' ')
  return <div className="chart-card">
    <div className="chart-title"><strong>{definition.label}</strong><span>Median and middle 50% of software for each year</span></div>
    <svg className="time-chart" viewBox="0 0 900 300" role="img" aria-label={`${definition.label} aggregate trend`}>
      {yTicks.map((tick, index) => <g key={index}><line x1="75" x2="825" y1={y(tick)} y2={y(tick)} className="grid-line" /><text x="67" y={y(tick) + 3} textAnchor="end">{formatNumber(tick, definition.unit)}</text></g>)}
      {years.map((year) => <g key={year}><line x1={x(year)} x2={x(year)} y1="50" y2="250" className="grid-line" /><text x={x(year)} y="278" textAnchor="middle">{year}</text></g>)}
      {dataset.methodology.ai_context.map((event) => { const date = new Date(`${event.date}T00:00:00Z`); const position = x(date.getUTCFullYear() + date.getUTCMonth() / 12); return <g key={event.date}><line x1={position} x2={position} y1="45" y2="250" className="ai-marker" /><title>{event.label}</title></g> })}
      <polygon points={band} className="trend-band"><title>Interquartile range: the middle 50% of observed software</title></polygon>
      <polyline points={summaries.map((row) => `${x(row.year)},${y(row.median)}`).join(' ')} className="trend-median" />
      {summaries.map((row) => <circle key={row.year} cx={x(row.year)} cy={y(row.median)} r="5" className="history-dot"><title>{row.year}: median {formatNumber(row.median, definition.unit)}; Q1 {formatNumber(row.q1, definition.unit)}; Q3 {formatNumber(row.q3, definition.unit)}; n={row.n}</title></circle>)}
    </svg>
    <div className="trend-key"><span><i className="key-band" />Middle 50%</span><span><i className="key-line" />Median</span><span><i className="key-ai" />AI-tooling milestone</span></div>
  </div>
}
