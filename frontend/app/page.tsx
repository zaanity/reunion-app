"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";

type UploadFile = { file: File; id: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://127.0.0.1:8000";
const ACCEPT = "image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/webm";
const MAX_FILES = 50;
const MAX_FILE_BYTES = 500 * 1024 * 1024;
const MAX_TOTAL_BYTES = 2048 * 1024 * 1024;
const CONTRIBUTOR_KEY = "samaagam_memory_drop_contributor_id";

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function getContributorId() {
  const existing = window.localStorage.getItem(CONTRIBUTOR_KEY);
  if (existing) return existing;
  const id = crypto.randomUUID();
  window.localStorage.setItem(CONTRIBUTOR_KEY, id);
  return id;
}

export default function Home() {
  const [name, setName] = useState("");
  const [contributorId, setContributorId] = useState("");
  const [items, setItems] = useState<UploadFile[]>([]);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploadedCount, setUploadedCount] = useState(0);
  const [totalAtStart, setTotalAtStart] = useState(0);
  const [status, setStatus] = useState("");
  const [currentFileLabel, setCurrentFileLabel] = useState("");
  const [uploadComplete, setUploadComplete] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queueRef = useRef<UploadFile[]>([]);

  useEffect(() => setContributorId(getContributorId()), []);

  // Warn before a reload/tab close while there are unsent files or an active upload.
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (!uploading && items.length === 0) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [uploading, items.length]);

  const totalSize = useMemo(() => items.reduce((sum, item) => sum + item.file.size, 0), [items]);
  const queueFull = items.length >= MAX_FILES || totalSize >= MAX_TOTAL_BYTES;
  const canUpload = name.trim().length > 1 && items.length > 0 && !uploading && Boolean(contributorId);

  function addFiles(list: FileList | File[]) {
    if (uploadComplete) setUploadComplete(false);
    if (queueRef.current.length >= MAX_FILES || queueRef.current.reduce((sum, item) => sum + item.file.size, 0) >= MAX_TOTAL_BYTES) {
      setStatus("THE MEMORY QUEUE IS FULL. SEND THESE MEMORIES BEFORE ADDING MORE.");
      return;
    }

    const incoming = Array.from(list);
    const acceptedTypes = ACCEPT.split(",");
    const valid = incoming.filter((file) => acceptedTypes.includes(file.type));
    const tooLarge = valid.filter((file) => file.size > MAX_FILE_BYTES);
    const accepted = valid.filter((file) => file.size <= MAX_FILE_BYTES);
    const currentQueue = queueRef.current;
    const currentTotal = currentQueue.reduce((sum, item) => sum + item.file.size, 0);
    const availableSlots = Math.max(0, MAX_FILES - currentQueue.length);
    const next = accepted.slice(0, availableSlots).map((file) => ({
      file,
      id: `${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
    }));
    const projectedTotal = currentTotal + next.reduce((sum, item) => sum + item.file.size, 0);

    if (projectedTotal > MAX_TOTAL_BYTES) {
      setStatus("THE QUEUE EXCEEDS THE 2 GB LIMIT. REMOVE A FEW FILES OR SEND THE CURRENT QUEUE FIRST.");
      return;
    }

    queueRef.current = [...queueRef.current, ...next];
    setItems(queueRef.current);
    if (tooLarge.length || valid.length !== incoming.length || next.length < accepted.length) {
      setStatus("SOME FILES WERE SKIPPED. EACH FILE MUST BE ≤ 500 MB, WITH UP TO 50 FILES / 2 GB IN THE QUEUE.");
    } else if (uploading) {
      setStatus("ADDED TO THE BROADCAST QUEUE — IT WILL GO OUT AUTOMATICALLY.");
    } else {
      setStatus("");
    }
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    if (event.target.files) addFiles(event.target.files);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (event.dataTransfer.files.length) addFiles(event.dataTransfer.files);
  }

  function removeFile(id: string) {
    if (uploading) return;
    queueRef.current = queueRef.current.filter((item) => item.id !== id);
    setItems(queueRef.current);
  }

  function uploadBatch(batch: UploadFile[], batchNumber: number, batchTotal: number) {
    return new Promise<any>((resolve, reject) => {
      const form = new FormData();
      form.append("user_name", name.trim());
      form.append("contributor_id", contributorId);
      for (const item of batch) form.append("files", item.file, item.file.name);

      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_URL}/api/memory-drop`);
      xhr.upload.onprogress = (event) => {
        if (!event.lengthComputable) return;
        const batchProgress = event.loaded / event.total;
        const overall = ((batchNumber + batchProgress) / batchTotal) * 100;
        setProgress(Math.min(99, Math.round(overall)));
      };
      xhr.onload = () => {
        let data: any = {};
        try { data = JSON.parse(xhr.responseText || "{}"); } catch {}
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new Error(data.detail || `Upload failed (${xhr.status})`));
      };
      xhr.onerror = () => reject(new Error("NETWORK ERROR — PLEASE CHECK YOUR CONNECTION AND TRY AGAIN."));
      xhr.onabort = () => reject(new Error("UPLOAD CANCELLED."));
      xhr.send(form);
    });
  }

  async function upload() {
    if (!canUpload) return;

    queueRef.current = [...items];
    setUploading(true);
    setUploadComplete(false);
    setProgress(0);
    setUploadedCount(0);
    setTotalAtStart(items.length);
    setStatus("TUNING IN TO THE MEMORY FREQUENCY…");

    let completed = 0;

    try {
      // Each batch is a snapshot. New files can be added while the current batch is uploading.
      // They remain in the queue and are picked up automatically after the current batch.
      while (queueRef.current.length > 0) {
        const batch = queueRef.current.slice(0, MAX_FILES);
        setCurrentFileLabel(batch.length === 1 ? batch[0].file.name : `${batch.length} memories in this transmission`);
        setStatus(batch.length === 1 ? `BROADCASTING ${batch[0].file.name}…` : `BROADCASTING ${batch.length} MEMORIES…`);

        const result = await uploadBatch(batch, 0, 1);
        completed += Number(result.uploaded ?? batch.length);
        setUploadedCount(completed);
        setProgress(100);

        // Remove only the files that were actually sent. Any files added while
        // the request was running remain in queueRef and are sent next.
        queueRef.current = queueRef.current.slice(batch.length);
        setItems(queueRef.current);

        if (queueRef.current.length > 0) {
          setProgress(Math.min(99, Math.round((completed / Math.max(totalAtStart, completed + queueRef.current.length)) * 100)));
        }
      }

      // The upload is fully acknowledged by the server. Clear the client queue
      // so sent files do not continue to look pending after a successful upload.
      queueRef.current = [];
      setItems([]);
      setProgress(100);
      setCurrentFileLabel("");
      setUploadComplete(true);
      setStatus(`MEMORY DROP COMPLETE — ${completed} FILE${completed === 1 ? "" : "S"} SENT TO YOUR MEMORY FOLDER.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "THE BROADCAST COULD NOT RECEIVE YOUR FILES. PLEASE TRY AGAIN.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <main className="page">
      <div className="grid" /><div className="noise" />

      {uploading && (
        <div className="broadcastOverlay" role="dialog" aria-modal="true" aria-label="Uploading your memories">
          <div className="broadcastGlow" />
          <div className="broadcastPanel">
            <div className="broadcastTopline"><span><i /> ON AIR</span><span>SAMAAGAM ’26</span></div>
            <div className="radioVisual" aria-hidden="true">
              <div className="dialOuter"><div className="dialInner"><span>FM</span><b>∞</b></div></div>
              <div className="waveform">
                {[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15].map((bar) => <i key={bar} style={{ animationDelay: `${bar * -0.08}s` }} />)}
              </div>
            </div>
            <p className="broadcastKicker">CAMPUS FM / YAADON KA FM BOX</p>
            <h2>BROADCASTING<br /><em>YOUR MEMORIES.</em></h2>
            <p className="broadcastCopy">Your originals are being sent to your private memory folder. Please keep this page open until the broadcast is complete.</p>
            <div className="broadcastStats">
              <strong>{progress}%</strong>
              <span>{uploadedCount} / {Math.max(totalAtStart, uploadedCount + items.length)} FILES SENT</span>
            </div>
            <div className="broadcastTrack"><div style={{ width: `${progress}%` }} /></div>
            <div className="nowPlaying"><span className="equalizer"><i/><i/><i/><i/></span><span className="marquee">NOW BROADCASTING · {currentFileLabel || "YOUR MEMORIES"}</span></div>
            <button
              className="queueButton"
              type="button"
              disabled={queueFull}
              onClick={() => fileInputRef.current?.click()}
            >
              {queueFull ? "QUEUE LIMIT REACHED" : "+ ADD MORE TO THE QUEUE"}
            </button>
            <input ref={fileInputRef} className="hiddenFileInput" type="file" accept={ACCEPT} multiple onChange={onFileChange} />
            <p className="queueHint">{queueFull ? "50 files or 2 GB is the maximum queue size." : "Added files will be broadcast automatically after the current transmission."}</p>
          </div>
        </div>
      )}

      <header className="header shell"><div className="brand"><span>SIBM BENGALURU</span><strong>CAMPUS FM</strong></div><div className="onAir"><i />MEMORY DROP</div></header>
      <section className="hero shell">
        <div className="kicker">SAMAAGAM &apos;26 / YAADON KA FM BOX</div>
        <h1>ADD YOUR<br /><em>MEMORIES</em><br />TO THE BROADCAST.</h1>
        <p className="intro">Help us build the shared alumni archive. Enter your name, choose your photos and videos, and send them directly to your private memory folder. Your original files are sent without client-side compression.</p>
        <section className="card">
          <div className="step">01 — IDENTIFY YOUR MEMORY DROP</div>
          <label htmlFor="name">YOUR NAME</label>
          <input id="name" value={name} maxLength={120} autoComplete="name" placeholder="Enter your full name" onChange={(event) => setName(event.target.value)} disabled={uploading} />
          <div className="divider" />
          <div className="step">02 — ADD YOUR MEMORIES</div>
          <div className={`drop ${dragging ? "dragging" : ""} ${uploading ? "uploadingDrop" : ""}`} onDragEnter={(event) => { event.preventDefault(); setDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
            <div className="uploadIcon">↥</div><strong>{uploading ? "ADD MORE TO THE QUEUE" : "DROP PHOTOS & VIDEOS HERE"}</strong>
            <span>JPG · PNG · WEBP · MP4 · MOV · WEBM<br />ORIGINAL FILES — NO CLIENT-SIDE COMPRESSION</span>
            <label className="selectButton" htmlFor="files">{uploading ? "ADD MORE FILES" : "SELECT FILES"}</label>
            <input id="files" type="file" accept={ACCEPT} multiple onChange={onFileChange} disabled={queueFull} />
          </div>
          {!uploadComplete && items.length > 0 && <div className="fileList">{items.map((item) => <div className="fileRow" key={item.id}><div className="fileInfo"><strong>{item.file.name}</strong><span>{formatSize(item.file.size)} · {item.file.type || "FILE"}</span></div><button className="remove" type="button" onClick={() => removeFile(item.id)} aria-label={`Remove ${item.file.name}`} disabled={uploading}>×</button></div>)}</div>}
          {!uploadComplete && items.length > 0 && <div className="summary">{items.length} FILE{items.length === 1 ? "" : "S"} IN QUEUE · {formatSize(totalSize)} · MAX 50 FILES / 2 GB</div>}
          {!uploading && <p className="uploadDesktopHint">{items.length ? "READY TO BROADCAST — THE UPLOAD CONTROL STAYS WITH YOU AS YOU REVIEW YOUR MEMORIES." : "ADD YOUR MEMORIES ABOVE TO START THE BROADCAST."}</p>}
          <p className="status" aria-live="polite">{status}</p>
          <p className="privacy">YOUR NAME IS USED TO IDENTIFY YOUR PRIVATE MEMORY FOLDER. VISITORS CANNOT BROWSE THE DRIVE OR ACCESS OTHER USERS&apos; FILES. GOOGLE DRIVE CREDENTIALS STAY ON THE SERVER.</p>
        </section>
      </section>
      {!uploading && !uploadComplete && items.length > 0 && (
        <div className="floatingUploadBar" role="region" aria-label="Upload controls">
          <div className="floatingUploadInner">
            <div className="floatingUploadInfo">
              <span className="floatingLiveDot" />
              <div>
                <strong>{items.length} MEMORY{items.length === 1 ? "" : "IES"} READY</strong>
                <span>{formatSize(totalSize)} · MAX 50 FILES / 2 GB</span>
              </div>
            </div>
            <button className="submit floatingSubmit" type="button" disabled={!canUpload} onClick={upload}>
              <span>{canUpload ? "CREATE MY FOLDER & SEND MEMORIES" : "ENTER NAME TO SEND MEMORIES"}</span>
              <b>↗</b>
            </button>
          </div>
        </div>
      )}
      <footer className="footer shell"><span>BROADCASTING THE GOOD TIMES</span><span>© SAMAAGAM &apos;26</span><span>#YAADONKAFMBOX</span><strong>DESIGNED BY ALUMNI COMMITTEE <b>♥</b> WITH LOVE</strong></footer>
    </main>
  );
}
