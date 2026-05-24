import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/global.scss'

const app = createApp(App)

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { size: 'default', zIndex: 3000 })

// 移除加载动画
app.mount('#app')
setTimeout(() => {
  const loading = document.getElementById('app-loading')
  if (loading) {
    loading.style.opacity = '0'
    loading.style.transition = 'opacity 0.3s ease'
    setTimeout(() => loading.remove(), 300)
  }
}, 100)

console.log('%c🎯 QuantDesk', 'font-size: 24px; font-weight: bold; color: #3b82f6;')
console.log('%c基金T+1净值预测系统 v1.0.0', 'font-size: 14px; color: #94a3b8;')
