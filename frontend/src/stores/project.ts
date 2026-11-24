import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { projectsApi, type ProjectQuery } from '@/api/modules/projects'
import type { Project, Repository } from '@/types'

const PROJECT_KEY = 'gma_project_id'
const REPO_KEY = 'gma_repo_id'

function readId(key: string): number {
  const value = Number(localStorage.getItem(key))
  return Number.isFinite(value) && value > 0 ? value : 0
}

export const useProjectStore = defineStore('project', () => {
  const projects = ref<Project[]>([])
  const repositories = ref<Repository[]>([])
  const currentProjectId = ref<number>(0)
  const currentRepoId = ref<number>(0)
  const loading = ref(false)
  const initialized = ref(false)

  const currentProject = computed(
    () => projects.value.find((item) => item.id === currentProjectId.value) || null,
  )
  const currentRepo = computed(
    () => repositories.value.find((item) => item.id === currentRepoId.value) || null,
  )

  async function fetchProjects(params?: ProjectQuery) {
    loading.value = true
    try {
      projects.value = await projectsApi.getProjects(params)
      return projects.value
    } finally {
      loading.value = false
    }
  }

  async function loadRepositories(projectId?: number) {
    const id = projectId || currentProjectId.value
    if (!id) {
      repositories.value = []
      currentRepoId.value = 0
      return []
    }
    repositories.value = await projectsApi.getRepositories(id)
    if (!repositories.value.some((repo) => repo.id === currentRepoId.value)) {
      currentRepoId.value = repositories.value[0]?.id ?? 0
    }
    return repositories.value
  }

  async function selectProject(id: number) {
    currentProjectId.value = id
    localStorage.setItem(PROJECT_KEY, String(id))
    currentRepoId.value = readId(REPO_KEY)
    await loadRepositories(id)
    localStorage.setItem(REPO_KEY, String(currentRepoId.value))
  }

  function selectRepo(id: number) {
    currentRepoId.value = id
    localStorage.setItem(REPO_KEY, String(id))
  }

  /** 恢复上次选择；视图通过 repo_id 查询参数传入时优先使用 */
  async function restore(queryRepoId?: number) {
    if (initialized.value) return
    initialized.value = true
    try {
      await fetchProjects()
      const storedProjectId = readId(PROJECT_KEY)
      if (storedProjectId && projects.value.some((item) => item.id === storedProjectId)) {
        await selectProject(storedProjectId)
      } else if (projects.value.length) {
        await selectProject(projects.value[0].id)
      }
      if (queryRepoId && repositories.value.some((repo) => repo.id === queryRepoId)) {
        selectRepo(queryRepoId)
      }
    } catch {
      initialized.value = false
    }
  }

  return {
    projects,
    repositories,
    currentProjectId,
    currentRepoId,
    currentProject,
    currentRepo,
    loading,
    initialized,
    fetchProjects,
    loadRepositories,
    selectProject,
    selectRepo,
    restore,
  }
})
