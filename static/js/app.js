// MedSearch — the page's behaviour (moved out of templates/index.html).
// Server values come from window.MS, set in the template.
// ── State ─────────────────────────────────────────────────────────────────
let allArticles    = [];

// ── Onboarding (bilingual welcome popup) ───────────────────────────────────
const ONBOARD_CONTENT = {
  en: {
    welcome: 'Welcome to <span class="accent">MedSearch</span>',
    purpose: 'A quick setup guide to get you searching the medical literature.',
    closeBtn: 'Get started',
    dismiss: "Don't show this again",
    sections: [
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-key\"/></svg> Set up your API key (for AI features)',
        steps: [
          'Click <strong>Settings</strong> in the bar at the bottom of the window.',
          'Paste your <strong>Anthropic key</strong> to enable AI summaries and synthesis. Get one free at <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>.',
          'Click <strong>Save</strong>. That\'s the only key you need for the AI features.',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-search\"/></svg> How to search',
        steps: [
          'Type your topic in the bar at the top and press <strong>Search</strong>.',
          'Click the <strong>sources</strong> button beside Search to tick the databases you want (PubMed, Cochrane and others are free).',
          'Keep <strong>Strict</strong> on for focused results; turn it off to search more broadly.',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Useful features',
        steps: [
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-star\"/></svg> Save</strong> a search to re-run it later with one click.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Explain</strong> any article for a plain-language breakdown.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-cite\"/></svg> Citations</strong> shows what a paper cites and what cites it.',
          '<strong>Institutional access:</strong> add your university\'s library proxy in Settings, and paywalled papers your institution subscribes to open through your library login. Pick it under <strong>Options</strong> in the bottom bar.',
        ],
      },
    ],
    note: '<strong>Optional keys:</strong> Scopus, Web of Science and a PubMed key add more sources and higher limits — but everything works without them.',
    note2: '<strong>Scopus &amp; Web of Science:</strong> these only work from your <strong>institution\'s network</strong>. From home, connect to your university VPN, or ask your library for an Elsevier "institutional token" and add it in Settings. If you see a 401 error, you\'re off-network.',
  },
  it: {
    welcome: 'Benvenuto su <span class="accent">MedSearch</span>',
    purpose: 'Una breve guida per iniziare a cercare nella letteratura medica.',
    closeBtn: 'Inizia',
    dismiss: 'Non mostrare più',
    sections: [
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-key\"/></svg> Configura la tua chiave API (per le funzioni IA)',
        steps: [
          'Clicca <strong>Settings</strong> nella barra in basso nella finestra.',
          'Incolla la tua <strong>chiave Anthropic</strong> per attivare i riassunti e la sintesi IA. Ottienine una gratis su <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>.',
          'Clicca <strong>Save</strong>. È l\'unica chiave necessaria per le funzioni IA.',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-search\"/></svg> Come cercare',
        steps: [
          'Scrivi l\'argomento nella barra in alto e premi <strong>Search</strong>.',
          'Clicca il pulsante delle <strong>fonti</strong> accanto a Search per scegliere i database (PubMed, Cochrane e altri sono gratuiti).',
          'Tieni <strong>Strict</strong> attivo per risultati mirati; disattivalo per cercare in modo più ampio.',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Funzioni utili',
        steps: [
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-star\"/></svg> Save</strong> salva una ricerca per rieseguirla con un clic.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Explain</strong> spiega qualsiasi articolo in linguaggio semplice.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-cite\"/></svg> Citations</strong> mostra cosa cita un articolo e da chi è citato.',
          '<strong>Accesso istituzionale:</strong> aggiungi il proxy della biblioteca universitaria nelle Impostazioni e gli articoli a pagamento a cui la tua istituzione è abbonata si apriranno con le tue credenziali. Selezionalo in <strong>Options</strong> nella barra in basso.',
        ],
      },
    ],
    note: '<strong>Chiavi opzionali:</strong> Scopus, Web of Science e una chiave PubMed aggiungono più fonti e limiti più alti — ma tutto funziona anche senza.',
    note2: '<strong>Scopus e Web of Science:</strong> funzionano solo dalla <strong>rete della tua istituzione</strong>. Da casa, connettiti alla VPN dell\'università, oppure chiedi alla biblioteca un "institutional token" Elsevier e inseriscilo nelle Impostazioni. Se vedi un errore 401, sei fuori dalla rete.',
  },
};

let _onboardLang = 'en';

function renderOnboardBody() {
  const t = ONBOARD_CONTENT[_onboardLang];
  let html = `<div class="onboard-welcome">${t.welcome}</div>
    <div class="onboard-purpose">${t.purpose}</div>`;
  t.sections.forEach(sec => {
    html += `<div class="onboard-section"><h3>${sec.title}</h3>`;
    sec.steps.forEach((step, i) => {
      html += `<div class="onboard-step">
        <span class="onboard-step-num">${i+1}</span>
        <span>${step}</span></div>`;
    });
    html += `</div>`;
  });
  html += `<div class="onboard-note">${t.note}</div>`;
  if (t.note2) html += `<div class="onboard-note onboard-note-warn">${t.note2}</div>`;
  document.getElementById('onboardBody').innerHTML = html;
  document.getElementById('onboardCloseBtn').textContent = t.closeBtn;
  document.getElementById('onboardDismissLabel').textContent = t.dismiss;
}

function setOnboardLang(lang) {
  _onboardLang = lang;
  document.getElementById('langEn').classList.toggle('active', lang === 'en');
  document.getElementById('langIt').classList.toggle('active', lang === 'it');
  renderOnboardBody();
}

function openOnboarding() {
  setOnboardLang('en');
  openOverlay('onboardOverlay');
}

function closeOnboarding() {
  // If "don't show again" is ticked, persist it server-side
  if (document.getElementById('onboardDismissChk').checked) {
    fetch('/onboarding/dismiss', {method: 'POST'});
  }
  closeOverlay('onboardOverlay');
}

// Show automatically on first launch (server decides via show_onboarding flag)
const _onboardingShowing = MS.showOnboarding;
if (_onboardingShowing) window.addEventListener('load', () => { openOnboarding(); });

// ── Auto-update ────────────────────────────────────────────────────────────
function checkForUpdate() {
  fetch('/update/check')
    .then(r => r.json())
    .then(data => {
      if (!data.ok || !data.update_available) return;   // silent if up-to-date or offline
      const text = document.getElementById('updateText');
      const actions = document.getElementById('updateActions');
      const btn = document.getElementById('updateNowBtn');
      if (data.can_apply) {
        text.innerHTML = `A new version of MedSearch is available.<br><br>
          <span class="ver">${escHtml(data.local)}</span> → <span class="ver">${escHtml(data.remote)}</span>`;
        btn.style.display = '';
      } else {
        // Not a git checkout (e.g. a frozen .app) — can't auto-apply. Point
        // them at the source install, which DOES auto-update.
        text.innerHTML = `A new version (<span class="ver">${escHtml(data.remote)}</span>) is available, but this copy can't auto-update.<br><br>
          To get automatic updates, run MedSearch from a clone of the GitHub repo
          (double-click <span class="mono">MedSearch.command</span>) instead of the packaged app.`;
        btn.style.display = 'none';
      }
      openOverlay('updateOverlay');
    })
    .catch(() => { /* offline — stay silent */ });
}

// The server starts a fresh copy once this one has exited, so the window
// closes and reopens on its own.
function restartApp() {
  document.getElementById('updateActions').style.display = 'none';
  document.getElementById('updateProgress').style.display = 'flex';
  document.getElementById('updateProgressText').textContent = 'Restarting MedSearch…';
  fetch('/app/restart', {method: 'POST'})
    .then(r => r.json())
    .then(d => { if (!d.ok) fail(d.message || 'Please quit and reopen MedSearch.', "Couldn't restart"); })
    .catch(() => { /* the server went away mid-response: that is the restart */ });
}

function closeUpdate() {
  closeOverlay('updateOverlay');
}

function applyUpdate() {
  document.getElementById('updateActions').style.display = 'none';
  document.getElementById('updateProgress').style.display = 'flex';
  document.getElementById('updateProgressText').textContent = 'Downloading update…';

  fetch('/update/apply', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      const prog = document.getElementById('updateProgress');
      const title = document.getElementById('updateTitle');
      const text = document.getElementById('updateText');
      if (data.ok) {
        prog.style.display = 'none';
        if (data.unchanged) {
          title.textContent = 'Already up to date';
          text.innerHTML = escHtml(data.message || `You're on the latest version.`);
        } else {
          title.textContent = 'Update complete';
          if (data.can_restart) {
            text.innerHTML = `Updated to <span class="ver">${escHtml(data.new_version)}</span>.<br><br>
              MedSearch needs to restart to use it. It takes a few seconds.`;
            document.getElementById('updateActions').style.display = 'flex';
            document.getElementById('updateActions').innerHTML =
              '<button class="btn-secondary" onclick="closeUpdate()">Later</button>' +
              '<button class="btn-primary" onclick="restartApp()">Restart now</button>';
            return;
          }
          text.innerHTML = `Updated to <span class="ver">${escHtml(data.new_version)}</span>.<br><br>
            Please <strong>close and reopen MedSearch</strong> to use the new version.`;
        }
        document.getElementById('updateActions').style.display = 'flex';
        document.getElementById('updateActions').innerHTML =
          '<button class="btn-primary" onclick="closeUpdate()">Got it</button>';
      } else {
        prog.style.display = 'none';
        title.textContent = 'Update failed';
        text.innerHTML = escHtml(data.message || 'Could not update.') +
          (data.error ? `<br><br><span style="font-size:0.72rem;color:var(--text3);font-family:var(--mono)">${escHtml(data.error)}</span>` : '');
        document.getElementById('updateActions').style.display = 'flex';
        document.getElementById('updateActions').innerHTML =
          '<button class="btn-secondary" onclick="closeUpdate()">Close</button>';
      }
    })
    .catch(e => {
      document.getElementById('updateProgress').style.display = 'none';
      document.getElementById('updateTitle').textContent = 'Update failed';
      document.getElementById('updateText').textContent = 'Could not reach the update service: ' + e.message;
      document.getElementById('updateActions').style.display = 'flex';
    });
}

// Run the update check on launch — but defer if onboarding is showing,
// so we never stack two popups on a first-time user.
window.addEventListener('load', () => {
  const delay = _onboardingShowing ? 0 : 1500;
  if (_onboardingShowing) {
    // wait until they've closed onboarding, then check
    const iv = setInterval(() => {
      if (!document.getElementById('onboardOverlay').classList.contains('open')) {
        clearInterval(iv);
        setTimeout(checkForUpdate, 800);
      }
    }, 1000);
  } else {
    setTimeout(checkForUpdate, delay);
  }
});

// Apply the initial AI on/off state to the UI (hides the dock's Assistant button if off)
window.addEventListener('load', () => { applyAIState(); renderProxyPicker(); loadGuidelineBodies(); maybeAutoSearch(); startPendingSearchPolling(); });

// If launched from the menu-bar quick search (/?q=...&src=...), pre-select the
// requested source(s), fill the query, and run the search immediately.
function maybeAutoSearch() {
  const q = MS.autoQuery;
  const src = MS.autoSource;
  if (!q) return;
  runSearchWithSource(q, src, 150);
}

// Fill the query, select the requested source(s), and run the search. Shared by
// the initial deep-link (maybeAutoSearch) and the menu-bar handoff poller.
function runSearchWithSource(q, src, delay) {
  if (!q) return;
  const input = document.getElementById('searchInput');
  if (input) input.value = q;
  if (src) {
    document.querySelectorAll('.db-item').forEach(item => {
      const db = item.dataset.db;
      const shouldCheck = (src === 'all') ? true : (db === src);
      const needsKey = item.dataset.needsKey;
      const blocked = shouldCheck && needsKey && !dbKeyPresent[needsKey];
      item.classList.toggle('checked', shouldCheck && !blocked);
    });
    if (!document.querySelectorAll('.db-item.checked').length) {
      const pm = document.querySelector('.db-item[data-db="pubmed"]');
      if (pm) pm.classList.add('checked');
    }
  }
  setTimeout(() => { runSearch(); }, delay || 0);
}

// Poll for searches queued by the menu-bar app, and run them in THIS window so
// the search always happens inside the native app (no browser hop).
function startPendingSearchPolling() {
  setInterval(async () => {
    try {
      const res = await fetch('/pending_search');
      const data = await res.json();
      if (data && data.pending && data.query) {
        // Bring this window to the front, then run the search here.
        try { window.focus(); } catch(e) {}
        runSearchWithSource(data.query, data.source, 50);
      }
    } catch(e) { /* server momentarily busy; ignore */ }
  }, 1000);
}

// ── National guideline bodies ───────────────────────────────────────────────
let guidelineBodies = [];
async function loadGuidelineBodies() {
  const sel = document.getElementById('guidelineCountry');
  if (!sel) return;
  try {
    const data = await (await fetch('/guidelines/bodies')).json();
    guidelineBodies = data.bodies || [];
    sel.innerHTML = guidelineBodies.map(b =>
      `<option value="${b.code}" ${b.code === data.selected ? 'selected' : ''}>${escHtml(b.country)} — ${escHtml(shortBodyName(b.name))}</option>`
    ).join('');
    updateGuidelineHint();
  } catch(e) { /* leave empty */ }
  sel.onchange = updateGuidelineHint;
}

// The body names are long; show a short tag in the dropdown
function shortBodyName(name) {
  // take the acronym before the em-dash if present
  const m = name.split('—')[0].trim();
  return m || name;
}

function updateGuidelineHint() {
  const sel = document.getElementById('guidelineCountry');
  const hint = document.getElementById('natlGuidelineHint');
  if (!sel || !hint) return;
  const b = guidelineBodies.find(x => x.code === sel.value);
  if (!b) { hint.textContent = ''; return; }
  hint.textContent = b.prefill
    ? `Opens ${b.name} with your search term filled in.`
    : `Opens ${b.name} (type your term there — its site doesn't accept linked searches).`;
}

async function openNationalGuidelines() {
  const sel = document.getElementById('guidelineCountry');
  if (!sel || !sel.value) return;
  const query = (document.getElementById('searchInput')?.value || '').trim();
  try {
    const res = await fetch('/guidelines/link', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({country: sel.value, query})
    });
    const data = await res.json();
    if (data.ok && data.url) {
      openInAppBrowser(data.url, data.name);
    } else {
      fail(data.message || 'Could not open guidelines.');
    }
  } catch(e) {
    fail('Could not open guidelines: ' + e.message);
  }
}

