<template>
  <div style="max-width:1000px;margin:0 auto">
    <h2>数据管理</h2>

    <el-card shadow="never" style="margin-bottom:16px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <div style="font-size:14px;font-weight:600">数据总览</div>
          <div style="font-size:13px;color:#909399;margin-top:4px">
            基金总数：{{ overallStats.fund_count ?? '--' }} |
            最新净值日：{{ overallStats.latest_nav_date || '--' }} |
            最新持仓季：{{ overallStats.latest_holding_quarter || '--' }}
          </div>
        </div>
        <el-button type="primary" :loading="updating" @click="triggerUpdate">触发更新</el-button>
      </div>
    </el-card>

    <el-card shadow="never">
      <template #header><span style="font-weight:600">基金数据状态</span></template>
      <el-table :data="statusList" size="small" stripe empty-text="暂无数据" max-height="600">
        <el-table-column prop="fund_code" label="基金代码" width="110" align="center" />
        <el-table-column prop="fund_name" label="基金名称" min-width="140" />
        <el-table-column prop="latest_nav_date" label="最新净值日期" width="130" align="center" />
        <el-table-column prop="latest_holding_quarter" label="最新持仓季度" width="130" align="center" />
        <el-table-column prop="model_age" label="模型年龄(天)" width="120" align="center" />
        <el-table-column label="净值状态" width="100" align="center">
          <template #default="{row}">
            <el-tag :type="row.nav_status === 'ok' ? 'success' : 'warning'" size="small">
              {{ row.nav_status === 'ok' ? '正常' : '滞后' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="持仓状态" width="100" align="center">
          <template #default="{row}">
            <el-tag :type="row.holding_status === 'ok' ? 'success' : 'warning'" size="small">
              {{ row.holding_status === 'ok' ? '正常' : '滞后' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDataStatus, updateData } from '@/api/admin'
import { ElMessage } from 'element-plus'

const statusList = ref([])
const overallStats = ref({})
const updating = ref(false)

async function loadData() {
  try {
    const data = await getDataStatus()
    if (data) {
      statusList.value = data.fund_status || []
      overallStats.value = data.overall || {}
    }
  } catch {}
}

async function triggerUpdate() {
  updating.value = true
  try {
    await updateData({})
    ElMessage.success('数据更新任务已启动')
    setTimeout(loadData, 3000)
  } catch {
    ElMessage.error('更新失败')
  } finally {
    updating.value = false
  }
}

onMounted(loadData)
</script>