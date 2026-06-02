import { expect, test } from '@playwright/test'

test('пользователь может зарегистрироваться через интерфейс', async ({ page }) => {
  const suffix = Date.now()
  const email = `e2e-user-${suffix}@example.com`
  const phone = `+7${String(suffix).slice(-10).padStart(10, '0')}`

  await page.route('**/api/auth/register/', async (route) => {
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        verification_token: 'test-verification-token',
        email,
        email_verification_required: true,
      }),
    })
  })

  await page.goto('/register')

  const fieldInput = (label) => page.locator('.field').filter({ hasText: label }).locator('input').first()

  await fieldInput('Фамилия').fill('Тестов')
  await fieldInput('Имя').fill('Егор')
  await fieldInput('Электронная почта').fill(email)
  await fieldInput('Телефон').fill(phone)
  await fieldInput('Пароль').fill('StrongPass123!')
  await fieldInput('Подтверждение пароля').fill('StrongPass123!')

  await page.getByRole('button', { name: 'Продолжить' }).click()
  await page.getByRole('button', { name: 'Пропустить и зарегистрироваться' }).click()

  await expect(page.getByText(`Мы отправили код подтверждения на ${email}.`)).toBeVisible()
  await expect(fieldInput('Код из письма')).toBeVisible()
})
