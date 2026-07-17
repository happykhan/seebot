import { describe, expect, it } from 'vitest'
import { contractCatalogue, describeRule, ruleDocumentationUrl } from './catalogue'
import { analyzerRuleMetadata } from './ruleMetadata'
import { compatibleMetricLanguages, selectMetricPoints } from './charts'
import { practiceAreas, softwareHref } from './projects'
import { describeSeverity, summarizeRules } from './presentation'
import type { MetricPoint, NativeRule } from './types'

describe('public reporting contracts', () => {
  it('keeps the four assessment areas and canonical Software route', () => {
    expect(Object.keys(practiceAreas)).toEqual(['repository', 'source', 'usage', 'dependencies'])
    expect(softwareHref()).toBe('#/software')
    expect(softwareHref({ exemplar: 'dependencies' })).toBe('#/software?exemplar=dependencies')
    expect(softwareHref({ dependencyCoverage: 'no_supported_input' }))
      .toBe('#/software?dependencyCoverage=no_supported_input')
  })

  it('does not apply an incompatible language filter to repository observations', () => {
    const repositoryPoints: MetricPoint[] = [
      { project_id: 'one', value: 10 },
      { project_id: 'two', value: 20 },
    ]
    expect(compatibleMetricLanguages(repositoryPoints)).toEqual([])
    expect(selectMetricPoints(repositoryPoints, 'python')).toEqual(repositoryPoints)
  })

  it('filters language-specific source observations when that language exists', () => {
    const sourcePoints: MetricPoint[] = [
      { project_id: 'one', language: 'python', value: 10 },
      { project_id: 'two', language: 'rust', value: 20 },
    ]
    expect(compatibleMetricLanguages(sourcePoints)).toEqual(['python', 'rust'])
    expect(selectMetricPoints(sourcePoints, 'python')).toEqual([sourcePoints[0]])
  })

  it('keeps a plain-language catalogue entry for Bandit B102', () => {
    expect(describeRule('bandit', 'B102')).toContain('exec')
    expect(describeRule('bandit', 'B102')).toContain('risky')
  })

  it('publishes exact metadata and specific documentation links for observed Python rules', () => {
    expect(Object.keys(analyzerRuleMetadata)).toHaveLength(319)
    expect(describeRule('ruff', 'E501')).toContain('maximum character length')
    expect(ruleDocumentationUrl('ruff', 'E501')).toBe('https://docs.astral.sh/ruff/rules/line-too-long/')
    expect(describeRule('pylint', 'import-outside-toplevel')).toContain('module toplevel')
    expect(ruleDocumentationUrl('pylint', 'import-outside-toplevel'))
      .toBe('https://pylint.readthedocs.io/en/latest/user_guide/messages/convention/import-outside-toplevel.html')
    expect(describeRule('bandit', 'B603')).toContain('without the use of a command shell')
    expect(ruleDocumentationUrl('bandit', 'B603'))
      .toBe('https://bandit.readthedocs.io/en/latest/plugins/b603_subprocess_without_shell_equals_true.html')
  })

  it('summarizes the largest rule categories and groups the remainder', () => {
    const rules: NativeRule[] = [
      { rule: 'small', count: 2 }, { rule: 'largest', count: 20 }, { rule: 'middle', count: 5 },
    ]
    expect(summarizeRules(rules, 2)).toEqual({
      visible: [rules[1], rules[2]], hidden: [rules[0]], hiddenTypeCount: 1, hiddenFindingCount: 2,
    })
  })

  it('translates a CVSS vector into practical attack and impact characteristics', () => {
    const description = describeSeverity('CVSS_V3:CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N')
    expect(description.summary).toContain('Local access')
    expect(description.summary).toContain('Low privileges required')
    expect(description.summary).toContain('High integrity impact')
    expect(description.vector).toBe('CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:H/A:N')
  })

  it('describes the valid no-record input contract in the usage catalogue', () => {
    const contract = contractCatalogue['CLI-SEMANTICALLY-EMPTY-INPUT-001']
    expect(contract.label).toBe('Valid input with no records')
    expect(contract.expectation).toContain('zero records')
  })
})
