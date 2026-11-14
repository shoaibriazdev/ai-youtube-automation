import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { get, post, waitJob, usd, fmtTime } from "./api.js";

export const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function Card({ title, right, children, className = "" }) {
  return (
    <div className={`card ${className}`}>
      {(title || right) && <h2><span>{title}</span><span className="row">{right}</span></h2>}
      {children}
    </div>
  );
}

const STATUS_CLASS = {
  done: "ok", uploaded: "ok", approved: "ok", scheduled: "info", ready_for_review: "info", running: "info",
  queued: "info", uploading: "info", failed: "err", awaiting_cost_approval: "warn", needs_approval: "warn",
  cancelled: "warn", draft: "", error: "err", warning: "warn", info: "",
};
export const Badge = ({ s, children }) => <span className={`badge ${STATUS_CLASS[s] ?? ""}`}>{children ?? String(s || "").replaceAll("_", " ")}</span>;

export function ErrorBox({ error }) {
  if (!error) return null;
  return <div className="alert err">{String(error)}</div>;
}

export function Field({ label, children, hint }) {
  return <label className="f">{label}{children}{hint && <span className="small muted">{hint}</span>}</label>;
}

export function Modal({ title, children, onClose, actions }) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>{title}</h3>
        {children}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>{actions}</div>
      </div>
    </div>
  );
}

/** Starts a backend job and tracks it. */
export function useJob(onDone) {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const start = useCallback(async (promise) => {
    setError(null);
    try {
      const { job_id } = await promise;
      setJob({ id: job_id, status: "queued", progress: 0, message: "Queued" });
      const final = await waitJob(job_id, setJob);
      if (final.status === "failed") setError(final.error || "Job failed");
      onDone && onDone(final);
      return final;
    } catch (e) { setError(e.message); }
  }, [onDone]);
  return { job, error, start, running: job && ["queued", "running"].includes(job.status), setError };
}

export function JobBar({ job }) {
  if (!job) return null;
  const pct = Math.round((job.progress || 0) * 100);
  return (
    <div style={{ margin: "10px 0" }}>
      <div className="row small"><Badge s={job.status} /> <span className="muted">{job.message}</span><span className="spacer" /><span>{pct}%</span>
        {["queued", "running"].includes(job.status) && <button className="btn small" onClick={() => post(`/jobs/${job.id}/cancel`)}>Cancel</button>}
      </div>
      <div className="progress" style={{ marginTop: 6 }}><div style={{ width: `${pct}%` }} /></div>
      {job.error && <div className="alert err" style={{ marginTop: 8 }}>{job.error}</div>}
    </div>
  );
}

export function useLoad(path, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const reload = useCallback(() => {
    if (!path) return;
    get(path).then((d) => { setData(d); setError(null); }).catch((e) => setError(e.message));
  }, [path]);
  useEffect(() => { reload(); }, [reload, ...deps]); // eslint-disable-line
  return [data, reload, error, setData];
}

/** Project selector shared by all production sections. */
export function ProjectPicker() {
  const { projectId, setProjectId, projectsList, reloadProjects } = useApp();
  return (
    <div className="row">
      <select value={projectId || ""} onChange={(e) => setProjectId(e.target.value)} style={{ minWidth: 320 }}>
        <option value="">— choose a video project —</option>
        {(projectsList || []).map((p) => <option key={p.id} value={p.id}>{p.title} · {p.format} · {p.status.replaceAll("_", " ")}</option>)}
      </select>
      <button className="btn small" onClick={reloadProjects}>Refresh</button>
    </div>
  );
}

export const STAGES = ["research", "script", "characters", "images", "video", "voice", "edit", "thumbnail", "seo", "review"];

/** Run one or more pipeline stages for the current project, with cost-approval handling. */
export function StageRunner({ project, stages, label, force = false, extra = {}, onDone, primary = true }) {
  const { reloadProjects } = useApp();
  const { job, error, start, running } = useJob(async (j) => { onDone && onDone(j); reloadProjects(); });
  const [estimate, setEstimate] = useState(null);
  const run = async () => {
    const res = await start(post(`/projects/${project.id}/run`, { stages, force: force ? stages : [], ...extra }));
    if (res && res.status === "needs_approval") setEstimate(res.result?.estimate);
  };
  return (
    <div>
      <button className={`btn ${primary ? "primary" : ""}`} disabled={!project || running} onClick={run}>{running ? "Working…" : label}</button>
      <JobBar job={job} />
      <ErrorBox error={error} />
      {estimate && <CostApproval project={project} estimate={estimate} onApproved={() => { setEstimate(null); run(); }} onClose={() => setEstimate(null)} />}
    </div>
  );
}

export function CostApproval({ project, estimate, onApproved, onClose }) {
  const [err, setErr] = useState(null);
  return (
    <Modal title="Approve estimated API cost" onClose={onClose} actions={<>
      <button className="btn" onClick={onClose}>Not now</button>
      <button className="btn primary" onClick={async () => { try { await post(`/projects/${project.id}/approve-cost`, { amount: estimate.total_usd }); onApproved(); } catch (e) { setErr(e.message); } }}>
        Approve up to {usd(estimate.total_usd)}</button></>}>
      <p className="muted small">Paid providers are selected. Nothing is charged until you approve. These are estimates; check each provider's pricing.</p>
      <table><thead><tr><th>Stage</th><th>Provider</th><th>Units</th><th>Est.</th></tr></thead><tbody>
        {estimate.items.map((i, k) => <tr key={k}><td>{i.stage}</td><td>{i.provider}</td><td>{i.units} {i.unit}</td><td>{i.free ? "free" : usd(i.usd)}</td></tr>)}
      </tbody></table>
      <p><b>Total: {usd(estimate.total_usd)}</b>{estimate.over_budget && <span className="badge err" style={{ marginLeft: 8 }}>exceeds monthly budget</span>}</p>
      <ErrorBox error={err} />
    </Modal>
  );
}

export function Events({ events }) {
  if (!events?.length) return <div className="muted small">No activity yet.</div>;
  return (
    <table><tbody>{events.filter((e) => e.level !== "debug").slice(0, 60).map((e) => (
      <tr key={e.id}><td className="small muted" style={{ whiteSpace: "nowrap" }}>{fmtTime(e.ts)}</td><td><Badge s={e.level}>{e.stage}</Badge></td><td className="small">{e.message}</td></tr>
    ))}</tbody></table>
  );
}

export function NeedProject({ children }) {
  const { project } = useApp();
  if (!project) return <Card><p className="muted">Choose a video project above, or create one in <b>AI Topic Research</b> (or click <b>Create today's video</b>).</p></Card>;
  return children;
}
