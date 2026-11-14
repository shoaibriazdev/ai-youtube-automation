import React, { useEffect, useState } from "react";
import { del, fileUrl, fmtTime, get, post, put, usd, isLocal } from "./api.js";
import { Badge, Card, ErrorBox, Events, Field, JobBar, Modal, NeedProject, ProjectPicker, StageRunner, useApp, useJob, useLoad } from "./components.jsx";
import { Pipeline } from "./sections2.jsx";

/* ---------------- 10. Thumbnail Studio ---------------- */
export function Thumbnail() {
  const { project, reloadProject } = useApp();
  const [text, setText] = useState("");
  const [style, setStyle] = useState("pop");
  useEffect(() => { setText(project?.thumbnail?.text || project?.seo?.thumbnail_text || ""); }, [project?.id]);
  const t = project?.thumbnail;
  return (
    <>
      <Card title="Project"><ProjectPicker /></Card>
      <NeedProject>{project && <div className="grid g2">
        <Card title="Design">
          <Field label="Thumbnail text (max 3 words — must not repeat the title)"><input value={text} onChange={(e) => setText(e.target.value)} /></Field>
          <Field label="Style"><select value={style} onChange={(e) => setStyle(e.target.value)}><option value="pop">Pop (yellow on black)</option><option value="clean">Clean (white)</option><option value="shock">Shock (red outline)</option></select></Field>
          <StageRunner project={project} stages={["thumbnail"]} extra={{ thumbnail_text: text, thumbnail_style: style }} label="Generate thumbnail" onDone={reloadProject} />
          <p className="small muted">Background = the dedicated thumbnail image from the image step (or the hook scene). Output: 1280×720 JPG under YouTube's 2 MB limit + PNG.</p>
        </Card>
        <Card title="Preview">
          {t ? <>
            <img src={fileUrl(project.id, t.jpg)} style={{ width: "100%", borderRadius: 10 }} alt="thumbnail" />
            <div className="row small" style={{ marginTop: 6 }}><span>{t.size_kb} KB</span><a href={fileUrl(project.id, t.jpg)} download>JPG</a><a href={fileUrl(project.id, t.png)} download>PNG</a>
              <img src={fileUrl(project.id, t.jpg)} style={{ width: 168, borderRadius: 6, marginLeft: "auto" }} title="feed size" alt="feed size" /></div>
            {t.warnings?.map((w, k) => <div key={k} className="alert warn">{w}</div>)}
            {t.lint && <><h3>Title + thumbnail pairing (title.py) — {t.lint.score}/100</h3>
              {t.lint.issues.map((i, k) => <div key={k} className="small">✗ <b>{i.kind}</b> {i.message}</div>)}
              {t.lint.good.map((g, k) => <div key={k} className="small muted">✓ {g}</div>)}</>}
          </> : <p className="muted">No thumbnail yet.</p>}
        </Card></div>}
      </NeedProject>
    </>
  );
}

