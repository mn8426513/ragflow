import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useQuery } from '@tanstack/react-query';

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';

import Spotlight from '@/components/spotlight';
import { TableEmpty } from '@/components/table-skeleton';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { RAGFlowPagination } from '@/components/ui/ragflow-pagination';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

import { listAuditLogs } from '@/services/admin-service';

import { EMPTY_DATA, createFuzzySearchFn } from './utils';

const columnHelper = createColumnHelper<AdminService.AuditLog>();
const globalFilterFn = createFuzzySearchFn<AdminService.AuditLog>([
  'email',
  'action',
  'resource_type',
  'resource_id',
]);

function AdminAuditLogs() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [email, setEmail] = useState('');
  const [action, setAction] = useState('');

  const { data, refetch, isFetching } = useQuery({
    queryKey: ['admin/auditLogs', page, pageSize, email, action],
    queryFn: async () =>
      (await listAuditLogs({ page, page_size: pageSize, email, action })).data
        .data,
    retry: false,
  });

  const logs = useMemo(() => data?.logs || EMPTY_DATA, [data]);

  const columnDefs = useMemo(
    () => [
      columnHelper.accessor('create_date', {
        header: t('admin.createTime'),
      }),
      columnHelper.accessor('email', {
        header: t('admin.email'),
      }),
      columnHelper.accessor('action', {
        header: t('admin.action'),
      }),
      columnHelper.accessor('resource_type', {
        header: t('admin.resourceTypeLabel'),
      }),
      columnHelper.accessor('resource_id', {
        header: t('admin.resourceId'),
      }),
      columnHelper.accessor('ip_address', {
        header: 'IP',
      }),
    ],
    [t],
  );

  const table = useReactTable({
    data: logs,
    columns: columnDefs,
    globalFilterFn,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    autoResetPageIndex: false,
  });

  return (
    <Card className="!shadow-none relative w-full h-full border-0.5 border-border-button bg-transparent rounded-xl">
      <Spotlight />
      <ScrollArea className="size-full">
        <CardHeader className="space-y-0 flex flex-row justify-between items-center gap-4">
          <CardTitle>{t('admin.auditLogs')}</CardTitle>
          <div className="flex gap-2">
            <Input
              placeholder={t('admin.email')}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setPage(1);
              }}
            />
            <Input
              placeholder={t('admin.action')}
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
            />
            <Button onClick={() => refetch()} loading={isFetching}>
              {t('admin.refresh')}
            </Button>
          </div>
        </CardHeader>

        <CardContent>
          <Table>
            <TableHeader>
              {table.getHeaderGroups().map((headerGroup) => (
                <TableRow key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                    </TableHead>
                  ))}
                </TableRow>
              ))}
            </TableHeader>
            <TableBody>
              {table.getRowModel().rows?.length ? (
                table.getRowModel().rows.map((row) => (
                  <TableRow key={row.id} className="group/row">
                    {row.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext(),
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              ) : (
                <TableEmpty key="empty" columnsLength={columnDefs.length} />
              )}
            </TableBody>
          </Table>
        </CardContent>

        <CardFooter className="flex items-center justify-end">
          <RAGFlowPagination
            total={data?.total || 0}
            current={page}
            pageSize={pageSize}
            onChange={(nextPage, nextPageSize) => {
              setPage(nextPage);
              setPageSize(nextPageSize);
            }}
          />
        </CardFooter>
      </ScrollArea>
    </Card>
  );
}

export default AdminAuditLogs;
