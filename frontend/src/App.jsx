import { useEffect, useMemo, useState } from 'react'
import {
  ArrowRight, Bell, CalendarDays, Check, CheckCircle2, ChevronRight,
  Clock3, LogIn, LogOut, Mail, MapPin, Menu, RefreshCw, Search,
  ShieldCheck, Ticket, UserPlus, Users, X
} from 'lucide-react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function api(path, options = {}, token = null) {
  const headers = {
    ...(options.body ? {'Content-Type':'application/json'} : {}),
    ...(token ? {Authorization:'Bearer ' + token} : {}),
    ...(options.headers || {})
  }
  const response = await fetch(API_BASE + path, {...options, headers})
  const text = await response.text()
  let data = null
  try { data = text ? JSON.parse(text) : null } catch { data = text }
  if (!response.ok) {
    const error = new Error(data?.detail || data?.message || 'Request failed')
    error.status = response.status
    throw error
  }
  return data
}

function formatDate(value) {
  return value ? new Intl.DateTimeFormat('en-IN',{day:'2-digit',month:'short',year:'numeric'}).format(new Date(value)) : '—'
}
function formatTime(value) {
  return value ? new Intl.DateTimeFormat('en-IN',{hour:'2-digit',minute:'2-digit'}).format(new Date(value)) : '—'
}

export default function App() {
  const [token,setToken] = useState(() => localStorage.getItem('ticketflow_token'))
  const [user,setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ticketflow_user')) || null } catch { return null }
  })
  const [authMode,setAuthMode] = useState(null)
  const [mobile,setMobile] = useState(false)

  const logout = () => {
    localStorage.removeItem('ticketflow_token')
    localStorage.removeItem('ticketflow_user')
    setToken(null)
    setUser(null)
  }

  const authenticated = data => {
    const u = {
      user_id:data.user_id,
      email:data.email,
      name:data.name || data.email.split('@')[0]
    }
    localStorage.setItem('ticketflow_token',data.access_token)
    localStorage.setItem('ticketflow_user',JSON.stringify(u))
    setToken(data.access_token)
    setUser(u)
    setAuthMode(null)
  }

  if (token) {
    return <div className="app authenticatedApp">
      <CustomerApp token={token} user={user} onUnauthorized={logout} onLogout={logout}/>
    </div>
  }

  return <div className="app">
    <header className="nav">
      <a className="brand" href="#top"><i><Ticket size={20}/></i>Ticket<span>Flow</span></a>
      <nav className={mobile?'links open':'links'}>
        <a href="#events" onClick={()=>setMobile(false)}>Events</a>
        <a href="#how" onClick={()=>setMobile(false)}>How it works</a>
      </nav>
      <div className="actions">
        <button className="login secondary" onClick={()=>setAuthMode('login')}>Sign in</button>
        <button className="login" onClick={()=>setAuthMode('register')}>Get started</button>
        <button className="menu" onClick={()=>setMobile(!mobile)}>{mobile?<X/>:<Menu/>}</button>
      </div>
    </header>

    <main id="top">
      <section className="hero">
        <div className="heroText">
          <div className="eyebrow"><Ticket size={14}/> Simple event booking</div>
          <h1>Find your next<br/><em>experience.</em></h1>
          <p>Discover events, choose your seats and keep every booking in one place.</p>
          <div className="heroActions">
            <button className="primaryCta" onClick={()=>document.getElementById('events')?.scrollIntoView({behavior:'smooth'})}>Explore events <ArrowRight size={16}/></button>
            <button className="secondaryCta" onClick={()=>setAuthMode('login')}>Sign in <LogIn size={16}/></button>
          </div>
          <div className="stats">
            <span><b>Secure</b> authenticated bookings</span>
            <span><b>Live</b> seat availability</span>
            <span><ShieldCheck size={15}/> Email confirmations</span>
          </div>
        </div>
        <div className="heroCard">
          <div className="live"><i/> Booking platform online</div>
          <div className="ticketArt">
            <div className="ticketTop"><Ticket/><span>TICKETFLOW</span></div>
            <div className="ticketMain"><small>YOUR NEXT EVENT</small><h3>Discover. Select. Book.</h3><p>A focused booking experience without operational clutter.</p></div>
            <div className="ticketBottom"><span>EVENTS</span><span>SEATS</span><span>BOOK</span></div>
          </div>
          <div className="availability"><span>● Platform connected</span><b>Secure</b></div>
        </div>
      </section>

      <PublicEventCatalog onLogin={()=>setAuthMode('login')}/>
      <section className="section how" id="how">
        <div className="heading"><div><span className="kicker">HOW IT WORKS</span><h2>Three steps to your seat.</h2></div></div>
        <div className="steps">
          <Step n="01" icon={<Search/>} title="Discover" text="Browse upcoming events and open the one you want to attend."/>
          <Step n="02" icon={<Ticket/>} title="Choose seats" text="See live availability and select the seats that work for you."/>
          <Step n="03" icon={<CheckCircle2/>} title="Confirm" text="Complete the booking and receive confirmation in your account and email."/>
        </div>
      </section>
    </main>
    <footer><div className="brand"><i><Ticket size={17}/></i>Ticket<span>Flow</span></div><span>Event discovery · Seat booking · Account notifications</span></footer>
    {authMode && <AuthModal mode={authMode} close={()=>setAuthMode(null)} onAuthenticated={authenticated} switchMode={()=>setAuthMode(authMode==='login'?'register':'login')}/>}
  </div>
}

