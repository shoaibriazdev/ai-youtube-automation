import React, { useEffect, useState } from "react";
import { del, fileUrl, post, put, usd } from "./api.js";
import { Badge, Card, ErrorBox, Field, JobBar, Modal, NeedProject, ProjectPicker, StageRunner, STAGES, useApp, useJob, useLoad } from "./components.jsx";

function ProviderSelect({ kind, settings, onSaved }) {
  const [v, setV] = useState(settings?.providers?.[kind]);
  useEffect(() => setV(settings?.providers?.[kind]), [settings, kind]);
  if (!settings) return null;
  const notes = { ...settings.options.free_notes, ...settings.options.paid_notes };
  return (
    <div className="row">
      <select value={v} style={{ maxWidth: 240 }} onChange={async (e) => { setV(e.target.value); await put("/settings/providers", { ...settings.providers, [kind]: e.target.value }); onSaved && onSaved(); }}>
        {settings.options[kind].map((p) => <option key={p} value={p}>{p}{settings.options.free_notes[p] ? " (free)" : " (paid)"}</option>)}
      </select>
      <span className="small muted">{notes[v] || ""}</span>
    </div>
  );
}

/* ---------------- 5. Character Library ---------------- */
const EMPTY = { name: "", species: "cat", personality: "", visual_dna: "", palette: ["#F28C28", "#FFFFFF", "#333333"], catchphrase: "", voice: { edge: { voice: "en-US-GuyNeural", rate: "+0%", pitch: "+0Hz" }, openai: { voice: "alloy" }, elevenlabs: { voice_id: "" }, sapi: {} } };

