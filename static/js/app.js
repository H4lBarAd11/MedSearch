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
          '{Click} <strong>Settings</strong> in the bar {window}.',
          'Paste your <strong>Anthropic key</strong> to enable AI summaries and synthesis. Get one free at <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>.',
          '{Click} <strong>Save</strong>. That\'s the only key you need for the AI features.',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-search\"/></svg> How to search',
        steps: [
          'Type your topic in the bar at the top and press <strong>Search</strong>.',
          '{Click} the <strong>sources</strong> button {sourcesWhere} to tick the databases you want (PubMed, Cochrane and others are free).',
          'Keep <strong>Strict</strong> on for focused results; turn it off to search more broadly.',
          'To find a paper you already know, paste its <strong>DOI</strong>, a doi.org link or the article\'s link (several DOIs work too).',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Useful features',
        steps: [
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-star\"/></svg> Save</strong> a search to re-run it later with one {click}.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Explain</strong> any article for a plain-language breakdown.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-cite\"/></svg> Citations</strong> shows what a paper cites and what cites it.',
          '<strong>Institutional access:</strong> add your university\'s library proxy in Settings, and paywalled papers your institution subscribes to open through your library login. Pick it under <strong>Options</strong> in the bottom bar.',
        ],
      },
    ],
    note: '<strong>Optional keys:</strong> Scopus, Web of Science, IEEE Xplore, Semantic Scholar and Google Books need a key to be searched; keys for PubMed, OpenAlex and CORE raise their limits. Everything else works without them.',
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
          '{Click} <strong>Settings</strong> nella barra {window}.',
          'Incolla la tua <strong>chiave Anthropic</strong> per attivare i riassunti e la sintesi IA. Ottienine una gratis su <a href="https://console.anthropic.com" target="_blank">console.anthropic.com</a>.',
          '{Click} <strong>Save</strong>. È l\'unica chiave necessaria per le funzioni IA.',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-search\"/></svg> Come cercare',
        steps: [
          'Scrivi l\'argomento nella barra in alto e premi <strong>Search</strong>.',
          '{Click} il pulsante delle <strong>fonti</strong> {sourcesWhere} per scegliere i database (PubMed, Cochrane e altri sono gratuiti).',
          'Tieni <strong>Strict</strong> attivo per risultati mirati; disattivalo per cercare in modo più ampio.',
          'Per trovare un articolo che conosci già, incolla il suo <strong>DOI</strong>, un link doi.org o il link dell\'articolo (anche più DOI insieme).',
        ],
      },
      {
        title: '<svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Funzioni utili',
        steps: [
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-star\"/></svg> Save</strong> salva una ricerca per rieseguirla con un {click}.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-sparkle\"/></svg> Explain</strong> spiega qualsiasi articolo in linguaggio semplice.',
          '<strong><svg class=\"ico\" aria-hidden=\"true\"><use href=\"#i-cite\"/></svg> Citations</strong> mostra cosa cita un articolo e da chi è citato.',
          '<strong>Accesso istituzionale:</strong> aggiungi il proxy della biblioteca universitaria nelle Impostazioni e gli articoli a pagamento a cui la tua istituzione è abbonata si apriranno con le tue credenziali. Selezionalo in <strong>Options</strong> nella barra in basso.',
        ],
      },
    ],
    note: '<strong>Chiavi opzionali:</strong> Scopus, Web of Science, IEEE Xplore, Semantic Scholar e Google Books richiedono una chiave per essere cercati; le chiavi di PubMed, OpenAlex e CORE alzano i loro limiti. Tutto il resto funziona anche senza.',
    note2: '<strong>Scopus e Web of Science:</strong> funzionano solo dalla <strong>rete della tua istituzione</strong>. Da casa, connettiti alla VPN dell\'università, oppure chiedi alla biblioteca un "institutional token" Elsevier e inseriscilo nelle Impostazioni. Se vedi un errore 401, sei fuori dalla rete.',
  },
};

let _onboardLang = 'en';

// WHERE THINGS ARE, AND WHAT A FINGER DOES, IN WORDS. The sources button sits
// beside Search in a wide window, and above the bottom bar on a phone and
// under the iOS app's own bars; a finger taps where a mouse clicks (his
// phone, 20 Oct: "beside it" was untrue there). {name} in the text is
// replaced at the moment it is shown.
function sourcesAtBottom() {
  return document.documentElement.classList.contains('native-chrome') ||
         window.matchMedia('(max-width: 700px)').matches;
}
function layoutWords(text, lang) {
  const touch = window.matchMedia('(pointer: coarse)').matches;
  const bottom = sourcesAtBottom();
  const w = (lang || 'en') === 'it'
    ? {Click: touch ? 'Tocca' : 'Clicca', click: touch ? 'tocco' : 'clic',
       window: touch ? 'in basso' : 'in basso nella finestra',
       sourcesWhere: bottom ? 'sopra la barra in basso' : 'accanto a Search'}
    : {Click: touch ? 'Tap' : 'Click', click: touch ? 'tap' : 'click',
       window: touch ? 'at the bottom of the screen' : 'at the bottom of the window',
       sourcesWhere: bottom ? 'just above the bottom bar' : 'beside Search'};
  return String(text).replace(/\{(\w+)\}/g, (m, k) => (k in w ? w[k] : m));
}
function emptyHint() {
  return sourcesAtBottom()
    ? 'Type your question in the bar above, pick your sources just above the bottom bar, and press Search.'
    : 'Type your question in the bar above, pick your sources beside it, and press Search.';
}

function renderOnboardBody() {
  const t = ONBOARD_CONTENT[_onboardLang];
  let html = `<div class="onboard-welcome">${t.welcome}</div>
    <div class="onboard-purpose">${t.purpose}</div>`;
  t.sections.forEach(sec => {
    html += `<div class="onboard-section"><h3>${sec.title}</h3>`;
    sec.steps.forEach((step, i) => {
      html += `<div class="onboard-step">
        <span class="onboard-step-num">${i+1}</span>
        <span>${layoutWords(step, _onboardLang)}</span></div>`;
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
// Checked when MedSearch starts and each time its window comes back: it lives
// on in the menu bar, so its start can be weeks ago. At most once a minute:
// coming back to the window many times in a row needs one answer. "Later" puts the offer off
// until the next day (the server keeps that); Settings ▸ Check for updates asks
// at any time and always says what it found.
let _updateOffered = null;     // the version the open popup offers
let _lastUpdateCheck = 0;

// What a check's answer calls for: 'offer', 'latest', 'unreachable', or null
// for nothing. Asked from Settings, there is always an answer; by itself, the
// window speaks only to offer an update that was not put off today.
function updateVerdict(data, manual) {
  if (!data || !data.ok) return manual ? 'unreachable' : null;
  if (!data.update_available) return manual ? 'latest' : null;
  return (manual || !data.deferred) ? 'offer' : null;
}

function checkForUpdate(manual) {
  _lastUpdateCheck = Date.now();
  return fetch('/update/check')
    .then(r => r.json())
    .catch(() => null)
    .then(data => {
      const verdict = updateVerdict(data, manual);
      if (verdict === 'offer') showUpdateOffer(data);
      else if (verdict === 'latest') showToast(`MedSearch ${data.local} is the latest version.`, 'green');
      else if (verdict === 'unreachable') fail("MedSearch couldn't reach GitHub, where its updates are published. "
                                               + 'Check the internet connection and try again.', "Couldn't check for updates");
    });
}

// Launch, and the window coming back. Never over another dialog or the PDF
// viewer: the next time the window comes back will do. Before the page has loaded, the load
// handler below decides, since the welcome dialog may be about to open.
function autoCheckForUpdate() {
  if (MS.onIOS) return;        // the App Store (or Xcode) updates the iOS app
  if (document.readyState !== 'complete') return;
  if (Date.now() - _lastUpdateCheck < 60000) return;
  if (document.querySelector('.modal-overlay.open, .pdf-overlay.open')) return;
  checkForUpdate(false);
}

// Settings ▸ Check for updates.
function checkForUpdatesNow() {
  const btn = document.getElementById('updateCheckBtn');
  btn.disabled = true;
  btn.textContent = 'Checking…';
  checkForUpdate(true).finally(() => {
    btn.disabled = false;
    btn.textContent = 'Check for updates';
  });
}

// The popup is set up afresh each time: an update that failed earlier in this
// session left its own title and buttons in it.
function showUpdateOffer(data) {
  const text = document.getElementById('updateText');
  const actions = document.getElementById('updateActions');
  document.getElementById('updateTitle').textContent = 'Update available';
  document.getElementById('updateProgress').style.display = 'none';
  actions.style.display = 'flex';
  // What the new version changes, when it says so.
  const notes = (data.changes || []).length
    ? `<ul class="update-changes">${data.changes.map(c => `<li>${escHtml(c)}</li>`).join('')}</ul>`
    : '';
  actions.innerHTML = '<button class="btn-secondary" onclick="closeUpdate()">Later</button>'
    + (data.can_apply ? '<button class="btn-primary" id="updateNowBtn" onclick="applyUpdate()">Update now</button>' : '');
  if (data.can_apply) {
    text.innerHTML = `A new version of MedSearch is available.<br><br>
      <span class="ver">${escHtml(data.local)}</span> → <span class="ver">${escHtml(data.remote)}</span>
      ${notes}`;
  } else {
    // Run from source: it can't replace itself.
    text.innerHTML = `A new version (<span class="ver">${escHtml(data.remote)}</span>) is available, but this copy can't update itself.${notes}<br><br>
      Download it from <span class="mono">github.com/H4lBarAd11/MedSearch</span>.`;
  }
  _updateOffered = data.remote;
  openOverlay('updateOverlay');
}

// Closing the offer without updating, by Later or Escape, puts it off for the day.
function closeUpdate() {
  if (_updateOffered) {
    fetch('/update/later', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({version: _updateOffered})
    }).catch(() => {});
    _updateOffered = null;
  }
  closeOverlay('updateOverlay');
}

// A failed update keeps the offer, so closing its message puts it off for the
// day as Later does, instead of it coming back each time the window does.
// MedSearch is replaced and reopened by itself once the server answers: the
// window then only says so, and goes.
function applyUpdate() {
  const offered = _updateOffered;
  _updateOffered = null;
  document.getElementById('updateActions').style.display = 'none';
  document.getElementById('updateProgress').style.display = 'flex';
  document.getElementById('updateProgressText').textContent = 'Downloading update…';

  fetch('/update/apply', {method: 'POST'})
    .then(r => r.json())
    .then(data => {
      const prog = document.getElementById('updateProgress');
      const title = document.getElementById('updateTitle');
      const text = document.getElementById('updateText');
      if (data.ok && data.restarting) {
        document.getElementById('updateProgressText').textContent =
          'MedSearch will close and reopen by itself.';
        return;
      }
      if (data.ok) {
        // Nothing to replace: this already is the published version.
        prog.style.display = 'none';
        title.textContent = 'Already up to date';
        text.innerHTML = escHtml(data.message || `You're on the latest version.`);
        document.getElementById('updateActions').style.display = 'flex';
        document.getElementById('updateActions').innerHTML =
          '<button class="btn-primary" onclick="closeUpdate()">Got it</button>';
      } else {
        prog.style.display = 'none';
        _updateOffered = offered;
        title.textContent = 'Update failed';
        text.innerHTML = escHtml(data.message || 'Could not update.') +
          (data.error ? `<br><br><span style="font-size:0.72rem;color:var(--text3);font-family:var(--mono)">${escHtml(data.error)}</span>` : '');
        document.getElementById('updateActions').style.display = 'flex';
        document.getElementById('updateActions').innerHTML =
          '<button class="btn-secondary" onclick="closeUpdate()">Close</button>';
      }
    })
    .catch(e => {
      _updateOffered = offered;
      document.getElementById('updateProgress').style.display = 'none';
      document.getElementById('updateTitle').textContent = 'Update failed';
      document.getElementById('updateText').textContent = 'Could not reach the update service: ' + e.message;
      document.getElementById('updateActions').style.display = 'flex';
    });
}

// Run the update check on launch — but defer if onboarding is showing,
// so we never stack two popups on a first-time user.
window.addEventListener('load', () => {
  if (_onboardingShowing) {
    // wait until they've closed onboarding, then check
    const iv = setInterval(() => {
      if (!document.getElementById('onboardOverlay').classList.contains('open')) {
        clearInterval(iv);
        setTimeout(autoCheckForUpdate, 800);
      }
    }, 1000);
  } else {
    autoCheckForUpdate();
  }
});
// And each time the window comes back: from the menu bar, the Dock, or another app.
window.addEventListener('focus', autoCheckForUpdate);
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'visible') autoCheckForUpdate();
});

// Apply the initial AI on/off state to the UI (hides the dock's Assistant button if off)
// Under the iOS app's native bars, the filter chips leave the hidden top bar
// for a row of their own under the status line.
function placeFilterChips() {
  if (!document.documentElement.classList.contains('native-chrome')) return;
  const host = document.getElementById('nativeFilterHost');
  if (!host) return;
  ['peopleChips', 'languageChip'].forEach(id => {
    const el = document.getElementById(id);
    if (el && el.parentElement !== host) host.appendChild(el);
  });
  host.hidden = false;
  // Each chip and its X is a pair of capsules, so the chips often take two
  // or three rows: the results move down by however tall the rows are.
  if (window.ResizeObserver) new ResizeObserver(() => {
    document.documentElement.style.setProperty('--filter-chips-h', host.offsetHeight + 'px');
  }).observe(host);
}
window.addEventListener('load', () => { placeFilterChips(); const hint = document.querySelector('#emptyState .empty-sub'); if (hint) hint.textContent = emptyHint(); applyAIState(); renderProxyPicker(); loadGuidelineBodies(); maybeAutoSearch(); startPendingSearchPolling(); });

// If launched with a search (/?q=...&src=...), pre-select the
// requested source(s), fill the query, and run the search immediately.
function maybeAutoSearch() {
  const q = MS.autoQuery;
  const src = MS.autoSource;
  if (!q) return;
  runSearchWithSource(q, src, 150);
}

// Fill the query, select the requested source(s), and run the search. Shared by
// the initial deep-link (maybeAutoSearch), the second-launch handoff poller,
// and the menu bar's quick search (statusbar.py, via evaluate_js).
function runSearchWithSource(q, src, delay) {
  if (!q) return;
  const input = document.getElementById('searchInput');
  if (input) input.value = q;
  if (src) {
    // A single source that needs a key it doesn't have is REFUSED, and says
    // so, rather than silently becoming a PubMed search (it used to). "All
    // sources" means all the usable ones, so it skips keyless ones quietly.
    const only = document.querySelector(`.db-item[data-db="${src}"]`);
    if (src !== 'all' && only && only.dataset.needsKey && !dbKeyPresent[only.dataset.needsKey]) {
      showApiKeyPrompt(only.dataset.needsKey);
      return;
    }
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

// Poll for searches queued by a second launch, and run them in THIS window so
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
  sel.onchange = () => {
    updateGuidelineHint();
    fetch('/guidelines/country', {method: 'POST', headers: {'Content-Type': 'application/json'},
                                  body: JSON.stringify({country: sel.value})}).catch(() => {});
  };
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
// URLs are filled in by the user; UniTN's is known and pre-filled. openurl is
// the library's own catalogue, asked about a book (see libraryOpenUrl): UniTN's
// is its Primo discovery service; the others' aren't known.
const PREDEFINED_INSTITUTIONS = [
  {id: 'unitn', label: 'UniTN', url: 'https://ezp.biblio.unitn.it', predefined: true,
   openurl: 'https://strutture-provincia.primo.exlibrisgroup.com/discovery/openurl?institution=39SBT_INST&vid=39SBT_INST:39SBT_UNI_TN'},
  {id: 'asuit', label: 'ASUIT', url: '', predefined: true, openurl: ''},
  {id: 'fbk',   label: 'FBK',   url: '', predefined: true, openurl: ''},
];

// Saved proxies from config: a list of {id?, label, url, openurl?}. Custom ones have no id.
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
      // Saved only when changed from the built-in one, so a corrected
      // built-in address reaches everyone who left it alone.
      openurl: saved && saved.openurl != null ? saved.openurl : base.openurl,
      predefined: true,
      remember: !!(saved && saved.remember_signin === true),
    };
  });
  // Append custom (non-predefined) institutions
  (savedProxies || []).forEach(p => {
    if (!p.id) merged.push({id: null, label: p.label || 'Institution', url: p.url || '',
                            openurl: p.openurl || '',
                            predefined: false, remember: p.remember_signin === true});
  });
  return merged;
}

