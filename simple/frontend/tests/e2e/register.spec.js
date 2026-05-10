import { expect, test } from '@playwright/test'

test('пользователь может зарегистрироваться через интерфейс', async ({ page }) => {
  const suffix = Date.now()
  const username = `e2e-user-${suffix}`
  const email = `e2e-user-${suffix}@example.com`
  const phone = `+7${String(suffix).slice(-10).padStart(10, '0')}`

  await page.goto('/register')

  const fieldInput = (label) => page.locator('.field').filter({ hasText: label }).locator('input').first()

  await fieldInput('Логин').fill(username)
  await fieldInput('Фамилия').fill('Тестов')
  await fieldInput('Имя').fill('Егор')
  await fieldInput('Электронная почта').fill(email)
  await fieldInput('Телефон').fill(phone)
  await fieldInput('Пароль').fill('StrongPass123!')

  await page.getByRole('button', { name: 'Продолжить' }).click()
  await page.getByRole('button', { name: 'Пропустить и зарегистрироваться' }).click()

  await expect(page).toHaveURL(/\/account(\?welcome=1)?$/)
  await expect(page.locator('.topbar__user-meta b')).toHaveText(username)
  await expect(page.locator('.info-row__value').filter({ hasText: email }).first()).toBeVisible()
})
