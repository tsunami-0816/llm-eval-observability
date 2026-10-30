import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: () => import('../views/Dashboard.vue') },
    { path: '/prompts', component: () => import('../views/Prompts.vue') },
    { path: '/datasets', component: () => import('../views/Datasets.vue') },
    { path: '/runs', component: () => import('../views/Runs.vue') },
    { path: '/runs/:id', component: () => import('../views/RunDetail.vue') },
  ],
})

export default router