// The domain a library's sign-in is filled on, from its proxy address:
// https://ezp.biblio.unitn.it → unitn.it. The same rule as signins.domain_of,
// which is the one that decides; this one only says it in Settings.
function signinDomain(url) {
  const shared = new Set(['ac', 'co', 'com', 'edu', 'gov', 'net', 'nhs', 'org']);
  let s = String(url || '').trim().toLowerCase();
  if (s.includes('://')) s = s.slice(s.indexOf('://') + 3);
  let host = s.split('/')[0].split('?')[0].split('#')[0];
  host = host.split('@').pop().split(':')[0].replace(/^\.+|\.+$/g, '');
  const labels = host.split('.').filter(Boolean);
  if (labels.length < 2 || labels.every(x => /^\d+$/.test(x))) return host;
  const second = labels[labels.length - 2];
  const keep = labels.length >= 3 && (second.length <= 2 || shared.has(second)) ? 3 : 2;
  return labels.slice(-keep).join('.');
}

let institutionProxies = buildInstitutions();

// The library picked under Options, or null for No library.
function activeLibrary() {
  if (activeProxy === -1) return null;
  return institutionProxies[activeProxy] || null;
}

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

// ── Author and institution ─────────────────────────────────────────────────
// A search can be narrowed to an author and to an institution (Options).
// Picked from OpenAlex's suggestions, each is {name, hint, openalex, orcid};
// typed and not picked, it is {name} alone and searched as written (his
// choice, 2 Oct 2026). Each one in use shows as a chip in the top bar.
const people = {author: null, institution: null};
const PEOPLE_LABEL = {author: 'Author', institution: 'Institution'};
const _suggested = {author: [], institution: []};
const _activeOption = {author: -1, institution: -1};
// Per field, so typing in one never cancels the other's suggestions.
const _suggestTimer = {author: null, institution: null};
const _suggestAsked = {author: 0, institution: 0};

function setPerson(kind, value) {
  people[kind] = value && value.name ? value : null;
  const input = document.getElementById(kind + 'Input');
  if (input) input.value = people[kind] ? people[kind].name : '';
  renderPeopleChips();
}

function clearPeople(kind) {
  setPerson(kind, null);
  hideSuggestions(kind);
}

// What one person or place is, for a chip's tooltip and a saved search's line.
function personLine(kind, p) {
  return `${PEOPLE_LABEL[kind]}: ${p.name}` + (p.openalex ? (p.hint ? ` (${p.hint})` : '') : ' (as typed)');
}

function renderPeopleChips() {
  const box = document.getElementById('peopleChips');
  if (!box) return;
  box.innerHTML = ['author', 'institution'].filter(k => people[k]).map(k => `
    <span class="sources-chip people-chip" title="${escHtml(personLine(k, people[k]))}">
      <button type="button" class="people-chip-name" onclick="openOptionsPanel()"><span>${PEOPLE_LABEL[k]}: ${escHtml(people[k].name)}</span></button>
      <button type="button" class="people-chip-x" onclick="clearPeople('${k}')" aria-label="Stop narrowing the search to this ${k}">${ico('close')}</button>
    </span>`).join('');
}

// ── Languages ─────────────────────────────────────────────────────────────
// The languages searches are narrowed to, two-letter codes with English first,
// kept for the next start. None means any language.
let languages = MS.languages || [];
const LANGUAGE_NAMES = Object.fromEntries(MS.languageNames || []);

// The list after adding one: the first one added brings English with it, and
// English always comes first.
function languagesAfterAdding(list, code) {
  if (!code || list.includes(code)) return list;
  const out = list.length ? [...list, code] : ['en', code];
  return [...out.filter(c => c === 'en'), ...out.filter(c => c !== 'en')].filter((c, i, a) => a.indexOf(c) === i);
}

function languageLabel(list) {
  return list.map(c => LANGUAGE_NAMES[c] || c).join(', ');
}

function setLanguages(list) {
  languages = list;
  renderLanguages();
  fetch('/languages', {method: 'POST', headers: {'Content-Type': 'application/json'},
                       body: JSON.stringify({languages})}).catch(() => {});
}

function addLanguage(code) { setLanguages(languagesAfterAdding(languages, code)); }
function removeLanguage(code) { setLanguages(languages.filter(c => c !== code)); }

// Options' chips and menu, and the chip beside the search bar while any is set.
function renderLanguages() {
  const list = document.getElementById('languageList');
  const add = document.getElementById('languageAdd');
  const chip = document.getElementById('languageChip');
  if (list) list.innerHTML = languages.length ? languages.map(c => `
    <span class="sources-chip people-chip"><span class="people-chip-name"><span>${escHtml(LANGUAGE_NAMES[c] || c)}</span></span>
      <button type="button" class="people-chip-x" onclick="removeLanguage('${escAttr(c)}')" aria-label="Stop searching in ${escHtml(LANGUAGE_NAMES[c] || c)}">${ico('close')}</button>
    </span>`).join('') : '<span class="language-any">Any</span>';
  if (add) add.innerHTML = '<option value="">Add a language…</option>' +
    Object.keys(LANGUAGE_NAMES).filter(c => !languages.includes(c))
      .map(c => `<option value="${escHtml(c)}">${escHtml(LANGUAGE_NAMES[c])}</option>`).join('');
  if (chip) chip.innerHTML = !languages.length ? '' : `
    <span class="sources-chip people-chip" title="Searching in ${escHtml(languageLabel(languages))} only">
      <button type="button" class="people-chip-name" onclick="openOptionsPanel()"><span>${escHtml(languageLabel(languages))}</span></button>
      <button type="button" class="people-chip-x" onclick="setLanguages([])" aria-label="Search in any language">${ico('close')}</button>
    </span>`;
}

function openOptionsPanel() {
  const panel = document.getElementById('panelOptions');
  if (panel.hidden) togglePanel('panelOptions', document.getElementById('dockOptions'));
}

function suggestionHint(it) {
  const works = Number(it.works || 0);
  return [it.hint, `${works.toLocaleString('en')} paper${works === 1 ? '' : 's'}`, it.orcid ? 'ORCID' : '']
    .filter(Boolean).join(' · ');
}

function showSuggestions(kind, data) {
  const list = document.getElementById(kind + 'List');
  const input = document.getElementById(kind + 'Input');
  _suggested[kind] = data.ok ? (data.items || []) : [];
  _activeOption[kind] = -1;
  if (!data.ok) {
    list.innerHTML = `<div class="people-note">${escHtml(data.message || "OpenAlex didn't answer.")} ` +
                     `What you typed will be searched as written.</div>`;
  } else if (!_suggested[kind].length) {
    list.innerHTML = `<div class="people-note">OpenAlex suggests nothing for this. ` +
                     `It will be searched as written.</div>`;
  } else {
    list.innerHTML = _suggested[kind].map((it, i) => `
      <div class="people-option" role="option" id="${kind}Opt${i}" aria-selected="false"
           onmousedown="event.preventDefault(); pickSuggestion('${kind}', ${i})">
        <div class="people-option-name">${escHtml(it.name)}</div>
        <div class="people-option-hint">${escHtml(suggestionHint(it))}</div>
      </div>`).join('');
  }
  list.hidden = false;
  input.setAttribute('aria-expanded', 'true');
}

