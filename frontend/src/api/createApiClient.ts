// Kept apart from client.ts so the interface module does not import its own implementations (no import cycle).
import { HttpApiClient } from './http';
import { MockApiClient } from '@/mock/MockApiClient';
import type { ApiClient, ApiMode } from './client';

export function createApiClient(mode: ApiMode): ApiClient {
  return mode === 'mock' ? new MockApiClient() : new HttpApiClient();
}
