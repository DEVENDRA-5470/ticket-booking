import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, CalendarDays, CheckCircle2, ChevronRight, Clock3, Edit3, LogIn, LogOut, MapPin, Menu, Plus, Search, ShieldCheck, Ticket, Trash2, UserPlus, Users, X } from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function api(path, options = {}, token = null) {
  const headers = { ...(options.body ? {'Content-Type':'application/json'} : {}), ...(token ? {Authorization:'Bearer ' + token} : {}), ...(options.headers || {}) }
  const response = await fetch(API_BASE + path, {...options, headers})
  const text = await response.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!response.ok) { const error = new Error(data?.detail || data?.message || 'Request failed'); error.status = response.status; throw error }
  return data
}

function formatDate(value) {
  return value ? new Intl.DateTimeFormat('en-IN',{day:'2-digit',month:'short',year:'numeric'}).format(new Date(value)) : '—'
}
function formatTime(value) {
  return value ? new Intl.DateTimeFormat('en-IN',{hour:'2-digit',minute:'2-digit'}).format(new Date(value)) : '—'
}
function toInputDateTime(value) {
  if (!value) return ''
  const d = new Date(value), p = n => String(n).padStart(2,'0')
  return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())+'T'+p(d.getHours())+':'+p(d.getMinutes())
}
function toApiDateTime(value) { return new Date(value).toISOString() }

export default function App() {
  const [token,setToken] = useState(() => localStorage.getItem('ticketflow_token'))
  const [user,setUser] = useState(() => { try{return JSON.parse(localStorage.getItem('ticketflow_user'))||null}catch{return null} })
  const [authMode,setAuthMode] = useState(null), [mobile,setMobile] = useState(false)

  const logout = () => {
    localStorage.removeItem('ticketflow_token'); localStorage.removeItem('ticketflow_user')
    setToken(null); setUser(null)
  }
  const authenticated = data => {
    const u={user_id:data.user_id,email:data.email,name:data.name || data.email.split('@')[0]}
    localStorage.setItem('ticketflow_token',data.access_token); localStorage.setItem('ticketflow_user',JSON.stringify(u))
    setToken(data.access_token); setUser(u); setAuthMode(null)
  }

  return <div className="app">
    <header className="nav">
      <a className="brand" href="#top"><i><Ticket size={20}/></i>Ticket<span>Flow</span></a>
      <nav className={mobile?'links open':'links'}>
        <a href="#events" onClick={()=>setMobile(false)}>Events</a><a href="#how" onClick={()=>setMobile(false)}>How it works</a>
        {token && <a href="#manage" onClick={()=>setMobile(false)}>Manage</a>}
      </nav>
      <div className="actions">
        {token ? <><span className="user-chip">{user?.name || user?.email}</span><button className="login ghost" onClick={logout}><LogOut size={15}/> Logout</button></> :
          <><button className="login secondary" onClick={()=>setAuthMode('login')}>Sign in</button><button className="login" onClick={()=>setAuthMode('register')}>Get started</button></>}
        <button className="menu" onClick={()=>setMobile(!mobile)}>{mobile?<X/>:<Menu/>}</button>
      </div>
    </header>

    <main id="top">
      <section className="hero">
        <div className="heroText">
          <div className="eyebrow"><Ticket size={14}/> Production-ready ticketing workflow</div>
          <h1>Manage events.<br/><em>Book experiences.</em></h1>
          <p>TicketFlow connects authentication, event management and booking workflows through a protected API.</p>
          <div className="heroActions">{token ?
            <a className="primaryCta" href="#manage">Open Event Manager <ArrowRight size={16}/></a> :
            <><button className="primaryCta" onClick={()=>setAuthMode('register')}>Create account <UserPlus size={16}/></button><button className="secondaryCta" onClick={()=>setAuthMode('login')}>Sign in <LogIn size={16}/></button></>}
          </div>
          <div className="stats"><span><b>JWT</b> protected API</span><span><b>PostgreSQL</b> persistent events</span><span><ShieldCheck size={15}/> Authenticated actions</span></div>
        </div>
        <div className="heroCard"><div className="live"><i/> Live platform status</div><div className="ticketArt">
          <div className="ticketTop"><Ticket/><span>TICKETFLOW</span></div><div className="ticketMain"><small>EVENT MANAGEMENT</small><h3>Create. Update. Delete.</h3><p>One dedicated event workspace with real API operations.</p></div>
          <div className="ticketBottom"><span>AUTH</span><span>API</span><span>DB</span></div>
        </div><div className="availability"><span>● Backend connected</span><b>Secure</b></div></div>
      </section>

      {token ? <EventManager token={token} user={user} onUnauthorized={logout}/> : <PublicEvents onLogin={()=>setAuthMode('login')}/>}
      <section className="trust"><div><ShieldCheck/><b>Protected routes</b><span>Business APIs require a valid bearer token.</span></div><div><CheckCircle2/><b>Persistent events</b><span>Events are read and written through PostgreSQL.</span></div><div><Users/><b>Account-based workflow</b><span>Register once and manage your platform session.</span></div></section>
      <section className="section how" id="how"><div className="heading"><div><span className="kicker">HOW IT WORKS</span><h2>Simple workflow, real API calls.</h2></div></div>
        <div className="steps"><Step n="01" icon={<UserPlus/>} title="Register or sign in" text="Create an account or authenticate with your existing credentials."/><Step n="02" icon={<CalendarDays/>} title="Manage events" text="Create, update, list and delete events from the dedicated event section."/><Step n="03" icon={<CheckCircle2/>} title="Receive notifications" text="Event creation triggers the configured email notification workflow."/></div>
      </section>
    </main>
    <footer><div className="brand"><i><Ticket size={17}/></i>Ticket<span>Flow</span></div><span>Ticket booking platform · Authenticated event management</span></footer>
    {authMode && <AuthModal mode={authMode} close={()=>setAuthMode(null)} onAuthenticated={authenticated} switchMode={()=>setAuthMode(authMode==='login'?'register':'login')}/>}
  </div>
}

