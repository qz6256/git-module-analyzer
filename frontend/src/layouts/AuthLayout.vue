<template>
  <div class="auth-shell">
    <section class="auth-hero">
      <div class="brand">
        <div class="brand-mark"><el-icon><Connection /></el-icon></div>
        <div>
          <h1>GIT KNOWLEDGE</h1>
          <p>AI 驱动的代码变更历史知识库</p>
        </div>
      </div>

      <div class="hero-copy">
        <h2>让每一次代码变更<br />都有迹可循</h2>
        <p>从需求单据到提交，从代码块到模块档案，构建可追溯、可持续维护的工程知识图谱。</p>
        <ul>
          <li><span class="tick">✓</span> 归纳而非罗列：模块与文件的当前态持续维护</li>
          <li><span class="tick">✓</span> 证据充分性评估：不臆测、不输出运行时判断</li>
          <li><span class="tick">✓</span> 高信号过滤：只保留值得被记录的变化</li>
        </ul>
      </div>

      <div class="auth-foot">Minimalism &amp; Swiss · 内部开发者工具</div>
    </section>

    <section class="auth-panel">
      <div class="auth-card">
        <slot />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts"></script>

<style scoped>
.auth-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(380px, 0.9fr);
}

.auth-hero {
  background: var(--color-background-subtle);
  border-right: 1px solid var(--color-border);
  padding: 32px 40px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  overflow: hidden;
}

.auth-hero::after {
  content: '';
  position: absolute;
  right: -160px;
  bottom: -200px;
  width: 460px;
  height: 460px;
  border-radius: 50%;
  border: 1px solid var(--color-accent-line);
  background: radial-gradient(circle, var(--color-accent-soft), transparent 70%);
  pointer-events: none;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
  z-index: 1;
}

.brand-mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-line);
  color: var(--color-accent);
  font-size: 20px;
}

.brand h1 {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: -0.2px;
  margin: 0;
}

.brand p {
  font-size: 11px;
  color: var(--color-muted-foreground);
  margin: 2px 0 0;
}

.hero-copy {
  position: relative;
  z-index: 1;
  max-width: 520px;
}

.hero-copy h2 {
  font-family: var(--font-display);
  font-size: clamp(28px, 3.4vw, 44px);
  line-height: 1.25;
  letter-spacing: -1.6px;
  margin: 0 0 18px;
}

.hero-copy > p {
  color: var(--color-muted-foreground);
  font-size: 14px;
  line-height: 1.8;
  margin: 0 0 22px;
}

.hero-copy ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
}

.hero-copy li {
  font-size: 13px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
  color: var(--color-foreground);
}

.tick {
  color: var(--color-accent);
  font-weight: 700;
}

.auth-foot {
  position: relative;
  z-index: 1;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-muted-foreground);
}

.auth-panel {
  display: grid;
  place-items: center;
  padding: 32px;
  background: var(--color-background);
}

.auth-card {
  width: 100%;
  max-width: 380px;
}

@media (max-width: 900px) {
  .auth-shell {
    grid-template-columns: 1fr;
  }
  .auth-hero {
    display: none;
  }
  .auth-panel {
    min-height: 100vh;
  }
}
</style>