/* ---------------- 11. SEO Manager ---------------- */
export function SEO() {
  const { project, reloadProject } = useApp();
  const [seo, setSeo] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { setSeo(project?.seo ? { ...project.seo } : null); }, [project?.id, project?.stages?.seo?.done]);
  const save = async () => { setErr(null); try { await put(`/projects/${project.id}/seo`, { ...seo, tags: typeof seo.tags === "string" ? seo.tags.split(",").map((x) => x.trim()).filter(Boolean) : seo.tags }); setMsg("Saved"); reloadProject(); setTimeout(() => setMsg(null), 2000); } catch (e) { setErr(e.message); } };
  return (
    <>
      <Card title="Project"><ProjectPicker /></Card>
      <NeedProject>{project && <>
        <Card title="Generate SEO package"><StageRunner project={project} stages={["seo"]} label={seo ? "Regenerate SEO" : "Generate SEO"} onDone={reloadProject} />
          <p className="small muted">Titles are linted with the original title.py; tags capped at YouTube's 500 characters; chapters only when YouTube would actually render them.</p></Card>
        {seo && <div className="grid g2">
          <Card title="Metadata" right={<><button className="btn primary small" onClick={save}>Save</button>{msg && <span className="badge ok">{msg}</span>}</>}>
            <ErrorBox error={err} />
            <Field label={`Title (${(seo.title || "").length}/100)`}><input value={seo.title} onChange={(e) => setSeo({ ...seo, title: e.target.value })} /></Field>
            <Field label="Description"><textarea style={{ minHeight: 220 }} value={seo.description} onChange={(e) => setSeo({ ...seo, description: e.target.value })} /></Field>
            <Field label="Tags (comma separated)"><input value={Array.isArray(seo.tags) ? seo.tags.join(", ") : seo.tags} onChange={(e) => setSeo({ ...seo, tags: e.target.value })} /></Field>
            <div className="kv"><div>Hashtags</div><div>{(seo.hashtags || []).join(" ")}</div><div>Category</div><div>{seo.category_name} ({seo.category_id})</div>
              <div>Made for kids</div><div>{seo.made_for_kids ? "yes" : "no"} <span className="small muted">— set in Channel Settings</span></div>
              <div>Synthetic media flag</div><div>{seo.contains_synthetic_media ? "yes" : "no"}</div><div>Generated by</div><div>{seo.source}</div></div>
            <p className="small muted">{seo.audience_note}</p>
          </Card>
          <Card title="Title options (ranked by title.py)">
            <table><tbody>{(seo.title_options || []).map((t, k) => (
              <tr key={k}><td className="score">{t.score}</td><td>{t.title}<div className="small muted">{t.issues.map((i) => i.kind).join(", ") || "no issues"}</div></td><td><button className="btn small" onClick={() => setSeo({ ...seo, title: t.title })}>Use</button></td></tr>))}</tbody></table>
            <h3>Chapters</h3>
            {seo.chapters?.valid ? seo.chapters.chapters.map((c) => <div key={c.label} className="mono">{c.label} {c.title}</div>) : <p className="small muted">{seo.chapters?.reason}</p>}
            <h3>Query check</h3>
            {(seo.query_check || []).map((q) => <div key={q.query} className="small">{q.query}: {q.covered}/{q.of} words in title+hook {q.missing.length ? <span className="muted">(missing: {q.missing.join(", ")})</span> : "✓"}</div>)}
          </Card></div>}
      </>}</NeedProject>
    </>
  );
}

/* ---------------- 12. YouTube Upload Manager ---------------- */
function ClientSecretPaste({ reload, web }) {
  const [txt, setTxt] = useState("");
  const [err, setErr] = useState(null);
  const [ok, setOk] = useState(null);
  return (
    <details style={{ margin: "10px 0" }}>
      <summary className="small"><b>Upload</b> or paste the OAuth client JSON {web ? "(type: Web application)" : "(type: Desktop app)"}</summary>
      {web && <p className="small muted">Authorized redirect URI to add in Google Cloud: <span className="mono">{location.origin}/api/youtube/oauth/callback</span></p>}
      <div className="row" style={{ margin: "8px 0" }}>
        <label className="btn primary small" style={{ cursor: "pointer" }}>📁 Choose JSON file
          <input type="file" accept=".json,application/json" style={{ display: "none" }} onChange={async (e) => {
            const f = e.target.files?.[0]; if (!f) return;
            setErr(null); setOk(null);
            try { const r = await post("/youtube/client-secret", JSON.parse(await f.text())); setOk(`Saved (${r.type} client) — now click Connect YouTube`); reload(); }
            catch (ex) { setErr(ex instanceof SyntaxError ? "That file is not valid JSON." : ex.message); }
            e.target.value = "";
          }} /></label>
        <span className="small muted">or paste its contents below</span>
      </div>
      <textarea placeholder='{"web": {"client_id": "...", "client_secret": "...", ...}}' value={txt} onChange={(e) => setTxt(e.target.value)} />
      <button className="btn small" style={{ marginTop: 6 }} onClick={async () => {
        setErr(null); setOk(null);
        try { const r = await post("/youtube/client-secret", JSON.parse(txt)); setOk(`Saved (${r.type} client)`); setTxt(""); reload(); }
        catch (e) { setErr(e instanceof SyntaxError ? "That is not valid JSON." : e.message); }
      }}>Save client</button>{ok && <span className="badge ok" style={{ marginLeft: 8 }}>{ok}</span>}
      <ErrorBox error={err} />
    </details>
  );
}

