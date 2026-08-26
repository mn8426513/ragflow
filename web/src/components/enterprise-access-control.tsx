import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { LucidePlus, LucideTrash2, LucideUsers } from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

import {
  AccessGrant,
  AccessTargets,
  getAccessTargets,
  getDatasetPermissions,
  updateDatasetPermissions,
} from '@/services/enterprise-service';

const IS_ENTERPRISE =
  import.meta.env.VITE_RAGFLOW_ENTERPRISE === 'RAGFLOW_ENTERPRISE';

function EnterpriseAccessControl({ datasetId }: { datasetId?: string }) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [subjectType, setSubjectType] =
    useState<AccessGrant['subject_type']>('user');
  const [subjectId, setSubjectId] = useState('');
  const [permission, setPermission] =
    useState<AccessGrant['permission']>('read');

  const { data: targets } = useQuery<AccessTargets>({
    queryKey: ['enterprise/accessTargets'],
    queryFn: async () => (await getAccessTargets()).data.data,
    enabled: IS_ENTERPRISE,
    retry: false,
  });

  const { data: permissionsData } = useQuery<AccessGrant[]>({
    queryKey: ['enterprise/datasetPermissions', datasetId],
    queryFn: async () =>
      (await getDatasetPermissions(datasetId || '')).data.data.grants,
    enabled: IS_ENTERPRISE && !!datasetId,
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: (grants: AccessGrant[]) =>
      updateDatasetPermissions(datasetId || '', grants),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['enterprise/datasetPermissions', datasetId],
      });
    },
  });

  const grants = useMemo(() => permissionsData || [], [permissionsData]);

  const subjectOptions = useMemo(() => {
    if (subjectType === 'department') {
      return (targets?.departments || []).map((item) => ({
        value: item.id,
        label: item.name,
      }));
    }
    if (subjectType === 'role') {
      return (targets?.roles || []).map((item) => ({
        value: item.id,
        label: item.role_name,
      }));
    }
    return (targets?.users || []).map((item) => ({
      value: item.id,
      label: item.email,
    }));
  }, [subjectType, targets]);

  const labelFor = (grant: AccessGrant) => {
    if (grant.subject_type === 'user') {
      return (
        targets?.users.find((item) => item.id === grant.subject_id)?.email ||
        grant.subject_id
      );
    }
    if (grant.subject_type === 'department') {
      return (
        targets?.departments.find((item) => item.id === grant.subject_id)
          ?.name || grant.subject_id
      );
    }
    if (grant.subject_type === 'role') {
      return (
        targets?.roles.find((item) => item.id === grant.subject_id)?.role_name ||
        grant.subject_id
      );
    }
    return grant.subject_id;
  };

  const addGrant = () => {
    if (!subjectId) return;
    saveMutation.mutate([
      ...grants,
      { subject_type: subjectType, subject_id: subjectId, permission },
    ]);
    setSubjectId('');
  };

  const removeGrant = (index: number) => {
    saveMutation.mutate(grants.filter((_, i) => i !== index));
  };

  if (!IS_ENTERPRISE || !datasetId) return null;

  return (
    <Card className="border-0.5 border-border-default bg-transparent">
      <CardHeader className="space-y-0 flex flex-row items-center justify-between">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <LucideUsers className="size-4" />
          {t('knowledgeConfiguration.accessControl')}
        </CardTitle>
        <Button
          size="sm"
          disabled={!subjectId || saveMutation.isPending}
          onClick={addGrant}
        >
          <LucidePlus />
          {t('admin.add')}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <Select
            value={subjectType}
            onValueChange={(value) => {
              setSubjectType(value as AccessGrant['subject_type']);
              setSubjectId('');
            }}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-bg-base">
              <SelectItem value="user">
                {t('knowledgeConfiguration.grantUser')}
              </SelectItem>
              <SelectItem value="department">
                {t('knowledgeConfiguration.grantDepartment')}
              </SelectItem>
              <SelectItem value="role">
                {t('knowledgeConfiguration.grantRole')}
              </SelectItem>
            </SelectContent>
          </Select>
          <Select value={subjectId} onValueChange={setSubjectId}>
            <SelectTrigger>
              <SelectValue placeholder={t('admin.selectUser')} />
            </SelectTrigger>
            <SelectContent className="bg-bg-base">
              {subjectOptions.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={permission}
            onValueChange={(value) =>
              setPermission(value as AccessGrant['permission'])
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-bg-base">
              <SelectItem value="read">
                {t('knowledgeConfiguration.grantRead')}
              </SelectItem>
              <SelectItem value="write">
                {t('knowledgeConfiguration.grantWrite')}
              </SelectItem>
              <SelectItem value="manage">
                {t('knowledgeConfiguration.grantManage')}
              </SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          {grants.map((grant, index) => (
            <div
              key={`${grant.subject_type}-${grant.subject_id}-${grant.permission}`}
              className="flex items-center justify-between rounded-md border border-border-button px-3 py-2"
            >
              <div className="text-sm">
                <span className="font-medium">{labelFor(grant)}</span>
                <span className="ml-2 text-text-secondary">
                  {grant.subject_type} / {grant.permission}
                </span>
              </div>
              <Button
                variant="danger"
                size="icon"
                onClick={() => removeGrant(index)}
              >
                <LucideTrash2 />
              </Button>
            </div>
          ))}
          {!grants.length && (
            <div className="text-sm text-text-secondary">
              {t('knowledgeConfiguration.noGrants')}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default EnterpriseAccessControl;
