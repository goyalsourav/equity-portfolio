from flask import Flask, jsonify, request
import json, os, time

app = Flask(__name__)
DATA_FILE = "/tmp/portfolio_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"holdings": {}, "trades": []}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

price_cache = {}
CACHE_TTL = 300  # 5 minutes

def get_price_yfinance(symbol):
    """Fetch via yfinance using history() - most reliable method"""
    try:
        import yfinance as yf
        for suffix in [".NS", ".BO"]:
            try:
                t = yf.Ticker(symbol + suffix)
                hist = t.history(period="2d", interval="1d")
                if not hist.empty:
                    price = round(float(hist["Close"].iloc[-1]), 2)
                    if price > 0:
                        return price
            except:
                continue
    except Exception as e:
        print(f"yfinance error for {symbol}: {e}")
    return None

def get_price_nse(symbol):
    """Fallback: fetch from NSE India directly"""
    try:
        import urllib.request
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "*/*",
            "Referer": "https://www.nseindia.com"
        }
        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            price = data.get("priceInfo", {}).get("lastPrice")
            if price:
                return round(float(price), 2)
    except Exception as e:
        print(f"NSE error for {symbol}: {e}")
    return None

def get_price(symbol):
    now = time.time()
    if symbol in price_cache and now - price_cache[symbol]["ts"] < CACHE_TTL:
        return price_cache[symbol]["price"]

    price = get_price_yfinance(symbol)
    if not price:
        price = get_price_nse(symbol)

    if price:
        price_cache[symbol] = {"price": price, "ts": now}
    return price

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Equity Portfolio Dashboard</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@2.44.0/tabler-icons.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;background:#f5f5f0;color:#1a1a1a;min-height:100vh}
.topbar{background:#fff;border-bottom:1px solid #e0e0d8;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10;flex-wrap:wrap;gap:10px}
.topbar h1{font-size:18px;font-weight:600}
.topbar-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.last-upd{font-size:12px;color:#888;background:#f0f0ea;padding:4px 10px;border-radius:20px}
.main{max-width:1140px;margin:0 auto;padding:20px 16px}
.metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:18px}
.metric{background:#fff;border-radius:10px;padding:14px 16px;border:1px solid #e8e8e0}
.metric-label{font-size:11px;color:#888;margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}
.metric-value{font-size:22px;font-weight:600;color:#1a1a1a}
.metric-value.pos{color:#1D9E75}.metric-value.neg{color:#D85A30}
.metric-sub{font-size:12px;margin-top:2px;font-weight:500}
.metric-sub.pos{color:#1D9E75}.metric-sub.neg{color:#D85A30}
.chart-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px}
@media(max-width:640px){.chart-row{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid #e8e8e0;border-radius:12px;padding:16px 18px;margin-bottom:14px}
.card-title{font-size:11px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-size:11px;font-weight:600;color:#888;padding:7px 8px;border-bottom:1px solid #eee;white-space:nowrap}
td{padding:10px 8px;border-bottom:1px solid #f0f0ea;color:#1a1a1a;vertical-align:middle}
tr:last-child td{border-bottom:none}
tr:hover td{background:#fafaf8}
td.sym{font-weight:700;font-family:monospace;font-size:14px}
td.pos{color:#1D9E75;font-weight:600}
td.neg{color:#D85A30;font-weight:600}
.badge{display:inline-block;font-size:11px;padding:3px 9px;border-radius:20px;font-weight:600}
.badge-buy{background:#E1F5EE;color:#0F6E56}
.badge-sell{background:#FAECE7;color:#993C1D}
.btn{height:34px;padding:0 14px;font-size:13px;border-radius:8px;border:1px solid #d0d0c8;background:#fff;color:#1a1a1a;cursor:pointer;font-weight:500;white-space:nowrap;display:inline-flex;align-items:center;gap:5px}
.btn:hover{background:#f0f0ea}
.btn-primary{background:#1D9E75;color:#fff;border-color:#1D9E75}
.btn-primary:hover{background:#0F6E56}
.btn-refresh{background:#378ADD;color:#fff;border-color:#378ADD}
.btn-refresh:hover{background:#185FA5}
.btn-danger{background:#D85A30;color:#fff;border-color:#D85A30}
.btn-danger:hover{background:#993C1D}
.btn-icon{height:28px;width:28px;padding:0;display:inline-flex;align-items:center;justify-content:center;border-radius:6px;border:1px solid #e0e0d8;background:#fff;cursor:pointer;color:#777;font-size:15px;transition:all .15s}
.btn-icon.sell-btn:hover{color:#D85A30;border-color:#D85A30}
.btn-icon.del:hover{color:#D85A30;border-color:#D85A30}
.field{display:flex;flex-direction:column;gap:4px}
.field label{font-size:11px;color:#666;font-weight:600}
.field input,.field select{height:36px;border:1px solid #d0d0c8;border-radius:8px;padding:0 10px;font-size:13px;color:#1a1a1a;background:#fff;outline:none;transition:border .15s}
.field input:focus,.field select:focus{border-color:#1D9E75;box-shadow:0 0 0 3px rgba(29,158,117,.1)}
.form-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px;margin-bottom:12px}
.form-msg{font-size:12px;color:#D85A30;margin-top:6px;display:none;padding:6px 10px;background:#FFF3F0;border-radius:6px;border:1px solid #F5C4B3}
.empty{text-align:center;padding:2.5rem;color:#aaa;font-size:13px}
.empty i{font-size:32px;display:block;margin-bottom:8px;opacity:.4}
.legend{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:10px;font-size:12px;color:#555}
.legend span{display:flex;align-items:center;gap:5px}
.legend-dot{width:10px;height:10px;border-radius:2px;flex-shrink:0}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200;align-items:center;justify-content:center;padding:16px}
.modal-overlay.open{display:flex}
.modal{background:#fff;border-radius:14px;padding:24px;width:100%;max-width:500px;box-shadow:0 20px 60px rgba(0,0,0,.15)}
.modal h3{font-size:16px;font-weight:600;margin-bottom:6px;display:flex;align-items:center;gap:8px}
.modal-sub{font-size:13px;color:#888;margin-bottom:18px}
.modal-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:20px;padding-top:16px;border-top:1px solid #f0f0ea}
.divider{height:1px;background:#f0f0ea;margin:14px 0}
.info-box{background:#f8f8f5;border-radius:8px;padding:12px 14px;font-size:13px;color:#555;margin-bottom:16px;line-height:1.6}
.info-box strong{color:#1a1a1a}
.tag{display:inline-block;font-size:10px;padding:2px 6px;border-radius:10px;background:#f0f0ea;color:#888;margin-left:4px;vertical-align:middle}
.actions-cell{display:flex;gap:4px;align-items:center}
.chart-empty{display:flex;align-items:center;justify-content:center;height:180px;color:#bbb;font-size:13px;flex-direction:column;gap:8px}
.chart-empty i{font-size:28px}
.spinning{animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.price-live{font-size:10px;background:#E1F5EE;color:#0F6E56;padding:2px 6px;border-radius:10px;font-weight:600;margin-left:4px;vertical-align:middle}
.price-na{font-size:10px;background:#f0f0ea;color:#888;padding:2px 6px;border-radius:10px;margin-left:4px;vertical-align:middle}
.toast{position:fixed;bottom:24px;right:24px;background:#1a1a1a;color:#fff;padding:10px 18px;border-radius:10px;font-size:13px;z-index:999;display:none;align-items:center;gap:8px;max-width:340px}
.toast.show{display:flex}
.toast.success{background:#1D9E75}
.toast.error{background:#D85A30}
.price-refresh-time{font-size:11px;color:#aaa;margin-top:4px}
</style>
</head>
<body>
<div class="topbar">
  <h1>📊 Equity Portfolio</h1>
  <div class="topbar-right">
    <span class="last-upd" id="last-updated">Loading…</span>
    <button class="btn btn-refresh" onclick="refreshPrices()" id="refresh-btn">
      <i class="ti ti-refresh" id="refresh-icon"></i> Refresh prices
    </button>
    <button class="btn btn-primary" onclick="openAddModal()"><i class="ti ti-plus"></i> Add stock</button>
  </div>
</div>
<div class="main">
  <div id="price-refresh-info" style="display:none;font-size:12px;color:#888;margin-bottom:12px;padding:8px 12px;background:#fff;border-radius:8px;border:1px solid #e8e8e0"></div>
  <div class="metric-grid" id="metrics"></div>
  <div class="chart-row">
    <div class="card">
      <div class="card-title">Allocation</div>
      <div class="legend" id="pie-legend"></div>
      <div id="pie-wrap"><div class="chart-empty"><i class="ti ti-chart-donut"></i>No active holdings</div></div>
    </div>
    <div class="card">
      <div class="card-title">Unrealised P&amp;L per stock</div>
      <div id="bar-wrap"><div class="chart-empty"><i class="ti ti-chart-bar"></i>No holdings with live price</div></div>
    </div>
  </div>
  <div class="card">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
      <div class="card-title" style="margin-bottom:0">Holdings</div>
    </div>
    <div id="holdings-wrap"><p class="empty"><i class="ti ti-briefcase"></i>No holdings yet. Click "Add stock" to get started.</p></div>
  </div>
  <div class="card">
    <div class="card-title">Trade log</div>
    <div id="log-wrap"><p class="empty"><i class="ti ti-list"></i>No trades yet.</p></div>
  </div>
</div>

<!-- ADD MODAL -->
<div class="modal-overlay" id="add-modal">
  <div class="modal">
    <h3><i class="ti ti-plus" style="color:#1D9E75"></i> Add stock</h3>
    <p class="modal-sub">Type the NSE symbol — current price is auto-fetched from NSE.</p>
    <div class="form-row">
      <div class="field">
        <label>Symbol * (NSE)</label>
        <input type="text" id="a-sym" placeholder="e.g. TCS, RELIANCE, INFY" style="text-transform:uppercase;font-family:monospace;font-weight:700">
      </div>
      <div class="field">
        <label>Sector</label>
        <select id="a-sector">
          <option>IT</option><option>Finance</option><option>FMCG</option>
          <option>Pharma</option><option>Auto</option><option>Energy</option>
          <option>Infra</option><option>Metals</option><option>Other</option>
        </select>
      </div>
    </div>
    <div class="form-row">
      <div class="field">
        <label>Qty *</label>
        <input type="number" id="a-qty" placeholder="0" min="1" step="1">
      </div>
      <div class="field">
        <label>Buy price (₹) *</label>
        <input type="number" id="a-price" placeholder="0.00" min="0.01" step="0.01">
      </div>
      <div class="field">
        <label>Date</label>
        <input type="date" id="a-date">
      </div>
    </div>
    <div class="divider"></div>
    <div class="form-row">
      <div class="field">
        <label>Current price (₹) <span class="tag">auto-fetched from NSE</span></label>
        <input type="number" id="a-cmp" placeholder="Type symbol above to fetch…" step="0.01">
      </div>
    </div>
    <p class="form-msg" id="add-msg"></p>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal('add-modal')">Cancel</button>
      <button class="btn btn-primary" onclick="confirmAdd()"><i class="ti ti-check"></i> Add to portfolio</button>
    </div>
  </div>
</div>

<!-- SELL MODAL -->
<div class="modal-overlay" id="sell-modal">
  <div class="modal">
    <h3><i class="ti ti-trending-down" style="color:#D85A30"></i> Sell — <span id="sell-sym-label" style="font-family:monospace;color:#D85A30"></span></h3>
    <p class="modal-sub">Realised P&amp;L will be recorded in the trade log.</p>
    <div class="info-box" id="sell-info"></div>
    <div class="form-row">
      <div class="field">
        <label>Qty to sell *</label>
        <input type="number" id="s-qty" placeholder="0" min="1" step="1">
      </div>
      <div class="field">
        <label>Sell price (₹) *</label>
        <input type="number" id="s-price" placeholder="0.00" min="0.01" step="0.01">
      </div>
      <div class="field">
        <label>Date</label>
        <input type="date" id="s-date">
      </div>
    </div>
    <p class="form-msg" id="sell-msg"></p>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal('sell-modal')">Cancel</button>
      <button class="btn btn-danger" onclick="confirmSell()"><i class="ti ti-check"></i> Confirm sell</button>
    </div>
  </div>
</div>

<!-- DELETE MODAL -->
<div class="modal-overlay" id="del-modal">
  <div class="modal">
    <h3><i class="ti ti-alert-triangle" style="color:#D85A30"></i> Remove holding</h3>
    <p class="modal-sub">Remove <strong id="del-sym-label"></strong> and all its trade history?</p>
    <div class="modal-actions">
      <button class="btn" onclick="closeModal('del-modal')">Cancel</button>
      <button class="btn btn-danger" onclick="confirmDelete()"><i class="ti ti-trash"></i> Yes, remove</button>
    </div>
  </div>
</div>
<div class="toast" id="toast"></div>

<script>
const COLORS=['#1D9E75','#378ADD','#D85A30','#7F77DD','#BA7517','#D4537E','#639922','#E24B4A','#888780','#5DCAA5'];
let holdings={},trades=[],pieChart,barChart,activeSym=null;

function showToast(msg,type='success'){
  const t=document.getElementById('toast');
  t.textContent=msg;t.className='toast show '+type;
  setTimeout(()=>t.className='toast',3500);
}
async function api(url,opts={}){
  const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opts});
  return r.json();
}
async function loadFromServer(){
  try{const d=await api('/api/portfolio');holdings=d.holdings||{};trades=d.trades||[];}
  catch(e){holdings={};trades=[];}
}
async function saveToServer(){
  try{await api('/api/portfolio',{method:'POST',body:JSON.stringify({holdings,trades})});}
  catch(e){showToast('Save failed','error');}
}

// ── CLIENT-SIDE PRICE FETCH ──
// Render's server IP gets blocked by Yahoo/NSE (datacenter IP blocking).
// So we fetch directly from the user's browser instead, via a free CORS proxy.
// Try multiple proxies in sequence for resilience.
const CORS_PROXIES = [
  url => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
  url => `https://corsproxy.io/?url=${encodeURIComponent(url)}`,
  url => `https://thingproxy.freeboard.io/fetch/${url}`
];

async function fetchYahooPrice(symbol){
  for(const suffix of ['.NS','.BO']){
    const yahooUrl = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}${suffix}?interval=1d&range=5d`;
    for(const proxyFn of CORS_PROXIES){
      try{
        const proxied = proxyFn(yahooUrl);
        const res = await fetch(proxied, { signal: AbortSignal.timeout(8000) });
        if(!res.ok) continue;
        const data = await res.json();
        const result = data?.chart?.result?.[0];
        const price = result?.meta?.regularMarketPrice;
        if(price && price > 0){
          return Math.round(price * 100) / 100;
        }
      }catch(e){ continue; }
    }
  }
  return null;
}

async function refreshPrices(){
  const syms=Object.keys(holdings);
  if(!syms.length){showToast('No holdings to refresh','error');return;}
  const icon=document.getElementById('refresh-icon'),btn=document.getElementById('refresh-btn');
  icon.classList.add('spinning');btn.disabled=true;
  showToast(`Fetching prices for ${syms.join(', ')}…`,'success');
  let updated=0,failed=[];
  for(const s of syms){
    const price = await fetchYahooPrice(s);
    if(price){ holdings[s].cmp = price; updated++; }
    else failed.push(s);
  }
  await saveToServer();render();
  const infoEl=document.getElementById('price-refresh-info');
  const now=new Date().toLocaleTimeString('en-IN');
  let msg=`✓ Prices refreshed at ${now} — ${updated}/${syms.length} updated`;
  if(failed.length) msg+=` | Not found: ${failed.join(', ')} (check symbol spelling)`;
  if(infoEl){ infoEl.innerHTML=msg; infoEl.style.display='block'; }
  showToast(updated>0?`✓ ${updated}/${syms.length} prices updated`:'Could not fetch any prices — try again','success');
  icon.classList.remove('spinning');btn.disabled=false;
}

let symTimer=null;
function onSymInput(){
  clearTimeout(symTimer);
  const sym=document.getElementById('a-sym').value.trim().toUpperCase();
  const cmpEl=document.getElementById('a-cmp');
  cmpEl.value='';cmpEl.style.borderColor='';
  if(sym.length<2){cmpEl.placeholder='Type symbol above to fetch…';return;}
  cmpEl.placeholder='Fetching…';
  symTimer=setTimeout(async()=>{
    const price = await fetchYahooPrice(sym);
    if(price){cmpEl.value=price;cmpEl.style.borderColor='#1D9E75';cmpEl.placeholder='';}
    else{cmpEl.placeholder='Not found — enter manually';cmpEl.style.borderColor='#D85A30';}
  },800);
}

function fmt(n){
  if(n===null||n===undefined||isNaN(n))return'—';
  return'₹'+Number(n).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
}
function fmtPct(n){
  if(n===null||n===undefined||isNaN(n))return'';
  return(n>=0?'+':'')+n.toFixed(2)+'%';
}
function today(){return new Date().toISOString().split('T')[0];}
function closeModal(id){document.getElementById(id).classList.remove('open');activeSym=null;}
function showMsg(id,msg){const el=document.getElementById(id);el.textContent=msg;el.style.display='block';}
function clearMsg(id){document.getElementById(id).style.display='none';}

document.querySelectorAll('.modal-overlay').forEach(el=>{
  el.addEventListener('click',e=>{if(e.target===el)el.classList.remove('open');});
});
document.addEventListener('keydown',e=>{
  if(e.key==='Escape')document.querySelectorAll('.modal-overlay.open').forEach(el=>el.classList.remove('open'));
});

function openAddModal(){
  ['a-sym','a-qty','a-price','a-cmp'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('a-cmp').style.borderColor='';
  document.getElementById('a-cmp').placeholder='Type symbol above to fetch…';
  document.getElementById('a-date').value=today();
  clearMsg('add-msg');
  document.getElementById('add-modal').classList.add('open');
  setTimeout(()=>document.getElementById('a-sym').focus(),120);
}
async function confirmAdd(){
  const sym=document.getElementById('a-sym').value.trim().toUpperCase();
  const qty=parseFloat(document.getElementById('a-qty').value);
  const price=parseFloat(document.getElementById('a-price').value);
  const cmpRaw=document.getElementById('a-cmp').value.trim();
  const cmp=cmpRaw?parseFloat(cmpRaw):null;
  const sector=document.getElementById('a-sector').value;
  const date=document.getElementById('a-date').value||today();
  if(!sym)return showMsg('add-msg','Enter a symbol.');
  if(isNaN(qty)||qty<=0)return showMsg('add-msg','Enter a valid quantity.');
  if(isNaN(price)||price<=0)return showMsg('add-msg','Enter a valid buy price.');
  if(!holdings[sym])holdings[sym]={qty:0,cost:0,cmp:null,sector};
  const h=holdings[sym];
  h.cost=(h.cost*h.qty+price*qty)/(h.qty+qty);
  h.qty+=qty;
  if(cmp&&!isNaN(cmp)&&cmp>0)h.cmp=cmp;
  h.sector=sector;
  trades.unshift({sym,type:'buy',qty,price,sector,date});
  await saveToServer();render();closeModal('add-modal');
  showToast(`✓ Added ${qty} × ${sym}`,'success');
}
function openSellModal(sym){
  activeSym=sym;const h=holdings[sym];
  document.getElementById('sell-sym-label').textContent=sym;
  document.getElementById('sell-info').innerHTML=
    `Qty held: <strong>${h.qty} shares</strong> &nbsp;|&nbsp; Avg cost: <strong>${fmt(h.cost)}</strong>${h.cmp?` &nbsp;|&nbsp; CMP: <strong>${fmt(h.cmp)}</strong>`:''}`;
  document.getElementById('s-qty').value='';
  document.getElementById('s-price').value=h.cmp||'';
  document.getElementById('s-date').value=today();
  clearMsg('sell-msg');
  document.getElementById('sell-modal').classList.add('open');
  setTimeout(()=>document.getElementById('s-qty').focus(),120);
}
async function confirmSell(){
  const qty=parseFloat(document.getElementById('s-qty').value);
  const price=parseFloat(document.getElementById('s-price').value);
  const date=document.getElementById('s-date').value||today();
  const h=holdings[activeSym];
  if(isNaN(qty)||qty<=0)return showMsg('sell-msg','Enter a valid quantity.');
  if(qty>h.qty)return showMsg('sell-msg',`You only hold ${h.qty} shares.`);
  if(isNaN(price)||price<=0)return showMsg('sell-msg','Enter a valid sell price.');
  const realizedPnl=(price-h.cost)*qty;
  trades.unshift({sym:activeSym,type:'sell',qty,price,sector:h.sector,date,realizedPnl,avgCost:h.cost});
  h.qty-=qty;h.cmp=price;
  if(h.qty===0)delete holdings[activeSym];
  await saveToServer();render();closeModal('sell-modal');
  showToast(`Sold ${qty} × ${activeSym} | P&L: ${fmt(realizedPnl)}`,realizedPnl>=0?'success':'error');
}
function openDeleteModal(sym){
  activeSym=sym;
  document.getElementById('del-sym-label').textContent=sym;
  document.getElementById('del-modal').classList.add('open');
}
async function confirmDelete(){
  trades=trades.filter(t=>t.sym!==activeSym);
  delete holdings[activeSym];
  await saveToServer();render();closeModal('del-modal');
  showToast('Holding removed');
}

function render(){
  const syms=Object.keys(holdings);
  let totalInvested=0,totalCurrent=0,totalUnrealised=0;
  syms.forEach(s=>{
    const h=holdings[s],inv=h.cost*h.qty;
    totalInvested+=inv;
    if(h.cmp){totalCurrent+=h.cmp*h.qty;totalUnrealised+=(h.cmp-h.cost)*h.qty;}
    else totalCurrent+=inv;
  });
  const totalRealised=trades.filter(t=>t.type==='sell').reduce((a,t)=>a+(t.realizedPnl||0),0);
  const totalPnl=totalUnrealised+totalRealised;
  const unrealisedPct=totalInvested>0?(totalUnrealised/totalInvested)*100:0;
  const lastTrade=trades.find(t=>t.type==='buy'||t.type==='sell');
  document.getElementById('last-updated').textContent=lastTrade?'Updated: '+lastTrade.date:'No trades yet';

  document.getElementById('metrics').innerHTML=`
    <div class="metric"><div class="metric-label">Invested</div><div class="metric-value">${fmt(totalInvested)}</div></div>
    <div class="metric"><div class="metric-label">Current value</div><div class="metric-value">${fmt(totalCurrent)}</div></div>
    <div class="metric"><div class="metric-label">Unrealised P&amp;L</div><div class="metric-value ${totalUnrealised>=0?'pos':'neg'}">${fmt(totalUnrealised)}</div><div class="metric-sub ${totalUnrealised>=0?'pos':'neg'}">${fmtPct(unrealisedPct)}</div></div>
    <div class="metric"><div class="metric-label">Realised P&amp;L</div><div class="metric-value ${totalRealised>=0?'pos':'neg'}">${fmt(totalRealised)}</div><div class="metric-sub" style="color:#888">from ${trades.filter(t=>t.type==='sell').length} sell(s)</div></div>
    <div class="metric"><div class="metric-label">Total P&amp;L</div><div class="metric-value ${totalPnl>=0?'pos':'neg'}">${fmt(totalPnl)}</div></div>
    <div class="metric"><div class="metric-label">Stocks held</div><div class="metric-value">${syms.length}</div></div>`;

  if(!syms.length){
    document.getElementById('holdings-wrap').innerHTML='<p class="empty"><i class="ti ti-briefcase"></i>No active holdings.</p>';
  }else{
    const rows=syms.map(s=>{
      const h=holdings[s],inv=h.cost*h.qty,hasCmp=!!h.cmp;
      const cur=hasCmp?h.cmp*h.qty:null,p=hasCmp?cur-inv:null,pct=hasCmp&&inv>0?(p/inv)*100:null;
      return`<tr>
        <td class="sym">${s}</td>
        <td><span style="font-size:11px;background:#f0f0ea;padding:2px 7px;border-radius:10px;color:#666">${h.sector}</span></td>
        <td>${h.qty}</td><td>${fmt(h.cost)}</td>
        <td>${hasCmp?fmt(h.cmp):'<span style="color:#bbb;font-style:italic;font-size:12px">Not set</span>'}
          <span class="${hasCmp?'price-live':'price-na'}">${hasCmp?'LIVE':'—'}</span></td>
        <td>${fmt(inv)}</td>
        <td>${cur!==null?fmt(cur):'<span style="color:#bbb">—</span>'}</td>
        <td>${p===null?'<span style="color:#bbb">—</span>':`<span class="${p>=0?'pos':'neg'}">${fmt(p)}</span><br><span style="font-size:11px;color:${p>=0?'#1D9E75':'#D85A30'}">${fmtPct(pct)}</span>`}</td>
        <td><div class="actions-cell">
          <button class="btn-icon sell-btn" onclick="openSellModal('${s}')" title="Sell"><i class="ti ti-trending-down"></i></button>
          <button class="btn-icon del" onclick="openDeleteModal('${s}')" title="Remove"><i class="ti ti-trash"></i></button>
        </div></td></tr>`;
    }).join('');
    document.getElementById('holdings-wrap').innerHTML=`<table><thead><tr><th>Symbol</th><th>Sector</th><th>Qty</th><th>Avg cost</th><th>CMP</th><th>Invested</th><th>Current</th><th>P&amp;L</th><th></th></tr></thead><tbody>${rows}</tbody></table>`;
  }

  const visT=trades.filter(t=>t.type==='buy'||t.type==='sell');
  if(!visT.length){
    document.getElementById('log-wrap').innerHTML='<p class="empty"><i class="ti ti-list"></i>No trades yet.</p>';
  }else{
    const rows=visT.map(t=>{
      const pnlCell=t.type==='sell'&&t.realizedPnl!==undefined?`<span class="${t.realizedPnl>=0?'pos':'neg'}">${fmt(t.realizedPnl)}</span>`:'—';
      return`<tr><td style="color:#888">${t.date}</td><td class="sym">${t.sym}</td>
        <td><span class="badge badge-${t.type}">${t.type.toUpperCase()}</span></td>
        <td>${t.qty}</td><td>${fmt(t.price)}</td>
        <td><span style="font-size:11px;background:#f0f0ea;padding:2px 7px;border-radius:10px;color:#666">${t.sector}</span></td>
        <td>${pnlCell}</td></tr>`;
    }).join('');
    document.getElementById('log-wrap').innerHTML=`<table><thead><tr><th>Date</th><th>Symbol</th><th>Type</th><th>Qty</th><th>Price</th><th>Sector</th><th>Realised P&amp;L</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
  updateCharts(syms);
}

function updateCharts(syms){
  if(pieChart){pieChart.destroy();pieChart=null;}
  if(barChart){barChart.destroy();barChart=null;}
  const pieWrap=document.getElementById('pie-wrap'),barWrap=document.getElementById('bar-wrap');
  if(!syms.length){
    pieWrap.innerHTML='<div class="chart-empty"><i class="ti ti-chart-donut"></i>No active holdings</div>';
    barWrap.innerHTML='<div class="chart-empty"><i class="ti ti-chart-bar"></i>No holdings with live price</div>';
    document.getElementById('pie-legend').innerHTML='';return;
  }
  const pieData=syms.map(s=>(holdings[s].cmp||holdings[s].cost)*holdings[s].qty);
  const total=pieData.reduce((a,b)=>a+b,0);
  const colors=syms.map((_,i)=>COLORS[i%COLORS.length]);
  document.getElementById('pie-legend').innerHTML=syms.map((s,i)=>
    `<span><span class="legend-dot" style="background:${colors[i]}"></span>${s} ${total>0?((pieData[i]/total)*100).toFixed(1)+'%':''}</span>`).join('');
  pieWrap.innerHTML='<div style="position:relative;height:190px"><canvas id="pieChart"></canvas></div>';
  pieChart=new Chart(document.getElementById('pieChart'),{type:'doughnut',
    data:{labels:syms,datasets:[{data:pieData,backgroundColor:colors,borderWidth:2,borderColor:'#fff'}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>` ${fmt(ctx.raw)}`}}}}});
  const barSyms=syms.filter(s=>holdings[s].cmp);
  if(!barSyms.length){barWrap.innerHTML='<div class="chart-empty"><i class="ti ti-refresh"></i>Click "Refresh prices" to load live prices</div>';return;}
  const barData=barSyms.map(s=>parseFloat(((holdings[s].cmp-holdings[s].cost)*holdings[s].qty).toFixed(2)));
  const barColors=barData.map(v=>v>=0?'#1D9E75':'#D85A30');
  barWrap.innerHTML=`<div style="position:relative;height:${Math.max(200,barSyms.length*50+60)}px"><canvas id="barChart"></canvas></div>`;
  barChart=new Chart(document.getElementById('barChart'),{type:'bar',
    data:{labels:barSyms,datasets:[{data:barData,backgroundColor:barColors,borderRadius:4}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},tooltip:{callbacks:{label:ctx=>` ${fmt(ctx.raw)}`}}},
      scales:{x:{ticks:{font:{size:11},color:'#888'},grid:{display:false}},
        y:{ticks:{callback:v=>{const a=Math.abs(v);return(v<0?'-':'')+'₹'+(a>=100000?(a/100000).toFixed(1)+'L':a>=1000?(a/1000).toFixed(0)+'k':a);},font:{size:11},color:'#888'},grid:{color:'rgba(0,0,0,.05)'}}}}});
}

document.getElementById('a-sym').addEventListener('input',onSymInput);
document.getElementById('a-date').value=today();
loadFromServer().then(render);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    return jsonify(load_data())

@app.route("/api/portfolio", methods=["POST"])
def save_portfolio():
    save_data(request.get_json())
    return jsonify({"status": "ok"})

@app.route("/api/prices", methods=["POST"])
def get_prices():
    symbols = request.get_json().get("symbols", [])
    result = {}
    for s in symbols:
        p = get_price(s)
        if p:
            result[s] = p
    return jsonify(result)

@app.route("/api/price/<symbol>")
def get_single_price(symbol):
    price = get_price(symbol.upper())
    if price:
        return jsonify({"symbol": symbol.upper(), "price": price})
    return jsonify({"error": "not found"}), 404

@app.route("/api/debug/<symbol>")
def debug_price(symbol):
    """Debug endpoint to see what's happening with price fetch"""
    import traceback
    results = {}
    try:
        import yfinance as yf
        for suffix in [".NS", ".BO"]:
            try:
                t = yf.Ticker(symbol.upper() + suffix)
                hist = t.history(period="2d", interval="1d")
                results[suffix] = {
                    "empty": hist.empty,
                    "price": round(float(hist["Close"].iloc[-1]), 2) if not hist.empty else None
                }
            except Exception as e:
                results[suffix] = {"error": str(e)}
    except Exception as e:
        results["yfinance_import"] = {"error": str(e)}
    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
