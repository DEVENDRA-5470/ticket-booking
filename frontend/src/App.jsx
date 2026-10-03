import { useEffect, useMemo, useState } from 'react'
import { Activity, ArrowRight, Bell, CalendarDays, Check, CheckCircle2, ChevronRight, Clock3, CreditCard, Edit3, LayoutDashboard, LogIn, LogOut, Mail, MapPin, Menu, Plus, RefreshCw, Search, ShieldCheck, Ticket, Trash2, UserPlus, Users, Utensils, X } from 'lucide-react'

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

      {token ? <Dashboard token={token} user={user} onUnauthorized={logout}/> : <PublicEvents onLogin={()=>setAuthMode('login')}/>}
      {!token && <section className="trust"><div><ShieldCheck/><b>Protected routes</b><span>Business APIs require a valid bearer token.</span></div><div><CheckCircle2/><b>Persistent events</b><span>Events are read and written through PostgreSQL.</span></div><div><Users/><b>Account-based workflow</b><span>Register once and manage your platform session.</span></div></section>}
      <section className="section how" id="how"><div className="heading"><div><span className="kicker">HOW IT WORKS</span><h2>Simple workflow, real API calls.</h2></div></div>
        <div className="steps"><Step n="01" icon={<UserPlus/>} title="Register or sign in" text="Create an account or authenticate with your existing credentials."/><Step n="02" icon={<CalendarDays/>} title="Manage events" text="Create, update, list and delete events from the dedicated event section."/><Step n="03" icon={<CheckCircle2/>} title="Receive notifications" text="Event creation triggers the configured email notification workflow."/></div>
      </section>
    </main>
    <footer><div className="brand"><i><Ticket size={17}/></i>Ticket<span>Flow</span></div><span>Ticket booking platform · Authenticated event management</span></footer>
    {authMode && <AuthModal mode={authMode} close={()=>setAuthMode(null)} onAuthenticated={authenticated} switchMode={()=>setAuthMode(authMode==='login'?'register':'login')}/>}
  </div>
}

