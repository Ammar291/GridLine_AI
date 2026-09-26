import type { ApiClient } from '@/api/client';
import { cityFixture } from '@/test/fixtures/city';

/** An ApiClient for tests: city() resolves the fixture, approvals() resolves [], everything else rejects unless overridden. */
export function fakeClient(overrides: Partial<ApiClient> = {}): ApiClient {
  const rejectMock = () => Promise.reject(new Error('not implemented'));
  return {
    mode: 'mock', health: rejectMock, llmStatus: rejectMock, city: () => Promise.resolve(cityFixture), events: rejectMock,
    incidents: rejectMock, incident: rejectMock, approvals: () => Promise.resolve([]), decide: rejectMock, actions: rejectMock,
    action: rejectMock, document: rejectMock, chunk: rejectMock,
    simulation: { start: rejectMock, pause: rejectMock, resume: rejectMock, reset: rejectMock, setSpeed: rejectMock, inject: rejectMock },
    openSocket: () => ({ close: () => undefined }),
    ...overrides,
  };
}
