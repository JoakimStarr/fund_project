<template>
  <div class="chart-container" v-loading="loading" :style="{ height: height }">
    <v-chart
      ref="chartRef"
      :option="chartOption"
      :autoresize="true"
      :theme="theme"
      class="echarts-chart"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import {
  LineChart,
  BarChart,
  PieChart,
  ScatterChart,
  RadarChart
} from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  VisualMapComponent,
  MarkLineComponent,
  MarkPointComponent
} from 'echarts/components'

// 注册 ECharts 组件
use([
  CanvasRenderer,
  LineChart,
  BarChart,
  PieChart,
  ScatterChart,
  RadarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  VisualMapComponent,
  MarkLineComponent,
  MarkPointComponent
])

const props = defineProps({
  option: {
    type: Object,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  },
  height: {
    type: String,
    default: '400px'
  },
  theme: {
    type: String,
    default: 'dark'
  }
})

const chartRef = ref(null)
const chartOption = computed(() => props.option)

// 监听主题变化，更新图表主题
watch(() => document.documentElement.getAttribute('data-theme'), (theme) => {
  if (chartRef.value) {
    // ECharts 会自动响应主题变化
  }
})

onMounted(() => {
  // 图表已挂载
})

onUnmounted(() => {
  // 清理资源
})
</script>

<style lang="scss" scoped>
.chart-container {
  width: 100%;
  position: relative;

  .echarts-chart {
    width: 100%;
    height: 100%;
  }
}
</style>
