export interface ExemplarLabels {
  usage_exemplar: boolean
  repository_practice_exemplar: boolean
  complete_assessment: boolean
  practice_exemplar: boolean
}
export interface ProjectSummary {
  id: string
  name: string
  description: string | null
  category: string | null
  tags: string[]
  included: boolean
  exclusion_code: string | null
  repository_url: string | null
  snapshot_date: string
  languages: string[]
  primary_executable: string | null
  valid_run_status: 'not_designed' | 'draft' | 'reviewed' | 'untestable'
  curation_status: 'unreviewed' | 'in_review' | 'reviewed' | 'adjudication_required'
  labels: ExemplarLabels
}

export interface DatasetSummary {
  catalogued_projects: number
  included_projects: number
  language_counts: Record<string, number>
  labels: {
    usage_exemplars: number
    repository_practice_exemplars: number
    complete_assessments: number
    practice_exemplars: number
  }
}

export interface Dataset {
  schema_version: 2
  snapshot_date: string
  projects: ProjectSummary[]
  summary: DatasetSummary
}
