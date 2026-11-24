<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function goConsole() {
  router.push(auth.isAuthenticated ? '/projects' : '/login')
}
function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const typed = ref('')
const typingWords = ['可追溯的答案', '团队知识资产', '每一次变更的来龙去脉']
let typeTimer: number | undefined
let wordIdx = 0
let charIdx = 0
let deleting = false
function typeTick() {
  const word = typingWords[wordIdx]
  if (!deleting) {
    charIdx++
    typed.value = word.slice(0, charIdx)
    if (charIdx >= word.length) {
      deleting = true
      typeTimer = window.setTimeout(typeTick, 1600)
      return
    }
  } else {
    charIdx--
    typed.value = word.slice(0, charIdx)
    if (charIdx <= 0) {
      deleting = false
      wordIdx = (wordIdx + 1) % typingWords.length
    }
  }
  typeTimer = window.setTimeout(typeTick, deleting ? 45 : 110)
}

const canvasRef = ref<HTMLCanvasElement | null>(null)
let raf = 0
let particles: { x: number; y: number; vx: number; vy: number; r: number }[] = []
function initParticles() {
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const resize = () => {
    const dpr = window.devicePixelRatio || 1
    canvas.width = canvas.clientWidth * dpr
    canvas.height = canvas.clientHeight * dpr
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }
  resize()
  window.addEventListener('resize', resize)
  const count = 64
  const W = () => canvas.clientWidth
  const H = () => canvas.clientHeight
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * W(), y: Math.random() * H(),
    vx: (Math.random() - 0.5) * 0.35, vy: (Math.random() - 0.5) * 0.35,
    r: Math.random() * 1.6 + 0.6,
  }))
  const draw = () => {
    const w = W(), h = H()
    ctx.clearRect(0, 0, w, h)
    for (const p of particles) {
      p.x += p.vx; p.y += p.vy
      if (p.x < 0 || p.x > w) p.vx *= -1
      if (p.y < 0 || p.y > h) p.vy *= -1
      ctx.beginPath()
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2)
      ctx.fillStyle = 'rgba(34,197,94,0.65)'
      ctx.fill()
    }
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const a = particles[i], b = particles[j]
        const dx = a.x - b.x, dy = a.y - b.y
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d < 120) {
          ctx.beginPath()
          ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y)
          ctx.strokeStyle = `rgba(34,197,94,${(1 - d / 120) * 0.16})`
          ctx.lineWidth = 0.7
          ctx.stroke()
        }
      }
    }
    raf = requestAnimationFrame(draw)
  }
  draw()
}

const capabilities = [
  { icon: '\u25C6', title: '三视角追溯', desc: '文件、功能模块、需求缺陷，一处看全变更来龙去脉。', tag: 'TRACE' },
  { icon: '\u25C7', title: '多数据库自由切换', desc: 'SQLite / PG / MySQL / Oracle / MSSQL，一行配置切换。', tag: 'DATA' },
  { icon: '\u25CB', title: '工程项目多仓库', desc: '前端、后端、App 合成一个项目视图，按项目区分管理。', tag: 'PROJECT' },
  { icon: '\u25A3', title: '企业级权限', desc: 'JWT 登录，四角色 RBAC，项目级细粒度授权。', tag: 'AUTH' },
]

const stats = [
  { value: '28', label: '文件档案' },
  { value: '05', label: '功能模块' },
  { value: '15', label: '分析提交' },
  { value: '08', label: '追溯关联' },
]

const chain = [
  { step: '01', title: '需求单据', sub: '为什么改' },
  { step: '02', title: 'Git 提交', sub: '谁在何时改' },
  { step: '03', title: '代码块 / 档案', sub: '改了什么' },
]

onMounted(() => {
  typeTimer = window.setTimeout(typeTick, 500)
  initParticles()
})
onUnmounted(() => {
  if (typeTimer) clearTimeout(typeTimer)
  cancelAnimationFrame(raf)
  window.removeEventListener('resize', () => {})
})
</script>

