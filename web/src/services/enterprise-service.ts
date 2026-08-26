/*
 *  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
 *
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

import api from '@/utils/api';
import request from '@/utils/request';

const {
  enterpriseAccessTargets,
  enterpriseDatasetPermissions,
  enterpriseWatermark,
} = api;

export type AccessGrant = {
  id?: string;
  subject_type: 'user' | 'department' | 'role' | 'team';
  subject_id: string;
  permission: 'read' | 'write' | 'manage';
};

export type AccessTargets = {
  departments: { id: string; name: string; parent_id?: string | null }[];
  roles: { id: string; role_name: string }[];
  users: { id: string; email: string; nickname?: string }[];
};

export const getAccessTargets = async (): Promise<any> =>
  request.get<{ code: number; data: AccessTargets }>(enterpriseAccessTargets);

export const getDatasetPermissions = async (datasetId: string): Promise<any> =>
  request.get<{ code: number; data: { grants: AccessGrant[] } }>(
    enterpriseDatasetPermissions(datasetId),
  );

export const updateDatasetPermissions = async (
  datasetId: string,
  grants: AccessGrant[],
): Promise<any> =>
  request.put<{ code: number }>(enterpriseDatasetPermissions(datasetId), {
    grants,
  });

export const getWatermarkConfig = async (): Promise<any> =>
  request.get<{
    code: number;
    data: {
      enabled: boolean;
      text: string;
      opacity: number;
      font_size: number;
    };
  }>(enterpriseWatermark);
