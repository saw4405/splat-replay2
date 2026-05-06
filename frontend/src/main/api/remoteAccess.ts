export type RemoteAccessStatus = {
  enabled: boolean;
  active: boolean;
  bind_host: string;
  port: number;
  restart_required: boolean;
  access_urls: string[];
};

export async function fetchRemoteAccessStatus(): Promise<RemoteAccessStatus> {
  const response = await fetch('/api/remote-access/status', { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`failed with status ${response.status}`);
  }
  return (await response.json()) as RemoteAccessStatus;
}
