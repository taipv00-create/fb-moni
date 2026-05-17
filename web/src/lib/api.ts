export function getApiBase(): string {
  return (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:5000').replace(/\/$/, '');
}

export function api(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${getApiBase()}${path}`, {
    credentials: 'include',
    ...init,
  });
}
