import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    component: () => import('@/components/layout/AppLayout.vue'),
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '决策中心', icon: 'DataAnalysis' }
      },
      {
        path: 'intraday',
        name: 'Intraday',
        component: () => import('@/views/Intraday.vue'),
        meta: { title: 'T日盘中估算', icon: 'Timer' }
      },
      {
        path: 'train',
        name: 'Train',
        component: () => import('@/views/Train.vue'),
        meta: { title: '模型训练', icon: 'Setting' }
      },
      {
        path: 'backtest',
        name: 'Backtest',
        component: () => import('@/views/Backtest.vue'),
        meta: { title: '回测诊断', icon: 'DataLine' }
      },

      {
        path: 'profile/:code?',
        name: 'Profile',
        component: () => import('@/views/Profile.vue'),
        meta: { title: '基金画像', icon: 'UserFilled' }
      },
      {
        path: 'monitor',
        name: 'Monitor',
        component: () => import('@/views/ModelMonitor.vue'),
        meta: { title: '模型监控', icon: 'Monitor' }
      },
      {
        path: 'admin/data',
        name: 'AdminData',
        component: () => import('@/views/AdminDataStatus.vue'),
        meta: { title: '数据管理', icon: 'SetUp', isAdmin: true }
      }
    ]
  }
]

export default createRouter({ history: createWebHistory(), routes })