export function downloadMarkdown(name: string, content: string) {
  const url = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${name.replace(/[^a-z0-9_-]/gi, "-")}.md`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadPdfResponse(response: Response, name: string) {
  if (!response.ok) throw new Error(`Download failed (${response.status}).`);
  const blob = await response.blob();
  const isZip = response.headers.get("Content-Type") === "application/zip";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${name.replace(/[^a-z0-9_-]/gi, "-")}.${isZip ? "zip" : "pdf"}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
