<template>
  <el-aside :width="appStore.sidebarCollapsed ? '64px' : '220px'" style="transition:width 0.3s;background:#304156;overflow:hidden">
    <el-menu
      :default-active="$route.path"
      router
      :collapse="appStore.sidebarCollapsed"
      background-color="#304156"
      text-color="#bfcbd9"
      active-text-color="#409EFF"
      style="height:100vh;border-right:none"
    >
      <div style="display:flex;align-items:center;justify-content:center;padding:16px;gap:8px;border-bottom:1px solid rgba(255,255,255,0.1);font-size:16px;font-weight:600;color:#fff;white-space:nowrap;overflow:hidden">
        <el-icon :size="22" color="#409EFF"><DataAnalysis /></el-icon>
        <span v-show="!appStore.sidebarCollapsed">基金预测系统</span>
      </div>
      <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <template #title>{{ item.title }}</template>
      </el-menu-item>
    </el-menu>
  </el-aside>
</template>

<script setup>
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const menuItems = [
  { path: '/', title: '决策中心', icon: 'DataAnalysis' },
  { path: '/predict', title: '智能预测', icon: 'TrendCharts' },
  { path: '/intraday', title: 'T日盘中估算', icon: 'Timer' },
  { path: '/train', title: '模型训练', icon: 'Setting' },
  { path: '/backtest', title: '回测诊断', icon: 'DataLine' },
  { path: '/compare', title: '多基金对比', icon: 'Grid' },
  { path: '/profile', title: '基金画像', icon: 'UserFilled' },
  { path: '/monitor', title: '模型监控', icon: 'Monitor' },
  { path: '/admin/data', title: '数据管理', icon: 'SetUp' },
]
</script>