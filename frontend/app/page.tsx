'use client';

import {useCallback, useEffect, useRef, useState} from 'react';
import {ArrowUpRight, ArrowRight, BookOpen, Check, CheckCheck, ChevronRight, CircleHelp, Compass, FileText, FlaskConical, Layers3, LoaderCircle, Menu, MessageCircle, Plus, Search, SlidersHorizontal, Sparkles, ThumbsDown, ThumbsUp, TrendingUp, X} from 'lucide-react';

type Tab = 'route' | 'progress' | 'catalog' | 'jury';
type Profile = {stage?:string|null; industry?:string|null; experience?:string|null; format?:string|null; urgency?:string|null};
type Material = {id:string; title:string; description:string; source_type:string; topics:string[]; industries:string[]; access:string; price:number|null; duration:string|null; url:string|null; provenance:string; demo_content?:string|null};
type Item = {material:Material; reasons:string[]; next_action:string; phase:string; score:number; rank_score:number; signals:Record<string,number>};
type Route = {route_id:string; query:string; profile:Profile; items:Item[]; clarification:string|null; notice:string|null; elapsed_ms:number; algorithm:string; excluded_count:number; candidate_count:number; active_profile_fields:string[]; catalog_version:string};
type Evaluation = {status:string;note:string;metrics?:Record<string,Record<string,Record<string,number>>>|null;judged_profiles?:number};
type Persona = {id:string; name:string; situation:string; query:string; profile:Profile};
const formats:Record<string,string> = {article:'Статья',course:'Курс',document:'Шаблон',webinar:'Вебинар',podcast:'Подкаст',glossary:'Термин',calculator:'Калькулятор'};
const access:Record<string,string> = {free:'Бесплатно',paid:'Платный материал',subscription:'По подписке',unknown:'Условия на сайте'};
const signalsText:Record<string,string> = {helpful:'Полезно',not_relevant:'Не подходит',known:'Уже знаю',completed:'Изучено'};
const examples = [
  {icon:'01', title:'Привлечь клиентов',query:'В моей кофейне мало клиентов. Как привлечь новых посетителей?',topic:'Маркетинг и продажи'},
  {icon:'02', title:'Разобраться с деньгами',query:'Как избежать кассового разрыва и спланировать платежи?',topic:'Финансы бизнеса'},
  {icon:'03', title:'Запустить своё дело',query:'Хочу открыть свой бизнес с нуля. С чего начать?',topic:'Первые шаги'},
];