function YouTubeConnect({ status, reload }) {
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  if (!status) return null;
  const web = !isLocal();
  const connect = async () => {
    if (web) { location.href = "/api/youtube/oauth/start"; return; }
    setErr(null);
    try {
      const r = await post("/youtube/connect"); setMsg(r.message);
      const t = setInterval(async () => { const s = await get("/youtube/status"); if (!s.oauth_in_progress) { clearInterval(t); reload(); setMsg(null); } }, 2500);
    } catch (e) { setErr(e.message); }
  };
  return (
    <>
      {!status.client_secrets_found && <div className="alert warn">No OAuth client yet. Follow <b>{web ? "docs/DEPLOY.md" : "docs/YOUTUBE_OAUTH.md"}</b>: Google Cloud project → enable YouTube Data API v3 → OAuth client ID of type <b>{web ? "Web application" : "Desktop app"}</b> → download the JSON and paste it below.</div>}
      {web && status.client_type === "desktop" && <div className="alert warn">The saved client is a Desktop client. Online sign-in needs a <b>Web application</b> client — paste one below.</div>}
      {status.connected ? <div className="row"><Badge s="done">connected</Badge><b>{status.channel?.title}</b><span className="small muted">{status.channel?.subscribers} subscribers · {status.channel?.videos} videos</span><span className="spacer" />
        <button className="btn small danger" onClick={async () => { await post("/youtube/disconnect"); reload(); }}>Disconnect</button></div>
        : <div className="row"><Badge s="warning">not connected</Badge><button className="btn primary" disabled={!status.client_secrets_found} onClick={connect}>Connect YouTube</button>
          {status.oauth_in_progress && <span className="small muted">Waiting for you to approve in the browser…</span>}</div>}
      <ClientSecretPaste reload={reload} web={web} />
      {msg && <div className="alert">{msg}</div>}<ErrorBox error={err || status.last_oauth_error || status.error} />
      <p className="small muted">The token is stored on this server in the data folder (never in source code). Scopes: upload, read-only channel, read-only analytics.</p>
    </>
  );
}

export function Upload() {
  const { project, reloadProject, reloadProjects } = useApp();
  const [status, reloadStatus] = useLoad("/youtube/status");
  const [hist, reloadHist] = useLoad("/uploads");
  const [privacy, setPrivacy] = useState("private");
  const [aspect, setAspect] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const { job, error, start, running } = useJob(() => { reloadHist(); reloadProject(); reloadProjects(); });
  const outs = project?.render?.outputs || {};
  const doUpload = (confirmPublic) => start(post(`/projects/${project.id}/upload`, { privacy, aspect: aspect || undefined, confirm_public: confirmPublic }));
  return (
    <>
      <Card title="YouTube account"><YouTubeConnect status={status} reload={reloadStatus} /></Card>
      <Card title="Upload a video"><ProjectPicker />
        <NeedProject>{project && <div style={{ marginTop: 12 }}>
          <div className="kv"><div>Status</div><div><Badge s={project.row?.status} /> {project.row?.approved ? <Badge s="approved">approved</Badge> : <Badge s="warning">not approved</Badge>}</div>
            <div>Title</div><div>{project.seo?.title || <span className="muted">run SEO first</span>}</div>
            <div>Thumbnail</div><div>{project.thumbnail ? "ready" : <span className="muted">none</span>}</div>
            <div>YouTube</div><div>{project.youtube ? <a href={project.youtube.url} target="_blank" rel="noreferrer">{project.youtube.url}</a> : "not uploaded"}</div></div>
          {!project.row?.approved && <div className="alert warn" style={{ marginTop: 10 }}>Watch the video in the <a href="#editor">Video Editor</a> and approve it first. Uploads are blocked until you do.</div>}
          <div className="row" style={{ marginTop: 12 }}>
            <select value={privacy} onChange={(e) => setPrivacy(e.target.value)} style={{ maxWidth: 200 }}><option value="private">Private (default)</option><option value="unlisted">Unlisted</option><option value="public">Public</option></select>
            {Object.keys(outs).length > 1 && <select value={aspect} onChange={(e) => setAspect(e.target.value)} style={{ maxWidth: 180 }}><option value="">primary format</option>{Object.keys(outs).map((a) => <option key={a}>{a}</option>)}</select>}
            <button className="btn primary" disabled={running || !project.row?.approved || !status?.connected || !project.seo} onClick={() => privacy === "public" ? setConfirmOpen(true) : doUpload(false)}>{running ? "Uploading…" : `Upload as ${privacy}`}</button>
          </div>
          <JobBar job={job} /><ErrorBox error={error} />
        </div>}</NeedProject>
      </Card>
      {confirmOpen && <Modal title="Publish publicly?" onClose={() => setConfirmOpen(false)} actions={<><button className="btn" onClick={() => setConfirmOpen(false)}>Cancel</button>
        <button className="btn primary" disabled={typed !== "PUBLISH"} onClick={() => { setConfirmOpen(false); setTyped(""); doUpload(true); }}>Publish now</button></>}>
        <p>The video will be visible to everyone immediately. Type <b>PUBLISH</b> to confirm.</p><input value={typed} onChange={(e) => setTyped(e.target.value)} /></Modal>}
      <Card title="Upload history" right={<button className="btn small" onClick={reloadHist}>Refresh</button>}>
        <table><thead><tr><th>When</th><th>Title</th><th>Privacy</th><th>Status</th><th>Thumbnail</th><th>Link / error</th></tr></thead><tbody>
          {(hist || []).map((u) => <tr key={u.id}><td className="small">{fmtTime(u.ts)}</td><td>{u.title}</td><td>{u.privacy}{u.publish_at && <div className="small muted">→ {u.publish_at}</div>}</td><td><Badge s={u.status} /></td><td className="small">{u.thumbnail_status}</td>
            <td className="small">{u.url ? <a href={u.url} target="_blank" rel="noreferrer">{u.video_id}</a> : <span style={{ color: "var(--err)" }}>{u.error}</span>}</td></tr>)}
        </tbody></table>
      </Card>
    </>
  );
}

