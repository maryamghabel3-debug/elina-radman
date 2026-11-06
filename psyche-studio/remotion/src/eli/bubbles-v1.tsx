import React, {CSSProperties, useEffect, useState} from "react";
import {
  AbsoluteFill,
  Img,
  cancelRender,
  continueRender,
  delayRender,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import cues from "./cues_test01.json";

const W = 1080;
const H = 1920;
const FPS = cues.fps;
const font = "Vazirmatn, sans-serif";
type Pose = "excited" | "curious" | "suspicious";
type ElinaPose = "neutral" | "concerned";
type Line = (typeof cues.lines)[number];
type CameraKind = "shared" | "eli" | "elina" | "phone";
type EditBeat = {
  id: string;
  start: number;
  end: number;
  kind: CameraKind;
  focus: [number, number];
  target: [number, number];
  cutScale: number;
  scale: number;
  punchFrames: number;
};
type MouthState = "closed" | "small" | "open";
type BubblePlan = {
  text: string;
  key: string;
  startFrame: number;
  caption?: boolean;
};

// Keep the already-approved shot order, punch-ins, phone close-up, and reaction.
// These are the same camera beats as cutzoom-v1.tsx; this separate entry only
// changes dialogue presentation and adds a restrained mouth-state prototype.
const EDIT: EditBeat[] = [
  {id:"shared-open", start:0, end:.75, kind:"shared", focus:[540,960], target:[540,960], cutScale:1, scale:1, punchFrames:0},
  {id:"eli-first-beat", start:.75, end:2.15, kind:"eli", focus:[235,720], target:[540,820], cutScale:1.18, scale:1.30, punchFrames:6},
  {id:"elina-first-reply", start:2.15, end:3.5, kind:"elina", focus:[590,445], target:[540,760], cutScale:1.16, scale:1.26, punchFrames:6},
  {id:"eli-question", start:3.5, end:4.45, kind:"eli", focus:[235,720], target:[540,820], cutScale:1.18, scale:1.30, punchFrames:5},
  {id:"phone-message", start:4.45, end:6.5, kind:"phone", focus:[540,960], target:[540,960], cutScale:1, scale:1, punchFrames:0},
  {id:"eli-reaction", start:6.5, end:10.05, kind:"eli", focus:[250,730], target:[540,820], cutScale:1.18, scale:1.32, punchFrames:6},
  {id:"elina-reaction", start:10.05, end:11.15, kind:"elina", focus:[590,445], target:[540,760], cutScale:1.17, scale:1.27, punchFrames:6},
  {id:"shared-finish", start:11.15, end:12, kind:"shared", focus:[540,960], target:[540,960], cutScale:1.04, scale:1.04, punchFrames:0},
];

const eliFile: Record<Pose,string> = {
  excited:"eli_excited.png",
  curious:"eli_curious.png",
  suspicious:"eli_suspicious.png",
};
const elinaFile: Record<ElinaPose,string> = {
  neutral:"elina_chair_neutral.png",
  concerned:"elina_chair_concerned.png",
};
const clamp = {extrapolateLeft:"clamp" as const, extrapolateRight:"clamp" as const};

function image(src:string, style:CSSProperties={}) {
  return <Img src={staticFile(`eli_elina_test01/${src}`)} style={{position:"absolute",width:"100%",height:"100%",objectFit:"fill",...style}} />;
}

function lineAt(frame:number) {
  const sec = frame / FPS;
  const index = Math.max(0, cues.lines.findIndex((line) => sec >= line.start && sec < line.end));
  return {line:cues.lines[index] ?? cues.lines[cues.lines.length - 1], index};
}

function beatAt(sec:number):EditBeat {
  return EDIT.find((beat) => sec >= beat.start && sec < beat.end) ?? EDIT[EDIT.length - 1];
}

function poseAt<T extends Pose | ElinaPose>(frame:number, index:number, key:"eliPose"|"elinaPose") {
  const current = cues.lines[index][key] as T;
  const previous = index > 0 ? cues.lines[index - 1][key] as T : undefined;
  if (!previous || previous === current) return {current, previous:undefined as T|undefined, mix:1};
  const start = Math.round(cues.lines[index].start * FPS);
  return {current, previous, mix:interpolate(frame,[start,start+4],[0,1],clamp)};
}

function stableHash(value:string) {
  let hash = 2166136261;
  for (let i=0;i<value.length;i++) hash = Math.imul(hash ^ value.charCodeAt(i),16777619);
  return hash >>> 0;
}

// Silent-cue prototype only: deterministic irregular 10–14-frame cycles,
// with brief closed holds at punctuation pauses. Not phoneme or audio sync.
function mouthStateAt(line:Line, frame:number):MouthState {
  const start = Math.round(line.start * FPS);
  const elapsed = Math.max(0,frame-start-4); // let a pose crossfade settle first
  const pauses:Record<string,Array<[number,number]>> = {
    p1_l2:[[17,24]],
    p1_l3:[[15,20]],
    p1_l5:[[40,47],[70,76],[91,97]],
    p1_l6:[[14,21]],
  };
  if ((pauses[line.id] ?? []).some(([a,b]) => frame-start >= a && frame-start < b)) return "closed";
  let cycle=0, consumed=0, period=10;
  while (consumed <= elapsed) {
    period = 10 + (stableHash(`${line.id}-${cycle}`) % 5);
    if (elapsed < consumed + period) break;
    consumed += period;
    cycle++;
  }
  const phase = elapsed - consumed;
  const closedFrames = Math.round(period * .58);
  const smallEnd = Math.round(period * .86);
  if (phase < closedFrames) return "closed";
  if (phase < smallEnd) return "small";
  return "open";
}

function MouthOverlay({speaker,eliPose,elinaPose,state}:{speaker:string;eliPose:Pose;elinaPose:ElinaPose;state:MouthState}) {
  if (state === "closed") return null;
  if (speaker === "eli") {
    // eli_excited already contains an open grin. Avoid covering it with an
    // unstable repair patch; animate only the clean closed-smile poses.
    if (eliPose === "excited") return null;
    const width = state === "small" ? 31 : 38;
    const height = state === "small" ? 9 : 14;
    const cx = 30 + 556 * 460 / 1080;
    const cy = 320 + 953 * 818 / 1920;
    return <svg aria-hidden="true" viewBox="0 0 80 36" style={{position:"absolute",left:cx-width/2,top:cy-height/2,width,height,overflow:"visible",pointerEvents:"none"}}>
      <ellipse cx="40" cy="18" rx={state === "small" ? 31 : 38} ry={state === "small" ? 11 : 16} fill="#5c4a70" opacity=".43" />
      <ellipse cx="40" cy="18" rx={state === "small" ? 28 : 35} ry={state === "small" ? 9 : 13} fill="#2b2038" />
      <path d="M13 20 Q40 32 67 20 Q40 25 13 20" fill="#b95c79" opacity=".9" />
    </svg>;
  }
  if (speaker === "elina") {
    const width = state === "small" ? 38 : 48;
    const height = state === "small" ? 5 : 9;
    const cx = elinaPose === "concerned" ? 594 : 601;
    const cy = 145 + 483 * 920 / 1080;
    return <svg aria-hidden="true" viewBox="0 0 60 18" preserveAspectRatio="none" style={{position:"absolute",left:cx-width/2,top:cy-height/2,width,height,overflow:"visible",pointerEvents:"none"}}>
      <path d="M2 7 Q30 3 58 7 Q30 16 2 7Z" fill="#522b32" opacity={state === "small" ? ".48" : ".68"} />
      {state === "open" && <path d="M18 10 Q30 15 42 10 Q30 12 18 10Z" fill="#b95f67" opacity=".72" />}
    </svg>;
  }
  return null;
}

function CameraScene({frame,beat,line,lineIndex,mouthState}:{frame:number;beat:EditBeat;line:Line;lineIndex:number;mouthState:MouthState}) {
  const {current:eliPose, previous:oldEliPose, mix:eliMix} = poseAt<Pose>(frame,lineIndex,"eliPose");
  const {current:elinaPose, previous:oldElinaPose, mix:elinaMix} = poseAt<ElinaPose>(frame,lineIndex,"elinaPose");
  const elapsed = Math.max(0, frame - Math.round(beat.start * FPS));
  const z = beat.punchFrames > 0
    ? interpolate(elapsed,[0,beat.punchFrames],[beat.cutScale,beat.scale],clamp)
    : beat.scale;
  const tx = beat.target[0] - z * beat.focus[0];
  const ty = beat.target[1] - z * beat.focus[1];
  const camera = `translate3d(${tx}px,${ty}px,0) scale(${z})`;
  const shared = beat.kind === "shared";
  const showEli = shared || beat.kind === "eli";
  const showElina = shared || beat.kind === "elina";
  const entry = interpolate(frame,[0,5],[0,1],clamp);
  const backgroundScale = shared ? 1.02 : 1.10;
  return <AbsoluteFill style={{overflow:"hidden",background:"#83c0c3"}}>
    {image("room_plate.png",{transform:`scale(${backgroundScale})`,transformOrigin:"center"})}
    <div style={{position:"absolute",inset:0,transform:camera,transformOrigin:"0 0"}}>
      {showElina && <>
        {image(elinaFile[elinaPose],{left:130,top:145,width:920,height:1636,opacity:elinaMix,filter:"drop-shadow(0 18px 20px rgba(25,39,42,.16))"})}
        {oldElinaPose && image(elinaFile[oldElinaPose],{left:130,top:145,width:920,height:1636,opacity:1-elinaMix,filter:"drop-shadow(0 18px 20px rgba(25,39,42,.16))"})}
      </>}
      {showEli && <>
        {image(eliFile[eliPose],{left:30,top:320,width:460,height:818,opacity:eliMix*(shared?entry:1),filter:"drop-shadow(0 16px 18px rgba(26,31,43,.22))"})}
        {oldEliPose && image(eliFile[oldEliPose],{left:30,top:320,width:460,height:818,opacity:(1-eliMix)*(shared?entry:1),filter:"drop-shadow(0 16px 18px rgba(26,31,43,.22))"})}
      </>}
      {beat.kind === "eli" && line.speaker === "eli" && <MouthOverlay speaker="eli" eliPose={eliPose} elinaPose={elinaPose} state={mouthState} />}
      {beat.kind === "elina" && line.speaker === "elina" && <MouthOverlay speaker="elina" eliPose={eliPose} elinaPose={elinaPose} state={mouthState} />}
      {beat.kind === "shared" && line.speaker === "eli" && <MouthOverlay speaker="eli" eliPose={eliPose} elinaPose={elinaPose} state={mouthState} />}
      {beat.kind === "shared" && line.speaker === "elina" && <MouthOverlay speaker="elina" eliPose={eliPose} elinaPose={elinaPose} state={mouthState} />}
      {beat.id === "shared-open" && <Notification frame={frame} />}
    </div>
  </AbsoluteFill>;
}

function Notification({frame}:{frame:number}) {
  const opacity = interpolate(frame,[7,11,19,24],[0,1,1,0],clamp);
  return <div style={{position:"absolute",left:528,top:650,width:58,height:58,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",opacity,background:"#ffd34e",border:"5px solid #fff8e7",color:"#4c3d2c",fontFamily:font,fontSize:34,fontWeight:700,boxShadow:"0 0 0 12px rgba(255,214,99,.23),0 8px 18px rgba(20,35,38,.2)"}}>!</div>;
}

function PhoneCloseup({frame,shotStart}:{frame:number;shotStart:number}) {
  const messageStart = Math.round(cues.lines.find((line) => line.id === "p1_l4")!.start * FPS);
  const elapsed = Math.max(0, frame - shotStart);
  const phoneScale = interpolate(elapsed,[0,6],[.94,1],clamp);
  const messageOpacity = interpolate(frame,[messageStart,messageStart+5],[0,1],clamp);
  const messageScale = interpolate(frame,[messageStart,messageStart+6],[.88,1],clamp);
  return <AbsoluteFill style={{background:"linear-gradient(155deg,#77b9be,#9acbc6 55%,#efd1b1)"}}>
    {image("room_plate.png",{filter:"blur(10px) brightness(.68)",transform:"scale(1.08)"})}
    <AbsoluteFill style={{background:"rgba(17,37,45,.28)"}} />
    <div style={{position:"absolute",left:212,top:95,width:656,height:1166,borderRadius:84,padding:20,boxSizing:"border-box",background:"linear-gradient(145deg,#26343c,#111820 58%,#34414a)",boxShadow:"0 52px 90px rgba(12,31,39,.34),inset 0 2px 5px rgba(255,255,255,.28)",transform:`scale(${phoneScale})`,transformOrigin:"center"}}>
      <div style={{position:"absolute",top:13,left:"50%",transform:"translateX(-50%)",width:160,height:28,borderRadius:18,background:"#111820"}} />
      <div style={{width:"100%",height:"100%",overflow:"hidden",borderRadius:66,background:"#f8f4eb",position:"relative"}}>
        <div style={{height:105,display:"flex",alignItems:"center",justifyContent:"center",background:"#e7f1ed",boxShadow:"0 3px 10px rgba(36,58,59,.08)"}}><div style={{width:54,height:54,borderRadius:"50%",background:"linear-gradient(145deg,#f5c86b,#ed967e)",border:"5px solid #fff"}} /></div>
        <div style={{position:"absolute",inset:"108px 0 0",background:"linear-gradient(180deg,#f6f5ef,#f0eee6)"}} />
        <div dir="rtl" style={{position:"absolute",top:240,right:38,minWidth:260,padding:"30px 42px",borderRadius:"34px 34px 8px 34px",background:"#d8f1d4",color:"#26333a",fontFamily:font,fontWeight:700,fontSize:60,textAlign:"center",whiteSpace:"nowrap",boxShadow:"0 12px 24px rgba(53,77,54,.12)",transform:`scale(${messageScale})`,transformOrigin:"top right",opacity:messageOpacity}}>«باشه»</div>
        <div style={{position:"absolute",bottom:42,left:36,right:36,height:64,borderRadius:42,background:"#fff",border:"2px solid #e1e5dd"}} />
        <div style={{position:"absolute",bottom:62,left:"50%",transform:"translateX(-50%)",width:25,height:25,borderRadius:"50%",background:"#e5ece8"}} />
      </div>
    </div>
  </AbsoluteFill>;
}

function ReactionGraphics({frame}:{frame:number}) {
  const start = Math.round(6.66 * FPS);
  const hide = Math.round(8.25 * FPS);
  const opacity = interpolate(frame,[start,start+5,hide-5,hide],[0,1,1,0],clamp);
  const bubbles = [{x:340,y:310,size:68,delay:0},{x:440,y:220,size:82,delay:2},{x:545,y:330,size:62,delay:4}];
  const wordStart = Math.round(6.63 * FPS);
  const wordHide = Math.round(7.75 * FPS);
  const wordOpacity = interpolate(frame,[wordStart,wordStart+4,wordHide-5,wordHide],[0,1,1,0],clamp);
  const wordScale = interpolate(frame,[wordStart,wordStart+6],[.82,1],clamp);
  return <>
    {bubbles.map((bubble,i) => {
      const pop = interpolate(frame,[start+bubble.delay,start+bubble.delay+5],[.55,1],clamp);
      return <div key={i} style={{position:"absolute",zIndex:14,left:bubble.x,top:bubble.y,width:bubble.size,height:bubble.size,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",background:"#fff8df",border:"5px solid #ffc83e",color:"#6648a3",fontFamily:font,fontSize:48,fontWeight:700,opacity,transform:`scale(${pop})`,transformOrigin:"center",boxShadow:"0 10px 22px rgba(29,24,42,.24)"}}>؟</div>;
    })}
    <div dir="rtl" style={{position:"absolute",zIndex:16,left:58,top:1050,opacity:wordOpacity,transform:`scale(${wordScale}) rotate(-5deg)`,transformOrigin:"center",fontFamily:font,fontSize:98,fontWeight:700,color:"#ffe06a",WebkitTextStroke:"3px #503876",paintOrder:"stroke fill",textShadow:"0 8px 16px rgba(23,25,37,.44)"}}>همین؟!</div>
  </>;
}

function wrapPersian(text:string,maxChars=34) {
  const words = text.trim().split(/\s+/);
  const lines:string[]=[];
  let current="";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (current && next.length > maxChars) { lines.push(current); current=word; }
    else current=next;
  }
  if (current) lines.push(current);
  if (lines.length <= 2) return lines.join("\n");
  // Keep the two-line cap. Prefer a balanced split while preserving all cue text.
  return `${lines.slice(0,lines.length-1).join(" ")}\n${lines[lines.length-1]}`;
}

function bubblePlan(line:Line,frame:number):BubblePlan {
  const lineStart = Math.round(line.start * FPS);
  if (line.id === "p1_l5") {
    const splitFrame = Math.round(8.15 * FPS);
    if (frame < splitFrame) return {text:"فقط باشه؟",key:`${line.id}-a`,startFrame:lineStart};
    return {text:"نه سلامی، نه استیکری، نه هیچی؟",key:`${line.id}-b`,startFrame:splitFrame};
  }
  if (line.id === "p1_l4") return {text:"فقط نوشته «باشه». ",key:line.id,startFrame:lineStart,caption:true};
  return {text:wrapPersian(line.text),key:line.id,startFrame:lineStart};
}

function BubbleTail({side}:{side:"left"|"right"|"center"}) {
  const pointX = side === "left" ? 23 : side === "right" ? 55 : 40;
  const leftPath = `M2 2 L76 2 L${pointX} 58 Z`;
  const innerX = side === "left" ? 24 : side === "right" ? 54 : 40;
  const innerPath = `M7 6 L69 6 L${innerX} 49 Z`;
  const placeLeft = side === "left" ? 24 : side === "center" ? "calc(50% - 40px)" : undefined;
  return <svg aria-hidden="true" width="80" height="62" viewBox="0 0 80 62" style={{position:"absolute",left:placeLeft,right:side === "right" ? 24 : undefined,bottom:-42,zIndex:0,overflow:"visible"}}>
    <path d={leftPath} fill="#e97f72" />
    <path d={innerPath} fill="#fff7ec" />
  </svg>;
}

function DialogueBubble({line,frame,beat}:{line:Line;frame:number;beat:EditBeat}) {
  // Do not put the question bubble over the phone shot during the six-frame edit overlap.
  if (beat.kind === "phone" && line.id !== "p1_l4") return null;
  const plan = bubblePlan(line,frame);
  if (plan.caption && frame < plan.startFrame) return null;
  const elapsed = frame - plan.startFrame;
  const opacity = interpolate(elapsed,[0,4],[0,1],clamp);
  const scale = interpolate(elapsed,[0,4],[.9,1],clamp);
  const eli = line.speaker === "eli";
  const shared = beat.kind === "shared";
  const phone = plan.caption;
  const placement = phone
    ? {left:310,top:1335,width:460,tail:"none" as const}
    : shared
      ? eli
        ? {left:20,top:50,width:520,tail:"center" as const}
        : {left:20,top:50,width:520,tail:"right" as const}
      : eli && line.id === "p1_l5"
        ? {left:610,top:430,width:440,tail:"left" as const}
        : eli
          ? {left:485,top:230,width:565,tail:"left" as const}
          : {left:24,top:225,width:540,tail:"right" as const};
  const visibleText = phone ? plan.text.trim() : plan.text;
  const tail = placement.tail;
  return <div aria-label={visibleText} style={{position:"absolute",left:placement.left,top:placement.top,width:placement.width,zIndex:40,opacity,transform:`scale(${scale})`,transformOrigin:eli?"bottom left":"bottom right",pointerEvents:"none",fontFamily:font}}>
    {tail !== "none" && <BubbleTail side={tail} />}
    <div dir="rtl" style={{position:"relative",zIndex:1,boxSizing:"border-box",width:"100%",padding:phone?"10px 18px":"16px 23px",borderRadius:phone?22:26,background:"#fff7ec",border:`4px solid ${phone?"#e97f72":"#e97f72"}`,boxShadow:"0 12px 28px rgba(38,33,35,.2)",color:"#392e2b",fontSize:phone?26:32,fontWeight:700,lineHeight:1.25,textAlign:"center",unicodeBidi:"plaintext",whiteSpace:"pre-line",overflowWrap:"anywhere"}}>{visibleText}</div>
  </div>;
}

export const EliElinaBubblesV1:React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const [fontHandle] = useState(() => delayRender("Loading bundled Vazirmatn"));
  useEffect(() => {
    const face = new FontFace("Vazirmatn",`url(${staticFile("fonts/Vazirmatn-Bold.ttf")})`,{weight:"700"});
    face.load().then((loaded) => {document.fonts.add(loaded);continueRender(fontHandle);}).catch(cancelRender);
  },[fontHandle]);
  const {line,index} = lineAt(frame);
  const beat = beatAt(frame / fps);
  const phoneStart = Math.round(beat.start * fps);
  const mouthState = line.speaker ? mouthStateAt(line,frame) : "closed";
  return <AbsoluteFill style={{width:W,height:H,overflow:"hidden",background:"#83c0c3",fontFamily:font}}>
    {beat.kind === "phone"
      ? <PhoneCloseup frame={frame} shotStart={phoneStart} />
      : <CameraScene frame={frame} beat={beat} line={line} lineIndex={index} mouthState={mouthState} />}
    {beat.id === "eli-reaction" && <ReactionGraphics frame={frame} />}
    {line.speaker && <DialogueBubble line={line} frame={frame} beat={beat} />}
  </AbsoluteFill>;
};
