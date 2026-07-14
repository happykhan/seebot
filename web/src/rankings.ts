import type { AwardRanking } from './types'

export type RankingSort = 'score' | 'name' | 'contracts' | 'repository' | 'recipe'

export function filterAndSortRankings(
  rankings: AwardRanking[],
  query: string,
  category: string,
  sort: RankingSort,
): AwardRanking[] {
  const normalized = query.trim().toLowerCase()
  return rankings
    .filter((item) =>
      (category === 'all' || item.category === category)
      && (!normalized || `${item.name} ${item.description} ${item.category}`.toLowerCase().includes(normalized)),
    )
    .sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name)
      if (sort === 'contracts') return b.breakdown.contracts - a.breakdown.contracts || a.name.localeCompare(b.name)
      if (sort === 'repository') return b.breakdown.repository - a.breakdown.repository || a.name.localeCompare(b.name)
      if (sort === 'recipe') return b.breakdown.recipe_test - a.breakdown.recipe_test || a.name.localeCompare(b.name)
      return b.score - a.score || a.name.localeCompare(b.name)
    })
}

export function rankingPage(rankings: AwardRanking[], page: number, pageSize: number) {
  const pages = Math.max(1, Math.ceil(rankings.length / pageSize))
  const currentPage = Math.max(1, Math.min(page, pages))
  return {
    currentPage,
    pages,
    items: rankings.slice((currentPage - 1) * pageSize, currentPage * pageSize),
  }
}
