import React, {CSSProperties, useEffect, useState} from "react";
import {AbsoluteFill, Img, cancelRender, continueRender, delayRender, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import cues from "./cues_test01.json";

const W = 1080;
const H = 1920;
const FPS = cues.fps;
type Pose = "excited" | "curious" | "suspicious";
type ElinaPose = "neutral" | "concerned";
type Line = (typeof cues.lines)[number];
const phoneShot = cues.shots.find(s => s.id === "phone_closeup")!;
const mediumShot = cues.shots.find(s => s.id === "medium")!;
const messageLine = cues.lines.find(l => l.id === "p1_l4")!;
const reactionLine = cues.lines.find(l => l.id === "p1_l5")!;
const eliFile: Record<Pose,string> = {excited:"eli_excited.png", curious:"eli_curious.png", suspicious:"eli_suspicious.png"};
const elinaFile: Record<ElinaPose,string> = {neutral:"elina_chair_neutral.png", concerned:"elina_chair_concerned.png"};
const clamp = {extrapolateLeft:"clamp" as const, extrapolateRight:"clamp" as const};
const font = "Vazirmatn, sans-serif";

function portrait(src:string, style:CSSProperties={}) {
  return <Img src={staticFile(`eli_elina_test01/${src}`)} style={{position:"absolute",width:"100%",height:"100%",objectFit:"fill",...style}} />;
}
function activeLine(frame:number) {
  const sec=frame/FPS;
  const index=Math.max(0,cues.lines.findIndex(l=>sec>=l.start && sec<l.end));
  return {line:cues.lines[index] ?? cues.lines[cues.lines.length-1],index};
}
function poseBlend(frame:number,index:number,key:"eliPose"|"elinaPose") {
  const line=cues.lines[index];
  const prev=index>0 ? cues.lines[index-1] : undefined;
  const now=line[key] as Pose|ElinaPose;
  const old=prev?.[key] as Pose|ElinaPose|undefined;
  if (!prev || old===now) return {old:undefined,mix:1,pop:1};
  const start=Math.round(line.start*FPS);
  const mix=interpolate(frame,[start,start+5],[0,1],clamp);
  const p=spring({frame:Math.max(0,frame-start),fps:FPS,config:{damping:11,stiffness:250,mass:.55}});
  return {old,mix,pop:.94+p*.06};
}

function PhoneCloseup({frame}:{frame:number}) {
  const {fps}=useVideoConfig();
  const messageStart=Math.round(messageLine.start*fps);
  const pop=spring({frame:Math.max(0,frame-messageStart),fps,config:{damping:10,stiffness:210,mass:.7}});
  const bubbleOpacity=interpolate(frame,[messageStart,messageStart+Math.round(.17*fps)],[0,1],clamp);
  const bubbleScale=frame<messageStart?.15:.78+pop*.22;
  const phoneScale=interpolate(frame,[phoneShot.start*fps,(phoneShot.start+.5)*fps,phoneShot.end*fps],[.91,1,1.025],clamp);
  return <AbsoluteFill style={{background:"linear-gradient(155deg,#77b9be,#9acbc6 55%,#f0d5b7)"}}>
    {portrait("room_plate.png",{filter:"blur(9px) brightness(.72)",transform:"scale(1.08)"})}
    <AbsoluteFill style={{background:"rgba(17,37,45,.25)"}} />
    <div style={{position:"absolute",left:212,top:95,width:656,height:1166,borderRadius:84,padding:20,boxSizing:"border-box",background:"linear-gradient(145deg,#26343c,#111820 58%,#34414a)",boxShadow:"0 52px 90px rgba(12,31,39,.34),inset 0 2px 5px rgba(255,255,255,.28)",transform:`scale(${phoneScale})`,transformOrigin:"center"}}>
      <div style={{position:"absolute",top:13,left:"50%",transform:"translateX(-50%)",width:160,height:28,borderRadius:18,background:"#111820"}} />
      <div style={{width:"100%",height:"100%",overflow:"hidden",borderRadius:66,background:"#f8f4eb",position:"relative"}}>
        <div style={{height:105,display:"flex",alignItems:"center",justifyContent:"center",background:"#e7f1ed",boxShadow:"0 3px 10px rgba(36,58,59,.08)"}}><div style={{width:54,height:54,borderRadius:"50%",background:"linear-gradient(145deg,#f5c86b,#ed967e)",border:"5px solid #fff"}} /></div>
        <div style={{position:"absolute",inset:"108px 0 0",background:"linear-gradient(180deg,#f6f5ef,#f0eee6)"}} />
        <div dir="rtl" style={{position:"absolute",top:240,right:38,minWidth:220,padding:"30px 42px",borderRadius:"34px 34px 8px 34px",background:"#d8f1d4",color:"#26333a",fontFamily:font,fontWeight:700,fontSize:62,textAlign:"right",boxShadow:"0 12px 24px rgba(53,77,54,.12)",transform:`scale(${bubbleScale})`,transformOrigin:"top right",opacity:bubbleOpacity}}>باشه</div>
        <div style={{position:"absolute",bottom:42,left:36,right:36,height:64,borderRadius:42,background:"#fff",border:"2px solid #e1e5dd"}} />
        <div style={{position:"absolute",bottom:62,left:"50%",transform:"translateX(-50%)",width:25,height:25,borderRadius:"50%",background:"#e5ece8"}} />
      </div>
    </div>
  </AbsoluteFill>;
}

function Subtitle({line}:{line:Line}) {
  const eli=line.speaker==="eli";
  const label=eli?"الی":"الینا";
  const color=eli?"#ffd447":"#f08070";
  return <div style={{position:"absolute",zIndex:25,top:1320,left:70,right:70,minHeight:170,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:8}}>
    <div dir="rtl" style={{padding:"4px 22px",borderRadius:20,background:color,color:"#263139",fontFamily:font,fontSize:28,fontWeight:700,boxShadow:"0 4px 14px rgba(0,0,0,.2)"}}>{label}</div>
    <div dir="rtl" style={{width:"100%",textAlign:"center",color:"#fff",fontFamily:font,fontSize:line.id==="p1_l5"?40:44,fontWeight:700,lineHeight:1.28,textShadow:"0 3px 7px rgba(12,25,29,.95),0 1px 20px rgba(12,25,29,.8)",unicodeBidi:"plaintext"}}>{line.text}</div>
  </div>;
}

function ThoughtBubbles({frame}:{frame:number}) {
  const start=Math.round((reactionLine.start+.12)*FPS);
  const fadeStart=Math.round((reactionLine.end+.45)*FPS);
  const fadeEnd=fadeStart+Math.round(.67*FPS);
  const visible=interpolate(frame,[start,start+5,fadeStart,fadeEnd],[0,1,1,0],clamp);
  const items=[{x:84,y:380,d:0,s:70},{x:176,y:302,d:3,s:84},{x:287,y:385,d:6,s:64}];
  return <>{items.map((it,i)=>{
    const p=spring({frame:Math.max(0,frame-start-it.d),fps:FPS,config:{damping:10,stiffness:210,mass:.55}});
    const orbit=Math.sin((frame+i*19)/17)*9;
    return <div key={i} style={{position:"absolute",zIndex:12,left:it.x,top:it.y+orbit,width:it.s,height:it.s,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",background:"#fff8df",border:"5px solid #ffc83e",color:"#6648a3",fontFamily:font,fontSize:50,fontWeight:700,opacity:visible,transform:`scale(${Math.max(.03,p)})`,boxShadow:"0 10px 22px rgba(29,24,42,.24)"}}>؟</div>;
  })}</>;
}

export const EliElinaTest01:React.FC=()=>{
  const frame=useCurrentFrame();
  const {fps}=useVideoConfig();
  const [fontHandle]=useState(()=>delayRender("Loading bundled Vazirmatn"));
  useEffect(()=>{
    const f=new FontFace("Vazirmatn",`url(${staticFile("fonts/Vazirmatn-Bold.ttf")})`,{weight:"700"});
    f.load().then(loaded=>{document.fonts.add(loaded);continueRender(fontHandle);}).catch(err=>cancelRender(err));
  },[fontHandle]);

  const {line,index}=activeLine(frame);
  const sec=frame/fps;
  const phoneStart=Math.round(phoneShot.start*fps), phoneEnd=Math.round(phoneShot.end*fps);
  const mediumStart=Math.round(mediumShot.start*fps), reactStart=Math.round(reactionLine.start*fps);
  const fade=5;
  const close=sec>=phoneShot.start && sec<phoneShot.end;
  const medium=sec>=mediumShot.start;
  const sceneAlpha=frame<phoneStart?1:frame<phoneStart+fade?interpolate(frame,[phoneStart,phoneStart+fade],[1,0],clamp):frame<phoneEnd-fade?0:frame<phoneEnd?interpolate(frame,[phoneEnd-fade,phoneEnd],[0,1],clamp):1;
  const phoneAlpha=close?1-sceneAlpha:0;
  const camera=medium?interpolate(frame,[mediumStart,cues.durationSeconds*fps],[1.015,1.075],clamp):1.025;
  const eliBlend=poseBlend(frame,index,"eliPose"), elinaBlend=poseBlend(frame,index,"elinaPose");
  const eliPose=line.eliPose as Pose, elinaPose=line.elinaPose as ElinaPose;
  const eliBounce=line.speaker==="eli"?Math.sin((frame-line.start*fps)*.8)*8:0;
  const elinaBounce=line.speaker==="elina"?Math.sin((frame-line.start*fps)*.8)*5:0;
  const breath=1+Math.sin(frame/38)*.005, tilt=Math.sin(frame/47)*.12;
  const buzzStart=Math.round((cues.lines[0].start+1)*fps), buzzEnd=buzzStart+Math.round(.5*fps);
  const buzz=Math.max(0,Math.sin((frame-buzzStart)*1.8))*interpolate(frame,[buzzStart,buzzEnd],[1,0],clamp);
  const buzzOpacity=frame>=buzzStart&&frame<buzzEnd?.34+buzz*.34:0;
  const shakeX=frame>=buzzStart&&frame<buzzEnd?Math.sin(frame*8.4)*3:0;
  const shakeY=frame>=buzzStart&&frame<buzzEnd?Math.cos(frame*7.1)*1.8:0;
  const entry=Math.round((cues.lines[0].start+.13)*fps);
  const entrySpring=spring({frame:Math.max(0,frame-entry),fps,config:{damping:8,stiffness:190,mass:.58}});
  const entryOpacity=interpolate(frame,[entry,entry+7],[0,1],clamp);
  const entryScale=frame<entry+12?.84+entrySpring*.16:1;
  const kinPop=spring({frame:Math.max(0,frame-reactStart-Math.round(.18*fps)),fps,config:{damping:9,stiffness:240,mass:.5}});
  const kinOpacity=medium?interpolate(frame,[reactStart,reactStart+5,Math.round(reactionLine.end*fps),Math.round((reactionLine.end+.5)*fps)],[0,1,1,0],clamp):0;
  const roomShift=Math.sin(frame/105)*8;

  const elinaStyle:CSSProperties={left:130,top:145,width:920,height:1636,transform:`translate(${shakeX}px,${elinaBounce+shakeY}px) scale(${breath}) rotate(${tilt}deg)`,transformOrigin:"50% 80%",filter:"drop-shadow(0 18px 22px rgba(21,40,42,.14))"};
  const eliStyle:CSSProperties={left:30,top:320,width:460,height:818,transform:`translateY(${Math.sin(frame/14)*13+eliBounce}px) rotate(${Math.sin(frame/31)*1.5}deg) scale(${entryScale})`,transformOrigin:"50% 70%",filter:"drop-shadow(0 16px 18px rgba(26,31,43,.23))"};

  return <AbsoluteFill style={{width:W,height:H,overflow:"hidden",background:"#84c4c5",fontFamily:font}}>
    <div style={{position:"absolute",inset:-70,width:W+140,height:H+140,transform:`translateX(${roomShift}px) scale(${camera})`,transformOrigin:"center"}}>{portrait("room_plate.png")}</div>
    <div style={{position:"absolute",inset:0,opacity:sceneAlpha,pointerEvents:"none"}}>
      <div style={{position:"absolute",inset:0,transform:`scale(${camera})`,transformOrigin:"center"}}>
        {portrait(elinaFile[elinaPose],{...elinaStyle,opacity:elinaBlend.mix})}
        {elinaBlend.old&&portrait(elinaFile[elinaBlend.old as ElinaPose],{...elinaStyle,opacity:1-elinaBlend.mix})}
        <div style={{position:"absolute",left:375,top:820,width:205,height:310,borderRadius:70,opacity:buzzOpacity,filter:"blur(9px)",background:"radial-gradient(ellipse,rgba(255,217,99,.74),rgba(255,186,80,0))",transform:`translate(${Math.sin(frame*2.3)*6}px,${Math.cos(frame*2.8)*4}px)`}} />
      </div>
      <div style={{position:"absolute",inset:0,transform:`scale(${camera})`,transformOrigin:"center"}}>
        {portrait(eliFile[eliPose],{...eliStyle,opacity:entryOpacity*eliBlend.mix,transform:`${eliStyle.transform} scale(${eliBlend.pop})`})}
        {eliBlend.old&&portrait(eliFile[eliBlend.old as Pose],{...eliStyle,opacity:entryOpacity*(1-eliBlend.mix)})}
      </div>
      {medium&&<>
        <div dir="rtl" style={{position:"absolute",left:70,top:965,zIndex:15,opacity:kinOpacity,transform:`scale(${Math.max(.01,kinPop)}) rotate(-6deg)`,transformOrigin:"center",fontFamily:font,fontSize:96,fontWeight:700,color:"#ffe06a",WebkitTextStroke:"3px #503876",paintOrder:"stroke fill",textShadow:"0 8px 16px rgba(23,25,37,.44)"}}>همین؟!</div>
        <ThoughtBubbles frame={frame} />
      </>}
      <div style={{position:"absolute",zIndex:16,left:375,top:820,width:205,height:310,borderRadius:70,opacity:buzzOpacity,border:"4px solid rgba(255,227,125,.7)",boxShadow:"0 0 55px 24px rgba(255,206,91,.58)",transform:`translate(${Math.sin(frame*2.6)*5}px,${Math.cos(frame*2.8)*3}px)`}} />
    </div>
    <div style={{position:"absolute",inset:0,opacity:phoneAlpha,pointerEvents:"none"}}><PhoneCloseup frame={frame} /></div>
    <Subtitle line={line} />
  </AbsoluteFill>;
};
