import React, {CSSProperties, useEffect, useState} from "react";
import {
  AbsoluteFill, Audio, Img, cancelRender, continueRender, delayRender,
  interpolate, staticFile, useCurrentFrame,
} from "remotion";
import {useVideoConfig} from "remotion";

const W = 1080;
const H = 1920;
const FONT = "Vazirmatn, sans-serif";
type Speaker = "eli" | "elina";
type Camera = "shared" | "eli" | "elina" | "phone";
type Pose = "excited" | "curious" | "suspicious" | "neutral" | "concerned";
type Cue = {
  turn:number; speaker:Speaker; text:string; start:number; end:number; startFrame:number; endFrame:number;
  camera:Camera; beat:string; eliPose:Pose; elinaPose:Pose; rmsEnvelopeFrameStart:number;
  rmsEnvelopeDb:number[]; confidence:string;
};
type CueFile = {fps:number; durationInFrames:number; lines:Cue[]};
type CameraBeat = {kind:Camera; focus:[number,number]; target:[number,number]; scale:number; cutScale:number};
type MouthState = "closed" | "small" | "open";

const clamp = {extrapolateLeft:"clamp" as const, extrapolateRight:"clamp" as const};
const ELI_FILES:Record<string,string> = {excited:"eli_excited.png",curious:"eli_curious.png",suspicious:"eli_suspicious.png"};
const ELINA_FILES:Record<string,string> = {neutral:"elina_chair_neutral.png",concerned:"elina_chair_concerned.png"};
const ASSET = "eli_elina_test01/";
const camDefaults:Record<Camera,CameraBeat> = {
  shared:{kind:"shared",focus:[540,960],target:[540,960],scale:1,cutScale:1},
  eli:{kind:"eli",focus:[260,729],target:[540,920],scale:1.28,cutScale:1.15},
  elina:{kind:"elina",focus:[590,963],target:[540,950],scale:1.25,cutScale:1.14},
  phone:{kind:"phone",focus:[540,960],target:[540,960],scale:1,cutScale:1},
};

function img(file:string, style:CSSProperties={}) {
  return <Img src={staticFile(`${ASSET}${file}`)} style={{position:"absolute",width:"100%",height:"100%",objectFit:"fill",...style}} />;
}
function wrapRtl(text:string,maxChars:number):string[] {
  const words=text.split(/\s+/).filter(Boolean); const rows:string[]=[]; let row="";
  for (const word of words) {
    const candidate=row?`${row} ${word}`:word;
    if (row && candidate.length>maxChars) { rows.push(row); row=word; } else row=candidate;
  }
  if (row) rows.push(row);
  return rows;
}
function lineAt(cues:Cue[], sec:number):{cue:Cue;index:number;active:boolean} {
  const index=cues.findIndex(c=>sec>=c.start && sec<c.end);
  if(index>=0) return {cue:cues[index],index,active:true};
  const prior=cues.reduce((best,c,i)=>c.start<=sec?i:best,-1);
  return {cue:cues[prior<0?0:prior],index:prior<0?0:prior,active:false};
}
function mouthState(cue:Cue,frame:number):MouthState {
  const i=frame-cue.rmsEnvelopeFrameStart;
  if(i<0||i>=cue.rmsEnvelopeDb.length) return "closed";
  const values=cue.rmsEnvelopeDb.filter(v=>v>-85).slice().sort((a,b)=>a-b);
  if(values.length<3) return "closed";
  const p20=values[Math.floor((values.length-1)*.20)];
  const p72=values[Math.floor((values.length-1)*.72)];
  const value=cue.rmsEnvelopeDb[i];
  if(value<p20+3.2) return "closed";
  if(value>p72) return "open";
  return "small";
}
function PoseCrossfade({frame,cue,previous,children}:{frame:number;cue:Cue;previous?:Cue;children:(cue:Cue,opacity:number)=>React.ReactNode}) {
  if(!previous) return <>{children(cue,1)}</>;
  const s=cue.startFrame;
  const mix=interpolate(frame,[s,s+5],[0,1],clamp);
  return <>{children(previous,1-mix)}{children(cue,mix)}</>;
}