let synthesisOpen  = false;
let searchRunning  = false;
let lastSearchParams = null;   // for saving searches
let sortMode = 'relevance';    // 'relevance' (default) or 'date'

// Predefined Trentino research institutions (always shown, in this order).
// URLs are filled in by the user; UniTN's is known and pre-filled.
const PREDEFINED_INSTITUTIONS = [
  {id: 'unitn', label: 'UniTN', url: 'https://ezp.biblio.unitn.it', predefined: true},
  {id: 'asuit', label: 'ASUIT', url: '', predefined: true},
  {id: 'fbk',   label: 'FBK',   url: '', predefined: true},
];

// Saved proxies from config: a list of {id?, label, url}. Custom ones have no id.
let savedProxies = MS.institutionProxies;
let activeProxy = MS.activeProxy;

// Merge predefined institutions with saved data: predefined keep their slot
// (taking a saved URL if the user set one), then any custom institutions follow.
function buildInstitutions() {
  const byId = {};
  (savedProxies || []).forEach(p => { if (p.id) byId[p.id] = p; });
  const merged = PREDEFINED_INSTITUTIONS.map(base => {
    const saved = byId[base.id];
    return {
      id: base.id,
      label: base.label,
      url: saved && saved.url != null ? saved.url : base.url,
      predefined: true,
    };
  });
  // Append custom (non-predefined) institutions
  (savedProxies || []).forEach(p => {
    if (!p.id) merged.push({id: null, label: p.label || 'Institution', url: p.url || '', predefined: false});
  });
  return merged;
}

let institutionProxies = buildInstitutions();

// The currently-active proxy URL (or '' if none / disabled / unset)
function currentProxyUrl() {
  if (activeProxy === -1) return '';
  const p = institutionProxies[activeProxy];
  return p && p.url ? p.url.trim() : '';
}

// Open a URL as a live web page INSIDE the PDF modal (same window/layout),
// replacing the PDF canvas with an iframe. The iframe is a real browser
// context — it runs JavaScript and carries the user's login cookies, so
// Open a URL in a separate native browser window (PyWebView). This window runs
// JavaScript and carries the user's login session/cookies, so paywalled/proxied
// papers and JS-rendered publisher viewers load natively — no system browser,
// and no X-Frame-Options issues (unlike an embedded iframe). Falls back to a
// normal new tab when not running under PyWebView (browser-tab mode).
function openInAppBrowser(url, title) {
  if (!url) return;
  // The PDF viewer is pointless once we hand off to the browser — close it.
  closePdf();
  try {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external) {
      window.pywebview.api.open_external(url, title || 'MedSearch — Article');
      return;
    }
  } catch (e) { /* fall through to tab */ }
  window.open(url, '_blank', 'noopener');
}

// Wrap a URL in the active institutional proxy so paywalled-but-subscribed
// papers open through the user's library. No-op if no proxy is active.
// Handles two EZProxy modes plus OpenAthens:
//   1) URL-prefix / login style:  https://login.ezproxy.uni.edu/login?url=
//   2) hostname-rewriting style:  https://ezp.biblio.unitn.it
function proxify(url) {
  const p = currentProxyUrl();
  if (!p || !url) return url;

  // ── Mode 1: prefix style (contains/ends with "url=") ──────────────────
  if (/url=$/i.test(p) || p.endsWith('=') || /\?url=/i.test(p)) {
    return (/\?url=/i.test(p) ? p : p) + encodeURIComponent(url);
  }

  // Bare proxy domain (strip scheme/path)
  let proxyDomain = p.replace(/^https?:\/\//i, '').replace(/\/.*$/, '');

  // ── Mode 2: hostname-rewriting (e.g. *.ezp.biblio.unitn.it) ───────────
  if (proxyDomain && !/\//.test(p.replace(/^https?:\/\//i, '')) && !p.includes('?')) {
    try {
      const u = new URL(url);
      const rewrittenHost = u.hostname.replace(/-/g, '--').replace(/\./g, '-')
                            + '.' + proxyDomain;
      return `${u.protocol}//${rewrittenHost}${u.pathname}${u.search}${u.hash}`;
    } catch (e) { return url; }
  }

  // ── Fallback: append after the proxy host ─────────────────────────────
  return p.replace(/\/$/, '') + '/' + url.replace(/^https?:\/\//, '');
}

// Toggle the Relevance / Recent sort control.
// suppressRerun=true updates the UI state only (used when another flow, e.g.
// running a saved search, will trigger the search itself).
function setSortMode(mode, suppressRerun) {
  if (mode !== 'relevance' && mode !== 'date') mode = 'relevance';
  sortMode = mode;
  document.querySelectorAll('#sortToggle .sort-opt').forEach(b => {
    b.classList.toggle('active', b.dataset.sort === mode);
  });
  // If results are already on screen, re-run so the new ordering applies.
  if (!suppressRerun && allArticles.filter(Boolean).length && !searchRunning) {
    runSearch();
  }
}

// ── DB checkboxes ─────────────────────────────────────────────────────────
// Which premium DBs currently have a key (set at render, updated on save)
let dbKeyPresent = {
  scopus: MS.hasScopus,
  wos:    MS.hasWos,
};

document.querySelectorAll('.db-item').forEach(item => {
  item.addEventListener('click', () => {
    const needsKey = item.dataset.needsKey;   // 'scopus' | 'wos' | undefined
    const turningOn = !item.classList.contains('checked');
    // If enabling a premium DB with no key, prompt gently instead of checking
    if (turningOn && needsKey && !dbKeyPresent[needsKey]) {
      showApiKeyPrompt(needsKey);
      return;   // don't check it
    }
    item.classList.toggle('checked');
  });
});

document.getElementById('selectAllBtn').addEventListener('click', () => {
  const items = document.querySelectorAll('.db-item');
  const allOn = [...items].every(i => i.classList.contains('checked'));
  items.forEach(i => {
    // Don't auto-enable keyless premium DBs via "Select all"
    if (!allOn && i.dataset.needsKey && !dbKeyPresent[i.dataset.needsKey]) return;
    i.classList.toggle('checked', !allOn);
  });
  document.getElementById('selectAllBtn').textContent = allOn ? 'Select all' : 'Deselect all';
});

function getSelectedDBs() {
  return [...document.querySelectorAll('.db-item.checked')].map(i => i.dataset.db);
}

// The chip beside Search always says what will be searched: "PubMed + 2".
const _DB_SHORT = {pubmed: 'PubMed', cochrane: 'Cochrane', guidelines: 'Guidelines',
                   clinicaltrials: 'ClinicalTrials.gov', arxiv: 'arXiv', scopus: 'Scopus',
                   wos: 'Web of Science'};
function updateSourcesSummary() {
  const dbs = getSelectedDBs();
  const label = document.getElementById('dockSourcesLabel');
  const chip  = document.getElementById('dockSources');
  if (!label) return;
  label.textContent = !dbs.length ? 'No source'
                    : _DB_SHORT[dbs[0]] + (dbs.length > 1 ? ` + ${dbs.length - 1}` : '');
  chip.classList.toggle('empty', !dbs.length);
  chip.title = dbs.length ? 'Searching: ' + dbs.map(d => _DB_SHORT[d]).join(', ') + ' — click to change'
                          : 'Choose at least one database';
}
new MutationObserver(updateSourcesSummary)
  .observe(document.getElementById('dbList'), {subtree: true, attributes: true, attributeFilter: ['class']});
updateSourcesSummary();

// ── API key prompt for premium databases ────────────────────────────────────
const DB_KEY_INFO = {
  scopus: {
    name: 'Scopus',
    intro: 'Scopus is a premium database from Elsevier. To search it, you need a free API key:',
    steps: [
      'Go to <a href="https://dev.elsevier.com" target="_blank">dev.elsevier.com</a> and sign in (institutional access often required).',
      'Create an API key under "My API Keys".',
      'Paste it into <strong>Settings</strong> (bottom bar) → Scopus, and Save.',
    ],
  },
  wos: {
    name: 'Web of Science',
    intro: 'Web of Science is a premium database from Clarivate. To search it, you need an API key:',
    steps: [
      'Go to <a href="https://developer.clarivate.com" target="_blank">developer.clarivate.com</a> and request access to the WoS Starter API.',
      'Once approved, copy your API key.',
      'Paste it into <strong>Settings</strong> (bottom bar) → Web of Science, and Save.',
    ],
  },
};

function showApiKeyPrompt(dbKey) {
  const info = DB_KEY_INFO[dbKey];
  if (!info) return;
  document.getElementById('apiKeyPromptTitle').textContent = `${info.name} needs an API key`;
  document.getElementById('apiKeyPromptBody').innerHTML =
    `<div>${info.intro}</div><ol>${info.steps.map(s => `<li>${s}</li>`).join('')}</ol>`;
  openOverlay('apiKeyPromptOverlay');
}

function closeApiKeyPrompt() {
  closeOverlay('apiKeyPromptOverlay');
}

function goToSettingsFromPrompt() {
  closeApiKeyPrompt();
  openSettings();
}

// Refresh the Scopus/WoS badges + internal state after settings are saved
function refreshDbKeyBadges(scopusPresent, wosPresent) {
  dbKeyPresent.scopus = !!scopusPresent;
  dbKeyPresent.wos = !!wosPresent;
  const map = {scopus: 'badge_scopus', wos: 'badge_wos'};
  for (const [k, id] of Object.entries(map)) {
    const badge = document.getElementById(id);
    if (!badge) continue;
    if (dbKeyPresent[k]) {
      badge.textContent = 'Available';
      badge.classList.remove('needs-key');
      badge.classList.add('available');
    } else {
      badge.textContent = 'API required';
      badge.classList.remove('available');
      badge.classList.add('needs-key');
      // if it was checked but key removed, uncheck it
      const item = document.querySelector(`.db-item[data-db="${k}"]`);
      if (item) item.classList.remove('checked');
    }
  }
}

// Live query-mode hint (mirrors backend is_power_query)
function detectPowerQuery(q) {
  if (/\b(AND|OR|NOT)\b/.test(q)) return true;
  if (/\[[a-zA-Z/ ]+\]/.test(q))  return true;
  if (q.includes('"'))            return true;
  return false;
}
function updateQueryHint() {
  const hint = document.getElementById('queryModeHint');
  if (!hint) return;
  const q = (document.getElementById('searchInput').value || '');
  const strict = document.getElementById('strictToggle').checked;
  if (q.trim() && detectPowerQuery(q)) {
    hint.textContent = 'Advanced query \u2014 operators & tags respected (toggle ignored)';
    hint.classList.add('power');
  } else if (strict) {
    hint.textContent = 'Strict \u2014 words must co-occur in title/abstract';
    hint.classList.remove('power');
  } else {
    hint.textContent = 'Broad \u2014 auto-expanded with synonyms & MeSH';
    hint.classList.remove('power');
  }
}
const _searchInputEl = document.getElementById('searchInput');
if (_searchInputEl) {
  _searchInputEl.addEventListener('input', updateQueryHint);
}
const _strictEl = document.getElementById('strictToggle');
if (_strictEl) {
  _strictEl.addEventListener('change', updateQueryHint);
}

// ── Search (progressive streaming) ─────────────────────────────────────────
let searchAbortController = null;
const erroredSources = new Map();   // source → error text, for this search (don't clobber the message)

function runSearch(isLoadMore) {
  // Defensive: if called as an event handler (e.g. btn.onclick = runSearch),
  // the first arg is a MouseEvent. Only treat an explicit `true` as load-more.
  isLoadMore = (isLoadMore === true);
  // "Find more" continues the search on screen, even if the box was edited since.
  if (isLoadMore && !lastSearchParams) return;
  const query = isLoadMore ? lastSearchParams.query
                           : document.getElementById('searchInput').value.trim();
  const dbs   = isLoadMore ? lastSearchParams.sources : getSelectedDBs();
  if (!query) { fail('Type what you are looking for in the search box.', 'No search terms'); return; }
  if (!dbs.length) { fail('Click the sources button beside Search and tick at least one database.', 'No database selected'); return; }
  if (searchRunning) return;

  searchRunning = true;
  setSearchButtonStop(true);
  if (!isLoadMore) {
    allArticles = [];
    erroredSources.clear();   // fresh error tracking per search
    closeSynthesis();
    resetAssistantSuggestions();   // refresh suggestions for the new search
  }

  searchAbortController = new AbortController();

  const perSource = parseInt(document.getElementById('maxResults').value) || 10;
  lastSearchParams = {
    query,
    sources:     dbs,
    max_results: perSource,
    year_from:   document.getElementById('yearFrom').value || null,
    year_to:     document.getElementById('yearTo').value   || null,
    strict:      document.getElementById('strictToggle').checked,
    sort:        sortMode,
    // The server keeps each source's own position, so "load more" asks every
    // source for its next batch rather than skipping by the combined count.
    load_more:   isLoadMore,
  };
  if (isLoadMore) {
    // same filters as the search on screen, only the batch size may change
    const prev = window._lastFullParams || {};
    Object.assign(lastSearchParams, {year_from: prev.year_from, year_to: prev.year_to,
                                     strict: prev.strict, sort: prev.sort});
  } else {
    window._lastFullParams = Object.assign({}, lastSearchParams);
  }

  // Fresh search: rebuild the results area. Load-more: keep existing results,
  // just remove the old "load more" button and show a small loading state.
  if (!isLoadMore) {
    scaffoldResults();
    setStatus('searching', 'Searching…');
  } else {
    const oldBtn = document.getElementById('loadMoreWrap');
    if (oldBtn) oldBtn.remove();
    setStatus('searching', 'Finding more…');
  }

  // POST then read the SSE stream from the response body
  fetch('/search_stream', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(lastSearchParams),
    signal: searchAbortController.signal
  }).then(response => {
    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    function pump() {
      return reader.read().then(({done, value}) => {
        if (done) { finishSearch(query, isLoadMore); return; }
        buffer += decoder.decode(value, {stream:true});

        // SSE events are separated by double newlines
        const parts = buffer.split('\n\n');
        buffer = parts.pop();   // keep incomplete tail
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;
          try { handleSearchEvent(JSON.parse(line.slice(5).trim())); }
          catch(e) { /* ignore parse errors on keep-alives */ }
        }
        return pump();
      });
    }
    return pump();
  }).catch(e => {
    if (e.name === 'AbortError') {
      // User stopped the search — keep whatever results arrived
      setStatus('done', `Search stopped · ${allArticles.length} result${allArticles.length===1?'':'s'} kept`);
      cleanupAfterSearch();
      return;
    }
    setStatus('error', 'Search failed: ' + e.message);
    fail(e.message, 'The search failed');
    cleanupAfterSearch();
  });
}

