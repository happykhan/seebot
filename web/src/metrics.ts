import type { CheckResult } from './types'

const titles: Record<string, string> = {
  'PKG-IDENTITY-001': 'Installed version identified',
  'CLI-HELP-001': 'Help command terminates',
  'CLI-HELP-CONTENT-001': 'Help explains the interface',
  'CLI-VERSION-001': 'Version command terminates',
  'CLI-INVALID-001': 'Invalid option rejected',
  'CLI-ERROR-QUALITY-001': 'Invalid option gives a clean diagnostic',
  'CLI-NOARGS-001': 'No-argument behaviour observed',
  'CLI-REPEAT-001': 'Help behaviour repeated',
  'CLI-FUNCTIONAL-001': 'Miniature analysis reproduced',
  'REPO-PRACTICES-001': 'Upstream project practices',
  'PY-RUFF-001': 'Ruff observations',
  'PY-PYLINT-001': 'Pylint observations',
  'PY-RADON-001': 'Cyclomatic complexity',
  'PY-INTERROGATE-001': 'Docstring coverage',
  'PY-VULTURE-001': 'Dead-code candidates',
  'PY-BANDIT-001': 'Security indicators',
  'PERL-COMPILE-001': 'Perl syntax observation',
  'PERL-CRITIC-001': 'Perl::Critic observations',
  'PERL-COMPLEXITY-001': 'Perl complexity',
  'PERL-POD-001': 'POD documentation coverage',
  'C-CLANGTIDY-001': 'clang-tidy observations',
  'C-CPPCHECK-001': 'Cppcheck observations',
  'C-COMPLEXITY-001': 'C complexity',
  'C-DOXYGEN-001': 'C API documentation',
  'CPP-CLANGTIDY-001': 'clang-tidy observations',
  'CPP-CPPCHECK-001': 'Cppcheck observations',
  'RS-CHECK-001': 'Cargo check observation',
  'RS-FMT-001': 'Rust formatting observation',
  'RS-CLIPPY-001': 'Clippy observations',
  'RS-COMPLEXITY-001': 'Rust complexity',
  'RS-DOCS-001': 'Rust documentation build',
  'RS-UNSAFE-001': 'Unsafe-code indicators',
  'RS-AUDIT-001': 'Rust dependency advisory indicators',
}

export function contractTitle(checkId: string): string { return titles[checkId] ?? checkId }

export function displayStatus(result: CheckResult): string {
  if (result.result_kind === 'MEASUREMENT' && result.status === 'PASS') return 'MEASURED'
  return result.status.replaceAll('_', ' ')
}

function observed(results: CheckResult[], checkId: string): Record<string, unknown> {
  return results.find((result) => result.check_id === checkId)?.observed ?? {}
}

function number(value: unknown): number { return typeof value === 'number' ? value : 0 }
function rate(count: number, lines: number): string { return lines ? (count * 1000 / lines).toFixed(1) : '—' }

export interface CohortMetric {
  key: string
  label: string
  value: number
  unit: string
}

export function cohortMetricValues(results: CheckResult[]): CohortMetric[] {
  const ruff = observed(results, 'PY-RUFF-001')
  const pylint = observed(results, 'PY-PYLINT-001')
  const radon = observed(results, 'PY-RADON-001')
  const docs = observed(results, 'PY-INTERROGATE-001')
  const vulture = observed(results, 'PY-VULTURE-001')
  const bandit = observed(results, 'PY-BANDIT-001')
  const lines = number(ruff.nonblank_noncomment_lines)
  const perThousand = (count: unknown) => lines ? number(count) * 1000 / lines : 0
  return [
    { key: 'ruff', label: 'Ruff findings', value: perThousand(ruff.finding_count), unit: '/ 1k lines' },
    { key: 'pylint', label: 'Pylint messages', value: perThousand(pylint.message_count), unit: '/ 1k lines' },
    { key: 'docstrings', label: 'Docstring coverage', value: number(docs.docstring_coverage_percent), unit: '%' },
    { key: 'complexity', label: 'Mean complexity', value: number(radon.complexity_mean), unit: '' },
    { key: 'vulture', label: 'Vulture candidates', value: perThousand(vulture.candidate_count), unit: '/ 1k lines' },
    { key: 'bandit', label: 'Bandit indicators', value: perThousand(bandit.indicator_count), unit: '/ 1k lines' },
  ]
}

export function packageMetrics(results: CheckResult[]) {
  const ruff = observed(results, 'PY-RUFF-001')
  const pylint = observed(results, 'PY-PYLINT-001')
  const radon = observed(results, 'PY-RADON-001')
  const docs = observed(results, 'PY-INTERROGATE-001')
  const vulture = observed(results, 'PY-VULTURE-001')
  const bandit = observed(results, 'PY-BANDIT-001')
  const repository = observed(results, 'REPO-PRACTICES-001')
  const lines = number(ruff.nonblank_noncomment_lines)
  const severity = bandit.indicators_by_severity as Record<string, number> | undefined
  return Object.assign([
    { value: `${rate(number(ruff.finding_count), lines)}`, label: 'Ruff findings / 1k lines', note: `${number(ruff.finding_count)} findings` },
    { value: `${rate(number(pylint.message_count), lines)}`, label: 'Pylint messages / 1k lines', note: `${number(pylint.message_count)} messages` },
    { value: `${number(docs.docstring_coverage_percent).toFixed(1)}%`, label: 'Docstring coverage', note: 'public API observation' },
    { value: `${number(radon.complexity_max)}`, label: 'Maximum complexity', note: `mean ${number(radon.complexity_mean).toFixed(1)}` },
    { value: `${rate(number(vulture.candidate_count), lines)}`, label: 'Vulture candidates / 1k lines', note: `${number(vulture.candidate_count)} candidates` },
    { value: `${number(bandit.indicator_count)}`, label: 'Bandit indicators', note: `${severity?.MEDIUM ?? 0} medium · ${severity?.HIGH ?? 0} high` },
  ], {
    repository,
  })
}