function Scene({frame,cue,previous,active}: {frame:number;cue:Cue;previous?:Cue;active:boolean}) {
  const camera=camDefaults[cue.camera];
  const elapsed=Math.max(0,frame-cue.startFrame);
  const z=interpolate(elapsed,[0,6],[camera.cutScale,camera.scale],clamp);
  const tx=camera.target[0]-z*camera.focus[0];
  const ty=camera.target[1]-z*camera.focus[1];
  const transform=`translate3d(${tx}px,${ty}px,0) scale(${z})`;
  const localFrame=frame-cue.startFrame;
  const shared=cue.camera==="shared";
  const showEli=shared||cue.camera==="eli";
  const showElina=shared||cue.camera==="elina";
  const state=active?mouthState(cue,frame):"closed";
  return <AbsoluteFill style={{overflow:"hidden",background:"#8fc5c4"}}>
    {img("room_plate.png",{transform:`scale(${shared?1.02:1.1})`,transformOrigin:"center"})}
    <div style={{position:"absolute",inset:0,transform,transformOrigin:"0 0"}}>
      {showElina && <PoseCrossfade frame={frame} cue={cue} previous={previous}>{(c,opacity)=><React.Fragment key={`elina-${c.turn}`}>
        {img(ELINA_FILES[c.elinaPose]||ELINA_FILES.neutral,{left:130,top:145,width:920,height:1636,opacity,filter:"drop-shadow(0 18px 20px rgba(25,39,42,.16))"})}
      </React.Fragment>}</PoseCrossfade>}
      {showEli && <PoseCrossfade frame={frame} cue={cue} previous={previous}>{(c,opacity)=><React.Fragment key={`eli-${c.turn}`}>
        {img(ELI_FILES[c.eliPose]||ELI_FILES.curious,{left:30,top:320,width:460,height:818,opacity,filter:"drop-shadow(0 16px 18px rgba(26,31,43,.22))"})}
      </React.Fragment>}</PoseCrossfade>}
      {active&&state!=="closed"&&cue.camera!=="phone"&&<MouthPatch speaker={cue.speaker} state={state} elinaPose={cue.elinaPose} />}
    </div>
    {cue.camera==="phone"&&<PhoneScene frame={frame} cue={cue} />}
    {cue.beat==="phone_intro"&&cue.camera==="shared"&&<PhonePulse frame={localFrame} />}
    {cue.beat==="thought_storm"&&cue.camera==="eli"&&<ThoughtStorm frame={localFrame} />}
    {cue.beat==="block_stamp"&&cue.camera==="eli"&&<BlockStamp frame={localFrame} />}
    {cue.beat==="stop_freeze"&&<StopFreeze frame={localFrame} />}
    {cue.beat==="missing_tone_labels"&&cue.camera==="shared"&&<ToneLabels frame={localFrame} />}
    {cue.beat==="mind_reading_impact"&&cue.camera==="elina"&&<ImpactFlash frame={localFrame} />}
    {cue.beat==="split_card"&&<SplitCard frame={localFrame} />}
    {cue.beat==="warm_outro"&&<WarmGlow frame={localFrame} />}
    {cue.beat==="final_gag"&&<FinalGag frame={localFrame} />}
    {cue.turn===35&&<div style={{position:"absolute",left:90,right:90,bottom:118,height:128,borderRadius:32,border:"2px solid rgba(255,255,255,.36)",background:"rgba(255,255,255,.13)"}} />}
  </AbsoluteFill>;
}

