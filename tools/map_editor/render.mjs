// Tile references come from the same C++ selector used in the ROM.
export function renderOverview(tileMap, art, step=4, decorations=null, spawns=null, spawnTypes=null, spawnProfiles=null) {
  const tileSize=8/step, side=1024*tileSize, pixels=new Uint8ClampedArray(side*side*4);
  const colors=new Uint8ClampedArray(art.tiles.length/64*tileSize*tileSize*4);
  for(let tile=0;tile<art.tiles.length/64;++tile)for(let y=0;y<tileSize;++y)for(let x=0;x<tileSize;++x){
    const rgb=[0,0,0];
    for(let yy=0;yy<step;++yy)for(let xx=0;xx<step;++xx){
      const index=art.tiles[tile*64+(y*step+yy)*8+x*step+xx]*3;
      for(let c=0;c<3;++c)rgb[c]+=art.palette[index+c];
    }
    colors.set([...rgb.map(v=>Math.round(v/(step*step))),255],(tile*tileSize*tileSize+y*tileSize+x)*4);
  }
  for(let ty=0;ty<1024;++ty)for(let tx=0;tx<1024;++tx){
    const tile=art.refs[tileMap[ty*1024+tx]];
    const decor=decorations?.[ty*1024+tx]??0;
    if(decor){
      for(let y=0;y<tileSize;++y)for(let x=0;x<tileSize;++x){
        const rgb=[0,0,0];
        for(let yy=0;yy<step;++yy)for(let xx=0;xx<step;++xx){
          const at=(y*step+yy)*8+x*step+xx,index=(art.decoration[decor*64+at]||art.tiles[tile*64+at])*3;
          for(let c=0;c<3;++c)rgb[c]+=art.palette[index+c];
        }
        pixels.set([...rgb.map(v=>Math.round(v/(step*step))),255],((ty*tileSize+y)*side+tx*tileSize+x)*4);
      }
      continue;
    }
    for(let y=0;y<tileSize;++y){
      const source=(tile*tileSize*tileSize+y*tileSize)*4;
      pixels.set(colors.subarray(source,source+tileSize*4),((ty*tileSize+y)*side+tx*tileSize)*4);
    }
  }
  if(spawns)for(let i=0;i<spawns.length;i+=2){
    const cx=Math.floor(spawns[i]/step),cy=Math.floor(spawns[i+1]/step),r=Math.max(2,Math.floor(12/step));
    const color=spawnProfiles?.find(profile=>profile.id==spawnTypes?.[i/2])?.color??'#f04040';
    const rgb=[1,3,5].map(offset=>parseInt(color.slice(offset,offset+2),16));
    for(let d=-r;d<=r;++d)for(const [x,y] of [[cx+d,cy],[cx,cy+d]])if(x>=0&&y>=0&&x<side&&y<side)pixels.set([...rgb,255],(y*side+x)*4);
  }
  return {pixels,side};
}
const crcTable=Uint32Array.from({length:256},(_,n)=>{
  for(let k=0;k<8;++k)n=n&1?0xedb88320^(n>>>1):n>>>1;
  return n>>>0;
});
function chunk(type,data){
  const out=new Uint8Array(data.length+12),view=new DataView(out.buffer);
  view.setUint32(0,data.length);out.set(new TextEncoder().encode(type),4);out.set(data,8);
  let crc=0xffffffff;
  for(let i=4;i<out.length-4;++i)crc=crcTable[(crc^out[i])&255]^(crc>>>8);
  view.setUint32(out.length-4,(crc^0xffffffff)>>>0);return out;
}
// Stream indexed PNG rows without allocating an 8192-square RGBA canvas.
export async function renderFullPng(tileMap,art,onProgress=()=>{},decorations=null,spawns=null,spawnTypes=null,spawnProfiles=null) {
  const size=8192,compression=new CompressionStream('deflate'),writer=compression.writable.getWriter();
  const compressed=new Response(compression.readable).arrayBuffer();
  for(let ty=0;ty<1024;++ty){
    const stripe=new Uint8Array((size+1)*8);
    for(let tx=0;tx<1024;++tx){
      const tile=art.refs[tileMap[ty*1024+tx]]*64;
      const decor=decorations?.[ty*1024+tx]??0;
      for(let y=0;y<8;++y)for(let x=0;x<8;++x)
        stripe[y*(size+1)+1+tx*8+x]=(decor?art.decoration[decor*64+y*8+x]:0)||art.tiles[tile+y*8+x];
    }
    if(spawns)for(let i=0;i<spawns.length;i+=2){
      const cx=spawns[i],cy=spawns[i+1];
      const color=spawnProfiles?.find(profile=>profile.id==spawnTypes?.[i/2])?.color??'#f04040',rgb=[1,3,5].map(offset=>parseInt(color.slice(offset,offset+2),16));
      let palette=15,best=Infinity;for(let p=0;p<art.palette.length/3;++p){const d=(art.palette[p*3]-rgb[0])**2+(art.palette[p*3+1]-rgb[1])**2+(art.palette[p*3+2]-rgb[2])**2;if(d<best){best=d;palette=p;}}
      for(let y=ty*8;y<ty*8+8;++y)if(Math.abs(y-cy)<=12)
        for(let dx=-12;dx<=12;++dx)if((Math.abs(dx)<=1 || Math.abs(y-cy)<=1)&&cx+dx>=0&&cx+dx<size)stripe[(y-ty*8)*(size+1)+1+cx+dx]=palette;
    }
    await writer.write(stripe);
    if(ty%32===0)onProgress(Math.round(ty/1024*100));
  }
  await writer.close();
  const header=new Uint8Array(13),view=new DataView(header.buffer);
  view.setUint32(0,size);view.setUint32(4,size);header[8]=8;header[9]=3;
  return new Blob([new Uint8Array([137,80,78,71,13,10,26,10]),chunk('IHDR',header),
    chunk('PLTE',new Uint8Array(art.palette)),chunk('IDAT',new Uint8Array(await compressed)),chunk('IEND',new Uint8Array())],{type:'image/png'});
}
