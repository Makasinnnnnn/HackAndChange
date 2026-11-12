import {expect,test,Page} from '@playwright/test';

async function nav(page:Page,label:string){
  if((page.viewportSize()?.width||1440)<760)await page.getByRole('button',{name:'Открыть меню',exact:true}).click();
  await page.getByRole('button',{name:label,exact:true}).click();
}

test.beforeEach(async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
});

test('task → explanation → material → feedback → persisted progress',async({page})=>{
  await page.getByRole('button',{name:/Привлечь клиентов/}).click();
  const first=page.locator('.route-card').first();
  await expect(first.locator('.reason')).toContainText('По задаче');
  const title=await first.locator('.card-title').textContent();
  await first.getByRole('button',{name:'Открыть материал',exact:true}).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByRole('dialog')).toContainText('учебный');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).not.toBeVisible();
  await first.getByRole('button',{name:'Изучено',exact:true}).click();
  await expect(first.getByRole('button',{name:'Изучено',exact:true})).toHaveAttribute('aria-pressed','true');
  await nav(page,'Мой прогресс');
  await expect(page.locator('.progress-list')).toContainText(title!);
  await page.reload();
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Построить маршрут',exact:true}).click();
  await expect(page.locator('.route-card').first()).toBeVisible();
  await expect(page.locator('.route-card .card-title')).not.toContainText([title!]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('vague task asks clarification and recovers',async({page})=>{
  await page.getByLabel('Ваша бизнес-задача').fill('Помогите с бизнесом');
  await page.getByRole('button',{name:'Построить маршрут',exact:true}).click();
  await expect(page.getByText('Давайте найдём точку старта')).toBeVisible();
  await expect(page.locator('.route-card')).toHaveCount(0);
  await page.getByRole('button',{name:'Разобраться с деньгами',exact:true}).click();
  await expect(page.locator('.route-card').first()).toBeVisible();
});

test('catalog search and jury comparison calculate real responses',async({page})=>{
  await nav(page,'Каталог знаний');
  await page.getByRole('textbox',{name:'Поиск в каталоге'}).fill('календарь');
  await expect(page.locator('.catalog-card')).toHaveCount(1);
  await expect(page.locator('.catalog-card')).toContainText('Платёжный календарь');
  await nav(page,'Для жюри');
  await page.getByLabel('Демонстрационный предприниматель').selectOption('cafe');
  await page.getByRole('button',{name:'Сравнить алгоритмы',exact:true}).click();
  await expect(page.locator('.comparison-column')).toHaveCount(2);
  await expect(page.locator('.comparison-column').first().locator('.route-card').first()).toBeVisible();
  await expect(page.locator('.comparison-column').last().locator('.route-card').first()).toBeVisible();
  await page.locator('.comparison-column').last().locator('.diagnostic summary').first().click();
  await expect(page.locator('.comparison-column').last().locator('.diagnostic[open]')).toContainText('relevance');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