function PublicEventCatalog({onLogin}) {
  const [events,setEvents]=useState([])
  const [loading,setLoading]=useState(true)
  const [search,setSearch]=useState('')
  const [selected,setSelected]=useState(null)

  useEffect(()=>{
    api('/v1/events/')
      .then(data=>setEvents(Array.isArray(data)?data:[]))
      .catch(()=>setEvents([]))
      .finally(()=>setLoading(false))
  },[])

  const filtered=useMemo(()=>{
    const q=search.trim().toLowerCase()
    return q ? events.filter(e=>(e.name+' '+e.venue).toLowerCase().includes(q)) : events
  },[events,search])

  return <section className="section publicCatalog" id="events">
    <div className="heading catalogHeading">
      <div><span className="kicker">UPCOMING EVENTS</span><h2>Choose where you want to be.</h2><p>Browse published events and check seat availability before booking.</p></div>
      <div className="search compact"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search events or venues"/></div>
    </div>
    {loading ? <div className="eventSkeletonGrid"><div/><div/><div/></div> :
      filtered.length ? <div className="clientEventGrid">{filtered.slice(0,12).map(event=><ClientEventCard key={event.id} event={event} onOpen={()=>setSelected(event)}/>)}</div> :
      <div className="empty managerEmpty"><CalendarDays size={30}/><b>{search?'No matching events':'No upcoming events'}</b><span>{search?'Try another search.':'New events will appear here as they are published.'}</span></div>}
    {selected&&<EventDetails event={selected} onClose={()=>setSelected(null)} onLogin={onLogin}/>}
  </section>
}

function ClientEventCard({event,onOpen}) {
  return <article className="clientEventCard">
    <div className="clientEventVisual"><span>LIVE EVENT</span><Ticket size={31}/></div>
    <div className="clientEventBody">
      <div className="clientEventDate"><CalendarDays size={13}/>{formatDate(event.starts_at)} · {formatTime(event.starts_at)}</div>
      <h3>{event.name}</h3>
      <p><MapPin size={14}/>{event.venue}</p>
      <div className="clientEventFooter"><span>{event.capacity} seats</span><button onClick={onOpen}>View event <ArrowRight size={14}/></button></div>
    </div>
  </article>
}

