import {expect,test,Page} from '@playwright/test';

async function nav(page:Page,label:string){
  const menu=page.getByRole('button',{name:'Альфа-Маршрут, открыть меню',exact:true});
  if(await menu.isVisible())await menu.click();
  await page.getByRole('button',{name:label,exact:true}).click();
}

test.beforeEach(async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
});

test('changed task, context and feedback mark the previous route until rebuilt',async({page})=>{
  await page.getByRole('button',{name:/Разобраться с деньгами/}).click();
  await expect(page.locator('.route-card').first()).toBeVisible();
  const stale=page.getByRole('status').filter({hasText:'Подборка ещё не обновлена'});
  await expect(stale).toHaveCount(0);
  await page.getByLabel('Ваша бизнес-задача').fill('Как привлечь клиентов в кофейню?');
  await expect(stale).toBeVisible();
  await expect(page.locator('.route-context')).toContainText('кассового разрыва');
  await page.getByRole('button',{name:'Перестроить подборку',exact:true}).click();
  await expect(stale).toHaveCount(0);
  await expect(page.locator('.route-context')).toContainText('привлечь клиентов');
  await page.getByRole('button',{name:'Быстро применить',exact:true}).click();
  await expect(stale).toBeVisible();
  await page.getByRole('button',{name:'Перестроить подборку',exact:true}).click();
  await expect(stale).toHaveCount(0);
  await page.locator('.route-card').first().getByRole('button',{name:'Не подходит',exact:true}).click();
  await expect(stale).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('clarification returns focus to the original task without replacing it',async({page})=>{
  const task=page.getByLabel('Ваша бизнес-задача');
  await task.fill('помоги');
  await page.getByRole('button',{name:'Построить маршрут',exact:true}).click();
  await expect(page.getByText('Давайте найдём точку старта')).toBeVisible();
  await page.getByRole('button',{name:'Уточнить мою задачу',exact:true}).click();
  await expect(task).toBeFocused();
  await expect(task).toHaveValue('помоги');
  await expect(page.getByText('Или выберите другую стартовую задачу — она заменит текущий текст.')).toBeVisible();
});

test('an older recommendation response cannot replace a newer result',async({page})=>{
  let releaseFirst:()=>void=()=>{};
  const held=new Promise<void>(resolve=>{releaseFirst=resolve;});
  let requests=0;
  await page.route('**/api/recommendations',async interception=>{
    const number=++requests;
    const response=await interception.fetch();
    const result=await response.json();
    if(number===1)await held;
    await interception.fulfill({json:{...result,query:number===1?'Первый ответ':'Последний ответ'}});
  });
  await page.getByLabel('Ваша бизнес-задача').fill('Как избежать кассового разрыва?');
  const form=page.locator('.task-card form');
  await form.dispatchEvent('submit');
  await expect.poll(()=>requests).toBe(1);
  await form.dispatchEvent('submit');
  await expect(page.locator('.route-context')).toContainText('Последний ответ');
  const firstResponse=page.waitForResponse(async response=>response.url().endsWith('/api/recommendations')&&(await response.json()).query==='Первый ответ');
  releaseFirst();
  await firstResponse;
  await page.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  await expect.poll(()=>requests).toBe(2);
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
  await expect(page.locator('.route-context')).toContainText('Последний ответ');
});

test('task → explanation → material → feedback → persisted progress',async({page})=>{
  await page.getByRole('button',{name:/Привлечь клиентов/}).click();
  const first=page.locator('.route-card').first();
  await expect(first.locator('.reason')).toContainText(/По задаче|В названии|В описании/);
  const title=await first.getByRole('heading',{level:3}).textContent();
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
  await expect(page.locator('.route-card-title')).not.toContainText([title!]);
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
  const personas=await (await page.request.get('/api/demo/profiles')).json();
  await page.getByRole('combobox',{name:'Демонстрационный предприниматель'}).click();
  await page.getByRole('option',{name:personas.find((persona:{id:string})=>persona.id==='cafe').name,exact:true}).click();
  await page.getByRole('button',{name:'Сравнить алгоритмы',exact:true}).click();
  await expect(page.locator('.comparison-column')).toHaveCount(2);
  await expect(page.locator('.comparison-column').first().locator('.route-card').first()).toBeVisible();
  await expect(page.locator('.comparison-column').last().locator('.route-card').first()).toBeVisible();
  await page.locator('.comparison-column').last().locator('.diagnostic summary').first().click();
  await expect(page.locator('.comparison-column').last().locator('.diagnostic[open]')).toContainText('relevance');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});


test('AI suggestion requires explicit acceptance and failure keeps original task',async({page})=>{
  await page.route('**/api/bootstrap',async route=>{
    const response=await route.fetch();const data=await response.json();
    await route.fulfill({json:{...data,llm_enabled:true}});
  });
  await page.route('**/api/intent',route=>route.fulfill({json:{status:'ready',intent:{goal:'Как привлечь клиентов в кофейню',clarification:null}}}));
  await page.reload();
  const task=page.getByLabel('Ваша бизнес-задача');
  await task.fill('Хочу больше клиентов');
  await page.getByRole('button',{name:'Уточнить задачу с AI',exact:true}).click();
  await expect(page.getByText('Предложение AI',{exact:true})).toBeVisible();
  await expect(task).toHaveValue('Хочу больше клиентов');
  await page.getByRole('button',{name:'Применить и построить маршрут',exact:true}).click();
  await expect(task).toHaveValue('Как привлечь клиентов в кофейню');
  await page.route('**/api/intent',route=>route.fulfill({json:{status:'unavailable',intent:null}}));
  await page.getByRole('button',{name:'Уточнить задачу с AI',exact:true}).click();
  await expect(page.getByText(/AI-помощник сейчас недоступен/)).toBeVisible();
  await page.getByRole('button',{name:'Построить маршрут',exact:true}).click();
  await expect(page.locator('.route-card').first()).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});


test('history file imports completed courses and persists after reload',async({page})=>{
  const catalog=await (await page.request.get('/api/catalog?limit=100')).json();
  const ready=await (await page.request.get('/api/ready')).json();
  const course=catalog.items.find((m:{source_type:string})=>m.source_type==='course');
  await nav(page,'Мой прогресс');
  await page.locator('input[type=file]').setInputFiles({name:'history.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify({catalog_version:ready.catalog_version,completed_material_ids:[course.id]}))});
  await expect(page.locator('.progress-list')).toContainText(course.title);
  await page.reload();
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
  await nav(page,'Мой прогресс');
  await expect(page.locator('.progress-list')).toContainText(course.title);
});

test('profile choices work across sidebar breakpoints and with the keyboard',async({page})=>{
  await page.setViewportSize({width:1101,height:900});
  const menu=page.getByRole('button',{name:'Альфа-Маршрут, открыть меню',exact:true});
  await expect(menu).toBeHidden();
  const stage=page.getByRole('combobox',{name:'Этап бизнеса',exact:true});
  await stage.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('listbox')).toBeVisible();
  await expect(page.getByRole('option',{name:'Можно пропустить',exact:true})).toBeFocused();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('option',{name:'Есть идея',exact:true})).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(stage).toContainText('Есть идея');

  await page.setViewportSize({width:1000,height:740});
  await menu.click();
  await expect(page.getByRole('button',{name:'Закрыть меню'})).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toBeFocused();
  await page.getByRole('button',{name:/Ваш контекст/}).click();
  await expect(stage).toContainText('Есть идея');
  await stage.click();
  await page.getByRole('option',{name:'Можно пропустить',exact:true}).click();
  await expect(stage).toContainText('Можно пропустить');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth===innerWidth)).toBeTruthy();
});