function hideSuggestions(kind) {
  const list = document.getElementById(kind + 'List');
  const input = document.getElementById(kind + 'Input');
  if (list) list.hidden = true;
  if (input) { input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); }
}

function pickSuggestion(kind, i) {
  const it = _suggested[kind][i];
  if (!it) return;
  setPerson(kind, {name: it.name, hint: it.hint || '', openalex: it.openalex, orcid: it.orcid || null});
  hideSuggestions(kind);
}

async function askSuggestions(kind, text) {
  const asked = ++_suggestAsked[kind];
  let data;
  try {
    data = await (await fetch(`/people/suggest?kind=${kind}&q=${encodeURIComponent(text)}`)).json();
  } catch (e) {
    data = {ok: false, message: 'MedSearch did not answer.'};
  }
  // Only the answer to the latest keystroke is shown.
  if (asked !== _suggestAsked[kind] || document.getElementById(kind + 'Input').value.trim() !== text) return;
  showSuggestions(kind, data);
}

document.querySelectorAll('.people-input').forEach(input => {
  const kind = input.dataset.kind;
  input.addEventListener('input', () => {
    const text = input.value.trim();
    // Typing changes what is searched: a picked name typed over is a typed one.
    people[kind] = text ? {name: text} : null;
    renderPeopleChips();
    clearTimeout(_suggestTimer[kind]);
    if (text.length < 2) { hideSuggestions(kind); return; }
    _suggestTimer[kind] = setTimeout(() => askSuggestions(kind, text), 250);
  });
  input.addEventListener('keydown', e => {
    const list = document.getElementById(kind + 'List');
    const open = !list.hidden && _suggested[kind].length;
    if (e.key === 'Escape' && !list.hidden) {
      e.preventDefault(); e.stopPropagation(); hideSuggestions(kind); return;
    }
    if (!open) return;
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const n = _suggested[kind].length, cur = _activeOption[kind];
      _activeOption[kind] = e.key === 'ArrowDown' ? (cur + 1) % n : (cur <= 0 ? n - 1 : cur - 1);
      list.querySelectorAll('.people-option').forEach((o, i) => {
        o.classList.toggle('active', i === _activeOption[kind]);
        o.setAttribute('aria-selected', i === _activeOption[kind] ? 'true' : 'false');
      });
      input.setAttribute('aria-activedescendant', `${kind}Opt${_activeOption[kind]}`);
    } else if (e.key === 'Enter' && _activeOption[kind] >= 0) {
      e.preventDefault();
      pickSuggestion(kind, _activeOption[kind]);
    }
  });
  input.addEventListener('blur', () => setTimeout(() => hideSuggestions(kind), 150));
});

// What runSearch sends, and a saved search keeps.
function peopleForSearch() {
  return {author: people.author ? {...people.author} : null,
          institution: people.institution ? {...people.institution} : null};
}

// The search in words: what a saved search is called unless named.
function describeSearch(params) {
  const said = ['author', 'institution'].filter(k => params[k]).map(k => `${k}: ${params[k].name}`);
  if (!said.length) return params.query || '';
  return params.query ? `${params.query} (${said.join('; ')})` : said.join('; ');
}

