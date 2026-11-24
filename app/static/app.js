/* 主题切换：深色（默认 / Code dark + run green） ↔ 浅色（Neutral grey + link blue） */
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  const next = cur === 'light' ? 'dark' : 'light';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('gkb-theme', next); } catch (e) {}
  const btn = document.getElementById('theme-toggle');
  if (btn) btn.title = next === 'dark' ? '切换到浅色主题' : '切换到深色主题';
}

/* 共享前端交互：toast / API 请求 / 分析任务轮询 / 仓库切换 / 添加仓库 */
function $(s, root) { return (root || document).querySelector(s); }
function $$(s, root) { return Array.from((root || document).querySelectorAll(s)); }

function toast(msg, bad) {
  const t = $('#toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast show' + (bad ? ' bad' : '');
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => { t.className = 'toast'; }, 4200);
}

async function api(url, opts) {
  const o = opts || {};
  const res = await fetch(url, {
    method: o.method || 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: o.body ? JSON.stringify(o.body) : undefined
  });
  let data;
  try { data = await res.json(); } catch (e) { data = {}; }
  if (!res.ok) throw new Error(data.detail || ('请求失败 ' + res.status));
  return data;
}

function switchRepo(sel) {
  const id = sel.value;
  const u = new URL(location.href);
  u.searchParams.set('repo_id', id);
  u.searchParams.delete('page');
  location.href = u.toString();
}

function openModal(id) { const m = document.getElementById(id); if (m) m.classList.add('show'); }
function closeModal(id) { const m = document.getElementById(id); if (m) m.classList.remove('show'); }

async function addRepo(ev) {
  ev.preventDefault();
  const source = $('#in-source').value.trim();
  const type = $('#in-type').value;
  const name = $('#in-name').value.trim();
  const branch = $('#in-branch').value.trim() || 'main';
  const branches = $('#in-branches').value.trim();
  const btn = $('#btn-add-save');
  btn.disabled = true; btn.textContent = '正在添加…';
  try {
    const data = await api('/api/repos', {
      method: 'POST',
      body: {
        source: source, source_type: type, name: name, default_branch: branch,
        branches: branches ? branches.split(/[,，\s]+/).filter(Boolean) : [branch]
      }
    });
    closeModal('modal-add');
    toast('仓库已添加：' + data.name);
    setTimeout(() => location.reload(), 700);
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false; btn.textContent = '添加仓库';
  }
}

function setBusy(on, label) {
  $$('[data-action]').forEach(b => { if (on) b.disabled = true; else b.disabled = false; });
  const ov = $('#loading-overlay');
  if (ov) { ov.style.display = on ? 'flex' : 'none'; ov.setAttribute('aria-hidden', on ? 'false' : 'true'); }
  const txt = $('#loading-text');
  if (txt && label) txt.textContent = label;
}

function pollJob(jobId, onDone) {
  const wrap = $('#progress-wrap');
  const bar = $('#progress-bar');
  const msg = $('#progress-msg');
  const logs = $('#progress-logs');
  if (wrap) wrap.classList.add('show');
  const tick = async () => {
    try {
      const j = await api('/api/jobs/' + jobId);
      if (bar) bar.style.width = (j.progress || 0) + '%';
      if (msg) msg.textContent = j.message;
      if (logs && j.logs) logs.innerHTML = j.logs.slice(-8).map(x =>
        '<div>' + x.replace(/</g, '&lt;') + '</div>').join('');
      if (j.status === 'running') {
        setTimeout(tick, 900);
      } else {
        setBusy(false);
        if (j.status === 'error') toast('任务失败：' + j.message, true);
        else toast(j.message || '任务完成');
        if (onDone) onDone(j);
        else setTimeout(() => location.reload(), 1100);
      }
    } catch (e) {
      setBusy(false);
      toast('查询任务状态失败：' + e.message, true);
    }
  };
  tick();
}

async function runAction(kind, repoId, body) {
  if (!repoId) { toast('请先添加并选择一个仓库', true); return; }
  setBusy(true, kind === 'initialize' ? '正在初始化扫描，首次分析可能需要几分钟…' : '正在同步新提交…');
  try {
    const url = '/api/repos/' + repoId + '/' + (kind === 'initialize' ? 'initialize' : 'sync');
    const data = await api(url, { method: 'POST', body: body || {} });
    pollJob(data.job_id);
  } catch (e) {
    setBusy(false);
    toast(e.message, true);
  }
}

async function deleteRepo(id, name) {
  if (!confirm('确定删除仓库「' + name + '」及其全部分析数据？\n（仅删除本工具数据库中的记录，不会删除你的源码仓库）')) return;
  try {
    await api('/api/repos/' + id, { method: 'DELETE' });
    toast('已删除');
    setTimeout(() => location.href = '/', 700);
  } catch (e) { toast(e.message, true); }
}

async function copyText(text, btn) {
  try {
    await navigator.clipboard.writeText(text);
    const old = btn.textContent; btn.textContent = '已复制';
    setTimeout(() => btn.textContent = old, 1500);
  } catch (e) { toast('复制失败：' + e.message, true); }
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = $('#theme-toggle');
  if (btn) btn.title = document.documentElement.getAttribute('data-theme') === 'light'
    ? '切换到深色主题' : '切换到浅色主题';
  const form = $('#form-add'); if (form) form.addEventListener('submit', addRepo);
  $$('.modal-mask').forEach(m => m.addEventListener('click', e => {
    if (e.target === m) m.classList.remove('show');
  }));
});
