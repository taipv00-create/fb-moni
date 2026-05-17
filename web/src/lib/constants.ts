export const CAT_COLORS: Record<string, { bg: string; fg: string }> = {
  'Mua bán': { bg: '#dcfce7', fg: '#166534' },
  'Hỏi đáp': { bg: '#dbeafe', fg: '#1e40af' },
  'Thông báo': { bg: '#f3e8ff', fg: '#6b21a8' },
  'Tán gẫu': { bg: '#ccfbf1', fg: '#115e59' },
  'Spam/Quảng cáo': { bg: '#fee2e2', fg: '#991b1b' },
  'Tuyển dụng': { bg: '#ffedd5', fg: '#9a3412' },
  'Chia sẻ kiến thức': { bg: '#e0e7ff', fg: '#3730a3' },
};

export function catBg(cat: string): string {
  return (CAT_COLORS[cat] || { bg: '#f3f4f6' }).bg;
}

export function catFg(cat: string): string {
  return (CAT_COLORS[cat] || { fg: '#374151' }).fg;
}
