export type DatasetOption = {
  id: string;
  name: string;
  url: string;
};

const apiUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

export async function fetchDatasets(): Promise<DatasetOption[]> {
  let response: Response;
  try {
    response = await fetch(`${apiUrl}/datasets`);
  } catch {
    throw new Error(`Failed to reach API at ${apiUrl}. Check backend server and CORS settings.`);
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Failed to load datasets (${response.status}): ${errorText || "unknown error"}`);
  }

  const payload = (await response.json()) as { datasets?: DatasetOption[] };
  const datasets = payload.datasets ?? [];
  return datasets.filter(
    (dataset) =>
      typeof dataset?.id === "string" &&
      typeof dataset?.name === "string" &&
      typeof dataset?.url === "string"
  );
}
