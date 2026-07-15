export interface ExemplarLabels {
  usage_exemplar: boolean
  repository_practice_exemplar: boolean
  complete_assessment: boolean
  practice_exemplar: boolean
}

export type ObservationStatus =
  | 'PASS' | 'FAIL' | 'OBSERVED' | 'NOT_OBSERVED' | 'NOT_APPLICABLE'
  | 'UNTESTABLE' | 'ERROR' | 'NOT_RUN' | 'NOT_EXISTING'

export interface ProbeObservation {
  probe_id: string
  status: ObservationStatus
  status_text: string
  command: string[] | null
  observed: Record<string, unknown>
  notes: string | null
  evidence: Record<string, string>
}

export interface ContractObservation {
  check_id: string
  status: ObservationStatus
  label: string
  domain: 'usage' | 'robustness'
  probes: ProbeObservation[]
}

export interface NativeFinding {
  kind: 'lint' | 'security'
  status: ObservationStatus
  language?: string
  analyzer?: string
  finding_count?: number
  findings_per_kloc?: number | null
  rules?: NativeRule[]
  reason?: string
}

export interface NativeRule {
  rule: string
  count: number
  findings_per_kloc?: number | null
  native_category?: string | null
  native_severity?: string | null
  native_confidence?: string | null
}

export interface SourceSnapshot {
  snapshot_date: string
  snapshot_commit: string | null
  language: string
  status: ObservationStatus
  metrics: {
    inventory?: Record<string, unknown>
    files?: Record<string, unknown>
    functions?: Record<string, unknown>
    complexity?: Record<string, unknown>
    duplication?: Record<string, unknown>
    documentation?: Record<string, unknown>
    dead_code?: Record<string, unknown>
  }
  native_findings: NativeFinding[]
}

export interface ProjectSummary {
  id: string
  name: string
  description: string | null
  category: string | null
  tags: string[]
  included: boolean
  primary_language: string
  languages: string[]
  repository: {
    id: string
    url: string
    snapshot_date: string
    snapshot_commit: string
    activity: Record<string, unknown>
    releases: Record<string, unknown>
    practices: Record<string, boolean>
    documentation: Record<string, unknown>
    standard_tests: Record<string, unknown>
    verification_ci: Record<string, unknown>
  }
  installation: {
    adapter: string
    artifact: string
    version: string
    build: string
    subdir: string
    artifact_sha256: string
  }
  primary_executable: string | null
  curation_status: string
  contracts: ContractObservation[]
  source_snapshots: SourceSnapshot[]
  dependency_advisories: {
    status: ObservationStatus
    observed: Record<string, unknown>
  }
  labels: ExemplarLabels
  results: Record<string, unknown>[]
}

export interface MetricPoint {
  project_id: string
  value: number
  language?: string
  analyzer?: string
}

export interface AggregateRule extends NativeRule {
  kind: 'lint' | 'security'
  language: string
  analyzer: string
  project_count: number
  projects: string[]
}

export interface Dataset {
  schema_version: 2
  snapshot_date: string
  historical_snapshot_dates: string[]
  methodology: {
    no_quality_score: boolean
    upstream_tests_executed: boolean
    test_source_in_code_metrics: boolean
    canonical_platform: string
    candidate_survey_size: number
    eligible_cli_projects_found: number
    first_200_eligible_reached_at_rank: number
    distribution_policy: Record<string, string>
    ai_context: { date: string, label: string, url: string }[]
  }
  summary: {
    assessed_projects: number
    labels: {
      usage_exemplars: number
      repository_practice_exemplars: number
      complete_assessments: number
      practice_exemplars: number
    }
  }
  aggregate: {
    primary_language_counts: Record<string, number>
    component_language_counts: Record<string, number>
    category_counts: Record<string, number>
    repository_practice_counts: Record<string, number>
    robustness: {
      check_id: string
      label: string
      statuses: Record<string, number>
    }[]
    metric_points: Record<string, MetricPoint[]>
    native_rules: AggregateRule[]
  }
  projects: ProjectSummary[]
}