function stopSearch() {
  if (searchAbortController) {
    searchAbortController.abort();
    searchAbortController = null;
  }
}

function cleanupAfterSearch() {
  searchRunning = false;
  setSearchButtonStop(false);
  // Any source still showing a spinner was interrupted — convert it to a count
  // (or remove the group if it never produced any cards).
  document.querySelectorAll('.source-group').forEach(g => {
    const body = g.querySelector('.source-body');
    const spin = g.querySelector('.source-spinner');
    const cards = body ? body.querySelectorAll('.article-card').length : 0;
    if (spin) {
      if (cards > 0) {
        spin.outerHTML = `<span class="source-count">${cards}</span>`;
      } else {
        g.remove();   // interrupted before any results
      }
    } else if (body && !body.children.length) {
      g.remove();
    }
  });
  const prog = document.getElementById('searchProgress');
  if (prog) prog.textContent = '';
}

// Toggle the Search button between "Search" and "Stop" states
function setSearchButtonStop(isStop) {
  const btn = document.getElementById('searchBtn');
  if (!btn) return;
  if (isStop) {
    btn.textContent = 'Stop';
    btn.classList.add('stop-btn');
    btn.disabled = false;
    btn.onclick = () => stopSearch();
  } else {
    btn.textContent = 'Search';
    btn.classList.remove('stop-btn');
    btn.disabled = false;
    // Wrap so the click MouseEvent isn't passed as the isLoadMore argument
    // (a bare `btn.onclick = runSearch` would make every click a "load more").
    btn.onclick = () => runSearch();
  }
}

// Build the empty results shell with a sticky header
function scaffoldResults() {
  const area = document.getElementById('resultsArea');
  area.innerHTML = `
    <div id="meshSlot"></div>
    <div class="results-header" id="resultsHeader">
      <div class="results-count"><strong id="runningCount">0</strong> <span id="runningNoun">articles</span>
        <span id="searchProgress" class="search-progress"></span>
      </div>
      <div class="action-row">
        <button class="action-btn primary ai-synthesis-btn" onclick="openSynthesis()" style="${aiEnabled ? '' : 'display:none'}">${ico('sparkle')} AI Synthesis</button>
        <button class="action-btn" onclick="saveCurrentSearch()">${ico('star')} Save</button>
        <button class="action-btn" onclick="openExport()">${ico('download')} Export</button>
      </div>
    </div>
    <div class="result-filters" id="resultFilters" hidden>
      <span class="rf-label">Show</span>
      <label class="rf-check"><input type="checkbox" id="rfOpen" onchange="applyResultFilters()"> Free full text only</label>
      <select class="rf-select" id="rfType" onchange="applyResultFilters()" aria-label="Study type">
        <option value="">All study types</option>
      </select>
      <select class="rf-select" id="rfQuartile" onchange="applyResultFilters()" aria-label="Journal quartile"
              title="Quartiles are known only for a built-in list of major journals; others are hidden by this filter.">
        <option value="">Any journal</option>
        <option value="Q1">Q1 journals</option>
        <option value="Q1Q2">Q1–Q2 journals</option>
      </select>
      <span class="rf-count" id="rfCount"></span>
    </div>
    <div id="sourceGroups"></div>`;
}

// ── Filtering the results already on screen ────────────────────────────────
// Filters hide cards; they never refetch, and "Find more" results are
// filtered the same way as they arrive.
const _TYPE_ORDER = ['Meta-analysis','Systematic review','Guideline','RCT','Clinical trial',
                     'Observational','Review','Case report','Preprint','Registered trial'];
function _refreshTypeOptions() {
  const sel = document.getElementById('rfType');
  if (!sel) return;
  const present = new Set();
  allArticles.forEach(a => (a && a.pub_types || []).forEach(t => present.add(t)));
  const want = _TYPE_ORDER.filter(t => present.has(t));
  const have = [...sel.options].slice(1).map(o => o.value);
  if (want.join('|') === have.join('|')) return;
  const cur = sel.value;
  sel.innerHTML = '<option value="">All study types</option>' +
    want.map(t => `<option value="${escHtml(t)}">${escHtml(t)}</option>`).join('');
  sel.value = want.includes(cur) ? cur : '';
}

function applyResultFilters() {
  const bar = document.getElementById('resultFilters');
  if (!bar) return;
  _refreshTypeOptions();
  const openOnly = document.getElementById('rfOpen').checked;
  const type     = document.getElementById('rfType').value;
  const q        = document.getElementById('rfQuartile').value;
  let shown = 0, total = 0;
  document.querySelectorAll('.article-card').forEach(card => {
    const a = allArticles[parseInt((card.id || '').replace('card_', ''), 10)];
    if (!a) return;
    total++;
    const ok = (!openOnly || a.access_kind === 'open')
            && (!type || (a.pub_types || []).includes(type))
            && (!q || (q === 'Q1' ? a.quartile === 'Q1' : ['Q1','Q2'].includes(a.quartile)));
    card.hidden = !ok;
    if (ok) shown++;
  });
  bar.hidden = total === 0;
  const active = openOnly || type || q;
  document.getElementById('rfCount').textContent = active ? `${shown} of ${total} shown` : '';
}

// Reset the app to its initial state — like just-launched, but in-session
// (databases, saved searches, recent history, settings all preserved).
function resetToHome() {
  // Stop any in-flight work
  if (typeof stopSearch === 'function') stopSearch();
  if (typeof closeSynthesis === 'function') closeSynthesis();

  // Clear results & state
  allArticles = [];
  lastSearchParams = null;
  resetAssistantSuggestions();

  // Clear the search box and filters back to defaults
  const q = document.getElementById('searchInput');
  if (q) q.value = '';
  const yf = document.getElementById('yearFrom');  if (yf) yf.value = '';
  const yt = document.getElementById('yearTo');    if (yt) yt.value = '';
  const mr = document.getElementById('maxResults');if (mr) mr.value = 10;
  const strict = document.getElementById('strictToggle'); if (strict) strict.checked = true;
  setSortMode('relevance', true);   // back to default ordering
  if (typeof updateQueryHint === 'function') updateQueryHint();

  // Restore the welcome screen
  const area = document.getElementById('resultsArea');
  if (area) area.innerHTML = `
    <div class="empty-state" id="emptyState">
      <div class="wordmark">Med<span>Search</span></div>
      <div class="wordmark-sub">RN · ${escHtml(APP_VERSION)}</div>
      <div class="empty-sub">Type your question in the bar above, pick your sources beside it, and press Search.</div>
    </div>`;
  setStatus('idle', 'Ready — choose sources and enter a query');

  // If the assistant panel is open, close it (and reset its history too)
  if (assistantOpen) toggleAssistant();
  assistantHistory = [];
  renderAssistantMessages();

  // Scroll to top
  document.getElementById('resultsScroll').scrollTo({top: 0, behavior: _reduceMotion.matches ? 'auto' : 'smooth'});
}

function handleSearchEvent(ev) {
  if (ev.type === 'mesh' && ev.mesh && ev.mesh.length) {
    const spelling = ev.mesh.filter(m => m.type === 'spelling');
    const mesh     = ev.mesh.filter(m => m.type !== 'spelling');
    const tag = m => `<button type="button" class="mesh-tag" data-term="${escHtml(m.text)}"
                        onclick="useMesh(this.dataset.term)">${escHtml(m.text)}</button>`;
    document.getElementById('meshSlot').innerHTML =
      (spelling.length ? '<div class="mesh-box"><span class="mesh-label">Did you mean</span>' +
                         spelling.map(tag).join('') + '</div>' : '') +
      (mesh.length ? '<div class="mesh-box"><span class="mesh-label">MeSH terms</span>' +
                     mesh.map(tag).join('') + '</div>' : '');
  }
  else if (ev.type === 'source_start') {
    // All sources start together; the count of finished ones is the progress.
    const n = ev.total;
    setStatus('searching', `Searching ${n} source${n === 1 ? '' : 's'}…`);
    document.getElementById('searchProgress').textContent = `· 0 of ${n} sources done`;
    addSourcePlaceholder(ev.source);
  }
  else if (ev.type === 'article') {
    appendArticleCard(ev.source, ev.article);
    setRunningCount(allArticles.filter(Boolean).length);
  }
  else if (ev.type === 'oneliner') {
    patchOneliner(ev.idx, ev.text);
  }
  else if (ev.type === 'source_done') {
    // Don't clobber an error message that source_error already displayed
    if (!erroredSources.has(ev.source)) {
      finalizeSourceGroup(ev.source, ev.count);
    }
    setRunningCount(ev.running_count);
    if (ev.total_sources) {
      document.getElementById('searchProgress').textContent =
        ev.done_sources < ev.total_sources ? `· ${ev.done_sources} of ${ev.total_sources} sources done` : '';
    }
    applyResultFilters();
  }
  else if (ev.type === 'source_error') {
    erroredSources.set(ev.source, ev.text);
    finalizeSourceGroup(ev.source, 0, ev.text);
  }
  else if (ev.type === 'done') {
    setRunningCount(ev.count);
  }
  else if (ev.type === 'error') {
    setStatus('error', ev.text);
    fail(ev.text, 'The search failed');
  }
}