<template>
  <div class="landing">
    <canvas ref="canvasRef" class="particles"></canvas>
    <div class="grid-bg"></div>
    <div class="glow glow-a"></div>
    <div class="glow glow-b"></div>

    <header class="nav">
      <div class="nav-inner">
        <div class="brand" @click="scrollTo('top')">
          <span class="brand-mark">C</span>
          <span class="brand-name">CodeAtlas</span>
          <span class="brand-sub">/ 变更知识库</span>
        </div>
        <nav class="nav-links">
          <span @click="scrollTo('capabilities')">产品能力</span>
          <span @click="scrollTo('chain')">追溯链</span>
          <span class="nav-cta" @click="goConsole">进入控制台 →</span>
        </nav>
      </div>
    </header>

    <main>
      <section id="top" class="hero">
        <div class="hero-copy">
          <div class="eyebrow">// CODE CHANGE KNOWLEDGE BASE</div>
          <h1 class="hero-title" data-text="让代码变更可追溯">让每一次代码变更<br>都有<span class="accent">可追溯的答案</span></h1>
          <div class="type-line">
            <span class="type-label">把「为什么改成现在这样」沉淀为</span>
            <span class="typed">{{ typed }}<i class="caret"></i></span>
          </div>
          <p class="hero-desc">需求 → 提交 → 代码块 / 文件 / 模块档案。<br>不再是散落的 git log，而是团队可检索、可追溯的知识资产。</p>
          <div class="hero-actions">
            <button class="btn btn-primary" @click="goConsole">进入控制台 <span>→</span></button>
            <button class="btn btn-ghost" @click="scrollTo('capabilities')">了解能力</button>
          </div>
          <div class="hero-stats">
            <div v-for="s in stats" :key="s.label" class="stat">
              <div class="stat-value">{{ s.value }}</div>
              <div class="stat-label">{{ s.label }}</div>
            </div>
          </div>
        </div>

        <div class="hero-visual">
          <div class="terminal">
            <div class="terminal-bar">
              <span class="dot dot-r"></span><span class="dot dot-y"></span><span class="dot dot-g"></span>
              <span class="terminal-title">trace · demand #101</span>
            </div>
            <div class="terminal-body">
              <div class="t-line"><span class="t-prompt">$</span> trace --issue #101</div>
              <div class="t-line t-hit">✓ 提交 a2f642e <span class="t-tag">fix #101</span></div>
              <div class="t-line">├─ 文件档案 <span class="t-num">28</span></div>
              <div class="t-line">├─ 功能模块 <span class="t-num">05</span></div>
              <div class="t-line">└─ 证据信号 <span class="t-num t-ok">4 / 4</span></div>
              <div class="t-line t-flow">需求 <b>→</b> 提交 <b>→</b> 代码块</div>
            </div>
          </div>
          <div class="visual-badge">TRACEABILITY ENGINE</div>
        </div>
      </section>

      <section id="capabilities" class="section">
        <div class="section-head">
          <div class="eyebrow">// CAPABILITIES</div>
          <h2>为工程团队设计的能力矩阵</h2>
        </div>
        <div class="cap-grid">
          <article v-for="c in capabilities" :key="c.tag" class="cap-card">
            <div class="cap-top"><span class="cap-icon">{{ c.icon }}</span><span class="cap-tag">{{ c.tag }}</span></div>
            <h3>{{ c.title }}</h3>
            <p>{{ c.desc }}</p>
            <div class="cap-line"></div>
          </article>
        </div>
      </section>

      <section id="chain" class="section chain-section">
        <div class="section-head">
          <div class="eyebrow">// TRACEABILITY CHAIN</div>
          <h2>一条完整的追溯链</h2>
          <p class="section-desc">卖的不是变更历史，而是「为什么是现在这个样子」的答案。</p>
        </div>
        <div class="chain-flow">
          <template v-for="(c, i) in chain" :key="c.step">
            <div class="chain-node">
              <div class="chain-step">{{ c.step }}</div>
              <div class="chain-title">{{ c.title }}</div>
              <div class="chain-sub">{{ c.sub }}</div>
            </div>
            <div v-if="i < chain.length - 1" class="chain-arrow"><span></span></div>
          </template>
        </div>
      </section>

      <section class="cta-section">
        <div class="cta-inner">
          <div class="eyebrow">// GET STARTED</div>
          <h2>准备好把代码历史变成知识资产了吗？</h2>
          <p>登录控制台，接入你的第一个工程项目与代码仓库。</p>
          <button class="btn btn-primary btn-lg" @click="goConsole">登录 / 进入控制台 <span>→</span></button>
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="brand"><span class="brand-mark">C</span><span class="brand-name">CodeAtlas</span></div>
      <span>AI 驱动的代码变更历史知识库</span>
      <span class="footer-copy">© 2026 CodeAtlas</span>
    </footer>
  </div>
