import { useEffect, useState } from "react";
import { ChevronRight, Download, File, FileCode2, Folder, FolderOpen } from "lucide-react";

const API_BASE_URL = "http://localhost:5000/api";

interface GeneratedCodeExplorerProps {
  prefix?: string;
  rootLabel?: string;
}

interface CodeTreeNode {
  name: string;
  path: string;
  type: "file" | "folder";
  children?: CodeTreeNode[];
}

interface CodeFilePreview {
  path: string;
  content: string;
  language: string;
}

function TreeNode({
  node,
  depth,
  selectedPath,
  onSelectFile,
}: {
  node: CodeTreeNode;
  depth: number;
  selectedPath: string | null;
  onSelectFile: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(true);

  if (node.type === "folder") {
    return (
      <div className="code-tree-branch">
        <button
          type="button"
          className="code-tree-row code-tree-folder"
          style={{ paddingLeft: `${depth * 16 + 10}px` }}
          onClick={() => setExpanded((current) => !current)}
        >
          <ChevronRight className={`code-tree-chevron ${expanded ? "expanded" : ""}`} />
          {expanded ? <FolderOpen /> : <Folder />}
          <span>{node.name}</span>
        </button>

        {expanded && node.children && (
          <div>
            {node.children.map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={depth + 1}
                selectedPath={selectedPath}
                onSelectFile={onSelectFile}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <button
      type="button"
      className={`code-tree-row code-tree-file ${selectedPath === node.path ? "active" : ""}`}
      style={{ paddingLeft: `${depth * 16 + 10}px` }}
      onDoubleClick={() => onSelectFile(node.path)}
      onClick={() => onSelectFile(node.path)}
      title="Double-click to preview"
    >
      <FileCode2 />
      <span>{node.name}</span>
    </button>
  );
}

export default function GeneratedCodeExplorer({ prefix = "", rootLabel = "generated/code" }: GeneratedCodeExplorerProps) {
  const [tree, setTree] = useState<CodeTreeNode[]>([]);
  const [loadingTree, setLoadingTree] = useState(true);
  const [treeError, setTreeError] = useState("");

  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [preview, setPreview] = useState<CodeFilePreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewError, setPreviewError] = useState("");

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const query = prefix ? `?prefix=${encodeURIComponent(prefix)}` : "";
        const response = await fetch(`${API_BASE_URL}/generated-code/tree${query}`);
        const data = await response.json();

        if (cancelled) {
          return;
        }

        if (data.success) {
          setTree(data.tree || []);
        } else {
          setTreeError(data.error || "Could not load the generated code tree.");
        }
      } catch {
        if (!cancelled) {
          setTreeError("Could not reach the backend to load generated files.");
        }
      } finally {
        if (!cancelled) {
          setLoadingTree(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [prefix]);

  const handleSelectFile = async (path: string) => {
    setSelectedPath(path);
    setLoadingPreview(true);
    setPreviewError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/generated-code/file?path=${encodeURIComponent(path)}`
      );
      const data = await response.json();

      if (data.success) {
        setPreview({ path: data.path, content: data.content, language: data.language });
      } else {
        setPreview(null);
        setPreviewError(data.error || "Could not load this file.");
      }
    } catch {
      setPreview(null);
      setPreviewError("Could not reach the backend to load this file.");
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleDownload = () => {
    if (!preview) {
      return;
    }

    const blob = new Blob([preview.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = preview.path.split("/").pop() || preview.path;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (loadingTree) {
    return <div className="code-explorer-empty">Loading generated files...</div>;
  }

  if (treeError) {
    return <div className="code-explorer-empty">{treeError}</div>;
  }

  if (!tree.length) {
    return <div className="code-explorer-empty">No files have been generated yet.</div>;
  }

  return (
    <div className="code-explorer">
      <div className="code-explorer-tree">
        <div className="code-explorer-tree-heading">
          <Folder />
          <span>{rootLabel}</span>
        </div>
        {tree.map((node) => (
          <TreeNode
            key={node.path}
            node={node}
            depth={0}
            selectedPath={selectedPath}
            onSelectFile={handleSelectFile}
          />
        ))}
      </div>

      <div className="code-explorer-preview">
        {loadingPreview ? (
          <div className="code-explorer-empty">Loading preview...</div>
        ) : previewError ? (
          <div className="code-explorer-empty">{previewError}</div>
        ) : preview ? (
          <div className="code-container">
            <div className="code-header">
              <span>{preview.path}</span>
              <div className="code-header-actions">
                <span>{preview.language}</span>
                <button type="button" className="code-download-btn" onClick={handleDownload} title="Download this file">
                  <Download />
                </button>
              </div>
            </div>
            <pre><code>{preview.content}</code></pre>
          </div>
        ) : (
          <div className="code-explorer-empty">
            <File />
            <span>Double-click a file to preview its contents.</span>
          </div>
        )}
      </div>
    </div>
  );
}