function PublicEvents({onLogin}) {
  const [events,setEvents]=useState([]),[loading,setLoading]=useState(true)
  useEffect(()=>{let active=true;api('/v1/events/').then(d=>{if(active)setEvents(Array.isArray(d)?d:[])}).catch(()=>{if(active)setEvents([])}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[])
  return <section className="section" id="events"><div className="heading"><div><span className="kicker">EVENTS</span><h2>Discover upcoming events.</h2></div><button className="view" onClick={onLogin}>Sign in to manage <ArrowRight size={16}/></button></div>
    {loading?<div className="state">Loading events…</div>:events.length?<div className="grid">{events.map(e=><EventCard key={e.id} event={e}/>)}</div>:<div className="empty"><CalendarDays size={28}/><b>No events available yet.</b><span>Sign in and create the first event.</span><button className="primaryCta small" onClick={onLogin}>Sign in</button></div>}
  </section>
}

function EventManager({token,user,onUnauthorized}) {
  const [events,setEvents]=useState([]),[loading,setLoading]=useState(true),[saving,setSaving]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState(''),[editing,setEditing]=useState(null),[showForm,setShowForm]=useState(false),[search,setSearch]=useState('')
  const loadEvents=async()=>{setLoading(true);try{const d=await api('/v1/events/',{},token);setEvents(Array.isArray(d)?d:[])}catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}finally{setLoading(false)}}
  useEffect(()=>{loadEvents()},[token])
  const filtered=useMemo(()=>{const q=search.trim().toLowerCase();return q?events.filter(e=>(e.name+' '+e.venue).toLowerCase().includes(q)):events},[events,search])
  const saveEvent=async form=>{
    setSaving(true);setError('');setNotice('')
    try{
      const params=new URLSearchParams({name:form.name.trim(),venue:form.venue.trim(),starts_at:toApiDateTime(form.starts_at)})
      await api('/v1/events/'+(editing?editing.id:'')+'?'+params,{method:editing?'PUT':'POST'},token)
      setNotice(editing?'Event updated successfully.':'Event created successfully. A notification email was queued.')
      setShowForm(false);setEditing(null);await loadEvents()
    }catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}finally{setSaving(false)}
  }
  const deleteEvent=async event=>{
    if(!window.confirm('Delete "'+event.name+'"?'))return
    try{await api('/v1/events/'+event.id,{method:'DELETE'},token);setNotice('Event deleted successfully.');await loadEvents()}catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}
  }
  return <section className="section manager" id="manage">
    <div className="managerTop"><div><span className="kicker">EVENT MANAGEMENT</span><h2>Your events.</h2><p>Welcome back, <strong>{user?.name||user?.email}</strong>. All operations below use authenticated API calls.</p></div>
      <button className="primaryCta" onClick={()=>{setEditing(null);setShowForm(true)}}><Plus size={17}/> Add event</button></div>
    {notice&&<div className="alert success"><CheckCircle2 size={17}/>{notice}<button onClick={()=>setNotice('')}><X size={14}/></button></div>}
    {error&&<div className="alert error"><X size={17}/>{error}<button onClick={()=>setError('')}><X size={14}/></button></div>}
    <div className="toolbar"><div className="search compact"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search your events..."/></div><span className="count">{events.length} event{events.length===1?'':'s'}</span></div>
    {loading?<div className="state">Loading your events…</div>:filtered.length?<div className="eventTable">{filtered.map(event=><article className="eventRow" key={event.id}>
      <div className="eventIcon"><CalendarDays size={21}/></div><div className="eventInfo"><h3>{event.name}</h3><p><MapPin size={13}/> {event.venue}</p><div className="rowMeta"><span><CalendarDays size={13}/> {formatDate(event.starts_at)}</span><span><Clock3 size={13}/> {formatTime(event.starts_at)}</span></div></div>
      <div className="rowActions"><button className="action edit" onClick={()=>{setEditing(event);setShowForm(true)}}><Edit3 size={15}/> Edit</button><button className="action danger" onClick={()=>deleteEvent(event)}><Trash2 size={15}/> Delete</button></div>
    </article>)}</div>:<div className="empty managerEmpty"><CalendarDays size={32}/><b>{search?'No matching events.':'No events yet.'}</b><span>{search?'Try another search.':'Create your first event to start the workflow.'}</span>{!search&&<button className="primaryCta small" onClick={()=>setShowForm(true)}><Plus size={15}/> Create event</button>}</div>}
    {showForm&&<EventForm event={editing} saving={saving} close={()=>{setShowForm(false);setEditing(null)}} onSubmit={saveEvent}/>}
  </section>
}

