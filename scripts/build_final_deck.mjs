import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const {Presentation,PresentationFile}=await import(process.env.ARTIFACT_TOOL_ENTRY||'@oai/artifact-tool');
const root=process.cwd();
const skill=process.env.PRESENTATIONS_SKILL;
const stage=path.join(root,'.private/deck-1.1');
const output=path.join(root,'output/presentation');
await fs.mkdir(stage,{recursive:true});await fs.mkdir(output,{recursive:true});
const deck=Presentation.create({slideSize:{width:1280,height:720}});
const color={ink:'#20232b',red:'#e93436',muted:'#6d7584',light:'#f6f7f9'};
function text(slide,content,x,y,w,h,size=26,fill=color.ink,bold=false){
 const item=slide.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 item.text=content;item.text.style={fontSize:size,typeface:'Arial',color:fill,bold};return item;
}
function slide(title,notes){const s=deck.slides.add();s.background.fill='#ffffff';text(s,title,65,43,1150,110,48);s.speakerNotes.text=notes;text(s,String(deck.slides.items.length).padStart(2,'0'),1180,672,40,22,16,color.muted);return s;}
function paragraph(s,title,body,y){text(s,title,70,y,1060,45,29,color.ink,true);text(s,body,70,y+53,1080,95,25,color.muted);}
let s=deck.slides.add();s.background.fill='#ffffff';
text(s,'Альфа-Маршрут',65,95,1140,100,76,color.red,true);
text(s,'Персональные рекомендации\nдля задач предпринимателя',70,220,1080,110,42);
text(s,'Hack&Change 2026. Web/AI от Альфа-Банка. Трек 1',70,365,1100,45,25,color.muted);
const repo=text(s,'github.com/Makasinnnnnn/HackAndChange',70,435,1100,42,26,color.red);repo.text.get('github.com/Makasinnnnnn/HackAndChange').link={uri:'https://github.com/Makasinnnnnn/HackAndChange',isExternal:true};
text(s,'Проверка: docker compose up --build\nОткрыть localhost:3080 и выбрать сценарий кофейни',70,500,1120,95,26);
text(s,'Версия 1.1, 13 ноября 2026. Исходники опубликованы.\nКачество рекомендаций и рост конверсии ещё не доказаны.',70,635,1120,50,17,color.muted);
s.speakerNotes.text='Название команды и участников владелец ещё не указал; не выдумывать. Репозиторий содержит код и инструкции. Комплект технически подготовлен; отправляет участник команды. PDF кейса, с. 7 и 9.';
s=slide('Задача предпринимателя определяет формат обучения','Источник: оригинальный PDF кейса, с. 4–5. Бизнес-эффект является гипотезой, а не измеренным результатом.');
paragraph(s,'Новичок открывает дело','Нужны вводный материал и понятный первый шаг. Длинная обязательная анкета мешает начать.',185);
paragraph(s,'Владелец решает срочную проблему','Нужен шаблон или короткая инструкция. Большой курс может быть неуместен первым.',355);
text(s,'Бизнес-цели: конверсия в покупку обучения и число активных дней.\nПроверяем влияние экспериментом после внедрения.',70,565,1100,88,26,color.red);
s=slide('Задача и контекст в одном экране','Скриншот локального приложения. DEMO: 36 авторских синтетических материалов, не действующий каталог Альфа-Курса.');
s.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,'docs/screenshots/desktop-demo.png'))),contentType:'image/png',alt:'Реальный экран запущенного прототипа',fit:'contain',position:{left:65,top:160,width:1150,height:500}});
text(s,'Анкета необязательна. Основной сценарий работает без API-ключей.',70,673,1100,28,17,color.muted);
s=slide('Рекомендация содержит объяснение и действие','Скриншот реальной выдачи на синтетическом каталоге. Порядок рассчитывается алгоритмом. Это не доказательство бизнес-эффекта.');
s.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,'docs/screenshots/route-demo.png'))),contentType:'image/png',alt:'Порядок материалов, объяснения и следующий шаг',fit:'contain',position:{left:65,top:160,width:1150,height:500}});
s=slide('Данные проходят отдельную проверку доступа','Фактический аудит .backup от 12.11.2026. 62 таблицы и 102128 строк. Импорт 1476 строк метаданных, после дедупликации 1473. Источник: docs/data-audit.md.');
text(s,'62',70,180,420,110,82,color.red,true);text(s,'таблицы в исходной базе',75,300,470,45,25,color.muted);
text(s,'102 128',650,180,560,110,82,color.ink,true);text(s,'строк проверены восстановлением',655,300,550,45,25,color.muted);
text(s,'1 473 материала после фильтров и удаления дублей',70,405,1120,55,35,color.ink,true);
text(s,'NULL Courses.Cost означает нулевую цену, подписочный доступ сохраняется.\nЗакрытые уроки, IP и пользовательские записи не попадают в каталог API.\nУ 507 материалов путь к источнику пока не подтверждён.',70,505,1120,135,24,color.muted);
s=slide('Baseline и персональный маршрут рассчитываются отдельно','Реальный экран сравнения на одинаковых запросе и синтетическом каталоге. Метрики релевантности ещё не рассчитаны: человеческих меток нет.');
s.images.add({blob:new Uint8Array(await fs.readFile(path.join(root,'docs/screenshots/comparison-demo.png'))),contentType:'image/png',alt:'Сравнение двух алгоритмов с реальными кандидатами',fit:'contain',position:{left:65,top:190,width:1150,height:460}});
text(s,'32 тестовых профиля подготовлены. Экспертная оценка ещё не проведена.',70,673,1100,26,17,color.red);
s=slide('Локальный поиск и независимое ранжирование','Код: backend/app/engine.py, semantic.py. E5: https://huggingface.co/intfloat/multilingual-e5-small и ONNX-конверсия Xenova. Модель опциональна, не доказано превосходство на независимой экспертной разметке.');
paragraph(s,'Поиск кандидатов','TF-IDF по словам и символьным сочетаниям. Опциональная локальная E5 помогает с перефразированием.',180);
paragraph(s,'Персональный порядок','Задача, известные метаданные и обратная связь. Импорт завершённых курсов учитывает историю; освоенное исключается.',355);
text(s,'Qwen 1.5B уточняет задачу локально, только с подтверждением.\nЦена не добавляет баллы; без модели работает обычный маршрут.',70,565,1110,90,25,color.red);
s=slide('Приложение запускается через Docker','Архитектура: docs/architecture.md. Проверены Windows Docker из ZIP 1.0, unit/API и desktop/mobile E2E. Текущие результаты в docs/verification.md.');
paragraph(s,'Next.js и FastAPI','Браузер обращается к одному origin. API хранит профиль и отметки в отдельном PostgreSQL приложения.',175);
paragraph(s,'DEMO и FULL','DEMO содержит авторские примеры. FULL читает локальные метаданные через read-only mount, без дампа в образе.',340);
text(s,'Проверен чистый Windows Docker-старт из ZIP релиза 1.0.\nQwen: 0,9–1,9 с на трёх запросах; это не метрика качества.',70,555,1110,95,25,color.red);
s=slide('Проверка эффекта после внедрения','План эксперимента: docs/product-metrics.md. Конверсия, эффект, размер выборки и сроки пока не измерены. Нужны базовая конверсия, MDE и интеграция событий покупки.');
paragraph(s,'Контрольная и экспериментальная группы','Рандомизация по пользователю. A: подбор по теме. B: персональные рекомендации и маршрут.',170);
paragraph(s,'Основная метрика','Покупка образовательного продукта за заранее выбранное окно после включения в эксперимент.',330);
text(s,'Дополнительно: активные дни, начало обучения и следующий шаг.\nОграничения: ошибки, задержки и негативная обратная связь.\nРазмер выборки рассчитываем до запуска по базовой конверсии и MDE.',70,505,1120,140,25,color.muted);
const candidate=path.join(stage,'candidate.pptx');
await (await PresentationFile.exportPptx(deck)).save(candidate);
for(const [i,slide]of deck.slides.items.entries()){
 const blob=await deck.export({slide,format:'png',scale:1});
 await fs.writeFile(path.join(stage,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
}
// PDF is assembled from the verified slide renders by build_deck_pdf.py.
// The bundled direct PDF exporter currently fails to resolve #standard-fonts/Helvetica.
const {finalizePresentation}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')).href);
const result=await finalizePresentation({workspaceDir:root,candidatePath:candidate,
 finalPath:path.join(output,'alfa-route-1.1.pptx'),
 pythonExecutable:process.env.ARTIFACT_PYTHON,
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-heading-fit'],
 fontPolicy:{basis:'design',families:['Arial']},verifyArtifactToolImport:true,
 explicitTotalSlideCount:9,requiredNativeTableOwnerSlides:[],requiredNativeChartOwnerSlides:[],
 receiptPath:path.join(stage,'validation-1.1.json')});
console.log(JSON.stringify({slides:deck.slides.items.length,output,result},null,2));
