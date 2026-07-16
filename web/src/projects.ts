import type { ExemplarLabels, ProjectSummary } from './types'

export const labelNames: Record<keyof ExemplarLabels, string> = {
  usage_exemplar: 'Usage best practices',
  repository_practice_exemplar: 'Repository best practices',
  complete_assessment: 'Complete assessment',
  practice_exemplar: 'Best practices across all areas',
}

export function activeLabelKeys(labels: ExemplarLabels): (keyof ExemplarLabels)[] {
  return (Object.keys(labels) as (keyof ExemplarLabels)[]).filter((key) => labels[key])
}

export interface SoftwareFilters {
  query?: string
  language?: string
  category?: string
  tag?: string
  exemplar?: 'usage' | 'repository' | 'all' | string
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
  return `#/projects${query ? `?${query}` : ''}`
}

export function filterSoftware(projects: ProjectSummary[], filters: SoftwareFilters): ProjectSummary[] {
  const query = (filters.query ?? '').trim().toLowerCase()
  const language = filters.language ?? 'all'
  const category = filters.category ?? 'all'
  return projects.filter((project) => {
    const text = `${project.name} ${project.description ?? ''} ${project.category ?? ''} ${project.tags.join(' ')}`.toLowerCase()
    const exemplar = filters.exemplar === 'usage'
      ? project.labels.usage_exemplar
      : filters.exemplar === 'repository'
        ? project.labels.repository_practice_exemplar
        : filters.exemplar === 'all'
          ? project.labels.practice_exemplar
          : true
    const practice = filters.practice ? project.repository.practices[filters.practice] === (filters.outcome === 'pass') : true
    const robustness = filters.robustness
      ? project.contracts.some((contract) => contract.check_id === filters.robustness && (
        filters.outcome === 'pass' ? contract.status === 'PASS' : contract.status === 'FAIL'
      ))
      : true
    return text.includes(query)
      && (language === 'all' || project.languages.includes(language))
      && (category === 'all' || project.category === category)
      && (!filters.tag || project.tags.includes(filters.tag))
      && exemplar
      && practice
      && robustness
  })
}

export function filterProjects(projects: ProjectSummary[], query: string, language: string, category: string): ProjectSummary[] {
  return filterSoftware(projects, { query, language, category })
}
