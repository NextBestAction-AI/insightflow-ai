import { useState, useRef } from "react";
import type { DragEvent, ChangeEvent } from "react";
import {
  UploadCloud,
  FileText,
  Trash2,
  Mail,
  MessageSquare,
  Headphones,
} from "lucide-react";

interface UploadCardProps {
  onStartAnalysis?: (fileName: string) => void;
  isAnalyzing?: boolean;
}

function UploadCard({ onStartAnalysis, isAnalyzing: isAnalyzingProp }: UploadCardProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<{
    name: string;
    size: string;
    type: string;
  } | null>(null);
  const [selectedDocType, setSelectedDocType] = useState<string>("Transcript");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isAnalyzing = isAnalyzingProp ?? false;

  const docTypes = [
    { name: "Transcript", icon: MessageSquare },
    { name: "CRM Notes", icon: FileText },
    { name: "Email", icon: Mail },
    { name: "Support Ticket", icon: Headphones },
    { name: "Conversation", icon: MessageSquare },
  ];

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const processFile = (file: File) => {
    const sizeInMB = (file.size / (1024 * 1024)).toFixed(2);
    setSelectedFile({
      name: file.name,
      size: `${sizeInMB} MB`,
      type: file.type || "application/octet-stream",
    });
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      processFile(e.target.files[0]);
    }
  };

  const triggerFileInput = () => {
    if (isAnalyzing) return;
    fileInputRef.current?.click();
  };

  const selectMockFile = (type: string) => {
    if (isAnalyzing) return;
    setSelectedDocType(type);
    setSelectedFile({
      name: `meeting_transcript.pdf`,
      size: "1.4 MB",
      type: "application/pdf",
    });
  };

  const removeFile = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedFile(null);
  };

  const handleStart = () => {
    if (selectedFile && onStartAnalysis) {
      onStartAnalysis(selectedFile.name);
    }
  };

  return (
    <div className="rounded-[24px] border border-[#334155] bg-[#1E293B] p-6 shadow-lg h-full flex flex-col justify-between">
      <div>
        <div className="flex items-center justify-between border-b border-[#334155] pb-4 mb-4">
          <h2 className="text-lg font-bold text-white">Start Customer Intelligence</h2>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-semibold border ${
              selectedFile
                ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
                : "bg-blue-500/10 border-blue-500/20 text-blue-400"
            }`}
          >
            {selectedFile ? "Ready for analysis" : "Awaiting input"}
          </span>
        </div>

        <p className="text-slate-400 text-xs leading-relaxed">
          Upload customer interactions to trigger the multi-agent orchestrator. Supported:
          Transcript, CRM Notes, Email, Support Ticket, Customer Conversation.
        </p>

        <div className="mt-4 grid grid-cols-3 sm:grid-cols-5 gap-2">
          {docTypes.map((t) => {
            const Icon = t.icon;
            const isSelected = selectedDocType === t.name;
            return (
              <button
                key={t.name}
                type="button"
                onClick={() => selectMockFile(t.name)}
                disabled={isAnalyzing}
                className={`flex flex-col items-center gap-1.5 rounded-xl border p-2 text-center transition-all ${
                  isSelected
                    ? "border-blue-500 bg-blue-500/10 text-white"
                    : "border-[#334155] bg-[#0F172A] text-slate-400 hover:text-slate-200"
                }`}
              >
                <Icon size={16} />
                <span className="text-[9px] font-medium leading-none">{t.name}</span>
              </button>
            );
          })}
        </div>

        <div
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
          onClick={triggerFileInput}
          className={`relative mt-5 flex h-40 cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed transition-all ${
            dragActive
              ? "border-blue-500 bg-blue-500/10"
              : selectedFile
              ? "border-emerald-500/30 bg-[#0F172A]/50"
              : "border-slate-600 bg-[#0F172A] hover:border-blue-500 hover:bg-slate-900/50"
          } ${isAnalyzing ? "opacity-60 cursor-not-allowed" : ""}`}
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            disabled={isAnalyzing}
            className="hidden"
            accept=".txt,.doc,.docx,.pdf,.json,.csv"
          />

          {selectedFile ? (
            <div className="flex flex-col items-center p-4 text-center">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">
                Uploaded
              </p>
              <FileText size={32} className="text-emerald-400" />
              <p className="mt-2 text-xs font-semibold text-white max-w-[200px] truncate">
                {selectedFile.name}
              </p>
              <p className="text-[10px] text-slate-400 mt-1">
                {selectedFile.size} · {selectedDocType}
              </p>
              {!isAnalyzing && (
                <button
                  type="button"
                  onClick={removeFile}
                  className="mt-3 flex items-center gap-1 rounded-lg bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 text-[10px] text-rose-400 font-semibold hover:bg-rose-500/20 transition"
                >
                  <Trash2 size={10} /> Remove
                </button>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center text-center p-4">
              <UploadCloud size={36} className="text-slate-400" />
              <p className="mt-3 text-xs font-semibold text-slate-200">
                Drag & drop interaction file
              </p>
              <p className="text-[10px] text-slate-500 mt-1">or click to browse</p>
            </div>
          )}
        </div>
      </div>

      <button
        onClick={handleStart}
        disabled={!selectedFile || isAnalyzing}
        className={`w-full mt-5 flex items-center justify-center gap-2 rounded-xl py-3.5 text-xs font-extrabold tracking-wider transition-all shadow-md uppercase ${
          selectedFile && !isAnalyzing
            ? "bg-blue-600 hover:bg-blue-700 text-white shadow-blue-500/15 cursor-pointer"
            : "bg-slate-800 text-slate-500 border border-[#334155] cursor-not-allowed"
        }`}
      >
        {isAnalyzing ? (
          <>
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-500 border-t-white" />
            Agents Running...
          </>
        ) : (
          "Start AI Analysis"
        )}
      </button>
    </div>
  );
}

export default UploadCard;
