import { describe, expect, it } from 'vitest'
import { filterAndSortRankings, rankingPage } from './rankings'
import type { AwardRanking } from './types'

function ranking(index: number): AwardRanking {
  return {
    package_id: `tool-${index}__1__0__noarch`, name: `tool-${String(index).padStart(3, '0')}`,
    version: '1', build: '0', subdir: 'noarch', category: index % 2 ? 'assembly' : 'qc',
    description: `Tool ${index}`, upstream_url: 'https://example.test', run_id: 'pilot',
    languages: ['python'],
    score: index, maximum_points: 100, eligible: true, missing_checks: [], tier: 'Reviewed',
    tier_colour: '#000', breakdown: { contracts: index, repository: 0, recipe_test: 0 }, rank: index,
  }
}

describe('scalable tool directory', () => {
  it('paginates a 200-tool cohort into bounded pages', () => {
    const rankings = Array.from({ length: 200 }, (_, index) => ranking(index + 1))
    const page = rankingPage(rankings, 8, 25)
    expect(page.pages).toBe(8)
    expect(page.items).toHaveLength(25)
    expect(page.items[0].name).toBe('tool-176')
  })

  it('filters and sorts without changing the input array', () => {
    const rankings = [ranking(2), ranking(1)]
    const result = filterAndSortRankings(rankings, 'tool', 'assembly', 'name')
    expect(result.map((item) => item.name)).toEqual(['tool-001'])
    expect(rankings.map((item) => item.name)).toEqual(['tool-002', 'tool-001'])
  })
})