export function Characters() {
  const [chars, reload] = useLoad("/characters");
  const [voices] = useLoad("/voices");
  const [edit, setEdit] = useState(null);
  const [err, setErr] = useState(null);
  const [bust, setBust] = useState(0);
  const { job, error, start } = useJob(() => { reload(); setBust(Date.now()); });
  const save = async () => { setErr(null); try { await post("/characters", edit); setEdit(null); reload(); } catch (e) { setErr(e.message); } };
  const testVoice = async (c, provider) => {
    setErr(null);
    const r = await fetch(`/api/characters/${c.id}/voice-test`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ provider }) });
    if (!r.ok) { setErr((await r.json()).detail); return; }
    new Audio(URL.createObjectURL(await r.blob())).play();
  };
  const v = (p, k, val) => setEdit({ ...edit, voice: { ...edit.voice, [p]: { ...(edit.voice?.[p] || {}), [k]: val } } });
  return (
    <>
      <Card title="Recurring original characters" right={<button className="btn primary small" onClick={() => setEdit(JSON.parse(JSON.stringify(EMPTY)))}>+ New character</button>}>
        <p className="small muted">Consistency: every image prompt embeds the character's exact <b>visual DNA</b>, uses a fixed <b>seed</b>, and the reference sheet is reused. Voices are mapped per provider so each character always sounds the same.</p>
        <JobBar job={job} /><ErrorBox error={error || err} />
        <div className="grid g2">
          {(chars || []).map((c) => (
            <div className="card" key={c.id} style={{ marginBottom: 0 }}>
              <div className="charcard">
                <div>{c.reference_image ? <img src={`/api/characters/${c.id}/image?b=${bust}`} alt={c.name} /> : <div className="muted small" style={{ width: 110, height: 110, display: "grid", placeItems: "center", border: "1px dashed var(--line)", borderRadius: 10 }}>no sheet yet</div>}</div>
                <div>
                  <div className="row"><b>{c.name}</b><span className="badge">{c.species}</span>{(c.palette || []).map((p) => <span key={p} className="swatch" style={{ background: p }} />)}<span className="spacer" />
                    <span className="small muted">seed {c.seed}</span></div>
                  <div className="small">{c.personality}</div>
                  <div className="small muted" style={{ marginTop: 4 }}>DNA: {c.visual_dna || "—"}</div>
                  {c.catchphrase && <div className="small" style={{ marginTop: 4 }}>“{c.catchphrase}”</div>}
                  <div className="row" style={{ marginTop: 8 }}>
                    <button className="btn small" onClick={() => setEdit(JSON.parse(JSON.stringify(c)))}>Edit</button>
                    {c.species !== "narrator" && <button className="btn small" onClick={() => start(post(`/characters/${c.id}/reference`))}>Generate reference sheet</button>}
                    <button className="btn small" onClick={() => testVoice(c)}>▶ Voice</button>
                    <button className="btn small danger" onClick={async () => { if (confirm(`Delete ${c.name}?`)) { await del(`/characters/${c.id}`); reload(); } }}>Delete</button>
                  </div>
                </div>
              </div>
            </div>))}
        </div>
      </Card>
      {edit && (
        <Modal title={edit.id ? `Edit ${edit.name}` : "New character"} onClose={() => setEdit(null)} actions={<><button className="btn" onClick={() => setEdit(null)}>Cancel</button><button className="btn primary" onClick={save}>Save</button></>}>
          <div className="grid g2">
            <Field label="Name"><input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></Field>
            <Field label="Species"><select value={edit.species} onChange={(e) => setEdit({ ...edit, species: e.target.value })}>{["cat", "dog", "owl", "human", "hamster", "parrot", "rabbit", "raccoon", "narrator", "other"].map((s) => <option key={s}>{s}</option>)}</select></Field>
          </div>
          <Field label="Personality"><textarea value={edit.personality} onChange={(e) => setEdit({ ...edit, personality: e.target.value })} /></Field>
          <Field label="Visual DNA (exact look, reused in every prompt)"><textarea value={edit.visual_dna} onChange={(e) => setEdit({ ...edit, visual_dna: e.target.value })} /></Field>
          <div className="grid g2">
            <Field label="Catchphrase"><input value={edit.catchphrase} onChange={(e) => setEdit({ ...edit, catchphrase: e.target.value })} /></Field>
            <Field label="Palette (3 hex colours)"><input value={(edit.palette || []).join(", ")} onChange={(e) => setEdit({ ...edit, palette: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} /></Field>
            <Field label="Edge voice (free)"><select value={edit.voice?.edge?.voice || ""} onChange={(e) => v("edge", "voice", e.target.value)}>{(voices?.edge || []).map((x) => <option key={x}>{x}</option>)}</select></Field>
            <Field label="Edge pitch / rate"><div className="row"><input value={edit.voice?.edge?.pitch || "+0Hz"} onChange={(e) => v("edge", "pitch", e.target.value)} /><input value={edit.voice?.edge?.rate || "+0%"} onChange={(e) => v("edge", "rate", e.target.value)} /></div></Field>
            <Field label="OpenAI voice"><select value={edit.voice?.openai?.voice || "alloy"} onChange={(e) => v("openai", "voice", e.target.value)}>{(voices?.openai || []).map((x) => <option key={x}>{x}</option>)}</select></Field>
            <Field label="ElevenLabs voice" hint={voices?.elevenlabs_error || (!voices?.elevenlabs?.length ? "Add ELEVENLABS_API_KEY to list your voices" : "")}>
              <select value={edit.voice?.elevenlabs?.voice_id || ""} onChange={(e) => v("elevenlabs", "voice_id", e.target.value)}><option value="">—</option>{(voices?.elevenlabs || []).map((x) => <option key={x.voice_id} value={x.voice_id}>{x.name}</option>)}</select></Field>
          </div>
        </Modal>)}
    </>
  );
}

/* ---------------- 6. Image Generation ---------------- */
export function Images() {
  const { project, reloadProject } = useApp();
  const [settings, reloadS] = useLoad("/settings");
  const imgs = project?.assets?.images || {};
  return (
    <>
      <Card title="Project & provider"><ProjectPicker /><div style={{ marginTop: 10 }}><ProviderSelect kind="image" settings={settings} onSaved={reloadS} /></div>
        <p className="small muted">Free: <b>storyboard</b> (offline cartoon frames, preview quality) and <b>pollinations</b> (free community AI, rate-limited, small watermark without a token). Paid: OpenAI, Stability, Replicate — need keys in API Settings.</p></Card>
      <NeedProject>{project && <>
        <Card title="Generate scene images">
          {!project.script && <div className="alert warn">Write the script first.</div>}
          <div className="row"><StageRunner project={project} stages={["characters", "images"]} label={Object.keys(imgs).length ? "Generate missing images" : "Generate images"} onDone={reloadProject} />
            {Object.keys(imgs).length > 0 && <StageRunner project={project} stages={["images"]} force label="Regenerate all" primary={false} onDone={reloadProject} />}</div>
        </Card>
        <Card title="Scenes">
          <div className="gallery">
            {(project.script?.scenes || []).map((s) => (
              <figure key={s.n}>{imgs[s.n] ? <img src={fileUrl(project.id, imgs[s.n])} alt={`scene ${s.n}`} /> : <div className="muted small" style={{ padding: 30 }}>not generated</div>}
                <figcaption><b>Scene {s.n}.</b> {project.assets?.prompts?.[s.n] || s.visual}</figcaption></figure>))}
            {imgs.thumb && <figure><img src={fileUrl(project.id, imgs.thumb)} alt="thumb background" /><figcaption>Thumbnail background</figcaption></figure>}
          </div>
        </Card></>}
      </NeedProject>
    </>
  );
}

/* ---------------- 7. Video Generation ---------------- */
export function VideoGen() {
  const { project, reloadProject } = useApp();
  const [settings, reloadS] = useLoad("/settings");
  const [opts, setOpts] = useState(null);
  useEffect(() => { if (settings) setOpts(settings.provider_options); }, [settings]);
  const clips = project?.assets?.clips || {};
  return (
    <>
      <Card title="Project & provider"><ProjectPicker /><div style={{ marginTop: 10 }}><ProviderSelect kind="video" settings={settings} onSaved={reloadS} /></div>
        {opts && <div className="grid g4" style={{ marginTop: 10 }}>
          <Field label="Seconds per AI clip"><input type="number" min="5" max="10" value={opts.video_clip_seconds} onChange={(e) => setOpts({ ...opts, video_clip_seconds: +e.target.value })} /></Field>
          <Field label="Max AI clips per video"><input type="number" min="1" max="20" value={opts.max_ai_video_scenes} onChange={(e) => setOpts({ ...opts, max_ai_video_scenes: +e.target.value })} /></Field>
          <Field label="Replicate video model"><input value={opts.replicate_video_model} onChange={(e) => setOpts({ ...opts, replicate_video_model: e.target.value })} /></Field>
          <Field label="Runway / Luma model"><div className="row"><input value={opts.runway_model} onChange={(e) => setOpts({ ...opts, runway_model: e.target.value })} /><input value={opts.luma_model} onChange={(e) => setOpts({ ...opts, luma_model: e.target.value })} /></div></Field>
          <button className="btn" onClick={async () => { await put("/settings/provider_options", opts); reloadS(); }}>Save options</button></div>}
        <p className="small muted"><b>kenburns</b> is free: the editor animates each still image with pan/zoom. AI clip providers (Runway, Luma, Replicate) are paid; scenes beyond the max, or whose clip fails, fall back to Ken Burns automatically.</p>
      </Card>
      <NeedProject>{project && <>
        <Card title="Generate clips"><StageRunner project={project} stages={["video"]} label="Generate video clips" onDone={reloadProject} /></Card>
        <Card title="Clips">{Object.keys(clips).length ? <div className="gallery">{Object.entries(clips).map(([n, f]) => <figure key={n}><video src={fileUrl(project.id, f)} controls muted /><figcaption>Scene {n}</figcaption></figure>)}</div>
          : <p className="muted">No AI clips — scenes will use Ken Burns motion.</p>}</Card></>}
      </NeedProject>
    </>
  );
}

/* ---------------- 8. Voiceover Studio ---------------- */
export function Voice() {
  const { project, reloadProject, go } = useApp();
  const [settings, reloadS] = useLoad("/settings");
  const voice = project?.assets?.voice || {};
  return (
    <>
      <Card title="Project & voice provider"><ProjectPicker /><div style={{ marginTop: 10 }}><ProviderSelect kind="tts" settings={settings} onSaved={reloadS} /></div>
        <p className="small muted">Each character's voice per provider is set in the <a href="#characters" onClick={() => go("characters")}>Character Library</a>. Switching provider regenerates all lines. Emotion and delivery notes from the script adjust pace (Edge) or are sent as acting instructions (OpenAI) / style (ElevenLabs).</p></Card>
      <NeedProject>{project && <>
        <Card title="Generate voiceovers"><div className="row"><StageRunner project={project} stages={["voice"]} label="Generate voiceovers" onDone={reloadProject} />
          {Object.keys(voice).length > 0 && <StageRunner project={project} stages={["voice"]} force label="Regenerate all" primary={false} onDone={reloadProject} />}</div></Card>
        <Card title="Dialogue lines">
          <table><thead><tr><th>Scene</th><th>Character</th><th>Line</th><th>Audio</th><th>Sec</th></tr></thead><tbody>
            {(project.script?.scenes || []).flatMap((s) => s.dialogue.map((d, i) => {
              const v = voice[`${s.n}-${i}`];
              return <tr key={`${s.n}-${i}`}><td>{s.n}</td><td>{d.character}</td><td className="small">{d.line}<div className="muted">{d.emotion} · {d.delivery}</div></td>
                <td>{v ? <audio controls preload="none" src={fileUrl(project.id, v.file)} style={{ height: 32 }} /> : <span className="muted small">—</span>}</td><td>{v?.duration}</td></tr>;
            }))}
          </tbody></table>
        </Card></>}
      </NeedProject>
    </>
  );
}

/* ---------------- 9. Video Editor ---------------- */
export function Pipeline({ project, onDone }) {
  const done = project.stages || {};
  const next = STAGES.filter((s) => !done[s]);
  return (
    <div>
      <div className="stages">{STAGES.map((s) => <span key={s} className={`stage ${done[s] ? "done" : ""} ${project.row?.stage === s && project.row?.status === "running" ? "cur" : ""}`}>{done[s] ? "✓ " : ""}{s}</span>)}</div>
      <div className="row" style={{ marginTop: 10 }}>
        <StageRunner project={project} stages={next.length ? next : STAGES.slice(1)} label={next.length ? `Run remaining (${next.length})` : "Re-run all"} onDone={onDone} />
      </div>
      {project.row?.error && <div className="alert err">Last error: {project.row.error}</div>}
    </div>
  );
}

export function Editor() {
  const { project, reloadProject, reloadProjects } = useApp();
  const [settings, reloadS] = useLoad("/settings");
  const [r, setR] = useState(null);
  const [aspects, setAspects] = useState([]);
  const [err, setErr] = useState(null);
  useEffect(() => { if (settings) setR(settings.render); }, [settings]);
  useEffect(() => { if (project) setAspects(project.export_aspects || [project.format === "short" ? "9:16" : "16:9"]); }, [project?.id]);
  const outs = project?.render?.outputs || {};
  const toggle = (a) => setAspects(aspects.includes(a) ? aspects.filter((x) => x !== a) : [...aspects, a]);
  const approve = async (ok) => { setErr(null); try { await post(`/projects/${project.id}/approve`, { approved: ok }); reloadProject(); reloadProjects(); } catch (e) { setErr(e.message); } };
  return (
    <>
      <Card title="Project"><ProjectPicker /></Card>
      <NeedProject>{project && <>
        <Card title="Production pipeline"><Pipeline project={project} onDone={reloadProject} /></Card>
        <div className="grid g2">
          <Card title="Edit settings">
            {r && <>
              <div className="grid g2">
                <Field label="Quality"><select value={r.quality} onChange={(e) => setR({ ...r, quality: e.target.value })}><option value="draft">draft (720p, fast)</option><option value="hd">HD (1080p)</option></select></Field>
                <Field label="Transition"><select value={r.transition} onChange={(e) => setR({ ...r, transition: e.target.value })}>{["fade", "slideleft", "wipeleft", "circleopen", "none"].map((t) => <option key={t}>{t}</option>)}</select></Field>
                <Field label="Transition seconds"><input type="number" step="0.1" min="0.1" max="1.5" value={r.transition_seconds} onChange={(e) => setR({ ...r, transition_seconds: +e.target.value })} /></Field>
                <Field label="Min scene seconds"><input type="number" step="0.1" value={r.min_scene_seconds} onChange={(e) => setR({ ...r, min_scene_seconds: +e.target.value })} /></Field>
                <Field label={`Music volume ${r.music_volume}`}><input type="range" min="0" max="0.5" step="0.01" value={r.music_volume} onChange={(e) => setR({ ...r, music_volume: +e.target.value })} /></Field>
                <Field label={`SFX volume ${r.sfx_volume}`}><input type="range" min="0" max="1" step="0.05" value={r.sfx_volume} onChange={(e) => setR({ ...r, sfx_volume: +e.target.value })} /></Field>
                <Field label="Words per caption"><input type="number" min="1" max="10" value={r.subtitle_words_per_caption} onChange={(e) => setR({ ...r, subtitle_words_per_caption: +e.target.value })} /></Field>
                <Field label="Subtitles"><label className="row"><input type="checkbox" checked={r.subtitles} onChange={(e) => setR({ ...r, subtitles: e.target.checked })} /> burn in captions</label></Field>
              </div>
              <div className="row" style={{ marginBottom: 10 }}>Export: <label className="row"><input type="checkbox" checked={aspects.includes("9:16")} onChange={() => toggle("9:16")} /> 9:16 vertical</label>
                <label className="row"><input type="checkbox" checked={aspects.includes("16:9")} onChange={() => toggle("16:9")} /> 16:9 horizontal</label></div>
              <div className="row"><button className="btn" onClick={async () => { await put("/settings/render", r); await put(`/projects/${project.id}/options`, { export_aspects: aspects }); reloadS(); reloadProject(); }}>Save settings</button>
                <StageRunner project={project} stages={["edit"]} extra={{ aspects }} label="Render video" onDone={reloadProject} /></div>
              <p className="small muted">Music and SFX are synthesized originals. Drop your own licensed files into <span className="mono">assets/music</span> and <span className="mono">assets/sfx</span> to replace them.</p>
            </>}
          </Card>
          <Card title="Review & approve">
            {Object.keys(outs).length === 0 && <p className="muted">No render yet.</p>}
            {Object.entries(outs).map(([a, o]) => (
              <div key={a} className="video-wrap" style={{ marginBottom: 12 }}>
                <div className="row small"><b>{a}</b><span className="muted">{o.width}×{o.height} · {o.duration}s · {o.size_mb} MB</span><span className="spacer" /><a href={fileUrl(project.id, o.file)} download>Download MP4</a><a href={fileUrl(project.id, o.srt)} download>SRT</a></div>
                <video controls src={fileUrl(project.id, o.file)} style={{ maxHeight: a === "9:16" ? 560 : 360 }} />
              </div>))}
            {Object.keys(outs).length > 0 && <div className="row">
              {project.row?.approved ? <><Badge s="approved">approved by you</Badge><button className="btn small" onClick={() => approve(false)}>Withdraw approval</button></>
                : <button className="btn primary" onClick={() => approve(true)}>✓ I watched it — approve for upload</button>}</div>}
            <ErrorBox error={err} />
          </Card>
        </div></>}
      </NeedProject>
    </>
  );
}
