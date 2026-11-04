import React, {CSSProperties, useEffect, useState} from "react";
import {
  AbsoluteFill,
  Img,
  cancelRender,
  continueRender,
  delayRender,
  interpolate,
  spring,
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

// Deliberate hard cuts follow the current temporary cue timings. Speaker IDs
// and line boundaries stay in cues_test01.json for the later TTS edit.
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

function CameraScene({frame, beat, lineIndex}:{frame:number;beat:EditBeat;lineIndex:number}) {
  const {current:eliPose, previous:oldEliPose, mix:eliMix} = poseAt<Pose>(frame,lineIndex,"eliPose");
  const {current:elinaPose, previous:oldElinaPose, mix:elinaMix} = poseAt<ElinaPose>(frame,lineIndex,"elinaPose");
  const elapsed = Math.max(0, frame - Math.round(beat.start * FPS));
  const z = beat.punchFrames > 0
    ? interpolate(elapsed,[0,beat.punchFrames],[beat.cutScale,beat.scale],clamp)
    : beat.scale;
  // Keep the selected face/gesture anchored while the punch-in settles.
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

function Subtitle({line}:{line:Line}) {
  const fontSize = line.id === "p1_l5" ? 36 : line.id === "p1_l3" ? 40 : 44;
  return <div dir="rtl" style={{position:"absolute",zIndex:30,top:1410,left:68,right:68,minHeight:190,display:"flex",alignItems:"center",justifyContent:"center",textAlign:"center",padding:"0 12px",boxSizing:"border-box",color:"#fff",fontFamily:font,fontSize,fontWeight:700,lineHeight:1.28,unicodeBidi:"plaintext",textShadow:"0 3px 8px rgba(8,20,25,.98),0 1px 20px rgba(8,20,25,.9)"}}>{line.text}</div>;
}

function ReactionGraphics({frame}:{frame:number}) {
  const start = Math.round(6.66 * FPS);
  const hide = Math.round(8.25 * FPS);
  const opacity = interpolate(frame,[start,start+5,hide-5,hide],[0,1,1,0],clamp);
  const bubbles = [{x:790,y:400,size:68,delay:0},{x:875,y:335,size:82,delay:2},{x:960,y:430,size:62,delay:4}];
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

export const EliElinaCutzoomV1:React.FC = () => {
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
  return <AbsoluteFill style={{width:W,height:H,overflow:"hidden",background:"#83c0c3",fontFamily:font}}>
    {beat.kind === "phone"
      ? <PhoneCloseup frame={frame} shotStart={phoneStart} />
      : <CameraScene frame={frame} beat={beat} lineIndex={index} />}
    {beat.id === "eli-reaction" && <ReactionGraphics frame={frame} />}
    <Subtitle line={line} />
  </AbsoluteFill>;
};