function MouthPatch({speaker,state,elinaPose}:{speaker:Speaker;state:MouthState;elinaPose:Pose}) {
  if(speaker==="eli") {
    const w=state==="small"?31:38,h=state==="small"?9:14;
    const cx=30+556*460/1080, cy=320+953*818/1920;
    return <svg aria-hidden="true" viewBox="0 0 80 36" style={{position:"absolute",left:cx-w/2,top:cy-h/2,width:w,height:h,overflow:"visible",pointerEvents:"none"}}>
      <ellipse cx="40" cy="18" rx={state==="small"?31:38} ry={state==="small"?11:16} fill="#5c4a70" opacity=".43" />
      <ellipse cx="40" cy="18" rx={state==="small"?28:35} ry={state==="small"?9:13} fill="#2b2038" />
      <path d="M13 20 Q40 32 67 20 Q40 25 13 20" fill="#b95c79" opacity=".9" />
    </svg>;
  }
  const w=state==="small"?38:48,h=state==="small"?5:9;
  const cx=elinaPose==="concerned"?594:601,cy=145+483*920/1080;
  return <svg aria-hidden="true" viewBox="0 0 60 18" preserveAspectRatio="none" style={{position:"absolute",left:cx-w/2,top:cy-h/2,width:w,height:h,overflow:"visible",pointerEvents:"none"}}>
    <path d="M2 7 Q30 3 58 7 Q30 16 2 7Z" fill="#522b32" opacity={state==="small"?".48":".68"} />
    {state==="open"&&<path d="M18 10 Q30 15 42 10 Q30 12 18 10Z" fill="#b95f67" opacity=".72" />}
  </svg>;
}
function PhonePulse({frame}:{frame:number}) {
  const alpha=interpolate(frame,[5,9,20,27],[0,1,1,0],clamp);
  return <div style={{position:"absolute",left:512,top:642,width:82,height:82,borderRadius:"50%",background:"rgba(255,211,88,.42)",border:"5px solid rgba(255,247,220,.94)",opacity:alpha,boxShadow:"0 0 0 18px rgba(255,214,99,.22)"}} />;
}
function ThoughtStorm({frame}:{frame:number}) {
  const words=["ناراحته؟","عصبانیه؟","دوستم نداره؟"];
  const opacity=interpolate(frame,[0,5],[0,1],clamp);
  return <div style={{position:"absolute",right:48,top:320,display:"flex",flexDirection:"column",alignItems:"flex-end",gap:16,opacity}}>
    {words.map((word,i)=><div key={word} dir="rtl" style={{padding:"14px 24px",borderRadius:28,background:"#fff5d4",border:"4px solid #efbd45",color:"#50396b",fontFamily:FONT,fontWeight:700,fontSize:34-i*2,textAlign:"center",transform:`rotate(${i%2?2:-2}deg)`,boxShadow:"0 12px 28px rgba(24,28,40,.22)"}}>{word}</div>)}
  </div>;
}
function BlockStamp({frame}:{frame:number}) {
  const opacity=interpolate(frame,[0,3,40,48],[0,1,1,0],clamp);
  return <div dir="rtl" style={{position:"absolute",right:56,top:370,padding:"12px 24px",background:"#ed6261",color:"white",fontFamily:FONT,fontSize:38,fontWeight:700,transform:"rotate(-8deg)",border:"5px solid #fff0dc",boxShadow:"0 12px 24px rgba(25,28,37,.25)",opacity}}>بلاکش کن!</div>;
}
function StopFreeze({frame}:{frame:number}) {
  const opacity=interpolate(frame,[0,2,28,36],[0,1,1,0],clamp);
  return <>
    <AbsoluteFill style={{background:"rgba(14,26,38,.2)",opacity}} />
    <div dir="rtl" style={{position:"absolute",left:290,top:640,width:500,textAlign:"center",fontFamily:FONT,fontSize:112,fontWeight:700,color:"#fff7d8",textShadow:"0 8px 24px rgba(27,34,47,.62)",opacity,transform:`scale(${interpolate(frame,[0,3],[.84,1],clamp)})`}}>استپ</div>
  </>;
}
function ToneLabels({frame}:{frame:number}) {
  const opacity=interpolate(frame,[0,5,55,65],[0,1,1,0],clamp);
  return <div style={{position:"absolute",top:1080,left:70,right:70,display:"flex",justifyContent:"center",gap:14,opacity}}>
    {[["؟","لحن"],["…","مکث"],["—","قیافه"]].map(([icon,label])=><div key={label} dir="rtl" style={{width:250,padding:"18px 12px",borderRadius:24,background:"rgba(255,255,255,.91)",color:"#324c54",textAlign:"center",fontFamily:FONT,fontWeight:700,fontSize:28,boxShadow:"0 8px 18px rgba(30,51,55,.15)"}}><span style={{fontSize:38,color:"#dc9a45",marginInlineEnd:10}}>{icon}</span>{label}</div>)}
  </div>;
}
function ImpactFlash({frame}:{frame:number}) {
  const opacity=interpolate(frame,[0,2,8,14],[0,.55,.2,0],clamp);
  return <AbsoluteFill style={{background:"rgba(255,227,167,.78)",opacity,mixBlendMode:"screen"}} />;
}
function SplitCard({frame}:{frame:number}) {
  const opacity=interpolate(frame,[0,4,75,88],[0,1,1,0],clamp);
  return <div style={{position:"absolute",left:65,right:65,top:1050,display:"flex",gap:16,opacity}}>
    {[["واقعیت","#d7f3e8"],["داستان ذهن","#f8d5d1"]].map(([label,color])=><div key={label} dir="rtl" style={{flex:1,minHeight:132,padding:"18px 12px",borderRadius:25,background:color,color:"#34434a",textAlign:"center",fontFamily:FONT,fontSize:30,fontWeight:700,boxShadow:"0 12px 22px rgba(27,39,42,.16)"}}>{label}<div style={{fontSize:21,marginTop:10,opacity:.78}}>{label==="واقعیت"?"یک جواب کوتاه":"ناراحته؟ عصبانیه؟"}</div></div>)}
  </div>;
}
function RewindMark({frame}:{frame:number}) {
  const opacity=interpolate(frame,[0,4,55,65],[0,1,1,0],clamp);
  return <div style={{position:"absolute",left:436,top:1290,width:208,height:208,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",background:"rgba(255,255,255,.92)",color:"#4b7580",fontSize:116,fontWeight:700,opacity,boxShadow:"0 12px 30px rgba(16,32,39,.22)"}}>↶</div>;
}
function WarmGlow({frame}:{frame:number}) {
  const alpha=interpolate(frame,[0,12,90,115],[0,.26,.22,0],clamp);
  return <AbsoluteFill style={{background:"linear-gradient(145deg,rgba(255,216,141,.45),rgba(255,237,201,.08))",opacity:alpha,pointerEvents:"none"}} />;
}
function FinalGag({frame}:{frame:number}) {
  const alpha=interpolate(frame,[0,5,60,78],[0,1,1,0],clamp);
  const scale=interpolate(frame,[0,5],[.65,1],clamp);
  return <div style={{position:"absolute",right:118,top:360,width:106,height:106,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",background:"#ffdf6b",border:"5px solid #fff9e9",color:"#51456a",fontSize:74,fontWeight:700,opacity:alpha,transform:`scale(${scale}) rotate(10deg)`,boxShadow:"0 10px 23px rgba(25,31,40,.2)"}}>✓</div>;
}

function PhoneScene({frame,cue}:{frame:number;cue:Cue}) {
  const msg=cue.beat==="chat_question"?"حالت خوبه؟ سرت شلوغه؟":cue.beat==="chat_reply"?"آره خوبم، فقط سرِ کار بودم.":"باشه";
  const sent=cue.beat==="chat_question";
  const top=cue.beat==="chat_reply"?300:250;
  const alpha=interpolate(frame-cue.startFrame,[0,5],[0,1],clamp);
  return <AbsoluteFill style={{pointerEvents:"none"}}>
    {img("room_plate.png",{filter:"blur(11px) brightness(.68)",transform:"scale(1.08)"})}
    <AbsoluteFill style={{background:"rgba(17,37,45,.30)"}} />
    <div style={{position:"absolute",left:212,top:105,width:656,height:1180,borderRadius:84,padding:20,boxSizing:"border-box",background:"linear-gradient(145deg,#26343c,#111820 58%,#34414a)",boxShadow:"0 52px 90px rgba(12,31,39,.34),inset 0 2px 5px rgba(255,255,255,.28)",transform:`scale(${interpolate(frame-cue.startFrame,[0,7],[.94,1],clamp)})`,transformOrigin:"center"}}>
      <div style={{position:"absolute",top:13,left:"50%",transform:"translateX(-50%)",width:160,height:28,borderRadius:18,background:"#111820"}} />
      <div style={{width:"100%",height:"100%",overflow:"hidden",borderRadius:66,background:"#f8f4eb",position:"relative"}}>
        <div style={{height:110,display:"flex",alignItems:"center",justifyContent:"center",background:"#e7f1ed",boxShadow:"0 3px 10px rgba(36,58,59,.08)"}}>
          <div style={{width:62,height:62,borderRadius:"50%",background:"linear-gradient(145deg,#f5c86b,#ed967e)",border:"5px solid #fff"}} />
        </div>
        <div dir="rtl" style={{position:"absolute",top,right:34,maxWidth:470,padding:"24px 28px",borderRadius:28,background:sent?"#d8f1d4":"#fff",color:"#26333a",fontFamily:FONT,fontSize:34,fontWeight:700,lineHeight:1.35,textAlign:"right",opacity:alpha,boxShadow:"0 9px 20px rgba(38,55,49,.10)"}}>{msg}</div>
        {cue.beat==="rewind"&&<div style={{position:"absolute",left:0,right:0,top:585,textAlign:"center",fontSize:132,color:"#5e8090",opacity:.72}}>↶</div>}
        <div style={{position:"absolute",bottom:42,left:36,right:36,height:64,borderRadius:42,background:"#fff",border:"2px solid #e1e5dd"}} />
        <div style={{position:"absolute",bottom:62,left:"50%",transform:"translateX(-50%)",width:25,height:25,borderRadius:"50%",background:"#e5ece8"}} />
      </div>
    </div>
  </AbsoluteFill>;
}
function Bubble({cue,active}:{cue:Cue;active:boolean}) {
  if(!active) return null;
  const rows=wrapRtl(cue.text,cue.text.length>80?39:cue.text.length>54?34:30);
  const fontSize=cue.text.length>95?30:cue.text.length>65?33:36;
  const phone=cue.camera==="phone";
  const shared=cue.camera==="shared";
  const left=phone?70:(shared?55:(cue.speaker==="eli"?54:120));
  const right=phone?70:(shared?55:(cue.speaker==="elina"?54:120));
  const top=phone?1380:(cue.beat==="missing_tone_labels"?1450:(shared?1290:95));
  const maxWidth=1080-left-right;
  return <div dir="rtl" style={{position:"absolute",zIndex:30,left,right,top,maxWidth,boxSizing:"border-box",padding:"24px 32px",borderRadius:28,background:cue.speaker==="eli"?"rgba(255,249,231,.97)":"rgba(255,255,255,.97)",border:`3px solid ${cue.speaker==="eli"?"#f0c964":"#b7ded5"}`,boxShadow:"0 13px 30px rgba(17,32,39,.22)",color:"#28353b",fontFamily:FONT,fontSize,fontWeight:700,lineHeight:1.32,textAlign:"center",unicodeBidi:"plaintext",transform:"translateY(0)"}}>
    {rows.map((r,i)=><React.Fragment key={`${cue.turn}-${i}`}>{i>0&&<br/>}{r}</React.Fragment>)}
  </div>;
}

function FullDraftContent({cues}:{cues:CueFile}) {
  const frame=useCurrentFrame(); const {fps}=useVideoConfig();
  const sec=frame/fps;
  const {cue,index,active}=lineAt(cues.lines,sec);
  const previous=index>0?cues.lines[index-1]:undefined;
  return <AbsoluteFill style={{width:W,height:H,overflow:"hidden",background:"#8fc5c4",fontFamily:FONT}}>
    <Scene frame={frame} cue={cue} previous={previous} active={active} />
    <Bubble cue={cue} active={active} />
    <Audio src={staticFile("eli_elina_full_draft_v1/full_dialogue_mix.wav")} />
    {cue.turn===35&&<div style={{position:"absolute",left:0,right:0,bottom:0,height:460,background:"linear-gradient(0deg,rgba(26,43,45,.15),transparent)",pointerEvents:"none"}} />}
  </AbsoluteFill>;
}

export const EliElinaFullDraft:React.FC = () => {
  const [cues,setCues]=useState<CueFile|null>(null);
  const [handle]=useState(()=>delayRender("Loading full dialogue cues and Vazirmatn"));
  useEffect(()=>{
    let alive=true;
    Promise.all([
      fetch(staticFile("eli_elina_full_draft_v1/full_cues.json")).then(r=>{if(!r.ok)throw new Error(`cue load ${r.status}`);return r.json() as Promise<CueFile>}),
      new FontFace("Vazirmatn",`url(${staticFile("fonts/Vazirmatn-Bold.ttf")})`,{weight:"700"}).load(),
    ]).then(([data,font])=>{
      if(!alive)return;
      document.fonts.add(font); setCues(data); continueRender(handle);
    }).catch((e)=>{console.error(e);cancelRender(e);});
    return ()=>{alive=false;};
  },[handle]);
  if(!cues) return null;
  return <FullDraftContent cues={cues} />;
};
