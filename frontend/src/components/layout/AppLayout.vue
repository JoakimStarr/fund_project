<template>
  <el-container style="height: 100vh">
    <Sidebar />
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:space-between;background:#fff;border-bottom:1px solid #eee;padding:0 20px;height:60px">
        <div style="display:flex;align-items:center;gap:12px">
          <el-icon :size="20" style="cursor:pointer" @click="appStore.toggleSidebar"><Fold /></el-icon>
          <el-breadcrumb>
            <el-breadcrumb-item to="/">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="$route.meta.title">{{ $route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <el-tag
            :type="marketTagType"
            size="small"
            effect="dark"
          >
            {{ appStore.marketSession.note }}
          </el-tag>
        </div>
      </el-header>
      <el-main style="background:#f5f7fa;padding:20px;overflow-y:auto">
        <router-view />
      </el-main>
      <el-footer style="display:flex;align-items:center;justify-content:center;height:40px;background:#fff;border-top:1px solid #eee;font-size:12px;color:#909399">
        基金净值预测系统 · 仅供研究参考，不构成投资建议
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import Sidebar from './Sidebar.vue'

const appStore = useAppStore()

const marketTagType = computed(() => {
  const session = appStore.marketSession.session
  if (session === 'morning' || session === 'afternoon') return 'success'
  if (session === 'lunch') return 'warning'
  return 'info'
})

let timer
onMounted(() => {
  appStore.updateMarketSession()
  appStore.fetchAiProviderStatus()
  timer = setInterval(() => {
    appStore.updateMarketSession()
  }, 60000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>