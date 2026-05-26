export function isValidFundCode(code) {
  return /^\d{6}$/.test(String(code).trim())
}

export function normalizeFundCode(input) {
  let code = String(input).trim().replace(/\s+/g, '')
  code = code.replace(/\.(OF|SH|SZ)$/i, '').replace(/^(sh|sz)/i, '')
  if (/^\d+$/.test(code)) {
    while (code.length < 6) {
      code = '0' + code
    }
  }
  return code
}