/* ---------------- 13. Publishing Schedule ---------------- */
function localIsoWithOffset(dtLocal) {
  const d = new Date(dtLocal);
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const pad = (n) => String(Math.floor(Math.abs(n))).padStart(2, "0");
  return `${dtLocal}:00${sign}${pad(off / 60)}:${pad(off % 60)}`;
}

export function AutopilotCard() {
  const [st, reload] = useLoad("/autopilot");
  const [cfg, setCfg] = useState(null);
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const { job, error, start, running } = useJob(reload);
  useEffect(() => { if (st) setCfg(st); }, [st]);
  if (!cfg) return <Card title="Autopilot">Loading…</Card>;
  const save = async (patch = {}) => {
    setErr(null);
    try { const r = await put("/autopilot", { ...cfg, ...patch }); setCfg(r); setMsg("Saved"); reload(); setTimeout(() => setMsg(null), 2000); }
    catch (e) { setErr(e.message); }
  };
  const lr = st?.last_result;
  return (
    <Card title="🤖 Autopilot — daily video, created and uploaded automatically" right={cfg.enabled ? <Badge s="done">ON</Badge> : <Badge s="warning">OFF</Badge>}>
      <p className="small muted">Every day at the chosen time it finds a topic, writes, generates, edits, makes the thumbnail and SEO, then uploads.
        Turning it on is your standing approval for these videos. It never spends more than the limit below (default $0 = free providers only).</p>
      <div className="grid g4">
        <Field label="Run every day at"><input type="time" value={cfg.run_at} onChange={(e) => setCfg({ ...cfg, run_at: e.target.value })} /></Field>
        <Field label="Timezone"><select value={cfg.timezone} onChange={(e) => setCfg({ ...cfg, timezone: e.target.value })}>
          {["Asia/Karachi", "Asia/Dubai", "Asia/Kolkata", "Europe/London", "America/New_York", "America/Chicago", "America/Los_Angeles", "UTC"].map((t) => <option key={t}>{t}</option>)}</select></Field>
        <Field label="Format"><select value={cfg.format} onChange={(e) => setCfg({ ...cfg, format: e.target.value })}><option value="short">Short 9:16</option><option value="long">Long 16:9</option></select></Field>
        <Field label="Max spend per video (USD)"><input type="number" min="0" step="0.05" value={cfg.max_cost_usd} onChange={(e) => setCfg({ ...cfg, max_cost_usd: +e.target.value })} /></Field>
      </div>
      <div className="grid g2">
        <Field label="After the video is made">
          <select value={cfg.upload ? cfg.privacy_mode : "none"} onChange={(e) => e.target.value === "none" ? setCfg({ ...cfg, upload: false }) : setCfg({ ...cfg, upload: true, privacy_mode: e.target.value })}>
            <option value="none">Don't upload (I review in the dashboard)</option>
            <option value="private">Upload as PRIVATE (safe default)</option>
            <option value="scheduled">Upload and auto-publish at the channel's best hour</option>
            <option value="public">Upload and publish PUBLIC immediately</option>
          </select></Field>
        {cfg.upload && cfg.privacy_mode !== "private" && <label className="row small" style={{ marginTop: 18 }}>
          <input type="checkbox" checked={!!cfg.public_confirmed} onChange={(e) => setCfg({ ...cfg, public_confirmed: e.target.checked })} />
          I understand these videos will become public without me watching them first.</label>}
      </div>
      <div className="row">
        <button className="btn" onClick={() => save()}>Save</button>
        {cfg.enabled ? <button className="btn danger" onClick={() => save({ enabled: false })}>Turn OFF</button>
          : <button className="btn primary" onClick={() => save({ enabled: true })}>Turn ON</button>}
        <button className="btn" disabled={running} onClick={() => start(post("/autopilot/run"))}>Run once now</button>
        {msg && <span className="badge ok">{msg}</span>}
        <span className="spacer" />
        {st?.next_run && <span className="small muted">Next run: {new Date(st.next_run).toLocaleString()}</span>}
      </div>
      <JobBar job={job} /><ErrorBox error={err || error} />
      {lr && <div className={`alert ${lr.ok ? "ok" : "warn"}`} style={{ marginTop: 10 }}>Last run {fmtTime(lr.time)}: {lr.ok ? "video created" : lr.error || "problem"}{lr.upload ? ` · upload: ${typeof lr.upload === "string" ? lr.upload : "done"}` : ""}</div>}
      <p className="small muted">Autopilot runs while the server is running (it always is on the VPS). Uploading needs YouTube connected in the Upload Manager.</p>
    </Card>
  );
}