function setRunningCount(n) {
  document.getElementById('runningCount').textContent = n;
  document.getElementById('runningNoun').textContent = n === 1 ? 'article' : 'articles';
}

function addSourcePlaceholder(source) {
  const groups = document.getElementById('sourceGroups');
  const id = 'grp_' + source.replace(/\W/g,'');
  if (document.getElementById(id)) return;
  const grp = document.createElement('div');
  grp.className = 'source-group';
  grp.id = id;
  grp.innerHTML = `
    <div class="source-group-title">
      ${sourceIcon(source)} ${source}
      <span class="source-spinner" id="spin_${id}">searching…</span>
    </div>
    <div class="source-body" id="body_${id}"></div>`;
  groups.appendChild(grp);
}

// Append a single article card the moment it arrives
function appendArticleCard(source, article) {
  const id   = 'grp_' + source.replace(/\W/g,'');
  const body = document.getElementById('body_' + id);
  if (!body) return;
  allArticles[article._idx] = article;   // store by global index
  const card = makeCard(article);
  card.id = 'card_' + article._idx;
  card.style.animation = 'fadeInUp 0.3s ease';
  body.appendChild(card);
}

// Reorder cards within each source group by publication year, newest first.
// Used in "Recent" sort mode. Cards carry their global index in the DOM id,
// and allArticles[idx].year holds the year, so we can sort by that.
function sortGroupsByDate() {
  const yearOf = card => {
    const idx = parseInt((card.id || '').replace('card_', ''), 10);
    const a = allArticles[idx];
    const y = a && a.year ? parseInt(String(a.year).slice(0, 4), 10) : NaN;
    return isNaN(y) ? -Infinity : y;   // undated items sink to the bottom
  };
  document.querySelectorAll('.source-body').forEach(body => {
    const cards = Array.from(body.querySelectorAll('.article-card'));
    if (cards.length < 2) return;
    cards.sort((a, b) => yearOf(b) - yearOf(a));   // descending
    cards.forEach(c => { c.style.animation = ''; body.appendChild(c); });  // re-append in order
  });
}

// Patch a one-liner into an already-displayed card
function patchOneliner(idx, text) {
  if (allArticles[idx]) allArticles[idx].oneliner = text;
  const card = document.getElementById('card_' + idx);
  if (!card) return;
  // Reuse the same slot makeCard would have produced (.ai-oneliner)
  let slot = card.querySelector('.ai-oneliner');
  if (!slot) {
    slot = document.createElement('div');
    slot.className = 'ai-oneliner';
    // place after the authors line, or after the meta row, else after title
    const anchor = card.querySelector('.article-authors')
                || card.querySelector('.article-meta')
                || card.querySelector('.article-title');
    if (anchor && anchor.parentNode) {
      anchor.parentNode.insertBefore(slot, anchor.nextSibling);
    } else {
      card.appendChild(slot);
    }
  }
  slot.innerHTML = `${ico('sparkle')} ${escHtml(text)}`;
  slot.style.animation = 'fadeInUp 0.25s ease';
}

// When a source finishes: turn spinner into a count, handle empty/error
function finalizeSourceGroup(source, count, errorText) {
  const id   = 'grp_' + source.replace(/\W/g,'');
  const grp  = document.getElementById(id);
  if (!grp) return;
  const spin = document.getElementById('spin_' + id);
  const body = document.getElementById('body_' + id);

  if (errorText) {
    if (spin) spin.outerHTML = `<span class="source-count">0</span>`;
    if (body) body.innerHTML = `<div class="source-error"><svg class="ico" aria-hidden="true"><use href="#i-warning"/></svg> ${escHtml(errorText)}</div>`;
    return;
  }
  if (spin) spin.outerHTML = `<span class="source-count">${count}</span>`;
  if (count === 0 && body) {
    body.innerHTML = `<div class="source-empty">No results from this source.</div>`;
  }
}

