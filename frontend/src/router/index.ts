import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useProjectStore } from '@/stores/project'
import MainLayout from '@/layouts/MainLayout.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'landing',
    component: () => import('@/views/Landing.vue'),
    meta: { public: true, title: '首页' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  // 后台布局：父路径仅作容器，子路由用绝对路径保持 /projects 等 URL 不变
  {
    path: '/app',
    component: MainLayout,
    children: [
      {
        path: '/projects',
        name: 'projects',
        component: () => import('@/views/Projects.vue'),
        meta: { title: '项目工作台' },
      },
      {
        path: '/projects/:id',
        name: 'project-detail',
        component: () => import('@/views/ProjectDetail.vue'),
        meta: { title: '项目详情' },
      },
      {
        path: '/modules',
        name: 'modules',
        component: () => import('@/views/Modules.vue'),
        meta: { title: '模块清单' },
      },
      {
        path: '/modules/:id',
        name: 'module-detail',
        component: () => import('@/views/ModuleDetail.vue'),
        meta: { title: '模块档案' },
      },
      {
        path: '/files',
        name: 'files',
        component: () => import('@/views/Files.vue'),
        meta: { title: '文件检索' },
      },
      {
        path: '/files/:id',
        name: 'file-detail',
        component: () => import('@/views/FileDetail.vue'),
        meta: { title: '文件档案' },
      },
      {
        path: '/commits',
        name: 'commits',
        component: () => import('@/views/Commits.vue'),
        meta: { title: '提交检索' },
      },
      {
        path: '/issues',
        name: 'issues',
        component: () => import('@/views/Issues.vue'),
        meta: { title: '需求与缺陷' },
      },
      {
        path: '/issues/:id',
        name: 'issue-detail',
        component: () => import('@/views/IssueDetail.vue'),
        meta: { title: '追溯详情' },
      },
      {
        path: '/users/:id/commits',
        name: 'user-commits',
        component: () => import('@/views/UserCommits.vue'),
        meta: { title: '用户提交' },
      },
      {
        path: '/settings',
        name: 'settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置' },
      },
      {
        path: '/403',
        name: 'forbidden',
        component: () => import('@/views/Forbidden.vue'),
        meta: { title: '无权限' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/NotFound.vue'),
    meta: { public: true, title: '页面不存在' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (to.meta.public) {
    // 已登录用户访问宣传页/登录页，直接进工作台
    if ((to.name === 'login' || to.name === 'landing') && auth.isAuthenticated) {
      return { path: '/projects' }
    }
    return true
  }

  if (!auth.isAuthenticated) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (!auth.currentUser) {
    await auth.fetchMe()
    if (!auth.isAuthenticated) {
      return { path: '/login', query: { redirect: to.fullPath } }
    }
  }

  // 支持从旧版链接带 repo_id 直达
  const queryRepo = Number(to.query.repo_id)
  if (queryRepo > 0) useProjectStore().selectRepo(queryRepo)

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return { path: '/403' }
  }

  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string | undefined) || 'Git 变更知识库'
  document.title = `${title} · Git 变更知识库`
})

export default router
