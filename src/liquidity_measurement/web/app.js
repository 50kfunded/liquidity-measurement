const $ = id => document.getElementById(id);
const money = n => n == null ? 'unavailable' : '$' + n.toLocaleString('en-US', {maximumFractionDigits: 2});
const number = n => n == null ? '—' : n.toFixed(3);
const text = (tag, value, className) => {const el = document.createElement(tag); el.textContent = value; if (className) el.className = className; return el;};
const label = value => value.replaceAll('_', ' ');
const time = value => new Date(value).toISOString().slice(11, 19);
let history = [], selected = null;

function chart(id, rows, key, series=['kraken', 'coinbase']) {
  const canvas = $(id), box = canvas.getBoundingClientRect(), ratio = devicePixelRatio || 1;
  canvas.width = Math.round(box.width * ratio); canvas.height = Math.round(box.height * ratio);
  const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
  const w = box.width, h = box.height, left = 62, right = 12, top = 18, bottom = 25;
  const get = (row, venue) => {const v = row.venues[venue]; if (!v || v.status !== 'valid') return null;
    if (key === 'cost') return v.displayed_cost?.[venue === 'kraken' ? '1000' : '1000']?.buy?.cost_bps ?? null;
    return v[key] ?? null;};
  const values = rows.flatMap(row => series.map(venue => get(row, venue))).filter(v => v !== null && Number.isFinite(v));
  ctx.fillStyle = '#788293'; ctx.font = '11px system-ui';
  if (!values.length || rows.length < 2) {ctx.fillText('no usable observations for this measure', 15, h/2); return;}
  let min = Math.min(...values), max = Math.max(...values); const pad = (max-min)*.1 || Math.max(Math.abs(max)*.01, .001); min -= pad; max += pad;
  const start = +new Date(rows[0].time), end = +new Date(rows.at(-1).time);
  const x = row => left + (+new Date(row.time)-start)/(end-start || 1)*(w-left-right);
  const y = value => top + (max-value)/(max-min)*(h-top-bottom);
  for(let i=0;i<4;i++) {const v=min+(max-min)*i/3, yp=y(v); ctx.strokeStyle='#263244';ctx.beginPath();ctx.moveTo(left,yp);ctx.lineTo(w-right,yp);ctx.stroke();ctx.fillStyle='#a1aabd';ctx.fillText(v.toLocaleString('en-US',{maximumFractionDigits:2}),3,yp+4);}
  series.forEach((venue,index) => {ctx.strokeStyle=['#679bff','#e9a164'][index];ctx.lineWidth=1.8;ctx.beginPath();let previous=null;
    rows.forEach(row => {const value=get(row,venue), when=+new Date(row.time);if(value===null){previous=null;return;}
      if(previous===null || when-previous>1500)ctx.moveTo(x(row),y(value));else ctx.lineTo(x(row),y(value));previous=when;});ctx.stroke();});
  ctx.fillStyle='#a1aabd';ctx.fillText(time(rows[0].time),left,h-5);ctx.fillText(time(rows.at(-1).time),Math.max(left,w-68),h-5);
}

function venueCard(venue, value, fresh) {
  const card = text('article', '', 'venue panel');
  const heading = text('div', '', 'section-title'); heading.append(text('h2', venue),text('span', fresh ? label(value.status) : 'last: '+label(value.status), 'badge '+value.status));card.append(heading);
  card.append(text('p', value.reason, 'note'));
  const metrics = text('div','','metrics');
  [['mid-price',money(value.mid_price)],['spread',number(value.spread_bps)+' bps'],['10 bps depth',money(value.depth_usd)],['book age',value.book_age_ms == null ? '—' : number(value.book_age_ms/1000)+' s']].forEach(([name,v])=>{const cell=text('div','');cell.append(text('small',name),text('strong',v));metrics.append(cell);});card.append(metrics);
  if(value.depth_complete === false)card.append(text('p','the first 100 levels do not cover the full 10 bps band.','note'));
  const table=text('table','');const head=text('tr','');['order size','buy cost','sell cost'].forEach(v=>head.append(text('th',v)));table.append(head);
  ['1000','5000','10000'].forEach(size=>{const tr=text('tr','');tr.append(text('td',money(+size)));['buy','sell'].forEach(side=>{const cost=value.displayed_cost?.[size]?.[side];tr.append(text('td',cost?.cost_bps == null ? 'unavailable' : number(cost.cost_bps)+' bps'));});table.append(tr);});card.append(table);
  return card;
}

async function showEvent(id) {
  selected = id; const response = await fetch('/api/events/'+encodeURIComponent(id)); if(!response.ok)return;
  const event=await response.json();$('detail').hidden=false;$('event-title').textContent=event.id+' · '+label(event.classification);$('event-reason').textContent=event.reason+' · '+event.confidence+' confidence';
  chart('event-spread',event.timeline,'spread_bps');chart('event-depth',event.timeline,'depth_usd');chart('event-price',event.timeline,'mid_price');chart('event-cost',event.timeline,'cost',[event.affected_venues[0]]);
  const table=text('table',''), head=text('tr','');['UTC','venue','status','spread (bps)','depth (USD)','checks'].forEach(v=>head.append(text('th',v)));table.append(head);
  event.timeline.filter((_,i)=>i%Math.max(1,Math.ceil(event.timeline.length/100))===0).forEach(row=>Object.entries(row.venues).forEach(([venue,v])=>{const tr=text('tr','');[time(row.time),venue,label(v.status),number(v.spread_bps),money(v.depth_usd),v.reason].forEach(value=>tr.append(text('td',value)));table.append(tr);}));$('timeline').replaceChildren(table);
  const {timeline,...evidence}=event;$('evidence').textContent=JSON.stringify(evidence,null,2);
}

async function refresh() {
  try {const response=await fetch('/api/state');if(!response.ok)throw Error('recording is not ready yet');const data=await response.json();
    $('session').textContent=(data.synthetic?'synthetic demonstration · ':data.phase ? data.phase+' · ' : '')+(data.fresh?'recording live':'saved recording')+(data.latest?' · last observation '+time(data.latest.time)+' UTC':'');
    $('venues').replaceChildren(...Object.entries(data.latest?.venues || {}).map(([v,s])=>venueCard(v,s,data.fresh)));
    $('count').textContent=data.events.length+' events';$('events').replaceChildren();
    if(!data.events.length)$('events').append(text('p','no events yet. the tool keeps uncertain cases too.','empty'));
    data.events.slice().reverse().forEach(event=>{const button=text('button','', 'event');button.append(text('span',time(event.start)+' UTC'),text('strong',label(event.classification)),text('span',event.affected_venues.join(' + ')+' · '+event.status));button.onclick=()=>showEvent(event.id);$('events').append(button);});
    const hr=await fetch('/api/history');if(hr.ok){history=await hr.json();chart('spread',history,'spread_bps');chart('depth',history,'depth_usd');}
    if(selected)await showEvent(selected);
  } catch(error) {$('session').textContent=error.message;}
}
window.addEventListener('resize',()=>{chart('spread',history,'spread_bps');chart('depth',history,'depth_usd');if(selected)showEvent(selected);});
refresh();setInterval(refresh,2000);
