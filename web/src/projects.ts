import type { ExemplarLabels, ProjectSummary } from './types'

export const labelNames: Record<keyof ExemplarLabels, string> = {
  usage_exemplar: 'Usage best practices',
  repository_practice_exemplar: 'Repository best practices',
  complete_assessment: 'Complete assessment',
  practice_exemplar: 'Best practices across all areas',
}

export type PracticeArea = 'repository' | 'source' | 'usage' | 'dependencies'

export const practiceAreas: Record<PracticeArea, { short: string, label: string, description: string }> = {
  repository: { short: 'R', label: 'Repository', description: 'Meets repository best practices' },
  source: { short: 'S', label: 'Source', description: 'Complete current source-code assessment' },
  usage: { short: 'U', label: 'Usage', description: 'Meets command-line usage best practices' },
  dependencies: { short: 'D', label: 'Dependencies', description: 'Runtime dependencies were scanned and no known vulnerabilities were found' },
}

export function projectAchievements(project: ProjectSummary): PracticeArea[] {
  const current = (project.source_snapshots ?? []).filter((snapshot) => snapshot.snapshot_date === '2026-07-01')
  const source = current.length > 0 && current.every((snapshot) => !['ERROR', 'UNTESTABLE', 'NOT_RUN'].includes(snapshot.status) && Object.keys(snapshot.metrics).length > 0)
  const dependency = project.dependency_advisories?.observed ?? {}
  const dependencies = dependency.coverage_status === 'runtime_scanned'
    && dependency.runtime_advisory_count === 0
  return [
    ...(project.labels.repository_practice_exemplar ? ['repository' as const] : []),
    ...(source ? ['source' as const] : []),
    ...(project.labels.usage_exemplar ? ['usage' as const] : []),
    ...(dependencies ? ['dependencies' as const] : []),
  ]
}

export function activeLabelKeys(labels: ExemplarLabels): (keyof ExemplarLabels)[] {
  return (Object.keys(labels) as (keyof ExemplarLabels)[]).filter((key) => labels[key])
}

export interface SoftwareFilters {
  query?: string
  language?: string
  category?: string
  tag?: string
  exemplar?: PracticeArea | string
  dependencyCoverage?: string
  practice?: string
  robustness?: string
  outcome?: 'pass' | 'fail' | string
}

export function softwareHref(filters: SoftwareFilters = {}): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value && !(['language', 'category'].includes(key) && value === 'all')) params.set(key, value)
  })
  const query = params.toString()
  return `#/software${query ? `?${query}` : ''}`
}

export function filterSoftware(projects: ProjectSummary[], filters: SoftwareFilters): ProjectSummary[] {
  const query = (filters.query ?? '').trim().toLowerCase()
  const language = filters.language ?? 'all'
  const category = filters.category ?? 'all'
  return projects.filter((project) => {
    const text = `${project.name} ${project.description ?? ''} ${project.category ?? ''} ${project.tags.join(' ')}`.toLowerCase()
    const exemplar = filters.exemplar === 'all'
      ? project.labels.practice_exemplar
      : filters.exemplar
        ? projectAchievements(project).includes(filters.exemplar as PracticeArea)
        : true
    const practice = filters.practice ? project.repository.practices[filters.practice] === (filters.outcome === 'pass') : true
    const robustness = filters.robustness
      ? project.contracts.some((contract) => contract.check_id === filters.robustness && (
        filters.outcome === 'pass' ? contract.status === 'PASS' : contract.status === 'FAIL'
      ))
      : true
    const dependencyCoverage = filters.dependencyCoverage
      ? project.dependency_advisories.observed.coverage_status === filters.dependencyCoverage
      : true
    return text.includes(query)
      && (language === 'all' || project.languages.includes(language))
      && (category === 'all' || project.category === category)
      && (!filters.tag || project.tags.includes(filters.tag))
      && exemplar
      && practice
      && robustness
      && dependencyCoverage
  })
}

export function filterProjects(projects: ProjectSummary[], query: string, language: string, category: string): ProjectSummary[] {
  return filterSoftware(projects, { query, language, category })
}
