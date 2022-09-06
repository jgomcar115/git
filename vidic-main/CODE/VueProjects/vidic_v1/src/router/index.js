import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/login',
    name: 'login',
    component: () => import(/* webpackChunkName: "login" */ '../views/LoginView.vue')

  },
  {
    path: '/menu',
    name: 'menu',
    component: () => import(/* webpackChunkName: "menu" */ '../views/MenuView.vue')
  },
  {
    path: '/instalacion_1',
    name: 'instalacion_1',
    component: () => import(/* webpackChunkName: "instalacion_1" */ '../views/Instalacion_1.vue')

  },
  {
    path: '/Reymos',
    name: 'Reymos',
    component: () => import(/* webpackChunkName: "Reymos" */ '../views/Reymos.vue')
  }
]

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes
})

export default router