function Dashboard({token,user,onUnauthorized}) {
  const [section,setSection]=useState('overview')
  const [events,setEvents]=useState([])
  const [bookings,setBookings]=useState([])
  const [notifications,setNotifications]=useState([])
  const [loading,setLoading]=useState(true)
  const [refreshing,setRefreshing]=useState(false)

  const loadDashboard=async(showSpinner=false)=>{
    if(showSpinner)setRefreshing(true)
    try{
      const [e,b,n]=await Promise.all([
        api('/v1/events/',{},token),
        api('/v1/bookings/',{},token),
        api('/v1/notifications/',{},token)
      ])
      setEvents(Array.isArray(e)?e:[])
      setBookings(Array.isArray(b)?b:[])
      setNotifications(Array.isArray(n)?n:[])
    }catch(e){if(e.status===401)onUnauthorized()}
    finally{setLoading(false);setRefreshing(false)}
  }

  const loadNotifications=async()=>{
    try{
      const n=await api('/v1/notifications/',{},token)
      setNotifications(Array.isArray(n)?n:[])
    }catch(e){if(e.status===401)onUnauthorized()}
  }

  useEffect(()=>{
    loadDashboard()
    const timer=setInterval(loadNotifications,5000)
    return()=>clearInterval(timer)
  },[token])

  const markNotificationRead=async id=>{
    try{await api('/v1/notifications/'+id+'/read',{method:'POST'},token);await loadNotifications()}
    catch(e){if(e.status===401)onUnauthorized()}
  }

  const markAllRead=async()=>{
    const unreadItems=notifications.filter(n=>n.status!=='READ')
    if(!unreadItems.length)return
    try{
      await Promise.all(unreadItems.map(n=>api('/v1/notifications/'+n.id+'/read',{method:'POST'},token)))
      await loadNotifications()
    }catch(e){if(e.status===401)onUnauthorized()}
  }

  const activeBookings=bookings.filter(b=>b.status==='CONFIRMED').length
  const cancelledBookings=bookings.filter(b=>b.status==='CANCELLED').length
  const unread=notifications.filter(n=>n.status!=='READ').length

  const nav=(key)=>setSection(key)

  return <section className="dashboardShell" id="dashboard">
    <aside className="dashboardSide">
      <div className="dashBrand"><div className="dashBrandMark"><Ticket size={17}/></div><div><b>TicketFlow</b><span>Operations</span></div></div>
      <div className="dashIdentity">
        <div className="avatar">{(user?.name||user?.email||'U').slice(0,1).toUpperCase()}</div>
        <div><b>{user?.name||'User'}</b><span>{user?.email}</span></div>
      </div>
      <div className="sideLabel">WORKSPACE</div>
      <button className={section==='overview'?'sideItem active':'sideItem'} onClick={()=>nav('overview')}><LayoutDashboard size={17}/> Overview</button>
      <button className={section==='events'?'sideItem active':'sideItem'} onClick={()=>nav('events')}><CalendarDays size={17}/> Events</button>
      <button className={section==='bookings'?'sideItem active':'sideItem'} onClick={()=>nav('bookings')}><Ticket size={17}/> Booking Lab</button>
      <button className={section==='notifications'?'sideItem active':'sideItem'} onClick={()=>nav('notifications')}><Bell size={17}/><span>Notifications</span>{unread>0&&<em>{unread}</em>}</button>
      <div className="sideBottom">
        <div className="sideHealth"><i/> All systems operational</div>
        <small>TicketFlow workspace</small>
      </div>
    </aside>

    <main className="dashboardMain">
      <div className="dashboardTopbar">
        <div className="breadcrumb"><span>Workspace</span><ChevronRight size={13}/><b>{section==='overview'?'Overview':section==='events'?'Events':section==='bookings'?'Booking Lab':'Notifications'}</b></div>
        <div className="topbarActions">
          <span className="syncLabel"><i/> Live sync</span>
          <button className="iconButton" title="Refresh dashboard" onClick={()=>loadDashboard(true)} disabled={refreshing}><RefreshCw size={16} className={refreshing?'spin':''}/></button>
          <button className="topProfile" onClick={()=>nav('overview')}><span className="miniAvatar">{(user?.name||user?.email||'U').slice(0,1).toUpperCase()}</span><span>{user?.name||'Account'}</span></button>
        </div>
      </div>

      <div className="dashboardHeader">
        <div>
          <span className="kicker">TICKETFLOW / {section.toUpperCase()}</span>
          <h2>{section==='overview'?'Command center':section==='events'?'Event management':section==='bookings'?'Booking & transaction lab':'Notifications'}</h2>
          <p>{section==='overview'?'Monitor your ticketing operations from one focused workspace.':section==='events'?'Create, update and manage your event inventory.':section==='bookings'?'Run controlled booking, food and payment workflows.':'Review, triage and clear platform activity.'}</p>
        </div>
        <div className="headerStatus"><span><i/> API connected</span><small>PostgreSQL</small></div>
      </div>

      {section==='overview'&&<div className="dashboardOverview">
        <div className="dashStat"><div className="statTop"><span>Total events</span><CalendarDays size={16}/></div><b>{loading?'—':events.length}</b><small>Across your workspace</small></div>
        <div className="dashStat"><div className="statTop"><span>Active bookings</span><Ticket size={16}/></div><b>{loading?'—':activeBookings}</b><small>Currently confirmed</small></div>
        <div className="dashStat"><div className="statTop"><span>Cancelled</span><Activity size={16}/></div><b>{loading?'—':cancelledBookings}</b><small>Booking records</small></div>
        <div className="dashStat"><div className="statTop"><span>Unread activity</span><Bell size={16}/></div><b>{loading?'—':unread}</b><small>{unread?'Needs attention':'All caught up'}</small></div>

        <div className="dashWelcome">
          <div><span className="kicker">OPERATIONS</span><h3>Your ticketing workspace.</h3><p>Manage inventory, run transaction flows and keep an eye on system activity without jumping between pages.</p></div>
          <div className="welcomeActions"><button className="secondaryCta" onClick={()=>nav('events')}>Manage events <ArrowRight size={15}/></button><button className="primaryCta" onClick={()=>nav('bookings')}>Open Booking Lab <ArrowRight size={15}/></button></div>
        </div>

        <div className="sectionLabel"><div><b>Quick actions</b><span>Start where you need to work.</span></div></div>
        <div className="quickGrid">
          <button onClick={()=>nav('events')}><div className="quickIcon purple"><CalendarDays size={18}/></div><b>Events</b><span>Create, edit and cancel events</span><ArrowRight size={15}/></button>
          <button onClick={()=>nav('bookings')}><div className="quickIcon blue"><Ticket size={18}/></div><b>Booking Lab</b><span>Tickets, food and payments</span><ArrowRight size={15}/></button>
          <button onClick={()=>nav('notifications')}><div className="quickIcon green"><Bell size={18}/></div><b>Notifications</b><span>{unread?unread+' items need attention':'Everything is up to date'}</span><ArrowRight size={15}/></button>
        </div>
      </div>}

      {section==='events'&&<EventManager token={token} user={user} onUnauthorized={onUnauthorized}/>}
      {section==='bookings'&&<BookingLab token={token} onUnauthorized={onUnauthorized}/>}
      {section==='notifications'&&<NotificationSection notifications={notifications} onMarkRead={markNotificationRead} onMarkAllRead={markAllRead}/>}
    </main>
  </section>
}

