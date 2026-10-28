// قالب فيديو "دليل الذكي". الإيجنت بيبعت المشاهد كـ props، والقالب بيحسب المدة من الصوت.
import React, {useEffect, useState} from 'react';
import {
  AbsoluteFill, Audio, Composition, Sequence, registerRoot, spring, interpolate,
  useCurrentFrame, useVideoConfig, staticFile, delayRender, continueRender, Easing,
} from 'remotion';

const C = {ink: '#17142b', yellow: '#ffd84d', purple: '#8a4fbf', white: '#fff', red: '#e5484d', green: '#20b07a'};
const BG = {
  a: 'radial-gradient(110% 70% at 50% 10%,#3b2a7a 0%,#141033 60%,#0b0a1c 100%)',
  b: 'radial-gradient(110% 70% at 20% 0%,#1d3f73 0%,#0e1a35 60%,#070c1a 100%)',
  light: 'linear-gradient(170deg,#f6f3ff 0%,#e9e4fb 100%)',
};
// TikTok/Reels UI covers the bottom ~20% and the right edge: keep text out of there.
const SAFE = {top: 190, bottom: 560, right: 150, left: 72};

const f = (name) => staticFile(`fonts/${name}.woff2`);
const fontCss = `
@font-face{font-family:Readex;src:url(${f('readex-pro-latin-700-normal')});font-weight:700;unicode-range:U+0000-00FF}
@font-face{font-family:Readex;src:url(${f('readex-pro-arabic-700-normal')});font-weight:700}
@font-face{font-family:Plex;src:url(${f('ibm-plex-sans-arabic-latin-400-normal')});font-weight:400;unicode-range:U+0000-00FF}
@font-face{font-family:Plex;src:url(${f('ibm-plex-sans-arabic-latin-600-normal')});font-weight:600;unicode-range:U+0000-00FF}
@font-face{font-family:Plex;src:url(${f('ibm-plex-sans-arabic-arabic-400-normal')});font-weight:400}
@font-face{font-family:Plex;src:url(${f('ibm-plex-sans-arabic-arabic-600-normal')});font-weight:600}
`;

const Fonts = () => {
  const [handle] = useState(() => delayRender('fonts'));
  useEffect(() => {
    Promise.all(['700 40px Readex', '400 40px Plex', '600 40px Plex'].map((x) => document.fonts.load(x, 'دليل AI 123')))
      .then(() => document.fonts.ready).then(() => continueRender(handle));
  }, [handle]);
  return <style>{fontCss}</style>;
};

const useSpring = (delay = 0, config = {damping: 14, mass: 0.7}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return spring({frame: frame - delay, fps, config});
};

// "قوالب [[جاهزة]] لكل مناسبة" -> words, with the bracketed part highlighted
const parseTitle = (title) => {
  const out = [];
  title.split(/(\[\[.+?\]\])/).forEach((part) => {
    if (!part) return;
    const hl = part.startsWith('[[');
    const text = hl ? part.slice(2, -2) : part;
    if (hl) out.push({w: text, hl: true});
    else text.split(/\s+/).filter(Boolean).forEach((w) => out.push({w, hl: false}));
  });
  return out;
};

const Title = ({title, size = 96, start = 0, every = 4, dark = true, center = false}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={{display: 'flex', flexWrap: 'wrap', gap: '0 22px', fontFamily: 'Readex', fontWeight: 700, fontSize: size,
      lineHeight: 1.42, justifyContent: center ? 'center' : 'flex-start'}}>
      {parseTitle(title).map(({w, hl}, i) => {
        const s = spring({frame: frame - start - i * every, fps, config: {damping: 12, mass: 0.6}});
        return (
          <span key={i} style={{display: 'inline-block', opacity: s, transform: `translateY(${(1 - s) * 40}px) scale(${0.8 + 0.2 * s})`,
            background: hl ? (dark ? C.yellow : C.purple) : 'transparent', color: hl ? (dark ? C.ink : C.white) : undefined,
            padding: hl ? '0 16px' : 0, borderRadius: 14}}>{w}</span>
        );
      })}
    </div>
  );
};

const Typewriter = ({text, start = 0, cps = 30}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const n = Math.max(0, Math.floor(((frame - start) / fps) * cps));
  return <span>{text.slice(0, n)}{n < text.length && frame >= start ? <span style={{opacity: Math.floor(frame / 8) % 2 ? 1 : 0.2}}>|</span> : null}</span>;
};

