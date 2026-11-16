import {expect,test} from '@playwright/test';

// Только авторские fixtures; запросы к внешней платформе перехватываются.
for(const kind of ['article','course','document','webinar','podcast','glossary','calculator']) {
  test(`переход к источнику: ${kind}, описание и отсутствие URL`,async({page,context})=>{
    const paths:Record<string,string>={article:'articles',course:'courses',document:'documents',webinar:'webinars',podcast:'podcasts',glossary:'vocabulary',calculator:'calculators'};
    const url=`https://kurs.alfabank.ru/${paths[kind]}/synthetic-link-test/`;
    const material={id:'link-test',title:'Тестовый учебный материал',description:'Авторский пример краткого описания.',source_type:kind,topics:[],industries:[],access:'paid',price:100,duration:null,url,provenance:'organizer'};
    let missing=false;
    await context.route('https://kurs.alfabank.ru/**',route=>route.fulfill({contentType:'text/html; charset=utf-8',body:'<h1>Тестовая страница источника</h1>'}));
    await page.route('**/api/bootstrap',async route=>{
      const response=await route.fetch();
      await route.fulfill({json:{...await response.json(),catalog_mode:'full',catalog_count:1,profile:{},query:'',signals:{}}});
    });
    await page.route('**/api/recommendations',async route=>{
      const response=await route.fetch();
      const data=await response.json();
      await route.fulfill({json:{...data,items:[{material:{...material,url:missing?null:url},phase:'Разобраться',reasons:['По задаче'],next_action:'Изучите материал на платформе.',score:1,rank_score:1,signals:{}}],clarification:null}});
    });
    await page.route('**/api/catalog**',async route=>{
      const path=new URL(route.request().url()).pathname;
      await route.fulfill({json:path.endsWith('/link-test')?material:{items:[material],total:1}});
    });
    await page.goto('/');
    await page.getByLabel('Ваша бизнес-задача').fill('Как управлять финансами бизнеса?');
    await page.getByRole('button',{name:'Построить маршрут',exact:true}).click();
    const card=page.locator('.route-card');
    const link=card.getByRole('link',{name:/Открыть на Альфа-Курсе/});
    await expect(link).toHaveAttribute('href',url);
    await expect(link).toHaveAttribute('target','_blank');
    await expect(link).toHaveAttribute('rel','noopener noreferrer');
    const popupPromise=page.waitForEvent('popup');
    await link.click();
    const popup=await popupPromise;
    await expect(popup).toHaveURL(url);
    await expect(popup.getByRole('heading')).toHaveText('Тестовая страница источника');
    await popup.close();
    await card.getByRole('button',{name:'Подробнее о материале'}).click();
    const dialog=page.getByRole('dialog');
    await expect(dialog).toContainText('может потребоваться покупка или подписка');
    await expect(dialog.getByRole('link',{name:/Открыть на Альфа-Курсе/})).toHaveAttribute('href',url);
    await page.keyboard.press('Escape');
    await expect(card.getByRole('button',{name:'Подробнее о материале'})).toBeFocused();
    missing=true;
    await page.getByRole('button',{name:'Построить маршрут',exact:true}).click();
    await expect(card).toContainText('Адрес этого материала не подтверждён');
    await expect(card.getByRole('link')).toHaveCount(0);
    const menu=page.getByRole('button',{name:'Альфа-Маршрут, открыть меню',exact:true});
    if(await menu.isVisible())await menu.click();
    await page.getByRole('button',{name:'Каталог знаний',exact:true}).click();
    await expect(page.locator('.catalog-card').getByRole('link',{name:/Открыть на Альфа-Курсе/})).toHaveAttribute('href',url);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  });
}
