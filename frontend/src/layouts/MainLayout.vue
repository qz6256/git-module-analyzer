<template>
  <el-container class="app-shell">
    <el-aside :width="ui.sidebarCollapsed ? '64px' : '236px'" class="sidebar">
      <div class="brand" :class="{ 'is-collapsed': ui.sidebarCollapsed }">
        <div class="brand-mark"><el-icon><Connection /></el-icon></div>
        <div v-if="!ui.sidebarCollapsed" class="brand-txt">
          <h1>GIT KNOWLEDGE</h1>
          <p>AI 驱动的代码变更历史</p>
        </div>
      </div>

      <el-menu
        class="side-menu"
        :default-active="route.path"
        :collapse="ui.sidebarCollapsed"
        router
      >
        <el-menu-item-group title="工作区">
          <el-menu-item index="/projects">
            <el-icon><Grid /></el-icon><span>项目工作台</span>
          </el-menu-item>
          <el-menu-item index="/project-modules">
            <el-icon><Connection /></el-icon><span>项目模块总览</span>
          </el-menu-item>
          <el-menu-item index="/modules">
            <el-icon><Files /></el-icon><span>模块清单</span>
          </el-menu-item>
          <el-menu-item index="/files">
            <el-icon><Document /></el-icon><span>文件检索</span>
          </el-menu-item>
          <el-menu-item index="/commits">
            <el-icon><Clock /></el-icon><span>提交检索</span>
          </el-menu-item>
          <el-menu-item index="/issues">
            <el-icon><Tickets /></el-icon><span>需求与缺陷</span>
          </el-menu-item>
        </el-menu-item-group>
        <el-menu-item-group title="系统">
          <el-menu-item index="/settings">
            <el-icon><Setting /></el-icon><span>系统设置</span>
          </el-menu-item>
        </el-menu-item-group>
      </el-menu>

      <div v-if="!ui.sidebarCollapsed" class="sidebar-foot">
        <div class="status-line">
          <span class="mode-dot"></span>
          <span>知识库 · 运行中</span>
        </div>
        <div class="foot-note">v2 · swiss/minimal</div>
      </div>
    </el-aside>

    <el-container class="main-area">
      <el-header class="topbar">
        <div class="topbar-left">
          <button class="icon-btn" title="收起/展开侧栏" @click="ui.toggleSidebar()">
            <el-icon><Fold v-if="!ui.sidebarCollapsed" /><Expand v-else /></el-icon>
          </button>
          <div class="topbar-titles">
            <h2>{{ pageTitle }}</h2>
            <div class="sub">{{ projectStore.currentProject?.name || '未选择项目' }}</div>
          </div>
        </div>

        <div class="topbar-right">
          <el-select
            v-model="projectStore.currentProjectId"
            size="small"
            filterable
            placeholder="选择项目"
            class="context-select"
            @change="onProjectChange"
          >
            <el-option
              v-for="item in projectStore.projects"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
          <el-select
            v-model="projectStore.currentRepoId"
            size="small"
            filterable
            placeholder="选择仓库"
            class="context-select"
            :disabled="!projectStore.repositories.length"
            @change="onRepoChange"
          >
            <el-option
              v-for="repo in projectStore.repositories"
              :key="repo.id"
              :label="repo.display_name || repo.name"
              :value="repo.id"
            />
          </el-select>
          <el-tooltip :content="ui.isDark ? '切换到浅色' : '切换到深色'" placement="bottom">
            <button class="icon-btn" @click="ui.toggleTheme()">
              <el-icon><Sunny v-if="ui.isDark" /><Moon v-else /></el-icon>
            </button>
          </el-tooltip>
          <el-dropdown trigger="click" @command="onUserCommand">
            <span class="user-trigger">
              <span class="avatar">{{ auth.displayName.slice(0, 1).toUpperCase() }}</span>
              <span class="user-name">{{ auth.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="settings">
                  <el-icon><Setting /></el-icon>系统设置
                </el-dropdown-item>
                <el-dropdown-item command="logout" divided>
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'
import { useProjectStore } from '@/stores/project'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const ui = useUiStore()
const projectStore = useProjectStore()

const pageTitle = computed(() => (route.meta.title as string | undefined) || '工作台')

onMounted(() => {
  const queryRepo = Number(route.query.repo_id)
  projectStore.restore(queryRepo > 0 ? queryRepo : undefined)
})

async function onProjectChange(id: number) {
  await projectStore.selectProject(id)
}

function onRepoChange(id: number) {
  projectStore.selectRepo(id)
}

function onUserCommand(command: string) {
  if (command === 'settings') {
    router.push('/settings')
  } else if (command === 'logout') {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.sidebar {
  background: var(--color-background-subtle);
  border-right: 1px solid var(--color-border);
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.brand {
  box-sizing: border-box;
  height: var(--header-height);
  flex: 0 0 var(--header-height);
  padding: 0 22px;
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 11px;
}

.brand.is-collapsed {
  justify-content: center;
  padding: 0;
}

.brand-mark {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-line);
  color: var(--color-accent);
  font-size: 18px;
}

.brand-txt {
  min-width: 0;
}

.brand h1 {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.2px;
  white-space: nowrap;
}

.brand p {
  font-size: 10.5px;
  color: var(--color-muted-foreground);
  margin: 2px 0 0;
  letter-spacing: 0.2px;
  white-space: nowrap;
}

.side-menu {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  border: none;
}

.sidebar-foot {
  padding: 12px 14px;
  border-top: 1px solid var(--color-border);
  font-size: 11.5px;
  color: var(--color-muted-foreground);
}

.status-line {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--color-background-tertiary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 8px 10px;
}

.mode-dot {
  width: 8px;
  height: 8px;
  flex: 0 0 8px;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 0 3px var(--color-success-soft);
}

.foot-note {
  margin-top: 8px;
  opacity: 0.8;
  font-family: var(--font-mono);
  font-size: 10.5px;
}

.main-area {
  min-width: 0;
  background: var(--color-background);
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  box-sizing: border-box;
  height: var(--header-height);
  padding: 0 22px;
  background: var(--color-background);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.topbar-titles {
  min-width: 0;
}

.topbar h2 {
  font-family: var(--font-display);
  font-size: 16px;
  margin: 0;
  font-weight: 650;
  letter-spacing: -0.3px;
  white-space: nowrap;
}

.topbar .sub {
  color: var(--color-muted-foreground);
  font-size: 12px;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.context-select {
  width: 138px;
}

.icon-btn {
  width: 34px;
  height: 34px;
  padding: 0;
  display: grid;
  place-items: center;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-card);
  color: var(--color-muted-foreground);
  cursor: pointer;
  font-size: 16px;
  transition: color 180ms ease, border-color 180ms ease, background 180ms ease;
}

.icon-btn:hover {
  color: var(--color-accent);
  border-color: var(--color-accent-line);
}

.user-trigger {
  display: flex;
  align-items: center;
  gap: 7px;
  cursor: pointer;
  padding: 3px 6px;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
}

.user-trigger:hover {
  background: var(--color-highlight);
}

.avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--color-accent-soft);
  border: 1px solid var(--color-accent-line);
  color: var(--color-accent);
  font-weight: 700;
  font-family: var(--font-display);
}

.user-name {
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.content {
  padding: 20px 24px 56px;
  max-width: 1520px;
  width: 100%;
}

@media (max-width: 900px) {
  .user-name,
  .context-select {
    display: none;
  }
  .topbar {
    padding: 0 14px;
  }
  .content {
    padding: 16px 14px 40px;
  }
}
</style>