function NotificationSection({notifications,onMarkRead,onMarkAllRead}) {
  const unreadCount=notifications.filter(n=>n.status!=='READ').length
  const [filter,setFilter]=useState('all')
  const visible=filter==='unread'?notifications.filter(n=>n.status!=='READ'):notifications

  return <div className="dashboardPanel notificationPanel">
    <div className="notificationToolbar">
      <div className="panelIntro"><span className="kicker">ACTIVITY CENTER</span><h3>Recent notifications</h3><p>Live workflow activity from bookings, food, payments and cancellations.</p></div>
      <div className="notificationActions">
        <div className="segmented"><button className={filter==='all'?'active':''} onClick={()=>setFilter('all')}>All <span>{notifications.length}</span></button><button className={filter==='unread'?'active':''} onClick={()=>setFilter('unread')}>Unread <span>{unreadCount}</span></button></div>
        {unreadCount>0&&<button className="markAllButton" onClick={onMarkAllRead}><Check size={14}/> Mark all read</button>}
      </div>
    </div>
    {visible.length?<div className="dashboardNotifications">{visible.map(n=>{
      const read=n.status==='READ'
      return <article className={'dashboardNotification '+(read?'isRead':'isUnread')} key={n.id}>
        <div className="notifIcon">{read?<CheckCircle2 size={17}/>:<span className="notifDot"/>}</div>
        <div className="notifContent">
          <div className="notifMeta"><b>{read?'READ':'UNREAD'}</b><span>{read?'Processed':'Needs attention'}</span>{!read&&<button onClick={()=>onMarkRead(n.id)}>Mark as read</button>}</div>
          <p>{n.message}</p>
        </div>
        <div className="notifChannel"><Mail size={13}/><span>In-app + email</span></div>
      </article>
    })}</div>:<div className="dashboardEmpty"><CheckCircle2 size={30}/><b>{filter==='unread'?'All caught up':'No notifications yet'}</b><span>{filter==='unread'?'There are no unread workflow events.':'Workflow activity will appear here automatically.'}</span></div>}
  </div>
}

