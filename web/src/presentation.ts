import type { NativeRule } from './types'

export interface RuleSummary {
  visible: NativeRule[]
  hiddenTypeCount: number
  hiddenFindingCount: number
}

export function summarizeRules(rules: NativeRule[] = [], limit = 8): RuleSummary {
  const ordered = [...rules].sort((left, right) => right.count - left.count || left.rule.localeCompare(right.rule))
  const visible = ordered.slice(0, limit)
  const hidden = ordered.slice(limit)
  return {
    visible,
    hiddenTypeCount: hidden.length,
    hiddenFindingCount: hidden.reduce((total, rule) => total + rule.count, 0),
  }
}

export interface SeverityDescription {
  summary: string
  vector: string | null
}

const metricValues: Record<string, Record<string, string>> = {
  AV: { N: 'Network access', A: 'Adjacent-network access', L: 'Local access', P: 'Physical access' },
  AC: { L: 'Low attack complexity', H: 'High attack complexity' },
  AT: { N: 'No extra attack conditions', P: 'Additional attack conditions required' },
  PR: { N: 'No privileges required', L: 'Low privileges required', H: 'High privileges required' },
  UI: { N: 'No user action', R: 'User action required', P: 'Passive user action', A: 'Active user action' },
  S: { U: 'Impact stays within the vulnerable system', C: 'Impact can cross a security boundary' },
}

const impactNames: Record<string, string> = {
  C: 'confidentiality', I: 'integrity', A: 'availability',
  VC: 'vulnerable-system confidentiality', VI: 'vulnerable-system integrity', VA: 'vulnerable-system availability',
  SC: 'subsequent-system confidentiality', SI: 'subsequent-system integrity', SA: 'subsequent-system availability',
}

export function describeSeverity(value: string): SeverityDescription {
  const vectorStart = value.indexOf('CVSS:')
  if (vectorStart < 0) return { summary: value.replaceAll('_', ' '), vector: null }
  const vector = value.slice(vectorStart)
  const metrics = Object.fromEntries(vector.split('/').slice(1).map((part) => part.split(':', 2)).filter((pair) => pair.length === 2))
  const parts = ['AV', 'AC', 'AT', 'PR', 'UI', 'S']
    .map((metric) => metricValues[metric]?.[metrics[metric]])
    .filter((part): part is string => Boolean(part))
  const impacts = Object.entries(impactNames)
    .filter(([metric]) => metrics[metric] === 'H' || metrics[metric] === 'L')
    .map(([metric, name]) => `${metrics[metric] === 'H' ? 'High' : 'Low'} ${name} impact`)
  parts.push(...impacts)
  return { summary: parts.join(' · ') || 'CVSS impact characteristics available', vector }
}
