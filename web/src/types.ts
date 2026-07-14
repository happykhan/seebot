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