// Subtitles follow the real word timings from the voice; without voice they are spread evenly.
const Caption = ({scene}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const t = frame / fps;
  const words = scene.words?.length
    ? scene.words
    : scene.voice.replace('[تأكد]', '').split(/\s+/).filter(Boolean).map((w, i, arr) => {
      const span = (durationInFrames / fps - 0.4) / arr.length;
      return {text: w, start: 0.2 + i * span, end: 0.2 + (i + 1) * span};
    });
  const shown = words.filter((w) => w.start <= t).length;
  if (!shown) return null;
  // show one short chunk at a time so hidden words never leave empty boxes
  const CHUNK = 6;
  const from = Math.floor((shown - 1) / CHUNK) * CHUNK;
  const chunk = words.slice(from, from + CHUNK);
  return (
    <div style={{position: 'absolute', left: SAFE.left, right: SAFE.right, bottom: SAFE.bottom - 150, textAlign: 'center'}}>
      <span style={{background: 'rgba(0,0,0,.75)', color: C.white, fontFamily: 'Plex', fontWeight: 600, fontSize: 46, lineHeight: 1.7,
        padding: '6px 22px', borderRadius: 16, boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone'}}>
        {chunk.map((w, i) => <span key={i} style={{color: from + i === shown - 1 ? C.yellow : C.white}}>{w.text}{i < chunk.length - 1 ? ' ' : ''}</span>)}
      </span>
    </div>
  );
};

const Frame = ({bg, dark = true, scene, handle, children}) => {
  const frame = useCurrentFrame();
  const enter = interpolate(frame, [0, 10], [1, 0], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
  const zoom = interpolate(frame, [0, 150], [1, 1.04], {extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill style={{background: bg, direction: 'rtl', color: dark ? C.white : C.ink, fontFamily: 'Plex',
      transform: `translateX(${-enter * 1080}px)`}}>
      <AbsoluteFill style={{padding: `${SAFE.top}px ${SAFE.right}px ${SAFE.bottom}px ${SAFE.left}px`, display: 'flex',
        flexDirection: 'column', justifyContent: 'center', gap: 50, transform: `scale(${zoom})`}}>
        {children}
      </AbsoluteFill>
      <Caption scene={scene} />
      <div style={{position: 'absolute', top: 100, right: SAFE.right, fontSize: 32, opacity: 0.8, direction: 'ltr'}}>{handle}</div>
      <div style={{position: 'absolute', top: 100, left: SAFE.left, fontSize: 30, opacity: 0.8}}>#إعلان</div>
    </AbsoluteFill>
  );
};

const Chips = ({items, start = 20, dark = true}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={{display: 'flex', gap: 18, flexWrap: 'wrap'}}>
      {items.map((t, i) => {
        const s = spring({frame: frame - start - i * 6, fps});
        return <span key={i} style={{background: dark ? 'rgba(255,255,255,.12)' : C.ink, color: C.white, border: dark ? '2px solid rgba(255,255,255,.3)' : 'none',
          borderRadius: 99, padding: '12px 34px', fontSize: 42, opacity: s, transform: `translateY(${(1 - s) * 30}px)`}}>{t}</span>;
      })}
    </div>
  );
};

const kinds = {
  hook: ({scene, handle}) => (
    <Frame bg={BG.a} scene={scene} handle={handle}><Title title={scene.title} size={104} /></Frame>
  ),
  problem: ({scene, handle}) => {
    const frame = useCurrentFrame();
    const shake = Math.sin(frame / 2) * interpolate(frame, [20, 30, 40], [0, 6, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    return (
      <Frame bg={BG.b} scene={scene} handle={handle}>
        <div style={{fontSize: 150, transform: `translateX(${shake}px)`, color: C.red, fontFamily: 'Readex', lineHeight: 1}}>×</div>
        <Title title={scene.title} size={92} start={6} />
      </Frame>
    );
  },
  before_after: ({scene, handle}) => {
    const a = useSpring(10);
    const b = useSpring(34);
    return (
      <Frame bg={BG.light} dark={false} scene={scene} handle={handle}>
        <Title title={scene.title} size={84} dark={false} />
        <div style={{opacity: a, transform: `translateX(${(1 - a) * 200}px)`, border: '3px dashed #c9c2e6', borderRadius: 30,
          padding: '28px 34px', fontSize: 42, lineHeight: 1.55, color: '#6b6585'}}>
          <div style={{fontSize: 30, fontWeight: 600, marginBottom: 6}}>قبل</div>{scene.before}</div>
        <div style={{opacity: b, transform: `translateX(${(1 - b) * -200}px)`, background: C.white, borderRadius: 30, padding: '28px 34px',
          fontSize: 42, lineHeight: 1.55, boxShadow: '0 30px 80px rgba(60,40,120,.22)'}}>
          <div style={{fontSize: 30, fontWeight: 600, marginBottom: 6, color: C.purple}}>بعد</div>
          <Typewriter text={scene.after} start={40} /></div>
      </Frame>
    );
  },
  feature: ({scene, handle, index}) => (
    <Frame bg={index % 2 ? BG.b : BG.a} scene={scene} handle={handle}>
      <Title title={scene.title} size={96} />
      {scene.bullets?.length ? <Chips items={scene.bullets} start={18} /> : null}
    </Frame>
  ),
  offer: ({scene, handle}) => {
    const frame = useCurrentFrame();
    const {fps} = useVideoConfig();
    const s = useSpring(4);
    return (
      <Frame bg={BG.a} scene={scene} handle={handle}>
        <div style={{transform: `scale(${0.85 + 0.15 * s})`, transformOrigin: 'right', opacity: s}}><Title title={scene.title} size={110} /></div>
        {(scene.bullets || []).map((b, i) => {
          const x = spring({frame: frame - 16 - i * 8, fps});
          return <div key={i} style={{fontSize: 50, opacity: x, display: 'flex', gap: 20, alignItems: 'center'}}>
            <span style={{color: C.green, fontFamily: 'Readex'}}>✓</span>{b}</div>;
        })}
      </Frame>
    );
  },
  cta: ({scene, handle}) => {
    const frame = useCurrentFrame();
    return (
      <Frame bg={BG.a} scene={scene} handle={handle}>
        <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 44, textAlign: 'center'}}>
          <div style={{fontFamily: 'Readex', fontSize: 160, color: C.yellow, lineHeight: 1, transform: `translateY(${Math.sin(frame / 5) * 18}px)`}}>↑</div>
          <div style={{background: C.yellow, color: C.ink, fontFamily: 'Readex', fontSize: 76, padding: '20px 60px', borderRadius: 99,
            transform: `scale(${1 + Math.sin(frame / 6) * 0.04})`}}>الرابط بالبايو</div>
          <Title title={scene.title} size={80} start={10} center />
          <div style={{fontSize: 32, opacity: 0.75}}>#إعلان · رابط عمولة</div>
        </div>
      </Frame>
    );
  },
};

const sceneFrames = (sc, fps, minSeconds) => Math.ceil(Math.max(minSeconds, (sc.seconds || 0) + 0.35) * fps);

const Progress = ({total}) => {
  const frame = useCurrentFrame();
  return <div style={{position: 'absolute', top: 60, left: SAFE.left, right: SAFE.right, height: 8, borderRadius: 4, background: 'rgba(255,255,255,.2)'}}>
    <div style={{height: '100%', width: `${(frame / total) * 100}%`, background: C.yellow, borderRadius: 4, marginLeft: 'auto'}} />
  </div>;
};

const Promo = ({scenes, handle, audioDir, minSeconds}) => {
  const {fps, durationInFrames} = useVideoConfig();
  let from = 0;
  return (
    <AbsoluteFill style={{background: '#0b0a1c'}}>
      <Fonts />
      {scenes.map((sc, i) => {
        const d = sceneFrames(sc, fps, minSeconds);
        const K = kinds[sc.kind] || kinds.feature;
        const el = (
          <Sequence key={i} from={from} durationInFrames={d}>
            <K scene={sc} handle={handle} index={i} />
            {sc.audio ? <Audio src={staticFile(`${audioDir}/${sc.audio}`)} /> : null}
          </Sequence>
        );
        from += d;
        return el;
      })}
      <Progress total={durationInFrames} />
    </AbsoluteFill>
  );
};

// Cover image for the article page and Pinterest (2:3)
const Cover = ({title, productName, handle}) => (
  <AbsoluteFill style={{background: BG.a, direction: 'rtl', color: C.white, fontFamily: 'Plex', padding: 80,
    display: 'flex', flexDirection: 'column', justifyContent: 'space-between'}}>
    <Fonts />
    <div style={{fontSize: 34, opacity: 0.8, direction: 'ltr', textAlign: 'right'}}>{handle}</div>
    <div style={{display: 'flex', flexDirection: 'column', gap: 40}}>
      <span style={{alignSelf: 'flex-start', background: C.yellow, color: C.ink, fontFamily: 'Readex', fontSize: 44,
        padding: '8px 30px', borderRadius: 99}}>{productName}</span>
      <div style={{fontFamily: 'Readex', fontSize: 82, lineHeight: 1.4}}>{title}</div>
    </div>
    <div style={{fontSize: 30, opacity: 0.7}}>دليل الذكي · شرح بالعربي</div>
  </AbsoluteFill>
);

const sample = {
  handle: '@daleel.ai', audioDir: 'audio/sample', minSeconds: 2.6,
  scenes: [
    {kind: 'hook', title: 'لسا بتدفع [[لمصمم]] على كل بوست؟', voice: 'لسا بتدفع لمصمم على كل بوست لمشروعك؟'},
    {kind: 'cta', title: 'الرابط [[بالبايو]]', voice: 'الرابط بالبايو'},
  ],
};

const Root = () => (
  <>
    <Composition id="Promo" component={Promo} fps={30} width={1080} height={1920} durationInFrames={300} defaultProps={sample}
      calculateMetadata={({props}) => ({durationInFrames: props.scenes.reduce((a, sc) => a + sceneFrames(sc, 30, props.minSeconds), 0)})} />
    <Composition id="Cover" component={Cover} fps={30} width={1000} height={1500} durationInFrames={1}
      defaultProps={{title: 'كيف تصمم بوستات مشروعك بنفسك', productName: 'Canva', handle: '@daleel.ai'}} />
  </>
);

registerRoot(Root);