export function Schedule() {
  const [d, reload] = useLoad("/schedule");
  const [pick, setPick] = useState({ pid: "", when: "" });
  const [typed, setTyped] = useState("");
  const [err, setErr] = useState(null);
  const { projectsList } = useApp();
  const { job, error, start, running } = useJob(reload);
  const target = (projectsList || []).find((p) => p.id === pick.pid);
  const submit = async () => {
    setErr(null);
    const when = localIsoWithOffset(pick.when);
    if (["uploaded", "scheduled"].includes(target?.status)) {
      try { await post(`/projects/${pick.pid}/schedule`, { publish_at: when, confirm_public: true }); reload(); } catch (e) { setErr(e.message); }
    } else start(post(`/projects/${pick.pid}/upload`, { privacy: "private", publish_at: when, confirm_public: true }));
    setTyped("");
  };
  const eligible = (projectsList || []).filter((p) => ["approved", "uploaded", "scheduled"].includes(p.status));
  return (
    <>
      <AutopilotCard />
      <Card title="Schedule a video">
        <p className="small muted">Scheduled videos upload as <b>private</b> and YouTube makes them public at the chosen time. Only approved videos can be scheduled. Your channel's best hour: {d?.channel?.best_publish_hour}:00 ({d?.channel?.upload_timezone}).</p>
        <div className="grid g3">
          <Field label="Video"><select value={pick.pid} onChange={(e) => setPick({ ...pick, pid: e.target.value })}><option value="">—</option>{eligible.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.status})</option>)}</select></Field>
          <Field label="Publish at (your local time)"><input type="datetime-local" value={pick.when} onChange={(e) => setPick({ ...pick, when: e.target.value })} /></Field>
          <Field label="Type SCHEDULE to confirm it goes public then"><input value={typed} onChange={(e) => setTyped(e.target.value)} /></Field>
        </div>
        <button className="btn primary" disabled={!pick.pid || !pick.when || typed !== "SCHEDULE" || running} onClick={submit}>Schedule</button>
        <JobBar job={job} /><ErrorBox error={error || err} />
      </Card>
      <Card title="Scheduled">
        <table><thead><tr><th>Publish at (UTC)</th><th>Title</th><th>Status</th><th>Link</th></tr></thead><tbody>
          {(d?.scheduled || []).map((u) => <tr key={u.id}><td className="mono">{u.publish_at}</td><td>{u.title}</td><td><Badge s={u.status} /></td><td>{u.url && <a href={u.url} target="_blank" rel="noreferrer">{u.video_id}</a>}</td></tr>)}
        </tbody></table>
        {!d?.scheduled?.length && <p className="muted">Nothing scheduled.</p>}
      </Card>
      <Card title="Ready / approved, not yet published">
        <table><tbody>{(d?.ready || []).map((p) => <tr key={p.id}><td>{p.title}</td><td><Badge s={p.status} /></td><td className="small muted">{fmtTime(p.created)}</td></tr>)}</tbody></table>
      </Card>
    </>
  );
}

