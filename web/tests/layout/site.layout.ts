import { expect, test, type Locator, type Page } from '@playwright/test'

const routes = [
  ['/#/', 'A review of bioinformatics software practices'],
  ['/#/explore', 'Patterns across bioinformatics software'],
  ['/#/software', 'Find a bioinformatics software report'],
  ['/#/guidance', 'Assess your own bioinformatics software'],
  ['/#/software/any2fasta', 'any2fasta'],
] as const

async function ready(page: Page, path: string, heading: string): Promise<void> {
  await page.goto(path)
  await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible()
}

async function expectNoHorizontalOverflow(page: Page): Promise<void> {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }))
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport + 1)
}

async function boxes(locator: Locator) {
  return locator.evaluateAll((elements) => elements.map((element) => {
    const box = element.getBoundingClientRect()
    return { top: box.top, left: box.left, width: box.width, height: box.height }
  }))
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
})

test.describe('desktop layout', () => {
  test.skip(({ isMobile }) => isMobile)

  test('critical pages render without horizontal overflow', async ({ page }) => {
    for (const [path, heading] of routes) {
      await test.step(path, async () => {
        await ready(page, path, heading)
        await expect(page.locator('main')).toBeVisible()
        await expectNoHorizontalOverflow(page)
      })
    }
  })

  test('overview cards retain a multi-column layout', async ({ page }) => {
    await ready(page, '/#/', routes[0][1])
    const cards = await boxes(page.locator('.best-practice-grid > a'))
    expect(cards).toHaveLength(4)
    expect(Math.abs(cards[0].top - cards[1].top)).toBeLessThan(2)
    expect(cards[0].width).toBeGreaterThan(180)
  })

  test('guidance and report sections retain their page-width layouts', async ({ page }) => {
    await ready(page, '/#/guidance', routes[3][1])
    const mainWidth = await page.locator('main').evaluate((element) => element.getBoundingClientRect().width)
    const guidanceCards = await boxes(page.locator('.guidance-checklist > article'))
    expect(guidanceCards).toHaveLength(4)
    expect(guidanceCards.every((card) => card.width >= mainWidth * 0.85)).toBe(true)

    await ready(page, '/#/software/any2fasta', routes[4][1])
    await expect(page.getByRole('heading', { name: 'Maintenance and repository practices' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Current source-code measurements' })).toBeVisible()
    await expect(page.locator('.report-section')).toHaveCount(5)
  })
})

test.describe('mobile layout', () => {
  test.skip(({ isMobile }) => !isMobile)

  test('critical pages render without horizontal overflow', async ({ page }) => {
    for (const [path, heading] of routes) {
      await test.step(path, async () => {
        await ready(page, path, heading)
        await expectNoHorizontalOverflow(page)
      })
    }
  })

  test('overview cards and guidance items collapse to one column', async ({ page }) => {
    await ready(page, '/#/', routes[0][1])
    const cards = await boxes(page.locator('.best-practice-grid > a'))
    expect(cards).toHaveLength(4)
    expect(cards[1].top).toBeGreaterThan(cards[0].top + cards[0].height - 2)
    expect(Math.abs(cards[0].left - cards[1].left)).toBeLessThan(2)

    await ready(page, '/#/guidance', routes[3][1])
    const columns = await page.locator('.guidance-checklist article > div').first().evaluate(
      (element) => getComputedStyle(element).gridTemplateColumns,
    )
    expect(columns.trim().split(/\s+/)).toHaveLength(1)
  })
})