test('dragging a JSON file imports progress through the same form',async({page})=>{
  const catalog=await (await page.request.get('/api/catalog?limit=100')).json();
  const ready=await (await page.request.get('/api/ready')).json();
  const course=catalog.items.find((item:{source_type:string})=>item.source_type==='course');
  await nav(page,'Мой прогресс');

  const transfer=await page.evaluateHandle(json=>{
    const files=new DataTransfer();
    files.items.add(new File([json],'history.json',{type:'application/json'}));
    return files;
  },JSON.stringify({catalog_version:ready.catalog_version,completed_material_ids:[course.id]}));

  const dropZone=page.locator('.file-picker');
  await dropZone.dispatchEvent('dragover',{dataTransfer:transfer});
  await expect(dropZone).toContainText('Отпустите файл');
  await dropZone.dispatchEvent('drop',{dataTransfer:transfer});
  await expect(page.locator('.progress-list')).toContainText(course.title);
});

test('catalog pages and material details keep pointer focus visually quiet',async({page})=>{
  await nav(page,'Каталог знаний');
  await expect(page.getByRole('button',{name:'Страница 1',exact:true})).toHaveAttribute('aria-current','page');
  const firstTitle=await page.locator('.catalog-open').first().textContent();
  await page.getByRole('button',{name:'Страница 2',exact:true}).click();
  await expect(page.getByRole('button',{name:'Страница 2',exact:true})).toHaveAttribute('aria-current','page');
  const card=page.locator('.catalog-card').first();
  await expect(card.locator('.catalog-open')).not.toHaveText(firstTitle!);
  await card.locator('.catalog-open').click();
  const dialog=page.getByRole('dialog');
  await expect(dialog.getByRole('heading',{level:2})).toBeFocused();
  await expect(dialog).toHaveCSS('border-top-width','0px');
  await dialog.getByRole('button',{name:'Полезно',exact:true}).click();
  await expect(dialog.getByRole('button',{name:'Полезно',exact:true})).toHaveAttribute('aria-pressed','true');
  await dialog.getByRole('button',{name:'Закрыть материал'}).click();
  await expect(dialog).toBeHidden();
  await expect(card).toHaveCSS('outline-style','none');
  await expect(card.locator('.catalog-open')).toBeFocused();
});


