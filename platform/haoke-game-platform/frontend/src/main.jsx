import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowUpRight, ArrowRight, ArrowLeft, Gamepad2, Users, Grid2X2, Sparkles, Copy, Check, X, LogOut, ChevronRight, Mail, ShieldCheck, KeyRound, Settings2, BarChart3, Search, Plus, RefreshCw, Monitor, Smartphone, Globe2, Clock3, CircleHelp, Smile, VolumeX, Volume2, CheckCircle2, AlertCircle, ExternalLink, Crown, DoorOpen, CircleDashed, LockKeyhole, Inbox, Radio, Download, Menu, Layers3, Play, Link2, History, Activity, Eye, EyeOff } from 'lucide-react';
import { api, post, setCSRF, fmtDate } from './api';
import './styles.css';
import Admin from './pages-admin';

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);
export function useData(path, deps = []) {
  const [data,setData]=useState(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[revision,setRevision]=useState(0);
  useEffect(()=>{
    const controller=new AbortController(); setLoading(true); setError('');
    api(path,{signal:controller.signal}).then(setData).catch(e=>{if(e.name!=='AbortError')setError(e.message)}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});
    return ()=>controller.abort();
  },[path,revision,...deps]);
  return {data,error,loading,reload:()=>setRevision(x=>x+1),setData};
}
export function Button({children,variant='primary',className='',busy=false,...props}) {
  return <button className={'btn '+variant+' '+className} {...props} disabled={props.disabled||busy}>{busy?<RefreshCw className="spin" size={17}/>:null}{children}</button>;
}
export function Tag({children,tone=''}) {return <span className={'tag '+tone}>{children}</span>}
export function ErrorBox({message,retry}) {return message?<div className="error-box" role="alert"><AlertCircle size={18}/><span>{message}</span>{retry&&<button onClick={retry}>重试</button>}</div>:null}
export function Empty({icon:Icon=CircleDashed,title,children,action}) {return <div className="empty"><span className="empty-icon"><Icon size={30}/></span><h3>{title}</h3><p>{children}</p>{action}</div>}
export function Loading(){return <div className="loading"><RefreshCw className="spin" size={22}/> 正在加载…</div>}
export function Emote({id='hello',index,className='',label,size=80}) {
  const {assets}=useApp();
  const emote=index!==undefined?assets?.emotes[index]:assets?.emotes.find(e=>e.id===id);
  if(!emote)return <span className="emote-placeholder" style={{width:size,height:size}} aria-hidden="true"/>;
  return <img className={'emote '+className} width={size} height={size} src={emote.asset} alt={label||emote.description||emote.label}/>;
}
export function Modal({title,children,onClose,wide=false}) {
  const ref=useRef(null);
  useEffect(()=>{
    const previous=document.activeElement;
    ref.current?.focus();
    const key=(event)=>{
      if(event.key==='Escape')onClose();
      if(event.key==='Tab') {
        const items=[...ref.current.querySelectorAll('button:not(:disabled),input:not(:disabled),select,textarea,a[href]')];
        const first=items[0],last=items.at(-1);
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}
        if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
      }
    };
    document.addEventListener('keydown',key);
    const old=document.body.style.overflow;document.body.style.overflow='hidden';
    return ()=>{document.removeEventListener('keydown',key);document.body.style.overflow=old;previous?.focus()};
  },[]);
  return <div className="modal-backdrop" onClick={e=>{if(e.target===e.currentTarget)onClose()}}><section className={'modal '+(wide?'wide':'')} ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button className="icon-btn" onClick={onClose} aria-label="关闭"><X/></button></header>{children}</section></div>
}
export function CopyButton({value,label='复制',variant='secondary'}) {
  const {toast}=useApp();const [fallback,setFallback]=useState(false);
  async function copy(){try{await navigator.clipboard.writeText(value);toast('已复制')}catch{setFallback(true)}}
  return <><Button variant={variant} onClick={copy}><Copy size={16}/>{label}</Button>{fallback&&<Modal title="手动复制" onClose={()=>setFallback(false)}><p className="muted">当前浏览器不支持自动复制，请选中下方内容复制。</p><input readOnly value={value} onFocus={e=>e.target.select()} aria-label="需要复制的内容"/></Modal>}</>
}
export function ShareButton({path,title='浩科游戏中心'}) {
  const {config}=useApp();const [show,setShow]=useState(false);
  const link=(config?.public_url||location.origin)+path;
  async function share(){
    if(navigator.share&&!config?.local_preview){try{await navigator.share({title,url:link});return}catch(e){if(e.name==='AbortError')return}}
    setShow(true);
  }
  return <><Button variant="secondary" onClick={share}><Link2 size={16}/>分享</Button>{show&&<Modal title="分享给小伙伴" onClose={()=>setShow(false)}><p className="muted">{config.local_preview?'这是本机预览地址，其他设备暂时不能通过互联网访问。上线后会使用正式域名。':'发送这个链接，邀请朋友一起来玩。'}</p><div className="copy-field"><input readOnly value={link} aria-label="分享链接" onFocus={e=>e.target.select()}/><CopyButton value={link}/></div></Modal>}</>
}
export function QQCard({compact=false}) {
  const {config}=useApp();const group=config?.site?.qq_group||'1136036532';
  return <div className={'qq-card '+(compact?'compact':'')}><span className="qq-icon"><Users size={compact?22:28}/></span><div><h3>{compact?'找到一起玩的伙伴':'好玩的事，一起分享。'}</h3><p>官方交流QQ群 · {group}</p>{!compact&&<small>复制群号，在QQ中搜索群聊加入。</small>}</div><CopyButton value={group} label="复制群号" variant="quiet"/></div>
}
function App(){
  const [route,setRoute]=useState(location.pathname+location.search+location.hash);
  const [me,setMe]=useState(null),[config,setConfig]=useState(null),[games,setGames]=useState([]),[assets,setAssets]=useState(null);
  const [initError,setInitError]=useState(''),[ready,setReady]=useState(false),[notices,setNotices]=useState([]);
  const toast=useCallback((text,tone='success')=>{
    const id=crypto.randomUUID();setNotices(n=>[...n.slice(-2),{id,text,tone}]);setTimeout(()=>setNotices(n=>n.filter(x=>x.id!==id)),4500);
  },[]);
  const navigate=useCallback((url,replace=false)=>{
    if(!url.startsWith('/')||url.startsWith('//'))url='/';
    history[replace?'replaceState':'pushState']({},'',url);setRoute(url);window.scrollTo({top:0,behavior:'instant'});
  },[]);
  useEffect(()=>{const fn=()=>setRoute(location.pathname+location.search+location.hash);window.addEventListener('popstate',fn);return()=>window.removeEventListener('popstate',fn)},[]);
  const refreshMe=useCallback(async()=>{const d=await api('/me');setMe(d);setCSRF(d.csrf);return d},[]);
  const refreshPublic=useCallback(async()=>{
    const [c,g]=await Promise.all([api('/config'),api('/games')]);setConfig(c);setGames(g.games);
  },[]);
  const initialize=useCallback(async()=>{
    setInitError('');
    try{await Promise.all([refreshMe(),refreshPublic(),fetch('/media/emotes.json').then(r=>{if(!r.ok)throw new Error('表情资源加载失败');return r.json()}).then(setAssets)]);setReady(true)}
    catch(e){setInitError(e.message)}
  },[]);
  useEffect(()=>{initialize()},[]);
  useEffect(()=>{if(config)document.title=config.site.site_name+' · 好玩，一起发生'},[config]);
  const user=me?.user;
  const requireLogin=(next)=>{if(!user){navigate('/login?next='+encodeURIComponent(next||route));return false}return true};
  const ctx={route,navigate,me,user,setMe,config,games,assets,refreshMe,refreshPublic,toast,requireLogin};
  const pathname=route.split(/[?#]/)[0];
  useEffect(()=>{if(route.includes('#community'))requestAnimationFrame(()=>document.getElementById('community')?.scrollIntoView({behavior:'smooth'}))},[route]);
  let page;
  if(pathname==='/login')page=<Login key={route}/>;
  else if(pathname==='/dev-mailbox')page=<DevMailbox/>;
  else if(pathname==='/rooms')page=<PlayInGame/>;
  else if(pathname.startsWith('/rooms/')||pathname.startsWith('/invite/'))page=<Invitation key={route} code={pathname.split('/')[2]}/>;
  else if(pathname.startsWith('/admin/lab'))page=<IntegrationLab/>;
  else if(pathname==='/community')page=<Community/>;
  else if(pathname.startsWith('/games/'))page=<GameDetail key={pathname} gameId={pathname.split('/')[2]}/>;
  else if(pathname==='/me')page=<MyGames/>;
  else if(pathname.startsWith('/admin'))page=<Admin/>;
  else if(pathname==='/')page=<Home/>;
  else page=<Empty title="这个页面走丢了" action={<Button onClick={()=>navigate('/')}>回到游戏广场</Button>}>请从导航中重新选择入口。</Empty>;
  return <AppContext.Provider value={ctx}>
    {!ready?<div className="boot"><span className="brand-mark">H</span><h1>浩科游戏中心</h1>{initError?<ErrorBox message={initError} retry={initialize}/>:<Loading/>}</div>:<Shell>{page}</Shell>}
    <div className="toast-stack" aria-live="polite">{notices.map(n=><div key={n.id} className={'toast '+n.tone}>{n.tone==='error'?<AlertCircle size={18}/>:<CheckCircle2 size={18}/>}<span>{n.text}</span></div>)}</div>
  </AppContext.Provider>
}
function Shell({children}){
  const {route,navigate,user,config,refreshMe,toast}=useApp();const [menu,setMenu]=useState(false);
  const nav=[{url:'/',icon:Grid2X2,label:'游戏广场'},{url:'/community',icon:Smile,label:'玩家社区'},{url:'/me',icon:Gamepad2,label:'我的游戏'}];
  const active=(url)=>url==='/'?(route==='/'||route.startsWith('/games/')):route.startsWith(url);
  async function logout(){try{await post('/auth/logout');await refreshMe();navigate('/');toast('已退出登录')}catch(e){toast(e.message,'error')}}
  return <div className="app-shell">
    <aside className={'sidebar '+(menu?'open':'')}><button className="brand" onClick={()=>{navigate('/');setMenu(false)}}><span className="brand-mark">H</span><span>{config.site.site_name}<small>HAOKE PLAY</small></span></button><div className="nav-label">探索你的下一场乐趣</div><nav>{nav.map(({url,icon:Icon,label})=><button key={url} className={'nav-item '+(active(url)?'active':'')} onClick={()=>{navigate(url);setMenu(false)}}><Icon size={21}/><span>{label}</span>{active(url)&&<span className="nav-dot"/>}</button>)}</nav><div className="side-divider"/><button className="nav-item" onClick={()=>{navigate('/community');setMenu(false)}}><Smile size={21}/><span>官方QQ群</span><ArrowUpRight size={15}/></button>{user?.role==='admin'&&<button className={'nav-item '+(route.startsWith('/admin')?'active':'')} onClick={()=>{navigate('/admin');setMenu(false)}}><Settings2 size={21}/><span>管理后台</span></button>}
      <div className="sidebar-bottom"><div className="side-hello"><Emote id="hello" size={100}/><span>有空，一起玩！</span></div><div className="local-indicator"><span/> {config.local_preview?'本地预览版':'服务已连接'}</div><small>为每一个好玩的想法，留个位置。</small></div>
    </aside>
    {menu&&<button className="menu-scrim" aria-label="关闭导航" onClick={()=>setMenu(false)}/>}
    <div className="main-shell"><header className="topbar"><div className="mobile-brand"><button className="icon-btn" onClick={()=>setMenu(x=>!x)} aria-label="打开导航"><Menu/></button><span className="brand-mark mini">H</span></div><span className="topbar-note"><span className="tiny-star">✦</span> 好玩，在这里相遇。</span><div className="topbar-right"><span className="local-pill"><span/>{config.local_preview?'本地预览':'欢迎回来'}</span>{user?<><button className="user-button" onClick={()=>navigate('/me')}><Emote index={user.avatar} size={36}/><span>{user.nickname}</span></button><button className="icon-btn logout" onClick={logout} aria-label="退出登录"><LogOut size={18}/></button></>:<Button variant="light" onClick={()=>navigate('/login?next='+encodeURIComponent(route))}>登录 / 注册 <ArrowUpRight size={16}/></Button>}</div></header>
    <main id="main">{children}</main><footer><span>© {config.site.site_name}</span><span>账号共用 · 乐趣各不相同</span><button onClick={()=>navigate('/community')}>QQ群 {config.site.qq_group}</button></footer></div>
    <nav className="mobile-nav">{nav.map(({url,icon:Icon,label})=><button key={url} className={active(url)?'active':''} onClick={()=>navigate(url)}><Icon size={20}/><span>{label}</span></button>)}</nav>
  </div>
}
function HeroArt({small=false}){
  return <div className={'hero-art '+(small?'small':'')} aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><span className="orbit-point point-one"/><span className="orbit-point point-two"/><span className="art-cross cross-one">+</span><span className="art-cross cross-two">+</span><div className="liquid-shadow"/><Emote id="ready" size={small?210:310} className="hero-mascot"/><div className="art-badge badge-flow"><span className="little-dot"/> 每一滴，都有无限可能</div><div className="art-badge badge-player"><Users size={17}/> 6 队混战 · 空位补电脑</div><div className="art-floating"><Emote id="hello" size={90}/></div><div className="art-coordinate">LIQUID WARS / 01</div></div>
}
function Home(){
  const {games,navigate,config}=useApp();const [search,setSearch]=useState('');
  const filtered=games.filter(g=>(g.title+g.tagline+g.genre+(g.id==='liquid-wars'?' Liquid Wars':'')).toLowerCase().includes(search.toLowerCase()));
  return <div className="page home-page"><div className="page-top"><div><span className="eyebrow">YOUR NEXT ADVENTURE</span><h1>游戏广场<span className="heading-dot">.</span></h1></div><div className="search-box"><Search size={18}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="找找你喜欢的游戏" aria-label="搜索游戏"/>{search&&<button onClick={()=>setSearch('')} aria-label="清除搜索"><X size={16}/></button>}</div></div>
    {!search&&<section className="hero"><div className="hero-copy"><span className="hero-kicker"><span/> 欢迎来到浩科</span><h2>好玩的世界，<br/>从这里<span>开始。</span></h2><p>{config.site.tagline}<br/>发现独立游戏，找到一起玩的伙伴。</p><div className="hero-actions"><Button onClick={()=>document.getElementById('games-list')?.scrollIntoView({behavior:'smooth'})}>发现游戏 <ArrowRight size={18}/></Button><button className="text-button" onClick={()=>navigate('/me')}>我的游戏账号 <ArrowUpRight size={17}/></button></div><div className="hero-foot"><Globe2 size={15}/><span>手机、平板、电脑，轻松访问</span></div></div><HeroArt/></section>}
    <section id="games-list" className="section"><div className="section-heading"><div><span className="eyebrow">PICK YOUR WORLD</span><h2>{search?'搜索结果':'从这一款开始'}</h2></div><span className="count-label">{filtered.length} 款游戏</span></div>
      <div className="discovery-grid"><div className="game-list">{filtered.length?filtered.map(g=><GameCard key={g.id} game={g}/>):<Empty icon={Search} title="没有找到匹配的游戏">换个关键词试试看。</Empty>}</div><aside className="community-teaser"><div className="mini-label"><Sparkles size={16}/> 一起玩，更有意思</div><div className="emote-trio"><Emote id="great" size={85}/><Emote id="haha" size={94}/><Emote id="thanks" size={85}/></div><h3>不用打字，<br/>一个表情就懂了。</h3><p>16款液滴表情，传递默契。<br/>为游戏内交流准备的液滴表情。</p><button className="text-button" onClick={()=>navigate('/community')}>看看液滴表情 <ArrowRight size={17}/></button></aside></div>
    </section>
    <section className="announcement"><span className="announcement-icon"><Radio size={18}/></span><div><strong>平台动态</strong><p>{config.site.announcement}</p></div><Tag>{config.local_preview?'本地预览':'平台公告'}</Tag></section>
    <section id="community"><QQCard/></section>
  </div>
}
function GameCard({game}){
  const {navigate}=useApp();
  return <article className="game-card"><button className={'game-cover '+(game.id==='liquid-wars'?'':'generic-cover')} onClick={()=>navigate('/games/'+game.id)} aria-label={'查看'+game.title}><div className="cover-grid"/><div className="cover-title">{game.id==='liquid-wars'?<>LIQUID<br/><span>WARS</span></>:game.title}</div>{game.id==='liquid-wars'?<Emote id="roger" size={190} className="cover-emote"/>:game.id==='mines3d'?<img className="generic-art" src="/mines3d-icon.png" width="150" height="150" alt="立体矿井与金色旗帜"/>:<Gamepad2 className="generic-art" size={110}/>}<span className="cover-caption">{game.id==='liquid-wars'?'流动 · 吞噬 · 包围':game.id==='mines3d'?'向下探索 · 携手撤离':'新的游戏世界'}</span><span className="cover-number">01 / PLAY</span></button><div className="game-card-body"><div className="game-meta"><Tag tone="green">{game.genre}</Tag><span>{game.id==='mines3d'?'2–6 人联机':'最多 '+game.max_players+' 人联机'}</span></div><h3>{game.title}{game.id==='liquid-wars'&&<small>Liquid Wars OS</small>}</h3><p>{game.tagline}</p><div className="game-card-bottom"><span className="status-note"><span/> {game.id==='mines3d'?(game.releases?.some(r=>r.version==='1.7.1-haoke.1')?'Android 正式版 · 2–6 人联机':'Android 公网联机测试版'):game.id==='liquid-wars'?'Android 公网联机测试版':'对战接入准备中'}</span><Button variant="secondary" onClick={()=>navigate('/games/'+game.id)}>探索游戏 <ArrowUpRight size={17}/></Button></div></div></article>
}
function Login(){
  const {navigate,route,refreshMe,config,user,toast}=useApp();
  const params=new URLSearchParams(route.split('?')[1]||'');
  const next=params.get('next')||'/me',reset=['reset','recovery'].includes(params.get('mode'));
  const [mode,setMode]=useState('code'),[email,setEmail]=useState(user?.email||''),[code,setCode]=useState(''),[password,setPassword]=useState(''),[repeat,setRepeat]=useState(''),[challenge,setChallenge]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[seconds,setSeconds]=useState(0);
  useEffect(()=>{setChallenge(null);setCode('');setPassword('');setRepeat('');setError('')},[reset,mode]);
  useEffect(()=>{if(user&&!reset)navigate(next,true)},[]);
  useEffect(()=>{if(!seconds)return;const timer=setTimeout(()=>setSeconds(x=>x-1),1000);return()=>clearTimeout(timer)},[seconds]);
  async function requestCode(e){e?.preventDefault();if(busy)return;setBusy(true);setError('');try{const result=await post('/auth/code',{email,purpose:reset?'password':'signin'});setChallenge(result);setSeconds(result.retry_after);setCode('');toast(result.delivery==='development'?'验证码已写入本地开发收件箱':'验证码已发送到邮箱')}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function submit(e){e.preventDefault();if(busy)return;if(reset&&password!==repeat){setError('两次输入的密码不一致');return}setBusy(true);setError('');try{const result=await post(reset?'/auth/password/reset':mode==='password'?'/auth/password/login':'/auth/verify',reset?{challenge_id:challenge.challenge_id,code,password,client:'web'}:mode==='password'?{email,password,client:'web'}:{challenge_id:challenge.challenge_id,code,client:'web'});setCSRF(result.csrf);setPassword('');setRepeat('');await refreshMe();toast(reset?'密码已保存，其他设备已退出':result.is_new?'注册成功，欢迎来到浩科':'登录成功');navigate(next.startsWith('/login')?'/me':next,true)}catch(e){setError(e.message)}finally{setBusy(false)}}
  const passwordMode=!reset&&mode==='password';
  return <div className="page auth-page"><button className="back-link" onClick={()=>navigate('/')}><ArrowLeft size={17}/> 回到游戏广场</button><div className="auth-layout"><div className="auth-story"><span className="eyebrow">ONE ACCOUNT. MANY WORLDS.</span><h1>下一场乐趣，<br/>等你<span>加入。</span></h1><HeroArt small/><div className="auth-benefits"><span><ShieldCheck size={17}/> 邮箱验证，安心登录</span><span><Layers3 size={17}/> 一个账号，多个游戏</span></div></div><section className="auth-form"><div className="auth-icon"><Mail size={27}/></div><span className="eyebrow">WELCOME TO HAOKE</span><h2>{reset?'设置 / 重置密码':'登录 / 注册'}</h2><p className="muted">{reset?'先验证邮箱，再设置新密码。保存后，其他设备需要重新登录。':'验证码登录可自动注册，已有密码也可以直接登录。'}</p>{!reset&&<div className="auth-methods" role="group" aria-label="登录方式"><button type="button" aria-pressed={mode==='code'} disabled={busy} onClick={()=>setMode('code')}>验证码登录</button><button type="button" aria-pressed={mode==='password'} disabled={busy} onClick={()=>setMode('password')}>密码登录</button></div>}<ErrorBox message={error}/><form onSubmit={passwordMode||challenge?submit:requestCode}><label>邮箱地址<input type="email" required maxLength={254} autoComplete="email" placeholder="you@example.com" value={email} disabled={!!challenge||busy} onChange={e=>setEmail(e.target.value)}/></label>{challenge&&<label>邮箱验证码<input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required placeholder="输入6位验证码" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} autoFocus/></label>}{(passwordMode||(reset&&challenge))&&<label>{reset?'新密码':'密码'}<input type="password" required minLength={reset?10:1} maxLength={128} autoComplete={reset?'new-password':'current-password'} placeholder={reset?'10–128个字符，可使用一句容易记住的话':'输入你的密码'} value={password} onChange={e=>setPassword(e.target.value)}/></label>}{reset&&challenge&&<label>再次输入新密码<input type="password" required minLength={10} maxLength={128} autoComplete="new-password" value={repeat} onChange={e=>setRepeat(e.target.value)}/></label>}<Button className="full" type="submit" busy={busy}>{passwordMode?'密码登录':challenge?(reset?'保存密码并登录':'验证并继续'):'获取邮箱验证码'} <ArrowRight size={17}/></Button></form>{challenge&&<div className="form-links"><button disabled={seconds>0||busy} onClick={requestCode}>{seconds>0?seconds+'秒后可重发':'重新发送'}</button><button disabled={busy} onClick={()=>{setChallenge(null);setCode('');setError('')}}>更换邮箱</button></div>}{challenge?.dev_mailbox_available&&<DevCode challengeId={challenge.challenge_id}/>}<div className="auth-foot"><LockKeyhole size={14}/><span>{reset?'网站与所有接入游戏使用同一密码。':'验证码10分钟内有效，也可选择密码登录。'}</span></div><button disabled={busy} className="text-button small-text" onClick={()=>navigate(reset?'/login':'/login?mode=reset')}>{reset?'返回注册登录':'设置密码 / 忘记密码？'}</button>{config.dev_mailbox_available&&<details className="dev-hint"><summary>本地开发说明</summary><p>当前不会发送真实邮件。获取验证码后可打开开发收件箱。管理员邮箱：<code>{config.admin_hint}</code>。正式部署会关闭此入口。</p></details>}</section></div></div>
}
function DevCode({challengeId}){
  const [shown,setShown]=useState(false),[value,setValue]=useState(null),[error,setError]=useState('');
  async function read(){setShown(true);try{setValue(await api('/dev/mailbox?challenge_id='+encodeURIComponent(challengeId)))}catch(e){setError(e.message)}}
  return <div className="dev-mail"><div><Inbox size={18}/><strong>本地开发收件箱</strong><Tag>未发送真实邮件</Tag></div>{shown?<><ErrorBox message={error}/>{value&&<p>本次验证码 <code className="otp">{value.code}</code><small>仅本机开发环境可见</small></p>}</>:<button className="text-button" type="button" onClick={read}>查看本次验证码 <ArrowUpRight size={16}/></button>}</div>
}
function DevMailbox(){
  let saved;try{saved=JSON.parse(sessionStorage.getItem('hk_challenge')||'null')}catch{}
  return <div className="page narrow"><h1>本地开发收件箱</h1>{saved?<DevCode challengeId={saved.challenge_id}/>:<Empty icon={Inbox} title="没有待验证的邮件">请先在登录页面获取验证码。</Empty>}</div>
}
function GameDetail({gameId}){
  const {data,error,loading,reload}=useData('/games/'+gameId);
  const {navigate}=useApp();
  if(loading)return <Loading/>;
  if(error)return <div className="page"><ErrorBox message={error} retry={reload}/></div>;
  const game=data.game;
  return <div className="page"><button className="back-link" onClick={()=>navigate('/')}><ArrowLeft size={17}/> 游戏广场</button>
    <section className="detail-hero"><div><span className="eyebrow">{game.id==='liquid-wars'?'LIQUID WARS OS':game.id==='mines3d'?'MINES 3D · DEEP SECTOR':'HAOKE GAMES'}</span><h1>{game.title}<span className="heading-dot">.</span></h1><h2>{game.tagline}</h2><p>{game.description}</p><div className="tag-row"><Tag tone="green">{game.genre}</Tag><Tag>{game.id==='mines3d'?'2–6 人联机':'最多 '+game.max_players+' 人联机'}</Tag><Tag>统一平台账号</Tag></div><div className="hero-actions"><Button onClick={()=>document.getElementById('downloads')?.scrollIntoView({behavior:'smooth'})}><Download size={18}/> 查看下载与平台</Button><ShareButton path={'/games/'+game.id} title={game.title}/></div><small className="muted">{game.id==='liquid-wars'?'游戏内邮箱登录、好友房、匹配和表情交流；匹配8秒后空位补电脑，单人也能开局。':game.id==='mines3d'?'2人即可准备开局，不补电脑。使用平台账号，在游戏内创建房间、匹配或观战。':'客户端接入状态与版本以本页下载信息为准。'}</small></div>{game.id==='liquid-wars'?<HeroArt small/>:game.id==='mines3d'?<img className="mines-detail-art" src="/mines3d-icon.png" width="260" height="260" alt="三维扫雷矿井图标"/>:<Gamepad2 size={170}/>}</section>
    <div className="detail-columns"><div><section className="panel"><div className="panel-heading"><Gamepad2 size={21}/><h2>关于这场冒险</h2></div><p>{game.description}</p>{game.id==='mines3d'&&<div className="feature-list">
      <div><span>01</span><div><h3>一起撤离，也能猎雷对决</h3><p>合作模式共享矿井，三格安全值、两次扫描，倒地后可由队友救援。猎雷模式每回合15秒，开格或确认一颗雷；错判淘汰，先得3分或成为最后存活者获胜。</p></div></div>
      <div><span>02</span><div><h3>每一次下矿都有新目标</h3><p>团队无猜解谜、四种断层布局、北京时间每日同图、2–6人同图竞速，以及六人专属3v3撤离。侦察员和救援员提供有限工具，任意职业组合都能玩。</p></div></div>
      <div><span>03</span><div><h3>真正可操作的立体矿井</h3><p>单指旋转、双指缩放和平移，切换当前层准确点选。提示统计同层上下左右与紧邻上下层，最多6格。原有单机模式继续保留；联机切后台时全队对局仍会推进。</p></div></div>
    </div>}{game.id==='liquid-wars'&&<div className="feature-list"><div><span>01</span><div><h3>指挥流动的军团</h3><p>液体粒子聚集、分散，在接触与包围中展开争夺。Android 版支持长按拖动跟随、松手保持目标。</p></div></div><div><span>02</span><div><h3>打开游戏，和伙伴一起玩</h3><p>在游戏内完成邮箱登录、好友房和匹配。最多6名真人，不足的空位由电脑补齐6队。网站负责介绍、下载与分享邀请。</p></div></div><div><span>03</span><div><h3>一个账号，连接更多游戏</h3><p>以后进入其他作品，可使用同一个平台账号；各款游戏独立保存自己的资料。</p></div></div></div>}</section>
    <section className="panel"><div className="panel-heading"><History size={20}/><h2>版本动态</h2></div>{game.releases.length?game.releases.map(r=><div key={r.id} className="release-note"><Tag>{r.platform} · {r.version}</Tag><p>{r.notes||'暂无更新说明'}</p><small>{fmtDate(r.created_at)}</small></div>):<p className="muted">网站尚未登记可下载版本。可先注册统一账号，或加入QQ群关注更新。</p>}</section></div>
    <aside><section id="downloads" className="panel"><h2>选择你的平台</h2><p className="muted small-text">网页支持多种设备，游戏客户端分别提供。</p><div className="platform-list">{[['android','Android',Smartphone],['ios','iPhone / iPad',Smartphone],['windows','Windows',Monitor],['macos','macOS',Monitor]].map(([key,label,Icon])=>{const r=game.releases.find(x=>x.platform===key);return <div key={key}><Icon size={21}/><span>{label}<small>{r?'版本 '+r.version:game.id==='liquid-wars'&&key==='android'?'已有本地试玩版，下载入口待登记':'客户端暂未提供'}</small></span>{r?<a className="icon-btn" href={r.url} target="_blank" rel="noopener noreferrer" aria-label={'下载'+label}><Download size={18}/></a>:<Tag>待提供</Tag>}</div>})}</div>{game.id==='mines3d'&&<p className="small-text"><a href="https://github.com/zh1414319052-lgtm/mines3d-haoke" target="_blank" rel="noopener noreferrer">对应源码与可编辑素材 · GPL-3.0-only</a><br/>正式版与 QA 分开安装；使用原平台账号登录。</p>}{game.id==='liquid-wars'&&game.releases.filter(r=>/^1\.(84|85)-QA$/.test(r.version)).slice(0,1).map(r=><p className="small-text" key={r.id}><a href={'/downloads/liquidwars-'+r.version.replace('-QA','')+'-source.zip'}>{r.version} 对应源码 · GPL-3.0-or-later</a></p>)}</section><QQCard compact/></aside></div></div>;
}
function PlayInGame(){
  const {navigate,route,games}=useApp();
  const id=new URLSearchParams(route.split('?')[1]||'').get('game')||'liquid-wars';
  const game=games.find(g=>g.id===id);
  return <div className="page narrow"><section className="panel"><Empty icon={Gamepad2} title="组队与匹配，在游戏里进行" action={<Button onClick={()=>navigate(game?'/games/'+game.id:'/')}><Download size={17}/>查看游戏与下载</Button>}>使用同一个平台账号进入游戏，再创建房间、邀请朋友或开始匹配。<br/>请下载 Android 联网测试版；其他平台客户端尚未提供。</Empty></section><QQCard compact/></div>;
}
function Invitation({code}){
  const {route,navigate,config}=useApp();
  const gid=new URLSearchParams(route.split('?')[1]||'').get('game');
  const {data,error,loading,reload}=useData('/invitations/'+encodeURIComponent(code)+(gid?'?game_id='+encodeURIComponent(gid):''));
  return <div className="page narrow"><button className="back-link" onClick={()=>navigate('/')}><ArrowLeft size={17}/> 游戏广场</button><section className="panel invitation-page"><Emote id="hello" size={140}/><span className="eyebrow">AN INVITATION TO PLAY</span><h1>一起玩，等你加入。</h1>{loading?<Loading/>:error?<><ErrorBox message={error} retry={reload}/><p className="muted">请朋友从游戏内重新分享有效邀请。</p></>:data&&<><h2>{data.game_title}</h2><p>{data.member_count} / {data.max_players} 人 · {data.status==='playing'?'对局进行中，可进入游戏观战':data.status==='finished'?'本局已结束，可进入游戏等待下一局':data.full?'当前房间已满':'等待伙伴加入'}</p><div className="room-code"><span>房间码</span><b>{data.code}</b><CopyButton value={data.code} label="复制房间码"/></div><p className="muted">请在对应游戏内登录账号并输入房间码。{data.game_id==='mines3d'?'等待中的房间可加入；已开局可选择观战。':'使用 Android 联网测试版的好友房间入口加入。'}查看此页面不会占用席位。</p><Button onClick={()=>navigate('/games/'+data.game_id)}><Download size={17}/>查看游戏与下载</Button>{config.local_preview&&<p className="small-text muted">本机验证链接，不能作为公网邀请使用。</p>}</>}</section><QQCard compact/></div>;
}
function Community(){
  const {config}=useApp();const [selected,setSelected]=useState(null);
  return <div className="page"><div className="page-top"><div><span className="eyebrow">BETTER TOGETHER</span><h1>玩家社区<span className="heading-dot">.</span></h1><p className="muted">聊游戏、提建议，找到一起玩的伙伴。</p></div></div><QQCard/>
    <section className="section"><div className="section-heading"><div><h2>一个表情，就懂了。</h2><p className="muted small-text">为游戏内交流准备的液滴表情 · 点击预览</p></div><Tag>{config.emotes.length} 款</Tag></div><div className="community-emotes">{config.emotes.map(e=><button key={e.id} className={selected?.id===e.id?'selected':''} onClick={()=>setSelected(e)} aria-label={'预览表情：'+e.label}><Emote id={e.id} size={100} label={e.label}/><span>{e.label}</span></button>)}</div><p className="muted small-text" aria-live="polite">{selected?'正在预览「'+selected.label+'」，没有向其他玩家发送消息。':'站内仅展示官方表情，不开放文字聊天、语音或图片上传。'}</p></section></div>;
}
function IntegrationLab(){
  const {user,route,navigate,config}=useApp();
  const check=useData('/admin/integration-lab');
  if(!user)return <div className="page"><Empty icon={LockKeyhole} title="接入验证需要管理员账号" action={<Button onClick={()=>navigate('/login?next='+encodeURIComponent(route))}>管理员登录</Button>}>玩家请在游戏内创建房间和匹配。</Empty></div>;
  if(check.loading)return <Loading/>;
  if(check.error||!config.local_preview)return <div className="page"><ErrorBox message={check.error||'本入口只用于本地开发验证'}/></div>;
  const code=route.split('?')[0].split('/')[4];
  return <><div className="lab-banner"><Tag>管理员接入验证</Tag><span>用于测试客户端 API、席位与表情；不是玩家大厅，也不会开始真实对战。</span><button onClick={()=>navigate('/admin/rooms')}>返回房间管理</button></div>{code?<Room key={code} code={code}/>:<Lobby/>}</>;
}
function Lobby(){
  const {navigate,route,games,user,requireLogin,toast,refreshMe}=useApp();
  const gameId=new URLSearchParams(route.split('?')[1]||'').get('game')||'liquid-wars';
  const {data,error,loading,reload}=useData('/rooms?game_id='+encodeURIComponent(gameId));
  const [code,setCode]=useState(''),[busy,setBusy]=useState(false);
  useEffect(()=>{const timer=setInterval(reload,12000);return()=>clearInterval(timer)},[gameId]);
  async function create(){if(!requireLogin('/admin/lab/rooms?game='+gameId))return;setBusy(true);try{const d=await post('/rooms',{game_id:gameId});await refreshMe();navigate('/admin/lab/rooms/'+d.room.code+'?game='+gameId)}catch(e){toast(e.message,'error')}finally{setBusy(false)}}
  function join(e){e.preventDefault();navigate('/admin/lab/rooms/'+code.trim().toUpperCase()+'?game='+gameId)}
  return <div className="page"><div className="page-top"><div><span className="eyebrow">BETTER TOGETHER</span><h1>房间接入验证<span className="heading-dot">.</span></h1><p className="muted">本地验证创建、加入、准备、掉线恢复和官方表情接口。</p></div><Button onClick={create} busy={busy}><Plus size={18}/> 创建验证房间</Button></div><div className="room-toolbar"><label className="inline-label"><Gamepad2 size={18}/><select aria-label="选择游戏" value={gameId} onChange={e=>navigate('/admin/lab/rooms?game='+e.target.value)}>{games.map(g=><option key={g.id} value={g.id}>{g.title}</option>)}</select></label><form className="join-form" onSubmit={join}><input placeholder="输入6位房间码" aria-label="房间码" value={code} onChange={e=>setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g,''))} maxLength={6} minLength={6} required/><Button type="submit" variant="secondary">加入 <ArrowRight size={16}/></Button></form><button className="icon-btn" onClick={reload} aria-label="刷新房间"><RefreshCw size={19}/></button></div>
    <div className="inline-notice"><Radio size={17}/><span>房间与表情可用 · 真实游戏客户端尚未接入</span></div><ErrorBox message={error} retry={reload}/>{loading&&!data?<Loading/>:data?.rooms.length?<div className="room-grid">{data.rooms.map(r=><article className="room-card" key={r.id}><div className="room-card-head"><span className="room-symbol"><Users size={24}/></span><Tag tone={r.member_count>=r.max_players?'':'green'}>{r.member_count>=r.max_players?'已满员':'等待加入'}</Tag></div><h3>{r.host_name} 的房间</h3><p>{r.game_title}</p><div className="room-dots">{Array.from({length:r.max_players},(_,i)=><span key={i} className={i<r.member_count?'filled':''}/>)}</div><div className="room-card-bottom"><span><b>{r.member_count}</b> / {r.max_players} 人<small>{r.code}</small></span><Button variant="secondary" onClick={()=>navigate('/admin/lab/rooms/'+r.code+'?game='+r.game_id)}>查看房间 <ArrowUpRight size={16}/></Button></div></article>)}</div>:!error&&<div className="panel"><Empty icon={Users} title="第一间房，等你来开">这里还没有等待中的房间。创建一个，再邀请朋友加入。<br/>每间房最多6人，刷新页面不会重复占位。</Empty></div>}<div className="room-guide"><div><span>01</span><h3>创建或加入</h3><p>分享房间码，快速找到彼此。</p></div><div><span>02</span><h3>用表情打招呼</h3><p>没有文字聊天，交流也很轻松。</p></div><div><span>03</span><h3>准备好下一局</h3><p>战斗客户端接入后，再一起出发。</p></div></div><QQCard compact/></div>
}
function Room({code}){
  const {user,me,route,navigate,requireLogin,refreshMe,toast,config}=useApp();
  const [state,setState]=useState(null),[messages,setMessages]=useState([]),[error,setError]=useState(''),[busy,setBusy]=useState(false),[connection,setConnection]=useState('connecting'),[cooldown,setCooldown]=useState(0),[mutes,setMutes]=useState(me?.mutes||[]),[confirmLeave,setConfirmLeave]=useState(false);
  const stateRef=useRef(null),socketRef=useRef(null),alive=useRef(true);
  const expectedGame=new URLSearchParams(route.split('?')[1]||'').get('game');
  async function load(){const d=await api('/rooms/'+code);stateRef.current=d;setState(d);setMessages(d.messages);return d}
  useEffect(()=>{if(!user){requireLogin(route);return}alive.current=true;load().catch(e=>setError(e.message));return()=>{alive.current=false}},[code,user?.id]);
  const isMember=state?.is_member&&state?.room.status==='waiting';
  useEffect(()=>{
    if(!isMember||!user)return;
    let cancelled=false,retryTimer,pingTimer;let attempts=0;
    async function connect(){
      if(cancelled)return;
      setConnection('connecting');
      try{
        const {ticket}=await post('/realtime-ticket');
        if(cancelled)return;
        const ws=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws?ticket='+encodeURIComponent(ticket));socketRef.current=ws;
        ws.onopen=()=>{attempts=0;setConnection('connected');load().catch(()=>{});pingTimer=setInterval(()=>{if(ws.readyState===1)ws.send(JSON.stringify({type:'ping'}))},20000)};
        ws.onmessage=(event)=>{
          const data=JSON.parse(event.data);
          if(data.type==='room'&&data.room.code===code){
            const member=data.room.members.some(m=>m.user_id===user.id);
            setState(prev=>({...prev,room:data.room,is_member:member}));
            if(!member)refreshMe().catch(()=>{});
          }
          if(data.type==='emote'&&data.message.room_id===stateRef.current?.room.id)setMessages(prev=>[...prev.filter(m=>m.id!==data.message.id),data.message].slice(-30));
        };
        ws.onclose=(event)=>{clearInterval(pingTimer);if(cancelled)return;setConnection('disconnected');if(event.code===4001){setError('登录已失效，请重新登录');refreshMe().catch(()=>{});return}retryTimer=setTimeout(connect,Math.min(15000,1000*2**attempts++))};
        ws.onerror=()=>{setConnection('disconnected')};
      }catch(e){if(!cancelled){setConnection('disconnected');retryTimer=setTimeout(connect,5000)}}
    }
    connect();
    const poll=setInterval(()=>{post('/rooms/'+code+'/heartbeat').then(load).catch(e=>{if(e.status===401||e.status===403||e.status===410)setError(e.message)})},25000);
    return()=>{cancelled=true;clearTimeout(retryTimer);clearInterval(pingTimer);clearInterval(poll);socketRef.current?.close()};
  },[isMember,user?.id,code]);
  useEffect(()=>{if(!cooldown)return;const t=setTimeout(()=>setCooldown(x=>x-1),1000);return()=>clearTimeout(t)},[cooldown]);
  useEffect(()=>{const t=setInterval(()=>setMessages(ms=>ms.filter(m=>Date.now()/1000-m.created_at<60)),5000);return()=>clearInterval(t)},[]);
  async function action(path,body={},after){setBusy(true);setError('');try{const result=await post('/rooms/'+code+path,body);await load();await refreshMe();after?.(result)}catch(e){setError(e.message)}finally{setBusy(false)}}
  async function send(id){if(cooldown||busy)return;setCooldown(3);try{const d=await post('/rooms/'+code+'/emotes',{emote_id:id});setMessages(ms=>[...ms.filter(m=>m.id!==d.message.id),d.message].slice(-30))}catch(e){toast(e.message,'error')}}
  async function mute(uid){const muted=!mutes.includes(uid);try{await api('/me/mutes/'+uid,{method:'PUT',body:{muted}});setMutes(prev=>muted?[...prev,uid]:prev.filter(x=>x!==uid));toast(muted?'已屏蔽该玩家表情':'已恢复该玩家表情')}catch(e){toast(e.message,'error')}}
  if(!user)return <Loading/>;
  if(!state)return <div className="page"><button className="back-link" onClick={()=>navigate('/admin/lab/rooms')}><ArrowLeft size={17}/> 房间接入验证</button>{error?<ErrorBox message={error} retry={()=>{setError('');load().catch(e=>setError(e.message))}}/>:<Loading/>}</div>;
  const r=state.room,self=r.members.find(m=>m.user_id===user.id);
  return <div className="page"><button className="back-link" onClick={()=>navigate('/admin/lab/rooms?game='+r.game_id)}><ArrowLeft size={17}/> 房间接入验证</button><div className="page-top"><div><span className="eyebrow">YOUR SQUAD, YOUR MOMENT</span><h1>{r.game_title} <span className="room-title-small">房间</span></h1><div className="room-code"><span>房间码</span><b>{r.code}</b><CopyButton value={r.code} label="复制"/></div></div><div className="button-row"><ShareButton path={'/invite/'+r.code+'?game='+r.game_id} title={r.game_title+'房间邀请'}/>{state.is_member&&<Button variant="quiet" onClick={()=>setConfirmLeave(true)}><DoorOpen size={17}/>退出房间</Button>}</div></div><ErrorBox message={error}/>{r.status!=='waiting'?<div className="panel"><Empty icon={DoorOpen} title="这个房间已关闭" action={<Button onClick={()=>navigate('/admin/lab/rooms?game='+r.game_id)}>返回大厅</Button>}>房间无人、超过有效期或被管理员关闭。可以创建新房间继续相聚。</Empty></div>:!state.is_member?<div className="join-invitation panel"><Emote id="hello" size={150}/><h2>伙伴的邀请，已送达。</h2><p>{r.members.length} / {r.max_players} 人 · {r.game_title}</p><Button busy={busy} disabled={r.members.length>=r.max_players} onClick={()=>action('/join',{game_id:expectedGame||r.game_id})}>{r.members.length>=r.max_players?'房间已满':'加入这个房间'} <ArrowRight size={18}/></Button></div>:<>
    <div className="room-status-bar"><span className={'connection '+connection}><span/>{connection==='connected'?'实时连接正常':connection==='connecting'?'正在连接…':'连接中断，正在重连…'}</span><span>掉线保留席位90秒 · 房主离开自动转移</span></div>
    <div className="player-grid">{Array.from({length:r.max_players},(_,index)=>{const member=r.members[index];const message=member&&!mutes.includes(member.user_id)&&[...messages].reverse().find(m=>m.user_id===member.user_id&&Date.now()/1000-m.created_at<15);return member?<article key={member.user_id} className={'player-slot '+(member.user_id===user.id?'self':'')}><div className="player-slot-top">{r.host_id===member.user_id?<Tag tone="gold"><Crown size={13}/> 房主</Tag>:<span className="slot-number">0{index+1}</span>}{member.user_id!==user.id&&<button className="icon-btn" aria-label={mutes.includes(member.user_id)?'恢复表情':'屏蔽表情'} onClick={()=>mute(member.user_id)}>{mutes.includes(member.user_id)?<VolumeX size={16}/>:<Volume2 size={16}/>}</button>}</div><div className="player-art"><Emote index={member.avatar} size={108}/>{message&&<div className="emote-bubble" key={message.id}><Emote id={message.emote_id} size={72}/></div>}</div><h3>{member.nickname}{member.user_id===user.id&&<small>你</small>}</h3><span className={'player-ready '+(member.ready?'ready':'')}>{member.ready?<CheckCircle2 size={14}/>:<Clock3 size={14}/>} {member.ready?'已准备':member.online?'等待准备':'重连中'}</span></article>:<div key={'empty'+index} className="player-slot unfilled"><span className="slot-number">0{index+1}</span><span className="empty-player"><Plus size={27}/></span><p>等待小伙伴</p><small>分享房间码邀请加入</small></div>})}</div>
    <div className="ready-bar"><div><strong>{r.members.filter(m=>m.ready).length} / {r.members.length} 人已准备</strong><p>真实对战待客户端接入，当前可体验组队和表情。</p></div><div className="button-row"><Button variant={self?.ready?'secondary':'primary'} busy={busy} onClick={()=>action('/ready',{ready:!self?.ready})}><Check size={18}/>{self?.ready?'取消准备':'我准备好了'}</Button>{r.host_id===user.id&&<Button variant="secondary" busy={busy} onClick={()=>action('/start')}>检查开局条件 <Play size={16}/></Button>}</div></div>
    <section className="emote-panel panel"><div className="section-heading"><div><h2><Smile size={20}/> 用表情，说你想说的</h2><p className="muted small-text">点击即发送 · 不开放文字、图片上传或语音</p></div><Tag>{cooldown?cooldown+'秒后可发送':'每3秒可发送一次'}</Tag></div><div className="emote-picker">{config.emotes.map(e=><button key={e.id} disabled={cooldown>0} onClick={()=>send(e.id)} title={e.label}><Emote id={e.id} size={64} label={e.label}/><span>{e.label}</span></button>)}</div><div className="recent-emotes" aria-live="polite">{messages.filter(m=>!mutes.includes(m.user_id)&&Date.now()/1000-m.created_at<60).slice(-8).map(m=><div key={m.id}><span>{m.nickname}</span><Emote id={m.emote_id} size={38}/></div>)}</div></section>
    </>}{confirmLeave&&<Modal title="离开这个房间？" onClose={()=>setConfirmLeave(false)}><p className="muted">离开后会释放席位。你是房主时，房主身份会交给剩余成员。</p><div className="modal-actions"><Button variant="secondary" onClick={()=>setConfirmLeave(false)}>再等等</Button><Button onClick={()=>action('/leave',{},()=>navigate('/admin/lab/rooms?game='+r.game_id))} busy={busy}>离开房间</Button></div></Modal>}</div>
}
function MyGames(){
  const {user,me,navigate,refreshMe,toast}=useApp();const [nickname,setNickname]=useState(user?.nickname||''),[avatar,setAvatar]=useState(user?.avatar||0),[busy,setBusy]=useState(false),[confirm,setConfirm]=useState(false);
  useEffect(()=>{if(user){setNickname(user.nickname);setAvatar(user.avatar)}},[user?.id]);
  if(!user)return <div className="page"><Empty icon={Gamepad2} title="你的游戏旅程，从这里开始" action={<Button onClick={()=>navigate('/login?next=/me')}>登录 / 注册 <ArrowRight size={17}/></Button>}>一个邮箱账号，管理你在不同游戏中的资料。</Empty></div>;
  async function save(e){e.preventDefault();setBusy(true);try{await api('/me',{method:'PATCH',body:{nickname,avatar}});await refreshMe();toast('个人资料已保存')}catch(e){toast(e.message,'error')}finally{setBusy(false)}}
  async function revoke(){try{await post('/auth/revoke-sessions');await refreshMe();navigate('/login');toast('所有设备已退出，请重新登录')}catch(e){toast(e.message,'error')}}
  return <div className="page"><div className="page-top"><div><span className="eyebrow">YOUR LITTLE CORNER</span><h1>我的游戏<span className="heading-dot">.</span></h1><p className="muted">一个账号，记录不同的游戏旅程。</p></div>{user.role==='admin'&&<Button variant="secondary" onClick={()=>navigate('/admin')}><Settings2 size={18}/>管理后台</Button>}</div>
    <div className="profile-layout"><aside className="panel profile-card"><Emote index={avatar} size={118}/><h2>{user.nickname}</h2><p className="muted email-text">{user.email}</p><Tag tone="green"><ShieldCheck size={14}/> 邮箱已验证</Tag><form onSubmit={save}><label>昵称<input maxLength={20} minLength={1} required value={nickname} onChange={e=>setNickname(e.target.value)}/></label><fieldset><legend>选择液滴头像</legend><div className="avatar-picker">{[0,1,2,3,8,9,12,15].map(i=><button className={avatar===i?'selected':''} type="button" key={i} onClick={()=>setAvatar(i)} aria-label={'选择头像'+(i+1)} aria-pressed={avatar===i}><Emote index={i} size={48}/></button>)}</div></fieldset><Button type="submit" className="full" busy={busy}>保存资料</Button></form><button className="text-button" onClick={()=>navigate('/login?mode=reset&next=/me')}><LockKeyhole size={15}/>{user.has_password?'修改 / 重置密码':'设置登录密码'}</button><button className="text-button danger-text" onClick={()=>setConfirm(true)}><LogOut size={15}/>退出所有设备</button><small className="muted">账号创建于 {fmtDate(user.created_at)}</small></aside>
    <div><section className="panel"><div className="section-heading"><h2>我的游戏资料</h2><Tag>{me.profiles?.length||0} 款</Tag></div>{me.profiles?.length?me.profiles.map(p=><div className="my-game-row" key={p.game_id}><span className="my-game-icon"><Gamepad2 size={30}/></span><div><h3>{p.title}</h3><p>资料建立于 {fmtDate(p.first_entered)}</p></div><Button variant="secondary" onClick={()=>navigate('/games/'+p.game_id)}>查看游戏 <ArrowRight size={16}/></Button></div>):<Empty icon={Gamepad2} title="下一场冒险，还在前方" action={<Button variant="secondary" onClick={()=>navigate('/')}>发现游戏</Button>}>以后使用这个账号进入游戏，就能在这里查看对应资料。<br/>浏览介绍不会创建游戏记录。</Empty>}</section><section className="panel"><h2>进入游戏，再约上伙伴</h2><p className="muted">建房、匹配、准备和表情交流都在游戏内完成。网站为你保留统一账号，方便发现其他作品。</p><Button variant="secondary" onClick={()=>navigate('/')}>发现更多游戏 <ArrowRight size={16}/></Button></section><QQCard compact/></div></div>
    {confirm&&<Modal title="退出所有设备" onClose={()=>setConfirm(false)}><p className="muted">当前浏览器和其它设备的登录都会失效。你可以随时使用邮箱验证码重新登录。</p><div className="modal-actions"><Button variant="secondary" onClick={()=>setConfirm(false)}>取消</Button><Button onClick={revoke}>确认退出</Button></div></Modal>}</div>;
}
createRoot(document.getElementById('root')).render(<App/>);
