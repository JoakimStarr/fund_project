<template>
  <PageContainer narrow>
    <div class="page-header mb-16">
      <h2 class="page-title">数据管理</h2>
    </div>

    <SectionCard class="mb-16">
      <div class="admin-header">
        <div>
          <div class="admin-header-title">数据总览</div>
          <div class="admin-header-meta">
            基金总数：{{ overallStats.fund_count ?? '--' }} |
            最新净值日：{{ overallStats.latest_nav_date || '--' }} |
            最新持仓季：{{ overallStats.latest_holding_quarter || '--' }}
          </div>
        </div>
        <el-button type="primary" :loading="updating" @click="triggerUpdate">触发更新</el-button>
      </div>
    </SectionCard>

    <SectionCard title="基金数据状态">
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
    </SectionCard>
  </PageContainer>
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

<style scoped lang="scss">
.page-header {
  animation: fadeInUp 0.5s var(--ease-out-expo);
}

.page-title {
  font-size: var(--font-size-2xl);
  font-weight: 700;
}

.admin-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-md);
}

.admin-header-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
}

.admin-header-meta {
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  margin-top: 4px;
}
</style>