test('late AI response cannot overwrite a changed task',async({page})=>{
  await page.route('**/api/bootstrap',async route=>{
    const response=await route.fetch();await route.fulfill({json:{...await response.json(),llm_enabled:true}});
  });
  let pending:import('@playwright/test').Route|undefined;
  await page.route('**/api/intent',route=>{pending=route;});
  await page.reload();
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
  const task=page.getByLabel('Ваша бизнес-задача');
  await task.fill('Нужна реклама кофейни');
  await page.getByRole('button',{name:'Уточнить задачу с AI',exact:true}).click();
  await expect.poll(()=>Boolean(pending)).toBeTruthy();
  await task.fill('Нужен договор с подрядчиком');
  await pending!.fulfill({json:{status:'ready',intent:{goal:'Старая формулировка рекламы',clarification:null}}});
  await expect(page.getByRole('button',{name:'Уточнить задачу с AI',exact:true})).toBeEnabled();
  await expect(page.getByText('Старая формулировка рекламы',{exact:true})).toHaveCount(0);
  await expect(task).toHaveValue('Нужен договор с подрядчиком');
});

test('hanging optional evaluation does not disable the primary route',async({page})=>{
  await page.route('**/api/evaluation/results',()=>{});
  await page.reload();
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:/Привлечь клиентов/}).click();
  await expect(page.locator('.route-card').first()).toBeVisible();
});


test('AI clarification answer builds a route instead of only replacing input',async({page})=>{
  await page.route('**/api/bootstrap',async route=>{
    const response=await route.fetch();await route.fulfill({json:{...await response.json(),llm_enabled:true}});
  });
  await page.route('**/api/intent',route=>route.fulfill({json:{status:'ready',intent:{goal:'Как привлечь клиентов в кофейню',clarification:'Кофейня уже работает?'}}}));
  await page.reload();
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
  await page.getByLabel('Ваша бизнес-задача').fill('Мало клиентов');
  await page.getByRole('button',{name:'Уточнить задачу с AI',exact:true}).click();
  await page.getByLabel('Ответ на уточнение AI').fill('Кофейня работает три месяца');
  await page.getByRole('button',{name:'Применить и построить маршрут',exact:true}).click();
  await expect(page.locator('.route-card').first()).toBeVisible();
  await expect(page.locator('.route-context')).toContainText('Кофейня работает три месяца');
});

test('unchanged AI answer is reported honestly',async({page})=>{
  await page.route('**/api/bootstrap',async route=>{
    const response=await route.fetch();await route.fulfill({json:{...await response.json(),llm_enabled:true}});
  });
  await page.route('**/api/intent',route=>route.fulfill({json:{status:'unchanged',intent:null}}));
  await page.reload();
  await expect(page.getByRole('button',{name:'Построить маршрут',exact:true})).toBeEnabled();
  await page.getByLabel('Ваша бизнес-задача').fill('Франшиза');
  await page.getByRole('button',{name:'Уточнить задачу с AI',exact:true}).click();
  await expect(page.locator('.error-banner')).toContainText('не нашёл более точной формулировки');
  await expect(page.getByText('Предложение AI',{exact:true})).toHaveCount(0);
});


test('general fallback is not presented as a specialized route',async({page})=>{
  await page.route('**/api/recommendations',async route=>{
    const response=await route.fetch();const result=await response.json();
    await route.fulfill({json:{...result,match_scope:'general',notice:'В этой подборке нет подтверждённого отраслевого совпадения.'}});
  });
  await page.getByRole('button',{name:/Привлечь клиентов/}).click();
  await expect(page.getByRole('heading',{name:/Общие материалы по задаче/})).toBeVisible();
  await expect(page.locator('.notice')).toContainText('нет подтверждённого отраслевого совпадения');
});
