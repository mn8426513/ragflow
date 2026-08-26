import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { getWatermarkConfig } from '@/services/enterprise-service';
import authorizationUtil from '@/utils/authorization-util';

const IS_ENTERPRISE =
  import.meta.env.VITE_RAGFLOW_ENTERPRISE === 'RAGFLOW_ENTERPRISE';

function EnterpriseWatermark() {
  const { data: watermark } = useQuery<{
    enabled: boolean;
    text: string;
    opacity: number;
    font_size: number;
  }>({
    queryKey: ['enterprise/watermark'],
    queryFn: async () => (await getWatermarkConfig()).data.data,
    enabled: IS_ENTERPRISE && !!authorizationUtil.getAuthorization(),
    retry: false,
  });

  const text = useMemo(() => {
    if (!watermark?.text) return '';
    const userInfo = authorizationUtil.getUserInfoObject();
    return watermark.text
      .replaceAll('${user_email}', userInfo?.email || '')
      .replaceAll('${user_name}', userInfo?.nickname || '');
  }, [watermark?.text]);

  if (!watermark?.enabled || !text) return null;

  const rows = 10;
  const cols = 10;
  const cells = Array.from({ length: rows * cols }, (_, index) => index);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-[9999] overflow-hidden"
      style={{ opacity: watermark.opacity ?? 0.08 }}
    >
      <div
        className="absolute"
        style={{
          top: '-20%',
          left: '-20%',
          width: '140%',
          height: '140%',
          display: 'grid',
          gridTemplateColumns: `repeat(${cols}, 240px)`,
          gridTemplateRows: `repeat(${rows}, 130px)`,
          alignItems: 'center',
          justifyItems: 'center',
          transform: 'rotate(-30deg)',
          color: 'currentColor',
        }}
      >
        {cells.map((index) => (
          <span
            key={index}
            className="whitespace-nowrap select-none"
            style={{ fontSize: watermark.font_size ?? 16 }}
          >
            {text}
          </span>
        ))}
      </div>
    </div>
  );
}

export default EnterpriseWatermark;