function finishSearch(query, isLoadMore) {
  searchRunning = false;
  setSearchButtonStop(false);
  searchAbortController = null;
  updateHistory(query);
  const n = allArticles.filter(Boolean).length;
  document.getElementById('searchProgress').textContent = '';
  setStatus('done', `Found ${n} unique article${n===1?'':'s'}`);

  // Convert any lingering spinners (e.g. a source that returned 0) to counts
  document.querySelectorAll('.source-group').forEach(g => {
    const body = g.querySelector('.source-body');
    const spin = g.querySelector('.source-spinner');
    const cards = body ? body.querySelectorAll('.article-card').length : 0;
    const hasError = body && body.querySelector('.source-error');
    if (spin) spin.outerHTML = `<span class="source-count">${cards}</span>`;
    // Keep groups that have an error message; only remove truly empty ones
    if (body && !body.children.length && !hasError) g.remove();
  });

  // Partial failure shows both: the inline note stays in each failed source's
  // group, and one dialog names them all so the gap isn't missed.
  if (erroredSources.size) {
    const lines = [...erroredSources].map(([src, text]) => `${src}: ${text}`);
    const title = erroredSources.size === 1 ? `${[...erroredSources.keys()][0]} returned no results`
                                            : `${erroredSources.size} sources returned no results`;
    fail(lines.join('\n\n') + (n ? `\n\nThe other sources' results are shown.` : ''), title);
  }

  applyResultFilters();

  // In "Recent" mode, guarantee newest-first ordering within each source group
  // (the per-source API date sort usually handles this, but this is a safety net
  // for sources whose ordering can't be fully trusted, e.g. Cochrane).
  if (sortMode === 'date') sortGroupsByDate();

  // Show "no results" empty state ONLY if there are no results AND no error
  // messages to display (otherwise we'd wipe the errors).
  const anyErrors = document.querySelector('.source-error');
  if (n === 0 && !anyErrors) {
    document.getElementById('sourceGroups').innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><svg class="ico" aria-hidden="true"><use href="#i-search"/></svg></div>
        <div class="empty-title">No results found</div>
        <div class="empty-sub">Try different keywords or expand the date range.</div>
      </div>`;
  }

  // "Find more" button. We hide it when a load-more pass added nothing new
  // (sources exhausted), or when there are no results at all.
  const addedSomething = !isLoadMore || (n > (window._countBeforeLoadMore || 0));
  window._countBeforeLoadMore = n;   // remember for the next pass
  if (n > 0 && addedSomething) {
    const perSource = parseInt(document.getElementById('maxResults').value) || 10;
    const groups = document.getElementById('sourceGroups');
    const wrap = document.createElement('div');
    wrap.id = 'loadMoreWrap';
    wrap.className = 'load-more-wrap';
    wrap.innerHTML =
      `<button class="load-more-btn" onclick="runMoreResults()">Find ${perSource} more per source ↓</button>`;
    groups.appendChild(wrap);
  } else if (isLoadMore && n > 0) {
    // Exhausted: let the user know there's nothing more.
    showToast('No more results to load.', 'green');
  }
}

// "Find more": re-run the same search, asking each source for the next batch,
// appending the new (deduplicated) results below the current ones.
function runMoreResults() {
  window._countBeforeLoadMore = allArticles.filter(Boolean).length;
  runSearch(true);
}

function sourceIcon(s) {
  const icons = {
    'PubMed': 'journal', 'Cochrane': 'sources', 'Guidelines': 'guidelines',
    'ClinicalTrials.gov': 'flask', 'arXiv': 'preprint', 'Scopus': 'chart', 'Web of Science': 'globe',
  };
  return `<svg class="ico" aria-hidden="true"><use href="#i-${icons[s] || 'journal'}"/></svg>`;
}

function makeCard(a) {
  const card = document.createElement('div');
  card.className = 'article-card';

  const qClass = a.quartile ? `q${a.quartile[1].toLowerCase()}` : '';
  const qTag   = a.quartile ? `<span class="meta-tag ${qClass}">${escHtml(a.quartile)}</span>` : '';
  const cited  = a.cited_by ? `<span class="meta-tag cited">Cited: ${escHtml(a.cited_by)}</span>` : '';

  let links = '';
  if (a.access_kind === 'open' && a.access_link)
    links += `<button class="link-btn open-access" onclick="openPdf('${escAttr(a.access_link)}', '${escAttr(a.title || 'PDF')}')">${ico('preprint')} Read PDF</button>`;
  if (a.access_kind === 'doi' && a.access_link) {
    const hasProxy = !!currentProxyUrl();
    const doiHref = proxify(a.access_link);
    if (hasProxy) {
      // Open through the library in the built-in browser, where the proxy
      // login session applies — so subscribed/paywalled papers load reliably.
      links += `<button class="link-btn doi" onclick="openInAppBrowser('${escAttr(doiHref)}', '${escAttr(a.title || 'Article')}')">${ico('library')} DOI (via library)</button>`;
    } else {
      links += `<a class="link-btn doi" href="${escHtml(doiHref)}" target="_blank">${ico('external')} DOI</a>`;
    }
  }
  if (a.scihub && a.scihub.length) {
    // Normalize: support old single-string format too (defensive)
    const mirrors = Array.isArray(a.scihub) ? a.scihub : [a.scihub];
    const primary = mirrors[0];
    const alts = mirrors.slice(1);
    const titleAttr = escAttr(a.title || 'PDF');
    if (alts.length) {
      const altsHtml = alts.map(u => {
        // pretty label: just the hostname
        let host = u;
        try { host = new URL(u).hostname; } catch(_) {}
        return `<button class="scihub-alt-item" onclick="openPdf('${escAttr(u)}', '${titleAttr}')">${escHtml(host)}</button>`;
      }).join('');
      links += `<span class="scihub-group">
        <button class="link-btn scihub" onclick="openPdf('${escAttr(primary)}', '${titleAttr}')">Sci-Hub</button><button class="scihub-alt-toggle" onclick="toggleScihubAlts(event, ${a._idx})" title="Other mirrors">▾</button>
        <span class="scihub-alts" id="scihub_alts_${a._idx}">
          <div class="scihub-alts-label">If this doesn't work, try:</div>
          ${altsHtml}
        </span>
      </span>`;
    } else {
      links += `<button class="link-btn scihub" onclick="openPdf('${escAttr(primary)}', '${titleAttr}')">Sci-Hub</button>`;
    }
  }
  if (a.pmid)
    links += `<a class="link-btn doi" href="https://pubmed.ncbi.nlm.nih.gov/${encodeURIComponent(a.pmid)}/" target="_blank">PubMed</a>`;
  if (a.nct_id)
    links += `<a class="link-btn doi" href="https://clinicaltrials.gov/study/${encodeURIComponent(a.nct_id)}" target="_blank">ClinicalTrials</a>`;

  const citeBtn = a.doi
    ? `<button class="link-btn cite-btn" onclick="openCitations(${a._idx})">${ico('cite')} Citations</button>`
    : '';
  // when there's no cite button, explain takes the right-push
  const explainBtn = `<button class="link-btn explain-btn${a.doi ? '' : ' push-right'}" onclick="openExplain(${a._idx})">${ico('sparkle')} Explain</button>`;
  // Send this one article straight to Zotero (if the desktop app is running)
  const zoteroBtn = `<button class="link-btn zotero-btn" onclick="sendSingleToZotero(${a._idx}, event)" title="Send to Zotero">${ico('download')} Zotero</button>`;

  // Study design, from PubMed's publication types (and the source for
  // preprints / registered trials). Strongest evidence first.
  const typeTags = (a.pub_types || [])
    .map(t => `<span class="meta-tag ptype">${escHtml(t)}</span>`).join(' ');
  // A retraction is stated on the card itself, above everything the reader
  // might otherwise quote from it.
  let retraction = '';
  if (a.retraction === 'retracted') {
    card.classList.add('is-retracted');
    retraction = `<div class="retraction-note retracted" role="note"><strong>Retracted.</strong> This paper has been retracted; do not rely on its findings.</div>`;
  } else if (a.retraction === 'concern') {
    retraction = `<div class="retraction-note concern" role="note"><strong>Expression of concern.</strong> The journal has published a concern about this paper.</div>`;
  }
  const abstract = a.abstract || '';
  const oneliner = a.oneliner
    ? `<div class="ai-oneliner">${ico('sparkle')} ${escHtml(a.oneliner)}</div>` : '';

  card.innerHTML = `
    ${retraction}
    <div class="article-title">${escHtml(a.title)}</div>
    <div class="article-meta">
      ${typeTags}
      ${a.journal ? `<span class="meta-tag journal">${escHtml(a.journal)}</span>` : ''}
      ${a.year    ? `<span class="meta-tag year">${escHtml(a.year)}</span>` : ''}
      ${qTag} ${cited}
    </div>
    ${a.authors ? `<div class="article-authors">${escHtml(a.authors)}</div>` : ''}
    ${oneliner}
    ${abstract ? `
      <div class="article-abstract" id="abs_${a._idx}">${escHtml(abstract)}</div>
      <button class="expand-btn" id="expbtn_${a._idx}"
        onclick="toggleAbstract(${a._idx})">Show more ▾</button>` : ''}
    <div class="article-links">${links} ${citeBtn} ${explainBtn} ${zoteroBtn}</div>`;
  return card;
}

function toggleAbstract(idx) {
  const el  = document.getElementById('abs_'    + idx);
  const btn = document.getElementById('expbtn_' + idx);
  el.classList.toggle('expanded');
  btn.textContent = el.classList.contains('expanded') ? 'Show less ▴' : 'Show more ▾';
}

// ── AI Synthesis ───────────────────────────────────────────────────────────
let synthesisEventSource = null;

function openSynthesis() {
  if (!allArticles.length) { fail('Run a search first.'); return; }
  const panel = document.getElementById('synthesisPanel');
  const text  = document.getElementById('synthesisText');
  panel.classList.add('open');
  text.textContent = '';
  synthesisOpen = true;
  document.getElementById('synthesisStopBtn').style.display = '';

  const es = new EventSource(withToken('/synthesis'));
  synthesisEventSource = es;
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'chunk') { text.textContent += d.text; }
    if (d.type === 'done')  { es.close(); synthesisEventSource = null; document.getElementById('synthesisStopBtn').style.display = 'none'; }
    if (d.type === 'error') {
      es.close(); synthesisEventSource = null;
      closeSynthesis();
      fail(d.text, "Couldn't write the synthesis");
      return;
    }
    document.getElementById('synthesisPanel').scrollTop = 9999;
  };
  es.onerror = () => {
    es.close(); synthesisEventSource = null;
    document.getElementById('synthesisStopBtn').style.display = 'none';
    // Dropped before a word arrived: nothing to read, so say so rather than
    // leave an empty sheet open.
    if (!text.textContent) { closeSynthesis(); fail('The connection to MedSearch dropped. Try again.', "Couldn't write the synthesis"); }
  };
}

function stopSynthesis() {
  if (synthesisEventSource) {
    synthesisEventSource.close();
    synthesisEventSource = null;
  }
  const text = document.getElementById('synthesisText');
  if (text && text.textContent) {
    text.textContent += '\n\n— stopped —';
  }
  document.getElementById('synthesisStopBtn').style.display = 'none';
}

function closeSynthesis() {
  stopSynthesis();   // also halts any in-progress generation
  document.getElementById('synthesisPanel').classList.remove('open');
  synthesisOpen = false;
}

// ── AI on/off toggle ────────────────────────────────────────────────────────
let aiEnabled = MS.aiOn;
const aiHasKey = MS.hasAiKey;
let assistantOpen = false;   // declared here so applyAIState() can read it safely on load

function toggleAI() {
  // If there's no API key at all, turning "on" makes no sense — guide them.
  if (!aiHasKey && !aiEnabled) {
    fail('Add your Anthropic API key in Settings to use AI features.');
    openSettings();
    return;
  }
  aiEnabled = !aiEnabled;
  applyAIState();
  // Persist the preference
  fetch('/ai/toggle', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({enabled: aiEnabled})
  }).catch(() => {});
  showToast(aiEnabled ? 'AI features enabled.' : 'AI features turned off.', aiEnabled ? 'green' : null);
}

// Reflect the current AI state across the badge and all AI UI elements
function applyAIState() {
  const badge = document.getElementById('aiBadge');
  if (badge) {
    document.getElementById('aiBadgeLabel').textContent = aiEnabled ? 'AI on' : 'AI off';
    badge.classList.toggle('on', aiEnabled);
    badge.classList.toggle('off', !aiEnabled);
    badge.setAttribute('aria-pressed', aiEnabled ? 'true' : 'false');
  }
  // The dock's Assistant button only exists while AI is on
  const dockAssistant = document.getElementById('dockAssistant');
  if (dockAssistant) dockAssistant.hidden = !aiEnabled;
  // If the assistant panel is open and AI gets turned off, close it
  if (!aiEnabled && assistantOpen) toggleAssistant();
  // AI Synthesis button in the results header (may not exist yet)
  document.querySelectorAll('.ai-synthesis-btn').forEach(b => {
    b.style.display = aiEnabled ? '' : 'none';
  });
}


let assistantHistory = [];      // [{role, content}, ...]
let assistantStreaming = false;
let assistantSuggestionsLoaded = false;

function toggleAssistant() {
  assistantOpen = !assistantOpen;
  const panel  = document.getElementById('assistantPanel');
  document.getElementById('dockAssistant').classList.toggle('on', assistantOpen);
  if (assistantOpen) {
    panel.classList.add('open');
    renderAssistantMessages();
    loadAssistantSuggestions();   // suggestions appear when opened
    setTimeout(() => document.getElementById('assistantInput').focus(), 100);
  } else {
    panel.classList.remove('open');
  }
}

function renderAssistantMessages() {
  const box = document.getElementById('assistantMessages');
  if (!assistantHistory.length) {
    box.innerHTML = `<div class="assistant-empty">
      <span class="big">${ico('sparkle')}</span>
      Ask me about your current search results, or any clinical question.
      I'll ground answers in the papers you've found and cite them by number.
    </div>`;
    return;
  }
  box.innerHTML = assistantHistory.map(m =>
    `<div class="msg ${m.role}">${m.role==='assistant' ? linkifyCites(m.content) : escHtml(m.content)}</div>`
  ).join('');
  box.scrollTop = box.scrollHeight;
}

// Turn [N] references into clickable spans that scroll to that card
function linkifyCites(text) {
  return escHtml(text).replace(/\[(\d+)\]/g, (m, n) =>
    `<span class="cite-ref" onclick="jumpToCard(${parseInt(n)-1})">[${n}]</span>`);
}

function jumpToCard(idx) {
  const card = document.getElementById('card_' + idx);
  if (card) {
    card.scrollIntoView({behavior:'smooth', block:'center'});
    card.style.transition = 'background 0.3s';
    const orig = card.style.background;
    card.style.background = 'var(--accent-tint)';
    setTimeout(() => { card.style.background = orig; }, 1200);
  }
}

async function loadAssistantSuggestions() {
  const wrap = document.getElementById('assistantSuggestions');
  // Only show suggestions if there's a current search and we haven't loaded yet this session
  if (!allArticles.filter(Boolean).length) { wrap.innerHTML = ''; return; }
  if (assistantSuggestionsLoaded) return;
  wrap.innerHTML = '<div class="suggestions-label">Thinking of questions…</div>';
  try {
    const res  = await fetch('/assistant/suggestions');
    const data = await res.json();
    if (data.suggestions && data.suggestions.length) {
      wrap.innerHTML = '<div class="suggestions-label">Suggested questions</div>' +
        data.suggestions.map(s =>
          `<button class="suggestion-chip" onclick="useSuggestion('${escAttr(s)}')">${escHtml(s)}</button>`
        ).join('');
      assistantSuggestionsLoaded = true;
    } else {
      wrap.innerHTML = '';
    }
  } catch(e) { wrap.innerHTML = ''; }
}

function useSuggestion(text) {
  document.getElementById('assistantInput').value = text;
  document.getElementById('assistantSuggestions').innerHTML = '';
  sendAssistantMessage();
}

function sendAssistantMessage() {
  const input = document.getElementById('assistantInput');
  const text  = input.value.trim();
  if (!text || assistantStreaming) return;

  // hide suggestions once the conversation starts
  document.getElementById('assistantSuggestions').innerHTML = '';

  assistantHistory.push({role:'user', content:text});
  input.value = '';
  input.style.height = 'auto';
  renderAssistantMessages();

  // Add a placeholder assistant message that we'll stream into
  assistantHistory.push({role:'assistant', content:''});
  const msgIndex = assistantHistory.length - 1;
  renderAssistantMessages();

  // Show a typing indicator on the (empty) last bubble
  const box = document.getElementById('assistantMessages');
  const typing = document.createElement('div');
  typing.className = 'msg-typing';
  typing.id = 'assistantTyping';
  typing.innerHTML = `${ico('sparkle')} thinking…`;
  box.appendChild(typing);
  box.scrollTop = box.scrollHeight;

  assistantStreaming = true;
  document.getElementById('assistantSend').disabled = true;

  fetch('/assistant/chat', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({messages: assistantHistory.slice(0, -1)})  // exclude empty placeholder
  }).then(response => {
    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    const typingEl = document.getElementById('assistantTyping');
    if (typingEl) typingEl.remove();

    function pump() {
      return reader.read().then(({done, value}) => {
        if (done) { finishAssistantMessage(); return; }
        buffer += decoder.decode(value, {stream:true});
        const parts = buffer.split('\n\n');
        buffer = parts.pop();
        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith('data:')) continue;
          try {
            const d = JSON.parse(line.slice(5).trim());
            if (d.type === 'chunk' && assistantHistory[msgIndex]) {
              assistantHistory[msgIndex].content += d.text;
              updateStreamingBubble(msgIndex);
            } else if (d.type === 'error') {
              _assistantFailed(msgIndex, d.text);
            }
          } catch(e) {}
        }
        return pump();
      });
    }
    return pump();
  }).catch(e => {
    _assistantFailed(msgIndex, 'Connection error: ' + e.message);
    finishAssistantMessage();
  });
}

// An error is a dialog, not a reply: the empty answer is dropped from the
// conversation (so it is not sent back as context), and the question stays.
function _assistantFailed(msgIndex, text) {
  if (assistantHistory[msgIndex] && assistantHistory[msgIndex].role === 'assistant')
    assistantHistory.splice(msgIndex, 1);
  renderAssistantMessages();
  fail(text, "The assistant couldn't answer");
}

function updateStreamingBubble(msgIndex) {
  const box = document.getElementById('assistantMessages');
  const bubbles = box.querySelectorAll('.msg.assistant');
  const last = bubbles[bubbles.length - 1];
  if (last) {
    last.innerHTML = linkifyCites(assistantHistory[msgIndex].content);
    box.scrollTop = box.scrollHeight;
  }
}

function finishAssistantMessage() {
  assistantStreaming = false;
  document.getElementById('assistantSend').disabled = false;
  const t = document.getElementById('assistantTyping');
  if (t) t.remove();
  renderAssistantMessages();
}

// When a new search runs, reset suggestions so they refresh next time assistant opens
function resetAssistantSuggestions() {
  assistantSuggestionsLoaded = false;
}

// auto-grow the textarea
document.addEventListener('DOMContentLoaded', () => {
  const ai = document.getElementById('assistantInput');
  if (ai) ai.addEventListener('input', () => {
    ai.style.height = 'auto';
    ai.style.height = Math.min(ai.scrollHeight, 110) + 'px';
  });
});

// ── Explain ────────────────────────────────────────────────────────────────
function openExplain(idx) {
  const a = allArticles[idx];
  if (!a) return;
  document.getElementById('explainTitle').textContent = a.title;
  document.getElementById('explainText').textContent  = '';
  openOverlay('explainOverlay');

  const es = new EventSource(withToken('/explain/' + idx));
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'chunk') { document.getElementById('explainText').textContent += d.text; }
    if (d.type === 'done')  { es.close(); }
    if (d.type === 'error') { es.close(); closeExplain(); fail(d.text, "Couldn't explain this paper"); }
  };
  es.onerror = () => {
    es.close();
    if (!document.getElementById('explainText').textContent) {
      closeExplain(); fail('The connection to MedSearch dropped. Try again.', "Couldn't explain this paper");
    }
  };
}

function closeExplain() {
  closeOverlay('explainOverlay');
}

// ── Citation graph ─────────────────────────────────────────────────────────
function openCitations(idx) {
  const a = allArticles[idx];
  if (!a) return;
  document.getElementById('citeTitle').textContent =
    'Citation graph · ' + (a.title.length > 70 ? a.title.slice(0,70)+'…' : a.title);
  document.getElementById('citeBody').innerHTML =
    '<div class="cite-loading">Fetching references & citations…</div>';
  openOverlay('citeOverlay');

  fetch('/citations/' + idx)
    .then(r => r.json())
    .then(data => renderCitations(data, a))
    .catch(e => { closeCitations(); fail(e.message, "Couldn't load the citation graph"); });
}

function closeCitations() {
  closeOverlay('citeOverlay');
}

// ── PDF viewer (PDF.js — full zoom + fit-to-width) ──────────────────────────
let pdfDoc = null;          // loaded PDF.js document
let pdfScale = 1.0;         // current zoom scale
let pdfFitScale = 1.0;      // the scale that fits the viewer width
let pdfBytes = null;        // raw PDF data (for Save)
let pdfFilename = 'article.pdf';

function _slugifyPdfName(title) {
  const base = (title || 'article').replace(/[^a-z0-9]+/gi, '_')
                 .replace(/^_+|_+$/g, '').slice(0, 60).toLowerCase();
  return (base || 'article') + '.pdf';
}

function openPdf(url, title) {
  const loading = document.getElementById('pdfLoading');
  const titleEl = document.getElementById('pdfTitle');
  const extLink = document.getElementById('pdfOpenExternal');
  const container = document.getElementById('pdfCanvasContainer');
  const zoomCtl = document.getElementById('pdfZoomControls');

  titleEl.textContent = title || 'PDF';
  extLink.onclick = () => openInAppBrowser(url, title || 'Article');
  pdfFilename = _slugifyPdfName(title);
  pdfBytes = null;
  const _saveBtn = document.getElementById('pdfSaveBtn');
  if (_saveBtn) _saveBtn.style.display = '';
  container.style.display = 'none';
  container.innerHTML = '';
  zoomCtl.style.display = 'none';
  loading.style.display = 'flex';
  // Sci-Hub takes two hops (page → embedded PDF), so signal it may be slower
  const isScihub = /sci-hub/i.test(url);
  document.getElementById('pdfLoadingText').textContent =
    isScihub ? 'Fetching from Sci-Hub…' : 'Loading PDF…';
  const oldErr = document.getElementById('pdfErrorPanel');
  if (oldErr) oldErr.remove();

  openOverlay('pdfOverlay');

  // Guard: PDF.js must have loaded (needs internet on first run). If not,
  // open the article in the browser instead of dead-ending.
  if (!window.pdfjsLib) {
    openInAppBrowser(url, title);
    return;
  }

  const proxyUrl = '/pdf_proxy?url=' + encodeURIComponent(url);

  fetch(proxyUrl)
    .then(async res => {
      const ct = res.headers.get('Content-Type') || '';
      if (!res.ok || !ct.includes('pdf')) {
        // The server couldn't return a direct PDF (paywall, login-gated, or a
        // JS-rendered page). The browser is the only way to read it, so go
        // straight there and close this viewer — no dead-end prompt.
        openInAppBrowser(url, title);
        return null;
      }
      return res.arrayBuffer();
    })
    .then(async buf => {
      if (!buf) return;
      pdfBytes = buf.slice(0);          // keep a copy for Save (getDocument consumes it)
      try {
        pdfDoc = await pdfjsLib.getDocument({data: buf}).promise;
        loading.style.display = 'none';
        container.style.display = 'flex';
        zoomCtl.style.display = 'flex';
        // Default: fit to width
        await computeFitScale();
        pdfScale = pdfFitScale;
        await renderAllPages();
      } catch(e) {
        // Couldn't render the bytes as a PDF — fall through to the browser.
        openInAppBrowser(url, title);
      }
    })
    .catch(e => openInAppBrowser(url, title));
}

// Save the currently-open PDF to disk (opens the browser's save dialog)
function savePdf() {
  if (!pdfBytes) { fail('PDF still loading — try again in a moment.'); return; }
  try {
    const blob = new Blob([pdfBytes], {type: 'application/pdf'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = pdfFilename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch(e) {
    fail('Could not save the PDF: ' + e.message);
  }
}

// Work out the scale at which page 1 fills the available width
async function computeFitScale() {
  if (!pdfDoc) return;
  const page = await pdfDoc.getPage(1);
  const unscaled = page.getViewport({scale: 1});
  const body = document.getElementById('pdfBody');
  // available width minus container padding (16px each side) and a little margin
  const avail = body.clientWidth - 44;
  pdfFitScale = Math.max(0.3, avail / unscaled.width);
}

async function renderAllPages() {
  const container = document.getElementById('pdfCanvasContainer');
  container.innerHTML = '';
  updateZoomLabel();
  if (!pdfDoc) return;
  // Render with a device-pixel multiplier for crispness
  const dpr = window.devicePixelRatio || 1;
  for (let n = 1; n <= pdfDoc.numPages; n++) {
    const page = await pdfDoc.getPage(n);
    const viewport = page.getViewport({scale: pdfScale});
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    canvas.width  = Math.floor(viewport.width  * dpr);
    canvas.height = Math.floor(viewport.height * dpr);
    canvas.style.width  = Math.floor(viewport.width)  + 'px';
    canvas.style.height = Math.floor(viewport.height) + 'px';
    container.appendChild(canvas);
    await page.render({
      canvasContext: ctx,
      viewport,
      transform: dpr !== 1 ? [dpr, 0, 0, dpr, 0, 0] : null
    }).promise;
  }
}

function updateZoomLabel() {
  const lvl = document.getElementById('pdfZoomLevel');
  if (lvl) lvl.textContent = Math.round(pdfScale * 100) + '%';
}

let _pdfRerenderTimer = null;
function pdfZoom(dir) {
  // No artificial cap — step by 20%, floor at 20%
  const step = 0.2;
  pdfScale = Math.max(0.2, pdfScale + dir * step);
  updateZoomLabel();
  // debounce re-render so rapid clicks don't stack
  clearTimeout(_pdfRerenderTimer);
  _pdfRerenderTimer = setTimeout(renderAllPages, 120);
}

async function pdfFitWidth() {
  await computeFitScale();
  pdfScale = pdfFitScale;
  updateZoomLabel();
  renderAllPages();
}

function closePdf() {
  closeOverlay('pdfOverlay');
  const container = document.getElementById('pdfCanvasContainer');
  container.innerHTML = '';
  const saveBtn = document.getElementById('pdfSaveBtn');
  if (saveBtn) saveBtn.style.display = '';
  pdfDoc = null;
  pdfBytes = null;
}

function renderCitations(data, article) {
  const body = document.getElementById('citeBody');

  if (data.error) {
    closeCitations();
    fail(data.error === 'no_doi' ? data.message : data.error, "Couldn't load the citation graph");
    return;
  }

  const refs = data.references || [];
  const cits = data.citations || [];

  if (!refs.length && !cits.length) {
    body.innerHTML = `<div class="cite-error">
      No citation data found for this article in OpenCitations.<br>
      <span style="font-size:0.75rem;color:var(--text3)">
      Coverage is best for articles with a Crossref DOI; very recent or niche papers may not be indexed yet.</span>
    </div>`;
    return;
  }

  // Build the visual graph (SVG) + the two lists
  const graphSvg = buildCiteGraph(article, refs, cits);

  const refList = refs.length
    ? refs.map(r => citeItemHtml(r)).join('')
    : '<div class="cite-empty-col">No references found in OpenCitations.</div>';
  const citList = cits.length
    ? cits.map(c => citeItemHtml(c)).join('')
    : '<div class="cite-empty-col">No citing papers found yet.</div>';

  body.innerHTML = `
    ${graphSvg}
    <div class="cite-columns">
      <div>
        <div class="cite-col-title refs">↓ References
          <span class="cite-col-count">${data.ref_total} total${refs.length < data.ref_total ? ', showing '+refs.length : ''}</span>
        </div>
        ${refList}
      </div>
      <div>
        <div class="cite-col-title cits">↑ Cited by
          <span class="cite-col-count">${data.cit_total} total${cits.length < data.cit_total ? ', showing '+cits.length : ''}</span>
        </div>
        ${citList}
      </div>
    </div>
    <div class="cite-note">Citation data from OpenCitations · titles resolved via Crossref</div>`;
}

function citeItemHtml(item) {
  const meta = [];
  if (item.authors) meta.push(escHtml(item.authors));
  if (item.year)    meta.push(item.year);
  if (item.journal) meta.push(escHtml(item.journal));
  const doiLink = item.doi
    ? `<a href="https://doi.org/${encodeURIComponent(item.doi)}" target="_blank">DOI ${ico('external')}</a>` : '';
  return `<div class="cite-item">
    <div class="cite-item-title">${escHtml(item.title || '(untitled)')}</div>
    <div class="cite-item-meta">${meta.join(' · ')} ${doiLink}</div>
  </div>`;
}

// Radial SVG: center node = this paper, references LEFT, citations RIGHT
function buildCiteGraph(article, refs, cits) {
  const W = 860, H = 320, cx = W/2, cy = H/2;
  const maxPer = 8;  // nodes shown per side in the graph (lists show all)
  const r = refs.slice(0, maxPer);
  const c = cits.slice(0, maxPer);

  let nodes = '', links = '';

  function place(items, side) {
    const n = items.length;
    if (!n) return;
    const rx = 300;            // horizontal reach
    const vSpan = 210;         // vertical spread (clears the side headings)
    const dir = (side === 'left' ? -1 : 1);
    items.forEach((it, i) => {
      const x = cx + dir * (140 + rx * (0.35 + 0.65 * (i % 2)));  // stagger depth
      const frac = n === 1 ? 0.5 : i / (n - 1);
      const y = cy - vSpan/2 + frac * vSpan;
      const cls = side === 'left' ? 'cite-node-ref' : 'cite-node-cit';
      links += `<line class="cite-link" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/>`;
      nodes += `<circle class="${cls}" cx="${x}" cy="${y}" r="8"/>`;
      if (it.year) nodes += `<text class="cite-node-label" x="${x}" y="${y - 13}" text-anchor="middle">${it.year}</text>`;
    });
  }
  place(r, 'left');
  place(c, 'right');

  // Center node + label
  nodes += `<circle class="cite-node-center" cx="${cx}" cy="${cy}" r="12"/>`;
  const shortTitle = (article.title || '').slice(0, 34) + ((article.title||'').length>34?'…':'');
  nodes += `<text class="cite-node-label" x="${cx}" y="${cy + 30}" text-anchor="middle" style="font-weight:700">${escHtml(shortTitle)}</text>`;
  // side headers
  nodes += `<text class="cite-axis-label" x="${cx - 300}" y="16" text-anchor="middle">↓ REFERENCES</text>`;
  nodes += `<text class="cite-axis-label" x="${cx + 300}" y="16" text-anchor="middle">↑ CITED BY</text>`;

  return `<div class="cite-graph-wrap">
    <svg class="cite-graph-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      ${links}${nodes}
    </svg>
    <div class="cite-legend">
      <span class="cite-legend-item"><span class="cite-dot center"></span> This paper</span>
      <span class="cite-legend-item"><span class="cite-dot ref"></span> References (what it cites)</span>
      <span class="cite-legend-item"><span class="cite-dot cit"></span> Cited by (what cites it)</span>
    </div>
  </div>`;
}

// ── Export ─────────────────────────────────────────────────────────────────
// What the export and "send to Zotero" cover: when result filters are on,
// only the cards they leave visible; otherwise everything found.
function exportSelection() {
  const all = allArticles.filter(Boolean);
  const cards = [...document.querySelectorAll('.article-card')];
  const visible = cards.filter(c => !c.hidden)
                       .map(c => parseInt((c.id || '').replace('card_', ''), 10))
                       .filter(i => !isNaN(i));
  const filtered = cards.length && visible.length < cards.length;
  return {indices: filtered ? visible : null, count: filtered ? visible.length : all.length,
          total: all.length, filtered};
}

function openExport() {
  if (!allArticles.length) { fail('No articles to export.'); return; }
  const sel = exportSelection();
  if (!sel.count) { fail('The filters hide every result. Change them to export something.', 'Nothing to export'); return; }
  document.getElementById('exportScope').textContent = sel.filtered
    ? `Exports the ${sel.count} of ${sel.total} results your filters show.`
    : (sel.total === 1 ? 'Exports the 1 result.' : `Exports all ${sel.total} results.`);
  document.getElementById('exportSuccess').style.display = 'none';
  openOverlay('exportOverlay');
  checkZoteroAvailable();
}
function closeExport() {
  closeOverlay('exportOverlay');
}

// Check whether the Zotero desktop app is running, update the row accordingly
function checkZoteroAvailable() {
  const row    = document.getElementById('zoteroRow');
  const status = document.getElementById('zoteroStatus');
  const btn    = document.getElementById('zoteroSendBtn');
  status.textContent = 'Checking for Zotero…';
  btn.disabled = true;
  fetch('/export/zotero/check')
    .then(r => r.json())
    .then(d => {
      if (d.available) {
        row.classList.remove('unavailable');
        status.textContent = 'Adds all results straight into your Zotero library.';
        btn.disabled = false;
      } else {
        row.classList.add('unavailable');
        status.innerHTML = 'Zotero isn\'t running. Open the Zotero desktop app, then reopen this.';
        btn.disabled = true;
      }
    })
    .catch(() => {
      row.classList.add('unavailable');
      status.textContent = 'Couldn\'t check Zotero status.';
      btn.disabled = true;
    });
}

async function sendToZotero() {
  const btn = document.getElementById('zoteroSendBtn');
  const status = document.getElementById('zoteroStatus');
  btn.disabled = true;
  btn.textContent = 'Sending…';
  try {
    const res  = await fetch('/export/zotero', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({indices: exportSelection().indices})
    });
    const data = await res.json();
    if (data.ok) {
      status.innerHTML = '✓ ' + escHtml(data.message);
      btn.textContent = 'Sent ✓';
      showToast('Sent to Zotero!', 'green');
      setTimeout(() => { btn.textContent = 'Send to Zotero'; btn.disabled = false; }, 2500);
    } else {
      status.innerHTML = '<svg class="ico" aria-hidden="true"><use href="#i-warning"/></svg> ' + escHtml(data.message);
      btn.textContent = 'Send to Zotero';
      btn.disabled = false;
      fail(data.message);
    }
  } catch(e) {
    btn.textContent = 'Send to Zotero';
    btn.disabled = false;
    fail('Zotero send failed: ' + e.message);
  }
}

// Send a single article (by index) to Zotero from its card button
async function sendSingleToZotero(idx, ev) {
  const btn = ev && ev.currentTarget ? ev.currentTarget : null;
  if (btn) { btn.disabled = true; btn.innerHTML = `${ico('download')} Sending…`; }
  try {
    const res = await fetch('/export/zotero/single', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({idx})
    });
    const data = await res.json();
    if (data.ok) {
      if (btn) btn.innerHTML = `${ico('download')} Sent`;
      showToast('Sent to Zotero!', 'green');
      if (btn) setTimeout(() => { btn.innerHTML = `${ico('download')} Zotero`; btn.disabled = false; }, 2500);
    } else {
      if (btn) { btn.innerHTML = `${ico('download')} Zotero`; btn.disabled = false; }
      fail(data.message || 'Could not send to Zotero.');
    }
  } catch(e) {
    if (btn) { btn.innerHTML = `${ico('download')} Zotero`; btn.disabled = false; }
    fail('Zotero send failed: ' + e.message);
  }
}

async function doExport() {
  const fmt = document.querySelector('input[name=exportFmt]:checked').value;
  const res  = await fetch('/export', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({format: fmt, indices: exportSelection().indices})
  });
  const data = await res.json();
  if (data.error) { fail(data.error); return; }
  const succ = document.getElementById('exportSuccess');
  succ.style.display = 'block';
  succ.textContent   = '✓ Saved to: ' + data.paths.join(', ');
  showToast('Export complete!', 'green');
}

// ── Settings ───────────────────────────────────────────────────────────────
async function openSettings() {
  openOverlay('settingsOverlay');
  // Load which keys are already saved and indicate them in each field.
  const fields = {
    anthropic_api_key: 'set_anthropic',
    pubmed_api_key:    'set_pubmed',
    scopus_api_key:    'set_scopus',
    scopus_insttoken:  'set_scopus_insttoken',
    wos_api_key:       'set_wos',
    unpaywall_email:   'set_email',
  };
  // Reset all to their original placeholders first
  _keysToClear.clear();
  document.querySelectorAll('.key-remove').forEach(b => b.remove());
  for (const id of Object.values(fields)) {
    const el = document.getElementById(id);
    if (el) {
      el.disabled = false;
      el.value = '';
      el.classList.remove('has-saved');
      if (el.dataset.origPlaceholder) el.placeholder = el.dataset.origPlaceholder;
      else el.dataset.origPlaceholder = el.placeholder;
    }
  }
  try {
    const res  = await fetch('/settings');
    const data = await res.json();
    for (const [key, id] of Object.entries(fields)) {
      const el  = document.getElementById(id);
      const val = data[key];
      if (!el || !val) continue;
      if (key === 'unpaywall_email') {
        // Email isn't sensitive — show it in full so they can see/edit it
        el.value = val;
        el.classList.add('has-saved');
      } else {
        // API keys stay masked; show a "saved" indicator in the placeholder
        const last4 = val.slice(-4);
        el.placeholder = `✓ Saved (••••${last4}) — type to replace`;
        el.classList.add('has-saved');
        _addRemoveKeyButton(el, key);
      }
    }
  } catch(e) { /* if it fails, fields just show normal placeholders */ }
  // Sync proxies from the server, then rebuild the merged list (predefined +
  // saved) so UniTN/ASUIT/FBK always show and saved URLs land in their slots.
  try {
    const s = await (await fetch('/settings')).json();
    if (Array.isArray(s.institution_proxies)) savedProxies = s.institution_proxies;
    if (typeof s.active_proxy === 'number') activeProxy = s.active_proxy;
    institutionProxies = buildInstitutions();
  } catch(e) {}
  renderProxyRows();
}
// A blank field means "keep the saved key", so removing one is its own action,
// applied when Settings is saved.
const _keysToClear = new Set();
function _addRemoveKeyButton(input, key) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'key-remove';
  btn.textContent = 'Remove';
  btn.onclick = () => {
    const removing = !_keysToClear.has(key);
    if (removing) _keysToClear.add(key); else _keysToClear.delete(key);
    input.value = '';
    input.disabled = removing;
    input.placeholder = removing ? 'Will be removed when you save'
                                 : input.dataset.savedPlaceholder;
    btn.textContent = removing ? 'Keep' : 'Remove';
  };
  input.dataset.savedPlaceholder = input.placeholder;
  input.insertAdjacentElement('afterend', btn);
}

function closeSettings() {
  closeOverlay('settingsOverlay');
}

// ── Institutional proxy management ──────────────────────────────────────────
function renderProxyRows() {
  const wrap = document.getElementById('proxyList');
  if (!wrap) return;
  wrap.innerHTML = institutionProxies.map((p, i) => {
    const hasUrl = !!(p.url && p.url.trim());
    const status = hasUrl
      ? `<span class="proxy-status set">✓ ready</span>`
      : `<span class="proxy-status unset">needs setup</span>`;
    const delBtn = p.predefined ? ''
      : `<button class="proxy-del" onclick="deleteCustomInstitution(${i})" title="Remove">✕</button>`;
    return `
      <div class="proxy-row ${i === activeProxy ? 'active' : ''}">
        <input type="radio" name="proxyActive" class="proxy-active" ${i === activeProxy ? 'checked' : ''}
               ${hasUrl ? '' : 'disabled'} onchange="pickActiveInSettings(${i})"
               title="${hasUrl ? 'Use this institution' : 'Add a proxy URL first'}">
        <span class="proxy-name">${escHtml(p.label)}</span>
        ${status}
        <button class="proxy-edit" onclick="openProxyEditor(${i})">${hasUrl ? 'Edit' : 'Set up'}</button>
        ${delBtn}
      </div>`;
  }).join('');
}

function pickActiveInSettings(i) {
  activeProxy = i;
  renderProxyRows();
}

function deleteCustomInstitution(i) {
  institutionProxies.splice(i, 1);
  if (activeProxy >= institutionProxies.length) activeProxy = Math.max(-1, institutionProxies.length - 1);
  renderProxyRows();
  renderProxyPicker();
}

// ── Add/edit institution popup ──────────────────────────────────────────────
let editingProxyIndex = null;   // index being edited, or null for "add new"

function openProxyEditor(i) {
  editingProxyIndex = (typeof i === 'number') ? i : null;
  const isEdit = editingProxyIndex !== null;
  const inst = isEdit ? institutionProxies[editingProxyIndex] : null;
  document.getElementById('proxyEditorTitle').textContent =
    isEdit ? `Set up ${inst.label}` : 'Add an institution';
  const labelField = document.getElementById('proxyEditorLabelField');
  const labelInput = document.getElementById('proxyEditorLabel');
  // Predefined institutions have a fixed name; hide the label field for them
  if (isEdit && inst.predefined) {
    labelField.style.display = 'none';
  } else {
    labelField.style.display = '';
    labelInput.value = isEdit ? (inst.label || '') : '';
  }
  document.getElementById('proxyEditorUrl').value = isEdit ? (inst.url || '') : '';
  openOverlay('proxyEditorOverlay');
  setTimeout(() => document.getElementById('proxyEditorUrl').focus(), 50);
}

function closeProxyEditor() {
  closeOverlay('proxyEditorOverlay');
  editingProxyIndex = null;
}

function saveProxyEditor() {
  const url = document.getElementById('proxyEditorUrl').value.trim();
  const labelInput = document.getElementById('proxyEditorLabel');
  if (editingProxyIndex !== null) {
    // Editing an existing institution
    institutionProxies[editingProxyIndex].url = url;
    if (!institutionProxies[editingProxyIndex].predefined) {
      institutionProxies[editingProxyIndex].label = labelInput.value.trim() || 'Institution';
    }
    // If it now has a URL and nothing is active yet, make it active
    if (url && activeProxy === -1) activeProxy = editingProxyIndex;
  } else {
    // Adding a new custom institution
    if (!url) { closeProxyEditor(); return; }
    institutionProxies.push({id: null, label: labelInput.value.trim() || 'Institution', url: url, predefined: false});
    if (activeProxy === -1) activeProxy = institutionProxies.length - 1;
  }
  closeProxyEditor();
  renderProxyRows();
  renderProxyPicker();
}

// The Library picker in the Options panel. Hidden when no proxies exist.
function renderProxyPicker() {
  const sel = document.getElementById('proxyPicker');
  if (!sel) return;
  // Only offer institutions that actually have a proxy URL configured.
  // Keep the original merged-list index as the option value so selecting it
  // sets the right active proxy.
  const usable = institutionProxies
    .map((p, i) => ({p, i}))
    .filter(x => x.p.url && x.p.url.trim());
  const rowLabel = document.getElementById('proxyRowLabel');
  if (!usable.length) {
    sel.style.display = 'none';
    if (rowLabel) rowLabel.hidden = true;
    return;
  }
  sel.style.display = '';
  if (rowLabel) rowLabel.hidden = false;
  const opts = usable.map(({p, i}) =>
    `<option value="${i}" ${i === activeProxy ? 'selected' : ''}>${escHtml(p.label || 'Library')}</option>`
  ).join('');
  sel.innerHTML = opts + `<option value="-1" ${activeProxy === -1 ? 'selected' : ''}>No library</option>`;
}

function onProxyPick(val) {
  activeProxy = parseInt(val, 10);
  // Persist the choice
  fetch('/proxy/active', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({index: activeProxy})
  }).catch(() => {});
  // Re-render visible result cards so DOI links use the new proxy
  rerenderVisibleCards();
}

// Re-render the currently-displayed article cards in place (e.g. after the
// active proxy changes, so DOI links point at the right library).
function rerenderVisibleCards() {
  document.querySelectorAll('.article-card').forEach(card => {
    const idx = parseInt((card.id || '').replace('card_', ''), 10);
    const a = allArticles[idx];
    if (!a) return;
    const fresh = makeCard(a);
    fresh.id = card.id;
    card.replaceWith(fresh);
  });
  applyResultFilters();
}

async function saveSettings() {
  const raw = {
    anthropic_api_key: document.getElementById('set_anthropic').value.trim(),
    pubmed_api_key:    document.getElementById('set_pubmed').value.trim(),
    scopus_api_key:    document.getElementById('set_scopus').value.trim(),
    scopus_insttoken:  document.getElementById('set_scopus_insttoken').value.trim(),
    wos_api_key:       document.getElementById('set_wos').value.trim(),
    unpaywall_email:   document.getElementById('set_email').value.trim(),
  };
  // Only send fields the user actually filled in, so blank fields don't
  // wipe previously-saved keys (the masked placeholder means "already set").
  const payload = {};
  for (const [k, v] of Object.entries(raw)) {
    if (v && !_keysToClear.has(k)) payload[k] = v;
  }
  payload.clear = [..._keysToClear];
  // Proxies: send the full list (drop empty rows) + the active index.
  // Persist proxies that have a URL. Keep the `id` for predefined institutions
  // so their URL rehydrates into the right slot on reload (and isn't duplicated
  // as a custom entry). Custom institutions have id null.
  const cleanProxies = institutionProxies
    .filter(p => (p.url || '').trim())
    .map(p => ({
      ...(p.id ? {id: p.id} : {}),
      label: (p.label || '').trim() || 'Institution',
      url: (p.url || '').trim(),
    }));
  payload.institution_proxies = cleanProxies;
  payload.active_proxy = activeProxy;

  await fetch('/settings', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  // Reflect saved proxies locally (rebuild merged list) and refresh the picker
  savedProxies = cleanProxies;
  institutionProxies = buildInstitutions();
  renderProxyPicker();
  // Refresh the Scopus/WoS badges to reflect any newly-added (or removed) keys
  try {
    const s = await (await fetch('/settings')).json();
    refreshDbKeyBadges(!!(s.scopus_api_key), !!(s.wos_api_key));
  } catch(e) {}
  closeSettings();
  showToast('Settings saved.', 'green');
}

// ── History ────────────────────────────────────────────────────────────────
function reuseQuery(q) {
  document.getElementById('searchInput').value = q;
  runSearch();
}
function updateHistory(q) {
  const list = document.getElementById('historyList');
  // A repeated search moves to the top rather than being listed twice.
  [...list.querySelectorAll('.history-item')].forEach(i => { if (i.dataset.query === q) i.remove(); });
  const item = document.createElement('div');
  item.className = 'history-item';
  item.dataset.query = q;
  item.innerHTML =
    `<span class="history-text" onclick="reuseQuery(this.parentNode.dataset.query)">${escHtml(q)}</span>
     <button class="history-delete" onclick="deleteRecent(this.parentNode.dataset.query, event)" title="Remove">✕</button>`;
  list.prepend(item);
}

// ── Three-dots menus ───────────────────────────────────────────────────────
function toggleDotsMenu(id, event) {
  event.stopPropagation();
  const menu = document.getElementById(id);
  const isOpen = menu.classList.contains('open');
  // close all menus first
  document.querySelectorAll('.dots-menu').forEach(m => m.classList.remove('open'));
  if (!isOpen) menu.classList.add('open');
}
// click anywhere else closes menus
document.addEventListener('click', () => {
  document.querySelectorAll('.dots-menu').forEach(m => m.classList.remove('open'));
  document.querySelectorAll('.scihub-alts.open').forEach(m => m.classList.remove('open'));
});

// Reveal alternative Sci-Hub mirrors for one article card
function toggleScihubAlts(event, idx) {
  event.stopPropagation();
  event.preventDefault();
  const menu = document.getElementById('scihub_alts_' + idx);
  if (!menu) return;
  const wasOpen = menu.classList.contains('open');
  // close any other open ones
  document.querySelectorAll('.scihub-alts.open').forEach(m => m.classList.remove('open'));
  if (!wasOpen) menu.classList.add('open');
}

// ── Delete individual recent query ─────────────────────────────────────────
function deleteRecent(q, event) {
  event.stopPropagation();
  const list = document.getElementById('historyList');
  [...list.querySelectorAll('.history-item')].forEach(i => {
    if (i.dataset.query === q) i.remove();
  });
  fetch('/history/delete', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({query: q})
  });
}

function clearAllRecent() {
  document.querySelectorAll('.dots-menu').forEach(m => m.classList.remove('open'));
  document.getElementById('historyList').innerHTML = '';
  fetch('/history/clear', {method: 'POST'});
  showToast('Recent searches cleared', '');
}

async function clearAllSaved() {
  document.querySelectorAll('.dots-menu').forEach(m => m.classList.remove('open'));
  const yes = await ask({title: 'Remove all saved searches?', text: 'This cannot be undone.',
                        okLabel: 'Remove all', danger: true});
  if (!yes) return;
  const res  = await fetch('/saved/clear', {method: 'POST'});
  const data = await res.json();
  renderSaved(data.saved || []);
  showToast('All saved searches removed', '');
}

// ── Saved searches ─────────────────────────────────────────────────────────
async function saveCurrentSearch() {
  if (!lastSearchParams) { fail('Run a search first.'); return; }
  const name = await ask({title: 'Name this saved search', input: lastSearchParams.query, okLabel: 'Save'});
  if (name === null) return;   // cancelled
  const payload = {...lastSearchParams, name: name.trim() || lastSearchParams.query};
  const res  = await fetch('/saved', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  renderSaved(data.saved);
  showToast('Search saved.', 'green');
}

function renderSaved(items) {
  const list = document.getElementById('savedList');
  if (!items || !items.length) {
    list.innerHTML = '<div class="saved-empty">No saved searches yet</div>';
    return;
  }
  list.innerHTML = items.map(s => `
    <div class="saved-item" data-id="${s.id}">
      <div class="saved-item-main" onclick='runSaved(${JSON.stringify(s).replace(/'/g,"&#39;")})'>
        <div class="saved-name">${escHtml(s.name)}</div>
        <div class="saved-sub">${escHtml(s.query)}</div>
      </div>
      <button class="saved-delete" onclick="deleteSaved('${s.id}', event)" title="Delete">✕</button>
    </div>`).join('');
}

function runSaved(s) {
  // Restore all parameters then search
  document.getElementById('searchInput').value = s.query;
  document.getElementById('maxResults').value  = s.max_results || 10;
  document.getElementById('yearFrom').value    = s.year_from || '';
  document.getElementById('yearTo').value      = s.year_to   || '';
  document.getElementById('strictToggle').checked = (s.strict !== false);
  // Restore sort mode (defaults to relevance for older saved searches)
  setSortMode(s.sort === 'date' ? 'date' : 'relevance', true);
  updateQueryHint();

  // Restore database selection
  document.querySelectorAll('.db-item').forEach(item => {
    const on = (s.sources || []).includes(item.dataset.db);
    item.classList.toggle('checked', on);
  });

  runSearch();
}

async function deleteSaved(id, event) {
  event.stopPropagation();   // don't trigger runSaved
  const res  = await fetch('/saved/' + id, {method: 'DELETE'});
  const data = await res.json();
  renderSaved(data.saved);
  showToast('Saved search removed', '');
}

// ── MeSH ──────────────────────────────────────────────────────────────────
function useMesh(term) {
  document.getElementById('searchInput').value = term;
  updateQueryHint();
  showToast('Search box updated. Press Search to run it.', '');
}

// ── Helpers ────────────────────────────────────────────────────────────────
// One of the drawn line icons in the page's <svg> sprite.
function ico(name) { return `<svg class="ico" aria-hidden="true"><use href="#i-${name}"/></svg>`; }

function setStatus(state, text) {
  const dot = document.getElementById('statusDot');
  dot.className = 'status-dot ' + (state === 'idle' ? '' : state);
  document.getElementById('statusText').textContent = text;
}

// ── Overlays ───────────────────────────────────────────────────────────────
// A dialog arrives and leaves along the same path (a short rise and fade, no
// overshoot), and does not move at all for someone whose system asks for
// reduced motion. Web Animations API, no library.
const _reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const _EASE = 'cubic-bezier(0.2, 0, 0, 1)';
function _panelOf(overlay) { return overlay.firstElementChild; }

function openOverlay(id) {
  const ov = document.getElementById(id);
  if (!ov || ov.classList.contains('open')) return;
  ov.classList.add('open');
  const panel = _panelOf(ov);
  if (_reduceMotion.matches || !panel || !panel.animate) return;
  ov.animate([{opacity: 0}, {opacity: 1}], {duration: 180, easing: 'linear'});
  panel.animate([{opacity: 0, transform: 'translateY(8px) scale(0.985)'},
                 {opacity: 1, transform: 'none'}], {duration: 220, easing: _EASE});
}

function closeOverlay(id) {
  const ov = document.getElementById(id);
  if (!ov || !ov.classList.contains('open')) return;
  const panel = _panelOf(ov);
  if (_reduceMotion.matches || !panel || !panel.animate) { ov.classList.remove('open'); return; }
  ov.animate([{opacity: 1}, {opacity: 0}], {duration: 160, easing: 'linear'});
  const a = panel.animate([{opacity: 1, transform: 'none'},
                           {opacity: 0, transform: 'translateY(8px) scale(0.985)'}],
                          {duration: 160, easing: _EASE});
  a.onfinish = () => ov.classList.remove('open');
}

// ── Dock panels ────────────────────────────────────────────────────────────
// A panel opens from its trigger (top bar → drops down, dock → rises up),
// centred on it and scaled from it, so where it came from stays obvious.
// One panel at a time; a click elsewhere, Escape, or the trigger closes it.
function _openPanel() { return document.querySelector('.dock-panel:not([hidden])'); }

function togglePanel(id, trigger) {
  const panel = document.getElementById(id);
  const wasOpen = !panel.hidden;
  closePanels(true);
  if (wasOpen) return;
  const fromTop = !!trigger.closest('.topbar');
  panel.classList.toggle('from-top', fromTop);
  panel.classList.toggle('from-bottom', !fromTop);
  panel.hidden = false;
  const r = trigger.getBoundingClientRect();
  const w = panel.offsetWidth;
  const left = Math.max(12, Math.min(window.innerWidth - w - 12, r.left + r.width / 2 - w / 2));
  panel.style.left = left + 'px';
  panel.style.transformOrigin = `${r.left + r.width / 2 - left}px ${fromTop ? '0%' : '100%'}`;
  panel._trigger = trigger;
  trigger.classList.add('on');
  trigger.setAttribute('aria-expanded', 'true');
  if (!_reduceMotion.matches && panel.animate) {
    panel.animate([{opacity: 0, transform: 'scale(0.96)'}, {opacity: 1, transform: 'none'}],
                  {duration: 200, easing: _EASE});
  }
  const first = panel.querySelector('input, select, button, [tabindex]');
  if (first && fromTop === false) setTimeout(() => first.focus({preventScroll: true}), 30);
}

function closePanels(instant) {
  const panel = _openPanel();
  if (!panel) return;
  const t = panel._trigger;
  if (t) { t.classList.remove('on'); t.setAttribute('aria-expanded', 'false'); }
  if (instant || _reduceMotion.matches || !panel.animate) { panel.hidden = true; return; }
  const a = panel.animate([{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'scale(0.96)'}],
                          {duration: 150, easing: _EASE});
  a.onfinish = () => { panel.hidden = true; };
}

// A click outside the open panel (and outside the bar that opened it) closes it.
document.addEventListener('mousedown', e => {
  const panel = _openPanel();
  if (!panel) return;
  if (panel.contains(e.target) || (panel._trigger && panel._trigger.contains(e.target))) return;
  closePanels();
});

// Escape closes the top-most open dialog (the last one in the page order),
// and only that one: an error raised over Settings closes, Settings stays.
// With nothing else open, it closes the synthesis sheet.
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (_openPanel() && !document.querySelector('.modal-overlay.open, .pdf-overlay.open')) {
    e.preventDefault(); closePanels(); return;
  }
  const open = [...document.querySelectorAll('.modal-overlay.open, .pdf-overlay.open')];
  const top = open[open.length - 1];
  if (!top) { if (synthesisOpen) { e.preventDefault(); closeSynthesis(); } return; }
  const closers = {failOverlay: closeFail, askOverlay: () => closeAsk(null), explainOverlay: closeExplain, citeOverlay: closeCitations,
                   settingsOverlay: closeSettings, exportOverlay: closeExport,
                   apiKeyPromptOverlay: closeApiKeyPrompt, proxyEditorOverlay: closeProxyEditor,
                   pdfOverlay: closePdf, updateOverlay: closeUpdate};
  if (closers[top.id]) { e.preventDefault(); closers[top.id](); }
});

// ask({title, text, input, okLabel, danger}) → Promise. With `input` (the
// starting value) it resolves to the typed text, else to true; Cancel,
// Escape or a click outside resolve to null.
let _askResolve = null, _askReturnFocus = null;
function ask(o) {
  document.getElementById('askTitle').textContent = o.title || '';
  document.getElementById('askText').textContent  = o.text || '';
  const field = document.getElementById('askField');
  const input = document.getElementById('askInput');
  const hasInput = o.input !== undefined;
  field.hidden = !hasInput;
  input.value = hasInput ? o.input : '';
  input.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); closeAsk(true); } };
  const ok = document.getElementById('askOk');
  ok.textContent = o.okLabel || 'OK';
  ok.classList.toggle('danger', !!o.danger);
  _askReturnFocus = document.activeElement;
  openOverlay('askOverlay');
  setTimeout(() => { if (hasInput) { input.focus(); input.select(); } else ok.focus(); }, 30);
  return new Promise(res => { _askResolve = res; });
}
function closeAsk(confirmed) {
  const res = _askResolve; _askResolve = null;
  const hasInput = !document.getElementById('askField').hidden;
  closeOverlay('askOverlay');
  if (_askReturnFocus && _askReturnFocus.focus) _askReturnFocus.focus();
  if (res) res(confirmed ? (hasInput ? document.getElementById('askInput').value : true) : null);
}

let _failReturnFocus = null;
function fail(message, title) {
  document.getElementById('failTitle').textContent = title || "Couldn't do that";
  document.getElementById('failText').textContent  = message || '';
  _failReturnFocus = document.activeElement;
  openOverlay('failOverlay');
  setTimeout(() => document.getElementById('failOk').focus(), 30);
}
function closeFail() {
  closeOverlay('failOverlay');
  if (_failReturnFocus && _failReturnFocus.focus) _failReturnFocus.focus();
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className   = 'toast show' + (type ? ' '+type : '');
  setTimeout(() => t.className = 'toast', 3500);
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function escAttr(s) {
  // Used inside single-quoted JS string literals in onclick="..." handlers.
  // Escape backslashes first, then quotes and newlines, to avoid breakout.
  return String(s)
    .replace(/\\/g, '\\\\')
    .replace(/'/g, "\\'")
    .replace(/"/g, '&quot;')
    .replace(/\n/g, ' ')
    .replace(/\r/g, '');
}

// ── Keyboard shortcut ──────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    document.getElementById('searchInput').focus();
  }
});