function CustomerApp({token,user,onUnauthorized,onLogout}) {
  const [section,setSection]=useState('overview')
  const [events,setEvents]=useState([])
  const [bookings,setBookings]=useState([])
  const [notifications,setNotifications]=useState([])
  const [loading,setLoading]=useState(true)
  const [refreshing,setRefreshing]=useState(false)

  const load=async(showSpinner=false)=>{
    if(showSpinner)setRefreshing(true)
    try {
      const [e,b,n]=await Promise.all([
        api('/v1/events/',{},token),
        api('/v1/bookings/',{},token),
        api('/v1/notifications/',{},token)
      ])
      setEvents(Array.isArray(e)?e:[])
      setBookings(Array.isArray(b)?b:[])
      setNotifications(Array.isArray(n)?n:[])
    } catch(e) {
      if(e.status===401)onUnauthorized()
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(()=>{
    load()
    const timer=setInterval(async()=>{
      try {
        const n=await api('/v1/notifications/',{},token)
        setNotifications(Array.isArray(n)?n:[])
      } catch(e) { if(e.status===401)onUnauthorized() }
    },5000)
    return()=>clearInterval(timer)
  },[token])

  const unread=notifications.filter(n=>n.status!=='READ').length
  const active=bookings.filter(b=>b.status==='CONFIRMED').length
  const cancelled=bookings.filter(b=>b.status==='CANCELLED').length

  const markRead=async id=>{
    try { await api('/v1/notifications/'+id+'/read',{method:'POST'},token); await load() }
    catch(e){if(e.status===401)onUnauthorized()}
  }

  const markAllRead=async()=>{
    try {
      await Promise.all(notifications.filter(n=>n.status!=='READ').map(n=>api('/v1/notifications/'+n.id+'/read',{method:'POST'},token)))
      await load()
    } catch(e){if(e.status===401)onUnauthorized()}
  }

  return <section className="customerShell">
    <aside className="customerSide">
      <div className="customerBrand"><div className="customerBrandMark"><Ticket size={17}/></div><div><b>TicketFlow</b><span>Customer</span></div></div>
      <div className="customerIdentity"><div className="avatar">{(user?.name||user?.email||'U').slice(0,1).toUpperCase()}</div><div><b>{user?.name||'Account'}</b><span>{user?.email}</span></div></div>
      <div className="sideLabel">MY ACCOUNT</div>
      <button className={section==='overview'?'sideItem active':'sideItem'} onClick={()=>setSection('overview')}><ShieldCheck size={17}/> Overview</button>
      <button className={section==='events'?'sideItem active':'sideItem'} onClick={()=>setSection('events')}><CalendarDays size={17}/> Discover events</button>
      <button className={section==='bookings'?'sideItem active':'sideItem'} onClick={()=>setSection('bookings')}><Ticket size={17}/> My bookings</button>
      <button className={section==='notifications'?'sideItem active':'sideItem'} onClick={()=>setSection('notifications')}><Bell size={17}/><span>Notifications</span>{unread>0&&<em>{unread}</em>}</button>
      <div className="sideBottom"><div className="sideHealth"><i/> Platform operational</div><small>Customer workspace</small></div>
    </aside>

    <main className="customerMain">
      <div className="customerTopbar">
        <div className="breadcrumb"><span>Account</span><ChevronRight size={13}/><b>{section==='overview'?'Overview':section==='events'?'Discover events':section==='bookings'?'My bookings':'Notifications'}</b></div>
        <div className="topbarActions">
          <span className="syncLabel"><i/> Live sync</span>
          <button className="iconButton" title="Refresh" onClick={()=>load(true)} disabled={refreshing}><RefreshCw size={16} className={refreshing?'spin':''}/></button>
          <div className="topProfile"><span className="miniAvatar">{(user?.name||user?.email||'U').slice(0,1).toUpperCase()}</span><span>{user?.name||'Account'}</span><button title="Log out" onClick={onLogout}><LogOut size={14}/></button></div>
        </div>
      </div>

      {section==='overview'&&<CustomerOverview user={user} loading={loading} active={active} cancelled={cancelled} unread={unread} onNavigate={setSection} bookings={bookings}/>}
      {section==='events'&&<AuthenticatedEvents events={events} onRefresh={load}/>}
      {section==='bookings'&&<MyBookings bookings={bookings} token={token} onChanged={load} onUnauthorized={onUnauthorized}/>}
      {section==='notifications'&&<NotificationCenter notifications={notifications} onMarkRead={markRead} onMarkAllRead={markAllRead}/>}
    </main>
  </section>
}

function CustomerOverview({user,loading,active,cancelled,unread,onNavigate,bookings}) {
  const next=bookings.find(b=>b.status==='CONFIRMED')
  return <div>
    <div className="customerHeader"><div><span className="kicker">TICKETFLOW / OVERVIEW</span><h2>Good to see you, {user?.name||'there'}.</h2><p>Your upcoming experiences, bookings and account activity in one place.</p></div><button className="primaryCta" onClick={()=>onNavigate('events')}>Find an event <ArrowRight size={15}/></button></div>
    <div className="customerStats">
      <Stat label="Upcoming bookings" value={loading?'—':active} note="Confirmed reservations" icon={<Ticket size={16}/>}/>
      <Stat label="Events available" value={loading?'—':'Browse'} note="Discover something new" icon={<CalendarDays size={16}/>}/>
      <Stat label="Cancelled" value={loading?'—':cancelled} note="Booking history" icon={<Clock3 size={16}/>}/>
      <Stat label="Notifications" value={loading?'—':unread} note={unread?'Need your attention':'All caught up'} icon={<Bell size={16}/>}/>
    </div>
    <div className="customerWelcome">
      <div><span className="kicker">YOUR NEXT STEP</span><h3>{next?'You have a booking ready to view.':'Find your next experience.'}</h3><p>{next?'Open My bookings to review your reservation details.':'Browse upcoming events and choose your preferred seats.'}</p></div>
      <button className="secondaryCta" onClick={()=>onNavigate(next?'bookings':'events')}>{next?'View booking':'Browse events'} <ArrowRight size={15}/></button>
    </div>
  </div>
}

function Stat({label,value,note,icon}) {
  return <div className="customerStat"><div className="statTop"><span>{label}</span>{icon}</div><b>{value}</b><small>{note}</small></div>
}

function AuthenticatedEvents({events,onRefresh}) {
  const [search,setSearch]=useState('')
  const [selected,setSelected]=useState(null)
  const filtered=useMemo(()=>{
    const q=search.trim().toLowerCase()
    return q?events.filter(e=>(e.name+' '+e.venue).toLowerCase().includes(q)):events
  },[events,search])
  return <div>
    <div className="customerHeader"><div><span className="kicker">DISCOVER</span><h2>Upcoming events.</h2><p>Pick an event, check live seats and reserve your place.</p></div></div>
    <div className="customerToolbar"><div className="search compact"><Search size={17}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search events or venues"/></div><span>{filtered.length} event{filtered.length===1?'':'s'}</span></div>
    {filtered.length?<div className="clientEventGrid">{filtered.map(e=><ClientEventCard key={e.id} event={e} onOpen={()=>setSelected(e)}/>)}</div>:<div className="dashboardEmpty"><CalendarDays size={30}/><b>No matching events</b><span>Try another event name or venue.</span></div>}
    {selected&&<EventDetails event={selected} onClose={()=>setSelected(null)} onBooked={()=>{setSelected(null);onRefresh()}}/>}
  </div>
}

function EventDetails({event,onClose,onLogin,onBooked}) {
  const [seats,setSeats]=useState([])
  const [selected,setSelected]=useState([])
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [booking,setBooking]=useState(false)
  const token=localStorage.getItem('ticketflow_token')

  useEffect(()=>{
    api('/v1/seats/event/'+event.id)
      .then(data=>setSeats(Array.isArray(data)?data:[]))
      .catch(e=>setError(e.message))
      .finally(()=>setLoading(false))
  },[event.id])

  const available=seats.filter(s=>s.status==='AVAILABLE').length

  const submit=async()=>{
    if(!token){onLogin?.();return}
    if(!selected.length)return
    setBooking(true);setError('')
    try {
      await api('/v1/bookings/',{method:'POST',body:JSON.stringify({event_id:event.id,seat_ids:selected})},token)
      if(onBooked)onBooked()
      else onClose()
      alert('Booking confirmed. Check your email for the confirmation.')
    } catch(e) {
      setError(e.message)
      if(e.status===401)onLogin?.()
    } finally {setBooking(false)}
  }

  return <div className="backdrop" onClick={onClose}>
    <div className="modal eventBookingModal" onClick={e=>e.stopPropagation()}>
      <button className="close" onClick={onClose}><X/></button>
      <div className="eventDetailHero"><span>EVENT</span><Ticket size={29}/></div>
      <div className="eventDetailContent">
        <span className="kicker">EVENT DETAILS</span>
        <h2>{event.name}</h2>
        <div className="eventFacts"><span><MapPin size={14}/>{event.venue}</span><span><CalendarDays size={14}/>{formatDate(event.starts_at)}</span><span><Clock3 size={14}/>{formatTime(event.starts_at)}</span></div>
        <div className="seatHeading"><div><b>Select your seats</b><span>{available} available</span></div><small>{selected.length} selected</small></div>
        {loading?<div className="seatLoading">Loading live availability…</div>:
          seats.length?<div className="clientSeatGrid">{seats.map(s=><button key={s.id} disabled={s.status!=='AVAILABLE'} className={'clientSeat '+(selected.includes(s.id)?'selected':'')+' '+(s.status!=='AVAILABLE'?'taken':'')} onClick={()=>setSelected(x=>x.includes(s.id)?x.filter(id=>id!==s.id):[...x,s.id])}>{s.seat_number.replace('S','')}</button>)}</div>:
          <div className="dashboardEmpty small"><b>Seats are not available yet.</b></div>}
        {error&&<div className="formError">{error}</div>}
        <div className="bookingSummary"><span>{selected.length} seat{selected.length===1?'':'s'} selected</span><b>Free booking</b></div>
        <div className="formActions"><button className="secondaryCta" onClick={onClose}>Close</button><button className="primaryCta" disabled={!selected.length||booking} onClick={submit}>{booking?'Confirming…':token?'Confirm booking':'Sign in to book'} <ArrowRight size={15}/></button></div>
      </div>
    </div>
  </div>
}

function MyBookings({bookings,token,onChanged,onUnauthorized}) {
  const [cancelling,setCancelling]=useState(null)
  const cancel=async booking=>{
    if(!window.confirm('Cancel this booking? Your seats will be released.'))return
    setCancelling(booking.id)
    try { await api('/v1/cancellations/'+booking.id,{method:'POST'},token); await onChanged() }
    catch(e){if(e.status===401)onUnauthorized();else alert(e.message)}
    finally{setCancelling(null)}
  }
  return <div>
    <div className="customerHeader"><div><span className="kicker">RESERVATIONS</span><h2>My bookings.</h2><p>Review your reservations and manage cancellations.</p></div></div>
    {bookings.length?<div className="bookingCards">{bookings.map(b=><article className="bookingCard" key={b.id}>
      <div className="bookingCardMain"><div className="bookingRef"><Ticket size={16}/><b>{b.reference}</b></div><span className={'statusPill '+b.status.toLowerCase()}>{b.status}</span></div>
      <div className="bookingCardMeta"><span>Event #{b.event_id}</span><span>Booking #{b.id}</span></div>
      {b.status==='CONFIRMED'&&<div className="bookingCardAction"><button className="dangerCta" disabled={cancelling===b.id} onClick={()=>cancel(b)}>{cancelling===b.id?'Cancelling…':'Cancel booking'}</button></div>}
    </article>)}</div>:<div className="dashboardEmpty"><Ticket size={30}/><b>No bookings yet</b><span>Your confirmed reservations will appear here.</span></div>}
  </div>
}

function NotificationCenter({notifications,onMarkRead,onMarkAllRead}) {
  const [filter,setFilter]=useState('all')
  const unread=notifications.filter(n=>n.status!=='READ').length
  const visible=filter==='unread'?notifications.filter(n=>n.status!=='READ'):notifications
  return <div>
    <div className="customerHeader"><div><span className="kicker">ACTIVITY</span><h2>Notifications.</h2><p>Booking confirmations, cancellations and account activity.</p></div></div>
    <div className="notificationToolbar">
      <div className="segmented"><button className={filter==='all'?'active':''} onClick={()=>setFilter('all')}>All <span>{notifications.length}</span></button><button className={filter==='unread'?'active':''} onClick={()=>setFilter('unread')}>Unread <span>{unread}</span></button></div>
      {unread>0&&<button className="markAllButton" onClick={onMarkAllRead}><Check size={14}/> Mark all read</button>}
    </div>
    {visible.length?<div className="dashboardNotifications">{visible.map(n=>{
      const read=n.status==='READ'
      return <article className={'dashboardNotification '+(read?'isRead':'isUnread')} key={n.id}>
        <div className="notifIcon">{read?<CheckCircle2 size={17}/>:<span className="notifDot"/>}</div>
        <div className="notifContent"><div className="notifMeta"><b>{read?'READ':'UNREAD'}</b><span>{read?'Processed':'New activity'}</span>{!read&&<button onClick={()=>onMarkRead(n.id)}>Mark as read</button>}</div><p>{n.message}</p></div>
        <div className="notifChannel"><Mail size={13}/><span>In-app + email</span></div>
      </article>
    })}</div>:<div className="dashboardEmpty"><CheckCircle2 size={30}/><b>{filter==='unread'?'All caught up':'No notifications yet'}</b><span>{filter==='unread'?'You have no unread activity.':'Activity will appear here after you use the platform.'}</span></div>}
  </div>
}

function AuthModal({mode,close,switchMode,onAuthenticated}) {
  const [name,setName]=useState('')
  const [email,setEmail]=useState('')
  const [password,setPassword]=useState('')
  const [loading,setLoading]=useState(false)
  const [error,setError]=useState('')

  const submit=async e=>{
    e.preventDefault();setLoading(true);setError('')
    try {
      const payload=mode==='register'?{name,email,password}:{email,password}
      const data=await api('/v1/auth/'+mode,{method:'POST',body:JSON.stringify(payload)})
      onAuthenticated({...data,name:mode==='register'?name:email.split('@')[0]})
    } catch(e){setError(e.message)}
    finally{setLoading(false)}
  }

  return <div className="backdrop" onClick={close}>
    <form className="modal authModal" onClick={e=>e.stopPropagation()} onSubmit={submit}>
      <button type="button" className="close" onClick={close}><X/></button>
      <span className="kicker">{mode==='login'?'WELCOME BACK':'GET STARTED'}</span>
      <h2>{mode==='login'?'Sign in to your account':'Create your account'}</h2>
      <p className="modalIntro">{mode==='login'?'Access your bookings and notifications.':'Create an account to reserve seats and manage your bookings.'}</p>
      {mode==='register'&&<label>Full name<input required minLength="2" value={name} onChange={e=>setName(e.target.value)} placeholder="Your name"/></label>}
      <label>Email<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} placeholder="you@example.com"/></label>
      <label>Password<input required minLength="8" type="password" value={password} onChange={e=>setPassword(e.target.value)} placeholder="Minimum 8 characters"/></label>
      {error&&<div className="formError">{error}</div>}
      <button className="primaryCta full" disabled={loading}>{loading?'Please wait…':mode==='login'?'Sign in':'Create account'} <ArrowRight size={16}/></button>
      <div className="switchAuth">{mode==='login'?'New here?':'Already have an account?'} <button type="button" onClick={switchMode}>{mode==='login'?'Create account':'Sign in'}</button></div>
    </form>
  </div>
}

function Step({n,icon,title,text}) {
  return <div className="step"><div className="stepTop"><span>{n}</span><i>{icon}</i></div><h3>{title}</h3><p>{text}</p></div>
}
