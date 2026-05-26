export function getMarketSession() {
  const now = new Date()
  const options = { timeZone: 'Asia/Shanghai', hour12: false }
  const beijingStr = now.toLocaleString('en-US', options)
  const beijing = new Date(beijingStr)
  const day = beijing.getDay()
  const hours = beijing.getHours()
  const minutes = beijing.getMinutes()
  const totalMinutes = hours * 60 + minutes

  if (day === 0 || day === 6) {
    return { isTrading: false, session: 'weekend', note: '周末非交易日' }
  }

  if (totalMinutes >= 570 && totalMinutes < 690) {
    return { isTrading: true, session: 'morning', note: '上午盘交易中 (9:30-11:30)' }
  }

  if (totalMinutes >= 690 && totalMinutes < 780) {
    return { isTrading: false, session: 'lunch', note: '午间休市 (11:30-13:00)' }
  }

  if (totalMinutes >= 780 && totalMinutes < 900) {
    return { isTrading: true, session: 'afternoon', note: '下午盘交易中 (13:00-15:00)' }
  }

  return { isTrading: false, session: 'closed', note: '已收盘 (15:00-次日9:30)' }
}