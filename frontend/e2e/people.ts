import { expect, type Page } from '@playwright/test';

export interface Person {
  name: string;
  reading?: string;
  birthYear?: number;
  birthplace?: string;
  language?: string;
}

/**
 * Creates a person through the API and selects them in the console.
 *
 * These tests share one backend and one database, so whether anyone already
 * exists depends on what ran before. Driving the form meant branching on that,
 * which was order-dependent and flaked. The form itself is covered by the
 * Japanese test, which runs against an empty store.
 */
export async function addPerson(page: Page, person: Person): Promise<void> {
  const response = await page.request.post('/api/seniors', {
    data: {
      name: person.name,
      name_reading: person.reading ?? '',
      birth_year: person.birthYear ?? null,
      birthplace: person.birthplace ?? '',
      family: [],
      language: person.language ?? 'ja',
    },
  });
  expect(response.ok(), `could not create ${person.name}`).toBe(true);
  const created: { id: string } = await response.json();

  await page.reload();
  const picker = page.locator('.interviewee select');
  await expect(picker).toBeVisible();
  await picker.selectOption(created.id);
}
