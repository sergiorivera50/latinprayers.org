/* Prayer Studio — local-only editor for data/prayers.csv.
 *
 * Vanilla, no build step, no dependencies, in keeping with the rest of the repo
 * (though nothing here ever ships: this file is not copied into dist/).
 *
 * The client never holds authority over the CSV. It sends one row and an
 * operation; the server re-reads the file, applies that single change, and
 * writes it back. So a stale tab cannot clobber the other prayers. */

'use strict';

const COLUMNS = ['slug', 'title', 'subtitle', 'category', 'order', 'description',
                 'la', 'en', 'context', 'source', 'source_url'];

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
};

let state = { rows: [], checks: [], categories: [], fields: COLUMNS };
let sort = { key: 'category', dir: 'asc' };
let editing = null;      // { slug, isNew, original } while the editor is open
let pending = null;      // the { op, slug, row } awaiting confirmation in the dialog

/* ------------------------------------------------------------------- api -- */
async function api(path, body) {
  const res = await fetch('/_studio/api/' + path, body === undefined ? {} : {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({ error: res.statusText }));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

let toastTimer = 0;
function toast(message, kind) {
  const node = $('toast');
  node.textContent = message;
  node.className = 'toast ' + (kind || 'busy');
  node.hidden = false;
  clearTimeout(toastTimer);
  if (kind !== 'busy') toastTimer = setTimeout(() => { node.hidden = true; }, 6000);
}

/* --------------------------------------------------------------- helpers -- */
/* Mirrors build.py's _split_stanzas: trim, split on blank lines, drop empties.
   Used only for the live line counts; the server's warnings are authoritative. */
function splitStanzas(text) {
  const trimmed = (text || '').replace(/\r\n/g, '\n').trim();
  if (!trimmed) return [];
  return trimmed.split(/\n\s*\n/)
    .filter((s) => s.trim())
    .map((s) => s.split('\n').map((l) => l.trim()).filter(Boolean));
}

const blankRow = () => Object.fromEntries(COLUMNS.map((c) => [c, '']));
const rowBySlug = (slug) => state.rows.find((r) => (r.slug || '').trim() === slug);
const checkFor = (slug) => state.checks[state.rows.indexOf(rowBySlug(slug))] || { errors: [], warnings: [] };

/* ------------------------------------------------------------- list view -- */
function statusRank(check) {
  if (check.errors.length) return 0;
  if (check.warnings.length) return 1;
  return 2;
}

function visibleRows() {
  const query = $('search').value.trim().toLowerCase();
  const category = $('filter-category').value;
  const status = $('filter-status').value;

  const paired = state.rows.map((row, i) => ({ row, check: state.checks[i] || { errors: [], warnings: [] } }));

  const filtered = paired.filter(({ row, check }) => {
    if (category && (row.category || '').trim() !== category) return false;
    if (status === 'errors' && !check.errors.length) return false;
    if (status === 'warnings' && !check.warnings.length) return false;
    if (!query) return true;
    return ['slug', 'title', 'subtitle', 'category', 'source']
      .some((c) => (row[c] || '').toLowerCase().includes(query));
  });

  const dir = sort.dir === 'asc' ? 1 : -1;
  filtered.sort((a, b) => {
    if (sort.key === 'status') return dir * (statusRank(a.check) - statusRank(b.check));
    if (sort.key === 'order') {
      const na = parseInt(a.row.order, 10), nb = parseInt(b.row.order, 10);
      return dir * ((isNaN(na) ? 1000 : na) - (isNaN(nb) ? 1000 : nb));
    }
    return dir * String(a.row[sort.key] || '').localeCompare(String(b.row[sort.key] || ''));
  });
  return filtered;
}

function renderList() {
  const body = $('rows');
  body.textContent = '';
  const rows = visibleRows();

  for (const { row, check } of rows) {
    const tr = el('tr');
    tr.tabIndex = 0;
    const slug = (row.slug || '').trim();

    const cells = [
      ['cell-slug', slug],
      ['cell-title', row.title || ''],
      ['cell-muted', row.subtitle || ''],
      ['', row.category || ''],
    ];
    for (const [cls, text] of cells) tr.appendChild(el('td', cls, text));
    tr.appendChild(el('td', 'num', row.order || '—'));
    tr.appendChild(el('td', 'cell-muted', row.source_url ? (row.source || hostOf(row.source_url)) : '—'));

    const status = el('td');
    status.appendChild(pillFor(check));
    tr.appendChild(status);

    const open = () => openEditor(slug);
    tr.addEventListener('click', open);
    tr.addEventListener('keydown', (e) => { if (e.key === 'Enter') open(); });
    body.appendChild(tr);
  }

  $('empty').hidden = rows.length > 0;
  const errs = state.checks.filter((c) => c.errors.length).length;
  const warns = state.checks.filter((c) => c.warnings.length).length;
  $('count').textContent = `${rows.length} of ${state.rows.length} prayers` +
    (errs ? ` · ${errs} with errors` : '') + (warns ? ` · ${warns} with warnings` : '');

  document.querySelectorAll('.grid th.sortable').forEach((th) => {
    if (th.dataset.sort === sort.key) th.dataset.dir = sort.dir;
    else delete th.dataset.dir;
  });
}

function pillFor(check) {
  if (check.errors.length) return el('span', 'pill pill-bad', `${check.errors.length} error${check.errors.length > 1 ? 's' : ''}`);
  if (check.warnings.length) return el('span', 'pill pill-warn', `${check.warnings.length} warning${check.warnings.length > 1 ? 's' : ''}`);
  return el('span', 'pill pill-ok', 'OK');
}

function hostOf(url) {
  try { return new URL(url).host; } catch (_) { return url; }
}

/* ----------------------------------------------------------- editor view -- */
const FIELD_HINTS = {
  slug: 'Becomes the URL /prayers/<slug>/. Kebab-case.',
  title: 'The Latin title, used as the page heading.',
  subtitle: 'The common English name.',
  category: 'Groups the prayer on /prayers/. Blurbs come from data/categories.csv.',
  order: 'Sort key within the category; lower comes first. Blank means 1000.',
  description: 'One or two sentences, shown on the index and as the meta description.',
  context: '“About this prayer”. Blank line starts a new paragraph.',
  source: 'Link text override. Blank shows the URL’s route instead.',
  source_url: 'Where the translation came from. Blank means no source line at all.',
};

function editorMarkup() {
  return `
  <div class="edit-head">
    <button type="button" class="btn" id="back">&larr; All prayers</button>
    <div>
      <h2 class="edit-title" id="edit-title"></h2>
      <div class="edit-sub" id="edit-sub"></div>
    </div>
    <span class="spacer"></span>
    <button type="button" class="btn" id="view-page">View page</button>
    <button type="button" class="btn btn-danger" id="delete">Delete</button>
    <button type="button" class="btn btn-primary" id="save">Review &amp; save</button>
  </div>

  <div class="edit-body">
    <section class="card">
      <h3>Identity</h3>
      <div class="card-body">
        <div class="fields">
          ${textField('slug', 'Slug', true)}
          ${textField('title', 'Latin title', true)}
          ${textField('subtitle', 'English name', true)}
          <div class="field" data-field="category">
            <label class="req" for="f-category">Category</label>
            <input id="f-category" list="categories" autocomplete="off">
            <datalist id="categories"></datalist>
            <span class="hint">${FIELD_HINTS.category}</span>
          </div>
          <div class="field" data-field="order">
            <label for="f-order">Order</label>
            <input id="f-order" inputmode="numeric" autocomplete="off">
            <span class="hint">${FIELD_HINTS.order}</span>
          </div>
        </div>
        <div class="fields" style="margin-top:14px">
          <div class="field wide" data-field="description">
            <label for="f-description">Description</label>
            <textarea id="f-description" rows="2"></textarea>
            <span class="hint">${FIELD_HINTS.description}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <h3>Text — Latin and English, line for line</h3>
      <div class="card-body">
        <div class="parallel">
          <div class="field" data-field="la">
            <label class="req" for="f-la">Latin (la)</label>
            <textarea id="f-la" spellcheck="false"></textarea>
            <span class="lines" id="lines-la"></span>
          </div>
          <div class="field" data-field="en">
            <label class="req" for="f-en">English (en)</label>
            <textarea id="f-en" spellcheck="false"></textarea>
            <span class="lines" id="lines-en"></span>
          </div>
        </div>
        <p class="hint" style="margin:10px 0 0">
          One line per line. A blank line starts a new stanza; keep the same
          stanza breaks in both columns. Lines beginning “V.&nbsp;” or “R.&nbsp;”
          are rubricated automatically.
        </p>
      </div>
    </section>

    <section class="card">
      <h3>About this prayer</h3>
      <div class="card-body">
        <div class="field" data-field="context">
          <label for="f-context">Context</label>
          <textarea id="f-context" rows="12"></textarea>
          <span class="hint">${FIELD_HINTS.context}</span>
        </div>
      </div>
    </section>

    <section class="card">
      <h3>Translation source</h3>
      <div class="card-body">
        <div class="fields">
          <div class="field" data-field="source_url">
            <label for="f-source_url">Source URL</label>
            <input id="f-source_url" type="url" autocomplete="off" placeholder="https://fisheaters.com/prayers.html">
            <span class="hint">${FIELD_HINTS.source_url}</span>
          </div>
          <div class="field" data-field="source">
            <label for="f-source">Source label</label>
            <input id="f-source" autocomplete="off">
            <span class="hint">${FIELD_HINTS.source}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="card">
      <h3>Checks</h3>
      <div class="card-body"><ul class="checks" id="checks"></ul></div>
    </section>
  </div>`;
}

function textField(name, label, required) {
  return `<div class="field" data-field="${name}">
    <label class="${required ? 'req' : ''}" for="f-${name}">${label}</label>
    <input id="f-${name}" autocomplete="off">
    <span class="hint">${FIELD_HINTS[name] || ''}</span>
  </div>`;
}

function openEditor(slug) {
  const isNew = slug === null;
  const row = isNew ? blankRow() : { ...rowBySlug(slug) };
  editing = { slug, isNew, original: { ...row } };

  const view = $('view-edit');
  view.innerHTML = editorMarkup();
  $('view-list').hidden = true;
  view.hidden = false;
  view.scrollTop = 0;

  const list = $('categories');
  for (const c of state.categories) list.appendChild(Object.assign(document.createElement('option'), { value: c }));

  for (const name of COLUMNS) {
    const input = $('f-' + name);
    if (input) input.value = row[name] || '';
  }

  $('edit-title').textContent = isNew ? 'New prayer' : (row.title || slug);
  $('edit-sub').textContent = isNew ? 'not yet in the CSV' : `/prayers/${slug}/`;
  $('view-page').hidden = isNew;
  $('delete').hidden = isNew;

  view.querySelectorAll('input, textarea').forEach((input) => {
    input.addEventListener('input', onEdit);
  });
  syncScroll($('f-la'), $('f-en'));

  if (!isNew) setHash(slug);
  $('back').addEventListener('click', closeEditor);
  $('save').addEventListener('click', review);
  $('delete').addEventListener('click', confirmDelete);
  $('view-page').addEventListener('click', () => window.open('/prayers/' + slug + '/', '_blank', 'noopener'));

  onEdit();
  $('f-' + (isNew ? 'slug' : 'title')).focus();
}

/* The open prayer lives in the URL hash, so a reload keeps your place and the
   badge on a prayer page (/_studio/#pater-noster) lands in the right editor. */
function setHash(slug) {
  const want = slug ? '#' + slug : ' ';
  if (location.hash !== (slug ? '#' + slug : '')) {
    history.replaceState(null, '', slug ? want : location.pathname);
  }
}

function closeEditor() {
  if (isDirty() && !confirm('Discard unsaved changes to this prayer?')) return;
  setHash(null);
  editing = null;
  $('view-edit').hidden = true;
  $('view-edit').textContent = '';
  $('view-list').hidden = false;
  renderList();
}

function collectRow() {
  const row = blankRow();
  for (const name of COLUMNS) {
    const input = $('f-' + name);
    if (input) row[name] = input.value;
  }
  return row;
}

function isDirty() {
  if (!editing) return false;
  const row = collectRow();
  return COLUMNS.some((c) => (row[c] || '').trim() !== (editing.original[c] || '').trim());
}

/* Live feedback while typing: stanza and line counts, plus the client-side half
   of the checks. The server re-runs all of it on save and has the final word. */
function onEdit() {
  const row = collectRow();
  const la = splitStanzas(row.la);
  const en = splitStanzas(row.en);

  const describe = (stanzas) => {
    const lines = stanzas.reduce((n, s) => n + s.length, 0);
    return `${stanzas.length} stanza${stanzas.length === 1 ? '' : 's'} · ${lines} line${lines === 1 ? '' : 's'}`;
  };
  const mismatch = la.length !== en.length ||
    la.some((s, i) => en[i] && s.length !== en[i].length);
  for (const [id, stanzas] of [['lines-la', la], ['lines-en', en]]) {
    const node = $(id);
    node.textContent = describe(stanzas);
    node.classList.toggle('mismatch', mismatch && stanzas.length > 0);
  }

  $('edit-title').textContent = editing.isNew
    ? (row.title || 'New prayer')
    : (row.title || editing.slug);
  $('edit-sub').textContent = (editing.isNew ? 'new · ' : '') +
    (row.slug ? `/prayers/${row.slug.trim()}/` : 'no slug yet') +
    (isDirty() ? ' · unsaved changes' : '');

  renderChecks(localChecks(row, la, en));
}

/* A subset of studio.py's check_row, run locally so the panel updates as you
   type. Anything needing the whole CSV (duplicate slugs, order collisions) is
   left to the server and appears when you press Review. */
function localChecks(row, la, en) {
  const errors = [];
  const warnings = [];
  const t = (c) => (row[c] || '').trim();

  for (const c of ['slug', 'title', 'subtitle', 'category', 'la', 'en']) {
    if (!t(c)) errors.push(`“${c}” is required and is empty.`);
  }
  if (t('slug') && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(t('slug'))) {
    errors.push('“slug” must be kebab-case — it becomes the URL /prayers/<slug>/.');
  }
  if (t('order') && !/^-?\d+$/.test(t('order'))) {
    errors.push(`“order” must be a whole number, got “${t('order')}”.`);
  }
  if (la.length && en.length) {
    if (la.length !== en.length) {
      warnings.push(`Latin has ${la.length} stanza(s), English has ${en.length}.`);
    } else {
      la.forEach((s, i) => {
        if (s.length !== en[i].length) {
          warnings.push(`stanza ${i + 1}: ${s.length} Latin line(s) against ${en[i].length} English.`);
        }
      });
    }
  }
  for (const c of ['title', 'subtitle', 'description', 'context', 'source']) {
    if ((row[c] || '').includes('—')) warnings.push(`“${c}” contains an em-dash; house style bans it.`);
  }
  if (t('category') && state.categories.length && !state.categories.includes(t('category'))) {
    warnings.push(`“${t('category')}” is a new category; add a blurb to data/categories.csv.`);
  }
  if (!t('description')) warnings.push('no description — the index entry will have no summary line.');
  if (!t('context')) warnings.push('no context — the page will have no “About this prayer”.');
  if (t('source') && !t('source_url')) warnings.push('“source” is set but “source_url” is empty, so no link is shown.');
  if (t('source_url') && !/^https?:\/\//.test(t('source_url'))) warnings.push('“source_url” does not start with http:// or https://.');

  return { errors, warnings };
}

function renderChecks(check) {
  const list = $('checks');
  list.textContent = '';
  const dirty = new Set();
  for (const message of check.errors) {
    list.appendChild(el('li', 'err', message));
    const match = message.match(/[“"]([a-z_]+)[”"]/);
    if (match) dirty.add(match[1]);
  }
  for (const message of check.warnings) list.appendChild(el('li', 'warn', message));
  if (!check.errors.length && !check.warnings.length) {
    list.appendChild(el('li', 'good', 'No errors and no warnings.'));
  }
  document.querySelectorAll('.field[data-field]').forEach((field) => {
    field.classList.toggle('invalid', dirty.has(field.dataset.field));
  });
  $('save').disabled = check.errors.length > 0;
}

function syncScroll(a, b) {
  let lock = false;
  const link = (from, to) => from.addEventListener('scroll', () => {
    if (lock) return;
    lock = true;
    to.scrollTop = from.scrollTop;
    requestAnimationFrame(() => { lock = false; });
  });
  link(a, b);
  link(b, a);
}

/* ------------------------------------------------------------ save / diff -- */
async function review() {
  const row = collectRow();
  const op = editing.isNew ? 'create' : 'update';
  await showDiff({ op, slug: editing.slug || row.slug, row },
                 editing.isNew ? 'Add prayer' : 'Save to CSV');
}

async function confirmDelete() {
  await showDiff({ op: 'delete', slug: editing.slug, row: null }, 'Delete prayer');
}

async function showDiff(request, confirmLabel) {
  toast('Preparing diff…', 'busy');
  let preview;
  try {
    preview = await api('diff', request);
  } catch (err) {
    return toast(err.message, 'bad');
  }
  $('toast').hidden = true;

  pending = request;
  const body = $('dialog-body');
  body.textContent = '';

  if (preview.errors.length) {
    body.appendChild(el('h4', null, 'Errors — these block the save'));
    const list = el('ul', 'checks');
    for (const m of preview.errors) list.appendChild(el('li', 'err', m));
    body.appendChild(list);
  }
  if (preview.warnings.length) {
    body.appendChild(el('h4', null, 'Warnings — you can save anyway'));
    const list = el('ul', 'checks');
    for (const m of preview.warnings) list.appendChild(el('li', 'warn', m));
    body.appendChild(list);
  }

  body.appendChild(el('h4', null, changeHeading(preview)));
  body.appendChild(renderFields(preview.fields, request.op));

  // The literal bytes, kept and kept honest, but folded away: this is the thing
  // that will actually be written, and the field view above is a reading of it.
  const raw = el('details', 'raw');
  raw.appendChild(el('summary', null, 'Raw diff of data/prayers.csv'));
  raw.appendChild(renderDiff(preview.diff));
  body.appendChild(raw);

  const { before, after } = preview.rowCount;
  $('dialog-title').textContent = request.op === 'delete' ? 'Delete prayer' : 'Review changes';
  $('dialog-note').textContent = before === after
    ? `${after} prayers, unchanged count`
    : `${before} prayers → ${after}`;
  const confirm = $('dialog-confirm');
  confirm.textContent = confirmLabel;
  confirm.disabled = preview.errors.length > 0 || !preview.diff;
  confirm.className = 'btn ' + (request.op === 'delete' ? 'btn-danger' : 'btn-primary');
  $('overlay').hidden = false;
  confirm.focus();
}

const FIELD_LABELS = {
  slug: 'Slug', title: 'Latin title', subtitle: 'English name',
  category: 'Category', order: 'Order', description: 'Description',
  la: 'Latin text', en: 'English text', context: 'Context',
  source: 'Source label', source_url: 'Source URL',
};

function changeHeading(preview) {
  const n = preview.fields.length;
  if (preview.op === 'create') return 'New prayer';
  if (preview.op === 'delete') return 'Removing this prayer';
  if (!n) return 'No field changed';
  return `${n} field${n === 1 ? '' : 's'} changed`;
}

/* One block per changed column. Short fields get a before/after pair with the
   changed words picked out; multi-line fields get a line diff of the cell. */
function renderFields(fields, op) {
  const wrap = el('div', 'fields-diff');
  if (!fields || !fields.length) {
    wrap.appendChild(el('p', 'none', 'Nothing in this row differs from what is already in the CSV.'));
    return wrap;
  }

  for (const field of fields) {
    const block = el('div', 'fdiff');
    const head = el('div', 'fdiff-head');
    head.appendChild(el('span', 'fdiff-name', FIELD_LABELS[field.name] || field.name));
    head.appendChild(el('code', 'fdiff-key', field.name));
    if (field.wasEmpty && !field.isEmpty) head.appendChild(el('span', 'pill pill-ok', 'filled in'));
    else if (field.isEmpty && !field.wasEmpty) head.appendChild(el('span', 'pill pill-warn', 'cleared'));
    block.appendChild(head);

    const body = el('div', 'fdiff-body' + (field.kind === 'block' ? ' mono' : ''));
    if (field.kind === 'inline') {
      if (!field.added) body.appendChild(sideLine('del', field.beforeParts));
      if (!field.removed) body.appendChild(sideLine('add', field.afterParts));
    } else {
      for (const line of field.lines) {
        if (line.type === 'gap') {
          body.appendChild(el('div', 'dline gap',
            `${line.count} unchanged line${line.count === 1 ? '' : 's'}`));
        } else if (line.type === 'pair') {
          body.appendChild(sideLine('del', line.beforeParts));
          body.appendChild(sideLine('add', line.afterParts));
        } else {
          const row = el('div', 'dline ' + line.type);
          row.appendChild(el('span', 'gutter', line.type === 'add' ? '+' : line.type === 'del' ? '\u2212' : ' '));
          row.appendChild(el('span', 'dtext', line.text || '\u00a0'));
          body.appendChild(row);
        }
      }
    }
    block.appendChild(body);
    wrap.appendChild(block);
  }
  return wrap;
}

/* One side of a change, with the differing words highlighted inside it. */
function sideLine(side, parts) {
  const row = el('div', 'dline ' + side);
  row.appendChild(el('span', 'gutter', side === 'add' ? '+' : '\u2212'));
  const text = el('span', 'dtext');
  if (!parts || !parts.length) {
    text.appendChild(el('span', 'blank', '(empty)'));
  } else {
    for (const [kind, chunk] of parts) {
      text.appendChild(kind === 'equal' ? document.createTextNode(chunk) : el('span', 'mark-' + kind, chunk));
    }
  }
  row.appendChild(text);
  return row;
}

function renderDiff(text) {
  const pre = el('pre', 'diff');
  if (!text) {
    pre.appendChild(el('div', 'none', 'No change — the CSV would be written exactly as it stands.'));
    return pre;
  }
  for (const line of text.split('\n')) {
    if (line === '' ) continue;
    let cls = '';
    if (line.startsWith('+++') || line.startsWith('---')) cls = 'hunk';
    else if (line.startsWith('@@')) cls = 'hunk';
    else if (line.startsWith('+')) cls = 'add';
    else if (line.startsWith('-')) cls = 'del';
    pre.appendChild(el('div', cls, line));
  }
  return pre;
}

function closeDialog() {
  $('overlay').hidden = true;
  pending = null;
}

async function commit() {
  if (!pending) return;
  const request = pending;
  $('dialog-confirm').disabled = true;
  toast('Saving…', 'busy');
  let result;
  try {
    result = await api('save', request);
  } catch (err) {
    closeDialog();
    return toast(err.message, 'bad');
  }
  closeDialog();

  state = result.state;
  populateFilters();

  if (!result.saved) {
    toast('Nothing changed; nothing written.', 'ok');
  } else if (result.build.ok) {
    toast(`Saved. ${result.build.message}`, 'ok');
  } else {
    toast(`Saved to CSV, but the build failed: ${result.build.message}`, 'bad');
  }

  if (request.op === 'delete') {
    setHash(null);
    editing = null;
    $('view-edit').hidden = true;
    $('view-edit').textContent = '';
    $('view-list').hidden = false;
    renderList();
  } else {
    openEditor((request.row.slug || '').trim());
  }
}

/* ------------------------------------------------------------------ boot -- */
function populateFilters() {
  const select = $('filter-category');
  const current = select.value;
  select.textContent = '';
  select.appendChild(Object.assign(document.createElement('option'), { value: '', textContent: 'All categories' }));
  for (const c of state.categories) {
    select.appendChild(Object.assign(document.createElement('option'), { value: c, textContent: c }));
  }
  select.value = state.categories.includes(current) ? current : '';
}

async function load() {
  toast('Loading…', 'busy');
  try {
    state = await api('state');
  } catch (err) {
    return toast(err.message, 'bad');
  }
  $('data-file').textContent = state.dataFile;
  populateFilters();
  renderList();
  $('toast').hidden = true;

  const wanted = decodeURIComponent(location.hash.slice(1));
  if (wanted && rowBySlug(wanted)) openEditor(wanted);
  else if (wanted) toast(`No prayer with the slug “${wanted}”.`, 'bad');
}

function wire() {
  $('search').addEventListener('input', renderList);
  $('filter-category').addEventListener('change', renderList);
  $('filter-status').addEventListener('change', renderList);
  $('new-prayer').addEventListener('click', () => openEditor(null));

  document.querySelectorAll('.grid th.sortable').forEach((th) => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      sort = { key, dir: sort.key === key && sort.dir === 'asc' ? 'desc' : 'asc' };
      renderList();
    });
  });

  $('rebuild').addEventListener('click', async () => {
    toast('Rebuilding…', 'busy');
    try {
      const result = await api('rebuild', {});
      toast(result.message, result.ok ? 'ok' : 'bad');
    } catch (err) {
      toast(err.message, 'bad');
    }
  });

  $('dialog-cancel').addEventListener('click', closeDialog);
  $('dialog-close').addEventListener('click', closeDialog);
  $('dialog-confirm').addEventListener('click', commit);
  $('overlay').addEventListener('click', (e) => { if (e.target === $('overlay')) closeDialog(); });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (!$('overlay').hidden) closeDialog();
      else if (editing) closeEditor();
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 's') {
      e.preventDefault();
      if (editing && !$('save').disabled && $('overlay').hidden) review();
    }
  });

  window.addEventListener('beforeunload', (e) => {
    if (isDirty()) { e.preventDefault(); e.returnValue = ''; }
  });
}

wire();
load();
