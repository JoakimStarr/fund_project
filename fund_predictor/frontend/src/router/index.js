import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: () => import('@/views/Dashboard.vue'),
    meta: { title: '决策中心', icon: 'DataAnalysis' }
  },
  {
    path: '/predict',
    name: 'Predict',
    component: () => import('@/views/Predict.vue'),
    meta: { title: '智能预测', icon: 'TrendCharts' }
  },
  {
    path: '/train',
    name: 'Train',
    component: () => import('@/views/Train.vue'),
    meta: { title: '模型训练', icon: 'Setting' }
  },
  {
    path: '/backtest',
    name: 'Backtest',
    component: () => import('@/views/Backtest.vue'),
    meta: { title: '回测诊断', icon: 'DataLine' }
  },
  {
    path: '/model-monitor',
    name: 'ModelMonitor',
    component: () => import('@/views/ModelMonitor.vue'),
    meta: { title: '模型监控', icon: 'Monitor' }
  },
  {
    path: '/compare',
    name: 'Compare',
    component: () => import('@/views/Compare.vue'),
    meta: { title: '多基金对比', icon: 'DataLine' }
  },
  {
    path: '/profile/:code?',
    name: 'Profile',
    component: () => import('@/views/Profile.vue'),
    meta: { title: '基金画像', icon: 'UserFilled' },
    props: true
  },
  {
    path: '/intraday',
    name: 'Intraday',
    component: () => import('@/views/Intraday.vue'),
    meta: { title: 'T日盘中估算', icon: 'Timer' }
  },
  {
    path: '/admin/data-status',
    name: 'AdminDataStatus',
    component: () => import('@/views/AdminDataStatus.vue'),
    meta: { title: '数据管理', icon: 'SetUp' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// 路由守卫：设置页面标题
router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'QuantDesk'} - 基金预测系统`
  next()
})

export default router
