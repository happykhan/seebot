import type { ExemplarLabels, ProjectSummary } from './types'

export const labelNames: Record<keyof ExemplarLabels, string> = {
  usage_exemplar: 'Usage exemplar',
  repository_practice_exemplar: 'Repository-practice exemplar',
  complete_assessment: 'Complete assessment',
  practice_exemplar: 'Practice exemplar',
}

export function activeLabelKeys(labels: ExemplarLabels): (keyof ExemplarLabels)[] {
  return (Object.keys(labels) as (keyof ExemplarLabels)[]).filter((key) => labels[key])
}

export function filterProjects(
  projects: ProjectSummary[],
  query: string,
  language: string,
  category: string,
): ProjectSummary[] {
  const normalizedQuery = query.trim().toLowerCase()
  return projects.filter((project) => {
    const text = `${project.name} ${project.description ?? ''} ${project.category ?? ''} ${project.tags.join(' ')}`.toLowerCase()
    return (
      text.includes(normalizedQuery)
      && (language === 'all' || project.languages.includes(language))
      && (category === 'all' || project.category === category)
    )
  })
}