async function api<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch('/api'+path,{signal:AbortSignal.timeout(20000),method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin'});
  if (!response.ok) throw new Error(response.status===422?'Проверьте длину запроса и параметры профиля.':response.status===503?'Каталог пока недоступен. Попробуйте позже.':'Не удалось выполнить действие. Проверьте соединение и попробуйте ещё раз.');
  return response.json();
}

export default function Home() {
  const [tab,setTab] = useState<Tab>('route');
  const [query,setQuery] = useState('');
  const [profile,setProfile] = useState<Profile>({});
  const [route,setRoute] = useState<Route|null>(null);
  const [comparison,setComparison] = useState<{baseline:Route;personal:Route;note:string}|null>(null);
  const [personas,setPersonas] = useState<Persona[]>([]);
  const [history,setHistory] = useState<Record<string,string>>({});
  const [catalog,setCatalog] = useState<{items:Material[];total:number}>({items:[],total:0});
  const [catalogQuery,setCatalogQuery] = useState('');
  const [offset,setOffset] = useState(0);
  const [progress,setProgress] = useState<{material:Material;signal:string}[]>([]);
  const [selected,setSelected] = useState<Material|null>(null);
  const [profileOpen,setProfileOpen] = useState(false);
  const [mobileMenu,setMobileMenu] = useState(false);
  const [busy,setBusy] = useState(false);
  const [ready,setReady] = useState(false);
  const [error,setError] = useState('');
  const [toast,setToast] = useState('');
  const [info,setInfo] = useState<{catalog_mode:string;catalog_count:number;semantic_model:string|null;industries:string[]}>({catalog_mode:'demo',catalog_count:0,semantic_model:null,industries:[]});
  const [evaluation,setEvaluation] = useState<Evaluation>({status:'',note:''});
  const textarea = useRef<HTMLTextAreaElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const learnCount = Object.values(history).filter(v=>v==='completed'||v==='known').length;

  useEffect(()=>{let active=true; Promise.all([
    api<{profile:Profile;query:string;signals:Record<string,string>;catalog_mode:string;catalog_count:number;semantic_model:string|null;industries:string[]}>('/bootstrap'),
    api<Persona[]>('/demo/profiles'), api<Evaluation>('/evaluation/results')
  ]).then(([data,people,e])=>{if(!active)return;setProfile(data.profile);setQuery(data.query);setHistory(data.signals);setInfo(data);setPersonas(people);setEvaluation(e);setReady(true);}).catch(()=>{if(active)setError('Не удалось подключиться к приложению. Обновите страницу после запуска сервера.');}); return()=>{active=false;};},[]);

  useEffect(()=>{if(selected){dialog.current?.showModal();}else{dialog.current?.close();}},[selected]);
  useEffect(()=>{if(!toast)return;const id=setTimeout(()=>setToast(''),4000);return()=>clearTimeout(id);},[toast]);

  const loadCatalog = useCallback(async(search:string,page:number)=>{
    try{setCatalog(await api(`/catalog?q=${encodeURIComponent(search)}&offset=${page}&limit=12`));}catch(e){setError((e as Error).message);}
  },[]);
  useEffect(()=>{if(tab==='catalog'){const timer=setTimeout(()=>loadCatalog(catalogQuery,offset),250);return()=>clearTimeout(timer);}},[tab,catalogQuery,offset,loadCatalog]);
  useEffect(()=>{if(tab==='progress')api<{items:{material:Material;signal:string}[]}>('/progress').then(d=>setProgress(d.items)).catch(e=>setError(e.message));},[tab,history]);

  function navigate(next:Tab){setTab(next);setMobileMenu(false);setError('');}
  function patchProfile(key:keyof Profile,value:string){if(busy)return;setProfile(p=>({...p,[key]:value||null}));setComparison(null);}
  async function recommend(override?:string){
    const value=override??query;if(override!==undefined)setQuery(override);setBusy(true);setError('');
    try{setRoute(await api('/recommendations',{query:value,profile}));setTab('route');}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function compare(){setBusy(true);setError('');try{setComparison(await api('/demo/compare',{query,profile}));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function feedback(materialId:string,signal:string){setBusy(true);setError('');try{
    const result=await api<{signals:Record<string,string>}>('/feedback',{material_id:materialId,signal});setHistory(result.signals);
    setToast(signal==='reset'?'Отметка удалена':'Сохранено. Следующая подборка учтёт вашу отметку.');setComparison(null);
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function openMaterial(material:Material){try{setSelected(await api<Material>('/catalog/'+encodeURIComponent(material.id)));}catch(e){setError((e as Error).message);}}
  function choosePersona(id:string){const p=personas.find(p=>p.id===id);if(p){setQuery(p.query);setProfile(p.profile);setComparison(null);}}

  function materialTags(m:Material){return <div className="material-tags"><span className={'format '+m.source_type}>{m.source_type==='document'?<FileText size={13}/>:<BookOpen size={13}/>} {formats[m.source_type]}</span><span className={m.access==='free'?'free':''}>{access[m.access]}</span>{m.duration&&<span>{m.duration}</span>}</div>;}
  function feedbackButtons(m:Material){return <div className="feedback" aria-label={'Обратная связь: '+m.title}>
    {([{signal:'helpful',label:'Полезно',Icon:ThumbsUp},{signal:'not_relevant',label:'Не подходит',Icon:ThumbsDown},{signal:'known',label:'Уже знаю',Icon:Check},{signal:'completed',label:'Изучено',Icon:CheckCheck}]).map(({signal,label,Icon})=><button key={signal} className={history[m.id]===signal?'active':''} disabled={busy} onClick={()=>feedback(m.id,history[m.id]===signal?'reset':signal)} aria-pressed={history[m.id]===signal}><Icon size={14}/><span>{label}</span></button>)}
  </div>;}
  function routeCard(item:Item,index:number,diagnostic=false){const m=item.material;return <article className="route-card" key={m.id}>
    <div className="step-number">{String(index+1).padStart(2,'0')}</div><div className="route-card-content">
      <div className="card-overline">{item.phase}{history[m.id]&&<span className="saved"><Check size={12}/>{signalsText[history[m.id]]}</span>}</div>
      {materialTags(m)}<button className="card-title" onClick={()=>openMaterial(m)}>{m.title}<ArrowUpRight size={20}/></button>
      <p className="description">{m.description}</p>
      <div className="reason"><Sparkles size={15}/><span>{item.reasons.slice(0,2).join(' · ')}</span></div>
      <div className="next-action"><span>Следующий шаг</span><p>{item.next_action}</p></div>
      {diagnostic&&<details className="diagnostic"><summary>Расчёт ранжирования · {item.rank_score.toFixed(3)}</summary><dl>{Object.entries(item.signals).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v.toFixed(3)}</dd></div>)}</dl><ul>{item.reasons.map(r=><li key={r}>{r}</li>)}</ul></details>}
      <div className="card-footer"><button className="text-button" onClick={()=>openMaterial(m)}>Открыть материал <ArrowRight size={15}/></button>{!diagnostic&&feedbackButtons(m)}</div>
    </div></article>;}

  const profileForm=<div className="profile-fields">
    <label>Этап бизнеса<select disabled={busy} value={profile.stage??''} onChange={e=>patchProfile('stage',e.target.value)}><option value="">Можно пропустить</option><option value="idea">Есть идея</option><option value="start">Недавно запустился</option><option value="growth">Развиваю бизнес</option></select></label>
    <label>Сфера<select disabled={busy} value={profile.industry??''} onChange={e=>patchProfile('industry',e.target.value)}><option value="">Не указана</option>{(info.industries.length?info.industries:['HoReCa','Торговля','Услуги','IT']).map(v=><option key={v}>{v}</option>)}</select></label>
    <label>Опыт<select disabled={busy} value={profile.experience??''} onChange={e=>patchProfile('experience',e.target.value)}><option value="">Можно пропустить</option><option value="beginner">Начинающий</option><option value="experienced">Есть опыт</option></select></label>
    <label>Удобный формат<select disabled={busy} value={profile.format??''} onChange={e=>patchProfile('format',e.target.value)}><option value="">Любой формат</option>{Object.entries(formats).map(([k,v])=><option value={k} key={k}>{v}</option>)}</select></label>
    <button className="text-button muted" onClick={()=>{setProfile({});setComparison(null);}}>Пропустить и сбросить профиль</button>
    <p className="small-note">Анкета необязательна. Учитываем только известные сведения о вас и материале.</p>
  </div>;

  return <div className="app-shell">
    <aside className={'sidebar '+(mobileMenu?'open':'')}>
      <a className="brand" href="/" aria-label="Альфа-Маршрут, главная"><span className="brand-mark"><Compass size={23}/></span><span>Альфа<span className="brand-sub">Маршрут</span></span></a>
      <div className="sidebar-label">ВАШЕ РАЗВИТИЕ</div>
      <nav aria-label="Основная навигация">{([{id:'route',label:'Мой маршрут',Icon:Compass},{id:'progress',label:'Мой прогресс',Icon:TrendingUp},{id:'catalog',label:'Каталог знаний',Icon:Layers3},{id:'jury',label:'Для жюри',Icon:FlaskConical}] as const).map(({id,label,Icon})=><button key={id} className={tab===id?'nav-item selected':'nav-item'} onClick={()=>navigate(id)}><Icon size={19}/>{label}{tab===id&&<span className="nav-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="mini-art"><span/><span/><span/><ArrowUpRight size={25}/></div><strong>Маленький шаг.<br/>Большое дело.</strong><p>Учитесь тому, что поможет<br/>двигаться дальше.</p><div className="prototype">Hack&Change 2026<br/>Конкурсный прототип</div></div>
    </aside>
    {mobileMenu&&<button aria-label="Закрыть меню" className="menu-backdrop" onClick={()=>setMobileMenu(false)}/>}
    <div className="main-shell">
      <header className="topbar"><div className="breadcrumb"><button className="mobile-menu" aria-label="Открыть меню" onClick={()=>setMobileMenu(true)}><Menu size={21}/></button><span>Моё обучение</span><ChevronRight size={14}/><strong>{{route:'Персональный маршрут',progress:'Прогресс',catalog:'Каталог',jury:'Демонстрация'}[tab]}</strong></div><span className="mode-badge"><span/>{info.catalog_mode==='demo'?'DEMO · учебный каталог':'Локальный каталог кейса'}</span></header>
      <main>
        <div className="page-heading"><div><div className="eyebrow">ЗНАНИЯ В НУЖНЫЙ МОМЕНТ</div><h1>{{route:<>Следующий шаг<br/>для вашего бизнеса<span>.</span></>,progress:<>Ваши знания<br/>становятся действиями<span>.</span></>,catalog:<>Найдите полезное<br/>для своего дела<span>.</span></>,jury:<>Рекомендации,<br/>которые можно проверить<span>.</span></>}[tab]}</h1></div><div className="heading-note"><span className="note-line"/>Практика вместо случайных подборок.<br/>В вашем темпе, под вашу задачу.</div></div>
        {error&&<div className="error-banner" role="alert">{error}<button aria-label="Закрыть сообщение" onClick={()=>setError('')}><X size={16}/></button></div>}
        {(tab==='route'||tab==='jury')&&<div className="workspace">
          <section className="task-card" aria-labelledby="task-title"><div className="section-top"><span className="section-icon"><MessageCircle size={19}/></span><div><h2 id="task-title">Что сейчас важно для вашего дела?</h2><p>Опишите задачу своими словами — начнём с неё.</p></div><span className="optional-label">ШАГ 01</span></div>
            <form onSubmit={e=>{e.preventDefault();if(tab==='jury')compare();else recommend();}}>
              <label className="sr-only" htmlFor="business-task">Ваша бизнес-задача</label><textarea disabled={busy} ref={textarea} id="business-task" placeholder="Например: открыл кофейню, клиентов пока мало. Хочу понять, с чего начать продвижение…" maxLength={1500} value={query} onChange={e=>{setQuery(e.target.value);setComparison(null);}}/>
              <div className="task-controls"><div className="pace-options" aria-label="Темп обучения"><button type="button" disabled={busy} aria-pressed={profile.urgency==='quick'} className={profile.urgency==='quick'?'active':''} onClick={()=>patchProfile('urgency',profile.urgency==='quick'?'':'quick')}>Быстро применить</button><button type="button" disabled={busy} aria-pressed={profile.urgency==='deep'} className={profile.urgency==='deep'?'active':''} onClick={()=>patchProfile('urgency',profile.urgency==='deep'?'':'deep')}>Разобраться глубже</button></div><span className="char-count">{query.length}/1500</span></div>
              <div className="task-submit"><span><Check size={14}/> Можно начать без анкеты</span><button className="primary" type="submit" disabled={busy||!ready}>{busy?<LoaderCircle className="spinning" size={17}/>:<ArrowRight size={17}/>} {tab==='jury'?'Сравнить алгоритмы':'Построить маршрут'}</button></div>
            </form>
          </section>
          <aside className={'context-card '+(profileOpen?'expanded':'')}><button className="context-toggle" onClick={()=>setProfileOpen(!profileOpen)} aria-expanded={profileOpen}><span className="section-icon pale"><SlidersHorizontal size={18}/></span><span><strong>Ваш контекст</strong><small>Точнее, если расскажете о себе</small></span><Plus size={17}/></button>{profileForm}</aside>
        </div>}

        {tab==='route'&&!route&&<section className="starting-points"><div className="section-label"><h2>Можно начать с этого</h2><span>Одна задача — понятный следующий шаг</span></div><div className="example-grid">{examples.map(e=><button className="example-card" key={e.title} disabled={busy||!ready} onClick={()=>recommend(e.query)}><div><span className="example-number">{e.icon}</span><ArrowUpRight size={19}/></div><h3>{e.title}</h3><p>{e.topic}</p></button>)}</div><div className="honesty-note"><CircleHelp size={17}/><p>{info.catalog_mode==='demo'?'Сейчас вы в учебном демо: материалы созданы для проверки прототипа и не являются курсами Альфа-Курса.':'Рекомендации используют метаданные локальной выгрузки. Условия доступа уточняйте на странице источника.'} {info.catalog_count>0&&`В каталоге ${info.catalog_count} материалов.`}</p></div></section>}
        {tab==='route'&&route&&<section className="route-results" aria-live="polite"><div className="section-label"><div><div className="eyebrow">ОТ ЗНАНИЯ К ДЕЙСТВИЮ</div><h2>Ваш маршрут{route.items.length>0&&<span className="count-badge">{route.items.length} шагов</span>}</h2></div><button className="text-button muted" onClick={()=>navigate('jury')}>Почему именно эти материалы? <ArrowUpRight size={15}/></button></div>
          <p className="route-context">Ваша задача: {route.query||'пока не задана'}</p>{route.active_profile_fields.length>0&&<p className="small-note">Учитываем только заполненный контекст. Материалы без известных признаков уровня и стадии не получают таких объяснений.</p>}{route.clarification&&<div className="empty-state"><CircleHelp size={28}/><h3>Давайте найдём точку старта</h3><p>{route.clarification}</p><div className="empty-actions">{examples.map(e=><button className="secondary" key={e.title} disabled={busy} onClick={()=>recommend(e.query)}>{e.title}</button>)}</div></div>}
          {route.notice&&<div className="notice">{route.notice}</div>}
          <div className="route-layout"><div>{route.items.map((item,i)=>routeCard(item,i))}</div>{route.items.length>0&&<aside className="route-summary"><span className="section-icon pale"><Compass size={22}/></span><h3>Не нужно изучать всё сразу</h3><p>Начните с первого полезного шага. После изучения отметьте материал — следующая подборка учтёт ваш прогресс.</p><div className="summary-rule"/><div><strong>{learnCount}</strong><span>материалов освоено<br/>в этой демо-сессии</span></div><button className="secondary" disabled={busy} onClick={()=>recommend()}>Обновить с учётом отметок <ArrowRight size={15}/></button><small>История сохраняется в этом браузере и базе приложения. Реальные пользователи платформы не подключены.</small></aside>}</div>
        </section>}

        {tab==='jury'&&<section className="jury-section"><div className="jury-toolbar"><div><h2>Один запрос. Два подхода.</h2><p>Выберите синтетический профиль или используйте свою задачу выше.</p></div><label className="sr-only" htmlFor="persona">Демонстрационный предприниматель</label><select disabled={busy} id="persona" defaultValue="" onChange={e=>choosePersona(e.target.value)}><option value="" disabled>Выбрать предпринимателя</option>{personas.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
          <div className="evaluation-note"><FlaskConical size={21}/><div><strong>{evaluation.status==='calculated'?'Результаты экспертной оценки':'Метрики качества: ожидается экспертная оценка'}</strong><p>{evaluation.note||'Результаты ещё не рассчитаны.'}</p></div></div>
          {evaluation.metrics&&<div className="metrics-scroll"><table className="metrics-table"><caption>Offline-метрики на размеченных профилях: {evaluation.judged_profiles}</caption><thead><tr><th>Выборка</th><th>Алгоритм</th><th>P@5</th><th>nDCG@5</th><th>MRR@5</th></tr></thead><tbody>{Object.entries(evaluation.metrics).flatMap(([split,algorithms])=>Object.entries(algorithms).map(([algorithm,m])=><tr key={split+algorithm}><td>{split}</td><td>{algorithm}</td><td>{m.precision_at_5.toFixed(3)}</td><td>{m.ndcg_at_5.toFixed(3)}</td><td>{m.mrr_at_5.toFixed(3)}</td></tr>))}</tbody></table></div>}{comparison&&<><p className="small-note">{comparison.note}</p><div className="comparison-grid">{([{title:'Подбор по теме',subtitle:'Baseline · без профиля и истории',route:comparison.baseline},{title:'Персональный маршрут',subtitle:'Задача + известный контекст + обратная связь',route:comparison.personal}]).map((col,i)=><section key={col.title} className={'comparison-column '+(i?'personal':'')}><div className="compare-heading"><span className="compare-letter">{i?'B':'A'}</span><div><h3>{col.title}</h3><p>{col.subtitle}</p></div></div><div className="compare-stats"><span>{col.route.elapsed_ms.toFixed(1)} мс</span><span>{col.route.candidate_count} кандидатов</span><span>{col.route.excluded_count} исключено</span></div>{col.route.clarification&&<div className="notice">{col.route.clarification}</div>}{col.route.items.map((item,index)=>routeCard(item,index,true))}</section>)}</div><p className="small-note">Время измерено для этого запроса на сервере, без сети. Алгоритм: {comparison.personal.algorithm.includes('e5')?'локальная E5 + TF-IDF и персональное ранжирование':'лексический TF-IDF и персональное ранжирование'}. Версия каталога: {comparison.personal.catalog_version}.</p></>}
        </section>}

        {tab==='catalog'&&<section><div className="catalog-toolbar"><label className="search-field"><Search size={18}/><input aria-label="Поиск в каталоге" placeholder="Название или тема материала" maxLength={150} value={catalogQuery} onChange={e=>{setCatalogQuery(e.target.value);setOffset(0);}}/></label><span className="small-note">Найдено: {catalog.total}</span></div><div className="catalog-grid">{catalog.items.map(m=><article className="catalog-card" key={m.id}>{materialTags(m)}<h3>{m.title}</h3><p>{m.description}</p><button className="text-button" onClick={()=>openMaterial(m)}>Подробнее <ArrowUpRight size={16}/></button></article>)}</div>{!catalog.items.length&&<div className="empty-state"><Search size={27}/><h3>Здесь пока ничего нет</h3><p>Попробуйте более короткий или другой запрос.</p></div>}<div className="pagination"><button className="secondary" disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-12))}>Назад</button><span>{catalog.total?offset+1:0}–{Math.min(offset+12,catalog.total)} из {catalog.total}</span><button className="secondary" disabled={offset+12>=catalog.total} onClick={()=>setOffset(offset+12)}>Далее</button></div></section>}

        {tab==='progress'&&<section><div className="progress-banner"><div><span className="eyebrow">ШАГ ЗА ШАГОМ</span><h2>Каждая отметка делает<br/>подборку полезнее.</h2><p>Изученное не появится в следующем маршруте.</p></div><div className="progress-counter"><strong>{learnCount.toString().padStart(2,'0')}</strong><span>освоено</span></div></div>{!progress.length?<div className="empty-state"><BookOpen size={30}/><h3>Здесь начнётся ваша история</h3><p>Постройте маршрут и отметьте полезный или изученный материал.</p><button className="primary" onClick={()=>navigate('route')}>Найти первый шаг <ArrowRight size={16}/></button></div>:<div className="progress-list">{progress.map(({material:m,signal})=><article key={m.id}>{materialTags(m)}<button className="card-title" onClick={()=>openMaterial(m)}>{m.title}<ArrowUpRight size={17}/></button><div className="progress-row"><span className="saved"><Check size={13}/>{signalsText[signal]}</span><button className="text-button muted" disabled={busy} onClick={()=>feedback(m.id,'reset')}>Убрать отметку</button></div></article>)}</div>}<p className="small-note">Прогресс хранится в базе приложения и связан с cookie этого браузера. Это собственные события прототипа, а не история пользователей Альфа-Курса.</p></section>}
        <footer><span>Альфа-Маршрут · Hack&Change 2026</span><span>Конкурсная разработка · не официальный сервис банка</span></footer>
      </main>
    </div>
    {toast&&<div className="toast" role="status"><Check size={17}/>{toast}</div>}
    <dialog ref={dialog} className="material-dialog" onCancel={()=>setSelected(null)} onClick={e=>{if(e.target===e.currentTarget)setSelected(null);}}>
      {selected&&<><button className="dialog-close" aria-label="Закрыть материал" onClick={()=>setSelected(null)}><X size={22}/></button><div className="eyebrow">{selected.provenance==='synthetic'?'УЧЕБНЫЙ ПРИМЕР · DEMO':'МАТЕРИАЛ КАТАЛОГА'}</div>{materialTags(selected)}<h2>{selected.title}</h2><p className="dialog-description">{selected.description}</p>{selected.provenance==='synthetic'?<><div className="demo-warning">Это авторский пример для проверки рекомендаций. Такого курса или материала может не быть на платформе Альфа-Курс.</div>{selected.demo_content?<div className="demo-content">{selected.demo_content}</div>:<p>Подробное содержание платного материала не раскрывается. В этом учебном демо покупка не предусмотрена.</p>}</>:<p>{selected.url?'Подробное содержание и актуальные условия доступны у первоисточника.':'В выгрузке есть относительный адрес, но путь к странице ещё не подтверждён. Ссылку не придумываем.'}</p>}{selected.url&&<a className="primary external-link" href={selected.url} target="_blank" rel="noopener noreferrer">Перейти к первоисточнику <ArrowUpRight size={17}/></a>}<div className="dialog-feedback"><h3>Как вам этот материал?</h3>{feedbackButtons(selected)}</div></>}
    </dialog>
  </div>;
}