/* ---------------- 14. Analytics ---------------- */
export function Analytics() {
  const [d, reload, err] = useLoad("/analytics");
  if (err) return <ErrorBox error={err} />;
  if (!d) return <Card>Loading analytics…</Card>;
  if (!d.connected) return <Card title="Analytics"><p className="muted">{d.message || d.error}</p></Card>;
  const rows = d.report?.rows || [];
  const max = Math.max(1, ...rows.map((r) => r.views || 0));
  return (
    <>
      <div className="grid g4">
        <Card className="stat"><div className="l">Subscribers</div><div className="v">{Number(d.channel?.subscribers || 0).toLocaleString()}</div></Card>
        <Card className="stat"><div className="l">Total views</div><div className="v">{Number(d.channel?.views || 0).toLocaleString()}</div></Card>
        <Card className="stat"><div className="l">Views (28d)</div><div className="v">{Number(d.report?.totals?.views || 0).toLocaleString()}</div></Card>
        <Card className="stat"><div className="l">Avg view duration (28d)</div><div className="v">{d.report?.totals?.averageViewDuration ?? "—"}s</div></Card>
      </div>
      <Card title="Daily views (last 28 days)" right={<button className="btn small" onClick={reload}>Refresh</button>}>
        {d.report_error ? <div className="alert warn">{d.report_error}</div> : <div className="bars">{rows.map((r) => <div key={r.day} title={`${r.day}: ${r.views} views`} style={{ height: `${(r.views / max) * 100}%` }} />)}</div>}
      </Card>
      <Card title="Videos uploaded by this platform">
        <table><thead><tr><th>Title</th><th>Privacy</th><th>Views</th><th>Likes</th><th>Comments</th><th>Published</th></tr></thead><tbody>
          {(d.videos || []).map((v) => <tr key={v.video_id}><td>{v.title}</td><td>{v.privacy}</td><td>{v.views.toLocaleString()}</td><td>{v.likes}</td><td>{v.comments}</td><td className="small">{v.published}</td></tr>)}
        </tbody></table>
        <p className="small muted">For the second-by-second retention read, export the retention CSV from YouTube Studio and use the <b>/yt-retention</b> skill.</p>
      </Card>
    </>
  );
}

