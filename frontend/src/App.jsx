import React, { useCallback, useEffect, useState } from "react";
import { get, post, usd, isLocal } from "./api.js";
import { AppCtx, JobBar, Modal, useJob, ErrorBox } from "./components.jsx";
import { Overview, ChannelSettings, Research, ScriptGen } from "./sections1.jsx";
import { Characters, Images, VideoGen, Voice, Editor } from "./sections2.jsx";
import { Thumbnail, SEO, Upload, Schedule, Analytics, ApiSettings, History } from "./sections3.jsx";

const SECTIONS = [
  ["overview", "Overview", Overview], ["channel", "Channel Settings", ChannelSettings],
  ["research", "AI Topic Research", Research], ["script", "Script Generator", ScriptGen],
  ["characters", "Character Library", Characters], ["images", "Image Generation", Images],
  ["video", "Video Generation", VideoGen], ["voice", "Voiceover Studio", Voice],
  ["editor", "Video Editor", Editor], ["thumbnail", "Thumbnail Studio", Thumbnail],
  ["seo", "SEO Manager", SEO], ["upload", "YouTube Upload Manager", Upload],
  ["schedule", "Publishing Schedule", Schedule], ["analytics", "Analytics", Analytics],
  ["api", "API Settings", ApiSettings], ["history", "Production History", History],
];

function TodayButton({ onStarted }) {
  const [open, setOpen] = useState(false);
  const [est, setEst] = useState(null);
  const [fmt, setFmt] = useState("short");
  const [hint, setHint] = useState("");
  const { job, error, start, running } = useJob(onStarted);
  useEffect(() => { if (open) post("/costs/estimate", {}).then(setEst).catch(() => {}); }, [open]);
  return (
    <>
      <button className="btn primary" disabled={running} onClick={() => setOpen(true)}>▶ Create today's video</button>
      {running || job ? <div style={{ minWidth: 280 }}><JobBar job={job} /></div> : null}
      <ErrorBox error={error} />
      {open && (
        <Modal title="CREATE TODAY'S VIDEO" onClose={() => setOpen(false)} actions={<>
          <button className="btn" onClick={() => setOpen(false)}>Cancel</button>
          <button className="btn primary" onClick={() => { setOpen(false); start(post("/today", { format: fmt, topic_hint: hint })); }}>Start</button></>}>
          <p className="small muted">Finds a topic → writes the script → creates scenes → generates visuals → voices → edits → thumbnail → SEO, then
            stops for your review. Nothing is uploaded until you approve it.</p>
          <div className="grid g2">
            <label className="f">Format<select value={fmt} onChange={(e) => setFmt(e.target.value)}><option value="short">Short (9:16)</option><option value="long">Long (16:9)</option></select></label>
            <label className="f">Topic hint (optional)<input value={hint} onChange={(e) => setHint(e.target.value)} placeholder="e.g. cats vs. robot vacuum" /></label>
          </div>
          {est && <div className={`alert ${est.free ? "ok" : "warn"}`}>
            Estimated cost with current providers: <b>{est.free ? "FREE" : usd(est.total_usd)}</b> ({est.providers.image} images · {est.providers.video} video · {est.providers.tts} voice · {est.llm_model}).
            {!est.free && " The run pauses for your approval before any paid call."}</div>}
        </Modal>
      )}
    </>
  );
}

export default function App() {
  const [section, setSection] = useState(() => (location.hash || "#overview").slice(1));
  const [projectsList, setProjectsList] = useState([]);
  const [projectId, setProjectIdState] = useState(() => { try { return localStorage.getItem("ytauto.project") || ""; } catch { return ""; } });
  const [project, setProject] = useState(null);

  const setProjectId = (id) => { setProjectIdState(id); try { localStorage.setItem("ytauto.project", id); } catch { /* ignore */ } };
  const reloadProjects = useCallback(() => { get("/projects").then(setProjectsList).catch(() => {}); }, []);
  const reloadProject = useCallback(() => {
    if (!projectId) { setProject(null); return; }
    get(`/projects/${projectId}`).then(setProject).catch(() => { setProject(null); });
  }, [projectId]);

  useEffect(() => { reloadProjects(); }, [reloadProjects]);
  useEffect(() => { reloadProject(); }, [reloadProject]);
  useEffect(() => { const t = setInterval(() => { reloadProjects(); reloadProject(); }, 5000); return () => clearInterval(t); }, [reloadProjects, reloadProject]);
  useEffect(() => { const f = () => setSection((location.hash || "#overview").slice(1)); window.addEventListener("hashchange", f); return () => window.removeEventListener("hashchange", f); }, []);

  const go = (id) => { location.hash = id; setSection(id); window.scrollTo(0, 0); };
  const current = SECTIONS.find((s) => s[0] === section) || SECTIONS[0];
  const Comp = current[2];
  const ctx = { projectId, setProjectId, project, reloadProject, projectsList, reloadProjects, go };

  return (
    <AppCtx.Provider value={ctx}>
      <div className="layout">
        <aside className="sidebar">
          <div className="logo"><div className="mark">▶</div><div>AI YouTube<br /><span className="muted small">Automation Pro</span></div></div>
          <nav className="nav">
            {SECTIONS.map(([id, name], i) => (
              <button key={id} className={current[0] === id ? "active" : ""} onClick={() => go(id)}><span className="num">{i + 1}</span>{name}</button>
            ))}
          </nav>
          {!isLocal() && <div style={{ padding: "16px 10px" }}><a className="btn small" href="/logout">Sign out</a></div>}
        </aside>
        <main className="main">
          <div className="topbar">
            <div><h1>{current[1]}</h1><div className="sub">{project ? <>Project: <b>{project.title}</b> · {project.format} · {project.row?.status?.replaceAll("_", " ")}</> : "Original family-friendly AI animated comedy"}</div></div>
            <div className="row"><TodayButton onStarted={(j) => { reloadProjects(); if (j?.result?.project) { setProjectId(j.result.project); go("editor"); } }} /></div>
          </div>
          <Comp />
        </main>
      </div>
    </AppCtx.Provider>
  );
}