function EventForm({event,saving,close,onSubmit}) {
  const [form,setForm]=useState({name:event?.name||'',venue:event?.venue||'',starts_at:toInputDateTime(event?.starts_at)||''})
  const submit=e=>{e.preventDefault();if(form.name.trim()&&form.venue.trim()&&form.starts_at)onSubmit(form)}
  return <div className="backdrop" onClick={close}><form className="modal formModal" onClick={e=>e.stopPropagation()} onSubmit={submit}><button type="button" className="close" onClick={close}><X/></button>
    <span className="kicker">{event?'EDIT EVENT':'CREATE EVENT'}</span><h2>{event?'Update event':'Create an event'}</h2><p className="modalIntro">{event?'Change the event details and save the update.':'Create a persistent event in PostgreSQL.'}</p>
    <label>Event name<input required value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="DevOps Conference"/></label>
    <label>Venue<input required value={form.venue} onChange={e=>setForm({...form,venue:e.target.value})} placeholder="Delhi Stadium"/></label>
    <label>Starts at<input required type="datetime-local" value={form.starts_at} onChange={e=>setForm({...form,starts_at:e.target.value})}/></label>
    <div className="formActions"><button type="button" className="secondaryCta" onClick={close}>Cancel</button><button className="primaryCta" disabled={saving}>{saving?'Saving…':event?'Update event':'Create event'} <ChevronRight size={16}/></button></div>
  </form></div>
}

function AuthModal({mode,close,switchMode,onAuthenticated}) {
  const [name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[loading,setLoading]=useState(false),[error,setError]=useState('')
  const submit=async e=>{e.preventDefault();setLoading(true);setError('');try{const payload=mode==='register'?{name,email,password}:{email,password};const data=await api('/v1/auth/'+mode,{method:'POST',body:JSON.stringify(payload)});onAuthenticated({...data,name:mode==='register'?name:email.split('@')[0]})}catch(e){setError(e.message)}finally{setLoading(false)}}
  return <div className="backdrop" onClick={close}><form className="modal authModal" onClick={e=>e.stopPropagation()} onSubmit={submit}><button type="button" className="close" onClick={close}><X/></button>
    <span className="kicker">{mode==='login'?'WELCOME BACK':'CREATE ACCOUNT'}</span><h2>{mode==='login'?'Sign in to TicketFlow':'Create your account'}</h2><p className="modalIntro">{mode==='login'?'Use your registered email and password.':'Your account unlocks the protected event manager.'}</p>
    {mode==='register'&&<label>Full name<input required minLength="2" value={name} onChange={e=>setName(e.target.value)} placeholder="Devendra"/></label>}
    <label>Email<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></label>
    <label>Password<input required minLength="8" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Minimum 8 characters"/></label>
    {error&&<div className="formError">{error}</div>}
    <button className="primaryCta full" disabled={loading}>{loading?'Please wait…':mode==='login'?'Sign in':'Create account'} <ArrowRight size={16}/></button>
    <div className="switchAuth">{mode==='login'?'New to TicketFlow?':'Already have an account?'} <button type="button" onClick={switchMode}>{mode==='login'?'Create account':'Sign in'}</button></div>
  </form></div>
}

function EventCard({event}) {
  return <article className="card"><div className="eventImage"><span>EVENT</span><div><Ticket size={30}/></div></div><div className="body"><div className="date"><CalendarDays size={13}/>{formatDate(event.starts_at)}</div><h3>{event.name}</h3><p><MapPin size={14}/>{event.venue}</p><div className="meta"><span><Clock3 size={13}/>{formatTime(event.starts_at)}</span><span>ID #{event.id}</span></div></div></article>
}
function Step({n,icon,title,text}){return <div className="step"><div className="stepTop"><span>{n}</span><i>{icon}</i></div><h3>{title}</h3><p>{text}</p></div>}
