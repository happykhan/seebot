export type Status =
  | 'PASS'
  | 'FAIL'
  | 'PARTIAL'
  | 'NOT_APPLICABLE'
  | 'UNTESTABLE'
  | 'ERROR'
  | 'NOT_RUN'

export interface CheckResult {
  schema_version: number
  run_id: string
  package_id: string
  check_id: string
  domain: string
  status: Status
  result_kind: 'CONTRACT' | 'MEASUREMENT'
  applicability: string
  method: string
  expected: Record<string, unknown>
  observed: Record<string, unknown>
  tool: { name: string; version: string }
  command: string[] | null
  started_at: string
  duration_seconds: number
  environment_id: string
  config_sha256: string
  evidence: { stdout: string; stderr: string; metadata: string }
  notes: string | null
}

export interface PackageSummary {
  package_id: string
  name: string
  version: string
  build: string
  subdir: string
  category: string
  description: string
  upstream_url: string
  run_id: string
  languages: string[]
}

export interface AwardRanking extends PackageSummary {
  score: number
  maximum_points: number
  eligible: boolean
  missing_checks: string[]
  tier: string
  tier_colour: string
  breakdown: {
    testing: number
    documentation: number
    reproducibility: number
    automation: number
    reuse_attribution: number
  }
  assessment_coverage: number
  category_coverage: Record<string, number>
  unknown_signals: string[]
  rank: number | null
}

export interface RankingData {
  schema_version: number
  rubric_version: string
  title: string
  scope_note: string
  provisional: boolean
  rankings: AwardRanking[]
}

export interface ProfileMetric {
  check_id: string
  label: string
  value: number
  unit: string
  higher_is_better: boolean
  cohort_size: number
  percentile: number | null
  interpretation: 'favourable' | 'unfavourable' | 'typical' | 'provisional' | 'insufficient'
}

export interface LanguageProfile {
  language: string
  metrics: ProfileMetric[]
  measured_count: number
}

export interface PackageProfileData { package_id: string; languages: LanguageProfile[] }

export interface ProfilesData {
  schema_version: number
  interpretation_version: string
  comparison_policy: string
  minimum_provisional_cohort: number
  minimum_classified_cohort: number
  profiles: PackageProfileData[]
}
