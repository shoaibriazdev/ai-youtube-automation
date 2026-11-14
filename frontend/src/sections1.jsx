import React, { useEffect, useState } from "react";
import { get, post, put, usd, fmtTime } from "./api.js";
import { Badge, Card, ErrorBox, Events, Field, JobBar, NeedProject, ProjectPicker, StageRunner, STAGES, useApp, useJob, useLoad, CostApproval } from "./components.jsx";

/* ---------------- 1. Overview ---------------- */
export function Overview() {
  const [d, reload, err] = useLoad("/overview");
  const { setProjectId, go } = useApp();
  useEffect(() => { const t = setInterval(reload, 6000); return () => clearInterval(t); }, [reload]);
  if (err) return <ErrorBox error={`Cannot reach the backend: ${err}`} />;
  if (!d) return <Card>Loading…</Card>;
  const c = d.counts || {};
  return (
    <>
      <div className="grid g4">
        <Card className="stat"><div className="l">Projects</div><div className="v">{d.total}</div></Card>
        <Card className="stat"><div className="l">Ready for review</div><div className="v">{(c.ready_for_review || 0) + (c.approved || 0)}</div></Card>
        <Card className="stat"><div className="l">Uploaded / scheduled</div><div className="v">{(c.uploaded || 0) + (c.scheduled || 0)}</div></Card>
        <Card className="stat"><div className="l">API spend (31 days)</div><div className="v">{usd(d.budget.month_spend_usd)}</div><div className="small muted">budget {usd(d.budget.monthly_budget_usd)}</div></Card>
      </div>
      <div className="grid g2">
        <Card title="System check" right={<button className="btn small" onClick={reload}>Re-check</button>}>
          <table><tbody>{d.doctor.checks.map((ch) => (
            <tr key={ch.name}><td>{ch.ok ? <Badge s="done">OK</Badge> : <Badge s={ch.required ? "failed" : "warning"}>{ch.required ? "FIX" : "optional"}</Badge>}</td><td>{ch.name}</td><td className="small muted">{ch.detail}</td></tr>
          ))}</tbody></table>
          <p className="small muted">Active providers: LLM {d.providers.llm} · images {d.providers.image} · video {d.providers.video} · voice {d.providers.tts}. Change them in <a href="#api">API Settings</a>.</p>
        </Card>
        <Card title="Recent projects">
          <table><tbody>{d.projects.map((p) => (
            <tr key={p.id} style={{ cursor: "pointer" }} onClick={() => { setProjectId(p.id); go("editor"); }}>
              <td>{p.title}<div className="small muted">{fmtTime(p.created)} · {p.format}</div></td><td><Badge s={p.status} /></td><td className="small muted">{p.stage}</td></tr>
          ))}</tbody></table>
          {!d.projects.length && <p className="muted">No videos yet. Click <b>Create today's video</b> (top right) — with the default free providers it costs nothing.</p>}
        </Card>
        <Card title="Background jobs">
          <table><tbody>{d.jobs.map((j) => (
            <tr key={j.id}><td className="small">{j.kind}</td><td><Badge s={j.status} /></td><td className="small muted">{Math.round((j.progress || 0) * 100)}% {j.message}{j.error && <div className="small" style={{ color: "var(--err)" }}>{j.error}</div>}</td></tr>
          ))}</tbody></table>
        </Card>
        <Card title="Activity & errors"><Events events={d.events} /></Card>
      </div>
    </>
  );
}

/* ---------------- 2. Channel Settings ---------------- */
export function ChannelSettings() {
  const [s, reload] = useLoad("/settings");
  const [ch, setCh] = useState(null);
  const [style, setStyle] = useState(null);
  const [msg, setMsg] = useState(null);
  useEffect(() => { if (s) { setCh(s.channel); setStyle(s.style); } }, [s]);
  if (!ch) return <Card>Loading…</Card>;
  const upd = (k, v) => setCh({ ...ch, [k]: v });
  const save = async () => { await put("/settings/channel", ch); await put("/settings/style", style); setMsg("Saved."); reload(); setTimeout(() => setMsg(null), 2500); };
  return (
    <div className="grid g2">
      <Card title="Channel profile">
        <Field label="Channel name"><input value={ch.name} onChange={(e) => upd("name", e.target.value)} /></Field>
        <Field label="Niche"><input value={ch.niche} onChange={(e) => upd("niche", e.target.value)} /></Field>
        <Field label="Target audience"><input value={ch.audience} onChange={(e) => upd("audience", e.target.value)} /></Field>
        <Field label="Tone"><input value={ch.tone} onChange={(e) => upd("tone", e.target.value)} /></Field>
        <Field label="Content themes (one per line)"><textarea value={ch.themes.join("\n")} onChange={(e) => upd("themes", e.target.value.split("\n").filter(Boolean))} /></Field>
      </Card>
      <Card title="Publishing defaults">
        <div className="grid g2">
          <Field label="Default format"><select value={ch.default_format} onChange={(e) => upd("default_format", e.target.value)}><option value="short">Short 9:16</option><option value="long">Long 16:9</option></select></Field>
          <Field label="Default upload privacy"><select value={ch.default_privacy} onChange={(e) => upd("default_privacy", e.target.value)}><option value="private">private</option><option value="unlisted">unlisted</option></select></Field>
          <Field label="Category"><select value={ch.category_id} onChange={(e) => upd("category_id", e.target.value)}>{Object.entries(s.options.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Language"><input value={ch.default_language} onChange={(e) => upd("default_language", e.target.value)} /></Field>
          <Field label="Timezone (for schedule)"><input value={ch.upload_timezone} onChange={(e) => upd("upload_timezone", e.target.value)} /></Field>
          <Field label="Best publish hour (local)"><input type="number" min="0" max="23" value={ch.best_publish_hour} onChange={(e) => upd("best_publish_hour", +e.target.value)} /></Field>
        </div>
        <label className="row"><input type="checkbox" checked={ch.made_for_kids} onChange={(e) => upd("made_for_kids", e.target.checked)} /> Made for kids (COPPA)</label>
        <p className="small muted">This is a legal declaration, not a style. Family-friendly comedy for a general audience is usually <b>not</b> "made for kids". If unsure, read YouTube's guidance.</p>
        <label className="row"><input type="checkbox" checked={ch.contains_synthetic_media} onChange={(e) => upd("contains_synthetic_media", e.target.checked)} /> Disclose altered/synthetic content</label>
        <p className="small muted">Sets YouTube's <span className="mono">containsSyntheticMedia</span> flag on upload.</p>
        <h3>Visual style (used in every image prompt)</h3>
        {style && <>
          <Field label="Art style"><textarea value={style.art_style} onChange={(e) => setStyle({ ...style, art_style: e.target.value })} /></Field>
          <Field label="Avoid"><input value={style.negative} onChange={(e) => setStyle({ ...style, negative: e.target.value })} /></Field></>}
        <div className="row"><button className="btn primary" onClick={save}>Save settings</button>{msg && <span className="badge ok">{msg}</span>}</div>
      </Card>
    </div>
  );
}

/* ---------------- 3. AI Topic Research ---------------- */
export function Research() {
  const { setProjectId, go, reloadProjects } = useApp();
  const [ideas, reloadIdeas] = useLoad("/ideas");
  const [opts, setOpts] = useState({ n: 10, format: "short", use_trends: true, topic_hint: "" });
  const [trends, setTrends] = useState(null);
  const [est, setEst] = useState(null);
  const { job, error, start, running } = useJob((j) => { reloadIdeas(); if (j.result) setTrends(j.result); });
  const [hooks, setHooks] = useState("");
  const [hookRes, setHookRes] = useState(null);
  useEffect(() => { post("/costs/estimate", { stages: ["research"] }).then(setEst).catch(() => {}); }, []);
  const create = async (idea) => { const p = await post("/projects", { idea_id: idea.id, format: idea.format }); reloadProjects(); setProjectId(p.id); go("script"); };
  return (
    <>
      <Card title="Generate original video ideas">
        <div className="grid g4">
          <Field label="How many"><input type="number" min="3" max="20" value={opts.n} onChange={(e) => setOpts({ ...opts, n: +e.target.value })} /></Field>
          <Field label="Format"><select value={opts.format} onChange={(e) => setOpts({ ...opts, format: e.target.value })}><option value="short">Short</option><option value="long">Long</option></select></Field>
          <Field label="Topic hint (optional)"><input value={opts.topic_hint} onChange={(e) => setOpts({ ...opts, topic_hint: e.target.value })} placeholder="e.g. back to school" /></Field>
          <Field label="Live YouTube trends"><label className="row"><input type="checkbox" checked={opts.use_trends} onChange={(e) => setOpts({ ...opts, use_trends: e.target.checked })} /> use YOUTUBE_API_KEY (free quota)</label></Field>
        </div>
        <div className="row">
          <button className="btn primary" disabled={running} onClick={() => {
            if (est && !est.free && !confirm(`This uses Claude and costs about ${usd(est.total_usd)}. Continue?`)) return;
            start(post("/ideas", opts));
          }}>{running ? "Researching…" : "Research & generate ideas"}</button>
          {est && <span className="small muted">Estimated cost: {est.free ? "free (offline writer)" : usd(est.total_usd) + " (" + est.llm_model + ")"}</span>}
        </div>
        <JobBar job={job} /><ErrorBox error={error} />
        {trends?.trend_error && <div className="alert warn">Trend lookup failed: {trends.trend_error}</div>}
        {trends?.trends && !trends.trends.available && <div className="alert">{trends.trends.note}</div>}
      </Card>
      {trends?.trends?.available && (
        <Card title="What's getting views in the niche (inspiration only — never copy)">
          <p className="small muted">Trending words: {trends.trends.keywords.join(", ")}</p>
          <table><thead><tr><th>Title</th><th>Channel</th><th>Views/day</th><th>×median</th><th>Formula</th></tr></thead><tbody>
            {trends.trends.videos.map((v) => <tr key={v.url}><td><a href={v.url} target="_blank" rel="noreferrer">{v.title}</a></td><td className="small">{v.channel}</td><td>{v.views_per_day.toLocaleString()}</td><td>{v.multiple}</td><td className="small">{v.formula}</td></tr>)}
          </tbody></table>
        </Card>)}
      <Card title={`Ideas (${ideas?.length || 0})`} right={<button className="btn small" onClick={reloadIdeas}>Refresh</button>}>
        <table><thead><tr><th>Score</th><th>Idea</th><th>Appeal</th><th>Feasible</th><th>Hook</th><th></th></tr></thead><tbody>
          {(ideas || []).map((i) => (
            <tr key={i.id} style={{ opacity: i.used ? 0.55 : 1 }}>
              <td className="score">{i.total_score}</td>
              <td><b>{i.title}</b><div className="small muted">{i.premise}</div><div className="small">Cast: {(i.characters || []).join(", ")} · {i.source}{i.used ? " · used" : ""}</div></td>
              <td>{i.appeal_score}</td><td>{i.feasibility_score}</td>
              <td className="small">{i.hook}<div><Badge s={i.hook_score?.band === "STRONG" ? "done" : i.hook_score?.band === "WEAK" ? "warning" : "info"}>{i.hook_score?.verdict} {i.hook_score?.band}</Badge></div></td>
              <td><button className="btn small primary" onClick={() => create(i)}>Make video</button></td>
            </tr>))}
        </tbody></table>
      </Card>
      <Card title="Hook tester (original hookscore panel)">
        <textarea placeholder="One hook per line" value={hooks} onChange={(e) => setHooks(e.target.value)} />
        <button className="btn" style={{ marginTop: 8 }} onClick={async () => setHookRes(await post("/hookscore", { hooks: hooks.split("\n") }))}>Score hooks</button>
        {hookRes && <table style={{ marginTop: 10 }}><tbody>{hookRes.sort((a, b) => b.verdict - a.verdict).map((h, k) => (
          <tr key={k}><td className="score">{h.verdict}</td><td><Badge s={h.band === "STRONG" ? "done" : h.band === "WEAK" ? "warning" : "info"}>{h.band}</Badge></td><td>{h.hook}<div className="small muted">{h.formula} · weakest: {h.weakest} · {Object.entries(h.properties).map(([k2, v]) => `${k2} ${v}`).join(" · ")}</div></td></tr>))}</tbody></table>}
      </Card>
    </>
  );
}

/* ---------------- 4. Script Generator ---------------- */
export function ScriptGen() {
  const { project, reloadProject } = useApp();
  const [script, setScript] = useState(null);
  const [notes, setNotes] = useState("");
  const [chars] = useLoad("/characters");
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { setScript(project?.script ? JSON.parse(JSON.stringify(project.script)) : null); }, [project?.id, project?.script?.title, project?.stages?.script?.done]);
  const updLine = (si, li, k, v) => { const s = { ...script }; s.scenes[si].dialogue[li][k] = v; setScript({ ...s }); };
  const updScene = (si, k, v) => { const s = { ...script }; s.scenes[si][k] = v; setScript({ ...s }); };
  const save = async () => { setErr(null); try { await put(`/projects/${project.id}/script`, script); setMsg("Saved — voiceover will be regenerated."); reloadProject(); } catch (e) { setErr(e.message); } };
  return (
    <>
      <Card title="Project"><ProjectPicker /></Card>
      <NeedProject>
        {project && <>
          <Card title="Write the script">
            {project.idea?.title && <p><b>Idea:</b> {project.idea.title} <span className="muted small">— {project.idea.premise}</span></p>}
            <Field label="Notes for the writer (optional)"><input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. make Biscuit the villain; end with a musical twist" /></Field>
            <StageRunner project={project} stages={project.idea?.title ? ["script"] : ["research", "script"]} force={!!project.script}
              label={project.script ? "Rewrite script" : "Generate script"} extra={{ notes }} onDone={reloadProject} />
          </Card>
          {script && <Card title={script.title} right={<><span className="small muted">~{script.estimated_seconds}s · {script.word_count} words · {script.source}</span><button className="btn primary small" onClick={save}>Save edits</button></>}>
            {msg && <div className="alert ok">{msg}</div>}<ErrorBox error={err} />
            <Field label="Title"><input value={script.title} onChange={(e) => setScript({ ...script, title: e.target.value })} /></Field>
            <h3>Hook options (scored)</h3>
            <table><tbody>{(script.hook_scores || []).map((h, k) => <tr key={k}><td className="score">{h.verdict}</td><td><Badge s={h.band === "STRONG" ? "done" : h.band === "WEAK" ? "warning" : "info"}>{h.band}</Badge></td><td>{h.hook}{h.hook === script.hook && <span className="badge ok" style={{ marginLeft: 6 }}>used</span>}</td></tr>)}</tbody></table>
            <h3>Scenes</h3>
            {script.scenes.map((s, si) => (
              <div className="scene" key={si}>
                <div className="row"><b>Scene {s.n}</b><span className="muted small">{s.setting}</span><span className="spacer" />{s.sfx?.map((x, k) => <span key={k} className="badge">SFX {x.name} @ {x.cue}</span>)}</div>
                <div className="grid g2" style={{ marginTop: 6 }}>
                  <Field label="Visual (image prompt)"><textarea value={s.visual} onChange={(e) => updScene(si, "visual", e.target.value)} /></Field>
                  <div><Field label="Camera"><input value={s.camera} onChange={(e) => updScene(si, "camera", e.target.value)} /></Field>
                    <Field label="On-screen text (≤3 words)"><input value={s.on_screen_text} onChange={(e) => updScene(si, "on_screen_text", e.target.value)} /></Field></div>
                </div>
                {s.dialogue.map((d, li) => (
                  <div className="line" key={li}>
                    <select value={d.character} onChange={(e) => updLine(si, li, "character", e.target.value)}>{(chars || []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
                    <input value={d.emotion} title={d.delivery} onChange={(e) => updLine(si, li, "emotion", e.target.value)} />
                    <input value={d.line} onChange={(e) => updLine(si, li, "line", e.target.value)} />
                  </div>))}
              </div>))}
            <p><b>Twist:</b> {script.ending_twist}</p>
          </Card>}
        </>}
      </NeedProject>
    </>
  );
}

export { Badge, STAGES, CostApproval, get };