/* ---------------- 15. API Settings ---------------- */
export function ApiSettings() {
  const [s, reload] = useLoad("/secrets");
  const [settings, reloadSettings] = useLoad("/settings");
  const [costs, reloadCosts] = useLoad("/costs");
  const [vals, setVals] = useState({});
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const [budget, setBudget] = useState(null);
  useEffect(() => { if (settings) setBudget(settings.costs); }, [settings]);
  const save = async () => {
    setErr(null);
    try { const r = await put("/secrets", vals); setMsg(`Saved ${r.written.join(", ")} to .env`); setVals({}); reload(); reloadCosts(); } catch (e) { setErr(e.message); }
  };
  const setProv = async (k, v) => { await put("/settings/providers", { ...settings.providers, [k]: v }); reloadSettings(); reloadCosts(); };
  return (
    <>
      <Card title="Providers (choose free or paid)">
        {settings && <div className="grid g4">{["llm", "image", "video", "tts"].map((k) => (
          <Field key={k} label={{ llm: "Script / ideas / SEO writer", image: "Images", video: "Video clips", tts: "Voices" }[k]}>
            <select value={settings.providers[k]} onChange={(e) => setProv(k, e.target.value)}>
              {settings.options[k].map((p) => <option key={p} value={p}>{p}{(settings.options.free_notes[p] || p === "auto") ? (p === "auto" ? " (Claude if key set, else offline)" : " (free)") : " (paid)"}</option>)}</select></Field>))}</div>}
        {costs && <div className={`alert ${costs.estimate.free ? "ok" : "warn"}`}>Estimated cost per video with these providers: <b>{costs.estimate.free ? "FREE" : usd(costs.estimate.total_usd)}</b> · LLM: {costs.estimate.llm_model}.
          Paid runs always pause for your approval first. A Claude Pro/Max subscription does <b>not</b> include API credits — the Anthropic API is billed separately.</div>}
      </Card>
      <Card title="API keys (stored only in your local .env file)">
        {s && <>
          <table><thead><tr><th>Service</th><th>Status</th><th>New value</th><th>Notes</th></tr></thead><tbody>
            {s.secrets.map((k) => (
              <tr key={k.key}><td><b>{k.label}</b><div className="mono muted">{k.key}</div></td>
                <td>{k.configured ? <><Badge s="done">set</Badge> <span className="mono">{k.masked}</span></> : <Badge s="warning">missing</Badge>}<div className="small">{k.paid ? "paid" : "free"}</div></td>
                <td><input type="password" autoComplete="off" placeholder={k.configured ? "leave blank to keep" : "paste key"} value={vals[k.key] || ""} onChange={(e) => setVals({ ...vals, [k.key]: e.target.value })} /></td>
                <td className="small muted">{k.note} <a href={k.url} target="_blank" rel="noreferrer">Get key</a></td></tr>))}
            <tr><td><b>Claude model</b><div className="mono muted">ANTHROPIC_MODEL</div></td><td className="mono">{s.env.ANTHROPIC_MODEL}</td>
              <td><select value={vals.ANTHROPIC_MODEL || ""} onChange={(e) => setVals({ ...vals, ANTHROPIC_MODEL: e.target.value })}><option value="">(keep)</option><option>claude-opus-5-5</option><option>claude-sonnet-5-5</option><option>claude-haiku-5-5</option></select></td>
              <td className="small muted">Opus 5.5 = best quality ($4/$20 per M tokens). Sonnet 5.5 = cheaper ($2/$10). Haiku 5.5 = cheapest ($0.10/$0.50).</td></tr>
            <tr><td><b>Google OAuth client file</b><div className="mono muted">GOOGLE_CLIENT_SECRETS_FILE</div></td><td>{s.youtube.client_secrets_found ? <Badge s="done">found</Badge> : <Badge s="warning">missing</Badge>}</td>
              <td className="mono small">{s.youtube.client_secrets_path}</td><td className="small muted">Desktop-app OAuth client JSON. See docs/YOUTUBE_OAUTH.md.</td></tr>
          </tbody></table>
          <div className="row" style={{ marginTop: 10 }}><button className="btn primary" disabled={!Object.values(vals).some(Boolean)} onClick={save}>Save keys</button>{msg && <span className="badge ok">{msg}</span>}</div>
          <ErrorBox error={err} />
          <p className="small muted">Keys are written to <span className="mono">{s.env_file}</span> on this computer and never shown again in full. The dashboard only listens on localhost.</p>
        </>}
      </Card>
      <Card title="Budget & spend">
        {budget && <div className="row">
          <Field label="Monthly budget (USD)"><input type="number" min="0" step="1" value={budget.monthly_budget_usd} onChange={(e) => setBudget({ ...budget, monthly_budget_usd: +e.target.value })} /></Field>
          <Field label="Ask for approval above (USD per video)"><input type="number" min="0" step="0.01" value={budget.require_approval_above_usd} onChange={(e) => setBudget({ ...budget, require_approval_above_usd: +e.target.value })} /></Field>
          <button className="btn" onClick={async () => { await put("/settings/costs", budget); reloadSettings(); reloadCosts(); }}>Save</button></div>}
        {costs && <>
          <p>Spent (31 days): <b>{usd(costs.budget.month_spend_usd)}</b> of {usd(costs.budget.monthly_budget_usd)}</p>
          <h3>Price table used for estimates (edit in data/pricing.json)</h3>
          <div className="grid g4">{["image", "video", "tts"].map((k) => <div key={k}><b>{k}</b>{Object.entries(costs.pricing[k]).map(([p, v]) => <div key={p} className="small">{p}: {v ? usd(v) : "free"} {k === "video" ? "/s" : k === "tts" ? "/1k chars" : "/image"}</div>)}</div>)}
            <div><b>llm</b>{Object.entries(costs.pricing.llm).map(([m, v]) => <div key={m} className="small">{m}: ${v[0]}/${v[1]} per M</div>)}</div></div>
          <h3>Recent spend log</h3>
          <table><tbody>{costs.log.slice(0, 20).map((c) => <tr key={c.id}><td className="small">{fmtTime(c.ts)}</td><td>{c.provider}</td><td>{c.kind}</td><td>{usd(c.usd)}</td><td className="small muted">{c.note}</td></tr>)}</tbody></table>
        </>}
      </Card>
    </>
  );
}

