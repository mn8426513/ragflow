import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  LucideKeyRound,
  LucidePlus,
  LucideShieldCheck,
  LucideTrash2,
  LucideDroplets,
} from 'lucide-react';

import Spotlight from '@/components/spotlight';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import {
  getSecuritySettings,
  getSsoProviders,
  testSsoProvider,
  updateSecuritySettings,
  updateSsoProviders,
} from '@/services/admin-service';

function SsoProviderDialog({
  open,
  onOpenChange,
  provider,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  provider: AdminService.SsoProvider | null;
  onSave: (provider: AdminService.SsoProvider) => void;
}) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<AdminService.SsoProvider>(
    provider || {
      channel: '',
      type: 'oidc',
      display_name: '',
      client_id: '',
      client_secret: '',
      redirect_uri: '',
      issuer: '',
      authorization_url: '',
      token_url: '',
      userinfo_url: '',
      scope: 'openid email profile',
    },
  );

  const current = useMemo(
    () =>
      provider ||
      ({
        channel: '',
        type: 'oidc',
        display_name: '',
        client_id: '',
        client_secret: '',
        redirect_uri: '',
        issuer: '',
        authorization_url: '',
        token_url: '',
        userinfo_url: '',
        scope: 'openid email profile',
      } as AdminService.SsoProvider),
    [provider],
  );

  const testMutation = useMutation({
    mutationFn: () => testSsoProvider(draft),
  });

  const set = (key: keyof AdminService.SsoProvider, value: string) =>
    setDraft((prev) => ({ ...prev, [key]: value }));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-bg-base">
        <DialogHeader>
          <DialogTitle>
            {provider ? t('admin.editSsoProvider') : t('admin.addSsoProvider')}
          </DialogTitle>
        </DialogHeader>
        <div className="grid gap-4">
          <Label>{t('admin.channel')}</Label>
          <Input value={draft.channel} onChange={(e) => set('channel', e.target.value)} />
          <Label>{t('admin.ssoType')}</Label>
          <Select
            value={draft.type}
            onValueChange={(value) =>
              set('type', value as AdminService.SsoProvider['type'])
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-bg-base">
              <SelectItem value="oidc">OIDC</SelectItem>
              <SelectItem value="oauth2">OAuth2</SelectItem>
              <SelectItem value="github">GitHub</SelectItem>
            </SelectContent>
          </Select>
          <Label>{t('admin.displayName')}</Label>
          <Input
            value={draft.display_name}
            onChange={(e) => set('display_name', e.target.value)}
          />
          <Label>{t('admin.clientId')}</Label>
          <Input
            value={draft.client_id}
            onChange={(e) => set('client_id', e.target.value)}
          />
          <Label>{t('admin.clientSecret')}</Label>
          <Input
            type="password"
            value={draft.client_secret}
            onChange={(e) => set('client_secret', e.target.value)}
          />
          <Label>{t('admin.redirectUri')}</Label>
          <Input
            value={draft.redirect_uri}
            onChange={(e) => set('redirect_uri', e.target.value)}
          />
          {draft.type === 'oidc' ? (
            <>
              <Label>{t('admin.issuer')}</Label>
              <Input value={draft.issuer} onChange={(e) => set('issuer', e.target.value)} />
            </>
          ) : (
            <>
              <Label>{t('admin.authorizationUrl')}</Label>
              <Input
                value={draft.authorization_url}
                onChange={(e) => set('authorization_url', e.target.value)}
              />
              <Label>{t('admin.tokenUrl')}</Label>
              <Input
                value={draft.token_url}
                onChange={(e) => set('token_url', e.target.value)}
              />
              <Label>{t('admin.userinfoUrl')}</Label>
              <Input
                value={draft.userinfo_url}
                onChange={(e) => set('userinfo_url', e.target.value)}
              />
            </>
          )}
        </div>
        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            loading={testMutation.isPending}
            onClick={() => testMutation.mutate()}
          >
            {t('admin.testConnection')}
          </Button>
          <Button onClick={() => onSave({ ...current, ...draft })}>
            {t('admin.save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AdminSecurity() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const { data: settings } = useQuery({
    queryKey: ['admin/securitySettings'],
    queryFn: async () => (await getSecuritySettings()).data.data,
    retry: false,
  });

  const { data: sso } = useQuery({
    queryKey: ['admin/ssoProviders'],
    queryFn: async () => (await getSsoProviders()).data.data.providers,
    retry: false,
  });

  const [ssoDialogOpen, setSsoDialogOpen] = useState(false);
  const [editingProvider, setEditingProvider] =
    useState<AdminService.SsoProvider | null>(null);

  const updateMutation = useMutation({
    mutationFn: (patch: Partial<AdminService.SecuritySettings>) =>
      updateSecuritySettings(patch),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ['admin/securitySettings'] }),
  });

  const ssoMutation = useMutation({
    mutationFn: (providers: AdminService.SsoProvider[]) =>
      updateSsoProviders(providers),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin/ssoProviders'] });
      setSsoDialogOpen(false);
      setEditingProvider(null);
    },
  });

  const watermark = settings?.watermark || {
    enabled: false,
    text: '${user_email} ${user_name}',
    opacity: 0.08,
    font_size: 16,
  };
  const passwordPolicy = settings?.password_policy || {
    min_length: 8,
    require_uppercase: false,
    require_lowercase: false,
    require_digit: false,
    require_special: false,
  };
  const loginLockout = settings?.login_lockout || { max_attempts: 5, lock_minutes: 15 };

  return (
    <Card className="!shadow-none relative w-full h-full border-0.5 border-border-button bg-transparent rounded-xl">
      <Spotlight />
      <ScrollArea className="size-full">
        <CardHeader>
          <CardTitle>{t('admin.securitySettings')}</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="watermark">
            <TabsList>
              <TabsTrigger value="watermark">
                <LucideDroplets /> {t('admin.watermark')}
              </TabsTrigger>
              <TabsTrigger value="password">
                <LucideKeyRound /> {t('admin.passwordPolicy')}
              </TabsTrigger>
              <TabsTrigger value="lockout">
                <LucideShieldCheck /> {t('admin.loginLockout')}
              </TabsTrigger>
              <TabsTrigger value="sso">SSO</TabsTrigger>
            </TabsList>

            <TabsContent value="watermark" className="space-y-4">
              <div className="flex items-center gap-3">
                <Switch
                  checked={watermark.enabled}
                  onCheckedChange={(checked) =>
                    updateMutation.mutate({
                      watermark: { ...watermark, enabled: checked },
                    })
                  }
                />
                <Label>{t('admin.enableWatermark')}</Label>
              </div>
              <Label>{t('admin.watermarkText')}</Label>
              <Input
                value={watermark.text}
                onChange={(e) =>
                  updateMutation.mutate({
                    watermark: { ...watermark, text: e.target.value },
                  })
                }
              />
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>{t('admin.watermarkOpacity')}</Label>
                  <Input
                    type="number"
                    step={0.01}
                    min={0}
                    max={1}
                    value={watermark.opacity}
                    onChange={(e) =>
                      updateMutation.mutate({
                        watermark: {
                          ...watermark,
                          opacity: Number(e.target.value),
                        },
                      })
                    }
                  />
                </div>
                <div>
                  <Label>{t('admin.watermarkFontSize')}</Label>
                  <Input
                    type="number"
                    value={watermark.font_size}
                    onChange={(e) =>
                      updateMutation.mutate({
                        watermark: {
                          ...watermark,
                          font_size: Number(e.target.value),
                        },
                      })
                    }
                  />
                </div>
              </div>
            </TabsContent>

            <TabsContent value="password" className="space-y-4">
              <Label>{t('admin.minPasswordLength')}</Label>
              <Input
                type="number"
                value={passwordPolicy.min_length}
                onChange={(e) =>
                  updateMutation.mutate({
                    password_policy: {
                      ...passwordPolicy,
                      min_length: Number(e.target.value),
                    },
                  })
                }
              />
              {(
                [
                  ['require_uppercase', t('admin.requireUppercase')],
                  ['require_lowercase', t('admin.requireLowercase')],
                  ['require_digit', t('admin.requireDigit')],
                  ['require_special', t('admin.requireSpecial')],
                ] as const
              ).map(([key, label]) => (
                <div key={key} className="flex items-center gap-3">
                  <Switch
                    checked={passwordPolicy[key]}
                    onCheckedChange={(checked) =>
                      updateMutation.mutate({
                        password_policy: {
                          ...passwordPolicy,
                          [key]: checked,
                        },
                      })
                    }
                  />
                  <Label>{label}</Label>
                </div>
              ))}
            </TabsContent>

            <TabsContent value="lockout" className="space-y-4">
              <Label>{t('admin.maxLoginAttempts')}</Label>
              <Input
                type="number"
                value={loginLockout.max_attempts}
                onChange={(e) =>
                  updateMutation.mutate({
                    login_lockout: {
                      ...loginLockout,
                      max_attempts: Number(e.target.value),
                    },
                  })
                }
              />
              <Label>{t('admin.lockMinutes')}</Label>
              <Input
                type="number"
                value={loginLockout.lock_minutes}
                onChange={(e) =>
                  updateMutation.mutate({
                    login_lockout: {
                      ...loginLockout,
                      lock_minutes: Number(e.target.value),
                    },
                  })
                }
              />
            </TabsContent>

            <TabsContent value="sso" className="space-y-4">
              <div className="flex justify-end">
                <Button
                  onClick={() => {
                    setEditingProvider(null);
                    setSsoDialogOpen(true);
                  }}
                >
                  <LucidePlus />
                  {t('admin.addSsoProvider')}
                </Button>
              </div>
              {(sso || []).map((provider) => (
                <Card key={provider.channel} className="bg-bg-card">
                  <CardContent className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">
                        {provider.display_name || provider.channel}
                      </div>
                      <div className="text-sm text-text-secondary">
                        {provider.type} / {provider.issuer || provider.authorization_url}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="ghost"
                        onClick={() => {
                          setEditingProvider(provider);
                          setSsoDialogOpen(true);
                        }}
                      >
                        {t('admin.edit')}
                      </Button>
                      <Button
                        variant="danger"
                        size="icon"
                        onClick={() =>
                          ssoMutation.mutate(
                            (sso || []).filter(
                              (item) => item.channel !== provider.channel,
                            ),
                          )
                        }
                      >
                        <LucideTrash2 />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </TabsContent>
          </Tabs>
        </CardContent>
      </ScrollArea>

      <SsoProviderDialog
        key={editingProvider?.channel || 'new'}
        open={ssoDialogOpen}
        onOpenChange={setSsoDialogOpen}
        provider={editingProvider}
        onSave={(provider) => {
          const next = sso || [];
          const index = next.findIndex((item) => item.channel === provider.channel);
          if (index >= 0) {
            next[index] = provider;
          } else {
            next.push(provider);
          }
          ssoMutation.mutate(next);
        }}
      />
    </Card>
  );
}

export default AdminSecurity;
