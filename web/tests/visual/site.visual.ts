import { expect, test, type Page } from '@playwright/test'

async function ready(page: Page, path: string): Promise<void> {
  await page.goto(path)
  await page.locator('main').waitFor()
  await page.evaluate(async () => { await document.fonts.ready })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear())
  await page.emulateMedia({ colorScheme: 'light', reducedMotion: 'reduce' })
})

test.describe('desktop visual baselines', () => {
  test.skip(({ isMobile }) => isMobile)

  test('overview', async ({ page }) => {
    await ready(page, '/#/')
    await expect(page).toHaveScreenshot('overview.png', { fullPage: true })
  })

  test('guidance checklist', async ({ page }) => {
    await ready(page, '/#/guidance')
    await expect(page).toHaveScreenshot('guidance.png', { fullPage: true })
  })

  test('explore', async ({ page }) => {
    await ready(page, '/#/explore')
    await expect(page).toHaveScreenshot('explore.png', { fullPage: true })
  })

  test('software directory', async ({ page }) => {
    await ready(page, '/#/software')
    await expect(page).toHaveScreenshot('software-directory.png', { fullPage: true })
  })

  test('software report sections', async ({ page }) => {
    await ready(page, '/#/software/any2fasta')
    await expect(page.locator('.project-report > header')).toHaveScreenshot('software-report-header.png')
    const repository = page.locator('.report-section').filter({ has: page.getByRole('heading', { name: 'Maintenance and repository practices' }) })
    const source = page.locator('.report-section').filter({ has: page.getByRole('heading', { name: 'Current source-code measurements' }) })
    await expect(repository).toHaveScreenshot('repository-section.png')
    await expect(source).toHaveScreenshot('source-section.png')
  })
})

test.describe('mobile visual baselines', () => {
  test.skip(({ isMobile }) => !isMobile)

  test('overview', async ({ page }) => {
    await ready(page, '/#/')
    await expect(page).toHaveScreenshot('overview-mobile.png', { fullPage: true })
  })

  test('guidance checklist', async ({ page }) => {
    await ready(page, '/#/guidance')
    await expect(page.locator('.guidance-page')).toHaveScreenshot('guidance-mobile.png')
  })

  test('software directory', async ({ page }) => {
    await ready(page, '/#/software')
    await expect(page).toHaveScreenshot('software-directory-mobile.png', { fullPage: true })
  })
})
