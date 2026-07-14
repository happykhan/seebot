import { describe, expect, it } from 'vitest'
import { displayStatus, packageMetrics } from './metrics'
import type { CheckResult } from './types'

function result(check_id: string, observed: Record<string, unknown>, result_kind: 'CONTRACT' | 'MEASUREMENT' = 'MEASUREMENT'): CheckResult {
  return {
    schema_version: 1, run_id: 'pilot', package_id: 'tool__1__0__noarch', check_id,
    domain: 'python', status: 'PASS', result_kind, applicability: 'APPLICABLE', method: 'automated',
    expected: {}, observed, tool: { name: 'tool', version: '1' }, command: null,
    started_at: '2026-01-01T00:00:00Z', duration_seconds: 1, environment_id: 'test',
    config_sha256: '0'.repeat(64), evidence: { stdout: '', stderr: '', metadata: '' }, notes: null,
  }
}

describe('result presentation', () => {
  it('labels completed measurements without implying package success', () => {
    expect(displayStatus(result('PY-RUFF-001', {}))).toBe('MEASURED')
    expect(displayStatus(result('CLI-HELP-001', {}, 'CONTRACT'))).toBe('PASS')
  })

  it('normalizes finding counts by measured source lines', () => {
    const metrics = packageMetrics([
      result('PY-RUFF-001', { finding_count: 25, nonblank_noncomment_lines: 2500 }),
      result('PY-PYLINT-001', { message_count: 50 }),
    ])
    expect(metrics[0]).toMatchObject({ value: '10.0', note: '25 findings' })
    expect(metrics[1]).toMatchObject({ value: '20.0', note: '50 messages' })
  })
})