/* ---------------- 16. Production History ---------------- */
export function History() {
  const { projectsList, reloadProjects, setProjectId, project, go, reloadProject } = useApp();
  const [filter, setFilter] = useState("");
  const list = (projectsList || []).filter((p) => !filter || p.status === filter);
  return (
    <>
      <Card title="All videos" right={<select value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 200 }}><option value="">all statuses</option>{["draft", "running", "awaiting_cost_approval", "ready_for_review", "approved", "uploaded", "scheduled", "failed"].map((s) => <option key={s} value={s}>{s.replaceAll("_", " ")}</option>)}</select>}>
        <table><thead><tr><th>Created</th><th>Title</th><th>Format</th><th>Status</th><th>Stage</th><th>Est. cost</th><th></th></tr></thead><tbody>
          {list.map((p) => <tr key={p.id} style={{ background: project?.id === p.id ? "var(--panel2)" : undefined }}>
            <td className="small">{fmtTime(p.created)}</td><td><b>{p.title}</b>{p.error && <div className="small" style={{ color: "var(--err)" }}>{p.error}</div>}</td><td>{p.format}</td><td><Badge s={p.status} /></td><td className="small">{p.stage}</td><td>{usd(p.est_cost)}</td>
            <td className="row"><button className="btn small" onClick={() => setProjectId(p.id)}>Details</button><button className="btn small" onClick={() => { setProjectId(p.id); go("editor"); }}>Open</button>
              <button className="btn small danger" onClick={async () => { if (confirm(`Delete "${p.title}" and all its files?`)) { await del(`/projects/${p.id}`); reloadProjects(); } }}>Delete</button></td></tr>)}
        </tbody></table>
      </Card>
      {project && <div className="grid g2">
        <Card title={`Pipeline · ${project.title}`}><Pipeline project={project} onDone={reloadProject} />
          <h3>Stage timings</h3>{Object.entries(project.stages || {}).map(([k, v]) => <div key={k} className="small">{k}: {v.seconds}s · {fmtTime(v.done)}</div>)}
          <h3>Files</h3>
          <div className="small">{Object.entries(project.render?.outputs || {}).map(([a, o]) => <div key={a}><a href={fileUrl(project.id, o.file)} download>{o.file}</a></div>)}
            {project.thumbnail && <div><a href={fileUrl(project.id, project.thumbnail.jpg)} download>{project.thumbnail.jpg}</a></div>}
            <div><a href={fileUrl(project.id, "script.md")} target="_blank" rel="noreferrer">script.md</a> · <a href={fileUrl(project.id, "project.json")} target="_blank" rel="noreferrer">project.json</a></div></div>
        </Card>
        <Card title="Event log (progress & errors)"><Events events={project.events} /></Card>
      </div>}
    </>
  );
}
