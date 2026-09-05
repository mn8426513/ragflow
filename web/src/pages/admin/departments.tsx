import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  LucideBuilding2,
  LucidePlus,
  LucideTrash2,
  LucideUsers,
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
  DialogDescription,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { TableEmpty } from '@/components/table-skeleton';

import {
  addDepartmentMembers,
  createDepartment,
  deleteDepartment,
  listDepartmentMembers,
  listDepartments,
  listUsers,
  removeDepartmentMembers,
  updateDepartment,
} from '@/services/admin-service';

import { EMPTY_DATA } from './utils';

function DepartmentMembersDialog({
  department,
  open,
  onOpenChange,
}: {
  department: AdminService.Department | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedUserId, setSelectedUserId] = useState('');

  const { data: members } = useQuery({
    queryKey: ['admin/departmentMembers', department?.id],
    queryFn: async () =>
      (await listDepartmentMembers(department?.id || '')).data.data.members,
    enabled: open && !!department?.id,
    retry: false,
  });

  const { data: users } = useQuery({
    queryKey: ['admin/users'],
    queryFn: async () => (await listUsers()).data.data,
    retry: false,
  });

  const addMutation = useMutation({
    mutationFn: (userId: string) =>
      addDepartmentMembers(department?.id || '', [userId]),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['admin/departmentMembers', department?.id],
      });
      queryClient.invalidateQueries({ queryKey: ['admin/listDepartments'] });
      setSelectedUserId('');
    },
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) =>
      removeDepartmentMembers(department?.id || '', [userId]),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['admin/departmentMembers', department?.id],
      });
      queryClient.invalidateQueries({ queryKey: ['admin/listDepartments'] });
    },
  });

  const availableUsers = useMemo(
    () =>
      (users || EMPTY_DATA).filter(
        (user) => !(members || EMPTY_DATA).some((m) => m.user_id === user.id),
      ),
    [users, members],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-bg-base">
        <DialogHeader>
          <DialogTitle>
            {t('admin.departmentMembers')} - {department?.name}
          </DialogTitle>
          <DialogDescription>
            {t('admin.departmentMembersDescription')}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex gap-2">
            <Select value={selectedUserId} onValueChange={setSelectedUserId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t('admin.selectUser')} />
              </SelectTrigger>
              <SelectContent className="bg-bg-base">
                {availableUsers.map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {user.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              disabled={!selectedUserId || addMutation.isPending}
              onClick={() => addMutation.mutate(selectedUserId)}
            >
              <LucidePlus />
              {t('admin.add')}
            </Button>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('admin.email')}</TableHead>
                <TableHead>{t('admin.nickname')}</TableHead>
                <TableHead className="w-20"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(members || EMPTY_DATA).map((member) => (
                <TableRow key={member.user_id}>
                  <TableCell>{member.email}</TableCell>
                  <TableCell>{member.nickname}</TableCell>
                  <TableCell>
                    <Button
                      variant="danger"
                      size="icon"
                      onClick={() => removeMutation.mutate(member.user_id)}
                    >
                      <LucideTrash2 />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function AdminDepartments() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [editDepartment, setEditDepartment] =
    useState<AdminService.Department | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [membersOpen, setMembersOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [parentId, setParentId] = useState('');

  const { data: departments } = useQuery({
    queryKey: ['admin/listDepartments'],
    queryFn: async () => (await listDepartments()).data.data.departments,
    retry: false,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['admin/listDepartments'] });

  const createMutation = useMutation({
    mutationFn: () =>
      createDepartment({ name, description, parent_id: parentId || undefined }),
    onSuccess: () => {
      invalidate();
      setCreateOpen(false);
      setName('');
      setDescription('');
      setParentId('');
    },
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateDepartment(editDepartment?.id || '', {
        name,
        description,
        parent_id: parentId || undefined,
      }),
    onSuccess: () => {
      invalidate();
      setEditDepartment(null);
      setCreateOpen(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteDepartment(editDepartment?.id || ''),
    onSuccess: () => {
      invalidate();
      setDeleteOpen(false);
      setEditDepartment(null);
    },
  });

  const openCreate = () => {
    setEditDepartment(null);
    setName('');
    setDescription('');
    setParentId('');
    setCreateOpen(true);
  };

  const openEdit = (department: AdminService.Department) => {
    setEditDepartment(department);
    setName(department.name);
    setDescription(department.description || '');
    setParentId(department.parent_id || '');
    setCreateOpen(true);
  };

  return (
    <Card className="!shadow-none relative w-full h-full border-0.5 border-border-button bg-transparent rounded-xl">
      <Spotlight />
      <ScrollArea className="size-full">
        <CardHeader className="space-y-0 flex flex-row justify-between items-center">
          <CardTitle>{t('admin.departments')}</CardTitle>
          <Button className="h-10 px-4" onClick={openCreate}>
            <LucidePlus />
            {t('admin.newDepartment')}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {(departments || EMPTY_DATA).map((department) => (
            <Card
              key={department.id}
              className="border-0.5 border-border-default bg-transparent"
            >
              <CardHeader className="space-y-0 flex flex-row gap-4 items-center">
                <LucideBuilding2 className="size-5 text-text-secondary" />
                <div className="space-y-1 flex-1">
                  <div className="font-medium">{department.name}</div>
                  <div className="text-sm text-text-secondary break-words">
                    {department.description || t('admin.noDescription')}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    setEditDepartment(department);
                    setMembersOpen(true);
                  }}
                >
                  <LucideUsers />
                </Button>
                <Button variant="ghost" size="icon" onClick={() => openEdit(department)}>
                  {t('admin.edit')}
                </Button>
                <Button
                  variant="danger"
                  size="icon"
                  onClick={() => {
                    setEditDepartment(department);
                    setDeleteOpen(true);
                  }}
                >
                  <LucideTrash2 />
                </Button>
              </CardHeader>
            </Card>
          ))}
          {!departments?.length && (
            <TableEmpty columnsLength={1} />
          )}
        </CardContent>
      </ScrollArea>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-bg-base">
          <DialogHeader>
            <DialogTitle>
              {editDepartment
                ? t('admin.editDepartment')
                : t('admin.newDepartment')}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <Label>{t('admin.departmentName')}</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
            <Label>{t('admin.parentDepartment')}</Label>
            <Select value={parentId} onValueChange={setParentId}>
              <SelectTrigger>
                <SelectValue placeholder={t('admin.none')} />
              </SelectTrigger>
              <SelectContent className="bg-bg-base">
                {(departments || EMPTY_DATA)
                  .filter((d) => d.id !== editDepartment?.id)
                  .map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Label>{t('admin.description')}</Label>
            <Input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button
              loading={createMutation.isPending || updateMutation.isPending}
              onClick={() =>
                editDepartment
                  ? updateMutation.mutate()
                  : createMutation.mutate()
              }
            >
              {t('admin.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="bg-bg-base">
          <DialogHeader>
            <DialogTitle>{t('admin.deleteDepartment')}</DialogTitle>
            <DialogDescription>
              {t('admin.deleteDepartmentConfirmation', {
                name: editDepartment?.name,
              })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="danger"
              loading={deleteMutation.isPending}
              onClick={() => deleteMutation.mutate()}
            >
              {t('admin.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DepartmentMembersDialog
        department={editDepartment}
        open={membersOpen}
        onOpenChange={setMembersOpen}
      />
    </Card>
  );
}

export default AdminDepartments;