function PublicEvents({onLogin}) {
  return <section className="section" id="events">
    <div className="heading">
      <div><span className="kicker">EVENTS</span><h2>Your event workspace starts here.</h2></div>
      <button className="view" onClick={onLogin}>Sign in to manage <ArrowRight size={16}/></button>
    </div>
    <div className="empty managerEmpty">
      <ShieldCheck size={30}/>
      <b>Authentication required</b>
      <span>Sign in to view and manage events through the protected API.</span>
      <button className="primaryCta small" onClick={onLogin}>Sign in</button>
    </div>
  </section>
}
function EventManager({token,user,onUnauthorized}) {
  const [events,setEvents]=useState([]),[loading,setLoading]=useState(true),[saving,setSaving]=useState(false),[notice,setNotice]=useState(''),[error,setError]=useState(''),[editing,setEditing]=useState(null),[showForm,setShowForm]=useState(false),[showBulk,setShowBulk]=useState(false),[bulkReport,setBulkReport]=useState(null),[search,setSearch]=useState('')
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
    if(!window.confirm('Cancel "'+event.name+'"? Existing bookings will be cancelled, seats released and successful payments marked REFUND_PENDING.'))return
    try{await api('/v1/events/'+event.id,{method:'DELETE'},token);setNotice('Event cancelled successfully.');await loadEvents()}catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}
  }

  const deleteAllEvents=async()=>{
    if(!events.length)return
    const confirmed=window.confirm('PERMANENTLY DELETE ALL '+events.length+' EVENTS? This will permanently remove their bookings, seats, food orders and payments. This cannot be undone.')
    if(!confirmed)return
    setSaving(true);setError('');setNotice('')
    try{
      const result=await api('/v1/events/all',{method:'DELETE'},token)
      setNotice(result.message+' ('+result.deleted_events+' events, '+result.deleted_bookings+' bookings removed).')
      await loadEvents()
    }catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}
    finally{setSaving(false)}
  }
  return <section className="section manager" id="manage">
    <div className="managerTop"><div><span className="kicker">EVENT MANAGEMENT</span><h2>Your events.</h2><p>Welcome back, <strong>{user?.name||user?.email}</strong>. All operations below use authenticated API calls.</p></div>
      <div className="managerButtons"><button className="secondaryCta" onClick={()=>setShowBulk(true)}><Users size={17}/> Bulk add</button><button className="primaryCta" onClick={()=>{setEditing(null);setShowForm(true)}}><Plus size={17}/> Add event</button><button className="dangerCta" disabled={!events.length||saving} onClick={deleteAllEvents}><Trash2 size={17}/> {saving ? "Deleting…" : "Delete all"}</button></div></div>
    {notice&&<div className="alert success"><CheckCircle2 size={17}/>{notice}<button onClick={()=>setNotice('')}><X size={14}/></button></div>}
    {error&&<div className="alert error"><X size={17}/>{error}<button onClick={()=>setError('')}><X size={14}/></button></div>}
    <div className="toolbar"><div className="search compact"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search your events..."/></div><span className="count">{events.length} event{events.length===1?'':'s'}</span></div>
    {loading?<div className="state">Loading your events…</div>:filtered.length?<div className="eventTable">{filtered.map(event=><article className="eventRow" key={event.id}>
      <div className="eventIcon"><CalendarDays size={21}/></div><div className="eventInfo"><h3>{event.name}</h3><p><MapPin size={13}/> {event.venue}</p><div className="rowMeta"><span><CalendarDays size={13}/> {formatDate(event.starts_at)}</span><span><Clock3 size={13}/> {formatTime(event.starts_at)}</span></div></div>
      <div className="rowActions"><button className="action edit" onClick={()=>{setEditing(event);setShowForm(true)}}><Edit3 size={15}/> Edit</button><button className="action danger" onClick={()=>deleteEvent(event)}><Trash2 size={15}/> Delete</button></div>
    </article>)}</div>:<div className="empty managerEmpty"><CalendarDays size={32}/><b>{search?'No matching events.':'No events yet.'}</b><span>{search?'Try another search.':'Create your first event to start the workflow.'}</span>{!search&&<button className="primaryCta small" onClick={()=>setShowForm(true)}><Plus size={15}/> Create event</button>}</div>}
    {showForm&&<EventForm event={editing} saving={saving} close={()=>{setShowForm(false);setEditing(null)}} onSubmit={saveEvent}/>}
    {showBulk&&<BulkEventModal token={token} onUnauthorized={onUnauthorized} close={()=>setShowBulk(false)} onComplete={report=>{setBulkReport(report);setShowBulk(false);loadEvents()}}/>}
    {bulkReport&&<BulkReportModal report={bulkReport} close={()=>setBulkReport(null)}/>}
  </section>
}

