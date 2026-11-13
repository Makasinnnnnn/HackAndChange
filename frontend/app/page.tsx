'use client';

import Image from 'next/image';
import customersArt from './art/customers.webp';
import financeArt from './art/finance.webp';
import launchArt from './art/launch.webp';
import {useEffect, useRef, useState, type DragEvent} from 'react';
import {ChoiceField} from './choice-field';
import {NavigationIcon} from './navigation-icon';
import {MaterialCopy} from './material-copy';
import {ArrowUpRight, ArrowRight, BookOpen, Check, CheckCheck, ChevronDown, ChevronLeft, ChevronRight, CircleHelp, FileText, LoaderCircle, Plus, Search, Sparkles, ThumbsDown, ThumbsUp, Upload, X} from 'lucide-react';

type Tab = 'route' | 'progress' | 'catalog' | 'jury';
type Profile = {stage?:string|null; industry?:string|null; experience?:string|null; format?:string|null; urgency?:string|null};
type Material = {id:string; title:string; description:string; source_type:string; topics:string[]; industries:string[]; access:string; price:number|null; duration:string|null; url:string|null; provenance:string; demo_content?:string|null};
type Item = {material:Material; reasons:string[]; next_action:string; phase:string; score:number; rank_score:number; signals:Record<string,number>};
type Route = {match_scope?:'task'|'general';route_id:string; query:string; profile:Profile; items:Item[]; clarification:string|null; notice:string|null; elapsed_ms:number; algorithm:string; excluded_count:number; candidate_count:number; active_profile_fields:string[]; catalog_version:string};
type Evaluation = {status:string;note:string;metrics?:Record<string,Record<string,Record<string,number>>>|null;judged_profiles?:number};
type Persona = {id:string; name:string; situation:string; query:string; profile:Profile};
const catalogPageSize = 12;
function counted(count:number,forms:[string,string,string]) {
  const last=count%10, hundred=count%100;
  return `${count} ${forms[hundred>=11&&hundred<=14?2:last===1?0:last>=2&&last<=4?1:2]}`;
}
const formats:Record<string,string> = {article:'Статья',course:'Курс',document:'Шаблон',webinar:'Вебинар',podcast:'Подкаст',glossary:'Термин',calculator:'Калькулятор'};
const profileChoices = {
  stage: [{value: 'idea', label: 'Есть идея'}, {value: 'start', label: 'Недавно запустился'}, {value: 'growth', label: 'Развиваю бизнес'}],
  experience: [{value: 'beginner', label: 'Начинающий'}, {value: 'experienced', label: 'Есть опыт'}],
  format: Object.entries(formats).map(([value, label]) => ({value, label})),
};
const access:Record<string,string> = {free:'Бесплатно',paid:'Платный материал',subscription:'По подписке',unknown:'Условия на сайте'};
const signalsText:Record<string,string> = {helpful:'Полезно',not_relevant:'Не подходит',known:'Уже знаю',completed:'Изучено'};
const examples = [
  {art:customersArt, title:'Привлечь клиентов',query:'В моей кофейне мало клиентов. Как привлечь новых посетителей?',topic:'Маркетинг и продажи'},
  {art:financeArt, title:'Разобраться с деньгами',query:'Как избежать кассового разрыва и спланировать платежи?',topic:'Финансы бизнеса'},
  {art:launchArt, title:'Запустить своё дело',query:'Хочу открыть свой бизнес с нуля. С чего начать?',topic:'Первые шаги'},
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
  const [draggingHistory,setDraggingHistory] = useState(false);
  const [personaId,setPersonaId] = useState('');
  const [intent,setIntent] = useState<{goal:string;clarification:string|null}|null>(null);
  const [intentAnswer,setIntentAnswer] = useState('');
  const [aiBusy,setAiBusy] = useState(false);
  const [aiEnabled,setAiEnabled] = useState(false);
  const [aiExternal,setAiExternal] = useState(false);
  const [busy,setBusy] = useState(false);
  const [ready,setReady] = useState(false);
  const [error,setError] = useState('');
  const [toast,setToast] = useState({message:'', visible:false});
  const [info,setInfo] = useState<{catalog_mode:string;catalog_count:number;semantic_model:string|null;industries:string[]}>({catalog_mode:'demo',catalog_count:0,semantic_model:null,industries:[]});
  const [evaluation,setEvaluation] = useState<Evaluation>({status:'',note:''});
  const queryRef = useRef(query);
  const aiRequest = useRef(0);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const dialogTitle = useRef<HTMLHeadingElement>(null);
  const catalogTop = useRef<HTMLElement>(null);
  const pageCount = Math.ceil(catalog.total / catalogPageSize);
  const currentPage = Math.floor(offset / catalogPageSize) + 1;
  const pageNumbers = Array.from(new Set([1, currentPage - 1, currentPage, currentPage + 1, pageCount]))
    .filter(number=>number >= 1 && number <= pageCount).sort((a,b)=>a-b);
  const menuTrigger = useRef<HTMLButtonElement>(null);
  const menuClose = useRef<HTMLButtonElement>(null);
  const menuPanel = useRef<HTMLElement>(null);
  const restoreMenuFocus = useRef(false);
  const menuHoverTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const learnCount = Object.values(history).filter(v=>v==='completed'||v==='known').length;

  useEffect(()=>{
    let active=true;
    api<{profile:Profile;query:string;signals:Record<string,string>;catalog_mode:string;catalog_count:number;semantic_model:string|null;industries:string[];llm_enabled?:boolean;llm_external?:boolean}>('/bootstrap')
      .then(data=>{if(!active)return;setProfile(data.profile);updateQuery(data.query);setHistory(data.signals);setInfo(data);setAiEnabled(Boolean(data.llm_enabled));setAiExternal(Boolean(data.llm_external));setReady(true);})
      .catch(()=>{if(active)setError('Не удалось подключиться к приложению. Обновите страницу после запуска сервера.');});
    api<Persona[]>('/demo/profiles').then(people=>{if(active)setPersonas(people);}).catch(()=>{});
    api<Evaluation>('/evaluation/results').then(result=>{if(active)setEvaluation(result);})
      .catch(()=>{if(active)setEvaluation({status:'unavailable',note:'Оценка временно недоступна. Подбор материалов продолжает работать.'});});
    return()=>{active=false;};
  },[]);

  useEffect(()=>{
    if (selected) {
      dialog.current?.showModal();
      dialogTitle.current?.focus({preventScroll:true});
    } else {
      dialog.current?.close();
    }
  },[selected]);

  useEffect(()=>{
    const root = document.documentElement;
    const usePointer = ()=>{root.dataset.input = 'pointer';};
    const useKeyboard = (event: KeyboardEvent)=>{
      if (event.key === 'Tab') root.dataset.input = 'keyboard';
    };
    document.addEventListener('pointerdown', usePointer, true);
    document.addEventListener('keydown', useKeyboard, true);
    return ()=>{
      document.removeEventListener('pointerdown', usePointer, true);
      document.removeEventListener('keydown', useKeyboard, true);
      delete root.dataset.input;
    };
  },[]);
  useEffect(()=>{
    if(!toast.visible)return;
    const id=setTimeout(()=>setToast(current=>({...current, visible:false})),3200);
    return()=>clearTimeout(id);
  },[toast]);


  useEffect(()=>{
    if(tab!=='catalog')return;
    let active = true;
    const timer = setTimeout(async()=>{
      try {
        const result = await api<{items:Material[];total:number}>(`/catalog?q=${encodeURIComponent(catalogQuery)}&offset=${offset}&limit=${catalogPageSize}`);
        if(active)setCatalog(result);
      } catch(e) {
        if(active)setError((e as Error).message);
      }
    },250);
    return ()=>{active=false;clearTimeout(timer);};
  },[tab,catalogQuery,offset]);
  useEffect(()=>{if(tab==='progress')api<{items:{material:Material;signal:string}[]}>('/progress').then(d=>setProgress(d.items)).catch(e=>setError(e.message));},[tab,history]);

  useEffect(()=>{
    if (!mobileMenu) {
      if (restoreMenuFocus.current) menuTrigger.current?.focus();
      restoreMenuFocus.current = false;
      return;
    }
    menuClose.current?.focus();
    function onEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        restoreMenuFocus.current = true;
        setMobileMenu(false);
      }
    }
    const desktop = window.matchMedia('(width > 1100px)');
    function onResize(event: MediaQueryListEvent) {
      if (event.matches) {
        setMobileMenu(false);
        if (document.activeElement === menuClose.current) {
          menuPanel.current?.querySelector<HTMLButtonElement>('[aria-current="page"]')?.focus();
        }
      }
    }
    window.addEventListener('keydown', onEscape);
    desktop.addEventListener('change', onResize);
    return ()=>{
      window.removeEventListener('keydown', onEscape);
      desktop.removeEventListener('change', onResize);
    };
  },[mobileMenu]);

  useEffect(()=>()=>clearTimeout(menuHoverTimer.current),[]);

  function closeMenu() {
    restoreMenuFocus.current = true;
    setMobileMenu(false);
  }

  function navigate(next:Tab){
    setTab(next);
    window.scrollTo(0, 0);
    if (mobileMenu) closeMenu();
    setError('');
  }
  function goToCatalogPage(page:number) {
    setOffset((page - 1) * catalogPageSize);
    catalogTop.current?.scrollIntoView({block:'start'});
  }

  function updateQuery(value:string){queryRef.current=value;setQuery(value);setIntent(null);setIntentAnswer('');}
  function patchProfile(key:keyof Profile,value:string){if(busy||!ready)return;setProfile(p=>({...p,[key]:value||null}));setComparison(null);}
  async function recommend(override?:string){
    const value=override??query;if(override!==undefined)updateQuery(override);setBusy(true);setError('');
    try{setRoute(await api('/recommendations',{query:value,profile}));setTab('route');}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function clarifyTask(){
    const input=query;
    const request=++aiRequest.current;
    setAiBusy(true);setError('');setIntent(null);setIntentAnswer('');
    try{const result=await api<{status:string;intent:{goal:string;clarification:string|null}|null}>('/intent',{query:input});
      if(request!==aiRequest.current||queryRef.current!==input)return;
      if(result.intent)setIntent(result.intent);
      else if(result.status==='unchanged')setError('AI не нашёл более точной формулировки. Укажите, что хотите понять или решить; маршрут можно построить по вашему тексту.');
      else setError('AI-помощник сейчас недоступен. Можно построить маршрут по исходной задаче.');
    }catch{if(request===aiRequest.current&&queryRef.current===input)setError('AI-помощник не ответил. Можно построить маршрут обычным способом.');}finally{if(request===aiRequest.current)setAiBusy(false);}
  }
  function dropHistory(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDraggingHistory(false);
    if (busy || !ready) return;
    const files = event.dataTransfer.files;
    if (files.length > 1) {
      setError('Выберите один JSON-файл.');
      return;
    }
    if (files[0]) void importHistory(files[0]);
  }
  async function importHistory(file:File){
    setError('');if(file.size>16000){setError('Файл истории должен быть меньше 16 КБ.');return;}
    setBusy(true);
    try{const body=JSON.parse(await file.text());const result=await api<{signals:Record<string,string>;imported:number}>('/history/import',body);setHistory(result.signals);setToast({message:`Добавлено завершённых курсов: ${result.imported}`,visible:true});setComparison(null);}
    catch{setError('История не импортирована. Проверьте формат файла и версию каталога.');}finally{setBusy(false);}
  }
  async function compare(){setBusy(true);setError('');try{setComparison(await api('/demo/compare',{query,profile}));}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function feedback(materialId:string,signal:string){setBusy(true);setError('');try{
    const result=await api<{signals:Record<string,string>}>('/feedback',{material_id:materialId,signal});setHistory(result.signals);
    setToast({message:signal==='reset'?'Отметка удалена':'Отметка сохранена',visible:true});setComparison(null);
  }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  async function openMaterial(material:Material){setError('');setToast(current=>({...current,visible:false}));try{setSelected(await api<Material>('/catalog/'+encodeURIComponent(material.id)));}catch(e){setError((e as Error).message);}}
  function choosePersona(id:string){const p=personas.find(p=>p.id===id);if(p){setPersonaId(id);updateQuery(p.query);setProfile(p.profile);setComparison(null);}}

  function materialTags(m:Material){return <div className="material-tags"><span className={'format '+m.source_type}>{m.source_type==='document'?<FileText size={13}/>:<BookOpen size={13}/>} {formats[m.source_type]}</span><span className={m.access==='free'?'free':''}>{access[m.access]}</span>{m.duration&&<span>{m.duration}</span>}</div>;}
  function feedbackNotice() {
    return <div className="toast" role="status" aria-hidden={!toast.visible} data-visible={toast.visible}>
      <Check size={18} aria-hidden="true"/><span>{toast.message}</span>
    </div>;
  }

  function feedbackButtons(m:Material){return <div className="feedback" aria-label={'Обратная связь: '+m.title}>
    {([{signal:'helpful',label:'Полезно',Icon:ThumbsUp},{signal:'not_relevant',label:'Не подходит',Icon:ThumbsDown},{signal:'known',label:'Уже знаю',Icon:Check},{signal:'completed',label:'Изучено',Icon:CheckCheck}]).map(({signal,label,Icon})=><button key={signal} aria-label={label} title={label} disabled={busy} onClick={()=>feedback(m.id,history[m.id]===signal?'reset':signal)} aria-pressed={history[m.id]===signal}><Icon size={14}/><span>{label}</span></button>)}
  </div>;}
  function routeCard(item:Item,index:number,total:number,diagnostic=false){const m=item.material;return <article className="route-card" key={m.id}>
    <div className="route-card-meta">
      <span className="step-number">
        <svg viewBox="0 0 44 44" aria-hidden="true">
          <circle className="step-track" cx="22" cy="22" r="19"/>
          <circle className="step-arc" cx="22" cy="22" r="19" pathLength="100" strokeDasharray={`${Math.round((index + 1) * 100 / total)} 100`}/>
        </svg>
        {index + 1}
      </span>
      <span>{item.phase}</span>
      {history[m.id]&&<span className="saved"><Check size={14}/>{signalsText[history[m.id]]}</span>}
    </div>
    <div className="route-card-content">
      {materialTags(m)}
      <h3 className="route-card-title">{m.title}</h3>
      <p className="description">{m.description}</p>
      <div className="reason"><span><strong>Почему этот материал</strong><br/>{item.reasons.slice(0,2).join(' · ')}</span></div>
      <div className="next-action"><strong>Следующий шаг</strong><p>{item.next_action}</p></div>
      {diagnostic&&<details className="diagnostic"><summary>Расчёт ранжирования · {item.rank_score.toFixed(3)}</summary><dl>{Object.entries(item.signals).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v.toFixed(3)}</dd></div>)}</dl><ul>{item.reasons.map(r=><li key={r}>{r}</li>)}</ul></details>}
      <div className="card-footer"><button className="primary route-open" aria-label="Открыть материал" onClick={()=>openMaterial(m)}><span>Открыть<span className="route-open-detail"> материал</span></span><ArrowRight size={15} aria-hidden="true"/></button>{!diagnostic&&feedbackButtons(m)}</div>
    </div></article>;}

  const profileForm=<div className="profile-fields" id="profile-fields">
    <ChoiceField label="Этап бизнеса" value={profile.stage??''} options={profileChoices.stage} emptyLabel="Можно пропустить" clearable disabled={busy||!ready} onChange={value=>patchProfile('stage', value)}/>
    <ChoiceField label="Сфера" value={profile.industry??''} options={(info.industries.length ? info.industries : ['HoReCa', 'Торговля', 'Услуги', 'IT']).map(value=>({value, label:value}))} emptyLabel="Не указана" clearable disabled={busy||!ready} onChange={value=>patchProfile('industry', value)}/>
    <ChoiceField label="Опыт" value={profile.experience??''} options={profileChoices.experience} emptyLabel="Можно пропустить" clearable disabled={busy||!ready} onChange={value=>patchProfile('experience', value)}/>
    <ChoiceField label="Удобный формат" value={profile.format??''} options={profileChoices.format} emptyLabel="Любой формат" clearable disabled={busy||!ready} onChange={value=>patchProfile('format', value)}/>
    <button className="text-button muted" disabled={busy||!ready} onClick={()=>{setProfile({});setComparison(null);}}>Сбросить профиль</button>
  </div>;

  return <div className="app-shell">
    <aside ref={menuPanel} id="main-menu" className={mobileMenu ? 'sidebar open' : 'sidebar'}>
      <div className="sidebar-header">
        <a className="brand" href="/" aria-label="Альфа-Маршрут, главная">
          <span className="brand-mark" aria-hidden="true"/>
          <span>Альфа-Маршрут</span>
        </a>
        <button type="button" ref={menuClose} className="mobile-menu menu-close" aria-label="Закрыть меню" onClick={closeMenu}><X size={22}/></button>
      </div>
      <nav aria-label="Основная навигация">
        {([{id:'route',label:'Мой маршрут'},{id:'progress',label:'Мой прогресс'},{id:'catalog',label:'Каталог знаний'},{id:'jury',label:'Для жюри'}] as const).map(({id,label})=>(
          <button key={id} className={tab===id?'nav-item selected':'nav-item'} aria-current={tab===id?'page':undefined} onClick={()=>navigate(id)}>
            <NavigationIcon tab={id}/>{label}
          </button>
        ))}
      </nav>
      <p className="sidebar-bottom">Hack&Change 2026</p>
    </aside>
    <div aria-hidden="true" className={mobileMenu ? 'menu-backdrop visible' : 'menu-backdrop'} onClick={closeMenu}/>
    <div className="main-shell" inert={mobileMenu}>
      <main>
        <div className="compact-navigation">
          <button
            type="button"
            ref={menuTrigger}
            className="brand compact-menu-trigger"
            aria-label="Альфа-Маршрут, открыть меню"
            aria-expanded={mobileMenu}
            aria-controls="main-menu"
            onPointerMove={event=>{
              if(event.pointerType==='mouse'&&menuHoverTimer.current===undefined){
                menuHoverTimer.current=setTimeout(()=>setMobileMenu(true),200);
              }
            }}
            onPointerLeave={()=>{
              clearTimeout(menuHoverTimer.current);
              menuHoverTimer.current=undefined;
            }}
            onClick={()=>{
              clearTimeout(menuHoverTimer.current);
              setMobileMenu(true);
            }}
          >
            <span className="brand-mark" aria-hidden="true"/>
            <span>Альфа-Маршрут</span>
          </button>
        </div>
        <h1 className={tab==='route'||tab==='jury' ? 'page-heading aligned-heading' : 'page-heading'}>{{route:'Персональный маршрут',progress:'Мой прогресс',catalog:'Каталог знаний',jury:'Сравнение рекомендаций'}[tab]}</h1>
        {error&&!selected&&<div className="error-banner" role="alert">{error}<button aria-label="Закрыть сообщение" onClick={()=>setError('')}><X size={16}/></button></div>}
        {(tab==='route'||tab==='jury')&&<div className="workspace">
          <section className="task-card" aria-labelledby="task-title">
            <div className="section-top">
              <h2 id="task-title">Что сейчас важно для вашего дела?</h2>
            </div>
            <form onSubmit={e=>{e.preventDefault();if(tab==='jury')compare();else recommend();}}>
              <div className="task-field">
                <label htmlFor="business-task">Ваша бизнес-задача</label>
                <span className="char-count" aria-hidden="true">{query.length}/1500</span>
                <textarea disabled={busy||!ready} ref={textarea} id="business-task" placeholder="Например, как привлечь больше клиентов в кофейню?" maxLength={1500} value={query} onChange={e=>{updateQuery(e.target.value);setIntent(null);setComparison(null);}}/>
              </div>
              <div className="task-controls"><div className="pace-options" aria-label="Темп обучения"><button type="button" disabled={busy} aria-pressed={profile.urgency==='quick'} className={profile.urgency==='quick'?'active':''} onClick={()=>patchProfile('urgency',profile.urgency==='quick'?'':'quick')}>Быстро применить</button><button type="button" disabled={busy} aria-pressed={profile.urgency==='deep'} className={profile.urgency==='deep'?'active':''} onClick={()=>patchProfile('urgency',profile.urgency==='deep'?'':'deep')}>Разобраться глубже</button></div></div>
              <div className="task-submit"><button className="primary" type="submit" disabled={busy||!ready}>{busy?<LoaderCircle className="spinning" size={17}/>:<ArrowRight size={17}/>} {tab==='jury'?'Сравнить алгоритмы':'Построить маршрут'}</button></div>
            </form>
            {aiEnabled&&<div className="honesty-note"><Sparkles size={17}/><div><button className="text-button" type="button" disabled={busy||aiBusy||!query.trim()} onClick={clarifyTask}>{aiBusy?'AI уточняет задачу…':'Уточнить задачу с AI'}</button><p>{aiExternal?'Текст задачи будет передан настроенному AI-сервису. Уберите имена, контакты и другие личные сведения.':'Текст задачи обрабатывается локальным AI-помощником.'} Проверьте предложенную формулировку перед применением.</p></div></div>}
            {intent&&<div className="empty-state"><h3>Предложение AI</h3><p>{intent.goal}</p>{intent.clarification&&<label className="intent-answer">{intent.clarification}<input aria-label="Ответ на уточнение AI" value={intentAnswer} maxLength={300} placeholder="Уточните здесь или оставьте поле пустым" onChange={e=>setIntentAnswer(e.target.value)}/></label>}<button className="secondary" disabled={busy} onClick={()=>{setComparison(null);void recommend(intent.goal+(intentAnswer.trim()?'. '+intentAnswer.trim():''));}}>Применить и построить маршрут</button><button className="text-button" onClick={()=>setIntent(null)}>Оставить мою задачу</button></div>}
          </section>
          <aside className={profileOpen ? 'context-card expanded' : 'context-card'}>
            <div className="context-heading"><h2>Ваш контекст</h2><p>Необязательно</p></div>
            <button className="context-toggle" type="button" onClick={()=>setProfileOpen(!profileOpen)} aria-expanded={profileOpen} aria-controls="profile-fields">
              <span>Ваш контекст <small>Необязательно</small></span><Plus size={20} aria-hidden="true"/>
            </button>
            {profileForm}
          </aside>
        </div>}

        {tab==='route'&&!route&&<section className="starting-points"><div className="section-label"><h2>Можно начать с этого</h2></div><div className="example-grid">{examples.map(e=><button className="example-card" key={e.title} disabled={busy||!ready} onClick={()=>recommend(e.query)}><span><strong>{e.title}</strong><small>{e.topic}</small></span><Image className="example-art" src={e.art} alt="" width={128} height={128} unoptimized/><ArrowUpRight size={18} aria-hidden="true"/></button>)}</div></section>}
        {tab==='route'&&route&&<section className="route-results" aria-live="polite"><div className="route-intro">
          <div className="section-label"><h2>{route.match_scope==='general'?'Общие материалы по задаче':'Ваш маршрут'}{route.items.length>0&&<span className="count-badge">{counted(route.items.length,route.match_scope==='general'?['материал','материала','материалов']:['шаг','шага','шагов'])}</span>}</h2><button className="text-button muted" onClick={()=>navigate('jury')}>Почему именно эти материалы? <ArrowUpRight size={15}/></button></div>
          {route.query&&<p className="route-context"><strong>Ваша задача</strong><br/>{route.query}</p>}
          {route.active_profile_fields.length>0&&<p className="small-note">Учитываем только заполненный контекст. Материалы без известных признаков уровня и стадии не получают таких объяснений.</p>}
          </div>{route.clarification&&<div className="empty-state"><CircleHelp size={28}/><h3>Давайте найдём точку старта</h3><p>{route.clarification}</p><div className="empty-actions">{examples.map(e=><button className="secondary" key={e.title} disabled={busy} onClick={()=>recommend(e.query)}>{e.title}</button>)}</div></div>}
          {route.notice&&<div className="notice">{route.notice}</div>}
          <div className="route-layout"><div>{route.items.map((item,i)=>routeCard(item,i,route.items.length))}</div>{route.items.length>0&&<aside className="route-summary">
            <h3>Ваш прогресс</h3>
            <p className="summary-count"><strong>{learnCount}</strong><span>Материалов освоено</span></p>
            <p>Отметьте материал, чтобы учесть его в следующей подборке.</p>
            <button className="secondary" disabled={busy} onClick={()=>recommend()}>Обновить маршрут <ArrowRight size={17}/></button>
          </aside>}</div>
        </section>}

        {tab==='jury'&&<section className="jury-section" aria-labelledby="jury-scenario">
          <div className="jury-setup">
            <div className="jury-toolbar">
              <div><h2 id="jury-scenario">Сценарий сравнения</h2><p>Выберите профиль предпринимателя или введите свою задачу выше.</p></div>
              <ChoiceField label="Демонстрационный предприниматель" value={personaId} options={personas.map(person=>({value:person.id, label:person.name}))} emptyLabel="Выбрать предпринимателя" disabled={busy} onChange={choosePersona}/>
            </div>
            <div className="evaluation-note">
              <h3>{evaluation.status==='calculated'?'Результаты экспертной оценки':'Экспертная оценка'}</h3>
              <p>{evaluation.note||'Результаты ещё не рассчитаны.'}</p>
            </div>
          </div>
          {evaluation.metrics&&<div className="metrics-scroll"><table className="metrics-table"><caption>Offline-метрики на размеченных профилях: {evaluation.judged_profiles}</caption><thead><tr><th>Выборка</th><th>Алгоритм</th><th>P@5</th><th>nDCG@5</th><th>MRR@5</th></tr></thead><tbody>{Object.entries(evaluation.metrics).flatMap(([split,algorithms])=>Object.entries(algorithms).map(([algorithm,m])=><tr key={split+algorithm}><td>{split}</td><td>{algorithm}</td><td>{m.precision_at_5.toFixed(3)}</td><td>{m.ndcg_at_5.toFixed(3)}</td><td>{m.mrr_at_5.toFixed(3)}</td></tr>))}</tbody></table></div>}{comparison&&<><p className="small-note">{comparison.note}</p><div className="comparison-grid">{([{title:'Подбор по теме',subtitle:'Baseline · без профиля и истории',route:comparison.baseline},{title:'Персональный маршрут',subtitle:'Задача + известный контекст + обратная связь',route:comparison.personal}]).map((col,i)=><section key={col.title} className={'comparison-column '+(i?'personal':'')}><div className="compare-heading"><span className="compare-letter">{i?'B':'A'}</span><div><h3>{col.title}</h3><p>{col.subtitle}</p></div></div><div className="compare-stats"><span>{col.route.elapsed_ms.toFixed(1)} мс</span><span>{col.route.candidate_count} кандидатов</span><span>{col.route.excluded_count} исключено</span></div>{col.route.clarification&&<div className="notice">{col.route.clarification}</div>}{col.route.items.map((item,index)=>routeCard(item,index,col.route.items.length,true))}</section>)}</div><p className="small-note">Время измерено для этого запроса на сервере, без сети. Алгоритм: {comparison.personal.algorithm.includes('e5')?'локальная E5 + TF-IDF и персональное ранжирование':'лексический TF-IDF и персональное ранжирование'}. Версия каталога: {comparison.personal.catalog_version}.</p></>}
        </section>}

        {tab==='catalog'&&<section ref={catalogTop} aria-label="Материалы каталога">
          <div className="catalog-toolbar">
            <label className="search-field">
              <Search size={20} aria-hidden="true"/>
              <input aria-label="Поиск в каталоге" placeholder="Название или тема материала" maxLength={150} value={catalogQuery} onChange={e=>{setCatalogQuery(e.target.value);setOffset(0);}}/>
            </label>
            <span className="small-note" aria-live="polite">Найдено: {catalog.total}</span>
          </div>
          <div className="catalog-grid">
            {catalog.items.map(m=><article className="catalog-card" key={m.id}>
              {materialTags(m)}
              <h2><button className="catalog-open" onClick={()=>openMaterial(m)}>{m.title}<ArrowUpRight size={22} aria-hidden="true"/></button></h2>
              <p>{m.description}</p>
            </article>)}
          </div>
          {!catalog.items.length&&<div className="empty-state"><Search size={27}/><h3>Здесь пока ничего нет</h3><p>Попробуйте более короткий или другой запрос.</p></div>}
          {pageCount>1&&<nav className="pagination" aria-label="Страницы каталога">
            <button className="page-button" aria-label="Предыдущая страница" disabled={currentPage===1} onClick={()=>goToCatalogPage(currentPage-1)}><ChevronLeft size={20}/></button>
            {pageNumbers.map((number,index)=><span className="page-slot" key={number}>
              {index>0&&number-pageNumbers[index-1]>1&&<span aria-hidden="true">…</span>}
              <button className="page-button" aria-label={`Страница ${number}`} aria-current={number===currentPage?'page':undefined} onClick={()=>goToCatalogPage(number)}>{number}</button>
            </span>)}
            <button className="page-button" aria-label="Следующая страница" disabled={currentPage===pageCount} onClick={()=>goToCatalogPage(currentPage+1)}><ChevronRight size={20}/></button>
          </nav>}
        </section>}

        {tab==='progress'&&<section aria-label="История обучения">
          <div className="progress-overview">
            <div className="progress-banner">
              <div className="progress-counter"><strong>{learnCount}</strong><span>Материалов освоено</span></div>
              <p>Изученные материалы исключаются из следующего маршрута.</p>
            </div>
            <section className="history-import" aria-labelledby="history-title">
              <h2 id="history-title">Добавить историю обучения</h2>
              <p id="history-help">Загрузите JSON с завершёнными курсами из текущего каталога.</p>
              <label
                className={draggingHistory ? 'file-picker dragging' : 'file-picker'}
                onDragOver={event=>{
                  if (!event.dataTransfer.types.includes('Files')) return;
                  event.preventDefault();
                  event.dataTransfer.dropEffect = busy || !ready ? 'none' : 'copy';
                  setDraggingHistory(!busy && ready);
                }}
                onDragLeave={event=>{
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDraggingHistory(false);
                }}
                onDrop={dropHistory}
              >
                <input className="sr-only" type="file" accept="application/json,.json" aria-label="Выбрать JSON-файл" aria-describedby="history-help" disabled={busy||!ready} onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void importHistory(file);}}/>
                <Upload size={20} aria-hidden="true"/>
                <span>{busy ? 'Добавляем…' : draggingHistory ? 'Отпустите файл' : 'Перетащите JSON сюда или выберите файл'}</span>
              </label>
            </section>
          </div>
          {!progress.length?<div className="empty-state progress-empty">
            <h2>Здесь появятся ваши отметки</h2>
            <p>Постройте маршрут и отметьте полезный или изученный материал.</p>
            <button className="primary" onClick={()=>navigate('route')}>Построить маршрут <ArrowRight size={16}/></button>
          </div>:<div className="progress-list">{progress.map(({material:m,signal})=><article key={m.id}>
            {materialTags(m)}
            <button className="card-title" onClick={()=>openMaterial(m)}>{m.title}<ArrowUpRight size={17}/></button>
            <div className="progress-row"><span className="saved"><Check size={13}/>{signalsText[signal]}</span><button className="text-button muted" disabled={busy} onClick={()=>feedback(m.id,'reset')}>Убрать отметку</button></div>
          </article>)}</div>}
        </section>}
      </main>
      <footer><span>Альфа-Маршрут</span><span>Конкурсная разработка · не официальный сервис банка</span></footer>
    </div>
    {!selected&&feedbackNotice()}
    <dialog ref={dialog} className="material-dialog" aria-labelledby="material-title" onClose={()=>setToast(current=>({...current,visible:false}))} onCancel={()=>setSelected(null)} onClick={e=>{
      if(e.target!==e.currentTarget)return;
      const {left,right,top,bottom}=e.currentTarget.getBoundingClientRect();
      if(e.clientX<left||e.clientX>right||e.clientY<top||e.clientY>bottom)setSelected(null);
    }}>
      {selected&&<>
        <div className="material-scroll">
          <div className="material-top">
            {selected.provenance==='synthetic'&&<p className="material-provenance">Учебный пример · DEMO</p>}
            {materialTags(selected)}
            <button className="dialog-close" aria-label="Закрыть материал" onClick={()=>setSelected(null)}><X size={22}/></button>
          </div>
          <h2 id="material-title" ref={dialogTitle} tabIndex={-1}>{selected.title}</h2>
          <p className="dialog-description">{selected.description}</p>
          {selected.provenance==='synthetic'&&selected.demo_content
            ? <MaterialCopy content={selected.demo_content} description={selected.description}/>
            : <p className="material-access-note">{selected.provenance==='synthetic'
              ? 'Это учебный пример. Подробное содержание платного материала недоступно.'
              : selected.url
                ? 'Подробное содержание и актуальные условия доступны у первоисточника.'
                : 'Ссылка на первоисточник пока не подтверждена.'}</p>}
          {selected.url&&<a className="primary external-link" href={selected.url} target="_blank" rel="noopener noreferrer">Перейти к первоисточнику <ArrowUpRight size={17}/></a>}
        </div>
        <div className="dialog-feedback">
          <h3>Как вам этот материал?</h3>
          {error&&<p className="error-banner" role="alert">{error}</p>}
          {feedbackButtons(selected)}
          {feedbackNotice()}
        </div>
      </>}
    </dialog>
  </div>;
}