// Google Scholar's own results page for a search: Scholar has no API, so it
// is opened, not asked. Years go in Scholar's own fields; anything else in
// them (a half-typed year) is left out rather than sent. An author goes in
// Scholar's author: operator, as Scholar writes names: "J Doe".
function scholarAuthor(name) {
  // Words that belong to the family name before it: "van Gogh", "de la Cruz".
  const particles = new Set(['van', 'von', 'der', 'den', 'de', 'del', 'della', 'dei', 'degli',
    'di', 'da', 'dos', 'das', 'do', 'du', 'le', 'la', 'ter', 'ten', 'bin', 'al', 'el']);
  name = String(name || '').replace(/"/g, ' ').replace(/\s+/g, ' ').trim();
  let family, given;
  if (name.includes(',')) {
    [family, given] = [name.slice(0, name.indexOf(',')).trim(), name.slice(name.indexOf(',') + 1).trim()];
  } else {
    const words = name.split(' ');
    let i = words.length - 1;
    while (i > 0 && particles.has(words[i - 1].toLowerCase())) i--;
    family = words.slice(i).join(' ');
    given = words.slice(0, i).join(' ');
    // PubMed's way round: "Doe JA".
    if (words.length > 1 && /^(?:[A-Z]\.?){1,3}$/.test(words[words.length - 1])) {
      family = words.slice(0, -1).join(' ');
      given = words[words.length - 1];
    }
  }
  const initial = (given.match(/\p{L}/u) || [''])[0].toUpperCase();
  return initial ? `${initial} ${family}` : family;
}
function scholarUrl(query, yearFrom, yearTo, author) {
  const words = [query, author ? `author:"${scholarAuthor(author)}"` : ''].filter(Boolean).join(' ');
  const p = new URLSearchParams({q: words});
  if (/^\d{4}$/.test(String(yearFrom || '').trim())) p.set('as_ylo', String(yearFrom).trim());
  if (/^\d{4}$/.test(String(yearTo || '').trim()))   p.set('as_yhi', String(yearTo).trim());
  return 'https://scholar.google.com/scholar?' + p.toString();
}

function openGoogleScholar() {
  const q = (document.getElementById('searchInput').value || '').trim();
  const author = people.author ? people.author.name : '';
  if (!q && !author) {
    fail('Type what to look for in the search box, or set an author under Options, ' +
         'then open Google Scholar.', 'Nothing to search for');
    return;
  }
  closePanels(true);
  if (people.institution)
    showToast("Google Scholar can't be narrowed to an institution: it opens without it.", '');
  openInAppBrowser(scholarUrl(q, document.getElementById('yearFrom').value,
                              document.getElementById('yearTo').value, author), 'Google Scholar');
}

// ── Library resources ─────────────────────────────────────────────────────
// Platforms a library subscribes to that no other app can search: ClinicalKey,
// UpToDate… Each is the address of one search with {q} where the words go,
// opened through the active library in a MedSearch window, as Scholar is.
let libraryResources = MS.libraryResources || {on: [], own: []};
let resourceDraft = null;          // Settings' working copy, saved with Save

// The resources with a Search button: the ready-made ones ticked, in their
// own order, then the user's own.
function activeResources(saved, presets) {
  return [...presets.filter(p => (saved.on || []).includes(p.id)), ...(saved.own || [])];
}

function resourceUrl(template, query) {
  return template.split('{q}').join(encodeURIComponent(query));
}

// Why an address of one's own can't be used, or ''. The server says the same.
function resourceProblem(name, url) {
  if (!name) return 'A library resource has no name.';
  if (!/^https?:\/\/[^\s/]+\.\S+$/.test(url) || url.length > 1000)
    return `${name}: the search address must be a web address, beginning https://, with no spaces.`;
  if (!url.includes('{q}'))
    return `${name}: the search address needs {q} where the words go. Search the site for one word, ` +
           'copy the address, and put {q} in place of the word.';
  return '';
}

// The page arrives with them drawn (index.html); they are drawn again here
// after Settings are saved, in the same form.
function renderResourceButtons() {
  const wrap = document.getElementById('resourceButtons');
  if (!wrap) return;
  wrap.innerHTML = activeResources(libraryResources, MS.resourcePresets || []).map((r, i) =>
    `<button class="select-all-btn scholar-btn" type="button" onclick="openLibraryResource(${i})">` +
    `${ico('external')} Search ${escHtml(r.name)}</button>`).join('');
}

function openLibraryResource(i) {
  const r = activeResources(libraryResources, MS.resourcePresets || [])[i];
  if (!r) return;
  const q = (document.getElementById('searchInput').value || '').trim();
  if (!q) {
    fail(`Type what to look for in the search box, then open ${r.name}.`, 'Nothing to search for');
    return;
  }
  closePanels(true);
  if (people.author || people.institution)
    showToast(`${r.name} can't be narrowed to an author or an institution: it opens with the words only.`, '');
  openInAppBrowser(proxify(resourceUrl(r.url, q)), r.name);
}

// Settings: the ready-made ones to tick, then the user's own, each removable.
function renderResourceList() {
  const wrap = document.getElementById('resourceList');
  if (!wrap || !resourceDraft) return;
  const presets = (MS.resourcePresets || []).map(p => `
    <div class="proxy-row">
      <input type="checkbox" class="proxy-active" ${resourceDraft.on.includes(p.id) ? 'checked' : ''}
             onchange="toggleResource('${escAttr(p.id)}', this.checked)" title="Show Search ${escHtml(p.name)}">
      <span class="proxy-name">${escHtml(p.name)}</span>
    </div>`);
  const own = resourceDraft.own.map((r, i) => `
    <div class="proxy-row">
      <input type="checkbox" class="proxy-active" checked disabled title="Added by you">
      <span class="proxy-name">${escHtml(r.name)}</span>
      <button class="proxy-del" type="button" onclick="removeOwnResource(${i})" title="Remove">${ico('close')}</button>
      <div class="resource-address">${escHtml(r.url)}</div>
    </div>`);
  wrap.innerHTML = [...presets, ...own].join('');
}

function toggleResource(id, on) {
  resourceDraft.on = resourceDraft.on.filter(x => x !== id).concat(on ? [id] : []);
}

// Adds what is typed in the two fields. False, with a popup saying why, when it
// can't be used; true when added or when both fields are empty.
function addOwnResource() {
  const nameEl = document.getElementById('resourceName'), urlEl = document.getElementById('resourceUrl');
  const name = nameEl.value.split(/\s+/).filter(Boolean).join(' '), url = urlEl.value.trim();
  if (!name && !url) return true;
  const problem = resourceProblem(name, url);
  if (problem) { fail(problem, "Couldn't add the library resource"); return false; }
  resourceDraft.own.push({name, url});
  nameEl.value = urlEl.value = '';
  renderResourceList();
  return true;
}

function removeOwnResource(i) {
  resourceDraft.own.splice(i, 1);
  renderResourceList();
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
// ── Appearance: System, Light or Dark ───────────────────────────────────────
// The page's colours change at once (index.html's head script); the engine
// keeps the choice and has the app's own windows follow it (the Mac's
// dialogs, the iPhone's glass bars and alerts).
let appearance = MS.appearance || 'system';
function renderAppearance() {
  document.querySelectorAll('#appearanceToggle .sort-opt').forEach(b => {
    const on = b.dataset.appearance === appearance;
    b.classList.toggle('active', on);
    b.setAttribute('aria-checked', on ? 'true' : 'false');
    b.setAttribute('role', 'radio');
  });
}
function setAppearance(value) {
  if (!['system', 'light', 'dark'].includes(value)) return;
  appearance = value;
  if (window.__msAppearance) window.__msAppearance(value);
  renderAppearance();
  fetch('/appearance', {method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({appearance: value})}).catch(() => {});
}
renderAppearance();

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
  scopus:          MS.hasScopus,
  wos:             MS.hasWos,
  ieee:            MS.hasIeee,
  semanticscholar: MS.hasSemanticscholar,
  googlebooks:     MS.hasGooglebooks,
};

document.querySelectorAll('.db-item').forEach(item => {
  item.addEventListener('click', () => {
    const needsKey = item.dataset.needsKey;   // a key of dbKeyPresent, or undefined
    const turningOn = !item.classList.contains('checked');
    // If enabling a premium DB with no key, prompt gently instead of checking
    if (turningOn && needsKey && !dbKeyPresent[needsKey]) {
      showApiKeyPrompt(needsKey);
      return;   // don't check it
    }
    item.classList.toggle('checked');
    rememberSources();
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
  rememberSources();
});

// The ticks MedSearch starts with may already be all of them.
document.getElementById('selectAllBtn').textContent =
  [...document.querySelectorAll('.db-item')].every(i => i.classList.contains('checked'))
    ? 'Deselect all' : 'Select all';

// Your own ticks are what MedSearch starts with next time. A quick search from
// the menu bar, or a saved search run again, changes them for that search only:
// only these two clicks call this.
function rememberSources() {
  fetch('/sources', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({sources: getSelectedDBs()})
  }).catch(() => {});
}

function getSelectedDBs() {
  return [...document.querySelectorAll('.db-item.checked')].map(i => i.dataset.db);
}

// The chip beside Search always says what will be searched: "PubMed + 2".
const _DB_SHORT = {pubmed: 'PubMed', cochrane: 'Cochrane', guidelines: 'Guidelines',
                   clinicaltrials: 'ClinicalTrials.gov', arxiv: 'arXiv', scopus: 'Scopus',
                   wos: 'Web of Science', europepmc: 'Europe PMC', openalex: 'OpenAlex',
                   crossref: 'Crossref', core: 'CORE', ieee: 'IEEE Xplore',
                   semanticscholar: 'Semantic Scholar', bookshelf: 'NCBI Bookshelf',
                   openlibrary: 'Open Library', googlebooks: 'Google Books'};
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
renderLanguages();

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
  ieee: {
    name: 'IEEE Xplore',
    intro: 'IEEE Xplore is the engineering and computing library of the IEEE. To search it, you need a free API key:',
    steps: [
      'Go to <a href="https://developer.ieee.org" target="_blank">developer.ieee.org</a>, register and request a key for the Metadata Search API.',
      'Once it is active (this can take a while), copy the key.',
      'Paste it into <strong>Settings</strong> (bottom bar) → IEEE Xplore, and Save.',
    ],
  },
  semanticscholar: {
    name: 'Semantic Scholar',
    intro: 'Semantic Scholar refuses most searches made without a key. The key is free:',
    steps: [
      'Fill in the request form at <a href="https://www.semanticscholar.org/product/api" target="_blank">semanticscholar.org/product/api</a>.',
      'Semantic Scholar sends the key by email.',
      'Paste it into <strong>Settings</strong> (bottom bar) → Semantic Scholar, and Save.',
    ],
  },
  googlebooks: {
    name: 'Google Books',
    intro: 'Google Books answers no searches made without a key. The key is free, from a Google account:',
    steps: [
      'In the <a href="https://console.cloud.google.com/apis/library/books.googleapis.com" target="_blank">Google Cloud console</a>, create a project and turn on the Books API.',
      'Under APIs &amp; Services → Credentials, choose Create credentials → API key, and copy the key it shows: one line beginning <code>AIza</code>.',
      'Paste it into <strong>Settings</strong> (bottom bar) → Google Books, and Save.',
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

// The settings that hold the key each database needs.
const DB_KEY_SETTING = {scopus: 'scopus_api_key', wos: 'wos_api_key', ieee: 'ieee_api_key',
                        semanticscholar: 'semantic_scholar_api_key',
                        googlebooks: 'google_books_api_key'};

// Refresh the badges of the databases that need a key, and the internal state,
// from the settings as /settings returns them (masked: only whether each is set).
function refreshDbKeyBadges(settings) {
  for (const [k, setting] of Object.entries(DB_KEY_SETTING)) {
    dbKeyPresent[k] = !!(settings && settings[setting]);
    const badge = document.getElementById('badge_' + k);
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
let doiLookup  = 0;      // how many DOIs this search looks up (0: an ordinary search)
let doiMissing = null;   // {count, text}: the DOIs nothing was found for

function runSearch(isLoadMore) {
  // Defensive: if called as an event handler (e.g. btn.onclick = runSearch),
  // the first arg is a MouseEvent. Only treat an explicit `true` as load-more.
  isLoadMore = (isLoadMore === true);
  // "Find more" continues the search on screen, even if the box was edited since.
  if (isLoadMore && !lastSearchParams) return;
  const query = isLoadMore ? lastSearchParams.query
                           : document.getElementById('searchInput').value.trim();
  const dbs   = isLoadMore ? lastSearchParams.sources : getSelectedDBs();
  const who   = isLoadMore ? {author: lastSearchParams.author, institution: lastSearchParams.institution}
                           : peopleForSearch();
  if (!query && !who.author && !who.institution) {
    fail('Type what you are looking for in the search box, or set an author or an institution ' +
         'under Options.', 'No search terms');
    return;
  }
  if (!dbs.length) { fail(layoutWords('{Click} the sources button {sourcesWhere} and tick at least one database.'), 'No database selected'); return; }
  if (searchRunning) return;

  searchRunning = true;
  setSearchButtonStop(true);
  if (!isLoadMore) {
    allArticles = [];
    erroredSources.clear();   // fresh error tracking per search
    doiLookup = 0;
    doiMissing = null;
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
    author:      who.author,
    institution: who.institution,
    languages:   [...languages],
    // The server keeps each source's own position, so "load more" asks every
    // source for its next batch rather than skipping by the combined count.
    load_more:   isLoadMore,
  };
  if (isLoadMore) {
    // same filters as the search on screen, only the batch size may change
    const prev = window._lastFullParams || {};
    Object.assign(lastSearchParams, {year_from: prev.year_from, year_to: prev.year_to,
                                     strict: prev.strict, sort: prev.sort,
                                     author: prev.author, institution: prev.institution,
                                     languages: prev.languages});
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
                     'Observational','Review','Case report','Preprint','Registered trial','Book'];
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

// The sticky results header paints the band above itself only while stuck
// (see .results-header.stuck in app.css).
document.getElementById('resultsScroll').addEventListener('scroll', function () {
  const h = document.getElementById('resultsHeader');
  if (!h) return;
  const stickAt = this.getBoundingClientRect().top + 102;   // css: top -16px + 118px padding
  h.classList.toggle('stuck', h.getBoundingClientRect().top <= stickAt + 1);
}, {passive: true});

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
  clearPeople('author');
  clearPeople('institution');
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
      <div class="empty-sub">${emptyHint()}</div>
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
  else if (ev.type === 'doi_lookup') {
    doiLookup = ev.dois.length;
  }
  else if (ev.type === 'source_start') {
    // All sources start together; the count of finished ones is the progress.
    // (Crossref starts last, in a DOI search, once the others have answered.)
    const n = ev.total;
    setStatus('searching', doiLookup
      ? `Looking up ${doiLookup} DOI${doiLookup === 1 ? '' : 's'} in ${n} source${n === 1 ? '' : 's'}…`
      : `Searching ${n} source${n === 1 ? '' : 's'}…`);
    document.getElementById('searchProgress').textContent = `· ${ev.done || 0} of ${n} sources done`;
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
      finalizeSourceGroup(ev.source, ev.count, null, ev.note);
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
  else if (ev.type === 'doi_missing') {
    doiMissing = {count: ev.count, text: ev.text};
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

// When a source finishes: turn spinner into a count, handle empty/error.
// A note says why a source had nothing to give (e.g. it has no DOIs).
function finalizeSourceGroup(source, count, errorText, note) {
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
    body.innerHTML = `<div class="source-empty">${escHtml(note || 'No results from this source.')}</div>`;
  } else if (note && body) {
    // Said above the results it is about (a database that can't be asked for the languages).
    body.insertAdjacentHTML('afterbegin', `<div class="source-empty source-note">${escHtml(note)}</div>`);
  }
}

function finishSearch(query, isLoadMore) {
  searchRunning = false;
  setSearchButtonStop(false);
  searchAbortController = null;
  if (query) updateHistory(query);
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
  const problems = searchProblems(erroredSources, doiMissing, n);
  if (problems) fail(problems.text, problems.title);

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
        <div class="empty-sub">${doiLookup ? 'Check the DOI for a typo.' : 'Try different keywords or expand the date range.'}</div>
      </div>`;
  }

  // "Find more" button. We hide it when a load-more pass added nothing new
  // (sources exhausted), or when there are no results at all.
  const addedSomething = !isLoadMore || (n > (window._countBeforeLoadMore || 0));
  window._countBeforeLoadMore = n;   // remember for the next pass
  // A DOI search has found all there is to find.
  if (n > 0 && addedSomething && !doiLookup) {
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

// The one dialog at the end of a search, or null: every source that failed,
// and the DOIs nothing was found for.
function searchProblems(errored, missing, n) {
  const lines = [...errored].map(([src, text]) => `${src}: ${text}`);
  if (missing) lines.push(missing.text);
  if (!lines.length) return null;
  const title = errored.size === 1 ? `${[...errored.keys()][0]} returned no results`
              : errored.size       ? `${errored.size} sources returned no results`
              : missing.count === 1 ? 'DOI not found' : `${missing.count} DOIs not found`;
  const shown = !n ? '' : errored.size ? `\n\nThe other sources' results are shown.`
                                       : '\n\nThe papers that were found are shown.';
  return {title, text: lines.join('\n\n') + shown};
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

// The button to a free copy, or ''. A PDF opens in the viewer. A book on NCBI
// Bookshelf, read as web pages, opens at its Bookshelf page in a MedSearch
// window; a free Open Library or Google Books book in its reader, which loads
// a page at a time.
function freeCopyButton(a) {
  if (a.access_kind !== 'open' || !a.access_link) return '';
  const reader = a.book && (a.book.bookshelf ? 'Read on Bookshelf'
                            : (a.book.openlibrary || a.book.google) ? 'Read free' : '');
  if (reader)
    return `<button class="link-btn open-access" onclick="openInAppBrowser('${escAttr(a.access_link)}', '${escAttr(a.title || 'Book')}')">${ico('preprint')} ${reader}</button>`;
  return `<button class="link-btn open-access" onclick="openPdf('${escAttr(a.access_link)}', '${escAttr(a.title || 'PDF')}')">${ico('preprint')} Read PDF</button>`;
}

// A book Open Library lends: its edition's page, where Borrow takes a free
// Internet Archive account. The window keeps the sign-in. A book Google Books
// shows some pages of: its preview.
function borrowButton(a) {
  if (!a.book) return '';
  const title = escAttr(a.title || 'Book');
  let out = '';
  if (a.book.borrow)
    out += `<button class="link-btn doi" onclick="openInAppBrowser('${escAttr(a.book.borrow)}', '${title}')">${ico('library')} Borrow</button>`;
  if (a.book.preview)
    out += `<button class="link-btn doi" onclick="openInAppBrowser('${escAttr(a.book.preview)}', '${title}')">${ico('preprint')} Preview</button>`;
  return out;
}

// WorldCat, the libraries' shared catalogue, on this book: by its ISBN when it
// has one, else by its title and first author, which finds every edition. A
// chapter is catalogued as its book, so by the book's title; '' when that is
// not known either.
function worldcatUrl(a) {
  const b = a.book || {};
  const isbn = (b.isbn || [])[0];
  const first = ((a.author_list || [])[0] || '').split(',')[0].trim();
  const q = isbn ? `bn:${isbn}`
          : b.kind === 'chapter' ? (b.title || '').trim()
          : [a.title || '', first].join(' ').trim();
  return q ? 'https://search.worldcat.org/search?' + new URLSearchParams({q}) : '';
}

// The book in the catalogue of the user's own library, through the library's
// OpenURL address (its link resolver or discovery service): the library's page
// for it, which says whether the library holds it or has the e-book, and offers
// a request or an interlibrary loan when it hasn't. A chapter is asked as a
// chapter of its book, '' when neither the book's title nor its ISBN is known.
// '' too when the library has no such address.
function libraryOpenUrl(a, lib) {
  const b = a.book || {};
  const base = ((lib && lib.openurl) || '').trim();
  const chapter = b.kind === 'chapter';
  const isbn = (b.isbn || [])[0];
  const bookTitle = (chapter ? b.title : a.title) || '';
  if (!base || (!isbn && !bookTitle.trim())) return '';
  const first = ((a.author_list || [])[0] || '').split(',')[0].trim();
  const year = /^\d{4}$/.test(String(a.year || '')) ? String(a.year) : '';
  const fields = [
    ['url_ver', 'Z39.88-2004'], ['ctx_ver', 'Z39.88-2004'],
    ['rft_val_fmt', 'info:ofi/fmt:kev:mtx:book'],
    ['rft.genre', chapter ? 'bookitem' : 'book'],
    ['rft.atitle', chapter ? a.title : ''], ['rft.btitle', bookTitle],
    ['rft.isbn', isbn], ['rft.aulast', first], ['rft.date', year],
    ['rft.pub', b.publisher], ['rft_id', a.doi ? `info:doi/${a.doi}` : ''],
  ].filter(([, v]) => v && String(v).trim())
   .map(([k, v]) => `${k}=${encodeURIComponent(String(v).trim())}`).join('&');
  const glue = !base.includes('?') ? '?' : /[?&]$/.test(base) ? '' : '&';
  return base + glue + fields;
}

// A book's ways to a copy beyond the free one: the user's own library, the
// libraries that hold it, and its Open Library page. Bookshelf's books are free
// online, so they have none.
function libraryButtons(a) {
  if (!a.book || a.book.bookshelf) return '';
  const title = escAttr(a.title || 'Book');
  const lib = activeLibrary();
  const own = libraryOpenUrl(a, lib);
  let out = own ? `<button class="link-btn doi" onclick="openInAppBrowser('${escAttr(own)}', '${title}')">${ico('library')} Get it at ${escHtml(lib.label || 'your library')}</button>` : '';
  const worldcat = worldcatUrl(a);
  if (worldcat)
    out += `<button class="link-btn doi" onclick="openInAppBrowser('${escAttr(worldcat)}', '${title}')">${ico('globe')} Find in a library</button>`;
  if (a.book.openlibrary)
    out += `<button class="link-btn doi" onclick="openInAppBrowser('${escAttr(a.book.openlibrary)}', '${title}')">${ico('external')} Open Library</button>`;
  return out;
}

function makeCard(a) {
  const card = document.createElement('div');
  card.className = 'article-card';

  const qClass = a.quartile ? `q${a.quartile[1].toLowerCase()}` : '';
  const qTag   = a.quartile ? `<span class="meta-tag ${qClass}">${escHtml(a.quartile)}</span>` : '';
  const cited  = a.cited_by ? `<span class="meta-tag cited">Cited: ${escHtml(a.cited_by)}</span>` : '';

  let links = freeCopyButton(a) + borrowButton(a);
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
  links += libraryButtons(a);

  const citeBtn = a.doi
    ? `<button class="link-btn cite-btn" onclick="openCitations(${a._idx})">${ico('cite')} Citations</button>`
    : '';
  // when there's no cite button, explain takes the right-push
  const explainBtn = `<button class="link-btn explain-btn${a.doi ? '' : ' push-right'}" onclick="openExplain(${a._idx})">${ico('sparkle')} Explain</button>`;
  // Send this one article straight to Zotero: the desktop app's connector
  // when it is running, else Zotero's web API with the person's key (the
  // iPhone's only way; his phone, 20 Oct: the share sheet was not saving).
  const zoteroBtn = `<button class="link-btn zotero-btn" onclick="sendSingleToZotero(${a._idx}, event)" title="Save to Zotero">${ico('download')} Zotero</button>`;

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
        onclick="toggleAbstract(${a._idx})">Show more ▾</button>`
      : (a.abstract_note ? `<div class="abstract-note">${escHtml(a.abstract_note)}</div>` : '')}
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
  if (synthesisEventSource) { synthesisEventSource.close(); synthesisEventSource = null; }
  panel.getAnimations().forEach(x => x.cancel());   // a slide-out still running
  panel.classList.add('open');
  if (_sheetsSlide() || _sheetsCentred()) _sheetIn(panel);
  setMd(text, '');
  synthesisOpen = true;
  document.getElementById('synthesisStopBtn').style.display = '';

  const es = new EventSource(withToken('/synthesis'));
  synthesisEventSource = es;
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.type === 'chunk') { setMd(text, text._raw + d.text); }
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
    if (!text._raw) { closeSynthesis(); fail('The connection to MedSearch dropped. Try again.', "Couldn't write the synthesis"); }
  };
}

function stopSynthesis() {
  const stopping = !!synthesisEventSource;
  if (synthesisEventSource) {
    synthesisEventSource.close();
    synthesisEventSource = null;
  }
  const text = document.getElementById('synthesisText');
  // Only a synthesis cut off mid-stream says so; a finished one is left alone.
  if (synthesisEventSource === null && stopping && text && text._raw) {
    setMd(text, text._raw + '\n\n— stopped —');
  }
  document.getElementById('synthesisStopBtn').style.display = 'none';
}

function closeSynthesis() {
  stopSynthesis();   // also halts any in-progress generation
  const panel = document.getElementById('synthesisPanel');
  const a = (_sheetsSlide() || _sheetsCentred()) && panel.classList.contains('open') ? _sheetOut(panel) : null;
  synthesisOpen = false;
  if (a) a.onfinish = () => { if (!synthesisOpen) panel.classList.remove('open'); };
  else panel.classList.remove('open');
}

// ── The AI tab: the switch and the monthly limit ────────────────────────────
let aiEnabled = MS.aiOn;
let aiHasKey = MS.hasAiKey;     // follows a Settings save (saveSettings)
let assistantOpen = false;   // declared here so applyAIState() can read it safely on load

// The switch in the AI panel. Without a key, "on" makes no sense: Settings
// opens instead and the switch stays off.
function setAI(on) {
  if (on && !aiHasKey && !aiEnabled) {
    const sw = document.getElementById('aiSwitch');
    if (sw) sw.checked = false;
    fail('Add your Anthropic API key in Settings to use AI features.');
    closePanels(true);
    openSettings();
    return;
  }
  if (on === aiEnabled) return;
  aiEnabled = on;
  applyAIState();
  fetch('/ai/toggle', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({enabled: aiEnabled})
  }).catch(() => {});
  showToast(aiEnabled ? 'AI features enabled.' : 'AI features turned off.', aiEnabled ? 'green' : null);
}
function toggleAI() { setAI(!aiEnabled); }

// Reflect the current AI state across the badge and all AI UI elements
function applyAIState() {
  const badge = document.getElementById('aiBadge');
  if (badge) {
    document.getElementById('aiBadgeLabel').textContent = aiEnabled ? 'AI on' : 'AI off';
    badge.classList.toggle('ai-on', aiEnabled);
    badge.classList.toggle('ai-off', !aiEnabled);
  }
  const sw = document.getElementById('aiSwitch');
  if (sw) sw.checked = aiEnabled;
  const keyHint = document.getElementById('aiKeyHint');
  if (keyHint) keyHint.hidden = !!aiHasKey;
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

// The limit: a switch and an amount, saved as soon as either changes. With
// the switch on, spending stops at the amount — at $0 before the first call.
let _aiCapSaving = null;
function _aiCapFields() {
  const sw = document.getElementById('aiCapSwitch');
  const amount = document.getElementById('set_ai_cap');
  return sw && amount ? {sw, amount} : null;
}
function _showAICap(capOn, amount, cost, overCap) {
  const f = _aiCapFields();
  if (!f) return;
  f.sw.checked = !!capOn;
  f.amount.value = Number.isFinite(amount) ? amount : 0;
  f.amount.disabled = !capOn;
  const row = document.getElementById('aiCapRow');
  if (row) row.classList.toggle('off', !capOn);
  const state = document.getElementById('aiCapState');
  if (state) {
    if (!capOn) state.textContent = 'No limit.';
    else if (overCap) state.textContent = 'Reached: the AI is paused until you raise it.';
    else state.textContent = `$${(Math.max(0, amount - (cost || 0))).toFixed(2)} left this month.`;
  }
}
async function saveAICap() {
  const f = _aiCapFields();
  if (!f) return;
  const capOn = f.sw.checked;
  let amount = parseFloat(f.amount.value);
  if (!Number.isFinite(amount) || amount < 0) amount = 0;
  f.amount.value = amount;
  f.amount.disabled = !capOn;
  try {
    _aiCapSaving = fetch('/settings', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ai_monthly_cap: amount, ai_cap_on: capOn})
    });
    const res = await (await _aiCapSaving).json();
    if (!res.ok) throw new Error(res.message || 'not saved');
  } catch (e) {
    fail('The limit could not be saved: ' + (e.message || e));
    return;
  }
  loadUsage();
}

// What the AI has cost this month and where the limit stands, shown in the
// AI panel. Counted from what the API reports it used, so it follows the
// real calls rather than guessing.
async function loadUsage() {
  const el = document.getElementById('aiSpend');
  if (!el) return;
  try {
    const u = await (await fetch('/usage')).json();
    const jobs = Object.entries(u.calls || {})
      .sort((a, b) => b[1] - a[1])
      .map(([name, n]) => `${n} ${name}`)
      .join(' · ');
    el.textContent = `$${(u.cost || 0).toFixed(2)}` + (jobs ? `  —  ${jobs}` : '  —  nothing yet');
    el.classList.toggle('over', !!u.over_cap);
    _showAICap(!!u.cap_on, Number(u.cap_amount) || 0, u.cost || 0, !!u.over_cap);
  } catch (e) {
    el.textContent = 'not available';
  }
}

let assistantHistory = [];      // [{role, content}, ...]
let assistantStreaming = false;
let assistantSuggestionsLoaded = false;

function toggleAssistant() {
  assistantOpen = !assistantOpen;
  const panel  = document.getElementById('assistantPanel');
  document.getElementById('dockAssistant').classList.toggle('on', assistantOpen);
  if (assistantOpen) {
    panel.getAnimations().forEach(x => x.cancel());   // a slide-out still running
    panel.classList.remove('closing');
    panel.classList.add('open');
    if (_sheetsSlide() || _sheetsCentred()) _sheetIn(panel);
    renderAssistantMessages();
    loadAssistantSuggestions();   // suggestions appear when opened
    setTimeout(() => document.getElementById('assistantInput').focus(), 100);
  } else {
    const a = (_sheetsSlide() || _sheetsCentred()) ? _sheetOut(panel) : null;
    if (a) a.onfinish = () => { if (!assistantOpen) panel.classList.remove('open'); };
    else panel.classList.remove('open');
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
  return renderMd(text).replace(/\[(\d+)\]/g, (m, n) =>
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
// The splash keeps the window hidden until the page says it has loaded
// (splash.py). pywebview's bridge arrives once the page has finished loading.
function tellWindowReady() {
  try { window.pywebview.api.page_ready(); } catch (e) { /* a browser tab: no splash */ }
}
if (window.pywebview && window.pywebview.api && window.pywebview.api.page_ready) tellWindowReady();
else window.addEventListener('pywebviewready', tellWindowReady, {once: true});

// ── The phone: the sources chip in its own pill above the dock ────────────
// A phone-narrow window (touch.css, 700px) shows the search pill with the
// field and Search alone, and the sources chip in a pill of its own at the
// bottom (his choice, 19 Oct). The chip is moved rather than duplicated, so
// it keeps its state and its handlers; a widening window puts it back.
const _phoneQuery = window.matchMedia('(max-width: 700px)');
function placeSourcesChip() {
  const chip = document.getElementById('dockSources');
  const host = document.getElementById('phoneSourcesHost');
  const bar = document.getElementById('topbar');
  if (!chip || !host || !bar) return;
  if (_phoneQuery.matches) {
    if (chip.parentElement !== host) { host.appendChild(chip); host.hidden = false; }
  } else if (chip.parentElement === host) {
    bar.insertBefore(chip, document.getElementById('searchBtn'));
    host.hidden = true;
  }
}
try { _phoneQuery.addEventListener('change', placeSourcesChip); } catch (e) { /* an old engine */ }

document.addEventListener('DOMContentLoaded', () => {
  placeSourcesChip();
  const ai = document.getElementById('assistantInput');
  if (ai) ai.addEventListener('input', () => {
    ai.style.height = 'auto';
    ai.style.height = Math.min(ai.scrollHeight, 110) + 'px';
  });
});

// ── Explain ────────────────────────────────────────────────────────────────
// One explanation at a time: closing the dialog stops its stream, and a
// second paper's never shares the text with the first's.
let _explainSource = null;
function openExplain(idx) {
  const a = allArticles[idx];
  if (!a) return;
  if (_explainSource) { _explainSource.close(); _explainSource = null; }
  document.getElementById('explainTitle').textContent = a.title;
  setMd(document.getElementById('explainText'), '');
  openOverlay('explainOverlay');

  const es = new EventSource(withToken('/explain/' + idx));
  _explainSource = es;
  es.onmessage = e => {
    if (_explainSource !== es) { es.close(); return; }
    const d = JSON.parse(e.data);
    if (d.type === 'chunk') { const el = document.getElementById('explainText'); setMd(el, el._raw + d.text); }
    if (d.type === 'done')  { es.close(); }
    if (d.type === 'error') { es.close(); closeExplain(); fail(d.text, "Couldn't explain this paper"); }
  };
  es.onerror = () => {
    es.close();
    if (_explainSource !== es) return;
    if (!document.getElementById('explainText')._raw) {
      closeExplain(); fail('The connection to MedSearch dropped. Try again.', "Couldn't explain this paper");
    }
  };
}

function closeExplain() {
  if (_explainSource) { _explainSource.close(); _explainSource = null; }
  closeOverlay('explainOverlay');
}

// ── Citation graph ─────────────────────────────────────────────────────────
function openCitations(idx) {
  const a = allArticles[idx];
  if (!a) return;
  document.getElementById('citeTitle').textContent =
    'Citation graph · ' + (a.title.length > 70 ? a.title.slice(0,70)+'…' : a.title);
  document.getElementById('citeBody').innerHTML =
    '<div class="cite-loading">Fetching references & citing papers (PubMed, Scopus, OpenAlex, OpenCitations)…</div>';
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

// Each opening of the viewer is one load: closing it, or opening another,
// aborts the fetch and makes whatever comes back of the old one do nothing
// (no browser window for a paper given up on, no pages under another title).
let _pdfLoad = 0, _pdfAbort = null;
function openPdf(url, title) {
  const load = ++_pdfLoad;
  if (_pdfAbort) _pdfAbort.abort();
  _pdfAbort = typeof AbortController === 'function' ? new AbortController() : null;
  const current = () => load === _pdfLoad;
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

  fetch(proxyUrl, _pdfAbort ? {signal: _pdfAbort.signal} : {})
    .then(async res => {
      if (!current()) return null;
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
      if (!buf || !current()) return;
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
        if (current()) openInAppBrowser(url, title);
      }
    })
    .catch(e => { if (current()) openInAppBrowser(url, title); });
}

// Save the currently-open PDF to Downloads. MedSearch writes the file (/save_pdf):
// a download link here showed the PDF in place of the whole window (26 Sep).
async function savePdf(retried) {
  if (!pdfBytes) { fail('PDF still loading — try again in a moment.'); return; }
  try {
    const res = await fetch('/save_pdf?name=' + encodeURIComponent(pdfFilename), {
      method: 'POST',
      headers: {'Content-Type': 'application/pdf'},
      body: pdfBytes
    });
    const data = await res.json().catch(() => ({}));
    if (data.need_folder && !retried) {         // iOS, no folder picked yet
      if (await pickExportFolder()) return savePdf(true);
      fail('Pick a folder, such as Downloads, for MedSearch to save PDFs in.', 'PDF not saved');
      return;
    }
    if (!res.ok || !data.name) {
      fail(data.error || `MedSearch answered ${res.status}.`, "Couldn't save the PDF");
      return;
    }
    showToast(`Saved to ${data.folder || 'Downloads'}: ${data.name}`, 'green');
  } catch(e) {
    fail('Could not save the PDF: ' + e.message, "Couldn't save the PDF");
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
  _pdfLoad++;
  if (_pdfAbort) { _pdfAbort.abort(); _pdfAbort = null; }
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
    // The source note stays: "nothing found" means little if a source failed.
    body.innerHTML = `<div class="cite-error">
      No references or citing papers found for this article.<br>
      <span style="font-size:0.75rem;color:var(--text3)">
      Coverage is best for articles with a Crossref DOI; very recent or niche papers may not be indexed yet.</span>
    </div>
    <div class="cite-note">${citeSourcesNote(data.cit_sources)}</div>`;
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
    <div class="cite-note">${citeSourcesNote(data.cit_sources)}References from OpenCitations · titles resolved via Crossref</div>`;
}

// Where the "Cited by" list came from, source by source. A source that failed
// or had no key says so, so a short list is never mistaken for a complete one.
function citeSourcesNote(reports) {
  if (!reports || !reports.length) return '';
  const parts = reports.map(r => {
    if (r.status === 'ok')
      return escHtml(r.label) + ' ' + (r.label === 'OpenCitations' ? r.count + ' more' : r.count);
    if (r.status === 'no key')      return escHtml(r.label) + ': no API key set';
    if (r.status === 'not indexed') return escHtml(r.label) + ': does not have this paper';
    return `<span class="cite-note-failed">${escHtml(r.label)} failed: ${escHtml(r.error || '')}</span>`;
  });
  return 'Cited by, from ' + parts.join(' · ') + '<br>';
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
    <div class="cite-item-meta">${meta.join(' · ')} ${doiLink}${item.found_in && item.found_in.length
      ? ` <span class="cite-found-in">${escHtml(item.found_in.join(', '))}</span>` : ''}</div>
  </div>`;
}

// Radial SVG: center node = this paper, references LEFT, citations RIGHT.
// Every node inside the drawing: the outer row used to be placed beyond its
// edges, so on a phone, where the drawing shrinks to a third, the lines ran
// off both sides (his phone, 20 Oct). A narrow screen gets a narrower,
// taller drawing, with this paper's title under it and larger lettering.
function buildCiteGraph(article, refs, cits) {
  const narrow = typeof window !== 'undefined' && window.matchMedia &&
                 window.matchMedia('(max-width: 700px)').matches;
  const W = narrow ? 380 : 860, H = narrow ? 400 : 320;
  const cx = W/2, cy = narrow ? (H - 34) / 2 : H/2;
  const fs = narrow ? 11 : 9;                     // label size, in the drawing's units (inline: app.css sets 9px)
  const inner = narrow ? 46 : 140;                // the gap kept around this paper
  const reach = cx - inner - 22;                  // so the outer row stays inside, label and all
  const vSpan = narrow ? H - 120 : 210;           // vertical spread (clears the side headings)
  const maxPer = 8;  // nodes shown per side in the graph (lists show all)
  const r = refs.slice(0, maxPer);
  const c = cits.slice(0, maxPer);

  let nodes = '', links = '';

  function place(items, side) {
    const n = items.length;
    if (!n) return;
    const dir = (side === 'left' ? -1 : 1);
    items.forEach((it, i) => {
      const x = cx + dir * (inner + reach * (0.35 + 0.65 * (i % 2)));  // stagger depth
      const frac = n === 1 ? 0.5 : i / (n - 1);
      const y = cy - vSpan/2 + frac * vSpan;
      const cls = side === 'left' ? 'cite-node-ref' : 'cite-node-cit';
      links += `<line class="cite-link" x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/>`;
      nodes += `<circle class="${cls}" cx="${x}" cy="${y}" r="8"/>`;
      if (it.year) nodes += `<text class="cite-node-label" x="${x}" y="${y - 13}" text-anchor="middle" style="font-size:${fs}px">${escHtml(String(it.year))}</text>`;
    });
  }
  place(r, 'left');
  place(c, 'right');

  // Center node + label: under the node on a wide drawing, under the whole
  // drawing on a narrow one, where the nodes come close to the middle.
  nodes += `<circle class="cite-node-center" cx="${cx}" cy="${cy}" r="12"/>`;
  const shortTitle = (article.title || '').slice(0, 34) + ((article.title||'').length>34?'…':'');
  nodes += `<text class="cite-node-label" x="${cx}" y="${narrow ? H - 8 : cy + 30}" text-anchor="middle" style="font-size:${fs}px;font-weight:700">${escHtml(shortTitle)}</text>`;
  // side headers, over the middle of each side
  const hx = inner + reach * 0.675;
  nodes += `<text class="cite-axis-label" x="${cx - hx}" y="16" text-anchor="middle">↓ REFERENCES</text>`;
  nodes += `<text class="cite-axis-label" x="${cx + hx}" y="16" text-anchor="middle">↑ CITED BY</text>`;

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
  if (document.getElementById('zoteroRow')) checkZoteroAvailable();   // not on iOS: no connector there
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
        status.textContent = d.via === 'web'
          ? 'Adds all results to your online Zotero library, which your Zotero apps sync.'
          : 'Adds all results straight into your Zotero library.';
        btn.disabled = false;
      } else {
        row.classList.add('unavailable');
        status.textContent = MS.onIOS
          ? 'Add a Zotero API key in Settings to save results to your Zotero library.'
          : 'Zotero isn\'t running. Open the Zotero desktop app, or add a Zotero API key in Settings.';
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

// No desktop Zotero and no key: offer Settings, where the key goes.
async function askForZoteroKey(message) {
  const yes = await ask({title: 'Save to Zotero', text: message, okLabel: 'Open Settings'});
  if (!yes) return;
  await openSettings();
  const field = document.getElementById('set_zotero');
  if (field) setTimeout(() => { field.scrollIntoView({block: 'center'}); field.focus(); }, 300);
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
      showToast(data.message || 'Sent to Zotero!', 'green');
      if (btn) setTimeout(() => { btn.innerHTML = `${ico('download')} Zotero`; btn.disabled = false; }, 2500);
    } else {
      if (btn) { btn.innerHTML = `${ico('download')} Zotero`; btn.disabled = false; }
      if (data.need_key) { askForZoteroKey(data.message); return; }
      fail(data.message || 'Could not send to Zotero.');
    }
  } catch(e) {
    if (btn) { btn.innerHTML = `${ico('download')} Zotero`; btn.disabled = false; }
    fail('Zotero send failed: ' + e.message);
  }
}

// iOS: the folder exports and saved PDFs go to is picked once in Files
// (Downloads), the system's own folder picker; true once one is picked.
// The answer is the folder's name ('' when none was picked), which Settings
// then shows: before, the pick left no trace there (his phone, 21 Oct).
async function pickExportFolder() {
  const native = globalThis.__msNative;
  if (!native || !native.pickFolder) return '';
  const got = await native.pickFolder();
  if (!got) return '';
  const name = typeof got === 'string' ? got : 'the folder you picked';
  const text = document.getElementById('exportsFolderText');
  const btn = document.getElementById('exportsFolderBtn');
  if (text) { text.textContent = 'Saving to '; text.append(Object.assign(document.createElement('b'), {textContent: name}), ', picked in Files.'); }
  if (btn) btn.textContent = 'Change folder…';
  return name;
}

async function doExport(retried) {
  const fmt = document.querySelector('input[name=exportFmt]:checked').value;
  let data;
  try {
    const res = await fetch('/export', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({format: fmt, indices: exportSelection().indices})
    });
    data = await res.json();
  } catch (e) { fail('MedSearch did not answer: ' + e.message, "Couldn't export"); return; }
  if (data.need_folder && !retried) {
    if (await pickExportFolder()) return doExport(true);
    fail('Pick a folder, such as Downloads, for MedSearch to save exports in.', 'Nothing exported');
    return;
  }
  if (data.error || !data.paths) { fail(data.error || 'The export did not finish.', "Couldn't export"); return; }
  const succ = document.getElementById('exportSuccess');
  succ.style.display = 'block';
  succ.textContent = `✓ Saved in ${data.folder}: ${(data.names || data.paths).join(', ')}`;
  if (data.can_show) {
    const show = document.createElement('button');
    show.type = 'button';
    show.className = 'btn-secondary export-show-btn';
    show.textContent = MS.onWindows ? 'Show in Explorer' : 'Show in Finder';
    show.onclick = () => fetch('/exports/show', {method: 'POST'}).then(r => r.json())
      .then(d => { if (!d.ok) fail(d.message, "Couldn't show the exports"); })
      .catch(e => fail(e.message, "Couldn't show the exports"));
    succ.appendChild(document.createTextNode(' '));
    succ.appendChild(show);
  }
  showToast('Export complete!', 'green');
}

// ── Settings ───────────────────────────────────────────────────────────────
// The library edits in Settings act on the live list, so leaving without
// saving puts back what was there (the sweep, 20 Oct).
let _settingsSaved = false, _librariesBefore = null;
async function openSettings() {
  _settingsSaved = false;
  _librariesBefore = {list: JSON.parse(JSON.stringify(institutionProxies)), active: activeProxy};
  openOverlay('settingsOverlay');
  // Load which keys are already saved and indicate them in each field.
  const fields = {
    anthropic_api_key: 'set_anthropic',
    pubmed_api_key:    'set_pubmed',
    scopus_api_key:    'set_scopus',
    scopus_insttoken:  'set_scopus_insttoken',
    wos_api_key:       'set_wos',
    ieee_api_key:      'set_ieee',
    semantic_scholar_api_key: 'set_semanticscholar',
    google_books_api_key: 'set_googlebooks',
    zotero_api_key:    'set_zotero',
    openalex_api_key:  'set_openalex',
    core_api_key:      'set_core',
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
    document.getElementById('loginField').hidden = !data.can_open_at_login;
    document.getElementById('set_open_at_login').checked = !!data.open_at_login;
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
    if (s.library_resources) libraryResources = s.library_resources;
  } catch(e) {}
  renderProxyRows();
  resourceDraft = {on: [...(libraryResources.on || [])],
                   own: (libraryResources.own || []).map(r => ({...r}))};
  document.getElementById('resourceName').value = document.getElementById('resourceUrl').value = '';
  renderResourceList();
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
  if (!_settingsSaved && _librariesBefore) {
    institutionProxies = _librariesBefore.list;
    activeProxy = _librariesBefore.active;
    renderProxyPicker();
  }
  _librariesBefore = null;
  _settingsSaved = false;
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
        ${hasUrl ? `<div class="proxy-remember">
          <label class="settings-check"><input type="checkbox" ${p.remember ? 'checked' : ''}
                 onchange="institutionProxies[${i}].remember = this.checked"> Remember sign-in</label>
          <div class="settings-hint">Kept in ${MS.onWindows ? 'Windows Credential Manager' : 'your Keychain'}; filled only on ${escHtml(signinDomain(p.url))}</div>
        </div>` : ''}
      </div>`;
  }).join('');
}

function pickActiveInSettings(i) {
  activeProxy = i;
  renderProxyRows();
}

function deleteCustomInstitution(i) {
  institutionProxies.splice(i, 1);
  // The active one stays the same library: the ones after it move up one;
  // the active one itself gone means no library.
  if (i < activeProxy) activeProxy--;
  else if (i === activeProxy) activeProxy = -1;
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
  document.getElementById('proxyEditorOpenUrl').value = isEdit ? (inst.openurl || '') : '';
  openOverlay('proxyEditorOverlay');
  setTimeout(() => document.getElementById('proxyEditorUrl').focus(), 50);
}

function closeProxyEditor() {
  closeOverlay('proxyEditorOverlay');
  editingProxyIndex = null;
}

function saveProxyEditor() {
  const url = document.getElementById('proxyEditorUrl').value.trim();
  const openurl = document.getElementById('proxyEditorOpenUrl').value.trim();
  const labelInput = document.getElementById('proxyEditorLabel');
  if (editingProxyIndex !== null) {
    // Editing an existing institution
    institutionProxies[editingProxyIndex].url = url;
    institutionProxies[editingProxyIndex].openurl = openurl;
    if (!institutionProxies[editingProxyIndex].predefined) {
      institutionProxies[editingProxyIndex].label = labelInput.value.trim() || 'Institution';
    }
    // If it now has a URL and nothing is active yet, make it active
    if (url && activeProxy === -1) activeProxy = editingProxyIndex;
  } else {
    // Adding a new custom institution
    if (!url) { closeProxyEditor(); return; }
    institutionProxies.push({id: null, label: labelInput.value.trim() || 'Institution', url: url,
                             openurl: openurl, predefined: false});
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

// A library's OpenURL address as saved: a predefined library's only when it
// differs from the built-in one (an emptied one included, which hides its
// button), so the built-in one can be corrected later; another's when set.
function openUrlToSave(p) {
  const openurl = (p.openurl || '').trim();
  const preset = PREDEFINED_INSTITUTIONS.find(x => p.id && x.id === p.id);
  if (preset) return openurl === preset.openurl ? {} : {openurl};
  return openurl ? {openurl} : {};
}

async function saveSettings() {
  const raw = {
    anthropic_api_key: document.getElementById('set_anthropic').value.trim(),
    pubmed_api_key:    document.getElementById('set_pubmed').value.trim(),
    scopus_api_key:    document.getElementById('set_scopus').value.trim(),
    scopus_insttoken:  document.getElementById('set_scopus_insttoken').value.trim(),
    wos_api_key:       document.getElementById('set_wos').value.trim(),
    ieee_api_key:      document.getElementById('set_ieee').value.trim(),
    semantic_scholar_api_key: document.getElementById('set_semanticscholar').value.trim(),
    google_books_api_key: document.getElementById('set_googlebooks').value.trim(),
    zotero_api_key:    document.getElementById('set_zotero').value.trim(),
    openalex_api_key:  document.getElementById('set_openalex').value.trim(),
    core_api_key:      document.getElementById('set_core').value.trim(),
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
      ...openUrlToSave(p),
      ...(p.remember ? {remember_signin: true} : {}),
    }));
  payload.institution_proxies = cleanProxies;
  payload.active_proxy = activeProxy;
  // A resource typed but not added with its button is added now, or nothing saves.
  if (resourceDraft) {
    if (!addOwnResource()) return;
    payload.library_resources = resourceDraft;
  }
  if (!document.getElementById('loginField').hidden)
    payload.open_at_login = document.getElementById('set_open_at_login').checked;

  const saved = await (await fetch('/settings', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  })).json().catch(() => ({ok: false, message: 'MedSearch did not answer.'}));
  if (!saved.ok) { fail(saved.message || 'Settings could not be saved.', "Couldn't save settings"); return; }
  // A warning means the settings ARE saved; only a part of them didn't apply.
  if (saved.warning) fail(saved.warning, 'Opening at login was not changed');
  // Reflect saved proxies locally (rebuild merged list) and refresh the picker
  savedProxies = cleanProxies;
  institutionProxies = buildInstitutions();
  renderProxyPicker();
  if (payload.library_resources) {
    libraryResources = payload.library_resources;
    renderResourceButtons();
  }
  // Refresh the badges of the keyed databases for any newly-added (or removed) keys
  try {
    const s = await (await fetch('/settings')).json();
    refreshDbKeyBadges(s);
    // A key added makes AI possible; a key removed turns it off here too.
    if (typeof s.has_ai_key === 'boolean') {
      aiHasKey = s.has_ai_key;
      aiEnabled = s.has_ai_key && s.ai_enabled !== false;
      applyAIState();
    }
  } catch(e) {}
  _settingsSaved = true;
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
async function toggleScihubAlts(event, idx) {
  event.stopPropagation();
  event.preventDefault();
  const menu = document.getElementById('scihub_alts_' + idx);
  if (!menu) return;
  // In the iOS app: the system's action sheet, not the page's card (his ask,
  // 21 Oct: everything as Liquid Glass). undefined: it could not show.
  const native = globalThis.__msNative;
  if (native && native.choose) {
    const items = [...menu.querySelectorAll('.scihub-alt-item')];
    const r = event.currentTarget ? event.currentTarget.getBoundingClientRect() : null;
    const i = await native.choose('Other Sci-Hub mirrors', "If this one doesn't work, try:",
                                  items.map(b => b.textContent),
                                  r && {x: r.left, y: r.top, w: r.width, h: r.height});
    if (i !== undefined) { if (i !== null && items[i]) items[i].click(); return; }
  }
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
  const said = describeSearch(lastSearchParams);
  const name = await ask({title: 'Name this saved search', input: said, okLabel: 'Save'});
  if (name === null) return;   // cancelled
  const payload = {...lastSearchParams, name: name.trim() || said};
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
      <div class="saved-item-main" onclick='runSaved(${JSON.stringify(s).replace(/&/g,"&amp;").replace(/'/g,"&#39;")})'>
        <div class="saved-name">${escHtml(s.name)}</div>
        <div class="saved-sub">${escHtml(describeSearch(s))}</div>
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
  setPerson('author', s.author || null);
  setPerson('institution', s.institution || null);
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
// The AI answers in Markdown. Shown raw, every heading arrived as "# …" and
// every emphasis as "**…**" (found on the live walk, 19 Sep). This renders the
// small subset it uses, AFTER escaping, so the text can never inject markup:
// headings, bold, italics, inline code, bullet and numbered lists, paragraphs.
function renderMd(src) {
  const inline = t => t
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>');
  const out = [];
  let list = null, para = [], fence = null;
  const flushPara = () => { if (para.length) { out.push('<p>' + inline(para.join(' ')) + '</p>'); para = []; } };
  const flushList = () => { if (list) { out.push(`<${list.tag}>` + list.items.map(i => '<li>' + inline(i) + '</li>').join('') + `</${list.tag}>`); list = null; } };
  const flushFence = () => { out.push('<pre><code>' + fence.join('\n') + '</code></pre>'); fence = null; };
  for (const raw of escHtml(src || '').split('\n')) {
    const line = raw.trimEnd();
    let m;
    // A fenced block is kept as typed: it is usually a search string to copy.
    if (/^\s*```/.test(line)) {
      if (fence) flushFence(); else { flushPara(); flushList(); fence = []; }
      continue;
    }
    if (fence) { fence.push(raw); continue; }
    if (!line.trim()) { flushPara(); flushList(); continue; }
    if ((m = line.match(/^\s*(#{1,4})\s+(.*)$/))) {
      flushPara(); flushList();
      out.push(`<div class="md-h md-h${m[1].length}">` + inline(m[2]) + '</div>');
    } else if ((m = line.match(/^\s*[-*•]\s+(.*)$/)) || (m = line.match(/^\s*(\d+)[.)]\s+(.*)$/))) {
      flushPara();
      const tag = /^\s*\d/.test(line) ? 'ol' : 'ul';
      if (!list || list.tag !== tag) { flushList(); list = {tag, items: []}; }
      list.items.push(m[m.length - 1]);
    } else if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) {
      flushPara(); flushList(); out.push('<hr>');
    } else {
      flushList(); para.push(line.trim());
    }
  }
  flushPara(); flushList();
  if (fence) flushFence();          // an answer cut off inside a fence
  return out.join('');
}
// Keep the raw text beside the rendering, so streamed chunks append to it.
function setMd(el, text) { el._raw = text; el.innerHTML = renderMd(text); }

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

// ON A PHONE UNDER THE NATIVE CHROME (the iOS app), whatever a tab opens is
// a screen, and it comes and goes as the system's sheets do: up from the
// bottom on the system's curve, and down again. The desktop keeps its fade
// and settle. Transform only, and nothing scaled: a scale on a sheet of
// glass re-blurs the page behind on every frame, which is what he saw as
// rough and bumpy (19 Oct); the native bars fade over the same time
// (chrome.py).
const _sheetsSlide = () => document.documentElement.classList.contains('native-chrome') &&
                           window.matchMedia('(max-width: 700px)').matches;
// On an iPad under the native chrome the sheets and panels are centred by a
// transform (touch.css), which an animated transform would replace while it
// runs: they fade instead (the sweep, 20 Oct).
const _sheetsCentred = () => document.documentElement.classList.contains('native-chrome') &&
                             !window.matchMedia('(max-width: 700px)').matches;
const _SHEET_EASE = 'cubic-bezier(0.32, 0.72, 0, 1)';
// Out: shorter, and quickening as it leaves, as the system's sheets do. On
// the rising curve it crawled the last stretch, and the X and the bars
// waited for it (too slow, his phone, 21 Oct).
const _SHEET_OUT_EASE = 'cubic-bezier(0.4, 0, 1, 1)';
const _SHEET_IN = 480, _SHEET_OUT = 240;
// .sliding while a screen moves: its scroll-edge mask (touch.css) moves with
// it, and mid-slide that clear band showed the page's chips through the
// rising screen (21 Oct); it comes back once the screen has settled.
function _sliding(el, a) {
  el.classList.add('sliding');
  const done = () => el.classList.remove('sliding');
  a.addEventListener('finish', done);
  a.addEventListener('cancel', done);
  return a;
}
function _sheetIn(el) {
  el.classList.remove('closing');     // see _sheetOut
  if (_reduceMotion.matches || !el.animate) return null;
  if (_sheetsSlide()) return _sliding(el, el.animate([{transform: 'translateY(100%)'}, {transform: 'none'}],
                                                     {duration: _SHEET_IN, easing: _SHEET_EASE}));
  if (_sheetsCentred()) return el.animate([{opacity: 0}, {opacity: 1}], {duration: 220, easing: _EASE});
  return el.animate([{opacity: 0, transform: 'translateY(8px) scale(0.985)'},
                     {opacity: 1, transform: 'none'}], {duration: 220, easing: _EASE});
}
function _sheetOut(el) {
  if (_reduceMotion.matches || !el.animate) return null;
  const a = _sheetsSlide()
    ? _sliding(el, el.animate([{transform: 'none'}, {transform: 'translateY(100%)'}],
                              {duration: _SHEET_OUT, easing: _SHEET_OUT_EASE}))
    : _sheetsCentred() ? el.animate([{opacity: 1}, {opacity: 0}], {duration: 160, easing: _EASE})
    : el.animate([{opacity: 1, transform: 'none'},
                  {opacity: 0, transform: 'translateY(8px) scale(0.985)'}], {duration: 160, easing: _EASE});
  // .closing while it leaves: the iOS app's chrome counts it gone at once,
  // so the X and the bars change over WITH the sheet, not after it. It stays
  // once the sheet is gone, until _sheetIn opens it again: taken off as the
  // slide finished, it went a moment before the caller's onfinish closed the
  // sheet, the page reported the sheet open again for that moment, and the
  // bars came back, went and came back — the flinch on every close (his
  // phone, 21 Oct). A slide turned round (cancelled) takes it off.
  el.classList.add('closing');
  a.addEventListener('cancel', () => el.classList.remove('closing'));
  return a;
}

function openOverlay(id) {
  const ov = document.getElementById(id);
  if (!ov) return;
  if (ov.classList.contains('open') && !ov._closing) return;
  const panel = _panelOf(ov);
  if (ov._closing) {               // still sliding out: turn it round
    ov._closing = false;
    ov.getAnimations().forEach(a => a.cancel());
    if (panel) panel.getAnimations().forEach(a => a.cancel());
  }
  ov.classList.add('open');
  if (panel) panel.classList.remove('closing');
  if (_reduceMotion.matches || !panel || !panel.animate) return;
  ov.animate([{opacity: 0}, {opacity: 1}], {duration: _sheetsSlide() ? 250 : 180, easing: 'linear'});
  _sheetIn(panel);
}

function closeOverlay(id) {
  const ov = document.getElementById(id);
  if (!ov || !ov.classList.contains('open') || ov._closing) return;
  const panel = _panelOf(ov);
  if (_reduceMotion.matches || !panel || !panel.animate) { ov.classList.remove('open'); return; }
  ov._closing = true;
  ov.animate([{opacity: 1}, {opacity: 0}], {duration: _sheetsSlide() ? _SHEET_OUT : 160, easing: 'linear'});
  _sheetOut(panel).onfinish = () => {
    if (!ov._closing) return;      // opened again meanwhile
    ov._closing = false;
    ov.classList.remove('open');
  };
}

// ── Dock panels ────────────────────────────────────────────────────────────
// A panel opens from its trigger (top bar → drops down, dock → rises up),
// centred on it and scaled from it, so where it came from stays obvious.
// One panel at a time; a click elsewhere, Escape, or the trigger closes it.
function _openPanel() { return document.querySelector('.dock-panel:not([hidden])'); }

function togglePanel(id, trigger) {
  const panel = document.getElementById(id);
  const wasOpen = !panel.hidden && !panel._closing;
  closePanels(true);
  if (wasOpen) return;
  const fromTop = !!trigger.closest('.topbar');
  panel.classList.toggle('from-top', fromTop);
  panel.classList.toggle('from-bottom', !fromTop);
  panel.hidden = false;
  panel.classList.remove('closing');
  const r = trigger.getBoundingClientRect();
  const w = panel.offsetWidth;
  const left = Math.max(12, Math.min(window.innerWidth - w - 12, r.left + r.width / 2 - w / 2));
  panel.style.left = left + 'px';
  panel.style.transformOrigin = `${r.left + r.width / 2 - left}px ${fromTop ? '0%' : '100%'}`;
  panel._trigger = trigger;
  trigger.classList.add('on');
  trigger.setAttribute('aria-expanded', 'true');
  if (!_reduceMotion.matches && panel.animate) {
    if (_sheetsSlide() || _sheetsCentred()) _sheetIn(panel);
    else panel.animate([{opacity: 0, transform: 'scale(0.96)'}, {opacity: 1, transform: 'none'}],
                       {duration: 200, easing: _EASE});
  }
  if (id === 'panelAI') { loadUsage(); return; }   // nothing to type first: no focus
  const first = panel.querySelector('input, select, button, [tabindex]');
  if (first && fromTop === false) setTimeout(() => first.focus({preventScroll: true}), 30);
}

function closePanels(instant) {
  // A panel still fading out goes at once: one panel at a time.
  document.querySelectorAll('.dock-panel').forEach(p => {
    if (p._closing) { p.getAnimations().forEach(a => a.cancel()); p._closing = false; p.hidden = true; }
  });
  const panel = _openPanel();
  if (!panel) return;
  const t = panel._trigger;
  if (t) { t.classList.remove('on'); t.setAttribute('aria-expanded', 'false'); }
  if (instant || _reduceMotion.matches || !panel.animate) { panel.hidden = true; return; }
  const a = (_sheetsSlide() || _sheetsCentred()) ? _sheetOut(panel)
          : panel.animate([{opacity: 1, transform: 'none'}, {opacity: 0, transform: 'scale(0.96)'}],
                          {duration: 150, easing: _EASE});
  panel._closing = true;
  a.onfinish = () => { if (panel._closing) { panel._closing = false; panel.hidden = true; } };
}

// A click outside the open panel (and outside the bar that opened it) closes it.
document.addEventListener('mousedown', e => {
  const panel = _openPanel();
  if (!panel) return;
  if (panel.contains(e.target) || (panel._trigger && panel._trigger.contains(e.target))) return;
  closePanels();
});

// Closes the top-most open dialog or the PDF viewer (the last one in the page
// order), and only that one: an error raised over Settings closes, Settings
// stays. Says whether it closed anything. Escape uses it, and so does closing
// the window: the PDF viewer is a panel inside the MedSearch window, so the
// window's red button and ⌘W were hiding the whole app when the user meant to
// close the PDF (24 Sep). statusbar.py now asks this first.
function closeTopDialog() {
  const open = [...document.querySelectorAll('.modal-overlay.open, .pdf-overlay.open')];
  const top = open[open.length - 1];
  if (!top) return false;
  const closers = {failOverlay: closeFail, askOverlay: () => closeAsk(null), explainOverlay: closeExplain, citeOverlay: closeCitations,
                   settingsOverlay: closeSettings, exportOverlay: closeExport,
                   apiKeyPromptOverlay: closeApiKeyPrompt, proxyEditorOverlay: closeProxyEditor,
                   pdfOverlay: closePdf, updateOverlay: closeUpdate,
                   onboardOverlay: closeOnboarding};
  if (!closers[top.id]) return false;
  closers[top.id]();
  return true;
}

// Escape closes the top-most open dialog (see closeTopDialog). With no dialog
// open, it closes the open panel, or else the synthesis sheet.
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  const dialogOpen = !!document.querySelector('.modal-overlay.open, .pdf-overlay.open');
  if (_openPanel() && !dialogOpen) { e.preventDefault(); closePanels(); return; }
  if (closeTopDialog()) { e.preventDefault(); return; }
  if (!dialogOpen && synthesisOpen) { e.preventDefault(); closeSynthesis(); }
});

// ask({title, text, input, okLabel, danger}) → Promise. With `input` (the
// starting value) it resolves to the typed text, else to true; Cancel,
// Escape or a click outside resolve to null.
//
// IN THE iOS APP both are the system's own alert (his ask, 20 Oct: errors and
// warnings as Liquid Glass popups, not whole screens): the shell's bridge
// (ios/src/medsearch/shell.py) puts window.__msNative in the page, and these
// hand it the words. Everywhere else, and if the bridge cannot, the page's
// own dialogs below.
let _askResolve = null, _askReturnFocus = null;
function ask(o) {
  const native = globalThis.__msNative;
  if (native && native.ask) return native.ask(o);
  return _pageAsk(o);
}
function _pageAsk(o) {
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

// Settings ▸ Uninstall MedSearch: asks first, in the danger colour; then the
// app removes its login item, quits, and its files go to the Trash.
async function uninstallMedSearch() {
  const win = !!MS.onWindows;
  const yes = await ask({
    title: 'Uninstall MedSearch?',
    text: (win ? 'Its settings, recent and saved searches, exports and the web data of its windows go to ' +
                 'the Recycle Bin, the app is removed, and MedSearch quits. API keys and library sign-ins ' +
                 'stay in Credential Manager, for a later install.'
               : 'The app, its settings, recent and saved searches, exports and the web data of its windows ' +
                 'go to the Trash, and MedSearch quits. API keys and library sign-ins stay in the Keychain, ' +
                 'for a later install.'),
    okLabel: win ? 'Move to the Recycle Bin and quit' : 'Move to Trash and quit',
    danger: true});
  if (!yes) return;
  let res, data = {};
  try {
    res = await fetch('/uninstall', {method: 'POST'});
    data = await res.json().catch(() => ({}));
  } catch (e) {
    fail('MedSearch did not answer: ' + e.message, "Couldn't uninstall MedSearch");
    return;
  }
  if (!res.ok || !data.ok) {
    fail(data.message || `MedSearch answered ${res.status}.`, "Couldn't uninstall MedSearch");
    return;
  }
  showToast(win ? 'MedSearch is quitting; its files go to the Recycle Bin.'
                : 'MedSearch is quitting; its files go to the Trash.', '');
}

let _failReturnFocus = null;
function fail(message, title) {
  const native = globalThis.__msNative;
  if (native && native.alert && native.alert(title || "Couldn't do that", message || '')) return;
  _pageFail(message, title);
}
function _pageFail(message, title) {
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
  const native = globalThis.__msNative;
  if (native && native.toast && native.toast(msg, type)) return;
  _pageToast(msg, type);
}
function _pageToast(msg, type) {
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
  // The & first: the HTML parser decodes character references inside the
  // attribute before the script runs, so a title holding a literal "&#39;"
  // came out as a quote and ended the string (found in the sweep, 20 Oct).
  return String(s)
    .replace(/&/g, '&amp;')
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