function BookingLab({token,onUnauthorized}) {
  const [events,setEvents]=useState([]),[eventId,setEventId]=useState(''),[seats,setSeats]=useState([]),[selectedSeats,setSelectedSeats]=useState([])
  const [food,setFood]=useState([]),[foodId,setFoodId]=useState(''),[foodQty,setFoodQty]=useState(1),[newFood,setNewFood]=useState({name:'',price:''})
  const [bookings,setBookings]=useState([]),[bookingId,setBookingId]=useState(''),[bulkCount,setBulkCount]=useState(10)
  const [bulkFoodCount,setBulkFoodCount]=useState(10),[bulkFoodQty,setBulkFoodQty]=useState(1),[notifications,setNotifications]=useState([])
  const [message,setMessage]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false)

  const load=async()=>{
    try{
      const [ev,fi,bo,no]=await Promise.all([
        api('/v1/events/',{},token),api('/v1/food/items',{},token),api('/v1/bookings/',{},token),api('/v1/notifications/',{},token)
      ])
      setEvents(Array.isArray(ev)?ev:[]);setFood(Array.isArray(fi)?fi:[]);setBookings(Array.isArray(bo)?bo:[]);setNotifications(Array.isArray(no)?no:[])
      if(!eventId&&ev?.length)setEventId(String(ev[0].id))
      if(!bookingId&&bo?.length)setBookingId(String(bo[0].id))
    }catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}
  }
  const loadSeats=async id=>{
    if(!id){setSeats([]);return}
    try{const d=await api('/v1/seats/event/'+id,{},token);setSeats(Array.isArray(d)?d:[]);setSelectedSeats([])}
    catch(e){setError(e.message)}
  }
  useEffect(()=>{load()},[token])
  useEffect(()=>{loadSeats(eventId)},[eventId])
  const run=async(fn)=>{
    setBusy(true);setError('');setMessage('')
    try{const result=await fn();setMessage(result?.message||'Operation completed successfully.');await load();if(eventId)await loadSeats(eventId)}catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}finally{setBusy(false)}
  }
  const generateSeats=()=>run(()=>api('/v1/seats/event/'+eventId+'/generate?count=50',{method:'POST'},token))
  const book=()=>run(()=>api('/v1/bookings/',{method:'POST',body:JSON.stringify({event_id:Number(eventId),seat_ids:selectedSeats})},token))
  const bulkBook=()=>run(()=>api('/v1/bookings/bulk?event_id='+eventId+'&count='+bulkCount,{method:'POST'},token))
  const placeFood=()=>run(()=>api('/v1/food/orders',{method:'POST',body:JSON.stringify({booking_id:Number(bookingId),items:[[Number(foodId),Number(foodQty)]]})},token))
  const bulkFood=()=>run(()=>api('/v1/food/orders/bulk?booking_id='+bookingId+'&food_item_id='+foodId+'&quantity='+bulkFoodQty+'&count='+bulkFoodCount,{method:'POST'},token))
  const createFood=()=>run(async()=>api('/v1/food/items',{method:'POST',body:JSON.stringify({name:newFood.name,price:Number(newFood.price),available:true})},token))
  const simulatePayment=()=>run(()=>api('/v1/payments/simulate/'+bookingId,{method:'POST'},token))
  const cancelBooking=()=>run(()=>api('/v1/cancellations/'+bookingId,{method:'POST'},token))

  return <section className="section bookingLab" id="booking-lab">
    <div className="heading"><div><span className="kicker">BOOKING LAB</span><h2>Tickets, food & payments.</h2><p>Manual and bulk flows are wired to the same transactional APIs used by the platform.</p></div></div>
    {message&&<div className="alert success"><CheckCircle2 size={17}/>{message}</div>}
    {error&&<div className="alert error"><X size={17}/>{error}</div>}
    <div className="labGrid">
      <div className="labCard">
        <div className="labTitle"><CalendarDays size={18}/><div><b>Manual ticket booking</b><span>Select an event and available seats.</span></div></div>
        <select value={eventId} onChange={e=>setEventId(e.target.value)}><option value="">Select event</option>{events.filter(e=>e.status!=='CANCELLED').map(e=><option key={e.id} value={e.id}>{e.name} — {e.venue}</option>)}</select>
        <div className="seatGrid">{seats.map(s=><button key={s.id} disabled={s.status!=='AVAILABLE'} className={'seat '+(selectedSeats.includes(s.id)?'selected':'')} onClick={()=>setSelectedSeats(x=>x.includes(s.id)?x.filter(id=>id!==s.id):[...x,s.id])}>{s.seat_number}</button>)}</div>
        {!seats.length&&eventId&&<button className="secondaryCta" onClick={generateSeats} disabled={busy}>Generate 50 seats</button>}
        <button className="primaryCta full" disabled={!selectedSeats.length||busy} onClick={book}>Book {selectedSeats.length} seat{selectedSeats.length===1?'':'s'}</button>
      </div>
      <div className="labCard">
        <div className="labTitle"><Users size={18}/><div><b>Bulk ticket booking</b><span>Generate bookings for load testing.</span></div></div>
        <select value={eventId} onChange={e=>setEventId(e.target.value)}><option value="">Select event</option>{events.filter(e=>e.status!=='CANCELLED').map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select>
        <label>Number of bookings<input type="number" min="1" max="500" value={bulkCount} onChange={e=>setBulkCount(Math.max(1,Math.min(500,Number(e.target.value)||1)))}/></label>
        <button className="primaryCta full" disabled={!eventId||busy} onClick={bulkBook}>Create {bulkCount} bookings <Users size={16}/></button>
      </div>
      <div className="labCard">
        <div className="labTitle"><Utensils size={18}/><div><b>Manual food order</b><span>Add food to a confirmed booking.</span></div></div>
        <select value={bookingId} onChange={e=>setBookingId(e.target.value)}><option value="">Select booking</option>{bookings.filter(b=>b.status==='CONFIRMED').map(b=><option key={b.id} value={b.id}>{b.reference} — event #{b.event_id}</option>)}</select>
        <select value={foodId} onChange={e=>setFoodId(e.target.value)}><option value="">Select food</option>{food.map(f=><option key={f.id} value={f.id}>{f.name} — ₹{f.price}</option>)}</select>
        <label>Quantity<input type="number" min="1" value={foodQty} onChange={e=>setFoodQty(Math.max(1,Number(e.target.value)||1))}/></label>
        <button className="primaryCta full" disabled={!bookingId||!foodId||busy} onClick={placeFood}>Place food order <Utensils size={16}/></button>
      </div>
      <div className="labCard">
        <div className="labTitle"><Users size={18}/><div><b>Bulk food orders</b><span>Create repeated food orders for testing.</span></div></div>
        <select value={bookingId} onChange={e=>setBookingId(e.target.value)}><option value="">Select booking</option>{bookings.filter(b=>b.status==='CONFIRMED').map(b=><option key={b.id} value={b.id}>{b.reference}</option>)}</select>
        <select value={foodId} onChange={e=>setFoodId(e.target.value)}><option value="">Select food</option>{food.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select>
        <label>Orders<input type="number" min="1" max="500" value={bulkFoodCount} onChange={e=>setBulkFoodCount(Math.max(1,Math.min(500,Number(e.target.value)||1)))}/></label>
        <button className="secondaryCta full" disabled={!bookingId||!foodId||busy} onClick={bulkFood}>Create {bulkFoodCount} food orders</button>
      </div>
      <div className="labCard">
        <div className="labTitle"><Utensils size={18}/><div><b>Add food item</b><span>Create menu data for manual/bulk ordering.</span></div></div>
        <input value={newFood.name} onChange={e=>setNewFood({...newFood,name:e.target.value})} placeholder="Veg Burger"/>
        <input type="number" min="1" value={newFood.price} onChange={e=>setNewFood({...newFood,price:e.target.value})} placeholder="Price"/>
        <button className="secondaryCta full" disabled={!newFood.name||!newFood.price||busy} onClick={createFood}>Add food item <Plus size={16}/></button>
      </div>
      <div className="labCard paymentCard">
        <div className="labTitle"><CreditCard size={18}/><div><b>Payment simulation</b><span>Ticket = ₹500/seat + active food total.</span></div></div>
        <select value={bookingId} onChange={e=>setBookingId(e.target.value)}><option value="">Select booking</option>{bookings.filter(b=>b.status==='CONFIRMED').map(b=><option key={b.id} value={b.id}>{b.reference}</option>)}</select>
        <button className="primaryCta full" disabled={!bookingId||busy} onClick={simulatePayment}><CreditCard size={16}/> Simulate successful payment</button>
        <button className="dangerCta full" disabled={!bookingId||busy} onClick={cancelBooking}><Trash2 size={16}/> Cancel everything</button>
      </div>
    </div>
    <div className="labBottom">
      <div className="labCard"><div className="labTitle"><Ticket size={18}/><div><b>My bookings</b><span>Select one for food, payment or cancellation.</span></div></div>{bookings.length?<div className="bookingList">{bookings.slice(0,20).map(b=><button key={b.id} className={String(b.id)===String(bookingId)?'bookingItem active':'bookingItem'} onClick={()=>setBookingId(String(b.id))}><b>{b.reference}</b><span>Event #{b.event_id} · {b.status}</span></button>)}</div>:<span className="muted">No bookings yet.</span>}</div>
      <div className="labCard"><div className="labTitle"><CheckCircle2 size={18}/><div><b>Notifications</b><span>Booking, food, payment and cancellation events.</span></div></div>{notifications.length?<div className="notificationList">{notifications.slice(0,10).map(n=><div className="notificationItem" key={n.id}><b>{n.status}</b><span>{n.message}</span></div>)}</div>:<span className="muted">No notifications yet.</span>}</div>
    </div>
  </section>
}


function BulkEventModal({token,onUnauthorized,close,onComplete}) {
  const [count,setCount]=useState(10),[running,setRunning]=useState(false),[error,setError]=useState('')
  const run=async e=>{e.preventDefault();setRunning(true);setError('')
    try{const report=await api('/v1/events/bulk?count='+encodeURIComponent(count),{method:'POST'},token);onComplete(report)}
    catch(e){if(e.status===401)onUnauthorized();else setError(e.message)}finally{setRunning(false)}
  }
  return <div className="backdrop" onClick={close}><form className="modal bulkModal" onClick={e=>e.stopPropagation()} onSubmit={run}>
    <button type="button" className="close" onClick={close}><X/></button>
    <span className="kicker">BULK EVENT CREATOR</span><h2>Create events in bulk</h2>
    <p className="modalIntro">Choose how many events to create. Names, venues and future start times will be generated randomly.</p>
    <label>Number of events<input required type="number" min="1" max="500" value={count} onChange={e=>setCount(Math.max(1,Math.min(500,Number(e.target.value)||1)))}/></label>
    {error&&<div className="formError">{error}</div>}
    <div className="bulkHint"><span>Range</span><b>1–500 events</b><span>Report</span><b>PASS / FAIL + time</b></div>
    <div className="formActions"><button type="button" className="secondaryCta" onClick={close}>Cancel</button><button className="primaryCta" disabled={running}>{running?'Creating…':'Create '+count+' events'} <ChevronRight size={16}/></button></div>
  </form></div>
}

function BulkReportModal({report,close}) {
  return <div className="backdrop" onClick={close}><div className="modal reportModal" onClick={e=>e.stopPropagation()}>
    <button className="close" onClick={close}><X/></button>
    <span className="kicker">BULK CREATION REPORT</span><h2>Run complete.</h2>
    <div className="reportStats"><div><b>{report.requested}</b><span>Requested</span></div><div className="pass"><b>{report.passed}</b><span>Passed</span></div><div className="fail"><b>{report.failed}</b><span>Failed</span></div><div><b>{report.total_time_ms} ms</b><span>Total time</span></div></div>
    <div className="reportTable">{report.results.map(item=><div className="reportRow" key={item.index}><span>#{item.index}</span><strong className={item.status==='PASS'?'passText':'failText'}>{item.status}</strong><span>{item.name||item.error}</span><span>{item.time_ms} ms</span></div>)}</div>
    <div className="reportFooter"><span>Average: <b>{report.average_time_ms} ms/event</b></span><button className="primaryCta small" onClick={close}>Done</button></div>
  </div></div>
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