</template>

<style scoped>
.landing {
  --g: #22c55e;
  --bg: #0b1120;
  --panel: #111c30;
  --line: rgba(34,197,94,0.22);
  --ink: #f8fafc;
  --muted: #93a4bd;
  position: relative;
  min-height: 100vh;
  background: var(--bg);
  color: var(--ink);
  overflow: hidden;
  font-family: 'IBM Plex Sans', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}
.particles { position: absolute; inset: 0; width: 100%; height: 100%; z-index: 0; }
.grid-bg {
  position: absolute; inset: 0; z-index: 0; pointer-events: none;
  background-image: linear-gradient(rgba(34,197,94,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34,197,94,0.05) 1px, transparent 1px);
  background-size: 46px 46px;
  mask-image: linear-gradient(to bottom, #000 0%, transparent 78%);
  -webkit-mask-image: linear-gradient(to bottom, #000 0%, transparent 78%);
}
.glow { position: absolute; border-radius: 50%; filter: blur(90px); z-index: 0; pointer-events: none; }
.glow-a { width: 460px; height: 460px; top: -160px; right: -80px; background: rgba(34,197,94,0.14); animation: float 9s ease-in-out infinite; }
.glow-b { width: 380px; height: 380px; top: 420px; left: -160px; background: rgba(56,189,248,0.10); animation: float 11s ease-in-out infinite reverse; }
@keyframes float { 0%,100% { transform: translate(0,0); } 50% { transform: translate(30px,40px); } }

.nav { position: relative; z-index: 3; border-bottom: 1px solid var(--line); }
.nav-inner { max-width: 1200px; margin: 0 auto; padding: 16px 28px; display: flex; align-items: center; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.brand-mark { width: 30px; height: 30px; border-radius: 7px; background: var(--g); color: #06120a; display: grid; place-items: center; font-weight: 700; font-family: 'JetBrains Mono', monospace; box-shadow: 0 0 18px rgba(34,197,94,0.5); }
.brand-name { font-weight: 700; font-size: 18px; letter-spacing: 0.3px; }
.brand-sub { color: var(--muted); font-size: 12px; font-family: 'JetBrains Mono', monospace; }
.nav-links { display: flex; align-items: center; gap: 26px; font-size: 13px; color: var(--muted); }
.nav-links span { cursor: pointer; transition: color 0.2s; }
.nav-links span:hover { color: var(--ink); }
.nav-cta { color: var(--g) !important; border: 1px solid var(--g); padding: 7px 14px; border-radius: 7px; font-family: 'JetBrains Mono', monospace; }
.nav-cta:hover { background: rgba(34,197,94,0.12); }

main { position: relative; z-index: 2; }
.hero { max-width: 1200px; margin: 0 auto; padding: 84px 28px 96px; display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 56px; align-items: center; }
.eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--g); letter-spacing: 1.5px; margin-bottom: 18px; }
.hero-title { font-size: 46px; line-height: 1.28; font-weight: 700; margin: 0 0 20px; letter-spacing: -0.5px; position: relative; }
.accent { color: var(--g); text-shadow: 0 0 26px rgba(34,197,94,0.45); }
.hero-title::after {
  content: attr(data-text); position: absolute; left: 0; top: 0; width: 100%; color: transparent;
  pointer-events: none; text-shadow: 2px 0 rgba(56,189,248,0.35), -2px 0 rgba(244,63,94,0.35);
  clip-path: inset(0 0 100% 0); animation: glitch 5s steps(1) infinite;
}
@keyframes glitch {
  0%, 92%, 100% { clip-path: inset(0 0 100% 0); transform: translate(0); }
  93% { clip-path: inset(12% 0 62% 0); transform: translate(-2px,1px); }
  95% { clip-path: inset(58% 0 22% 0); transform: translate(2px,-1px); }
  97% { clip-path: inset(30% 0 48% 0); transform: translate(-1px,0); }
}
.type-line { font-family: 'JetBrains Mono', monospace; margin-bottom: 18px; min-height: 24px; }
.type-label { color: var(--muted); font-size: 13px; }
.typed { color: var(--g); font-size: 14px; }
.caret { display: inline-block; width: 8px; height: 15px; background: var(--g); margin-left: 2px; vertical-align: -2px; animation: blink 0.9s steps(1) infinite; }
@keyframes blink { 50% { opacity: 0; } }
.hero-desc { color: var(--muted); font-size: 15px; line-height: 1.9; margin: 0 0 28px; }
.hero-actions { display: flex; gap: 14px; }
.btn { border: none; cursor: pointer; font-family: 'JetBrains Mono', monospace; font-size: 13px; padding: 12px 22px; border-radius: 8px; transition: all 0.2s; }
.btn span { margin-left: 6px; }
.btn-primary { background: var(--g); color: #06120a; font-weight: 700; box-shadow: 0 0 24px rgba(34,197,94,0.35); }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 6px 30px rgba(34,197,94,0.55); }
.btn-ghost { background: transparent; color: var(--muted); border: 1px solid rgba(148,163,184,0.35); }
.btn-ghost:hover { color: var(--ink); border-color: var(--ink); }
.hero-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 44px; max-width: 480px; }
.stat-value { font-family: 'JetBrains Mono', monospace; font-size: 26px; font-weight: 700; color: var(--g); }
.stat-label { font-size: 11px; color: var(--muted); margin-top: 4px; letter-spacing: 1px; }

.hero-visual { position: relative; }
.terminal { background: linear-gradient(160deg, #101d33, #0c1626); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; box-shadow: 0 24px 70px rgba(0,0,0,0.55), 0 0 0 1px rgba(34,197,94,0.05) inset; }
.terminal-bar { display: flex; align-items: center; gap: 7px; padding: 12px 16px; border-bottom: 1px solid rgba(148,163,184,0.12); }
.dot { width: 9px; height: 9px; border-radius: 50%; }
.dot-r { background: #f87171; } .dot-y { background: #fbbf24; } .dot-g { background: #4ade80; }
.terminal-title { margin-left: 8px; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: var(--muted); }
.terminal-body { padding: 20px; font-family: 'JetBrains Mono', monospace; font-size: 12.5px; line-height: 2; }
.t-line { color: #c7d3e6; }
.t-prompt { color: var(--g); margin-right: 6px; }
.t-hit { color: var(--g); }
.t-tag { color: #06120a; background: var(--g); padding: 1px 7px; border-radius: 4px; font-size: 10px; margin-left: 6px; }
.t-num { color: #fbbf24; }
.t-ok { color: var(--g); }
.t-flow { margin-top: 12px; padding-top: 12px; border-top: 1px dashed rgba(148,163,184,0.2); color: var(--muted); }
.t-flow b { color: var(--g); animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 50% { opacity: 0.35; } }
.visual-badge { position: absolute; bottom: -16px; right: 18px; font-family: 'JetBrains Mono', monospace; font-size: 10px; letter-spacing: 2px; color: var(--g); background: var(--bg); border: 1px solid var(--line); padding: 5px 12px; border-radius: 6px; }

.section { max-width: 1200px; margin: 0 auto; padding: 64px 28px; }
.section-head { margin-bottom: 36px; }
.section-head h2 { font-size: 30px; font-weight: 700; margin: 0; }
.section-desc { color: var(--muted); font-size: 14px; margin-top: 12px; }
.cap-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.cap-card { position: relative; background: rgba(17,28,48,0.75); border: 1px solid var(--line); border-radius: 12px; padding: 22px; transition: all 0.25s; overflow: hidden; }
.cap-card:hover { transform: translateY(-5px); border-color: rgba(34,197,94,0.55); box-shadow: 0 14px 40px rgba(34,197,94,0.12); }
.cap-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.cap-icon { font-size: 22px; color: var(--g); }
.cap-tag { font-family: 'JetBrains Mono', monospace; font-size: 10px; color: var(--muted); letter-spacing: 1px; }
.cap-card h3 { font-size: 16px; margin: 0 0 10px; font-weight: 600; }
.cap-card p { font-size: 12.5px; color: var(--muted); line-height: 1.8; margin: 0; }
.cap-line { position: absolute; left: 0; bottom: 0; height: 2px; width: 0; background: var(--g); transition: width 0.3s; }
.cap-card:hover .cap-line { width: 100%; }

.chain-section { padding-top: 20px; }
.chain-flow { display: flex; align-items: stretch; gap: 0; margin-top: 12px; }
.chain-node { flex: 1; background: rgba(17,28,48,0.75); border: 1px solid var(--line); border-radius: 12px; padding: 26px 20px; text-align: center; }
.chain-step { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--g); margin-bottom: 10px; }
.chain-title { font-size: 17px; font-weight: 600; margin-bottom: 6px; }
.chain-sub { font-size: 12px; color: var(--muted); }
.chain-arrow { width: 70px; display: flex; align-items: center; justify-content: center; position: relative; }
.chain-arrow::before { content: ''; position: absolute; left: 0; right: 0; height: 1px; background: var(--line); }
.chain-arrow span { position: relative; width: 8px; height: 8px; border-top: 2px solid var(--g); border-right: 2px solid var(--g); transform: rotate(45deg); animation: arrowMove 1.8s ease-in-out infinite; }
@keyframes arrowMove { 0%,100% { transform: rotate(45deg) translateX(-4px); opacity: 0.5; } 50% { transform: rotate(45deg) translateX(4px); opacity: 1; } }

.cta-section { position: relative; z-index: 2; padding: 20px 28px 90px; max-width: 1200px; margin: 0 auto; }
.cta-inner { border: 1px solid var(--line); border-radius: 16px; padding: 54px 28px; text-align: center; background: radial-gradient(circle at 50% 0%, rgba(34,197,94,0.12), transparent 65%), rgba(17,28,48,0.7); }
.cta-inner h2 { font-size: 28px; font-weight: 700; margin: 0 0 12px; }
.cta-inner p { color: var(--muted); font-size: 14px; margin: 0 0 26px; }
.btn-lg { font-size: 14px; padding: 14px 30px; }

.footer { position: relative; z-index: 2; border-top: 1px solid var(--line); padding: 26px 28px; display: flex; align-items: center; gap: 20px; max-width: 1200px; margin: 0 auto; color: var(--muted); font-size: 12px; }
.footer-copy { margin-left: auto; font-family: 'JetBrains Mono', monospace; }

@media (max-width: 900px) {
  .hero { grid-template-columns: 1fr; padding-top: 54px; }
  .hero-title { font-size: 34px; }
  .cap-grid { grid-template-columns: repeat(2, 1fr); }
  .chain-flow { flex-direction: column; gap: 12px; }
  .chain-arrow { width: 100%; height: 34px; }
  .chain-arrow::before { top: 50%; left: 50%; width: 1px; height: 100%; }
  .nav-links span:not(.nav-cta) { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .glow, .caret, .hero-title::after, .t-flow b, .chain-arrow span { animation: none !important; }
}
</style>
